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
It writes its proposed pages as drafts, has them reviewed by the
`aitask-docs-review` procedure (step 3b) before the user confirms, and applies
them only over pages no other session changed meanwhile (step 5).

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

### 3. Infer + draft the doc updates

Using the configured guide's change-kind→doc-area map **and the shape of the
existing docs**, determine which doc pages/sections to create or update. Follow the
guide's writing conventions. If the change touches no doc-relevant surface at all,
plan to record `skip` (step 6).

**Write every proposed page as a complete draft, never as an outline and never
into the real page.** The drafts directory for this run is:

```bash
drafts=".aitask-gates/<task-id>/docs_updated_<run-id>_drafts"
```

For each page to create or update, under `"$drafts"` at the page's own path
(`mkdir -p` the parent directories):

1. **Existing page:** **first** copy the page as it is now to `<page path>.base`.
   **New page:** write no `.base`.
2. Write the complete proposed page to `<page path>.draft`. For an existing page,
   draft **from the `.base` copy**, never from a second read of the live page:
   the `.base` is the exact text the draft was built on.

**A page that already has a draft in this run keeps its `.base`.** Further
changes to it (an "Adjust", a fact moved in by the review, a re-entry from step 5)
edit its `.draft` only. Its `.base` changes only through the step-5 transitions
(the merge snapshot, a "created" re-draft, a "deleted" choice), never by
re-copying the live page.

The real pages are not touched until step 5.

**Fresh-reader budget, once per run id.** The run's budget lives in
`"$drafts/.reader_budget"`:

```bash
[ -f "$drafts/.reader_budget" ] || echo 3 > "$drafts/.reader_budget"
```

Write `3` **only when the file does not exist yet**; otherwise read what is left.
Step 5 sends created and deleted pages back to this step within the same run, and
that re-entry keeps the remaining budget: it never resets it. Every step that
spends or grants budget (3b, 4a) writes the new value back.

### 3b. Review the drafts

Read and follow **`.claude/skills/aitask-docs-review/SKILL.md`** (by file path, so
every agent tree can follow it) with:

- the `.draft` paths written or changed since their last review;
- `--caller gate`;
- `--budget <n>`, where `<n>` is the value in `"$drafts/.reader_budget"`.

Subtract the review's `BUDGET_USED` and write the result back to
`.reader_budget`. The budget is **3 per gate run, cumulative across every review
and re-review** in this run: the first review, every re-review after "Adjust" or
a reconciliation, and pages returned to step 3. Within a review the skill tests
beginner-level pages with the most changed body lines first; pages left over
once the budget is spent are `reader=not-run(cap)`.

The review may fix level and prose findings in the drafts themselves, and may put
a moved fact into the owning page's draft: it reuses that page's existing draft
and `.base` when the page already has one in this run, and starts a new pair only
for a page not yet in the run. Every draft it adds or changes is reviewed in the
same call, so all of them reach step 4 reviewed. Keep its report for steps 4 and
6.
When the guide has no level model, the review skips the level check and the
fresh-reader test (`not-run(no-level-model)`) and uses no budget.

### 4. Confirm with the user

Present the proposed doc changes **and the attributed file list they were
derived from** — the `COMMITTED:` + `TASK:` paths, plus any `UNKNOWN:` the user
included at step 2b. Showing the attributed set is not redundant with step 2b:
`TASK:` rests on the task's plan naming a path, which is a *declared* signal,
not a proven one. A concurrent session's edit to a file this task's plan happens
to name is classified `TASK:` and would otherwise never be seen. This list is
the user's only chance to catch that before doc edits land.

Present the review with them: per page the `level=`, `prose=` and `reader=`
results, the reader report, the **unresolved problems**, the pages left
`reader=not-run(cap)`, and the remaining fresh-reader budget. When the review
found no level model, say that the project's guide has no level model, so pages
were checked for prose only. Put all of this in the `AskUserQuestion` question
text itself (condensed to short lines if long), since the widget is the only
surface the user is sure to see. Unresolved problems inform the user's decision;
they do not fail the gate on their own.

**4a. More fresh-reader tests (interactive only, and only when a page is
`not-run(cap)`).** Ask first, as its own `AskUserQuestion`:
- Question: names each `not-run(cap)` page and the remaining budget, then asks
  whether to test them.
- Header: "Reader"
- Options: **Run more fresh-reader tests** (description: names the pages; tests
  exactly those) / **Continue without them**.

"Run more fresh-reader tests" is the user's explicit authorization: add one test
per named page to `.reader_budget`, re-run step 3b on those pages only, then come
back to step 4. Autonomous / non-interactive profiles never ask this and never
extend the budget; their `not-run(cap)` pages stay as they are and are logged.

**4b. The decision.** Use `AskUserQuestion`:
- **Apply** — apply the reviewed drafts (step 5).
- **Adjust** — revise the drafts per the user's guidance, re-run step 3b on the
  changed pages (level and prose check always; fresh-reader only within the
  remaining budget), then present step 4 again.
- **Not needed / skip** — the user judges no doc update is warranted.
- **Reject** — the user blocks doc work that is needed.

A draft changed after its last review is never applied: it goes through step 3b
and step 4 again first.

In autonomous / remote profiles (non-interactive), follow the active profile's
policy (apply per the spec, or record a deferral) instead of blocking.

### 5. Apply

