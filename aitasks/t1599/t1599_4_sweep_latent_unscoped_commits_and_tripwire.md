---
priority: medium
effort: medium
depends: [t1599_1, t1599_2, t1599_3]
issue_type: refactor
status: Ready
labels: [git, bash_scripts, robustness, test]
gates: [risk_evaluated]
folded_tasks: [1662]
anchor: 1599
created_at: 2026-08-25 12:50
updated_at: 2026-09-01 15:34
---

## Context

Parent: t1599. This child closes the **latent** half of the surface.

The audit found **19 unscoped `task_git commit` sites**. Three (owned by
t1599_1/2/3) also stage a whole directory and are the empirical bug. The
remaining **16** already stage explicit paths but still finish with a bare
`commit`, which writes the **entire index** — a TOCTOU race: any path a
concurrent session stages between your `add` and your `commit` lands in your
commit. This is exactly how t1207 captured 5 foreign files despite a verified
16-path allowlist.

## What this child does NOT buy — state this honestly

These sites measured **near-clean** on the live `aitask-data` branch:

| pattern | swallowed |
|---|---|
| `ait: Add task t…` | 2/300 (0.7%) |
| `ait: Add child task t…` | 0/300 |
| `ait: Update task t…` | 0/6 |
| `ait: Archive completed t…` | 3/300 (1%) |

So this is **latent-race hardening, not an observed defect**. Do not describe it
as fixing a measured bug. The value is closing the race class and preventing
regression.

## Dependencies — this child is gated

`depends: [t1599_1, t1599_2, t1599_3]`. The tripwire scans every script, so it
must not land until the three primary sites are scoped and the allowlist of
deliberate index-wide commits is settled — otherwise the guard fires on work
that is already planned.

## Exclusive script ownership

This child owns `aitask_create.sh`, `aitask_update.sh`, `aitask_archive.sh`,
`aitask_zip_old.sh`, `aitask_issue_import.sh`, and the new tripwire test.

**Do NOT edit** `aitask_pick_own.sh` (t1599_1), `aitask_fold_mark.sh`
(t1599_2), `aitask_sync.sh` / `aitask_lock.sh` (t1599_3) — even if the tripwire
flags them. If it does, those children did not finish; report it rather than
editing across the boundary.

## The 16 sites

Re-derive the current list before starting (other children will have changed
some), with:

```bash
grep -rn "task_git commit" .aitask-scripts/ --include=*.sh --include=*.py | grep -v -- '-- '
```

At audit time:

- `.aitask-scripts/aitask_create.sh` — `:864`, `:902`, `:904`, `:1958`, `:2136`,
  `:2138`, `:2168`, `:2170`
- `.aitask-scripts/aitask_update.sh` — `:1777`, `:2217`
- `.aitask-scripts/aitask_archive.sh` — `:283`, `:565`, `:645`
- `.aitask-scripts/aitask_zip_old.sh` — `:546`
- `.aitask-scripts/aitask_issue_import.sh` — `:792`

Each already stages an explicit path list immediately above. Mechanical
conversion: `add <paths>` + bare `commit -m <msg>` becomes
`commit -m <msg> -- <paths>`. Keep the `add` only where a path may be
**untracked** (a pathspec cannot name a file git does not know about) — which is
the common case here, since these scripts create new task/plan files.

Note the argument order: `-m` must precede `--`, or git reads the message as a
path.

## Two sites need care, not the mechanical edit

- **`aitask_zip_old.sh:537-539`** uses
  `task_git add -u "$TASK_ARCHIVED_DIR/" "$PLAN_ARCHIVED_DIR/"` — genuinely
  **directory-scoped by design** (archive bundling; it cannot enumerate the
  bundled files). Scope the commit to those same directory pathspecs, not to a
  file list. This is a legitimate broad scope, not a bug — but it is still
  narrower than the whole index.
