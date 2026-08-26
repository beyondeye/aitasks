---
Task: t1616_task_worktree_gitignore_and_data_symlinks.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1616 — Task-worktree gitignore and data symlinks

## Context

Two independent defects, both hit while working inside a task worktree
(`aiwork/<task_name>`, created by task-workflow Step 7), neither in the code the
originating task changed.

**Defect 1 — `aiwork/` is not ignored.** `.gitignore:15` ignores the sibling
AgentCrew worktree dir `.aitask-crews/`, but nothing ignores `aiwork/`
(`git check-ignore -v aiwork/` matches nothing). Every task worktree therefore
shows as `?? aiwork/` in the primary checkout and is exposed to a broad
`git add -A` — worst with several agents active at once, where one session's
staging command can sweep another session's worktree.

Exploration widened this slightly: **`ait setup` seeds neither rule.** The
`.aitask-crews/` line is a hand-written line in this repo's `.gitignore` only
(`grep -c aitask-crews aitask_setup.sh install.sh` → 0), so every downstream
project that uses task worktrees or crews has the same exposure and no rule at
all. The fix therefore lands in both places.

**Defect 2 — a task worktree has no task-data plumbing.** In the primary
checkout `aitasks` and `aiplans` are gitignored symlinks into `.aitask-data/`
(`.gitignore:43-46`), created by `aitask_init_data.sh` / `aitask_setup.sh` for
the primary checkout only. A `git worktree add` checkout of the code branch has
neither, and Step 7's fork block (`SKILL.md:490-493`) does no post-creation
setup at all. Consequences:

- Four python suite modules fail with `FileNotFoundError` on
  `aitasks/metadata/*.json`. They resolve `REPO_ROOT = Path(__file__).resolve()
  .parent.parent` and read the *real* tree — e.g.
  `tests/test_settings_brainstorm_descriptions.py:27`,
  `tests/test_profile_editor_shadow_tier.py:132/137/150`,
  `tests/test_board_movement.py:1267` (its isolation negative control asserts
  the real `aitasks/` is non-empty). A 4-minute suite run in a fresh worktree
  ends in four red modules that look like the task's own regressions, and the
  agent must disprove that before trusting any verdict.
- **`./ait` is broken inside the worktree.** `ait:4-9` cds to its *own*
  directory, so from a worktree `TASK_DIR="aitasks"` resolves locally and finds
  nothing. Worse, `_ait_detect_data_worktree()`
  (`lib/task_utils.sh:35-42`) probes `.aitask-data/.git` relative to cwd; with
  no `.aitask-data` present it silently selects **legacy mode**, so
  `./ait git add aitasks/…` — which task-workflow Step 8 runs — misroutes.

Intended outcome: task worktrees are ignored by git and are given the same
branch-mode data layout as the primary checkout, so the suite and every `ait`
command behave identically inside and outside a worktree.

## Approach

Three decisions were confirmed with the user:

1. Fix `.gitignore` **and** seed both rules (`aiwork/`, `.aitask-crews/`) from
   `ait setup` for downstream projects.
2. Link **all three** entries in the worktree (`.aitask-data`, then `aitasks`
   and `aiplans` relative to it) — byte-identical to the primary's layout, which
   both reuses the existing link form verbatim and fixes the `ait git`
   misrouting above.
3. Extract the symlink logic into one directory-parameterized lib helper and
   convert the two existing inline copies onto it.

---

## Deliverables

### 1. `.gitignore` — ignore task worktrees

Add beside the existing `.aitask-crews/` rule (`.gitignore:14-15`), matching its
comment shape:

```
# Task worktrees (local, per-task branches)
aiwork/
```

No regression surface: `git ls-files aiwork` is empty (nothing tracked to
un-track), and `aitask_codemap.sh` only scans directories containing
git-tracked files, so its "`aiwork/` is a normal project directory" behaviour is
unchanged.

### 2. New helper — `.aitask-scripts/lib/data_symlinks.sh`

