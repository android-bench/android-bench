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
"""Defines the core worker logic for executing a single Android benchmark task."""

import io
import json
import logging
import os
import tarfile
from pathlib import Path

from docker import DockerClient
from docker.errors import ContainerError

from common.models.benchmark import PatchScore, Status, TokenDetails, LatencyDetails
from .config import config as verifier_config
from .config import config as verifier_config
from common.config import BaseConfig
from common.constants import ROOT_DIR, VERIFIER_RESULTS_SUBDIR_LOCAL

logger = logging.getLogger(__name__)


def score_patch(
    task: dict,
    client: DockerClient,
    run_dir: Path,
    job_name: str,
    use_local_images: bool = False,
    print_container_logs: bool = False,
    host_project_path: Path | None = None,
) -> PatchScore:
    cfg = BaseConfig()
    container = None
    instance_id = task.get("instance_id", "unknown_task")
    if not host_project_path:
        import os
        host_pwd = os.environ.get("HOST_PWD")
        if host_pwd:
            host_project_path = Path(host_pwd)
        else:
            host_project_path = ROOT_DIR

    # Set up instance-specific verifier directory
    instance_dir = run_dir / VERIFIER_RESULTS_SUBDIR_LOCAL / instance_id
    instance_dir.mkdir(parents=True, exist_ok=True)
    task_json_file = instance_dir / "task.json"
    logs_file_path = instance_dir / "log.txt"
    try:
        logger.info(
            f"Instance {instance_id}: Acquired startup lock. Starting container."
        )

        # Write task JSON to file
        with open(task_json_file, "w") as f:
            json.dump(task, f, indent=2)
        logger.info(f"Task JSON written to: {task_json_file}")

        image_name = instance_id.lower()
        if not use_local_images:
            image_name = f"{cfg.docker_repository}/{instance_id.lower()}"
            # We need to pull the latest image first, otherwise we might have outdated ones
            logger.info(f"Pulling image {image_name}")
            client.images.pull(image_name)

        script_file_path = Path(__file__).resolve()
        local_project_path = script_file_path.parent.parent.parent
        volume_mapping = f"{host_project_path.as_posix()}:/android_bench:rw"

        # Convert task JSON file path to container path
        absolute_task_json = task_json_file.resolve()
        # We need to calculate the path relative to the LOCAL project root,
        # because checking against host_project_path (which might be external in DooD) will fail.
        relative_task_json_path = absolute_task_json.relative_to(local_project_path)
        container_task_json = (
            Path("/android_bench") / relative_task_json_path
        ).as_posix()

        container_command = [
            "python3",
            "-m",
            "harness.evaluation.harness",
            "--task-json-file",
            container_task_json,
        ]

        logger.info(f"Mounting {volume_mapping}")
        max_retries: int = verifier_config.docker_config.container_start_retries
        retry_count: int = 0
        while retry_count < max_retries:
            logger.info(
                f"Instance {instance_id}: Starting container (Attempt {retry_count}/{max_retries})."
            )
            container = client.containers.run(
                image_name,
                container_command,
                detach=True,
                devices=["/dev/kvm"],
                privileged=True,
                volumes=[volume_mapping],
                working_dir="/workspace",
                environment=["PYTHONPATH=/android_bench"],
            )

            if print_container_logs:
                for log in container.logs(stream=True, follow=True):
                    print(f"[{instance_id}] {log.decode('utf-8').strip()}")

            result = container.wait(
                timeout=verifier_config.docker_config.harness_docker_timeout
            )
            exit_code = result.get("StatusCode", -1)
            logger.info(
                f"[{instance_id}] Container finished with exit code: {exit_code}"
            )

            logs = container.logs().decode("utf-8").strip()
            if logs:
                open(logs_file_path, "w+").write(logs)

            if exit_code == 0:
                container_file_path = "/workspace/harness/evaluation/scores.json"
                bits, stat = container.get_archive(container_file_path)
                with tarfile.open(fileobj=io.BytesIO(b"".join(bits)), mode="r") as tar:
                    file_content = tar.extractfile("scores.json").read().decode("utf-8")
                    logger.info(file_content)
                    result_dict = json.loads(file_content)
                    # result_dict should have {instance_id: {score, status, diagnostics}}
                    result = result_dict.get(instance_id)
                    if isinstance(result, dict):
                        diagnostics_list = result.get("diagnostics", [])
                        diagnostics = (
                            "\n".join(diagnostics_list)
                            if isinstance(diagnostics_list, list)
                            else str(diagnostics_list)
                        )
                        status_name = result.get("status")
                        if status_name in [
                            Status.INFRA_FAILURE_EMULATOR_TIMEOUT.name,
                            Status.INFRA_FAILURE_EMULATOR_OFFLINE.name,
                        ]:
                            logger.info(
                                f"[{instance_id}] Emulator failure detected ({status_name}). Cleaning up container before retry."
                            )
                            container.stop()
                            container.remove()
                            container = None
                            retry_count += 1
                            continue
                        return PatchScore(
                            instance_id=instance_id,
                            score=float(result.get("score", 0.0)),
                            status=Status[status_name],
                            diagnostics=diagnostics,
                            job_name=job_name,
                            used_tokens=TokenDetails(**result.get("used_tokens", {})),
                            latency_details=LatencyDetails(
                                **result.get("latency_details", {})
                            ),
                            steps=str(result.get("steps", "0")),
                            cost=str(result.get("cost", "$0.0")),
                        )
                    else:
                        # Unexpected format
                        return PatchScore(
                            instance_id=instance_id,
                            score=0.0,
                            status=Status.INFRA_FAILURE,
                            diagnostics=f"Unexpected result format: {result}",
                            job_name=job_name,
                            used_tokens=TokenDetails(**task.get("used_tokens") or {}),
                            latency_details=LatencyDetails(
                                **task.get("latency_details") or {}
                            ),
                            steps=str(task.get("steps") or "0"),
                            cost=str(task.get("cost") or "$0.0"),
                        )
            else:
                return PatchScore(
                    instance_id=instance_id,
                    score=0.0,
                    status=Status.INFRA_FAILURE,
                    diagnostics=f"Container exited with non-zero status, see logs at {logs_file_path}",
                    job_name=job_name,
                    used_tokens=TokenDetails(**task.get("used_tokens") or {}),
                    latency_details=LatencyDetails(**task.get("latency_details") or {}),
                    steps=str(task.get("steps") or "0"),
                    cost=str(task.get("cost") or "$0.0"),
                )
        logger.error(
            f"[{instance_id}] Exhausted max retries ({max_retries}) due to emulator failures (timeout or offline)."
        )
        return PatchScore(
            instance_id=instance_id,
            score=0.0,
            status=Status.INFRA_FAILURE_EMULATOR_TIMEOUT,  # Or a more generic INFRA_ERROR
            diagnostics=f"Failed to score patch after {max_retries} attempts due to repeated emulator failures.",
            job_name=job_name,
            used_tokens=TokenDetails(**task.get("used_tokens") or {}),
            latency_details=LatencyDetails(**task.get("latency_details") or {}),
            steps=str(task.get("steps") or "0"),
            cost=str(task.get("cost") or "$0.0"),
        )
    except ContainerError as e:
        logger.error(f"[{instance_id}] Container error: {e}")
        if container:
            logs = container.logs().decode("utf-8").strip()
            open(logs_file_path, "w+").write(logs)
        return PatchScore(
            instance_id=instance_id,
            score=0.0,
            status=Status.INFRA_FAILURE,
            diagnostics=f"Container error: {e}",
            job_name=job_name,
            used_tokens=TokenDetails(**task.get("used_tokens") or {}),
            latency_details=LatencyDetails(**task.get("latency_details") or {}),
            steps=str(task.get("steps") or "0"),
            cost=str(task.get("cost") or "$0.0"),
        )
    except Exception as e:
        logger.error(f"[{instance_id}] An unexpected error occurred: {e}")
        if container:
            logs = container.logs().decode("utf-8").strip()
            open(logs_file_path, "w+").write(logs)
        return PatchScore(
            instance_id=instance_id,
            score=0.0,
            status=Status.INFRA_FAILURE,
            diagnostics=f"Unexpected error: {e}",
            job_name=job_name,
            used_tokens=TokenDetails(**task.get("used_tokens") or {}),
            latency_details=LatencyDetails(**task.get("latency_details") or {}),
            steps=str(task.get("steps") or "0"),
            cost=str(task.get("cost") or "$0.0"),
        )
    finally:
        if container:
            try:
                logger.info(
                    f"[{instance_id}] Cleaning up container {container.name}..."
                )
                container.stop()
                container.remove()
            except Exception as e:
                logger.error(f"[{instance_id}] Error during container cleanup: {e}")