Apply each confirmed draft only over a destination that has not changed since
drafting began. For each page, compare against the **live** destination and act
on exactly one row:

| `.base` | destination now | state | action |
|---|---|---|---|
| yes | exists, `cmp -s` equal to `.base` | unchanged | copy `.draft` over it |
| no | absent | unchanged (new page) | copy `.draft` into place |
| yes | exists, differs from `.base` | modified by another session | snapshot it, then three-way merge with `git merge-file` (below) |
| no | exists | created by another session | apply nothing for this page; back to step 3, which copies the page that now exists to `.base` first and drafts from that copy |
| yes | absent | deleted by another session | apply nothing for this page; back to step 3 and ask the user whether to recreate the page, move the change to another page, or drop it |

Never apply a draft over a destination that is not in an "unchanged" row. Pages
in an unchanged row still apply normally while other pages go back.

**Deleted by another session.** The user's answer sets the page's next state. The
run's budget is unchanged in every case.

- **Recreate the page:** delete `"$drafts/<page path>.base"`; the page is now a
  new page. Keep its `.draft` (or re-draft it as a new page); it goes through
  step 3b and step 4 again and then applies through the "unchanged (new page)"
  row, or through the "created" row if the page reappears meanwhile.
- **Move the change to another page:** **first** put the change into the other
  page's draft by step 3's rules (an existing draft there is reused with its
  `.base` untouched; otherwise a new pair is started), and confirm the write
  landed: the other page's `.draft` exists and contains the moved change. **Only
  then** delete this page's `.draft` and `.base`. If the write failed or cannot be
  confirmed, keep this page's pair as it is: the page stays pending in the
  "deleted" row, nothing is lost, and you report the failed move. The other
  page's draft goes through step 3b and step 4.
- **Drop it:** delete this page's `.draft` and `.base`. Nothing is applied for
  it, and the step-6 log records it as dropped.

**Modified by another session**, in this order:

1. Snapshot the destination once: `cp <destination> "$drafts/<page path>.snapshot"`.
2. Merge **from the snapshot**, never from the live page:

   ```bash
   rc=0
   git merge-file -p "$drafts/<page path>.snapshot" "$drafts/<page path>.base" \
       "$drafts/<page path>.draft" > "$drafts/<page path>.reconciled" || rc=$?
   ```

   - `rc` `0` → a clean reconciled draft.
   - `rc` `1`–`127` → that many conflicts. Resolve them by hand in
     `.reconciled`; it counts as a draft only once it holds no conflict markers
     (`<<<<<<<`, `=======`, `>>>>>>>`). Check, do not assume — this must print
     nothing:

     ```bash
     grep -nE '^(<<<<<<<|=======|>>>>>>>)( |$)' "$drafts/<page path>.reconciled"
     ```
   - any other `rc` (git reports errors as a negative value, seen as `255`) →
     an **error, not a reconciliation**: discard `.reconciled` and `.snapshot`,
     apply nothing for this page, and report it.
3. On a clean or hand-resolved merge, `.reconciled` replaces the `.draft`, and
   **the snapshot becomes the new `.base`** (`mv` the `.snapshot` over the
   `.base`). Never re-copy the live page for this: an edit that lands between the
   merge and a re-copy would be in `.base` but not in the draft, and the next
   apply would find the destination "unchanged" and overwrite that edit. With the
   snapshot as `.base`, such an edit puts the page back in this row.
4. The reconciled page goes back through step 3b (within the remaining budget)
   and step 4 before anything is written.

`git merge-file` runs only in this row: in the "created" and "deleted" rows one
of its three inputs does not exist.

The applied pages are code-tree files (e.g. the docs site / design docs) → they
are committed with the task in the normal review/commit step, so they land in
the task's `(t<task-id>)` commit.

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
# AND the review, one line per reviewed page:
#   <page path> level=<…> prose=<…> reader=<…> unresolved=<n>
# then the pages left reader=not-run(cap), any page not applied (and why), and
# the fresh-reader tests used out of the run's budget.

./.aitask-scripts/aitask_gate.sh append --only-if-running <run-id> \
    <task-id> docs_updated <pass|skip|fail> \
    run=<run-id> attempt=<attempt> type=machine \
    verifier=aitask-gate-docs-updated result="<short summary>" log="$log"
```

- Use the status from the table above.
- The review lines use the review skill's values as reported. `reader=` is
  exactly one of `subagent`, `self-review`, `not-run(not-beginner)`,
  `not-run(untagged)`, `not-run(cap)`, `not-run(no-level-model)`.
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
- **Apply a draft over a destination that is not in an "unchanged" row** of the
  step-5 table.
- **Treat a `git merge-file` error (exit status outside `0`–`127`) as a
  reconciliation.** It applies nothing for that page.
- **Rebaseline `.base` from a fresh read of the live page**, after a merge (the
  merge's snapshot is the new `.base`) or when a page that already has a draft
  in this run receives more changes (its `.base` stays as it is).
- **Leave a deleted page's old `.base` in place** once the user chose to
  recreate it: the recreated page is a new page.
- **Delete a page's draft pair before the change it carries is safely saved
  elsewhere** (the "move" choice writes and confirms the other page's draft
  first).
- **Apply a draft that changed after its last review.**
- **Reset `.reader_budget`** when step 3 is re-entered in the same run, or extend
  the fresh-reader budget without the user's explicit "Run more fresh-reader
  tests" choice (never in autonomous profiles).
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
