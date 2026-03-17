#!/bin/bash
# android-bench.sh
# Wrapper script to run Android Bench CLI commands inside a Docker container.

IMAGE_NAME="android-bench-cli"

# Build the image if it doesn't exist
if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "Building $IMAGE_NAME docker image..."
    docker build -t "$IMAGE_NAME" .
fi

# Run the command inside the docker container
# We mount the docker socket to allow Docker-out-of-Docker (DooD)
# We mount the current directory to /app to reflect code changes and persist outputs
# We mount /dev/kvm for hardware acceleration

DOCKER_ARGS=(
    -it --rm
    -v /var/run/docker.sock:/var/run/docker.sock
    -v "$(pwd):/app"
    -e GEMINI_API_KEY
    -e OPENAI_API_KEY
    -e HOST_PWD="$(pwd)"
)

if [ -e /dev/kvm ]; then
    DOCKER_ARGS+=(--device /dev/kvm)
fi

docker run "${DOCKER_ARGS[@]}" "$IMAGE_NAME" "$@"
