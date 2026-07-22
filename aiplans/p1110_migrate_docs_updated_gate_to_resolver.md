---
Task: t1110_migrate_docs_updated_gate_to_resolver.md
Base branch: main
plan_verified: []
---

# Plan: Migrate `docs_updated` gate to `resolve_config_path` seam (t1110)

## Context

The `docs_updated` gate skill (`.claude/skills/aitask-gate-docs-updated/SKILL.md`)
reads the project's doc-update guide pointer with an inline
`grep -A3 '^doc_update:' aitasks/metadata/project_config.yaml` — which mishandles
quoted values and inline `#` comments, and is cwd-dependent. t1071_6 (Done/archived)
delivered the canonical seam for exactly this shape:
`./.aitask-scripts/aitask_resolve_config_path.sh <dotted.key> [default_rel]`
(PyYAML-backed, always exits 0, prints the resolved repo-root-relative path or an
empty line on any failure). It supports dotted keys, so `doc_update.guide` is covered.

The reference consumer pattern already exists in
`.claude/skills/aitask-learn-skill/generate.md:26` (resolver call + "read that file;
empty output/failure → fall back" prose), with a drift-guard assertion in
`tests/test_resolve_config_path_cli.sh` (Case 4).

Surface audit: the inline grep exists **only** in
`.claude/skills/aitask-gate-docs-updated/SKILL.md:58`. No Codex/OpenCode ports exist
yet (tracked in t635_23), the skill is static (no `.j2`, no goldens, no rendered
variants), so this is a single-file skill edit plus a test guard.

## Changes

### 1. `.claude/skills/aitask-gate-docs-updated/SKILL.md` — rewrite Step 1's guide read

Replace the code block at lines 56–59:

```bash
# read the pointer, e.g.:
grep -A3 '^doc_update:' aitasks/metadata/project_config.yaml
```

with the resolver call (run from the repository root), mirroring the
`generate.md` pattern:

```bash
./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide \
  aitasks/metadata/doc_update_guide.md
```

Adjust the surrounding prose of Step 1 to:
- State that the command prints the effective guide path — the configured
  `doc_update.guide` if it names a readable file, otherwise the seeded default
  `aitasks/metadata/doc_update_guide.md` — and to **read and apply that file**.
- Map the fallback chain onto the resolver contract, preserving existing
  semantics exactly: configured guide → seeded default → (empty output or any
  failure) best-effort generic method with every proposed doc change confirmed
  with the user. The existing "Do NOT read `seed/doc_update_guide.md` at
  runtime" warning stays.
- Keep the `doc_update.extra_guides` sentence, clarified to be scope-honest:
  `extra_guides` is a **list** value read directly from
  `aitasks/metadata/project_config.yaml` — the scalar resolver does **not**
  cover it (per the task's scope-honest limit; a list-capable companion is out
  of scope here).

### 2. `tests/test_resolve_config_path_cli.sh` — add CLI acceptance case + drift guard

Coverage gap (verified): the Python tests (`tests/test_resolve_config_path.py`)
pin quoted values, trailing comments, and the nested `doc_update.guide` key —
but each **separately** and only through the Python function. The CLI test
exercises only the flat `learn_skill_authoring_guide` key with a plain
unquoted value. Nothing proves this migration's acceptance case through the
CLI seam the skill actually calls.

**Case 5 — nested `doc_update.guide`, quoted + inline comment (CLI level).**
New temp-repo fixture (reusing the `mkrepo` helper pattern of Cases 1–3):

```bash
mkdir -p "$repo/custom"; echo guide > "$repo/custom/guide.md"
printf 'doc_update:\n  guide: "custom/guide.md"  # note\n' \
    > "$repo/aitasks/metadata/project_config.yaml"
out="$(cd "$repo" && ./.aitask-scripts/aitask_resolve_config_path.sh \
    doc_update.guide aitasks/metadata/doc_update_guide.md)"
# assert_eq: resolves to custom/guide.md (quotes stripped, comment ignored,
# dotted key walked) — the exact case the old grep failed
```

**Case 6 — docs-updated gate skill consumes the resolver (real file),**
modeled on Case 4:
- `assert_contains` — SKILL.md invokes `aitask_resolve_config_path.sh`
- `assert_contains` — SKILL.md names the `doc_update.guide` key
- `assert_not_contains` — the old inline read `grep -A3 '^doc_update:'` is gone

Together these pin both acceptance criteria: Case 5 proves the CLI resolves
the nested/quoted/commented value the old grep mishandled; Case 6 pins "the
gate skill no longer contains the inline grep" as a regression guard.

## Verification

- `bash tests/test_resolve_config_path_cli.sh` — existing cases still pass +
  new Cases 5 and 6 pass. Negative control: temporarily reintroduce the grep
  line (or drop the resolver line) and confirm Case 6 fails; break the fixture
  (unresolvable guide) and confirm Case 5 fails; then restore.
- `bash tests/test_gate_procedure_docs.sh` — gate ledger flow unaffected.
- End-to-end re-verify of the gate's Step 1 fallback chain (manual, scratchpad
  fixture — complements Case 5 which now covers the quoted/commented case):
  - Real repo: resolver prints `aitasks/metadata/doc_update_guide.md`.
  - No `doc_update:` key / unreadable guide, no seeded default present →
    prints an empty line → skill falls back to the best-effort generic path.
