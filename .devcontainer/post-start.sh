#!/bin/bash

# Fix Docker socket permissions (docker-outside-of-docker feature)
sudo chmod 666 /var/run/docker-host.sock 2>/dev/null || true

# In GitHub Codespaces, HOST_PROJECT_PATH (set via containerEnv) resolves to the
# host-side path, which is meaningless inside the container. Override it with the
# container workspace path so downstream Docker bind-mounts work correctly.
if [ "$CODESPACES" = "true" ]; then
    # Login shells (VS Code terminals, SSH)
    echo "export HOST_PROJECT_PATH=\"$CONTAINER_WORKSPACE_FOLDER\"" | sudo tee /etc/profile.d/codespaces-host-path.sh >/dev/null
    # Non-interactive bash (Claude Code CLI, VS Code tasks)
    echo "export HOST_PROJECT_PATH=\"$CONTAINER_WORKSPACE_FOLDER\"" | sudo tee /etc/codespaces-env.sh >/dev/null
    grep -q 'BASH_ENV' /etc/environment 2>/dev/null || echo 'BASH_ENV=/etc/codespaces-env.sh' | sudo tee -a /etc/environment >/dev/null
fi
