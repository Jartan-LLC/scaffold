# Minimal Python image. It BUILDS as-is (installs the package); give it a real
# entrypoint before you run it. publish-docker.yml builds this on v* tags.
# TODO(/onboard): if the project isn't containerized, delete this file, .dockerignore,
# publish-docker.yml and ci.yml's commented docker job.

# Build stage, not an inline COPY --from: Dependabot only parses FROM lines.
FROM ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 AS uv-bin

# x.y.z, not 3.12-slim: Dependabot can suppress digest-only bumps (dependabot/dependabot-core#15103).
FROM python:3.12.16-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54
COPY --from=uv-bin /uv /uvx /bin/

# Unbuffered stdout, so output reaches docker logs at once and a killed process loses none.
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

# Set a start command before running the image, e.g.
# ENTRYPOINT ["your-cli"]
# CMD ["python", "-m", "app"]
