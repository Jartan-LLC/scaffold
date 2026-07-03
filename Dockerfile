# Minimal Python image. It BUILDS as-is (installs the package); give it a real
# entrypoint before you run it. publish-docker.yml builds this on v* tags.
# Delete this file (and publish-docker.yml / .dockerignore) if the project isn't
# containerized.
FROM python:3.12-slim

WORKDIR /app

# Install the package. Copy only what the build needs first, for layer caching.
# src-layout: pyproject + src/ must both be present before `pip install .`.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Copy the rest of the project (respects .dockerignore).
COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

# TODO: set your start command, e.g.
# ENTRYPOINT ["your-cli"]
# CMD ["python", "-m", "app"]
