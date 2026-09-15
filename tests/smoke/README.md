# Backend smoke tests

These smoke tests verify source runtime dependencies and an installed backend wheel.
They use standard-library harnesses inside virtual environments, with no pytest
or other development packages. Docker with Buildx is required. Run all commands
from the repository root.

## Source dependency profiles

Build and run the core profile:

```bash
docker buildx build --load --target core -f tests/smoke/Dockerfile \
  -t agentic-rag-smoke:core-py312 .
docker run --rm --network none agentic-rag-smoke:core-py312
```

Build and run local embedding support separately:

```bash
docker buildx build --load --target local-embeddings -f tests/smoke/Dockerfile \
  -t agentic-rag-smoke:local-py312 .
docker run --rm --network none agentic-rag-smoke:local-py312
```

Both dependency targets start from the same clean base and perform a locked
installation with `--no-default-groups --no-install-project`. Here,
`--no-install-project` deliberately isolates dependency coverage; the wheel
target below checks packaging. The optional target also passes
`--extra local-embeddings`. Package downloads happen during construction; uv's
download cache is a BuildKit cache mount and is not included in the resulting
image. Neither image receives the host's `.venv`, `.env`, application data, or
model cache. The Dockerfile-specific ignore file also limits the build context.

The local profile installs the PyPI PyTorch dependency stack, which can include
large CUDA libraries on Linux even though this smoke test does not use a GPU.
It imports Sentence Transformers without constructing a model or downloading
weights. Model weights, GPU support, and embedding quality are separate checks.

Each build checks that `uv lock --check` succeeds and a repeated offline locked
sync changes neither installed versions nor the lockfile bytes. It then copies
the metadata into a temporary directory, adds a satisfiable direct dependency,
and requires `uv sync --locked` to reject the stale lockfile. This negative check
runs during the online build because changed metadata invokes the existing
dynamic build backend and may need its build requirements.

Each container run checks:

- All backend modules import in production mode without credentials.
- Installed distributions and imported third-party extensions come from the venv;
  user/system site-packages and development dependencies are excluded.
- The transformer stack is absent in core and imports in the optional profile.
- Hosted integration classes import, and a generated text PDF loads through the
  real PDF loader.
- Uvicorn starts, `/api/health` returns `{"status":"ok"}`, and OpenAPI renders.
- A separate deterministic server accepts a multipart text upload and persists
  its manifest and vectors in temporary storage.

The harness starts each process with an allowlisted environment and uses an
isolated working directory before importing settings. Startup has a 30-second
deadline, failing processes emit server logs, and cleanup stops the server.
`--network none` denies external runtime access while retaining loopback HTTP.
The script prints the interpreter, platform, profile, and installed package
versions; build output includes the lockfile SHA-256.

## Installed wheel

```bash
docker buildx build --load --target wheel -f tests/smoke/Dockerfile \
  -t agentic-rag-smoke:wheel-py312 .
docker run --rm --network none agentic-rag-smoke:wheel-py312
```

The build stage runs `uv build --wheel --no-sources` and compares the archive
against every Python module under `backend/`. It rejects missing modules,
unexpected top-level contents, and the nonexistent `rag` console entry point.
The image context excludes Git metadata, so this also exercises the configured
fallback version. The harness records the artifact's filename, version, and SHA-256
without assuming a fixed version.

It then installs the wheel into a fresh core environment. Constraints exported
with `uv export --locked --no-default-groups --no-emit-project --no-hashes` keep
dependencies at I001's locked versions. Installation resolves the wheel's own
dependency declarations; the constraints do not preinstall packages or make
missing dependencies available. `uv pip check` verifies installed dependencies.
A separate `uv sync --locked --no-default-groups` checks that the source quickstart
now installs the project successfully.

The final stage starts from the clean Python image and receives only uv, the
wheel's installed environment, the test harness, and its expected-content manifest.
It contains no source checkout, build environment, or editable project install.
The runtime harness checks:

- Installation provenance identifies the built wheel and version; installed
  backend files match the SHA-256 digests recorded from the wheel.
- Every expected backend module imports from that wheel in the environment's
  `site-packages`; system/user packages, dev tools, and local embedding packages
  are excluded.
- Neither package metadata nor the environment advertises the broken `rag` CLI.
- Uvicorn starts from a fresh temporary working directory, with isolated Python
  imports and no source `--app-dir` or `PYTHONPATH`.
- `/api/health` returns `{"status":"ok"}`, OpenAPI contains the API routes, and
  model configuration confirms no API key is loaded.

Each runtime process uses a sanitized environment in production mode and temporary
storage. Runtime networking is restricted to loopback by `--network none`.
Startup has a 30-second deadline; failures include server logs and cleanup stops
the server. No model weights or provider calls are needed.

## Python versions

The default images are pinned by digest: Python 3.12.14 on Debian Bookworm and
uv 0.12.1. Digests fix the exact base images so their contents do not change
between runs; Bookworm keeps the Debian release consistent across interpreters.
The following commands extend core coverage to the other Python versions named
in the project classifiers, including the minimum supported version, Python 3.11:

```bash
docker buildx build --load --target core -f tests/smoke/Dockerfile \
  --build-arg PYTHON_IMAGE=python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84 \
  -t agentic-rag-smoke:core-py311 .
docker run --rm --network none agentic-rag-smoke:core-py311

docker buildx build --load --target core -f tests/smoke/Dockerfile \
  --build-arg PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e \
  -t agentic-rag-smoke:core-py313 .
docker run --rm --network none agentic-rag-smoke:core-py313
```

For wheel coverage on Python 3.11 and 3.13, run these same commands with
`--target wheel` and replace `core-py311`/`core-py313` with
`wheel-py311`/`wheel-py313` in both the build and run commands.

Digest pins are optional. To test with an updated Python image, `PYTHON_IMAGE`
also accepts plain tags such as `python:3.11-slim` or `python:3.13-slim`:

```bash
docker buildx build --pull --load --target core -f tests/smoke/Dockerfile \
  --build-arg PYTHON_IMAGE=python:3.13-slim \
  -t agentic-rag-smoke:core-py313-floating .
docker run --rm --network none agentic-rag-smoke:core-py313-floating
```

`--pull` checks for updated base images. Plain `slim` tags can change Python patch
versions and the Debian release; use `python:3.13-slim-bookworm` to keep Bookworm
while allowing image updates. When updating the pinned defaults or matrix
examples, resolve and review their digests, then rerun the matrix to validate
the updates, including security fixes.

A cached successful build may reuse its install checks; add `--no-cache` to
force those steps to execute again. Runtime checks execute on every run.

I005 owns the broader regression suite, and I008 can reuse these commands in CI.

## I002 validation results

Validated on 2026-09-14 with the pinned Linux images above and uv 0.12.1:

| Target | Python | Result |
| --- | --- | --- |
| `wheel` | 3.11.16 | Build, clean wheel install, quickstart sync, installed imports, health, and OpenAPI passed |
| `wheel` | 3.12.14 | Build, clean wheel install, quickstart sync, installed imports, health, and OpenAPI passed |
| `wheel` | 3.13.15 | Build, clean wheel install, quickstart sync, installed imports, health, and OpenAPI passed |
| `core` | 3.12.14 | Lock checks, imports, PDF extraction, startup, and deterministic upload/persistence passed |

All four containers ran with `--network none`. The checkout's Git-versioned wheel
also built successfully and passed archive inspection. Harness Ruff lint/format
checks and `git diff --check` passed. `uv lock --check --offline` passed with
`uv.lock` unchanged. Wheel runtime coverage here uses the core dependency profile;
local embedding model execution remains separate from packaging validation.
