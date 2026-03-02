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
import shutil
from pathlib import Path
from .base import Storage


class LocalStorage(Storage):
    """LocalStorage implementation for file system operations."""

    def __init__(self, base_path: str):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def upload(self, local_path: Path, remote_path: str):
        """Copy a file or directory to a local path."""
        destination = self._base_path / remote_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if local_path.is_dir():
            shutil.copytree(local_path, destination, dirs_exist_ok=True)
        else:
            shutil.copy(local_path, destination)

    def download(self, remote_path: str, local_path: Path):
        """Copy a file or directory from a local path."""
        source = self._base_path / remote_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, local_path, dirs_exist_ok=True)
        else:
            shutil.copy(source, local_path)

    def exists(self, remote_path: str) -> bool:
        """Check if a file or directory exists at a local path."""
        return (self._base_path / remote_path).exists()
