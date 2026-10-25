# EDI5 Phase 7S - Final Staging Preflight

- Decision date: 2026-10-25
- Scope: consolidate Phase 7N/7R staging gates using the existing Phase 7N, 7O, 7P, 7R and overall status evidence. No new database audit was performed.
- Safety: no Supabase connection, provisioning, credential/role/schema/data change, migration, restore, asset operation, or cutover.

## Evidence matrix

| Area | Status | Evidence and boundary |
|---|---|---|
| Local source and backup | **READY WITH SCOPE** | Phase 7O/7K identify local `ai_placement_platform`, PostgreSQL 16.13, revision `add_faculty_practice_assignments`, 39 public tables / 6,641 rows. Verified October 25 archive: 530,714 bytes, SHA-256 `466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B`. These are report findings; no new source/backup audit in 7S. |
| Restore validation | **PASS - LOCAL SCRATCH ONLY** | Phase 7K reports restore into a newly identified local scratch DB with matching 39 table counts and full-row fingerprints. It did not establish Supabase compatibility, ACL/runtime-role behavior, application behavior, or asset portability. Source, backup and scratch DB remain preservation-only. |
| ORM/schema issues | **PARTIAL** | Phase 7Q prepared ORM parity for `rl_attempt_log` FKs and the two active-session/round partial unique indexes; focused metadata tests passed. No migration was applied. Department default remains a migration decision; `coding_problems.blueprint_id` FK is absent on source despite nullable ORM intent and zero reported orphans; `refresh_tokens` remains unmapped and must be preserved. |
| Department migration deployment status | **NOT VERIFIED** | Local source and Phase 7K scratch show the parent revision. Repository docs/history do not prove status in shared environments. Phase 7R requires an identity-verified, read-only revision/default check in each supported environment. |
| `refresh_tokens` ownership | **OWNER DECISION REQUIRED** | Baseline/schema files create it; auth code describes opaque refresh tokens as a future option, with no runtime persistence found. Treat as EDI5-managed and preserve until authentication/security and schema owners decide its management policy. |
| Existing Supabase destination | **UNKNOWN - PRESERVE** | Phase 7M historically reported populated data (34 public tables / 7,599 rows), identity/TLS then verified, and an audit role with broad write/elevated privileges. This is historical evidence, not a fresh current-state verification. Ownership remains uncertain; do not reuse, query, or modify it in this phase. |
| Owner approval | **BLOCKED** | Phase 7N checklist remains unapproved. No new staging project identity, region, owner, budget, data scope, role approval, asset plan, rollback owner, or provision-now authorization is recorded. |
| Checks requiring a provisioned stage | **NOT YET PERFORMABLE** | New project identity and distinctness; staging database/version and CA/TLS `verify-full`; connection mode; exact roles/grants/RLS; empty-target inventory; current source/stage schema and key comparison; restore/acceptance rehearsal; asset-to-record validation; staging-only application/auth smoke tests; rollback rehearsal. |

## Owner decisions required before provisioning

The accountable owner must provide and approve all of the following in one recorded authorization:

1. **Project owner** and accountable administrative contacts; the **organization** that will own the project.
2. **Region** and intended isolated staging project name/purpose; after creation, confirm the assigned project reference is distinct from the protected existing destination.
3. **Maximum budget and currency**, including accepted compute, storage, backup/PITR, and egress limits, alert threshold/recipient, and whether any overage is prohibited. Confirm the current plan price and usage limits at approval time. No figure is assumed; a free tier does not establish zero total cost.
4. **Intended scope:** which schemas/data, integrations, and users are in scope; synthetic/minimized/copied data choice; access list and retention; explicit exclusion of production traffic and provider-managed schemas from generic restore.
5. **Role model:** approval for separate human administrator, temporary migration operator, runtime application identity, and read-only auditor, with least-privilege boundaries. Exact platform grants remain a technical verification after project creation.
6. **Asset/data handling:** approve whether resumes, historical company uploads, and the KB index/metadata pair are included; access/retention rules and isolated copy/path-mapping approach. Preserve all originals.
7. **Rollback owner:** named person authorized to stop the exercise and own recovery/retention decisions; approval of stop triggers and staging cleanup boundary.
8. **Explicit provisioning approval:** a clear statement authorizing creation of the named isolated project under the confirmed scope and cost ceiling. This does not authorize restore, migration, role/grant changes, asset transfer, or cutover; those require later phase-specific authorization.

These are owner/business decisions, not coding tasks. Until recorded, provisioning is **NOT AUTHORIZED**.

## Technical checks after staging exists

After approval and provision, but before any data load, verify and record (redacted):

- New project reference, owner/organization, region and database identity; prove it is distinct from the existing destination.
- TLS positively through client-side certificate/hostname verification (`verify-full`) with the CA for that project; record connection mode, PostgreSQL version and effective identity.
- Read-only inventory of empty staging schemas/tables, extensions, constraints, indexes, sequences and effective role privileges; compare current source and destination inventories from fresh, identity-gated evidence.
- Compatible primary-key definitions and privacy-preserving overlap counts, then resolve any entity/natural-key conflicts before import or merge.
- Exact least-privilege role behavior, including denied elevated powers, before assigning runtime or migration credentials.
- Approved backup identity/hash and isolated restore rehearsal; compare schema, aggregate counts/fingerprints, constraints/FKs/orphans, index predicates, sequences and acceptance thresholds. Keep source/verified backup/scratch intact.
- Approved asset manifest and database-reference-to-file mapping, copy checksums, path mapping, and access tests without moving/deleting originals.
- Staging-only application configuration, authentication/session smoke tests using non-production accounts, external-service isolation, rollback owner and stop/retention behavior.

No post-provision check is claimed complete because no staging project exists.

## Decision and next action

**Decision: STOP - OWNER INPUT REQUIRED.** Local backup/restore evidence is adequate for the stated local scope, but staging authorization is incomplete and several technical checks depend on a not-yet-approved project. The next action is for the owner to provide the eight approval items above. Do not start another audit phase or provision until the approval is explicit. After approval, the next technical phase should verify the new project's identity/TLS and empty-state read-only before considering a separately authorized restore rehearsal.

## Checks and files

- Read Phase 7N, 7O, 7P, 7R and the overall migration status; no destination or source database connection was made in Phase 7S.
- Initial and final `git status --short` captured; final diff and documentation whitespace checks reviewed.
- No tests were run: this phase changed documentation only. No database, migration, restore, cloud, credential, role, backup, scratch DB, or asset operation occurred.
- Phase 7S files: created this preflight report and appended its dated summary/link to the overall migration status report. All pre-existing changes and untracked files were preserved.
