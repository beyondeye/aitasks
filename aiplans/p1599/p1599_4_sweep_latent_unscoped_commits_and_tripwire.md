---
Task: t1599_4_sweep_latent_unscoped_commits_and_tripwire.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Archived Sibling Plans: aiplans/archived/p1599/p1599_1_scope_pick_own_claim_commit.md, aiplans/archived/p1599/p1599_2_scope_fold_mark_commit_and_guard_amend.md, aiplans/archived/p1599/p1599_3_sync_per_task_commits_and_live_lock_skip.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-07 17:53
---

# p1599_4 — Sweep the latent unscoped commits, add a tripwire

## Context

Parent t1599: three task-data helpers staged a whole directory and committed the
**entire index**, so any file a concurrent session was mid-edit on was swept into
a commit naming a different task (measured: 26% of 400 claim commits). Siblings
t1599_1/2/3 fixed the three empirical sites and have landed.

This child closes the **latent** half. The remaining sites already stage explicit
paths but still finish with a bare `commit`, which writes the whole index — a
TOCTOU race: anything a concurrent session stages between your `add` and your
`commit` lands in your commit. This is how t1207 captured 5 foreign files despite
a verified 16-path allowlist.

**What this does NOT buy — say so plainly.** Measured on the live `aitask-data`
branch these sites are near-clean: `Add task` 2/300 (0.7%), `Add child task`
0/300, `Update task` 0/6, `Archive completed` 3/300 (1%). This is **latent-race
hardening, not an observed defect**. Do not describe it as fixing a measured bug
in the commit message or the docs.

Folded in is **t1662**: `aitask_create.sh` stages the shared label vocabulary
unconditionally, so a concurrent session's `labels.txt` edit rides along. The two
halves are mutually completing — the staging gate closes the *unstaged* foreign
edit, the pathspec closes the *pre-staged* one. Neither alone fixes it.

## Verification of the existing plan (verify pass, 2026-09-07)

Re-derived against HEAD `4005a02f2`. Six material findings; the rest confirmed.

| claim | status |
|---|---|
| "16 unscoped sites" | ❌ **15**. `aitask_create.sh:1958` is no longer a commit site (now `task_git_commit_scoped` at `:1235`). Every line number in the task drifted. |
| hand-roll `add <paths>` + `commit -m <msg> -- <paths>` | ❌ **superseded** — t1626 promoted the shape to `task_git_commit_scoped` (`lib/task_utils.sh:398-434`); every sibling calls it. |
| tripwire = `grep -v -- '-- '` | ❌ **two false positives**: `aitask_note.sh:623,995` are scoped on a **line continuation**. The scan must join continuations. |
| t1662's 5 unconditional `LABELS_FILE` sites | ✅ confirmed, all shifted +1 (`:864 :901 :2061 :2238 :2270`); no `_stage_labels` anywhere in create.sh |
| `commit_task` is dead code | ✅ confirmed by word-boundary grep across `.aitask-scripts/` + `tests/` — only the definition matches. **User decision: delete it.** |
| "`AIT_LABELS_ADDED` goes stale, verified against unpatched code" | ⚠️ **imprecise**. `add_labels_csv_to_file` resets *before* its empty-CSV guard, so staleness comes only from `_register_task_labels`'s three early returns — and it is **latent**: nothing reads the array on the finalize path today. T10's negative control must target a **naive-gate build**, not unpatched code (unpatched stages `labels.txt` regardless, so the test would pass either way). |

**New leverage found:** `tests/test_metadata_writer_inventory.py:126` already pins
the exemption reason *"labels.txt is staged by its callers' `_stage_labels` gate
(create/update)"*. That statement is **currently false for create**. This task
makes the pinned reason true; cite it in the commit message.

## Sites (current, HEAD `4005a02f2`)

