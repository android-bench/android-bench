# ====================================================================== #
# Android Bench Docker Image (Fourth Revision: No PPA)
# ====================================================================== #

# 1. Start from a stable, full-featured Ubuntu LTS base image.
FROM ubuntu:22.04

# Use ARGs for version flexibility
ARG TARGETARCH
ARG JDK_VERSION=17
ARG KOTLIN_VERSION=2.1.0
ARG ANDROID_CMD_TOOLS_VERSION=11076708

ARG ANDROID_CMD_TOOLS_VERSION=11076708

# Set non-interactive frontend
ENV DEBIAN_FRONTEND=noninteractive

# 2. Install Python, pip, and core dependencies from default Ubuntu repos.
#    This avoids the flaky PPA and is much more reliable.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    ca-certificates \
    git \
    wget \
    unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Install the swe-rex remote agent using the default python3.
RUN python3 -m pip install swe-rex

# 4. Install Android dependencies: Java and optional virtualization tools.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-8-jdk \
    openjdk-11-jdk \
    openjdk-17-jdk \
    openjdk-18-jdk \
    openjdk-21-jdk \
    openjdk-25-jdk \
    qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV JAVA_HOME=/usr/lib/jvm/java-${JDK_VERSION}-openjdk-${TARGETARCH:-amd64}
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk
ENV KOTLIN_HOME=/opt/kotlinc

# Add EMULATOR conditionally depending on the architecture

# Download and install Kotlin compiler (if needed for your specific workflow)
RUN wget -q https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VERSION}/kotlin-compiler-${KOTLIN_VERSION}.zip -O kotlin.zip && \
    unzip kotlin.zip -d /opt && \
    rm kotlin.zip

# Download and install Android SDK using the modern 'latest' path
RUN mkdir -p ${ANDROID_SDK_ROOT} && \
    wget -q "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMD_TOOLS_VERSION}_latest.zip" -O android-sdk.zip && \
    unzip -q android-sdk.zip -d ${ANDROID_SDK_ROOT} && \
    mv ${ANDROID_SDK_ROOT}/cmdline-tools ${ANDROID_SDK_ROOT}/latest && \
    mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools && \
    mv ${ANDROID_SDK_ROOT}/latest ${ANDROID_SDK_ROOT}/cmdline-tools/latest && \
    rm android-sdk.zip

# When TARGETARCH=arm64, EMULATOR_PATH will evaluate to empty, otherwise to the emulator directory path
ENV EMULATOR_PATH=${TARGETARCH:+-arm64}
# This ugly bash parameter expansion says: if EMULATOR_PATH = "-arm64", return "", otherwise return ":${ANDROID_SDK_ROOT}/emulator"
ENV EMULATOR_PATH=${EMULATOR_PATH:+-arm64:}:${EMULATOR_PATH:+:${ANDROID_SDK_ROOT}/emulator}

ENV PATH=${PATH}:${KOTLIN_HOME}/bin:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools${EMULATOR_PATH}

# Install all SDK packages in a single, non-blocking command
RUN yes | sdkmanager --licenses > /dev/null && \
    if [ "$TARGETARCH" = "arm64" ]; then \
        sdkmanager \
        "platform-tools" \
        "platforms;android-31" \
        "platforms;android-32" \
        "platforms;android-33" \
        "platforms;android-34" \
        "platforms;android-35" \
        "build-tools;31.0.0" \
        "build-tools;32.0.0" \
        "build-tools;33.0.0" \
        "build-tools;34.0.0" \
        "build-tools;35.0.0" \
        "build-tools;36.0.0"; \
    else \
        sdkmanager \
        "platform-tools" \
        "emulator" \
        "platforms;android-31" \
        "platforms;android-32" \
        "platforms;android-33" \
        "platforms;android-34" \
        "platforms;android-35" \
        "build-tools;31.0.0" \
        "build-tools;32.0.0" \
        "build-tools;33.0.0" \
        "build-tools;34.0.0" \
        "build-tools;35.0.0" \
        "build-tools;36.0.0" \
        "system-images;android-36;google_apis;x86_64" \
        "system-images;android-35;google_apis;x86_64" \
        "system-images;android-34;google_apis;x86_64" \
        "system-images;android-33;google_apis;x86_64" \
        "system-images;android-32;google_apis;x86_64" \
        "system-images;android-31;google_apis;x86_64" \
        "system-images;android-30;default;x86_64" \
        "system-images;android-29;default;x86_64"; \
    fi

# RUN wget https://services.gradle.org/distributions/gradle-8.11.1-bin.zip && \
#      mkdir /opt/gradle && unzip -d /opt/gradle gradle-8.11.1-bin.zip

# ENV GRADLE_HOME=/opt/gradle/gradle-8.11.1
# Set a default working directory
WORKDIR /workspace
RUN mkdir /workspace/projects
RUN mkdir /workspace/output

RUN if [ "$TARGETARCH" != "arm64" ]; then \
    echo "no" | avdmanager create avd -n test_emulator_29 -k "system-images;android-29;default;x86_64" --device "pixel_6" --force || true; \
    echo "no" | avdmanager create avd -n test_emulator_30 -k "system-images;android-30;default;x86_64" --device "pixel_6" --force || true; \
    echo "no" | avdmanager create avd -n test_emulator_31 -k "system-images;android-31;google_apis;x86_64" --device "pixel_6" --force || true; \
    echo "no" | avdmanager create avd -n test_emulator_32 -k "system-images;android-32;google_apis;x86_64" --device "pixel_6" --force || true; \
    echo "no" | avdmanager create avd -n test_emulator_33 -k "system-images;android-33;google_apis;x86_64" --device "pixel_7" --force || true; \
    echo "no" | avdmanager create avd -n test_emulator_34 -k "system-images;android-34;google_apis;x86_64" --device "pixel_7" --force || true; \
    echo "no" | avdmanager create avd -n test_emulator_35 -k "system-images;android-35;google_apis;x86_64" --device "pixel_7" --force || true; \
    echo "no" | avdmanager create avd -n test_emulator_36 -k "system-images;android-36;google_apis;x86_64" --device "pixel_7" --force || true; \
    fi