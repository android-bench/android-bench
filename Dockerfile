FROM python:3.11-slim

# Install required system dependencies, including Docker CLI to interact with the host Docker daemon
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    docker.io \
    docker-cli \
    git \
    kmod \
    && rm -rf /var/lib/apt/lists/*

RUN getent group kvm || groupadd -g 994 kvm && usermod -aG kvm root

WORKDIR /app

# Copy the project files
COPY . .

# Install the python project dependencies
RUN pip install --no-cache-dir -e ".[dev,analysis]"

# By default, provide a shell
CMD ["bash"]