The one canonical creator of the branch-mode data layout. Today the logic is
duplicated in `aitask_init_data.sh:50-57` and an inline subshell in
`aitask_setup.sh:1625-1636`, and neither is parameterized by directory.

```bash
#!/usr/bin/env bash
# data_symlinks.sh - Canonical creation of the branch-mode data layout.
#
#   <root>/.aitask-data        the data-branch worktree (or a symlink to it)
#   <root>/aitasks  -> .aitask-data/aitasks
#   <root>/aiplans  -> .aitask-data/aiplans
#
# The RELATIVE link form is load-bearing: install.sh's ensure_data_root()
# (install.sh:353) recognizes ONLY `.aitask-data/<name>` and die()s on anything
# else. Do not change the target spelling here without changing that check in
# the same commit.

[[ -n "${_AIT_DATA_SYMLINKS_LOADED:-}" ]] && return 0
_AIT_DATA_SYMLINKS_LOADED=1

AIT_DATA_DIR_NAME=".aitask-data"
AIT_DATA_LINKS=(aitasks aiplans)

# ait_ensure_data_symlinks <root>
#   Create the two data symlinks under <root> if absent; drop a dangling link
#   first. SEMANTICS ARE UNCHANGED from the two inline copies it replaces — an
#   existing, resolving link is left alone, whatever its target. This is a pure
#   extraction, so the setup/install path gains no new behaviour.
#   Idempotent. Returns 1 if <root> is not a directory.
ait_ensure_data_symlinks() { … ; return 0; }

# ait_link_worktree_data <worktree_root> <main_root>
#   Give a LINKED WORKTREE the primary's data layout: a .aitask-data symlink to
#   <main_root>/.aitask-data, then the two relative links on top. Unlike the
#   primary path above this VALIDATES existing entries and repairs mismatches
#   (see the table in §3) — inside a task worktree all three names are
#   framework-owned and gitignored, so a stale link to another checkout's data
#   branch is drift to fix, not user state to preserve. An entry that is not a
#   symlink is still refused, never clobbered. Ends by calling
#   ait_ensure_data_symlinks to create whatever is now absent.
ait_link_worktree_data() { … ; }

# Both report what they changed on stderr and leave stdout to the caller.
```

Notes for the implementer:

- Keep the existing `[[ -L x && ! -e x ]] && rm -f x` repair idiom, but end each
  function with an explicit `return 0` — a trailing `[[ … ]] && …` that fails
  returns 1 and kills a `set -e` caller (`shell_conventions.md`).
- This lib is **not** added to `./ait`'s source-on-startup chain (only
  `aitask_init_data.sh` and `aitask_setup.sh` source it), so
  `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` needs **no** change.
- `install.sh` extracts the whole tarball, so the new lib ships automatically;
  `install.sh:964` already `chmod +x`es `lib/*.sh`.
- `install.sh:344-392` `ensure_data_root()` is deliberately **left alone** — it
  is a repair/refusal function that never creates links and runs before the lib
  is usable. Its shared literal is covered by the header comment above and by
  test G3.

### 3. `.aitask-scripts/aitask_init_data.sh` — `--link-worktree <dir>`

- Source the new lib; delete the local `ensure_symlinks()`; call
  `ait_ensure_data_symlinks "$PWD"` at its two existing call sites (L61, L106).
- Add a `--link-worktree <dir>` mode, handled before the existing flow.

