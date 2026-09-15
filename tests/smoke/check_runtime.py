"""Dependency smoke checks, run directly with the runtime venv (no pytest required)."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import site
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
LOCAL_PACKAGES = ("sentence-transformers", "transformers", "torch")


def installed_packages() -> dict[str, str]:
    return {
        re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower(): dist.version
        for dist in importlib.metadata.distributions()
    }


def check_environment(profile: str) -> None:
    prefix = Path(sys.prefix).resolve()
    assert sys.prefix != sys.base_prefix, "Run with the isolated runtime venv"
    assert not site.ENABLE_USER_SITE, "User site-packages must be disabled"
    config = (prefix / "pyvenv.cfg").read_text().lower()
    assert "include-system-site-packages = false" in config
    for dist in importlib.metadata.distributions():
        location = Path(dist.locate_file("")).resolve()
        assert location.is_relative_to(prefix), f"External distribution: {location}"

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    installed = installed_packages()
    for requirement in metadata["dependency-groups"]["dev"]:
        name = re.split(r"[<>=!~;\[]", requirement, maxsplit=1)[0]
        assert name not in installed, f"Development dependency installed: {name}"
    for name in LOCAL_PACKAGES:
        assert (name in installed) == (profile == "local-embeddings"), name
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "profile": profile,
                "packages": installed,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def pdf_fixture() -> bytes:
    """Build a one-page text PDF without installing a fixture-generation library."""
    stream = b"BT /F1 12 Tf 20 100 Td (Dependency smoke PDF) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def check_imports(profile: str) -> None:
    check_environment(profile)
    # This harness checks source dependencies; check_wheel.py checks installed artifacts.
    sys.path.insert(0, str(ROOT))
    for path in sorted((ROOT / "backend").rglob("*.py")):
        parts = path.relative_to(ROOT).with_suffix("").parts
        module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        importlib.import_module(module)
        print(f"Imported {module}", flush=True)

    for module in ("uvicorn", "python_multipart", "pypdf"):
        importlib.import_module(module)
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    assert callable(ChatOpenAI) and callable(OpenAIEmbeddings)
    from backend.config import get_settings
    from backend.indexing.loader import load_file

    assert get_settings().mode == "production"
    assert get_settings().openai_api_key is None
    documents = load_file(Path.cwd() / "fixture.pdf", pdf_fixture())
    assert len(documents) == 1
    assert "Dependency smoke PDF" in documents[0].page_content

    if profile == "local-embeddings":
        from sentence_transformers import SentenceTransformer

        assert callable(SentenceTransformer)

    # Check imported extensions as well as distribution metadata locations.
    prefix = Path(sys.prefix).resolve()
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and "site-packages" in Path(filename).parts:
            assert Path(filename).resolve().is_relative_to(prefix), filename
    print("PASS: production imports, provider imports, PDF extraction, and isolation", flush=True)


def child_environment(directory: Path, mode: str) -> dict[str, str]:
    # Allowlist the environment: no credentials, inherited Python paths, or proxy settings.
    return {
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "MODE": mode,
        "DATA_DIR": str(directory / "data"),
        "UPLOAD_DIR": str(directory / "uploads"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONNOUSERSITE": "1",
        "HF_HOME": str(directory / "models"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }


def request_json(url: str, data: bytes | None = None, content_type: str = "application/json"):
    request = Request(url, data=data, headers={"Content-Type": content_type})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        assert response.status == 200, response.status
        return json.load(response)


@contextmanager
def running_server(directory: Path, mode: str):
    # Each Docker run has its own network namespace; use an available loopback port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with (directory / "server.log").open("w+") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-m",
                "uvicorn",
                "backend.main:app",
                "--app-dir",
                str(ROOT),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=directory,
            env=child_environment(directory, mode),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                assert process.poll() is None, f"Uvicorn exited with {process.returncode}"
                try:
                    assert request_json(f"{url}/api/health") == {"status": "ok"}
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "Uvicorn did not become healthy within 30 seconds"
                        ) from None
                    time.sleep(0.1)
            yield url
            assert process.poll() is None, "Uvicorn exited during the smoke test"
        except BaseException:
            log.flush()
            log.seek(0)
            print(log.read(), file=sys.stderr, flush=True)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def check_upload(url: str, directory: Path) -> None:
    boundary = "dependency-smoke-boundary"
    fields = {"name": "Dependency smoke", "embedding_model": "smoke-hash"}
    body = b""
    for name, value in fields.items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
        ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="smoke.txt"'
        "\r\nContent-Type: text/plain\r\n\r\nDependency smoke text.\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    kb = request_json(f"{url}/api/kb", body, f"multipart/form-data; boundary={boundary}")
    assert kb["name"] == fields["name"]
    assert kb["file_count"] == 1
    kb_dir = directory / "data" / "kbs" / kb["id"]
    assert (kb_dir / "vectors.pkl").stat().st_size > 0
    assert json.loads((kb_dir / "manifest.json").read_text())["id"] == kb["id"]
    assert request_json(f"{url}/api/kb/{kb['id']}")["id"] == kb["id"]


def check_lock(profile: str) -> None:
    """Run during image construction while uv's installation cache is available."""
    lock = (ROOT / "uv.lock").read_bytes()
    installed = installed_packages()
    subprocess.run(["uv", "lock", "--check", "--offline"], cwd=ROOT, check=True, timeout=120)
    command = ["uv", "sync", "--locked", "--offline", "--no-default-groups", "--no-install-project"]
    if profile == "local-embeddings":
        command += ["--extra", profile]
    subprocess.run(command, cwd=ROOT, check=True, timeout=120)
    assert (ROOT / "uv.lock").read_bytes() == lock, "Locked sync modified uv.lock"
    assert installed_packages() == installed, "Repeated sync changed installed versions"

    with tempfile.TemporaryDirectory(prefix="rag-stale-lock-") as temp:
        directory = Path(temp)
        for name in ("pyproject.toml", "uv.lock", "README.md"):
            shutil.copyfile(ROOT / name, directory / name)
        metadata = directory / "pyproject.toml"
        # Add a satisfiable direct dependency already present transitively. An
        # impossible version would fail resolution even without --locked.
        stale, count = re.subn(
            r'("fastapi[^"]*")', r'"idna>=3.11",\n    \1', metadata.read_text(), count=1
        )
        assert count == 1
        metadata.write_text(stale)
        # Changed metadata makes uv invoke the existing dynamic build backend.
        # Allow its build requirements to resolve here, during the online build;
        # --locked must still reject the changed runtime dependency declaration.
        result = subprocess.run(
            [argument for argument in command if argument != "--offline"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(directory / ".venv")},
        )
        assert result.returncode != 0, "Locked sync accepted stale dependency declarations"
        assert "lockfile" in result.stderr.lower() and "--locked" in result.stderr, result.stderr
        assert (directory / "uv.lock").read_bytes() == lock
    print(
        f"PASS: repeated sync and stale-lock rejection; lock sha256={hashlib.sha256(lock).hexdigest()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("core", "local-embeddings"), default="core")
    parser.add_argument("--imports-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--check-lock", action="store_true", help="Check lock during image build")
    args = parser.parse_args()
    if args.check_lock:
        check_lock(args.profile)
        return
    if args.imports_only:
        check_imports(args.profile)
        return

    with tempfile.TemporaryDirectory(prefix="rag-runtime-smoke-") as temp:
        directory = Path(temp)
        subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--imports-only",
                "--profile",
                args.profile,
            ],
            cwd=directory,
            env=child_environment(directory, "production"),
            check=True,
            timeout=120,
        )
        with running_server(directory, "production") as url:
            schema = request_json(f"{url}/openapi.json")
            assert "/api/kb" in schema["paths"]
            assert request_json(f"{url}/api/models/config")["has_api_key"] is False
        print("PASS: production Uvicorn startup, health, and OpenAPI", flush=True)
        with running_server(directory, "deterministic") as url:
            check_upload(url, directory)
        print("PASS: deterministic multipart upload and persistence", flush=True)


if __name__ == "__main__":
    main()
