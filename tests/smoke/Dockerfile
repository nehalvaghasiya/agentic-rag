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

FROM source AS wheel-build
COPY tests/smoke/check_wheel.py ./tests/smoke/check_wheel.py
RUN --mount=type=cache,id=rag-smoke-uv,target=/root/.cache/uv \
    uv build --wheel --no-sources --out-dir /dist \
    && python tests/smoke/check_wheel.py --inspect /dist --source-root /app \
    && uv export --locked --no-default-groups --no-emit-project --no-hashes \
        --output-file /dist/constraints.txt \
    && uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python \
        --constraint /dist/constraints.txt /dist/*.whl \
    && uv pip check --python /opt/venv/bin/python \
    && uv sync --locked --no-default-groups \
    && uv run --no-sync python -c "import backend; from importlib.metadata import version; print('PASS: quickstart install', version('rag'))"

# Start from the clean interpreter image: no checkout, editable install, or build tools.
FROM ${PYTHON_IMAGE} AS wheel
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=wheel-build /opt/venv /opt/venv
COPY --from=wheel-build /dist/wheel-manifest.json /checks/wheel-manifest.json
COPY tests/smoke/check_wheel.py /checks/check_wheel.py
WORKDIR /run-api
ENV UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
CMD ["uv", "run", "--no-project", "--python", "/opt/venv/bin/python", "python", "-I", "/checks/check_wheel.py"]

FROM source AS local-embeddings
RUN --mount=type=cache,id=rag-smoke-uv,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project --extra local-embeddings \
    && uv run --no-sync python tests/smoke/check_runtime.py --check-lock --profile local-embeddings
CMD ["uv", "run", "--no-sync", "python", "-I", "/app/tests/smoke/check_runtime.py", "--profile", "local-embeddings"]

# Keep the smaller core profile as the default build target.
FROM source AS core
RUN --mount=type=cache,id=rag-smoke-uv,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project \
    && uv run --no-sync python tests/smoke/check_runtime.py --check-lock
CMD ["uv", "run", "--no-sync", "python", "-I", "/app/tests/smoke/check_runtime.py", "--profile", "core"]
