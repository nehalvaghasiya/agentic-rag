These smoke tests verify runtime dependencies from a clean source checkout.
They use a standard-library harness inside a virtual environment, with no pytest
or other development packages. Docker with Buildx is required. Run all commands
from the repository root.

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

Both targets start from the same clean base and perform a locked installation
with `--no-default-groups --no-install-project`. The optional target also passes
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

I002 still owns the wheel layout and broken `rag` entry point. I005 owns the
broader regression suite, and I008 can reuse these commands in CI. These tests
prove source-checkout runtime installation, not installed-wheel correctness.