- No rerender/goldens needed: the skill is static, Claude-tree only (ports are
  t635_23's scope); `aitask_skill_verify.sh` not required (no `.j2`/stub change).

## Post-implementation

Step 9 (task-workflow): merge N/A (current branch), gates run
(`risk_evaluated` is orchestrator-recorded), archive via
`./.aitask-scripts/aitask_archive.sh 1110`.

## Final Implementation Notes
- **Actual work done:** Exactly as planned. Rewrote Step 1 of
  `.claude/skills/aitask-gate-docs-updated/SKILL.md` to resolve the guide via
  `./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide
  aitasks/metadata/doc_update_guide.md` (run from the repo root), preserving the
  fallback chain (configured → seeded default → empty/failure = best-effort
  generic + per-change user confirmation) and keeping the "Do NOT read seed/"
  warning. Added Cases 5 and 6 to `tests/test_resolve_config_path_cli.sh`:
  Case 5 proves CLI-level resolution of nested `doc_update.guide` with a quoted
  value + inline comment (the case the old grep failed); Case 6 pins that the
  skill consumes the resolver and no longer contains `grep -A3 '^doc_update:'`.
- **Deviations from plan:** One post-review wording change (Change Request 1):
  the `extra_guides` sentence now frames the field as unchanged/out-of-scope
  instead of instructing a direct YAML read.
- **Issues encountered:** During negative-control verification, a
  `git checkout --` cleanup reverted the skill file to HEAD, wiping the
  in-progress edit along with the temporarily reintroduced grep line; the edit
  was re-applied and all tests re-run green (15/15). Both negative controls
  confirmed the suite exits 1 when the guards are violated.
- **Key decisions:** Placed the drift guard in
  `tests/test_resolve_config_path_cli.sh` (alongside the existing Case 4 guard
  for `generate.md`) rather than a new test file, so all resolver-consumer
  guards live in one suite. The migration is Claude-tree only — no Codex/
  OpenCode ports exist yet (tracked in t635_23), and the skill is static (no
  `.j2`/goldens), so no rerender was needed.
- **Upstream defects identified:** None

## Post-Review Changes

### Change Request 1 (2026-07-22 09:05)
- **Requested by user:** The revised Step 1 still told agents to read
  `doc_update.extra_guides` directly from `project_config.yaml` — pointing
  future agents at another ad-hoc YAML parse of the same config block the task
  is migrating away from. Reword as unchanged/out-of-scope until a list-capable
  resolver exists (disposition: follow-up).
- **Changes made:** Reworded the `extra_guides` sentence in the skill's Step 1
  to state the field is unchanged by this migration, is a list value out of
  scope for the scalar resolver, and is read as before until a list-capable
  companion resolver exists. Tests re-run: 15/15 pass.
- **Files affected:** `.claude/skills/aitask-gate-docs-updated/SKILL.md`

## Risk

### Code-health risk: low
- None identified. Single markdown skill edit that swaps a fragile inline read
  for the canonical, already-tested seam, plus an additive test assertion.

### Goal-achievement risk: low
- None identified. The resolver's contract (dotted keys, quoted/commented
  values, empty-on-failure) covers every acceptance case named in the task,
  and the scope-honest `extra_guides` limit is explicitly preserved.
