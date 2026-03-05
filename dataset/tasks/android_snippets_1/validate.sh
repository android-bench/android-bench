#!/bin/bash

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

RC=0

# Check kotlin version
kotlin_version=$(grep -oE 'kotlin[[:space:]]*=[[:space:]]*"[^"]+"' gradle/libs.versions.toml | cut -d'"' -f2)

if [ -z "$kotlin_version" ]; then
  echo "Kotlin version not found"
  RC=1
else
  min_kotlin_version="2.3.0"

  if [ "$(printf '%s\n' "$min_kotlin_version" "$kotlin_version" | sort -V | head -n1)" = "$min_kotlin_version" ]; then
    echo "Kotlin version is $kotlin_version"
  else
    echo "Kotlin version is $kotlin_version, which is less than $min_kotlin_version"
    RC=1
  fi
fi

# Check androidGradlePlugin version
agp_version=$(grep -oE 'androidGradlePlugin[[:space:]]*=[[:space:]]*"[^"]+"' gradle/libs.versions.toml | cut -d'"' -f2)

if [ -z "$agp_version" ]; then
  echo "androidGradlePlugin version not found"
  RC=1
else
  min_agp_version="8.13.2"

  if [ "$(printf '%s\n' "$min_agp_version" "$agp_version" | sort -V | head -n1)" = "$min_agp_version" ]; then
    echo "androidGradlePlugin version is $agp_version"
  else
    echo "androidGradlePlugin version is $agp_version, which is less than $min_agp_version"
    RC=1
  fi
fi

exit $RC
