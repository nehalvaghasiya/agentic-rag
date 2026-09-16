"""Inspect the built wheel, then smoke-test its isolated installation without source."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import re
import site
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


def inspect_wheel(directory: Path, source: Path) -> None:
    wheels = list(directory.glob("*.whl"))
    assert len(wheels) == 1, f"Expected one freshly built wheel, found {wheels}"
    wheel = wheels[0]
    expected = {path.relative_to(source).as_posix() for path in (source / "backend").rglob("*.py")}
    assert "backend/main.py" in expected and "backend/__init__.py" in expected
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert expected <= names, f"Missing backend modules: {sorted(expected - names)}"
        assert all(
            name.startswith("backend/") or name.split("/")[0].endswith(".dist-info")
            for name in names
        ), f"Unexpected wheel contents: {sorted(names)}"
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        assert len(metadata_paths) == 1
        metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode())
        assert metadata["Name"] == "rag"
        assert metadata["Version"]
        for name in names:
            if name.endswith(".dist-info/entry_points.txt"):
                entries = configparser.ConfigParser()
                entries.read_string(archive.read(name).decode())
                assert not entries.has_option("console_scripts", "rag"), "Broken rag CLI advertised"
        modules = {
            name: hashlib.sha256(archive.read(name)).hexdigest() for name in sorted(expected)
        }

    project = tomllib.loads((source / "pyproject.toml").read_text())
    forbidden = [
        re.split(r"[<>=!~;\[]", req, maxsplit=1)[0] for req in project["dependency-groups"]["dev"]
    ]
    manifest = {
        "wheel": wheel.name,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "version": metadata["Version"],
        "modules": modules,
        "forbidden_distributions": forbidden + ["sentence-transformers", "transformers", "torch"],
    }
    (directory / "wheel-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS: wheel contents and entry points; {json.dumps(manifest)}", flush=True)


def check_installation(manifest: dict) -> None:
    prefix = Path(sys.prefix).resolve()
    assert sys.prefix != sys.base_prefix, "Run inside the wheel's runtime environment"
    assert sys.flags.isolated and not site.ENABLE_USER_SITE
    assert "include-system-site-packages = false" in (prefix / "pyvenv.cfg").read_text().lower()
    installed = {}
    for dist in importlib.metadata.distributions():
        location = Path(dist.locate_file("")).resolve()
        assert location.is_relative_to(prefix), f"External distribution: {location}"
        name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
        installed[name] = dist.version
    for name in manifest["forbidden_distributions"]:
        assert name not in installed, f"Unexpected dependency in core wheel environment: {name}"

    dist = importlib.metadata.distribution("rag")
    assert dist.version == manifest["version"]
    assert not any(ep.group == "console_scripts" and ep.name == "rag" for ep in dist.entry_points)
    assert not (prefix / "bin" / "rag").exists(), "Broken rag executable installed"
    origin = json.loads(dist.read_text("direct_url.json") or "{}")
    assert "archive_info" in origin and origin["url"].endswith(manifest["wheel"]), origin

    for filename, digest in manifest["modules"].items():
        parts = Path(filename).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        module = importlib.import_module(name)
        location = Path(module.__file__).resolve()
        assert location == Path(dist.locate_file(filename)).resolve(), location
        assert location.is_relative_to(prefix) and "site-packages" in location.parts, location
        assert hashlib.sha256(location.read_bytes()).hexdigest() == digest, location
    from backend.config import get_settings

    assert get_settings().mode == "production"
    assert get_settings().openai_api_key is None
    print(
        json.dumps(
            {"python": platform.python_version(), "wheel": manifest["wheel"], "packages": installed}
        ),
        flush=True,
    )
    print("PASS: all backend modules import from the installed wheel; no rag CLI", flush=True)


def request_json(url: str):
    with build_opener(ProxyHandler({})).open(url, timeout=5) as response:
        assert response.status == 200, response.status
        return json.load(response)


def check_startup(directory: Path) -> None:
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
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=directory,
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
            schema = request_json(f"{url}/openapi.json")
            assert {"/api/kb", "/api/health"} <= schema["paths"].keys()
            assert request_json(f"{url}/api/models/config")["has_api_key"] is False
            assert process.poll() is None, "Uvicorn exited during the smoke test"
        except BaseException:
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
    print(
        "PASS: installed-wheel Uvicorn startup, health, and OpenAPI outside the checkout",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inspect", type=Path, help="Inspect a directory containing one built wheel"
    )
    parser.add_argument(
        "--source-root", type=Path, help="Source tree to compare with the built wheel"
    )
    parser.add_argument("--runtime-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inspect:
        if args.source_root is None:
            parser.error("--inspect requires --source-root")
        inspect_wheel(args.inspect, args.source_root)
        return
    if args.runtime_child:
        manifest = json.loads(Path(__file__).with_name("wheel-manifest.json").read_text())
        check_installation(manifest)
        check_startup(Path.cwd())
        return

    with tempfile.TemporaryDirectory(prefix="rag-wheel-smoke-") as temp:
        directory = Path(temp)
        # Sanitize before importing settings: no checkout paths, credentials, or model cache.
        environment = {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "MODE": "production",
            "DATA_DIR": str(directory / "data"),
            "UPLOAD_DIR": str(directory / "uploads"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "HF_HOME": str(directory / "models"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
        subprocess.run(
            [sys.executable, "-I", str(Path(__file__).resolve()), "--runtime-child"],
            cwd=directory,
            env=environment,
            check=True,
            timeout=120,
        )


if __name__ == "__main__":
    main()