**Guards — `<dir>` must be a *linked task worktree root*, not merely "inside the
repo and not the main root".** Every path below is canonicalized the same way on
both sides (`cd "$p" && pwd -P`); comparing a raw string against a git-returned
path silently fails on a symlinked checkout.

  1. `<dir>` exists and is a directory.
  2. `MAIN_ROOT` is derived **from `<dir>`** —
     `git -C "$dir" rev-parse --path-format=absolute --git-common-dir`, then
     `dirname` — the same idiom `aitask_task_worktree.sh:114-116` uses. Failure
     means `<dir>` is not inside a git repository at all.
  3. **`<dir>` is a worktree *root*:** canonical `<dir>` must equal canonical
     `git -C "$dir" rev-parse --show-toplevel`. **This check is load-bearing and
     checks 2 + 4 do not imply it** — an ordinary subdirectory of the primary
     (`.aitask-scripts/`, `website/`, any source dir) shares the primary's
     git-common-dir, so it resolves the same `MAIN_ROOT` and is trivially
     unequal to it. Without this check a mistyped path would plant
     `.aitask-data`, `aitasks` and `aiplans` symlinks into an arbitrary source
     directory. A *nested independent* repository is rejected by check 4
     instead: it resolves its own common dir, so it is its own `MAIN_ROOT`.
  4. canonical `<dir>` != canonical `MAIN_ROOT` — the main checkout uses the
     plain invocation.
  5. canonical `<dir>` != canonical `MAIN_ROOT/.aitask-data` — the data worktree
     is *also* a registered worktree root and therefore passes checks 3 and 4.
     Linking it would nest `.aitask-data/.aitask-data` inside the data branch.

  Each guard fails closed via `die` (exit 1, message on stderr naming the
  offending path and which condition it failed), creating nothing.

**Status tokens on stdout, exit 0** (extending the existing vocabulary):

  - `LEGACY_MODE` — `MAIN_ROOT/aitasks` is a real directory: task data lives on
    the code branch, so the worktree already has it. No-op.
  - `NOT_INITIALIZED` — `MAIN_ROOT/.aitask-data` carries no `.git`: the primary
    itself is not set up. No-op; `ait setup` repairs it.
  - `ALREADY_LINKED` — all three entries are already **exactly correct** (see
    below). Nothing was written.
  - `LINKED` — one or more entries were created or repaired.

**`ALREADY_LINKED` means correct, not merely present.** Existence-and-resolves
is too weak: a worktree reused across checkouts can carry
`.aitask-data -> /other/checkout/.aitask-data`, which resolves fine and would
silently point `./ait` and the whole suite at another repo's task data. Each
entry is validated against its required form, and a mismatch is **repaired**:

  | entry | required | wrong symlink target | not a symlink |
  |---|---|---|---|
  | `<wt>/.aitask-data` | symlink whose canonical target == canonical `MAIN_ROOT/.aitask-data` | repair | **refuse** |
  | `<wt>/aitasks` | symlink whose raw target is exactly `.aitask-data/aitasks` | repair | **refuse** |
  | `<wt>/aiplans` | symlink whose raw target is exactly `.aitask-data/aiplans` | repair | **refuse** |

**Two phases, and the split is the contract.** "Refuse with nothing else
written" is not achievable by a loop that decides per entry: a sequential
implementation can repair `.aitask-data`, then reach `aitasks`, find a real
directory, and `die` — leaving a partially rewritten worktree while claiming it
refused. `ait_link_worktree_data` must therefore:

  1. **Preflight (read-only).** Classify **all three** entries — absent /
     correct / wrong-target-symlink / non-symlink — touching nothing. If **any**
     entry is a non-symlink conflict, `die` naming every conflicting path (not
     just the first), having written nothing.
  2. **Apply.** Only once preflight passes, perform the `rm -f` / `ln -s`
     operations for the entries classified as wrong-target or absent, then
     report.

  Structure the code so this is enforced rather than remembered: preflight
  collects the planned operations into an array and the apply phase executes
  that array. There is no path from a conflict to a write.

  - *Repair* = `rm -f` the symlink and recreate it, then report `LINKED`. Each
    repair emits a `warn` on **stderr** naming the entry and the old target, so
    stdout stays a single parseable token.
  - *Refuse* = `die`. An entry that exists and is **not** a symlink (a real
    directory or file) is user state this helper does not own — the same
    posture as `install.sh:353` `ensure_data_root()`, which dies rather than
    unlinking anything it does not recognize. Never clobber a real directory:
    that is the one path that could destroy work.
  - A **dangling** symlink is a wrong target, not a refusal — it is repaired
    (this is what the existing `[[ -L x && ! -e x ]] && rm -f x` idiom already
    does for the primary).
  - The raw-string comparison for `aitasks` / `aiplans` is deliberate: it is the
    same literal `install.sh:353` recognizes, so this check and that one drift
    together or not at all.

