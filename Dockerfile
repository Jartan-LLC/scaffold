# Minimal Python image. It BUILDS as-is (installs the package); give it a real
# entrypoint before you run it. publish-docker.yml builds this on v* tags.
# Delete this file (and publish-docker.yml / .dockerignore) if the project isn't
# containerized.

# uv installs the package here, same as in CI and `make`. It arrives as a build
# stage rather than the shorter `COPY --from=ghcr.io/astral-sh/uv:0.12.5`
# because Dependabot's Dockerfile parser only reads `FROM` lines — an inline
# COPY reference is a pin nobody bumps. Named `uv-bin` so it does not collide
# with the `uv` binary in a later RUN.
FROM ghcr.io/astral-sh/uv:0.12.5 AS uv-bin

FROM python:3.12-slim
COPY --from=uv-bin /uv /uvx /bin/

# Unbuffered stdout/stderr so logs aren't lost to block-buffering on a hard crash.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create the non-root user up front so COPY can assign ownership directly —
# avoids a `chown -R` sweep that re-runs on every source change.
RUN useradd --create-home --uid 1000 appuser

# Install the package. Copy only what the build needs first, for layer caching.
# src-layout: pyproject + src/ must both be present before the install.
# `--system` because the container is the isolation; no venv needed inside it.
COPY pyproject.toml README.md LICENSE* ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .

# Copy the rest of the project (respects .dockerignore).
COPY --chown=appuser:appuser . .
USER appuser

# TODO: set your start command, e.g.
# ENTRYPOINT ["your-cli"]
# CMD ["python", "-m", "app"]
