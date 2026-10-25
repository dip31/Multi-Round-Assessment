from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from scripts.audit_supabase_destination import (
    AuditBlocked,
    SUPABASE_CA_PATH,
    client_tls_metadata,
    classify_endpoint,
    load_audit_config,
    safe_database_error_category,
    tls_url,
    validate_ca_certificate,
)


def _write_env(path: Path, *, url: str | None, project_ref: str | None) -> None:
    entries = [
        "DATABASE_URL=postgresql://local-user:local-secret@localhost/app",
        "SECRET_KEY=app-secret-placeholder",
    ]
    if url is not None:
        entries.append(f"EDI5_SUPABASE_AUDIT_URL={url}")
    if project_ref is not None:
        entries.append(f"EDI5_SUPABASE_EXPECTED_PROJECT_REF={project_ref}")
    path.write_text("\n".join(entries), encoding="utf-8")


def test_missing_audit_url_is_reported_without_exposing_values(tmp_path: Path) -> None:
    env_file = tmp_path / "empty.env"
    _write_env(env_file, url=None, project_ref="a" * 20)

    with pytest.raises(AuditBlocked, match="EDI5_SUPABASE_AUDIT_URL is not configured"):
        load_audit_config(environ={}, dotenv_path=env_file)


def test_missing_project_reference_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / "missing-ref.env"
    _write_env(
        env_file,
        url="postgresql://audit-user:dummy-secret@example.supabase.co:5432/postgres",
        project_ref=None,
    )

    with pytest.raises(
        AuditBlocked,
        match="EDI5_SUPABASE_EXPECTED_PROJECT_REF is not configured",
    ):
        load_audit_config(environ={}, dotenv_path=env_file)


def test_malformed_project_reference_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / "malformed-ref.env"
    _write_env(
        env_file,
        url="postgresql://audit-user:dummy-secret@example.supabase.co:5432/postgres",
        project_ref="not-a-valid-project-ref",
    )

    with pytest.raises(AuditBlocked, match="20-character project reference"):
        load_audit_config(environ={}, dotenv_path=env_file)


def test_audit_config_works_when_application_settings_reject_extra_dotenv_keys(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "app-and-audit.env"
    audit_url = "postgresql://audit-user:dummy-secret@example.supabase.co:5432/postgres"
    project_ref = "a" * 20
    _write_env(env_file, url=audit_url, project_ref=project_ref)

    class StrictAppSettingsProbe(BaseSettings):
        model_config = SettingsConfigDict(env_file=str(env_file), extra="forbid")
        DATABASE_URL: str
        SECRET_KEY: str

    with pytest.raises(ValidationError):
        StrictAppSettingsProbe()

    class AppSettingsProbe(BaseSettings):
        model_config = SettingsConfigDict(env_file=str(env_file), extra="ignore")
        DATABASE_URL: str
        SECRET_KEY: str

    app_settings = AppSettingsProbe()
    assert make_url(app_settings.DATABASE_URL).host == "localhost"

    loaded_url, loaded_ref = load_audit_config(environ={}, dotenv_path=env_file)
    assert make_url(loaded_url).host == "example.supabase.co"
    assert loaded_ref == project_ref


def test_process_environment_overrides_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / "configured.env"
    _write_env(
        env_file,
        url="postgresql://file-user:file-secret@file.supabase.co:5432/postgres",
        project_ref="a" * 20,
    )
    process_values = {
        "EDI5_SUPABASE_AUDIT_URL": "postgresql://process-user:process-secret@process.supabase.co:5432/postgres",
        "EDI5_SUPABASE_EXPECTED_PROJECT_REF": "b" * 20,
    }

    loaded_url, loaded_ref = load_audit_config(
        environ=process_values, dotenv_path=env_file
    )

    assert make_url(loaded_url).host == "process.supabase.co"
    assert loaded_ref == "b" * 20


def test_tls_defaults_to_full_certificate_and_hostname_verification() -> None:
    parsed = tls_url(
        "postgresql://audit-user:dummy-secret@" + "a" * 20 + ".supabase.co:5432/postgres"
    )
    assert parsed.query["sslmode"] == "verify-full"
    assert parsed.query["sslrootcert"] == str(SUPABASE_CA_PATH.resolve())
    assert classify_endpoint(parsed) == ("direct", "a" * 20)


def test_weaker_tls_mode_is_strengthened_to_verify_full() -> None:
    parsed = tls_url(
        "postgresql://audit-user:dummy-secret@" + "a" * 20 + ".supabase.co/postgres?sslmode=require"
    )
    assert parsed.query["sslmode"] == "verify-full"


def test_tls_disabled_or_fallback_mode_is_rejected() -> None:
    for mode in ("disable", "allow", "prefer"):
        with pytest.raises(AuditBlocked, match="explicitly permits"):
            tls_url(
                "postgresql://user:dummy@" + "a" * 20 + f".supabase.co/postgres?sslmode={mode}"
            )


def test_client_tls_metadata_requires_positive_driver_evidence() -> None:
    info = SimpleNamespace(
        get_parameters=lambda: {
            "sslmode": "verify-full",
            "sslrootcert": str(SUPABASE_CA_PATH.resolve()),
        }
    )
    connection = SimpleNamespace(
        connection=SimpleNamespace(
            driver_connection=SimpleNamespace(
                info=info,
                pgconn=SimpleNamespace(ssl_in_use=True),
            )
        )
    )
    assert client_tls_metadata(connection) == (
        "not exposed by psycopg 3",
        "not exposed by psycopg 3",
    )

    connection.connection.driver_connection.pgconn.ssl_in_use = False
    with pytest.raises(AuditBlocked, match="does not confirm active TLS"):
        client_tls_metadata(connection)


def test_client_tls_metadata_rejects_wrong_active_ca_parameters() -> None:
    info = SimpleNamespace(
        get_parameters=lambda: {
            "sslmode": "verify-full",
            "sslrootcert": "C:/wrong/ca.crt",
        }
    )
    connection = SimpleNamespace(
        connection=SimpleNamespace(
            driver_connection=SimpleNamespace(
                info=info,
                pgconn=SimpleNamespace(ssl_in_use=True),
            )
        )
    )
    with pytest.raises(AuditBlocked, match="not using the verified Supabase CA file"):
        client_tls_metadata(connection)


def test_database_error_categories_are_safe_and_redacted() -> None:
    tls_error = RuntimeError("certificate verify failed for postgres://user:secret@host")
    assert safe_database_error_category(tls_error) == "TLS certificate/hostname validation failed"
    assert "secret" not in safe_database_error_category(tls_error)

    net_error = RuntimeError("connection timed out for postgres://user:secret@host")
    assert safe_database_error_category(net_error) == "network connection failed"


def test_supabase_ca_file_is_valid_and_current() -> None:
    assert validate_ca_certificate() == SUPABASE_CA_PATH.resolve()


def test_missing_ca_file_fails_safely(tmp_path: Path) -> None:
    with pytest.raises(AuditBlocked, match="certificate file is missing"):
        validate_ca_certificate(tmp_path / "missing.crt")


def test_invalid_ca_file_fails_safely(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.crt"
    invalid.write_text("not a PEM certificate", encoding="utf-8")

    with pytest.raises(AuditBlocked, match="malformed, invalid, or not a trusted CA"):
        validate_ca_certificate(invalid)