- Update the header's `Output` / `Called by` blocks and the `--help` text.

### 4. `.aitask-scripts/aitask_setup.sh`

- Source the new lib beside `python_resolve.sh` / `github_release.sh` (L15-19).
- Replace Step 6's inline symlink subshell (L1625-1636) with
  `ait_ensure_data_symlinks "$project_dir"`. Behaviour is identical; covered by
  the existing `assert_symlink` cases in `tests/test_data_branch_setup.sh`
  (L426-427, L459-460).
- Add `setup_worktree_dirs_gitignore()`, modelled directly on
  `setup_gate_logs_gitignore()` (L2008-2035): one comment header, then the two
  rules `aiwork/` and `.aitask-crews/`, **each guarded independently** with
  `grep -qxF` so a project that already has one gets only the other. Commit with
  the same `git add .gitignore && git commit … || true` shape. Register the call
  beside its siblings in the call block at L3839-3852.

### 5. Skill wiring — `.claude/skills/task-workflow/SKILL.md`

In Step 7's **Deferred worktree fork**, insert a step after the reuse/cut
branches and immediately before "Work in the reused or newly cut directory"
(currently L495). It must run on **both** paths — a worktree created before this
change, or one whose links were removed, is repaired on reuse:

> - **Give the worktree its data layout.** A linked worktree checks out the code
>   branch only; `aitasks/` and `aiplans/` are gitignored symlinks that live in
>   the primary checkout, so a fresh worktree has neither. `./ait` run from
>   inside it then resolves `aitasks/` locally and finds nothing — `./ait git`
>   silently degrades to legacy mode — and four python suite modules fail with
>   `FileNotFoundError` on `aitasks/metadata/*.json`, which read as regressions
>   of *your* change. Create the layout now (idempotent, so run it on the reuse
>   path too), from the repo root, before you cd into the worktree:
>
>   ```bash
>   ./.aitask-scripts/aitask_init_data.sh --link-worktree "$worktree_path"
>   ```
>
>   Parse the single stdout line: `LINKED` / `ALREADY_LINKED` → continue.
>   `LEGACY_MODE` → this project keeps task data on the code branch, so the
>   worktree already has it; continue. `NOT_INITIALIZED` → the primary checkout
>   has no `.aitask-data` worktree; warn, say that `ait setup` repairs it, and
>   continue. A **non-zero exit is a refusal** — the path is not a linked
>   worktree root (an ordinary subdirectory, the main checkout, or the
>   `.aitask-data` worktree), or one of the three names already exists as a real
>   directory rather than a symlink. **Stop and report the message verbatim**;
>   do not implement in a tree whose data layout is unknown, and do not "fix" it
>   by deleting anything the helper refused to touch.

`$worktree_path` is bound to the reused (`$wt_path`) or newly cut path by the
branches above; the agent is still in the repo root at this point (Step 5:
"You are still in the repo root for Steps 6 and 7's pre-fork work").

Editing the authoring source is sufficient for every agent — Codex/OpenCode
variants auto-render from it and the change touches no `{% if agent %}` gate, so
**no cross-agent port task is warranted**.

