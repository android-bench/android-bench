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
from pathlib import Path
from logging import INFO
import os

# Use pathlib for all path definitions
ROOT_DIR = Path(__file__).resolve().parent.parent

# File Names
CONFIG_PROPERTIES_FILE = "config.properties"
AGENT_EXIT_STATUS_FILE = "agent_exit_status.yaml"
COMBINED_RESULTS_FILE = "combined_results.json"
GITIGNORE_FILE = ".gitignore"
SCORES_FILE_SUFFIX = "_scores.json"

# GCS Bucket names
SCRIPTS_BUCKET = "android_bench_scripts"
RESULTS_BUCKET = "android_bench_results"

# Results Subdirectory on GCS
VERIFIER_RESULTS_SUBDIR = "patch_verifier"
AGENT_RESULTS_SUBDIR = "android_bench_agent"

# Results subdirectory names on local machine
VERIFIER_RESULTS_SUBDIR_LOCAL = "verifier"
PATCHES_SUBDIR = "patches"
LOGS_SUBDIR = "logs"
TRAJECTORIES_SUBDIR = "trajectories"
OUT_SUBDIR = "out"

# Tasks subdirectory path
TASKS_DIR = ROOT_DIR / "dataset" / "tasks"

MODELS = [
    "anthropic/claude-opus-4-5",
    "openai/gpt-5.1-codex",
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-pro",
    "gemini/gemini-3-pro-preview",
]

LOG_LEVEL = "INFO"
