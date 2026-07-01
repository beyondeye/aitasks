---
priority: medium
effort: low
depends: [1071_6]
issue_type: refactor
status: Ready
labels: [claudeskills]
anchor: 1071
created_at: 2026-07-01 15:10
updated_at: 2026-07-01 15:10
---

Migrate the `docs_updated` gate skill to read its guide path via the shared
`resolve_config_path` seam introduced in t1071_6, replacing its fragile inline
`grep -A3 '^doc_update:'`.

## Context
t1071_6 added a general resolver for "a project_config.yaml value that names a
file on disk, with a seeded-default fallback":
- `config_utils.resolve_config_path(config_key, default_rel=None, root=None, check_readable=True)`
- CLI: `./.aitask-scripts/aitask_resolve_config_path.sh <dotted.key> [default_rel]`
  (always exits 0; prints the resolved path or an empty line). Supports dotted
  keys, so `doc_update.guide` is covered.

The `docs_updated` gate skill (`.claude/skills/aitask-gate-docs-updated/SKILL.md`,
owned by t635_19) currently reads `doc_update.guide` with an inline
`grep -A3 '^doc_update:' aitasks/metadata/project_config.yaml` — which mishandles
quoted values, inline comments, and is cwd-dependent.

## Coordination
- **Depends on t1071_6** (the resolver must exist).
- **Coordinates with t635_19** (owns the docs_updated gate skill). t635_19 carries
  a reverse pointer to this task. Re-verify the gate after the migration.

## Scope
- Rewrite the `doc_update.guide` read in `aitask-gate-docs-updated/SKILL.md` to call
  `aitask_resolve_config_path.sh doc_update.guide aitasks/metadata/doc_update_guide.md`
  (or import `resolve_config_path` if a Python step is more natural), preserving the
  existing fallback semantics (configured guide -> seeded default -> best-effort
  generic + user confirmation).
- Re-verify the docs_updated gate end-to-end (`aitask-gate-docs-updated`), including
  the "no guide configured" fallback path.

## Scope-honest limit
`resolve_config_path` resolves a **single scalar** path — it covers `doc_update.guide`
but NOT the list-valued `doc_update.extra_guides` (currently documented but unconsumed).
Migrating `extra_guides` is OUT OF SCOPE here; it would need a separate list-capable
companion resolver. Do not advertise the scalar helper as covering the list field.

## Verification
- The gate skill no longer contains the inline `grep -A3 '^doc_update:'` read.
- Quoted / commented `doc_update.guide` values resolve correctly (the cases the old
  grep failed).
- The docs_updated gate still passes/skips/falls-back as before.