- **`aitask_issue_import.sh:791-792`** is `task_git add "$created_file"` followed
  by `task_git commit --amend --no-edit`. It needs the same foreign-path guard
  t1599_2 adds to `aitask_fold_mark.sh`'s amend: refuse loudly if HEAD carries
  paths outside the expected set, rather than silently rewriting (and, if
  already pushed, rewriting published history).

## Reference patterns

- `.aitask-scripts/aitask_attach.sh:196-205` — `_attach_commit()`, with a
  load-bearing comment explaining exactly this bug
- `.aitask-scripts/aitask_gate_record.sh:81-82`
- `.aitask-scripts/aitask_gate.sh:1025-1032` — scoped no-op guard via
  `task_git status --porcelain -- "$file"`

## The tripwire

New `tests/test_no_unscoped_task_commit.sh`, in the spirit of the existing
`tests/test_no_raw_tmux.sh` (which enforces the tmux-gateway rule). Fail if a
`task_git commit` line carries no `--` pathspec.

Requirements:
- A **documented allowlist** for any deliberately index-wide commit, each entry
  carrying a comment explaining why. Settle the allowlist only after
  t1599_1/2/3 have landed.
- The failure message must name the offending file:line and point at the
  reference patterns above.

**State its limits in the test's header comment and in the docs:** it is a grep,
so it catches the common single-line shape and will NOT see a commit assembled
across lines or through a variable. It is a regression tripwire, **not** a proof
of absence. Do not let it read as stronger enforcement than it is.

## Verification

- `bash tests/test_no_unscoped_task_commit.sh` — passes on the fixed tree.
- **Negative control (required):** the tripwire must FAIL when pointed at a
  deliberately reintroduced unscoped commit. Prove it by adding a temporary
  fixture line (or a fixture file the test also scans) and confirming a
  non-zero exit — a guard that cannot fail guards nothing.
- Re-run the existing suites for every touched script:
  `bash tests/test_task_create.sh`, `bash tests/test_archive_no_overbroad_add.sh`
  (the t533 precedent for exactly this bug shape), plus any
  `test_update_*` / `test_zip_old*` / `test_issue_import*` files present.
- `shellcheck .aitask-scripts/aitask_*.sh`
- Confirm no cross-boundary edits: `git diff --name-only` must not list the five
  scripts owned by t1599_1/2/3.

## Merged from t1662: gate labels file staging in create like update does


## Origin

Surfaced while implementing t1599_2 (scoping `aitask_fold_mark.sh`'s commit and
guarding its amend). Enumerating what an amend-preceding `ait create` commit
legitimately contains required auditing every staging site in
`aitask_create.sh`, which is where this turned up.

## Defect

`aitask_create.sh` stages the label vocabulary **unconditionally** at every
commit site:

- `:863` (child), `:900` (parent), `:2060` (`commit_task`), `:2237` (batch
  child), `:2269` (batch parent) — each `task_git add "$LABELS_FILE" 2>/dev/null || true`

`aitasks/metadata/labels.txt` is a **shared global**, not task-owned. If it is
dirty for any reason — most commonly because a concurrent session just added a
label — the unconditional `add` stages that other session's edit and the
following commit carries it under a message naming *this* task.

`aitask_update.sh:2265-2271` already has the correct pattern for the same file:

```bash
# Only when this update actually appended to the vocabulary — otherwise
# labels.txt would be left dirty for an unrelated commit to sweep up.
if [[ "$_stage_labels" == true ]]; then
    task_git add "$LABELS_FILE" 2>/dev/null || true
fi
```

`aitask_create.sh` has no equivalent flag. The two writers of the same file
disagree about when to stage it.

## Why path-scoping does not fix this — t1599_4 is not a duplicate

`t1599_4` owns `aitask_create.sh` and scopes its **commits** (`:864`, `:902`,
`:904`, `:1958`, `:2136`, …). That is necessary but insufficient here: the
scoped pathspec must still *include* `labels.txt`, because a create that really
did add a label must commit it. So the foreign label edit rides along either
way. Only a "did *this* invocation append to the vocabulary?" gate distinguishes
them.

