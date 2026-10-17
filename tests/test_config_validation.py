"""Runtime constraints, isolated settings sources, and safe startup failures."""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
import warnings
from contextlib import AsyncExitStack
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings.sources import DotEnvSettingsSource

import backend.main as main
from backend.config import ConfigurationError, Settings, resolve_settings
from backend.indexing.embedder import HashEmbedder
from backend.llm import get_embedder, get_llm
from backend.services import AppServices


@pytest.mark.parametrize(
    "values",
    [
        {"chunk_size": 1, "chunk_overlap": 0},
        {"chunk_size": 120, "chunk_overlap": 119},
        {"chunk_overlap": 0},
        {"top_k": 1},
        {"max_retries": 0},
        {
            "chunk_size": 10**12,
            "chunk_overlap": 10**12 - 1,
            "top_k": 10**12,
            "max_retries": 10**12,
        },
    ],
)
def test_valid_boundaries_and_large_values_are_preserved(settings_factory, values: dict) -> None:
    settings = resolve_settings(settings_factory(**values))
    for field, value in values.items():
        assert getattr(settings, field) == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chunk_size", -1),
        ("chunk_size", 0),
        ("chunk_overlap", -1),
        ("top_k", -1),
        ("top_k", 0),
        ("max_retries", -1),
    ],
)
def test_settings_reject_invalid_minimums(settings_factory, field: str, value: int) -> None:
    with pytest.raises(ValidationError) as error:
        settings_factory(**{field: value})
    assert error.value.errors(include_input=False)[0]["loc"] == (field,)


@pytest.mark.parametrize("field", ["chunk_size", "chunk_overlap", "top_k", "max_retries"])
@pytest.mark.parametrize("value", [True, False, 1.5, "1.5", "invalid", ""])
def test_limits_reject_booleans_fractional_values_and_invalid_strings(
    settings_factory, field: str, value: object
) -> None:
    with pytest.raises(ValidationError) as error:
        settings_factory(**{field: value})
    assert error.value.errors(include_input=False)[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "values",
    [
        {"chunk_size": 120},  # Conflicts with the default overlap.
        {"chunk_size": 4, "chunk_overlap": 4},
        {"chunk_size": 4, "chunk_overlap": 5},
    ],
)
def test_settings_reject_incompatible_chunk_combinations(settings_factory, values: dict) -> None:
    with pytest.raises(ValidationError, match="CHUNK_OVERLAP must be smaller than CHUNK_SIZE"):
        settings_factory(**values)


@pytest.mark.parametrize("mode", ["", "development", "Production", "DETERMINISTIC", "production "])
def test_operating_mode_must_be_explicitly_supported(settings_factory, mode: str) -> None:
    with pytest.raises(ValidationError) as error:
        settings_factory(mode=mode)
    assert error.value.errors(include_input=False)[0]["loc"] == ("mode",)


