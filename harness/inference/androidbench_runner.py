# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Run on a single SWE-Bench instance."""

import datetime
import time
import traceback
from pathlib import Path
import logging
import litellm
from minisweagent.models import get_model
from minisweagent.run.extra.swebench import (
    ProgressTrackingAgent,
    get_sb_environment,
)

from minisweagent.run.extra.utils.batch_progress import RunBatchProgressManager
from minisweagent.run.utils.save import save_traj
from minisweagent.utils.log import logger
import threading
from litellm.integrations.custom_logger import CustomLogger
from .multimedia_processing_agent import MultimediaProcessingAgent


class ThreadedCustomLogger(CustomLogger):
    """
    Routes LiteLLM callbacks to thread-specific loggers.
    This is a global logger that is registered with litellm.
    To separate logs for different instances, we register a logger for each
    instance and keep the mapping.For each hook call we first get the
    current thread id and then look up the logger for that thread id to route the logs.
    """

    def __init__(self):
        super().__init__()
        self.loggers = {}  # thread_id -> logger
        self.lock = threading.Lock()

    def register_logger(self, thread_id, logger):
        with self.lock:
            self.loggers[thread_id] = logger

    def unregister_logger(self, thread_id):
        with self.lock:
            self.loggers.pop(thread_id, None)

    def _get_logger(self):
        return self.loggers.get(threading.get_ident())

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        """
        These logs isolate the specific message payloads that trigger
        retriable exceptions during LLM completion calls. While the full conversation is stored
        in the trajectory file, these logs provide a targeted view of the exact inputs causing
        API failures, facilitating faster debugging of edge cases or malformed prompts.
        """
        if logger := self._get_logger():
            logger.debug("On Failure: Information")
            messages = kwargs.get("messages")
            last_user_message = last_assistant_message = ""
            if messages and isinstance(messages, list) and len(messages) > 2:
                for m in reversed(messages):
                    if not last_user_message and m.get("role") == "user":
                        last_user_message = m
                    if not last_assistant_message and m.get("role") == "assistant":
                        last_assistant_message = m
                    if last_user_message and last_assistant_message:
                        break
                logger.debug(f"Last llm response: {last_assistant_message}")
                logger.debug(f"Last llm-issued command response: {last_user_message}")
            logger.debug(f"Optional Params: {kwargs.get('optional_params')}")
            logger.debug(f"Call Type: {kwargs.get('call_type')}")


# Initialize and register the global custom logger
_threaded_custom_logger = ThreadedCustomLogger()
litellm.callbacks.append(_threaded_custom_logger)


def save_patch(patch: str, path: Path, logger: logging.Logger):
    if patch.startswith("diff --git"):
        logger.debug(f"Saving patch to {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(patch)
    else:
        logger.warning(f"Agent did not output patch: {patch}")


def get_traj_output_path(traj_output_dir: Path, instance_id: str) -> Path:
    """Get the trajectory output path."""
    return traj_output_dir / f"{instance_id}.json"


def get_patch_output_path(patch_output_dir: Path, instance_id: str) -> Path:
    """Get the patch output path."""
    return patch_output_dir / f"{instance_id}.patch"


def setup_logger(i_id, log_dir):
    # Setup task-specific logger
    task_logger = logging.getLogger(f"minisweagent.task.{i_id}")
    task_logger.setLevel(logging.DEBUG)
    if task_logger.handlers:
        task_logger.handlers.clear()

    instance_log_file = log_dir / i_id / "run.log"
    instance_log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(instance_log_file)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    task_logger.addHandler(file_handler)

    task_logger.propagate = False
    return task_logger


def run_instance(
    instance: dict,
    config: dict,
    traj_output: Path,
    patch_output_dir: Path,
    model_name: str,
    progress_manager: RunBatchProgressManager | None,
    log_dir: Path,
    dry_run: bool = False,
):
    i_id = instance["instance_id"]

    task_logger = setup_logger(i_id, log_dir)
    # Register the logger for the current thread
    _threaded_custom_logger.register_logger(threading.get_ident(), task_logger)

    task_logger.info(f"========== Running instance {i_id} ==========")
    instance_config = config.copy()

    if progress_manager:
        progress_manager.on_instance_start(i_id)
        progress_manager.update_instance_status(i_id, "Pulling/starting docker")

    # --- Set Java Version ---
    jdk_version = instance.get("jdk_version")
    if jdk_version:
        progress_manager.update_instance_status(i_id, "Setting JAVA_HOME")
        java_home = f"/usr/lib/jvm/java-{jdk_version}-openjdk-amd64"
        instance_config.setdefault("environment", {}).setdefault("env", {}).update(
            {"JAVA_HOME": java_home}
        )
        task_logger.info(f"Setting JAVA_HOME to: {java_home}")

    task_logger.info(f"Using image: {instance['image_name']}")

    if dry_run:
        task_logger.info("Dry run mode, skipping agent execution.")
        if progress_manager:
            progress_manager.on_instance_end(i_id, "SUCCESS")
        return

    try:
        # Pass logger to environment via config.This is done to get the docker logs from mini-swe-agent in the same log file.
        instance_config.setdefault("environment", {})["logger"] = task_logger
        env = get_sb_environment(instance_config, instance)
    except Exception as e:
        task_logger.error(
            f"Error launching docker for instance {i_id}: {e}", exc_info=True
        )
        if progress_manager:
            progress_manager.update_instance_status(i_id, "Error launching docker")
        raise

    task_logger.info("Env: %s", env.config)
    model = get_model(model_name, instance_config.get("model", {}))
    reasoning_effort = instance_config.get("reasoning_config", {}).get(
        model_name, {}
    ).get("reasoning_effort") or instance_config.get("reasoning_config", {}).get(
        "default_reasoning_config", {}
    ).get(
        "reasoning_effort", "high"
    )

    task_logger.info(f"Reasoning effort: {reasoning_effort}")

    agent = MultimediaProcessingAgent(
        model,
        env,
        progress_manager=progress_manager,
        instance_id=i_id,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        **(instance_config.get("agent", {})),
    )
    exit_status, result, extra_info = None, None, None
    t_start_query = time.perf_counter()
    try:
        exit_status, result = agent.run(
            instance["problem_statement"],
            current_datetime=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            image_data=instance["image_urls"],
            video_data=instance["video_urls"],
        )
    except Exception as e:
        task_logger.error(f"Error processing instance {i_id}: {e}", exc_info=True)
        exit_status, result = type(e).__name__, str(e)
        extra_info = {"traceback": traceback.format_exc()}
    finally:
        traj_output_path = get_traj_output_path(traj_output, instance["instance_id"])
        patch_output_path = get_patch_output_path(
            patch_output_dir, instance["instance_id"]
        )
        # Calculate latency and add to model_stats
        t_end_query = time.perf_counter()
        if extra_info is None:
            extra_info = {}

        extra_info["model_stats"] = {
            "instance_cost": agent.model.cost,
            "api_calls": agent.model.n_calls,
            "total_latency_seconds": t_end_query - t_start_query,
        }

        traj_output_path.parent.mkdir(parents=True, exist_ok=True)
        save_traj(
            agent,
            traj_output_path,
            exit_status=exit_status,
            result=result,
            extra_info=extra_info,
        )

        if result:
            save_patch(result, patch_output_path, task_logger)

        if progress_manager:
            progress_manager.on_instance_end(i_id, exit_status)

        # Unregister the handler to avoid memory leaks or crossing threads later
        _threaded_custom_logger.unregister_logger(threading.get_ident())
