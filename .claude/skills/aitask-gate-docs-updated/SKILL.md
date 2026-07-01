---
name: aitask-gate-docs-updated
description: Procedure-backed verifier for the `docs_updated` gate — inspects a task's change, updates the project's documentation per the configured doc-update spec (confirming with the user), and records the gate result. Run by the attended agent (task-workflow / aitask-resume), not the headless engine.
---

## Purpose

This is the **verifier for the `docs_updated` gate** — a *procedure-backed*
(`kind: procedure`) gate. Unlike a command verifier (build/tests/lint), it is a
**skill run by the attended agent**: it inspects the task's change, updates the
project's user-facing / design documentation per the project's doc-update spec
(**confirming with the user**), and records the gate result in the ledger. The
headless engine (`ait gates run`) never executes this — it reports the gate as
`needs agent` and defers to the attended task-workflow / aitask-resume path, which
starts the run and Read-and-follows this skill.

This skill is **project-agnostic**: it reads *how* to update docs from the
project's configured guide (never from any framework-internal convention doc).

## Contract

**Invocation** (positional args, from the dispatch seam):

```
<task-id> <attempt> <run-id>
```

`<attempt>` and `<run-id>` are allocated by the dispatch seam via
`aitask_gate.sh begin-procedure <task-id> docs_updated` (which already opened the
`running` block). **Reuse `<run-id>` verbatim** when appending the terminal block.
Do **not** invent these values.

**Terminal status semantics (record exactly one):**

| Status | When |
|--------|------|
| `pass` | The procedure **performed the required doc work**, OR inspected the doc-relevant surfaces and **confirmed the existing docs are already correct**. |
| `skip` | The procedure **evaluated the task and concluded `docs_updated` is not applicable** to this change (no doc-relevant surface needed review/update). Terminal-satisfied, distinct from `pass`. |
| `fail` | Docs **are** needed but the user **blocks/rejects** the update. |

The dividing line between `pass` and `skip`: if doc-relevant surfaces existed and
were checked (whether edited or already-correct) → `pass`; if the change had **no**
doc-relevant surface at all → `skip`.

## Workflow

### 1. Load the doc-update spec

Read `aitasks/metadata/project_config.yaml` `doc_update.guide` and read the guide
it names — the project's **configured** doc-update spec (default
`aitasks/metadata/doc_update_guide.md`; on a fresh install this is the generic
guide the setup flow installed there, which the project then customizes). It is the
source of truth for doc roots, the change-kind→doc-area map, and writing
conventions. Also read any `doc_update.extra_guides`.

```bash
# read the pointer, e.g.:
grep -A3 '^doc_update:' aitasks/metadata/project_config.yaml
```

**Do NOT read `seed/doc_update_guide.md` at runtime** — `seed/` is removed after
install; it is only the install-time source of the default guide. If no guide is
configured or present, proceed with a best-effort generic method and confirm every
proposed doc change with the user.

### 2. Gather the change surface (to inform, not to gate)

Identify what this task changed, so you know which docs may be affected:

```bash
# committed under this task's tag
git log -F --grep="(t<task-id>)" --format=%H | while read -r sha; do git show --name-only --format= "$sha"; done
# plus still-uncommitted work during implementation
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

This is **only to inform** which areas changed — it is **not** a pass/fail
heuristic. Ignore task/plan data paths (`aitasks/`, `aiplans/`, `.aitask-data/`).

### 3. Infer + propose the doc updates

Using the configured guide's change-kind→doc-area map **and the shape of the
existing docs**, determine which doc pages/sections to create or update. Follow the
guide's writing conventions. If the change touches no doc-relevant surface at all,
plan to record `skip` (step 6).

### 4. Confirm with the user

Present the proposed doc changes and use `AskUserQuestion`:
- **Apply** — make the proposed doc edits.
- **Adjust** — revise per the user's guidance, then re-present.
- **Not needed / skip** — the user judges no doc update is warranted.
- **Reject** — the user blocks doc work that is needed.

In autonomous / remote profiles (non-interactive), follow the active profile's
policy (apply per the spec, or record a deferral) instead of blocking.

### 5. Apply

Make the confirmed documentation edits. These are code-tree files (e.g. the docs
site / design docs) → they are committed with the task in the normal review/commit
step, so they land in the task's `(t<task-id>)` commit.

### 6. Record the terminal block

Write a sidecar log and append the terminal block, **reconciling** the `running`
block the dispatch seam opened (reuse `<run-id>`):

```bash
logdir=".aitask-gates/<task-id>"; mkdir -p "$logdir"
log="${logdir}/docs_updated_<run-id>.log"
# ... write a short summary of what was updated / why skipped / why failed to "$log" ...

./.aitask-scripts/aitask_gate.sh append --only-if-running <run-id> \
    <task-id> docs_updated <pass|skip|fail> \
    run=<run-id> attempt=<attempt> type=machine \
    verifier=aitask-gate-docs-updated result="<short summary>" log="$log"
```

- Use the status from the table above.
- Do **not** pass a `kind=` field to `append` (the marker carries `type=machine`;
  `kind` lives in the registry only).
- `--only-if-running <run-id>` makes the terminal append atomic against the
  `running` block, exactly like a command verifier's reconcile.

## MUST NOT
- Invent the `attempt` / `run-id` (they come from `begin-procedure`).
- Record `pass` when no doc-relevant surface was touched — that is `skip`.
- Modify the task frontmatter or any other gate's `## Gate Runs` entries.
- Reference framework-internal convention docs — read the project's configured
  guide instead.

## Notes
- Procedure-backed gates and the command-vs-procedure distinction are documented in
  `aitask-gate-template` and the `aitasks/metadata/gates.yaml` header.
- The attended dispatch (allocate run → run this skill → it records) lives in the
  shared `task-workflow` (Step 8) and is reused by `aitask-resume`.
- Codex / OpenCode ports of the gate skills are tracked under **t635_23**.
