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

Resolve the project's **configured** doc-update spec by running, **from the
repository root**:

```bash
./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide \
  aitasks/metadata/doc_update_guide.md
```

It prints the effective guide path — the `doc_update.guide` value from
`aitasks/metadata/project_config.yaml` if it names a readable file, otherwise
the seeded default `aitasks/metadata/doc_update_guide.md` (on a fresh install
this is the generic guide the setup flow installed there, which the project
then customizes). **Read and apply that file** — it is the source of truth for
doc roots, the change-kind→doc-area map, and writing conventions. The
`doc_update.extra_guides` field is **unchanged by this migration**: it is a
**list** value, out of scope for the scalar resolver above — if the project has
it set, read the guides it lists as before, until a list-capable companion
resolver exists.

**Do NOT read `seed/doc_update_guide.md` at runtime** — `seed/` is removed after
install; it is only the install-time source of the default guide. **If the
command prints an empty line OR fails for any reason** (no guide configured or
present on disk, or the helper cannot run), proceed with a best-effort generic
method and confirm every proposed doc change with the user.

### 2. Gather the change surface — **attributed to this task**

Identify what **this task** changed, so you know which docs may be affected:

```bash
./.aitask-scripts/aitask_change_surface.sh list <task-id>
```

Do **not** hand-roll this with `git diff` / `git ls-files`. Those return the
**entire dirty tree**: procedure gates run before the review/commit, so the
uncommitted half is the primary signal, and on a shared or busy checkout it
contains other tasks' in-progress work and other sessions' edits. The helper
attributes it; a raw diff cannot.

The output is two header lines followed by one classified line per path:

| Line | Meaning | Use it? |
|------|---------|---------|
| `BASELINE:ok\|missing\|foreign` | was the claim-time baseline available? | header |
| `PLANSCOPE:ok\|missing` | was the task's plan available? | header |
| `COMMITTED:<path>` | proven this task's — in a commit tagged `(t<id>)` | **in scope** |
| `TASK:<path>` | declared this task's — named by the task's own plan | **in scope** |
| `OTHER:<path>` | proven other work — already dirty when this task claimed | **never in scope** |
| `UNKNOWN:<path>` | no positive signal, or signals conflict | **ask first** (step 2b) |

`UNKNOWN:` is its own state, **not** a quiet "no". It means the path appeared
after this task claimed and its plan does not name it by exact path — a
concurrent session's edit and a file you touched but never planned look
identical from here, so the helper refuses to guess. A missing header signal
(`PLANSCOPE:missing`, `BASELINE:missing`) likewise does **not** mean "nothing is
this task's"; it means one signal was unavailable and more paths will land in
`UNKNOWN:`.

This is **only to inform** which areas changed — it is **not** a pass/fail
heuristic. The helper already drops task/plan data paths (`aitasks/`,
`aiplans/`, `.aitask-data/`); do not re-filter them.

### 2b. Resolve `UNKNOWN:` paths before inferring anything

If there are no `UNKNOWN:` lines, skip to step 3. Otherwise resolve them
**before** proposing any doc change — inferring first and asking later means the
proposal itself was built from another task's work.

**Interactive:** use `AskUserQuestion`:
- List each `UNKNOWN:` path with **why** it is unknown — "changed after this
  task was claimed and not named in its plan", or "named by the plan but
  already dirty when the task claimed (conflicting signals)". Where a path sits
  under a directory the plan mentions, say so — it makes the path plausible, but
  it is not attribution and must not be presented as one.
- Header: "Scope"
- Options: "Include all" / "Choose a subset" (`multiSelect: true`, one option
  per path) / "Exclude all".

Only the paths the user includes join the in-scope set.

**Autonomous / non-interactive profiles:** **exclude** every `UNKNOWN:` path.
Record the exclusion in the step-6 sidecar log so a dropped doc obligation is
auditable rather than invisible. Never include them unasked — that is the
failure this attribution exists to prevent.

### 3. Infer + propose the doc updates

Using the configured guide's change-kind→doc-area map **and the shape of the
existing docs**, determine which doc pages/sections to create or update. Follow the
guide's writing conventions. If the change touches no doc-relevant surface at all,
plan to record `skip` (step 6).

### 4. Confirm with the user

Present the proposed doc changes **and the attributed file list they were
derived from** — the `COMMITTED:` + `TASK:` paths, plus any `UNKNOWN:` the user
included at step 2b. Showing the attributed set is not redundant with step 2b:
`TASK:` rests on the task's plan naming a path, which is a *declared* signal,
not a proven one. A concurrent session's edit to a file this task's plan happens
to name is classified `TASK:` and would otherwise never be seen. This list is
the user's only chance to catch that before doc edits land.

Then use `AskUserQuestion`:
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
# ALSO record the attribution state, so the verdict is auditable after the fact:
#   both header values (BASELINE:… / PLANSCOPE:…), the count per class, and the
#   full path list of every UNKNOWN: that was excluded rather than included.

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
- **Treat an unattributed dirty path as in-scope without the user's
  confirmation.** An `UNKNOWN:` path may belong to another task.
- **Gather the change surface with raw `git diff` / `git ls-files`.** That
  returns the whole dirty tree unattributed — use the helper in step 2.
- Record `pass` when no doc-relevant surface was touched — that is `skip`.
- Modify the task frontmatter or any other gate's `## Gate Runs` entries.
- Reference framework-internal convention docs — read the project's configured
  guide instead.

## Notes
- Procedure-backed gates and the command-vs-procedure distinction are documented in
  `aitask-gate-template` and the `aitasks/metadata/gates.yaml` header.
- The attended dispatch (allocate run → run this skill → it records) lives in the
  shared `task-workflow` (Step 8) and is reused by `aitask-resume`.
- This skill ships wrapper surfaces in every supported agent tree — Codex
  (`.agents/skills/aitask-gate-docs-updated/`) and OpenCode
  (`.opencode/skills/aitask-gate-docs-updated/` + `.opencode/commands/`). Those are
  generated pointers to this canonical body; refresh them with
  `./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> aitask-gate-docs-updated --force`
  rather than hand-editing.