| file | unscoped sites | disposition |
|---|---|---|
| `aitask_create.sh` | `:867 :905 :907 :2062 :2240 :2242 :2272 :2274` | scope + t1662 gate; `:2062` deleted with `commit_task` |
| `aitask_update.sh` | `:1809 :2272` | scope; the `_stage_labels`/`LABELS_VOCAB_DIRTY` gate already exists — the **pathspec** must inherit it |
| `aitask_archive.sh` | `:283 :565 :645` | scope (staging is already narrow; only the commit is not) |
| `aitask_zip_old.sh` | `:546` | directory pathspecs, `--no-stage` |
| `aitask_issue_import.sh` | `:792` | unscoped `--amend` — guard + scope |

`:905/:907`, `:2240/:2242`, `:2272/:2274` are silent/non-silent **forks of one
site**; the fork exists only to control git's own output, which the helper
handles uniformly, so each collapses to a single call.

### Pre-phase (risk mitigations)

**`probe_commit_pathspec_semantics`** — before converting anything, empirically pin three behaviours in a throwaway repo
and record the answers in the test header — the sibling precedent is "probed, not
assumed":

1. `git commit -o -- <dir>/` with an **untracked, unstaged** file under `<dir>` —
   confirm it is *not* committed (drives `zip_old`'s `--no-stage` choice).
2. `task_git_commit_scoped`'s internal `add -- <dir>/` **would** stage untracked
   files under that directory — confirm, since that is why `zip_old` must pass
   `--no-stage` rather than let the helper stage.
3. `commit -o -- <paths>` commits **worktree** content and ignores the index
   entry for those paths (inherited from t1599_1) — confirm it still holds.

## Step 2 — Convert the 13 ordinary sites to `task_git_commit_scoped`

Reuse the canonical seam; do not re-derive it. It already carries the two
non-obvious parts (empty-pathspec guard; `git status` exit captured separately so
a failing status reads as *unverified*, never *clean*) and passes `-o` so an
empty pathspec is fatal instead of silently committing the index.

Contract: `0` = committed, `2` = verified nothing to commit, `1` = failed.
Preserve each site's existing failure behaviour when mapping the return code —
`aitask_zip_old.sh` currently `warn`s on failure and must keep doing so, but the
`2` and `1` cases must stop being conflated (today `2>/dev/null || warn "Nothing
to commit"` reports a real failure as "nothing to commit").

Build every path list as an **array**, with the `${arr[@]+"${arr[@]}"}` empty-array
guard used at `aitask_pick_own.sh:622-624`, because several sites have
conditional members (`$parent_file`, `$LABELS_FILE`).

`aitask_zip_old.sh:534-546` is the one directory-scoped site: keep its existing
two-layer staging (tarball glob `add`, then `add -u` on the two archive dirs) and
call `task_git_commit_scoped --no-stage "$commit_msg" "$TASK_ARCHIVED_DIR/"
"$PLAN_ARCHIVED_DIR/"`. The file set is genuinely not enumerable there
(`archive_files` returns only counts), so directory pathspecs are the narrowest
honest scope — far narrower than the whole index, and **not** a bug to "fix" into
a file list.

## Step 3 — `aitask_issue_import.sh:789-793`: guard the amend, then scope it

Mirror the *shape* of `_fold_amend_guard` (`aitask_fold_mark.sh:859-941`), not its
code — that function reads fold-local globals (`primary_id`, `folded_ids`,
`fold_paths`) and is deliberately local to its script.

Here the expected HEAD set is exactly what `aitask_create.sh` staged: the created
task file, `$(labels_file_path)`, and — for a child — the parent task file.
Default-deny: any other path in `task_git show --name-only --format='' HEAD`
refuses. Add the same published-history refusal (`merge-base --is-ancestor HEAD
@{u}`), with the same accepted residual stated in the comment: it reads the local
tracking ref and does not fetch, so it can under-detect a published commit but can
never wrongly refuse an unpublished one.

**On refusal, fall back to a fresh scoped commit** of `$created_file` and `warn`
that it did so. Refusing and stopping would leave the frontmatter edits dirty in
the worktree — which is precisely the bystander state the next unscoped commit
sweeps up, i.e. this task's own defect re-created by its own guard. The fallback
terminates: it is a plain `task_git_commit_scoped` call with no further retry.

**Extract it into a named function — this is a testability requirement, not a
style preference.** The amend sits at the end of the batch import flow, which
cannot be driven in a test because it needs the `gh` CLI (the existing suite says
so at `tests/test_issue_import_contributor.sh:183-184`, which is exactly why this
block has **no coverage today**). Put the guard and the fallback in
`_import_commit_frontmatter <created_file>` — decides, commits, and returns — so a
test can source and drive it directly, the way `setup_parse_function`
(`tests/test_issue_import_contributor.sh:27-37`) already sources a function under
test without running `main`. The call site at `:789-793` becomes one call.

The refusal `warn` text is part of the guard's contract and is asserted, so it
must name the offending path and say that a fresh commit was made instead.

## Step 4 — t1662: gate the label-vocabulary staging in `aitask_create.sh`

The scoped pathspec must **itself** be conditional. `commit -- <paths>` commits
worktree content, so the naive `-- "$filepath" "$LABELS_FILE"` re-introduces
t1662 in full.

Reuse the name `_stage_labels` so both writers read alike. Use `if (( … )); then`
— `(( … )) && x=true` returns non-zero and aborts under `set -e`.

- **`:864` / `:901`** (`finalize_draft` child / parent) — each branch calls
  `_register_task_labels "$filepath"` itself (`:848` / `:884`), so each sets its
  own flag straight after that call from `${#AIT_LABELS_ADDED[@]}`.
- **`:2238` / `:2270`** (batch child / parent) — these **share one gate**. Both sit
  downstream of the single registration block at `:2186-2191`, which already
  computes `(( ${#AIT_LABELS_ADDED[@]} > 0 ))` for its info line. Declare
  `local _stage_labels=false` before it and set it inside that existing test —
  mirroring `aitask_update.sh:2086-2093`.
- **`:2061`** — deleted with `commit_task` (below).

**Entry reset.** `_register_task_labels` (`:805-815`) has three early returns
(`:808` missing file, `:810` no `labels:` line, `:812` empty CSV) that never reach
`add_labels_csv_to_file`, so it can leave the **previous draft's** result in the
array — and `finalize_all_drafts` (`:918-939`) loops `finalize_draft` in **one
process**. Add `AIT_LABELS_ADDED=()` immediately after the locals, with a comment
saying why. Today this is latent; it becomes load-bearing the moment Step 4's gate
reads the array, so it lands in the same change.

Do **not** add a shared `labels_vocab_dirty()` predicate for both writers: the
signal is per-call, and `aitask_update.sh:1699-1712` deliberately sticky-ORs it
across its interactive menu loop. A bare last-call predicate would regress that.
The small duplication is intentional.

## Step 5 — Delete the dead `commit_task` (`:2049-2070`)

Verified unreachable: a word-boundary grep over `.aitask-scripts/` and `tests/`
(excluding the unrelated Python `commit_task_paths` / `_do_git_commit_tasks`)
matches only the definition. The interactive flow ends at `create_draft_file`
(`:2544`) and both committing menu branches route to `finalize_draft`
(`:2447`, `:2580`). Deleting it removes an unscoped site and the "a revived caller
inherits a stale `AIT_LABELS_ADDED`" hazard together.

## Step 6 — `tests/test_no_unscoped_task_commit.sh`

Model: `tests/test_no_raw_tmux.sh`, whose house style is uniform across the
repo's guard tests — `set -uo pipefail`, sources `tests/lib/asserts.sh` only,
plain in-process `PASS/FAIL/TOTAL` (no `assert_counters_*`: no test body runs in a
`( … )` subshell), `ALLOWLIST` array with a per-entry `#` reason, `scan_dir`
**parameterized on root** so it runs against both the real tree and synthetic
fixtures, footer `Results: $PASS passed, $FAIL failed, $TOTAL total`.

Borrow the `ACTIVE_ALLOWLIST` indirection from
`tests/test_no_lib_to_tui_import.sh:67` so the allowlist-suppression control uses
a **synthetic** entry rather than pinning a real one.

- **Join line continuations before matching.** Otherwise `aitask_note.sh:623,995`
  are false positives. This is the single most important detail in the file.
- Match `task_git[[:space:]]+commit` with a word boundary so
  `task_git_commit_scoped` is never matched.
- Skip pure-comment lines, as `test_no_raw_tmux.sh:94` does.
- **The allowlist is empty after this task.** Keep the array and its mechanism,
  with a comment saying the empty state is the intended end state and what would
  justify an entry.
- Failure message: `FAIL:` header, one indented line per violation as
  `<relpath>:<line>:<text>`, then a two-line `->` remediation naming
  `task_git_commit_scoped` and the reference patterns
  (`aitask_attach.sh:205-212`, `aitask_gate_record.sh:81-82`,
  `aitask_gate.sh:1029-1037`).

**Limits disclosure — in the test header and in the docs.** Follow the house
phrasing ("Detection scope (documented on purpose — a guard that overclaims is
worse than one with a known boundary)"):

- it is a grep over joined logical lines: it will **not** see a commit assembled
  through a variable;
- it scans `.aitask-scripts/` `*.sh` only, not `tests/`;
- **it does not scan `./ait git commit`.** Two unscoped sites exist on that seam
  (`aitask_verification_followup.sh:251`, `lib/verified_update_lib.sh:128`); they
  are owned by the follow-up task in Step 8, not by this guard. Naming the gap is
  what keeps the guard from reading as stronger than it is.
- it is a **regression tripwire, not a proof of absence**.

**Negative controls (required, executable).** A synthetic tree under `mktemp -d`
with a trap cleanup, asserting each direction independently:

1. a rogue unscoped `task_git commit` **is** flagged;
2. a scoped one is **not**;
3. a scoped one **split across a continuation** is **not** (pins the joining
   logic — without this, joining could be dropped and every other test still
   passes);
4. an allowlisted rogue is suppressed (via `ACTIVE_ALLOWLIST`);
5. a commented-out line is not flagged;
6. an exact hit-count assertion, so the scan cannot pass by matching nothing.

## Step 7 — Docs

Add one bullet to `aidocs/framework/shell_conventions.md` (a flat bullet list;
CLAUDE.md routes every `.aitask-scripts/` shell edit through it): commit
task-data paths with `task_git_commit_scoped`, never a bare `task_git commit`,
because a bare commit writes the whole shared index. State the guard's name and
repeat its two limits (variable-built commands; `./ait git commit` out of scope).

## Step 8 — Spawn the `./ait git commit` follow-up

Create one task owning `aitask_verification_followup.sh:251` and
`lib/verified_update_lib.sh:128` — path-scope both, and decide there whether the
guard should grow a second pattern. `followup_kind: upstream_defect`.
Created post-approval (plan mode creates nothing).

### Post-phase (risk mitigations)

**`cochange_positive_controls`** — after the conversion lands, pin the two
legitimate co-changes as executable assertions so the scoping cannot silently
over-narrow: a **child** creation must still commit its **parent** task file, and
a genuinely-new label must still commit `labels.txt`. These are *permit*-direction
tests, not negative controls — they pass before and after the fix by
construction, and their job is to fail if the pathspec is drawn too tight. Detail
in Verification below.

## Verification

**Tripwire**
- `bash tests/test_no_unscoped_task_commit.sh` passes on the fixed tree.
- Its six negative controls pass — control 1 proves it can fail at all, control 3
  proves the continuation-joining is real.

**t1662 half — home is `tests/test_label_autoadd.sh`** (6 existing tests; add
T7+). Add a `files_in()` helper (`git show --name-only --pretty=format: "$1"`).

**The discriminating seed is a DIRTY `labels.txt`.** `git add` on an *unchanged*
file stages nothing — which is exactly why the file's existing Test 3
("pre-existing label ⇒ commit has no labels.txt") passes today and **cannot see
the bug**. Every new case seeds
`printf 'someone_elses_pending_label\n' >> "$VOCAB"` first.

- **T7 — batch parent (`:2270`)**: already-known label against a dirty vocabulary.
  Commit does **not** contain `labels.txt`; the foreign line is still pending in
  `git status --porcelain` and still on disk.
- **T8 — batch child (`:2238`)**: same on the `--parent` path. A parent-only fix
  passes T7 and silently misses this.
- **T9 — finalize (`:864` + `:901`)**: draft → `--finalize`, for a parent draft and
  a child draft, same assertions.
- **T10 — cross-draft stale signal (the entry reset).** The naive two-draft
  version does **not** discriminate. Working construction: a
  `.git/hooks/post-commit` hook that appends a foreign label **after the first
  commit only** (guard with a marker file under `$(git rev-parse --git-dir)`),
  then `--finalize-all` over two drafts named to pin the lexicographic order.
  **Its negative control is a naive-gate build** (the gate without the entry
  reset), not unpatched code — unpatched stages `labels.txt` unconditionally, so
  the assertion would pass against it for the wrong reason. No `post-commit` hook
  exists in the suite yet; the load-bearing fact is that hooks live in the
  **common** git dir, which the `.aitask-data` worktree shares
  (`test_metadata_commit_seam.sh:80-89`).
- **T11 — pre-staged foreign edit.** Assert the **safe** form only: a foreign
  `labels.txt` edit another session already `git add`-ed is **not** in the
  creation commit. Run the absorption reproduction once as a **throwaway**
  control before writing the fix, to prove the assertion can fail; never commit a
  test asserting today's absorption — with both halves landing together there is
  no interim state in which absorption is correct.
- **Positive controls that must keep passing:** existing T1, T2, T5 assert a
  genuinely new label **is** committed together with `labels.txt`. They are what
  catches an over-aggressive gate. Add one more: a **child** creation must still
  commit its **parent** task file — the co-change a naive "only the task file"
  pathspec would silently drop.

**Amend guard — new `tests/test_issue_import_amend_guard.sh`.** The block being
changed has **no coverage today**, so the existing contributor suite cannot
detect either failure mode: a guard that refuses a *safe* amend, or one that
refuses a contaminated HEAD and loses the frontmatter edit. Both branches must be
**forced**. Build a real repo with `setup_project`'s shape (bare remote + clone),
source `_import_commit_frontmatter`, and drive it:

- **A1 — expected HEAD amends.** HEAD carries the created task file (and, in a
  second variant, `+ $(labels_file_path)` and `+ the parent file`, the other two
  accepted shapes). Assert: commit **count unchanged**, HEAD **SHA changed**, the
  updated frontmatter is in HEAD, and no extra path entered the commit. This is
  the *permit* direction — without it, a guard that refuses everything passes the
  whole refuse side.
- **A2 — foreign path in HEAD refuses, and nothing is lost.** HEAD additionally
  carries an unrelated `aiplans/p999_*.md`. Assert: HEAD SHA **unchanged** (the
  contaminated commit was not rewritten), the foreign path is **still** in that
  old commit, **a new commit exists** whose `--name-only` is exactly
  `$created_file`, the injected frontmatter is in it, and
  `git status --porcelain` is clean for `$created_file` afterwards. The
  "nothing is lost" half is the load-bearing one: SHA-unchanged alone would also
  pass if the function had simply dropped the edit on the floor.
- **A3 — published HEAD refuses the same way.** `git push -u` so HEAD is an
  ancestor of `@{u}`; assert the A2 outcome. Pins the second refusal branch,
  which A2 does not reach.
- **A4 — the refusal warning is asserted**, naming the offending path. A silent
  fallback and a loud one are indistinguishable to A2's state assertions.
- **Negative controls (required).** Rebuild the fixture's copy of the script with
  the guard stripped (the `install_prefix_*` technique from
  `tests/test_pick_own_scoped_commit.sh`) and assert A2 **fails** against it — the
  contaminated HEAD gets amended and no fresh commit appears. A guard that cannot
  fail guards nothing. Separately assert A1 fails against a build whose guard
  refuses unconditionally, so the permit direction is proven discriminating too.

**Regression suites**
```bash
bash tests/test_label_autoadd.sh            bash tests/test_update_label_staging.sh
bash tests/test_label_vocabulary_lib.sh     bash tests/test_draft_finalize.sh
bash tests/test_create_silent_stdout.sh     bash tests/test_archive_no_overbroad_add.sh
bash tests/test_zip_old.sh                  bash tests/test_issue_import_contributor.sh
bash tests/test_issue_import_amend_guard.sh
bash tests/test_task_git.sh                 bash tests/test_metadata_commit_seam.sh
bash tests/test_fold_mark.sh
python3 tests/test_metadata_writer_inventory.py
shellcheck .aitask-scripts/aitask_*.sh
```
(`test_create_silent_stdout.sh` is load-bearing for Step 2's fork collapse: it
exists because a non-`--quiet` `task_git commit` leaked git's summary into the
`--silent` stdout data channel.)

**Boundary check.** `git diff --name-only` must not list `aitask_pick_own.sh`,
`aitask_fold_mark.sh`, `aitask_sync.sh` or `aitask_lock.sh`. If the tripwire flags
them, a sibling did not finish — report it rather than editing across the
ownership boundary.

**Commit boundaries.** Code and `aitasks/`/`aiplans/` files go in **separate**
commits, task data via `./ait git`.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.

## Risk

### Code health — high

Raised from medium on this verify pass: the blast radius is 14 call sites across
five scripts on the highest-frequency task-data write paths, and the change adds a
brand-new refusal guard on a path that has **no test coverage at all** today. Both
of that guard's failure modes are silent.

- **Silently dropping a legitimate co-change.** Scoping a commit narrower than the
  real change set is invisible at runtime: the commit succeeds, the co-changed
  file just stays dirty. The exposed cases are the child-creation parent file and
  a genuinely-new `labels.txt`. · severity: medium · → mitigation: inline
  post-phase `cochange_positive_controls`
- **Blast radius.** Five scripts on the highest-frequency task-data write paths
  (create / update / archive), 14 call sites. · severity: medium · → mitigation:
  inline pre-phase `probe_commit_pathspec_semantics`
- **`zip_old`'s directory pathspec is the widest scope retained**, and the helper's
  own staging would widen it further if `--no-stage` were forgotten. · severity:
  medium · → mitigation: inline pre-phase `probe_commit_pathspec_semantics`
- **The `issue_import` amend guard is new behaviour on a currently-uncovered
  path**, with two silent failure modes: refusing a *safe* amend, or refusing a
  contaminated HEAD and dropping the frontmatter edit. Neither is visible to any
  existing suite. · severity: high · → mitigation: `tests/test_issue_import_amend_guard.sh`
  (A1–A4 + negative controls), and the `_import_commit_frontmatter` extraction
  that makes the path reachable at all

### Goal achievement — low

The approach is fixed by three landed siblings and a canonical helper, and the
site inventory was re-derived rather than trusted. Residual: the guard's
published-history check carries a stated, accepted blind spot (it reads the local
tracking ref and does not fetch, so it can under-detect a published commit but can
never wrongly refuse an unpublished one). · severity: low · → mitigation: stated
in the guard's comment; no further action

### Planned mitigations
- timing: pre-phase | name: probe_commit_pathspec_semantics | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: blast radius + zip_old directory scope | desc: Empirically pin commit -o -- <dir> untracked behaviour, helper staging width, and worktree-vs-index semantics before converting any site.
- timing: post-phase | name: cochange_positive_controls | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: silently dropping a legitimate co-change | desc: Assert the child-creation parent file and the genuinely-new labels.txt still land in their commits, so the scoping cannot over-narrow.
