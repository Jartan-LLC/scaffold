# Minimal Python image. It BUILDS as-is (installs the package); give it a real
# entrypoint before you run it. publish-docker.yml builds this on v* tags.
# Delete this file (and publish-docker.yml / .dockerignore) if the project isn't
# containerized.

# Build stage, not an inline COPY --from: Dependabot only parses FROM lines.
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
COPY pyproject.toml README.md LICENSE* ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .

# Copy the rest of the project (respects .dockerignore).
COPY --chown=appuser:appuser . .
USER appuser

# TODO: set your start command, e.g.
# ENTRYPOINT ["your-cli"]
# CMD ["python", "-m", "app"]
