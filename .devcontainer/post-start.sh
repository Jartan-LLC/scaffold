#!/bin/bash

# Fix Docker socket permissions (docker-outside-of-docker feature)
sudo chmod 666 /var/run/docker-host.sock 2>/dev/null || true

# In GitHub Codespaces, HOST_PROJECT_PATH (set via containerEnv) resolves to the
# host-side path, which is meaningless inside the container. Override it with the
# container workspace path so downstream Docker bind-mounts work correctly.
if [ "$CODESPACES" = "true" ]; then
    grep -q 'HOST_PROJECT_PATH' ~/.bashrc 2>/dev/null || echo 'export HOST_PROJECT_PATH="$CONTAINER_WORKSPACE_FOLDER"' >> ~/.bashrc
fi
