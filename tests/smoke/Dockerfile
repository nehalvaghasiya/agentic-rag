# Pinned default for a repeatable base; PYTHON_IMAGE also accepts plain Python tags.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
FROM ghcr.io/astral-sh/uv:0.12.1@sha256:cf4eedcaa81655197f625739489effcbe71b61ceb1506f332c3facae5deceded AS uv
FROM ${PYTHON_IMAGE} AS source
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PYTHONNOUSERSITE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/
COPY tests/smoke/check_runtime.py ./tests/smoke/check_runtime.py

FROM source AS local-embeddings
RUN --mount=type=cache,id=rag-smoke-uv,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project --extra local-embeddings \
    && .venv/bin/python tests/smoke/check_runtime.py --check-lock --profile local-embeddings
CMD ["/app/.venv/bin/python", "-I", "/app/tests/smoke/check_runtime.py", "--profile", "local-embeddings"]

# Keep the smaller core profile as the default build target.
FROM source AS core
RUN --mount=type=cache,id=rag-smoke-uv,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project \
    && .venv/bin/python tests/smoke/check_runtime.py --check-lock
CMD ["/app/.venv/bin/python", "-I", "/app/tests/smoke/check_runtime.py", "--profile", "core"]