async def test_default_production_settings_start_without_credentials(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    app = main.create_app()
    async with app.router.lifespan_context(app):
        settings = app.state.services.settings
        assert settings.mode == "production"
        assert settings.openai_api_key is None
        assert (
            settings.chunk_size,
            settings.chunk_overlap,
            settings.top_k,
            settings.max_retries,
        ) == (800, 120, 5, 2)
        assert get_llm(settings) is None


def test_deterministic_mode_ignores_configured_provider_credentials(settings_factory) -> None:
    settings = resolve_settings(
        settings_factory(openai_api_key=SecretStr("configured-secret"), mode="deterministic")
    )
    assert get_llm(settings) is None
    assert isinstance(get_embedder("text-embedding-3-small", settings), HashEmbedder)


def test_environment_integer_strings_are_parsed(monkeypatch) -> None:
    for field, value in (
        ("CHUNK_SIZE", "2"),
        ("CHUNK_OVERLAP", "1"),
        ("TOP_K", "1"),
        ("MAX_RETRIES", "0"),
    ):
        monkeypatch.setenv(field, value)
    settings = resolve_settings()
    assert (settings.chunk_size, settings.chunk_overlap, settings.top_k, settings.max_retries) == (
        2,
        1,
        1,
        0,
    )


def test_settings_sources_retain_existing_precedence(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "CHUNK_SIZE=20\nCHUNK_OVERLAP=4\nTOP_K=6\nMODE=deterministic\nUNRELATED_SETTING=ignored\n"
    )
    monkeypatch.setenv("TOP_K", "7")
    settings = Settings(top_k=9)
    assert settings.top_k == 9
    loaded = resolve_settings()
    assert loaded.top_k == 7
    assert loaded.chunk_size == 20
    assert loaded.chunk_overlap == 4
    assert loaded.max_retries == 2
    assert loaded.mode == "deterministic"


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("TOP_K=0\n", "TOP_K must be an integer greater than or equal to 1"),
        ("CHUNK_SIZE=4\nCHUNK_OVERLAP=4\n", "CHUNK_OVERLAP must be smaller than CHUNK_SIZE"),
        ("MODE=unsupported\n", "MODE must be 'production' or 'deterministic'"),
        ("CORS_ORIGINS=invalid-json\n", "CORS_ORIGINS must be a JSON array of strings"),
    ],
)
def test_invalid_dotenv_values_fail_factory_creation(
    tmp_path: Path, contents: str, message: str
) -> None:
    (tmp_path / ".env").write_text(contents)
    with pytest.raises(ConfigurationError, match=message):
        main.create_app()
    assert not (tmp_path / ".data").exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("CHUNK_SIZE", "0", "CHUNK_SIZE must be an integer greater than or equal to 1"),
        ("CHUNK_OVERLAP", "-1", "CHUNK_OVERLAP must be an integer greater than or equal to 0"),
        ("TOP_K", "not-an-integer", "TOP_K must be an integer greater than or equal to 1"),
        ("MAX_RETRIES", "-1", "MAX_RETRIES must be an integer greater than or equal to 0"),
        ("MODE", "invalid", "MODE must be 'production' or 'deterministic'"),
    ],
)
def test_invalid_environment_fails_before_application_and_service_construction(
    monkeypatch, tmp_path: Path, field: str, value: str, message: str
) -> None:
    data_dir = tmp_path / "unopened-storage"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv(field, value)

    def forbidden_app(*args, **kwargs):
        pytest.fail("Invalid configuration must fail before FastAPI construction")

    async def forbidden_services(settings: Settings, stack: AsyncExitStack) -> AppServices:
        pytest.fail("Invalid configuration must fail before service construction")

    monkeypatch.setattr(main, "FastAPI", forbidden_app)
    with pytest.raises(ConfigurationError, match=message):
        main.create_app(services_factory=forbidden_services)
    assert not data_dir.exists()


def test_multiple_independent_errors_are_reported_together(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "0")
    monkeypatch.setenv("TOP_K", "0")
    monkeypatch.setenv("MAX_RETRIES", "-1")
    with pytest.raises(ConfigurationError) as error:
        resolve_settings()
    message = str(error.value)
    assert message.startswith("Invalid runtime configuration:\n")
    for field in ("CHUNK_SIZE", "TOP_K", "MAX_RETRIES"):
        assert f"- {field} must be an integer" in message


@pytest.mark.parametrize("source", ["mutation", "copy"])
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("top_k", -1, "TOP_K must be an integer greater than or equal to 1"),
        ("max_retries", -1, "MAX_RETRIES must be an integer greater than or equal to 0"),
        ("chunk_overlap", 800, "CHUNK_OVERLAP must be smaller than CHUNK_SIZE"),
        ("mode", "invalid", "MODE must be 'production' or 'deterministic'"),
    ],
)
def test_factory_revalidates_supplied_settings(
    settings: Settings, source: str, field: str, value: object, message: str
) -> None:
    if source == "copy":
        settings = settings.model_copy(update={field: value})
    else:
        setattr(settings, field, value)
    with pytest.raises(ConfigurationError, match=message):
        main.create_app(settings)
    assert not settings.data_dir.exists()


async def test_explicit_snapshot_ignores_invalid_external_sources(
    settings: Settings, monkeypatch, tmp_path: Path
) -> None:
    secret = SecretStr("explicit-credential")
    settings.openai_api_key = secret
    (tmp_path / ".env").write_bytes(b"\xffinvalid utf8")
    monkeypatch.setenv("CORS_ORIGINS", "invalid-json")
    monkeypatch.setenv("MODE", "invalid-mode")
    monkeypatch.setenv("TOP_K", "invalid-integer")

    app = main.create_app(settings)
    async with app.router.lifespan_context(app):
        snapshot = app.state.services.settings
        assert snapshot is not settings
        assert snapshot.cors_origins == settings.cors_origins
        assert snapshot.cors_origins is not settings.cors_origins
        assert snapshot.mode == settings.mode
        assert snapshot.top_k == settings.top_k
        assert isinstance(snapshot.openai_api_key, SecretStr)
        assert snapshot.openai_api_key.get_secret_value() == secret.get_secret_value()


