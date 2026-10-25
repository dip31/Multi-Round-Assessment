# EDI5 Phase 7N - Isolated Supabase Staging Approval and Plan

- Date: 2026-10-25
- Scope: staging architecture, role requirements, compatibility checklist, acceptance criteria, rollback outline, and owner approval checklist.
- Status: **PLAN ONLY. No project was provisioned and no database or application configuration was changed.**

## Evidence carried forward

Phase 7M fresh read-only findings:

- Local source: `ai_placement_platform`, PostgreSQL 16.13, 39 public tables and 6,641 bounded-exact rows.
- Existing Supabase project: project route and expected identity matched; database `postgres`, PostgreSQL 17.11, session pooler, client TLS verified with `sslmode=verify-full` and the pinned CA. This is historical destination evidence for the existing project, not the proposed staging target.
- Existing destination: 34 public tables and 7,599 bounded-exact rows; ownership is **UNKNOWN - PRESERVE**. Its audit identity is write-capable on 69 tables and has CREATEDB, CREATEROLE, and REPLICATION. Do not reuse it as a staging runtime or migration identity.
- Current PK overlap comparison remains unverified. The earlier Phase 7G overlap count is historical and is not used as a current staging assumption.
- Source backup: Phase 7K validated the October 25 530,714-byte dump (SHA-256 `466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B`) in the isolated local scratch DB; 39 table counts and full-row fingerprints matched. That validates the local restore only, not Supabase compatibility.

The prior destination must remain untouched. No new destination identity, region, project reference, owner, cost estimate, or credential has been selected or approved for staging.

## Proposed staging boundary

Use one newly provisioned Supabase project dedicated to staging, under an explicitly named owner. Select a project reference and region that are distinct from the existing destination and verify both before adding any credentials. Use a separate project/database boundary, project-specific credentials and trusted CA, and staging-only application configuration. Do not share mutable schemas, database roles, secrets, storage buckets, or application traffic with the existing destination or production.

Keep the repository's development `DATABASE_URL` local. Put any future staging URL in a separate deployment secret store/environment. Do not point a developer machine, production deployment, scheduled worker, or background process at staging implicitly. Disable production callbacks/webhooks and outbound actions in staging unless individually reviewed and safely stubbed.

Network access, dashboard membership, logs, backups, and asset storage should be restricted to approved staging operators. Keep production credentials out of staging. Verify staging TLS with the CA associated with that new project and `sslmode=verify-full`; do not reuse the existing project's CA or project reference by assumption.

## Roles and permissions proposal

This is a permission objective matrix, not SQL or a grant instruction. Confirm current Supabase-managed role behavior and restrictions for the selected project before writing an exact role/privilege design. Do not elevate the existing destination role or reuse it.

| Identity | Intended boundary | Exclusions / review |
|---|---|---|
| Project administrator | Owner-managed dashboard and break-glass administration; named human accounts with MFA and audit trail. | Not used by application code, jobs, or routine migration scripts. Owner controls membership and recovery. |
| Migration operator | Temporary, explicitly approved ability to create/import only the application objects required for the approved staging run. Remove/disable after acceptance if platform-supported. | No production access; no provider-managed schema changes; no role/database/replication administration unless provider requirements make a capability unavoidable and the owner approves it explicitly. Never grant before a reviewed operation plan. |
| Runtime application | Only required schema usage, table operations, sequence operations, and function execution for the tested application workflows. | No schema/object ownership, DDL, role creation, database creation, replication, or access to provider-managed schemas unless separately justified. Separate staging secret from production. |
| Read-only auditor | SELECT on approved application tables plus metadata needed to inspect schema and permissions. | No INSERT/UPDATE/DELETE/TRUNCATE, sequence UPDATE, CREATE, role, database, or replication privileges. Confirm Supabase catalog visibility limitations before the audit. |

Exact SQL, role names, grants, default privileges, RLS policies, and Supabase API/service keys are intentionally unspecified until the selected project and supported role model are reviewed and approved.

## Compatibility checklist before any staging import