### 6. Regenerate rendered artefacts (same commit)

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/procs/task-workflow/SKILL-$p.md
done
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
```

Only the three `-remote-` closures are git-tracked (`.claude`, `.agents/…-codex-`,
`.opencode`); `default`/`fast` refresh on disk but never appear in the diff.
Review the golden diff — it must contain only the inserted step.

### 7. Docs — `website/content/docs/workflows/parallel-development.md`

One sentence in "Git Worktrees for Isolation": the worktree is given the same
task-data symlinks as the primary checkout, so `ait` commands and the test suite
behave identically inside it. Current-state prose only, no version history.

---

## Tests

**G1 — `tests/test_init_data.sh`** (extends the existing 9 cases; the file's
`assert_symlink` / `assert_not_symlink` helpers and `setup_repo_with_remote`
scaffold are reused):

- 10. `--link-worktree` on a real task worktree creates all three entries, and a
  fixture file seeded on the data branch is readable as
  `<wt>/aitasks/metadata/<x>` — the exact `FileNotFoundError` class from the
  task report.
- 11. **Routing:** `[[ -f "<wt>/.aitask-data/.git" ]]` — the literal probe
  `_ait_detect_data_worktree()` runs, so the assertion is tied to the `ait git`
  misroute rather than to link existence alone.
- 12. Idempotent: second run prints `ALREADY_LINKED` and leaves the three link
  targets byte-identical.
- 13. Repairs a dangling link: pre-seed a broken `<wt>/aitasks` symlink, assert
  it is recreated and resolves.
- 14. **Stale `.aitask-data` target.** Build a *second* primary checkout with its
  own data branch and a distinguishable fixture, point `<wt>/.aitask-data` at
  **that** checkout's `.aitask-data`, then run `--link-worktree`. Assert:
  stdout `LINKED` (not `ALREADY_LINKED`), the link now canonicalizes to *this*
  `MAIN_ROOT/.aitask-data`, `<wt>/aitasks/metadata/<x>` reads **this** repo's
  fixture and not the other one, and stderr names the old target. Reading the
  wrong fixture is the discriminating assertion — link identity alone would
  pass even if the repair wrote the wrong root.
- 15. **Stale `aitasks` target.** Point `<wt>/aitasks` at a resolving path other
  than `.aitask-data/aitasks`; assert it is repaired to exactly that literal
  (`readlink` equality) and `LINKED` is reported.
- 15b. **Stale `aiplans` target — the symmetric case.** Same shape, with
  `aitasks` left correct and only `<wt>/aiplans` pointed at a resolving path
  other than `.aitask-data/aiplans`. Assert `LINKED` (not `ALREADY_LINKED`) and
  `readlink <wt>/aiplans` == `.aitask-data/aiplans`. Case 15 alone does not
  cover this: a validate-and-repair loop that only inspects the first element of
  `AIT_DATA_LINKS` passes 15 and every other case while leaving `aiplans`
  pointed at another tree. Both links must be probed independently, each with
  the other held correct, or the loop's second iteration is untested.
- 16. **Non-symlink entry is refused, not clobbered — and nothing else is
  written.** Create `<wt>/aitasks` as a real directory holding a file, and leave
  `.aitask-data` and `aiplans` **absent**. Assert non-zero exit; the directory
  and its file are byte-identical; and — the part that actually tests the
  preflight — `<wt>/.aitask-data` and `<wt>/aiplans` still do **not** exist.
  A sequential implementation creates `.aitask-data` first and fails here, so
  this case discriminates on the two-phase structure rather than on the refusal
  alone.
- 16b. **Conflict discovered on a later entry.** Same shape but with the
  conflict on `aiplans` (the last entry processed) and `.aitask-data` /
  `aitasks` stale-but-repairable. Assert both repairable entries are left with
  their **original stale targets** — proving preflight ran before any repair,
  not merely before the conflicting one.
- 17. **Refuses an ordinary subdirectory of the primary.** `mkdir <primary>/sub`
  → non-zero exit and **no** `.aitask-data` / `aitasks` / `aiplans` inside
  `sub`. This is the negative control for guard 3; without `--show-toplevel`
  the directory shares the primary's git-common-dir and passes every other
  guard.
- 18. Refuses the main root (non-zero exit, **and** nothing created).
- 19. Refuses `<MAIN_ROOT>/.aitask-data` — a registered worktree root that
  passes guards 3 and 4 (non-zero exit, no nested `.aitask-data`).
- 20. Refuses a directory outside any git repo (non-zero exit, no links).
- 21. Legacy-mode primary → `LEGACY_MODE`, exit 0, **no** links created
  (negative control: the no-op path must not fabricate a layout).
- 22. `--help` names `--link-worktree` and the new status tokens.

**G2 — `tests/test_data_branch_setup.sh`** (already sources
`aitask_setup.sh --source-only` at L123 and drives `SCRIPT_DIR` per test, so the
**real** function is exercised, not a replica):

- Run `setup_worktree_dirs_gitignore` in a scratch repo → `git check-ignore -q`
  matches `aiwork/t1_x/` and `.aitask-crews/crew-1/`.
- Negative control: a sibling path (`aiwork.md`, `aidocs/`) is **not** ignored.
- Idempotent: a second run adds no duplicate line (`grep -c '^aiwork/$'` is 1).
- Partial state: a `.gitignore` that already contains `.aitask-crews/` gains
  `aiwork/` only — proves the two guards are independent.

**G3 — link-form pin.** Assert `readlink <root>/aitasks` is exactly
`.aitask-data/aitasks`. This is the drift guard for the `install.sh:353`
coupling named in the lib header — if the helper ever changes the spelling,
`ensure_data_root()` starts `die`ing on fresh installs.

**G4 — teardown safety** (see `### Post-phase (risk mitigations)`).

