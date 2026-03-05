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
import time
import litellm
import warnings
from dataclasses import dataclass, asdict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
    retry_if_exception,
)

# Suppress Pydantic serializer warnings from LiteLLM
warnings.filterwarnings(
    "ignore", message=".*Pydantic serializer warnings.*", category=UserWarning
)

from minisweagent.run.extra.utils.batch_progress import RunBatchProgressManager


from minisweagent.agents.default import DefaultAgent
from minisweagent.agents.default import (
    NonTerminatingException,
    FormatError,
    ExecutionTimeoutError,
    TerminatingException,
    Submitted,
    LimitsExceeded,
)


@dataclass
class ReasoningConfig:
    reasoning_effort: str | None = None


class MultimediaProcessingAgent(DefaultAgent):
    """
    The main purpose of this class is to attach images in b64 encoded format.Its forked from the ProgressTrackingAgent.
    """

    def __init__(
        self,
        *args,
        progress_manager: RunBatchProgressManager,
        instance_id: str = "",
        model_name: str = "",
        reasoning_effort: str = "",
        **kwargs,
    ):
        self.progress_manager: RunBatchProgressManager = progress_manager
        self.instance_id = instance_id
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        # model_name, progress_manager, instance_id, reasoning_effort are consumed here and not passed to super
        super().__init__(*args, **kwargs)

    def _embed_image_links(self, image_data):
        content_list = []
        if litellm.supports_vision(model=self.model_name):
            for image_url in image_data:
                content_item = {"type": "image_url", "image_url": {"url": image_url}}
                content_list.append(content_item)
        return content_list

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """Run step() until agent is finished. Return exit status & message.
        This is identical to the run menthod in DefaultAgent(which progressTrackingAgent extends from).
        We have to create a separate method cause self.messages is set to null in the superclass DefaultAgent
        in its run method and we need to attach images before running the while true step loop.
        """

        self.extra_template_vars |= {"task": task, **kwargs}
        self.messages = []
        self.add_message("system", self.render_template(self.config.system_template))
        self.add_message("user", self.render_template(self.config.instance_template))
        if (
            "image_data" in self.extra_template_vars
            and self.extra_template_vars["image_data"]
        ):
            image_content = self._embed_image_links(
                self.extra_template_vars["image_data"]
            )
            for content_item in image_content:
                self.add_message("user", [content_item])

        while True:
            try:
                self.step()
            except NonTerminatingException as e:
                self.add_message("user", str(e))
            except TerminatingException as e:
                self.add_message("user", str(e))
                return type(e).__name__, str(e)

    def step(self):
        """
        Overrides the default step so that we can measure the latencies of the query and observation components of a step.
        """
        self.progress_manager.update_instance_status(
            self.instance_id,
            f"Step {self.model.n_calls + 1:3d} (${self.model.cost:.2f})",
        )
        t_start_query = time.perf_counter()
        completion = self.query()
        t_end_query = time.perf_counter()

        if self.messages and self.messages[-1]["role"] == "assistant":
            self.messages[-1]["query_latency_seconds"] = t_end_query - t_start_query

        t_start_obs = time.perf_counter()
        observation = self.get_observation(completion)
        t_end_obs = time.perf_counter()

        if self.messages and self.messages[-1]["role"] == "user":
            self.messages[-1]["processing_latency_seconds"] = t_end_obs - t_start_obs

        return observation

    def query(self) -> dict:
        """Query the model and return the response."""
        if (
            0 < self.config.step_limit <= self.model.n_calls
            or 0 < self.config.cost_limit <= self.model.cost
        ):
            raise LimitsExceeded()
        kwargs = {}
        if litellm.supports_reasoning(model=self.model_name):
            kwargs = {"reasoning_effort": self.reasoning_effort}

        """
        The retry logic is added to handle the transient errors that may occur while querying the model.
        502 - Bad Gateway
        503 - Service Unavailable
        504 - Gateway Timeout
        408 - Request Timeout
        429 - Too Many Requests
        Currently mini-swe-agent does not retry on exceptiontype litellm.APIError.It supports that in v2 but since
        its still in development we are currently not upgrading to that.
        """

        def is_retryable_error(e):
            if isinstance(e, litellm.APIError):
                if hasattr(e, "status_code") and e.status_code in [
                    502,
                    503,
                    504,
                    408,
                    429,
                ]:
                    return True
            return False

        @retry(
            reraise=True,
            stop=stop_after_attempt(4),
            # retry for 3 times with exponential backoff 2, 4, 8 seconds
            wait=wait_chain(*[wait_fixed(2), wait_fixed(4), wait_fixed(8)]),
            retry=retry_if_exception(is_retryable_error),
        )
        def _execute_query():
            return self.model.query(self.messages, **kwargs)

        response = _execute_query()
        self.add_message("assistant", **response)
        return response