@pytest.mark.parametrize("source", ["environment", "copied-settings", "chunk-combination"])
def test_diagnostics_never_expose_inputs_or_credentials(
    source: str, settings: Settings, monkeypatch, capsys, caplog
) -> None:
    credential = "sensitive-provider-credential"
    invalid_input = "sensitive-invalid-field"
    monkeypatch.setenv("OPENAI_API_KEY", credential)
    if source == "environment":
        monkeypatch.setenv("TOP_K", invalid_input)
        supplied = None
    elif source == "copied-settings":
        supplied = settings.model_copy(
            update={"top_k": invalid_input, "openai_api_key": credential}
        )
    else:
        monkeypatch.setenv("CHUNK_SIZE", "1")
        supplied = None

    with warnings.catch_warnings(record=True) as captured_warnings:
        with pytest.raises(ConfigurationError) as error:
            main.create_app(supplied)
    captured = capsys.readouterr()
    output = (
        str(error.value)
        + repr(error.value)
        + "".join(traceback.format_exception(error.value))
        + captured.out
        + captured.err
        + caplog.text
    )
    assert "Invalid runtime configuration" in output
    assert credential not in output
    assert invalid_input not in output
    assert "input_value" not in output
    assert "https://errors.pydantic.dev" not in output
    assert error.value.__suppress_context__ is True
    assert not captured_warnings


def test_direct_settings_validation_hides_secret_input() -> None:
    secret = "sensitive-direct-credential"
    with pytest.raises(ValidationError) as error:
        Settings(chunk_size=1, openai_api_key=secret)
    assert "CHUNK_OVERLAP must be smaller than CHUNK_SIZE" in str(error.value)
    assert secret not in str(error.value)
    assert "input_value" not in str(error.value)


@pytest.mark.parametrize("contents", ["private-json-sentinel", '{"private-json-sentinel": 1}'])
def test_cors_parse_and_type_errors_have_safe_actionable_messages(
    monkeypatch, contents: str
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", contents)
    with pytest.raises(ConfigurationError) as error:
        main.create_app()
    assert "CORS_ORIGINS must be a JSON array of strings" in str(error.value)
    assert "private-json-sentinel" not in "".join(traceback.format_exception(error.value))


def test_dotenv_decoding_failure_has_safe_diagnostic(tmp_path: Path) -> None:
    (tmp_path / ".env").write_bytes(b"\xffprivate-file-contents")
    with pytest.raises(ConfigurationError, match="UTF-8 encoding and read permissions") as error:
        main.create_app()
    assert "private-file-contents" not in "".join(traceback.format_exception(error.value))


def test_dotenv_read_failure_has_safe_diagnostic(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".env").touch()

    def unreadable(*args, **kwargs):
        raise PermissionError("private-file-location")

    monkeypatch.setattr(DotEnvSettingsSource, "_read_env_file", unreadable)
    with pytest.raises(ConfigurationError, match="UTF-8 encoding and read permissions") as error:
        main.create_app()
    assert "private-file-location" not in "".join(traceback.format_exception(error.value))


@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_uvicorn_rejects_invalid_configuration_without_exposing_secrets(
    tmp_path: Path, source: str
) -> None:
    data_dir = tmp_path / "unopened-storage"
    credential = "subprocess-provider-secret"
    invalid_value = "subprocess-invalid-limit"
    environment = {
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "DATA_DIR": str(data_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    values = {"MODE": "production", "OPENAI_API_KEY": credential, "TOP_K": invalid_value}
    if source == "environment":
        environment.update(values)
    else:
        (tmp_path / ".env").write_text(
            "\n".join(f"{name}={value}" for name, value in values.items())
        )

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "uvicorn",
            "backend.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Invalid runtime configuration" in output
    assert "TOP_K must be an integer greater than or equal to 1" in output
    assert credential not in output
    assert invalid_value not in output
    assert not data_dir.exists()