### Post-phase (risk mitigations)

Runs after the deliverables above, before the verification sweep.

- **`worktree_teardown_preserves_primary_data`** — add a teardown-safety case
  family to `tests/test_task_worktree_helper.sh` (its `fresh_repo` /
  `run_helper` scaffold already builds temp repos with real `aiwork/tA`
  worktrees). Build a primary in branch mode with a fixture file on the data
  branch, cut a task worktree, run
  `aitask_init_data.sh --link-worktree aiwork/tA`, then tear the worktree down
  **twice over, once per removal path**:

  1. `git worktree remove aiwork/tA --force`
  2. the helper's forced fallback — `aitask_task_worktree.sh remove tA --force`,
     which reaches the `rm -rf "$target"` at `aitask_task_worktree.sh:346`

  After **each**, assert the primary's `.aitask-data` is still a live worktree
  and `.aitask-data/aitasks/<fixture>` still exists with its original content.
  Assert on the *contents*, not just directory existence — an `rm -rf` that
  descended the symlink would leave the directory and empty it.

  This is a positive control on a destructive path: seed the fixture and assert
  it is readable **before** the teardown too, so a test that passes because
  nothing was ever there is impossible.

---

## Verification

1. `bash tests/test_init_data.sh` — all cases pass.
2. `bash tests/test_data_branch_setup.sh` — pre-existing symlink assertions
   still pass after the Step 6 refactor, plus the new gitignore cases.
3. `bash tests/test_task_worktree_helper.sh` — teardown unaffected.
4. `bash tests/test_skill_render_task_workflow.sh` — goldens match.
5. `shellcheck .aitask-scripts/lib/data_symlinks.sh .aitask-scripts/aitask_init_data.sh .aitask-scripts/aitask_setup.sh`
6. `git check-ignore -v aiwork/` reports `.gitignore:<n>:aiwork/`.
7. **Full install flow** (required by `aidocs/framework/aitasks_extension_points.md`
   for any `aitask_setup.sh` change): `bash install.sh --dir /tmp/scratchXY` into
   a fresh dir, run `ait setup` there, then confirm `aitasks`/`aiplans` are
   symlinks and `.gitignore` carries both new rules. Helper-level unit tests do
   not substitute for this.
8. **End-to-end, once, by hand** — the claim the task actually makes:
   create a real task worktree, run `./.aitask-scripts/aitask_init_data.sh
   --link-worktree aiwork/<name>`, then from inside it run
   `bash tests/run_all_python_tests.sh` and confirm the last line reads
   `PYTHON SUITE: PASSED (runner=pytest, exit=0)` — specifically that
   `test_board_movement.py`, `test_profile_editor_shadow_tier.py` and
   `test_settings_brainstorm_descriptions.py` are green. Use `set -o pipefail`
   if piping. Also run `./ait ls 3` from inside the worktree.

   *This is deliberately not automated.* A suite run is ~4 minutes and would
   need a full repo copy; G1/G2 pin the mechanism, this pins the symptom once.