| Area | Current evidence / risk | Required planning or validation |
|---|---|---|
| PostgreSQL version | Source 16.13. Existing destination was 17.11; the future staging version is unknown. | Verify the provisioned staging version and extension availability. Use compatible current dump/restore tools and validate the 16-to-target restore in staging. |
| Alembic baseline | Source revision is `add_faculty_practice_assignments`; repository head is `use_unspecified_student_department_default`. Existing destination has unrelated history. | Decide whether the verified backup is the baseline, then review every migration from that revision to head. Do not run migrations in this phase or apply autogeneration blindly. |
| Department default | Prior reconciliation found the migration assumes an existing `Computer Science` default while the live source column has no server default; ORM Python default differs. | Review/correct migration assumptions against the source and restored schema. Test insert behavior in staging after separate write authorization. |
| `refresh_tokens` | Table exists in the database but is absent from ORM metadata. | Preserve it in the source backup; reconcile model, retention, and session/auth behavior before deciding whether it is managed by EDI5. |
| `coding_problems.blueprint_id` | Model/source/destination foreign-key and column state have differed; current destination lacks source schema elements. | Use verified source/backup catalog as the import baseline. Decide the intended FK only after reviewing source data and application semantics. |
| `rl_attempt_log` foreign keys | Live source has validated FK constraints not fully represented in ORM metadata. | Preserve actual source constraints, reconcile ORM metadata, and validate orphans after authorized staging restore. |
| Partial unique indexes | Source has important active-session and active-round uniqueness rules; historical destination was missing one. | Verify names, predicates, validity and behavior on the staged restore; add nothing until migration SQL is reviewed and approved. |
| Constraints, sequences, ownership, ACLs | Phase 7K validated source schema/data restore but intentionally omitted owner/privilege restoration. | Define sequence state strategy, application ownership, least-privilege roles, grants, and default privileges separately. Verify before application tests. |
| Extensions and provider objects | Existing destination has additional extensions and provider-managed schemas; they are not automatically part of source scope. | Inventory staging's supported extension versions. Exclude provider schemas (`auth`, `storage`, `realtime`, `vault`, GraphQL/platform schemas) from generic restore; use documented provider mechanisms for any integration. |
| Authentication and sessions | Runtime uses application auth/JWT settings; database contains session-related data and `refresh_tokens`. | Use staging-only keys and test login/session/token flows with staging accounts. Never reuse production signing secrets or user sessions. |
| External uploads | Source stores local file paths for resumes and company historical uploads. Existing inventory has 87 resume files and 487 company upload files; content digests and row-to-file mapping remain unverified. | Define a separate access-controlled copy and manifest. Preserve originals. Rewrite or map paths only in an authorized staging copy; test authorization and retrieval. |
| Knowledge-base index | `app/data/kb.index` is a separate application asset; Phase 7I matched it to tracked content and the October 24 manifest. | Deploy a verified staging copy or rebuild only from approved input data in an isolated build step; do not modify the source asset during provisioning. |
| Absolute paths / environment | Database records can contain filesystem paths; `DATABASE_URL` remains local in this repository. | Inventory path-valued fields using aggregate/metadata-only methods, design staging storage mapping, and configure secrets only in a separate staging environment. |

## Staging acceptance criteria

Before import begins, all must pass:

1. Owner-approved project reference and region are recorded and distinct from the existing destination; project/database identity is verified over TLS.
2. Owner and administrative contacts, authorized users, permitted role model, and monthly maximum cost/resource boundary are documented.
3. Staging credentials are separately provisioned and stored in the approved secret manager; no production credentials are reused.
4. The approved source artifact hash matches the restore-validated Phase 7K artifact, or a newly authorized and verified backup replaces it. The exact archive sections/objects to import are listed.
5. The migration operator's approved operations are enumerated, with provider-managed objects excluded. Restore and any later Alembic upgrades are separate reviewed steps.
6. Post-import schema, row counts, deterministic fingerprints, constraints, foreign keys/orphans, indexes/predicates, sequences, extensions, and least-privilege access meet written thresholds.
7. Data/key collision and ownership questions are resolved for the staging copy. No IDs are assumed to identify the same entity across databases.
8. Staging application smoke, authentication/session, upload retrieval, and relevant external-service tests pass using staging-only config and non-production accounts.
9. External asset manifest/checksums and database-to-file mapping pass without deleting, moving, or overwriting original assets.
10. Rollback owner, trigger, source/backup retention, observability, and cleanup approval are documented. A staging failure must not require altering or deleting the existing destination or local source.

