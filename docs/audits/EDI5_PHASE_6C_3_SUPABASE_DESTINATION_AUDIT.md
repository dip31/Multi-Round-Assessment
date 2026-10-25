# EDI5 Phase 6C.3 / 6C.4 — Supabase Destination Audit

- **Audit date:** 2026-10-25
- **Scope:** Prepare a safely isolated read-only Supabase destination audit and run it only when identity prerequisites are met.
- **Constraints:** No migrations, DDL/DML, grants, restore, or cutover. No destination connection was made.

## Results

| Check | Result | Finding |
|---|---|---|
| Initial worktree status | PASS | `git status --short` was clean. |
| Local application database | PASS | `.env` still configures `localhost` / `ai_placement_platform`; it was not modified. |
| Audit URL availability | PASS | `EDI5_SUPABASE_AUDIT_URL` is present in the project's `.env` configuration. |
| Safe application settings load | FAIL | The existing Pydantic settings model rejects `EDI5_SUPABASE_AUDIT_URL` as an extra setting. Its validation exception included the supplied value in command output. |
| Destination identity, server, TLS, inventory, counts, privileges | BLOCKED | No Supabase connection or destination query was attempted after the credential appeared in tool output. These properties remain unverified. |
| Database/repository changes | PASS | No database was changed. This report is the only repository file added by this audit. |

## Phase 6C.4 configuration resolution (2026-10-25)

The rejection occurs because `Settings` uses Pydantic Settings with `.env` loading and the default extra-field behavior rejects `.env` keys that are not declared model fields. The audit credential remains outside that general application model.

Added `scripts/audit_supabase_destination.py`, an audit-only entry point that reads the audit URL and expected project reference directly from the process environment or `.env` using `python-dotenv`. It requires a matching independent project reference, a recognized Supabase endpoint/database, TLS, and a PostgreSQL read-only transaction before inspection. It performs only `SELECT` metadata/count/privilege queries inside that transaction and sanitizes database exceptions. Added `python-dotenv` as an explicit dependency. `DATABASE_URL` and application settings were not modified.

### Verified in Phase 6C.4

| Check | Result | Finding |
|---|---|---|
| Initial worktree status | PASS | Existing untracked report was present and preserved. |
| Local application DB | PASS | `.env` remains pointed at `localhost` / `ai_placement_platform`. |
| Audit URL | PASS | Configured in `.env`; value was not printed by the audit script. |
| Missing URL handling | PASS | `--self-test-config` detects an absent URL safely without connecting or exposing a value. |
| Audit script tests | PASS | `4 passed` (`pytest -p no:cacheprovider`). |
| Syntax compilation | PASS | `py_compile` succeeded. |
| Expected project reference | BLOCKED | `EDI5_SUPABASE_EXPECTED_PROJECT_REF` is absent. The actual audit command stopped before opening a connection. |
| Destination identity, server/TLS, inventory, counts, privileges | BLOCKED | No connection was attempted; no destination properties are verified. |
| Database changes | PASS | No database was contacted or changed. |

### Next step

Configure `EDI5_SUPABASE_EXPECTED_PROJECT_REF` with the intended Supabase project's 20-character reference, and ensure the audit URL contains the rotated credential before rerunning `python scripts/audit_supabase_destination.py`. The prior credential must not be reused. The script will require endpoint/project identity agreement and will stop if it finds any nonempty tables. No restore or production cutover is authorized.

## Blocker and next step

Rotate the audit credential because the settings validation exception exposed its value in tool output. After rotation, load the value through a mechanism that does not pass it to the current `Settings` model (which forbids extra fields), then rerun the audit using the rotated credential. Do not use the prior credential. No restore or production cutover is authorized by this audit.

### Retry on 2026-10-25

The worktree contained this report as an existing untracked file and it was preserved. The audit URL remains present in `.env`, and the local database target remains `localhost` / `ai_placement_platform`. Importing the project's existing settings still fails because `EDI5_SUPABASE_AUDIT_URL` is rejected as an extra setting. The error was captured and inspected without printing its value. No destination connection was attempted; all destination checks remain blocked. No database changes were made.
