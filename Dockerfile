# Minimal Python image. It BUILDS as-is (installs the package); give it a real
# entrypoint before you run it. ci.yml's docker job builds this when a change touches
# its inputs (ci/changes.py), and publish-docker.yml on v* tags.
# TODO(/onboard): if the project isn't containerized, delete this file and .dockerignore,
# and drop the image as docs/onboard.md's Publishing targets says.

# Build stage, not an inline COPY --from: Dependabot only parses FROM lines.
FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv-bin

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
COPY ci/build-requirements.txt ./ci/
# uv build, not uv pip install: uv pip install refuses a build package the lock lacks
# only with --require-build-hashes, which uv marks experimental. --exclude-newer keeps
# runtime dependencies to releases at least a week old, so a compromised release is
# less likely to reach the image before PyPI removes it.
RUN uv build --no-cache --wheel --out-dir /tmp/dist \
        --build-constraints ci/build-requirements.txt --require-hashes \
    && uv pip install --system --no-cache --exclude-newer "7 days" /tmp/dist/*.whl \
    && rm -rf /tmp/dist

# Copy the rest of the project (respects .dockerignore).
COPY --chown=appuser:appuser . .
USER appuser

# Set a start command before running the image, e.g.
# ENTRYPOINT ["your-cli"]
# CMD ["python", "-m", "app"]