## Out of scope

- **AgentCrew worktrees** (`aitask_crew_init.sh:118`) need no data layout: they
  are orphan branches with an **empty tree** (`git mktree` at L115-117), carry
  no source or `ait`, and are seeded with `_crew_meta.yaml` / `_crew_status.yaml`
  only.
- **`install.sh`'s `ensure_data_root()`** — repair/refusal semantics, different
  contract; see §2.
- **`_ait_data_gitdir()`** (`task_utils.sh:46-55`) still returns empty inside a
  worktree, because it probes `.git/worktrees/-aitask-data` and `.git` is a file
  there. Effect: `assert_data_worktree_clean()` no-ops in a worktree — a
  documented fail-open ("No-op … when the data worktree git-dir is missing"),
  not a new one, and not worsened by this change. Noted here so the residual is
  recorded rather than assumed away.

## Risk

### Code-health risk: medium

- Converting `aitask_setup.sh` Step 6's inline symlink block onto the shared
  helper touches the **install flow**; a regression there breaks bootstrapping
  for every new project, and helper-level unit tests would not catch it
  (`install.sh` deletes `seed/` at the end of install). Bounded deliberately:
  `ait_ensure_data_symlinks` keeps the two inline copies' semantics exactly —
  all new validate-and-repair behaviour lives in `ait_link_worktree_data`, which
  the install path never calls. · severity: medium · → mitigation: Verification
  step 7 (fresh `install.sh` → `ait setup` scratch run)
- `--link-worktree`'s repair path **deletes and recreates symlinks** in a
  directory supplied by the caller. A guard that is too loose turns a mistyped
  path into writes inside a source tree; one that mishandles a non-symlink entry
  turns it into data loss. · severity: medium · → mitigation: tests 14-22 —
  every guard has a negative control asserting *nothing was written*, and the
  never-clobber-a-real-directory refusal is pinned by test 16
- The relative link target `.aitask-data/<name>` is recognized in **exactly**
  that spelling by `install.sh:353` `ensure_data_root()`, which `die`s on
  anything else. Centralizing the literal in the new lib creates a silent
  cross-file coupling: a future edit to the helper would break fresh installs
  with no local test failing. · severity: medium · → mitigation: test G3
  (link-form pin) plus the coupling comment in the lib header
- A `.aitask-data` **symlink inside a task worktree** is new topology. Teardown
  (`git worktree remove`, and the forced `rm -rf "$target"` at
  `aitask_task_worktree.sh:346`) is expected to unlink the symlink rather than
  descend it — but that is reasoned, not observed. If it is wrong, removing a
  task worktree destroys the shared data-branch worktree and every task and plan
  file in it. · severity: high · → mitigation: inline post-phase
  worktree_teardown_preserves_primary_data

### Goal-achievement risk: low

- The task asks for "a guard test that a worktree's suite run is green". The
  delivered automated guard is narrower (a readable `aitasks/metadata` fixture
  from inside the worktree, plus the `.aitask-data/.git` probe that drives
  branch-mode routing); the full-suite claim is verified once by hand rather
  than on every run, because a suite run is ~4 minutes and needs a full repo
  copy. · severity: low · → mitigation: Verification step 8 (one-off end-to-end
  suite run inside a linked worktree)

### Planned mitigations
- timing: post-phase | name: worktree_teardown_preserves_primary_data | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 3 (.aitask-data symlink inside a task worktree; teardown may descend it) | desc: Assert that removing a linked task worktree — via both `git worktree remove --force` and `aitask_task_worktree.sh remove --force` — leaves the primary's `.aitask-data` worktree and its task/plan file contents intact.

## Post-implementation

Step 9 (Post-Implementation) handles cleanup, archival and merge per
`task-workflow`.
