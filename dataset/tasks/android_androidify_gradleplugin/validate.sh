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

# Search these files for logic that should have been extracted
TARGET_FILES=(
    "app/build.gradle.kts"
    "core/network/build.gradle.kts"
    "core/testing/build.gradle.kts"
    "core/theme/build.gradle.kts"
    "core/theme/build.gradle.kts"
    "core/util/build.gradle.kts"
    "core/xr/build.gradle.kts"
    "data/build.gradle.kts"
    "feature/camera/build.gradle.kts"
    "feature/creation/build.gradle.kts"
    "feature/home/build.gradle.kts"
    "feature/results/build.gradle.kts"
    "watchface/build.gradle.kts"
    "wear/build.gradle.kts"
    "wear/common/build.gradle.kts"
)

# If the following strings don't exist in these files, but the project still builds and passes tests then
# the logic must have been extracted
FORBIDDEN_STRINGS=(
    "libs.plugins.android.application"
    "libs.plugins.kotlin.android"
    "libs.plugins.kotlin.compose"
)

has_error=false

for file in "${TARGET_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: $file does not exist."
        has_error=true
        continue
    fi

    for str in "${FORBIDDEN_STRINGS[@]}"; do
        if grep -Fq "$str" "$file"; then
            echo "Error: Found forbidden string '$str' in $file"
            has_error=true
        fi
    done
done

# Application build gradle files should reference the application plugin, not library
APPLICATION_BUILD_GRADLE_FILES=(
    "app/build.gradle.kts"
    "wear/build.gradle.kts"
)

REQUIRED_APP_STRINGS=(
    "androidify.androidApplication"
)

FORBIDDEN_APP_STRINGS=(
    "androidify.androidLibrary"
    "androidify.androidComposeLibrary"
)

for file in "${APPLICATION_BUILD_GRADLE_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: Application file $file does not exist."
        has_error=true
        continue
    fi

    for str in "${REQUIRED_APP_STRINGS[@]}"; do
        if ! grep -Fq "$str" "$file"; then
            echo "Error: Missing required string '$str' in $file"
            has_error=true
        fi
    done

    for str in "${FORBIDDEN_APP_STRINGS[@]}"; do
        if grep -Fq "$str" "$file"; then
            echo "Error: Found forbidden string '$str' in $file"
            has_error=true
        fi
    done
done

# Library build gradle files should reference the library plugin, not application or compose library
LIBRARY_BUILD_GRADLE_FILES=(
    "core/network/build.gradle.kts"
    "data/build.gradle.kts"
    "watchface/build.gradle.kts"
    "wear/common/build.gradle.kts"
)

REQUIRED_LIB_STRINGS=(
    "androidify.androidLibrary"
)

FORBIDDEN_LIB_STRINGS=(
    "androidify.androidApplication"
    "androidify.androidComposeLibrary"
)

for file in "${LIBRARY_BUILD_GRADLE_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: Library file $file does not exist."
        has_error=true
        continue
    fi

    for str in "${REQUIRED_LIB_STRINGS[@]}"; do
        if ! grep -Fq "$str" "$file"; then
            echo "Error: Missing required string '$str' in $file"
            has_error=true
        fi
    done

    for str in "${FORBIDDEN_LIB_STRINGS[@]}"; do
        if grep -Fq "$str" "$file"; then
            echo "Error: Found forbidden string '$str' in $file"
            has_error=true
        fi
    done
done

# Compose library build gradle files should reference the compose library plugin
COMPOSE_LIBRARY_BUILD_GRADLE_FILES=(
    "core/testing/build.gradle.kts"
    "core/theme/build.gradle.kts"
    "core/util/build.gradle.kts"
    "core/xr/build.gradle.kts"
    "feature/camera/build.gradle.kts"
    "feature/creation/build.gradle.kts"
    "feature/home/build.gradle.kts"
    "feature/results/build.gradle.kts"
)

REQUIRED_COMPOSE_LIB_STRINGS=(
    "androidify.androidComposeLibrary"
)

FORBIDDEN_COMPOSE_LIB_STRINGS=(
    "androidify.androidApplication"
    "androidify.androidLibrary"
)

for file in "${COMPOSE_LIBRARY_BUILD_GRADLE_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: Compose library file $file does not exist."
        has_error=true
        continue
    fi

    for str in "${REQUIRED_COMPOSE_LIB_STRINGS[@]}"; do
        if ! grep -Fq "$str" "$file"; then
            echo "Error: Missing required string '$str' in $file"
            has_error=true
        fi
    done

    for str in "${FORBIDDEN_COMPOSE_LIB_STRINGS[@]}"; do
        if grep -Fq "$str" "$file"; then
            echo "Error: Found forbidden string '$str' in $file"
            has_error=true
        fi
    done
done

if [ "$has_error" = true ]; then
    exit 1
fi

echo "Validation successful."