The two changes are complementary and touch the same file, so sequence them
behind `t1599_4` (or fold this into it) rather than landing both blind.

## Suggested fix

Mirror `aitask_update.sh`: have `add_label_to_file` / the label-registration path
report whether it actually appended, set a `_stage_labels`-style flag, and gate
all five `add "$LABELS_FILE"` sites on it. Reuse the existing name so the two
writers read the same way.

Note `lib/task_utils.sh` owns the canonical accessor `labels_file_path()` and
the label helpers (`sanitize_label` / `ensure_labels_file` / `add_label_to_file`)
— the "did it append" signal probably belongs there, so both writers share it
rather than each deriving it.

## Verification

- Seed a dirty `labels.txt` (simulating a concurrent session's append), run
  `ait create --batch --commit` with labels that are **already** in the
  vocabulary, and assert the resulting commit does **not** contain
  `aitasks/metadata/labels.txt` and that the file is still dirty afterwards.
- Negative control: the assertion must fail against today's unconditional `add`.
- Positive case: a create that introduces a genuinely new label **must** still
  commit `labels.txt` in the same commit — the co-change is legitimate and
  dropping it would leave the vocabulary uncommitted.
- Cover all five staging sites, or prove they share one gate.

## Verified findings (t1662 planning session, 2026-09-01)

Everything below was reproduced in a throwaway sandbox against `main` at
`679ddc446`, using the `tests/lib/test_scaffold.sh` `setup_fake_aitask_repo`
fixture. These are the parts a fresh context cannot cheaply re-derive.

### Reproduction — two distinct variants

**(a) Unstaged foreign edit — what the staging gate fixes.** Seed
`printf 'someone_elses_pending_label\n' >> aitasks/metadata/labels.txt` (no
`git add`), then
`ait create --batch --commit --silent --name probe --desc x --labels preexisting_label`
(a label already in the vocabulary). Observed: the creation commit
`ait: Add task t1: probe` contains **both** `aitasks/t1_probe.md` and
`aitasks/metadata/labels.txt`, the committed `labels.txt` carries
`someone_elses_pending_label`, and `git status --porcelain` comes back **empty**
— the other session's edit was silently absorbed.

**(b) Pre-staged foreign edit — what the staging gate does NOT fix.** Same seed,
but the other session already ran `git add aitasks/metadata/labels.txt`.
Observed: identical absorption. `task_git commit -m …` with **no pathspec**
commits the **entire index**, so refraining from `git add` in this invocation
changes nothing.

**Consequence — the two halves are mutually completing.** The staging gate buys
protection against **unstaged** foreign edits only. The staged half is closed
exclusively by this task's (t1599_4's) pathspec scoping. Neither change alone
fixes the reported bug.

### The pathspec hazard — t1599_4's mechanical conversion can re-open t1662

`git commit -- <pathspec>` commits the **working-tree** content at those paths,
**bypassing the index**. A create that genuinely added a label must commit
`labels.txt`, so the naive scoped form
`task_git commit -m "$msg" -- "$filepath" "$LABELS_FILE"` re-introduces t1662 in
full: a foreign worktree edit rides along regardless of what was staged.

**The pathspec must itself be conditional on the staging flag** — build the path
list as an array and append `"$LABELS_FILE"` only when this invocation actually
appended to the vocabulary:

```bash
local -a _paths=( "$filepath" )
if [[ "$_stage_labels" == true ]]; then
    _paths+=( "$LABELS_FILE" )
fi
task_git commit -m "$msg" -- "${_paths[@]}"
```

This is why t1662 was folded here rather than landed separately: the correct
final code is one edit, not two.

### The "did it append" signal already exists — do not invent one