## Cost, ownership, and resource boundary

The owner must set a maximum monthly spend in an identified currency before provisioning; no price or tier is inferred in this plan. Also approve compute sizing, disk/storage allowance, expected backup/PITR retention, egress/network use, alert threshold/recipient, project pause/retention behavior, and the person authorized to approve increases. Verify the selected plan's current price and usage limits in the dashboard at approval time.

The staging project owner must be named and accountable for billing, membership, credential recovery, data retention, and eventual project disposition. Identify whether the staging data is synthetic, minimized, or copied from the verified source; approve who may access it and how long it may remain. If real candidate or company data is included, approve the privacy/access controls and separate asset scope before import.

## Rollback and cleanup strategy

- Keep the local source, validated Phase 7K scratch database, backup, manifests, and original assets unchanged.
- Isolate staging from all production traffic. A failed import or test is contained to the staging project; restore/recreate actions are allowed only under a later, explicit phase authorization naming exact resources and commands.
- Do not roll back by modifying the existing Supabase destination or overwriting a backup. Preserve failed staging evidence until the owner decides retention.
- If staging must be abandoned, disable staging application access and revoke only staging credentials using an approved owner action. Project deletion or resource cleanup requires separate explicit approval and identity verification.
- Production cutover is out of scope. A future cutover requires a separate go/no-go, freeze window, fresh source snapshot, rehearsed rollback, and named incident owner.

## Owner approval checklist - required before provisioning

No items are approved by this Phase 7N plan. The project owner must complete and explicitly approve each item:

- [ ] **Project identity:** intended new project name/reference (assigned at creation), organization, region, and confirmation it is distinct from the existing destination.
- [ ] **Ownership:** accountable project/data owner and administrative contacts.
- [ ] **Scope:** database schema/data scope, environment users, integrations, external asset plan, and explicit exclusions for provider-managed schemas and production traffic.
- [ ] **Cost boundary:** monthly maximum and currency, compute/storage/backup/egress limits, alerts and recipients, and authorization for any overage.
- [ ] **Roles:** approved auditor, migration operator, runtime permissions, human administrators, and secure secret-management route.
- [ ] **Data handling:** approve data minimization/synthetic data choice, access list, retention period, and asset copy scope.
- [ ] **Rollback:** named rollback/change owner, failure trigger, recovery artifacts, and staging retention/deletion approval process.
- [ ] **Provision now:** explicit statement that the named owner authorizes creation of the new isolated staging project under the listed scope and cost boundary.

Until all required approvals are explicit and the project is uniquely identified, provisioning is **NOT AUTHORIZED**. Phase 7N itself does not authorize backup restore, schema/data import, migrations, role/grant changes, asset copies, application configuration changes, or cutover.

## Checks, files, and decision

- Phase 7M, 7K and 7L evidence was reviewed. Current Phase 7M observations are distinguished from older Phase 7G destination results.
- This phase makes no database connection and creates no cloud resources.
- `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**.
- `git diff --check`: **passed**; Git emitted its existing line-ending warning for the pre-existing `requirements.txt` modification. Both report files also passed a direct trailing-whitespace scan.
- Intended Phase 7N file changes: this plan and the appended Phase 7N section in `EDI5_PHASE_7_LOCAL_TO_SUPABASE_MIGRATION_STATUS.md`. Earlier modified and untracked files remain preserved.

**Phase 7N decision: approval package prepared; provisioning BLOCKED pending explicit owner selections and authorization.** Stop here and wait for approval before Phase 7O.
