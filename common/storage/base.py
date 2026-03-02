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
from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    """Abstract base class for storage operations."""

    @abstractmethod
    def upload(self, local_path: Path, remote_path: str):
        """Upload a file or directory to a remote path."""
        pass

    @abstractmethod
    def download(self, remote_path: str, local_path: Path):
        """Download a file or directory from a remote path."""
        pass

    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        """Check if a file or directory exists at a remote path."""
        pass
