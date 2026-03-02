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
import os
import shutil
from common.constants import CONFIG_PROPERTIES_FILE


def setup_agent(source_path):
    """
    A unified function to copy patch data and create the config.properties file.

    Args:
        source_path (str): The path to the source directory (correct or invalid patches).
    """
    dest_dir = "out/oracle-agent/"
    config_file = os.path.join(dest_dir, CONFIG_PROPERTIES_FILE)

    # 1. Clean and Prepare Destination
    if os.path.exists(dest_dir):
        # Use shutil.rmtree to safely delete the directory and its contents
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    # 3. Create config.properties
    with open(config_file, "w") as f:
        f.write("model_name=oracle-agent\n")
        f.write("run_name=oracle-agent\n")


# --- New Entry Point Functions ---


def setup_oracle_agent():
    """Sets up the oracle agent using the correct patches."""
    CORRECT_SOURCE = (
        "tests/harness_evaluation_integration_test/data/out/oracle-agent/patches"
    )
    setup_agent(CORRECT_SOURCE)
    print(
        f"Setup complete: Correct patches copied to {os.path.join('out/oracle-agent/', 'patches')}"
    )


# --- Main Block Removed/Simplified ---

# The 'main()' function and the 'if __name__ == "__main__":' block
# are removed/commented out because the file is now designed to be run
# via entry points (like 'setup_oracle_agent') defined in pyproject.toml.
# If you still want a default action when the file is run directly:

if __name__ == "__main__":
    # Default behavior when running 'python your_file.py'
    setup_oracle_agent()
