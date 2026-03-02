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
from google.cloud import storage
from pathlib import Path
from .base import Storage


class GCloudStorage(Storage):
    """GCloudStorage implementation for GCS operations."""

    def __init__(self, base_path: str):
        if not base_path.startswith("gs://"):
            raise ValueError("GCloudStorage base_path must start with gs://")
        parts = base_path[5:].split("/", 1)
        self._bucket_name = parts[0]
        self._prefix = parts[1] if len(parts) > 1 else ""
        self._client = storage.Client()
        self._bucket = self._client.bucket(self._bucket_name)

    def upload(self, local_path: Path, remote_path: str):
        """Upload a file or directory to a GCS path."""
        blob_path = f"{self._prefix}/{remote_path}"
        if local_path.is_dir():
            for file_path in local_path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(local_path)
                    blob = self._bucket.blob(f"{blob_path}/{rel_path}")
                    blob.upload_from_filename(str(file_path))
        else:
            blob = self._bucket.blob(blob_path)
            blob.upload_from_filename(str(local_path))

    def download(self, remote_path: str, local_path: Path):
        """Download a file or directory from a GCS path."""
        blob_path = f"{self._prefix}/{remote_path}"
        blobs = list(self._bucket.list_blobs(prefix=blob_path))
        for blob in blobs:
            if blob.name.endswith("/"):
                continue
            rel_path = blob.name[len(blob_path) :].lstrip("/")
            destination_file = local_path / rel_path
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(destination_file))

    def exists(self, remote_path: str) -> bool:
        """Check if a file or directory exists at a GCS path."""
        blob_path = f"{self._prefix}/{remote_path}"
        blobs = list(self._bucket.list_blobs(prefix=blob_path, max_results=1))
        return len(blobs) > 0