`lib/task_utils.sh` already documents the rich-return globals
(`AIT_LABELS_NORMALIZED` / `AIT_LABELS_ADDED` / `AIT_LABELS_DROPPED`).
`add_labels_csv_to_file` **resets then populates** `AIT_LABELS_ADDED`;
`add_label_to_file` **appends** to it. `aitask_create.sh` simply never reads it
at the finalize commit sites. Nothing new belongs in the lib.

**Never call the label helpers via `$( )`** — command substitution runs them in a
subshell and the globals evaporate.

**The signal is PER-CALL, so a looping caller must sticky-OR it.** This rules out
a single shared `labels_vocab_dirty()` predicate for both writers:
`aitask_update.sh:1707` deliberately sticky-ORs `LABELS_VOCAB_DIRTY` across its
interactive menu loop, because each menu iteration re-calls
`add_labels_csv_to_file` and resets the array. A bare last-call predicate would
regress it. Keep the small duplication; it is not accidental.

### Site map and dispositions (line numbers as of `679ddc446`)

Reuse the name `_stage_labels` so both writers read the same way. Use
`if (( … )); then` — `(( … )) && x=true` returns non-zero and aborts under
`set -e`.

- **`:863` (finalize_draft, child) and `:900` (finalize_draft, parent)** — each
  branch calls `_register_task_labels "$filepath"` itself, so each sets its own
  flag immediately after that call:
  ```bash
  _register_task_labels "$filepath"
  local _stage_labels=false
  if (( ${#AIT_LABELS_ADDED[@]} > 0 )); then
      _stage_labels=true
  fi
  ```
- **`:2237` (batch child) and `:2269` (batch parent)** — these two **share one
  gate**. Both sit downstream of the single registration block at `:2185`, in
  the same `run_batch_mode` scope: declare `local _stage_labels=false` before
  that block and set it inside the existing
  `if (( ${#AIT_LABELS_ADDED[@]} > 0 ))` test that already emits the "Added to
  label vocabulary" info line. This mirrors `aitask_update.sh:2085-2093` exactly.
- **`:2060` (`commit_task`)** — **unreachable dead code.**
  `grep -rn 'commit_task' .aitask-scripts/ tests/` finds only the definition; the
  interactive flow (`:2496`) creates a *draft* and commits nothing, and the
  commit happens later in `finalize_draft`.

  **Disposition chosen in the t1662 session: gate it, do not delete it** — that
  decision was made while deleting it would have crossed t1599_4's ownership
  boundary. Gate directly on `AIT_LABELS_ADDED` (empty array ⇒ don't stage ⇒
  fail-safe).

  Two constraints, because the gate reads a global the function does not itself
  populate:

  - **Revival constraint — put this in the comment at the gate, not only here.**
    `commit_task` establishes no fresh per-invocation state, so a future caller
    could inherit a stale `AIT_LABELS_ADDED` from an earlier registration and
    stage `labels.txt` under the wrong commit. Any revival MUST set its own
    `_stage_labels` from its own registration call (per-call, or sticky-OR if it
    loops) rather than trusting the ambient global.
  - **Deletion is now available to you.** Post-fold, t1599_4 owns
    `aitask_create.sh`, so the boundary objection is gone: deleting the dead
    function removes the site and the revival hazard together, and shrinks this
    task's own site inventory by one (the audited 19 unscoped `task_git commit`
    sites become 18). Owner's call.

### `_register_task_labels` must reset `AIT_LABELS_ADDED=()` at entry

`_register_task_labels()` (`aitask_create.sh:804`) has three early returns —
missing file, no `labels:` line, empty CSV — that never reach
`add_labels_csv_to_file` and therefore leave the **previous draft's** result in
the array. `finalize_all_drafts` loops `finalize_draft` in **one process**, so
draft B inherits draft A's append:

```bash
_register_task_labels() {
    local filepath="$1"
    local raw csv
    # Every exit path must leave a truthful signal: finalize_all_drafts loops
    # this in one process, and a stale AIT_LABELS_ADDED from an earlier draft
    # would stage labels.txt under a later draft's commit.
    AIT_LABELS_ADDED=()
    [[ -f "$filepath" ]] || return 0
    ...
```

### Test plan — with the negative controls already validated

Home: `tests/test_label_autoadd.sh`, which already owns create.sh label
vocabulary + commit hygiene. Add a `files_in()` helper
(`git show --name-only --pretty=format: "$1"`) so per-commit assertions are
possible.

**The discriminating seed is a DIRTY `labels.txt`.** `git add` on an *unchanged*
file stages nothing, which is exactly why the file's existing Test 3
("pre-existing label ⇒ commit has no labels.txt") passes today and **cannot see
the bug**. Every new case must seed
`printf 'someone_elses_pending_label\n' >> "$VOCAB"` first.

- **T7 — batch parent (`:2269`)**: create with an already-known label against a
  dirty vocabulary. Assert the commit does **not** contain `labels.txt`, the
  foreign line is still pending in `git status --porcelain`, and still on disk.
- **T8 — batch child (`:2237`)**: same on the `--parent` path. A parent-only fix
  passes T7 and silently misses this.
- **T9 — finalize (`:863` + `:900`)**: draft → `--finalize`, for both a parent
  draft and a child draft, same assertions.
- **T10 — cross-draft stale signal (the entry reset).** ⚠️ **The naive version
  does not discriminate — verified.** Two drafts where A carries a new label and
  B carries none: A's commit includes `labels.txt` and leaves it *clean*, so B's
  stale-signal `git add` is a no-op on an unchanged file and B's commit is clean
  even against unpatched code. The test would pass either way.

  **Working construction:** inject a concurrent write through a
  `.git/hooks/post-commit` hook that appends a foreign label **after the first
  commit only** (guard with a marker file under `$(git rev-parse --git-dir)`),
  then run `--finalize-all` over both drafts. Verified against unpatched code:
  draft B — which carries **no** labels at all — commits `labels.txt` carrying
  `someone_elses_pending_label`, purely from the stale array. Draft order is the
  lexicographic glob over `aitasks/new/draft_*.md`, so name the drafts to pin it.

- **The pre-staged (staged-index) case is asserted in its SAFE form — never
  characterized.** Because this task lands the staging gate and the pathspec
  scoping **together**, there is no interim state in which absorption is correct.
  **Do not commit a test asserting today's absorption** — it would be a
  deliberate failure waiting for its own fix. Instead run reproduction (b) once
  as a **throwaway negative control** before writing the fix (proving the
  assertion can fail), and commit only the final assertion: a foreign edit that
  another session already `git add`-ed is **not** in the creation commit. That
  assertion is satisfied by the conditional scoped `commit -m … -- <paths>`
  above, so it belongs alongside T7–T10 and the suite then enforces the desired
  behavior continuously.

- **Positive control is already in the file and must keep passing.** Tests 1, 2
  and 5 assert that a genuinely new label **is** committed together with
  `labels.txt`. They are what catches an over-aggressive gate.

### Regression suites for the create.sh half

```bash
bash tests/test_label_autoadd.sh          # new cases + preserved positives
bash tests/test_update_label_staging.sh   # sibling writer, unchanged
bash tests/test_label_vocabulary_lib.sh   # lib rich-return contract
bash tests/test_draft_finalize.sh         # finalize path
bash tests/test_create_silent_stdout.sh   # --silent stdout still one line
```

### Commit boundaries

Code and `aitasks/` / `aiplans/` files must go in **separate** commits, task data
via `./ait git` — `task-workflow` SKILL.md:667 ("Never mix code files and
`aitasks/`/`aiplans/` files in the same `git add` or commit").

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1662** (`t1662_gate_labels_file_staging_in_create_like_update_does.md`)
