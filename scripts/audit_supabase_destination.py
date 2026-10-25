"""Read-only, isolated audit of the configured Supabase PostgreSQL destination.

This script deliberately does not import application Settings. It reads only
the audit URL and expected project reference from the process environment or
the repository .env file, with process environment taking precedence.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, ed448, padding, rsa
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


ROOT = Path(__file__).resolve().parents[1]
SUPABASE_CA_PATH = ROOT / "certs" / "supabase-project-ca.crt"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
AUDIT_URL_KEY = "EDI5_SUPABASE_AUDIT_URL"
EXPECTED_PROJECT_KEY = "EDI5_SUPABASE_EXPECTED_PROJECT_REF"
PROJECT_REF_RE = re.compile(r"^[a-z0-9]{20}$")


class AuditBlocked(Exception):
    """A safe-to-report audit precondition or identity failure."""


@dataclass
class AuditResult:
    lines: list[str]
    blockers: list[str]


def load_audit_config(
    environ: Mapping[str, str] | None = None,
    dotenv_path: Path = ROOT / ".env",
) -> tuple[str, str]:
    """Load audit-only values without constructing application Settings."""
    process = os.environ if environ is None else environ
    file_values = dotenv_values(dotenv_path) if dotenv_path.exists() else {}
    url = process.get(AUDIT_URL_KEY) or file_values.get(AUDIT_URL_KEY)
    expected_ref = process.get(EXPECTED_PROJECT_KEY) or file_values.get(
        EXPECTED_PROJECT_KEY
    )
    if not url:
        raise AuditBlocked(f"{AUDIT_URL_KEY} is not configured")
    if not expected_ref:
        raise AuditBlocked(f"{EXPECTED_PROJECT_KEY} is not configured")
    if not PROJECT_REF_RE.fullmatch(expected_ref):
        raise AuditBlocked(
            f"{EXPECTED_PROJECT_KEY} must contain the expected 20-character project reference"
        )
    return str(url), str(expected_ref)


def validate_ca_certificate(path: Path = SUPABASE_CA_PATH) -> Path:
    """Validate the pinned Supabase CA file before using it as a trust anchor."""
    if not path.is_file():
        raise AuditBlocked("Verified Supabase CA certificate file is missing")
    try:
        pem = path.read_bytes()
        if pem.count(b"-----BEGIN CERTIFICATE-----") != 1:
            raise ValueError("unexpected certificate block count")
        cert = x509.load_pem_x509_certificate(pem)
        constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not constraints.ca or not usage.key_cert_sign or cert.subject != cert.issuer:
            raise ValueError("certificate is not a self-issued CA trust anchor")
        now = datetime.now(timezone.utc)
        if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
            raise ValueError("certificate is outside its validity period")

        key = cert.public_key()
        if isinstance(key, rsa.RSAPublicKey):
            key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
        elif isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm))
        elif isinstance(key, dsa.DSAPublicKey):
            key.verify(cert.signature, cert.tbs_certificate_bytes, cert.signature_hash_algorithm)
        elif isinstance(key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
            key.verify(cert.signature, cert.tbs_certificate_bytes)
        else:
            raise ValueError("unsupported CA public key type")
    except InvalidSignature:
        raise AuditBlocked("Supabase CA certificate self-signature is invalid") from None
    except AuditBlocked:
        raise
    except Exception:
        raise AuditBlocked("Supabase CA certificate is malformed, invalid, or not a trusted CA") from None
    return path.resolve()


def tls_url(url: str, ca_path: Path = SUPABASE_CA_PATH):
    """Require encrypted TLS with CA and hostname verification."""
    parsed = make_url(url)
    if parsed.drivername not in (
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    ):
        raise AuditBlocked("Audit URL must use a supported PostgreSQL driver")
    query = dict(parsed.query)
    sslmode = str(query.get("sslmode", "")).lower()
    if sslmode in {"disable", "allow", "prefer"}:
        raise AuditBlocked(
            "Audit URL explicitly permits an unverified or plaintext connection; configure certificate-verified TLS"
        )
    # Strengthen missing/require/verify-ca modes to verify-full for this audit.
    # Pin the verified CA file while preserving the URL hostname for SAN checks.
    query["sslmode"] = "verify-full"
    query["sslrootcert"] = str(validate_ca_certificate(ca_path))
    return parsed.set(query=query)


def client_tls_metadata(
    connection, expected_ca_path: Path = SUPABASE_CA_PATH
) -> tuple[str, str]:
    """Verify client TLS and the active libpq parameters used for this connection."""
    try:
        raw = connection.connection.driver_connection
        info = raw.info
        pgconn = getattr(raw, "pgconn", None)
        if pgconn is not None and hasattr(pgconn, "ssl_in_use"):
            ssl_in_use = pgconn.ssl_in_use
            parameters = info.get_parameters()
            protocol = "not exposed by psycopg 3"
            cipher = "not exposed by psycopg 3"
        else:
            ssl_in_use = info.ssl_in_use
            parameters = getattr(info, "dsn_parameters", {})
            attribute = getattr(info, "ssl_attribute", None)
            protocol = attribute("protocol") if attribute else None
            cipher = attribute("cipher") if attribute else None
            protocol = str(protocol or "not exposed by driver")
            cipher = str(cipher or "not exposed by driver")

        if ssl_in_use is not True:
            raise AuditBlocked("Client connection metadata does not confirm active TLS")
        if parameters.get("sslmode") != "verify-full":
            raise AuditBlocked("Active driver connection is not configured with sslmode=verify-full")
        configured_ca = parameters.get("sslrootcert")
        if not configured_ca or Path(configured_ca).resolve() != expected_ca_path.resolve():
            raise AuditBlocked("Active driver connection is not using the verified Supabase CA file")
        return protocol, cipher
    except AuditBlocked:
        raise
    except Exception:
        raise AuditBlocked("TLS could not be verified from PostgreSQL client connection metadata") from None


def safe_database_error_category(exc: BaseException) -> str:
    """Classify driver errors without returning or logging exception text."""
    fragments = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        fragments.append(str(current).lower())
        current = current.__cause__ or current.__context__
    details = " ".join(fragments)
    if any(token in details for token in (
        "certificate verify failed", "root certificate file", "self signed certificate",
        "hostname mismatch", "does not match host", "certificate has expired",
    )):
        return "TLS certificate/hostname validation failed"
    if any(token in details for token in (
        "password authentication failed", "authentication failed", "invalid password",
    )):
        return "database authentication rejected"
    if any(token in details for token in (
        "could not translate host name", "name or service not known", "getaddrinfo failed",
    )):
        return "destination name resolution failed"
    if any(token in details for token in (
        "timed out", "connection refused", "network is unreachable", "permission denied",
    )):
        return "network connection failed"
    if "ssl" in details or "tls" in details:
        return "TLS negotiation failed"
    return "database connection or read-only query failed"


def classify_endpoint(url) -> tuple[str, str]:
    host = (url.host or "").lower()
    if host.endswith(".supabase.co") and host.count(".") == 2:
        project_ref = host.split(".", 1)[0]
        if not PROJECT_REF_RE.fullmatch(project_ref):
            raise AuditBlocked("Direct Supabase endpoint has an unrecognized project reference")
        return "direct", project_ref
    if host.endswith(".pooler.supabase.com"):
        if url.port == 6543:
            mode = "transaction pooler"
        elif url.port == 5432:
            mode = "session pooler"
        else:
            raise AuditBlocked("Supabase pooler mode is uncertain from the endpoint port")
        # Supabase pooler usernames conventionally identify the project as
        # `postgres.<project-ref>`; require that independent identity signal.
        return mode, ""
    raise AuditBlocked("Endpoint is not a recognized Supabase direct or pooler hostname")


def _catalog_query(connection, label: str, statement: str):
    try:
        return connection.execute(text(statement))
    except SQLAlchemyError as exc:
        original = getattr(exc, "orig", None)
        sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        suffix = f"SQLSTATE {sqlstate}" if sqlstate else "SQLSTATE unavailable"
        raise AuditBlocked(f"Read-only {label} catalog query failed ({suffix}; details redacted)") from None


def _catalog_snapshot(connection) -> dict[str, dict]:
    """Collect schema-only metadata; definitions stay in memory and are never printed."""
    table_rows = _catalog_query(
        connection,
        "table",
            "SELECT n.nspname, c.relname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('information_schema') "
            "AND n.nspname NOT LIKE 'pg_%'"
        ).all()
    tables = {(s, t): () for s, t in table_rows}

    columns = _catalog_query(
        connection,
        "column",
            "SELECT table_schema, table_name, column_name, data_type, udt_name, "
            "is_nullable, column_default, is_identity, identity_generation "
            "FROM information_schema.columns WHERE table_schema NOT IN ('information_schema') "
            "AND table_schema NOT LIKE 'pg_%'"
        ).all()
    column_map = {
        (row[0], row[1], row[2]): tuple(row[3:]) for row in columns
    }

    indexes = _catalog_query(
        connection,
        "index",
            "SELECT n.nspname, t.relname, irel.relname, ix.indisunique, ix.indisprimary, "
            "ix.indisvalid, pg_get_expr(ix.indpred, ix.indrelid), pg_get_indexdef(ix.indexrelid) "
            "FROM pg_index ix JOIN pg_class irel ON irel.oid=ix.indexrelid "
            "JOIN pg_class t ON t.oid=ix.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
            "WHERE n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%'"
        ).all()
    index_map = {(r[0], r[1], r[2]): tuple(r[3:]) for r in indexes}

    constraints = _catalog_query(
        connection,
        "constraint",
            "SELECT n.nspname, t.relname, c.conname, c.contype, c.convalidated, "
            "pg_get_constraintdef(c.oid, true) FROM pg_constraint c "
            "JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
            "WHERE n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%'"
        ).all()
    constraint_map = {(r[0], r[1], r[2]): tuple(r[3:]) for r in constraints}

    sequences = _catalog_query(
        connection,
        "sequence",
            "SELECT n.nspname, s.relname, ps.data_type, ps.start_value, ps.min_value, "
            "ps.max_value, ps.increment_by, ps.cycle, ps.cache_size, "
            "t.relname AS owned_table, a.attname AS owned_column "
            "FROM pg_class s JOIN pg_namespace n ON n.oid=s.relnamespace "
            "LEFT JOIN pg_sequences ps ON ps.schemaname=n.nspname AND ps.sequencename=s.relname "
            "LEFT JOIN pg_depend d ON d.objid=s.oid AND d.classid='pg_class'::regclass "
            "AND d.refclassid='pg_class'::regclass AND d.deptype IN ('a','i') "
            "LEFT JOIN pg_class t ON t.oid=d.refobjid "
            "LEFT JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid "
            "WHERE s.relkind='S' AND n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%'"
        ).all()
    sequence_map = {(r[0], r[1]): tuple(r[2:]) for r in sequences}

    extensions = _catalog_query(
        connection, "extension", "SELECT extname, extversion FROM pg_extension"
    ).all()
    extension_map = {(r[0],): (r[1],) for r in extensions}

    views = _catalog_query(
        connection,
        "view",
            "SELECT table_schema, table_name, view_definition FROM information_schema.views "
            "WHERE table_schema NOT IN ('information_schema') AND table_schema NOT LIKE 'pg_%'"
        ).all()
    view_map = {(r[0], r[1]): (r[2],) for r in views}

    routines = _catalog_query(
        connection,
        "routine",
            "SELECT routine_schema, routine_name, specific_name, routine_type, "
            "external_language, routine_definition FROM information_schema.routines "
            "WHERE routine_schema NOT IN ('information_schema') AND routine_schema NOT LIKE 'pg_%'"
        ).all()
    routine_map = {(r[0], r[1], r[2]): tuple(r[3:]) for r in routines}

    triggers = _catalog_query(
        connection,
        "trigger",
            "SELECT trigger_schema, event_object_table, trigger_name, action_timing, "
            "event_manipulation, action_statement FROM information_schema.triggers "
            "WHERE trigger_schema NOT IN ('information_schema') AND trigger_schema NOT LIKE 'pg_%'"
        ).all()
    trigger_map = {(r[0], r[1], r[2]): tuple(r[3:]) for r in triggers}

    alembic_table = _catalog_query(
        connection, "Alembic revision", "SELECT to_regclass('public.alembic_version') IS NOT NULL"
    ).scalar_one()
    alembic_version = None
    if alembic_table:
        alembic_version = _catalog_query(
            connection,
            "Alembic revision",
            "SELECT version_num FROM public.alembic_version ORDER BY version_num",
        ).scalars().all()

    return {
        "tables": tables,
        "columns": column_map,
        "indexes": index_map,
        "constraints": constraint_map,
        "sequences": sequence_map,
        "extensions": extension_map,
        "views": view_map,
        "routines": routine_map,
        "triggers": trigger_map,
        "alembic_version": {("revision", str(v)): () for v in (alembic_version or [])},
    }


def _compare_snapshots(source: dict[str, dict], destination: dict[str, dict]) -> list[str]:
    lines = []
    for name in (
        "tables", "columns", "indexes", "constraints", "sequences",
        "extensions", "views", "routines", "triggers", "alembic_version",
    ):
        src = source[name]
        dst = destination[name]
        if name not in ("extensions", "alembic_version"):
            src = {key: value for key, value in src.items() if key and key[0] == "public"}
            dst = {key: value for key, value in dst.items() if key and key[0] == "public"}
        missing = sorted(set(src) - set(dst), key=str)
        extra = sorted(set(dst) - set(src), key=str)
        changed = sorted((key for key in set(src) & set(dst) if src[key] != dst[key]), key=str)
        lines.append(
            f"Source comparison {name}: missing_in_destination={len(missing)}; "
            f"destination_only={len(extra)}; definitions_differ={len(changed)}"
        )
        if missing:
            lines.append(f"  Missing examples: {missing[:10]}")
        if extra:
            lines.append(f"  Destination-only examples: {extra[:10]}")
        if changed:
            lines.append(f"  Definition-difference examples: {changed[:10]}")
    return lines


def audit(url: str, expected_ref: str) -> AuditResult:
    endpoint_url = tls_url(url)
    mode, endpoint_ref = classify_endpoint(endpoint_url)
    if endpoint_ref and endpoint_ref != expected_ref:
        raise AuditBlocked("Endpoint project reference does not match the expected reference")
    if endpoint_url.database != "postgres":
        raise AuditBlocked("Destination database is not the expected Supabase postgres database")
    stage = "connection establishment"
    engine = create_engine(
        endpoint_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 8, "application_name": "edi5_read_only_audit"},
    )
    try:
        with engine.connect() as connection:
            # libpq verifies the CA and endpoint name before the connection opens.
            stage = "client TLS verification"
            tls_protocol, tls_cipher = client_tls_metadata(connection)
            with connection.begin():
                stage = "read-only transaction setup"
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                stage = "destination identity verification"
                identity = connection.execute(
                    text(
                        "SELECT current_database() AS db, current_user AS role, "
                        "current_setting('server_version') AS version, "
                        "inet_server_addr()::text AS server_addr"
                    )
                ).mappings().one()
                if identity["db"] != "postgres":
                    raise AuditBlocked("Connected database identity does not match the expected database")
                if mode == "direct" and endpoint_ref != expected_ref:
                    raise AuditBlocked("Connected endpoint identity is uncertain")
                if mode.endswith("pooler") and not (endpoint_url.username or "").endswith(
                    "." + expected_ref
                ):
                    raise AuditBlocked("Pooler username does not confirm the expected project reference")

                stage = "read-only inventory and privilege inspection"
                schemas = connection.execute(
                    text(
                        "SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name NOT IN ('information_schema') "
                        "AND schema_name NOT LIKE 'pg_%' ORDER BY schema_name"
                    )
                ).scalars().all()
                tables = connection.execute(
                    text(
                        "SELECT n.nspname AS table_schema, c.relname AS table_name, "
                        "GREATEST(c.reltuples, 0)::bigint AS estimated_rows "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE c.relkind IN ('r','p') "
                        "AND n.nspname NOT IN ('information_schema') "
                        "AND n.nspname NOT LIKE 'pg_%' "
                        "ORDER BY n.nspname, c.relname"
                    )
                ).all()
                table_tuples = [(row[0], row[1]) for row in tables]
                estimated_counts = [(row[0], row[1], int(row[2])) for row in tables]

                object_inventory = connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM pg_index i JOIN pg_class ic ON ic.oid=i.indexrelid "
                        " JOIN pg_namespace n ON n.oid=ic.relnamespace "
                        " WHERE n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%') AS indexes, "
                        "(SELECT count(*) FROM pg_index i JOIN pg_class ic ON ic.oid=i.indexrelid "
                        " JOIN pg_namespace n ON n.oid=ic.relnamespace "
                        " WHERE n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%' AND i.indisvalid) AS valid_indexes, "
                        "(SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
                        " JOIN pg_namespace n ON n.oid=t.relnamespace "
                        " WHERE n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%') AS constraints, "
                        "(SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
                        " JOIN pg_namespace n ON n.oid=t.relnamespace "
                        " WHERE c.contype='f' AND n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%') AS foreign_keys, "
                        "(SELECT count(*) FROM information_schema.sequences "
                        " WHERE sequence_schema NOT IN ('information_schema') AND sequence_schema NOT LIKE 'pg_%') AS sequences, "
                        "(SELECT count(*) FROM information_schema.views "
                        " WHERE table_schema NOT IN ('information_schema') AND table_schema NOT LIKE 'pg_%') AS views, "
                        "(SELECT count(*) FROM information_schema.triggers "
                        " WHERE trigger_schema NOT IN ('information_schema') AND trigger_schema NOT LIKE 'pg_%') AS triggers, "
                        "(SELECT count(*) FROM information_schema.routines "
                        " WHERE routine_schema NOT IN ('information_schema') AND routine_schema NOT LIKE 'pg_%') AS routines"
                    )
                ).mappings().one()
                constraints_by_type = connection.execute(
                    text(
                        "SELECT c.contype, count(*) AS object_count "
                        "FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
                        "JOIN pg_namespace n ON n.oid=t.relnamespace "
                        "WHERE n.nspname NOT IN ('information_schema') AND n.nspname NOT LIKE 'pg_%' "
                        "GROUP BY c.contype ORDER BY c.contype"
                    )
                ).all()
                extensions = connection.execute(
                    text("SELECT extname, extversion FROM pg_extension ORDER BY extname")
                ).all()
                privileges = connection.execute(
                    text(
                        "SELECT current_user AS role, "
                        "has_database_privilege(current_user, current_database(), 'CONNECT') AS can_connect, "
                        "has_database_privilege(current_user, current_database(), 'CREATE') AS can_create_db_objects, "
                        "has_database_privilege(current_user, current_database(), 'TEMP') AS can_temp, "
                        "(SELECT bool_and(has_schema_privilege(current_user, s, 'USAGE')) "
                        " FROM unnest(current_schemas(false)) AS s) AS all_schema_usage"
                    )
                ).mappings().one()

                write_access = connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_type='BASE TABLE' "
                        "AND table_schema NOT IN ('information_schema') "
                        "AND table_schema NOT LIKE 'pg_%' "
                        "AND (has_table_privilege(current_user, quote_ident(table_schema)||'.'||quote_ident(table_name), 'INSERT') "
                        " OR has_table_privilege(current_user, quote_ident(table_schema)||'.'||quote_ident(table_name), 'UPDATE') "
                        " OR has_table_privilege(current_user, quote_ident(table_schema)||'.'||quote_ident(table_name), 'DELETE') "
                        " OR has_table_privilege(current_user, quote_ident(table_schema)||'.'||quote_ident(table_name), 'TRUNCATE'))"
                    )
                ).scalar_one()
                select_access = connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_type='BASE TABLE' "
                        "AND table_schema NOT IN ('information_schema') "
                        "AND table_schema NOT LIKE 'pg_%' "
                        "AND has_table_privilege(current_user, quote_ident(table_schema)||'.'||quote_ident(table_name), 'SELECT')"
                    )
                ).scalar_one()
                sequence_access = connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.sequences "
                        "WHERE sequence_schema NOT IN ('information_schema') "
                        "AND sequence_schema NOT LIKE 'pg_%' "
                        "AND (has_sequence_privilege(current_user, quote_ident(sequence_schema)||'.'||quote_ident(sequence_name), 'USAGE') "
                        " OR has_sequence_privilege(current_user, quote_ident(sequence_schema)||'.'||quote_ident(sequence_name), 'SELECT') "
                        " OR has_sequence_privilege(current_user, quote_ident(sequence_schema)||'.'||quote_ident(sequence_name), 'UPDATE'))"
                    )
                ).scalar_one()
                schema_privileges = connection.execute(
                    text(
                        "SELECT count(*) FILTER (WHERE has_schema_privilege(current_user, schema_name, 'USAGE')) AS schema_usage, "
                        "count(*) FILTER (WHERE has_schema_privilege(current_user, schema_name, 'CREATE')) AS schema_create "
                        "FROM information_schema.schemata "
                        "WHERE schema_name NOT IN ('information_schema') AND schema_name NOT LIKE 'pg_%'"
                    )
                ).mappings().one()
                current_role = connection.execute(
                    text(
                        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication "
                        "FROM pg_roles WHERE rolname=current_user"
                    )
                ).mappings().one()

                destination_snapshot = _catalog_snapshot(connection)
                source_comparison_lines = ["Source comparison: NOT VERIFIED"]
                source_engine = None
                try:
                    from app.config.settings import settings

                    source_url = make_url(settings.DATABASE_URL)
                    source_port = source_url.port or 5432
                    if (
                        source_url.host not in ("localhost", "127.0.0.1", "::1")
                        or source_port != 5432
                        or source_url.database != "ai_placement_platform"
                    ):
                        raise AuditBlocked(
                            "DATABASE_URL does not target the verified local source; comparison skipped"
                        )
                    source_engine = create_engine(
                        settings.DATABASE_URL,
                        connect_args={"connect_timeout": 8},
                        pool_pre_ping=True,
                    )
                    with source_engine.connect() as source_connection:
                        with source_connection.begin():
                            source_connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                            source_identity = source_connection.execute(
                                text("SELECT current_database(), inet_server_port(), inet_server_addr()::text")
                            ).one()
                            if (
                                source_identity[0] != "ai_placement_platform"
                                or source_identity[1] != 5432
                                or (source_identity[2] or "").split("/")[0] not in ("127.0.0.1", "::1")
                            ):
                                raise AuditBlocked(
                                    "Connected source identity does not match the verified local database"
                                )
                            source_snapshot = _catalog_snapshot(source_connection)
                    source_comparison_lines = _compare_snapshots(
                        source_snapshot, destination_snapshot
                    )
                except AuditBlocked as exc:
                    source_comparison_lines = [f"Source comparison: BLOCKED ({exc})"]
                except Exception as exc:
                    source_comparison_lines = [
                        "Source comparison: BLOCKED (read-only metadata comparison failed; "
                        f"error type={type(exc).__name__}; details redacted)"
                    ]
                finally:
                    if source_engine is not None:
                        source_engine.dispose()

                estimated_nonempty = [(s, t, n) for s, t, n in estimated_counts if n > 0]
                blockers = []
                if not privileges["can_connect"] or select_access < len(table_tuples):
                    blockers.append("Audit role lacks CONNECT or SELECT access to all inventoried tables")
                lines = [
                    "Identity: database and endpoint project-reference routing checks passed",
                    f"Project reference: {expected_ref}",
                    f"Database: {identity['db']}",
                    f"PostgreSQL version: {identity['version']}",
                    f"Connection mode: {mode}",
                    f"TLS: verified by libpq sslmode=verify-full; protocol={tls_protocol}; cipher={tls_cipher}",
                    f"Server address available: {bool(identity['server_addr'])}",
                    f"Database role: {privileges['role']}",
                    "Schemas: " + (", ".join(schemas) if schemas else "none"),
                    f"Base tables: {len(table_tuples)}",
                    f"Public base tables: {sum(1 for schema, _ in table_tuples if schema == 'public')}",
                    "Estimated rows (pg_class.reltuples; approximate): " + (", ".join(f"{s}.{t}~{n}" for s, t, n in estimated_counts) if estimated_counts else "no tables"),
                    "Public estimated rows (approximate): " + (", ".join(f"{s}.{t}~{n}" for s, t, n in estimated_counts if s == "public") or "no public tables"),
                    "Object inventory: " + ", ".join(f"{k}={v}" for k, v in object_inventory.items()),
                    "Constraint types: " + (", ".join(f"{row[0]}={row[1]}" for row in constraints_by_type) or "none"),
                    "Extensions: " + (", ".join(f"{name}@{version}" for name, version in extensions) or "none"),
                    "Effective privileges: " + ", ".join(f"{k}={v}" for k, v in privileges.items() if k != "role"),
                    f"Schema privileges: {dict(schema_privileges)}",
                    f"Role attributes: {dict(current_role)}",
                    f"Tables with INSERT/UPDATE/DELETE/TRUNCATE privilege: {write_access}",
                    f"Tables with SELECT privilege: {select_access}/{len(table_tuples)}",
                    f"Sequences with USAGE/SELECT/UPDATE privilege: {sequence_access}/{object_inventory['sequences']}",
                    "Detailed schema object counts: " + ", ".join(
                        f"{name}={len(destination_snapshot[name])}"
                        for name in (
                            "tables", "columns", "indexes", "constraints", "sequences",
                            "extensions", "views", "routines", "triggers", "alembic_version",
                        )
                    ),
                    "Index inventory includes full definitions and partial predicates; definitions are compared but not printed.",
                    "Constraint, sequence ownership/parameters, view, routine, trigger definitions are compared but not printed.",
                ]
                lines.extend(source_comparison_lines)
                lines.append(
                    "Existing data indicator: estimated rows present in "
                    + str(len(estimated_nonempty))
                    + " tables; estimates are not exact and cannot certify emptiness"
                )
                if estimated_nonempty:
                    blockers.append(
                        "Destination has estimated existing rows; do not overwrite or restore without an approved plan"
                    )
                return AuditResult(lines=lines, blockers=blockers)
    except AuditBlocked:
        raise
    except SQLAlchemyError as exc:
        # Do not include driver exception text; it can embed the connection URL.
        raise AuditBlocked(
            f"{stage} failed: {safe_database_error_category(exc)} (driver details redacted)"
        ) from None
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test-config",
        action="store_true",
        help="Exercise missing-URL handling without reading .env or connecting",
    )
    args = parser.parse_args(argv)
    if args.self_test_config:
        try:
            load_audit_config(environ={}, dotenv_path=ROOT / "missing-audit-test.env")
        except AuditBlocked as exc:
            if AUDIT_URL_KEY in str(exc) and "not configured" in str(exc):
                print("PASS: missing audit URL detected safely; no connection attempted")
                return 0
            print("FAIL: unexpected safe configuration-check outcome")
            return 1
        print("FAIL: missing audit URL was not detected")
        return 1

    try:
        url, expected_ref = load_audit_config()
        result = audit(url, expected_ref)
        for line in result.lines:
            print(line)
        if result.blockers:
            for blocker in result.blockers:
                print(f"BLOCKED: {blocker}")
            return 2
        print("PASS: read-only destination audit completed")
        return 0
    except AuditBlocked as exc:
        print(f"BLOCKED: {exc}")
        return 2
    except Exception:
        print("BLOCKED: audit failed unexpectedly; details redacted")
        return 2


if __name__ == "__main__":
    sys.exit(main())
