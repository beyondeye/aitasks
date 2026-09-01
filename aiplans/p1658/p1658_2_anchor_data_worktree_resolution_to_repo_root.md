---
Task: t1658_2_anchor_data_worktree_resolution_to_repo_root.md
Parent Task: aitasks/t1658_data_branch_metadata_push_strands_local_branch.md
Sibling Tasks: aitasks/t1658/t1658_1_converge_local_data_branch_after_offbranch_push.md
Base branch: main
Output branch: main
---

# t1658_2 — Anchor data-worktree resolution and the metadata entry scripts to the repo root

Covers parent **AC5**. The converge seam (AC1–AC4) belongs to t1658_1 — do not
change `task_data_converge()` or `verified_update_lib.sh` here beyond what the
entry scripts' `cd` requires.

## Context

`_ait_detect_data_worktree()` (`.aitask-scripts/lib/task_utils.sh:35`) resolves
`.aitask-data` **relative to the caller's cwd** and falls back to legacy mode
`"."` when it is absent. The fallback is silent and, by design, indistinguishable
from a genuine legacy-mode project.

Reproduced on this repo during t1658 exploration:

- run from `website/` → `task_sync` pulls **`main`**
- run from a crew worktree → pulls **`crew-brainstorm-1017`**

Both report success while the data branch is never reconciled. **None of the 15
scripts that perform data-branch git ops `cd` to the repo root** —
`aitask_archive`, `aitask_artifact`, `aitask_attach`, `aitask_create`,
`aitask_fold_mark`, `aitask_followup_backfill`, `aitask_gate_record`,
`aitask_gate`, `aitask_issue_import`, `aitask_lock`, `aitask_pick_own`,
`aitask_remote_drift_check`, `aitask_sync`, `aitask_update`, `aitask_zip_old`.
Task worktrees are safe (task-workflow Step 5 runs
`aitask_init_data.sh --link-worktree`); crew worktrees are **not** linked —
verified missing on both live crew worktrees, which sit at
`.aitask-crews/crew-brainstorm-*` and carry neither `ait` nor `aitasks/`.

Separately, `aitask_usage_update.sh` (`models_file_for_agent` at :158, the
`[[ -f "$models_file" ]] || die` at :242) and `aitask_verified_update.sh` (:172)
resolve `aitasks/metadata/models_<agent>.json` and `./ait` relative to cwd, so
from a subdirectory they die on "Model config not found" before any resolution
fix is reached.

## Decision already taken — do not re-litigate

**Anchor detection *and* both entry scripts** (user-selected over "narrow guard
in the metadata seam only" and "detection only"). A silent fallback to legacy
mode from inside a branch-mode project must not remain possible for any of the
15 scripts, and the two metadata scripts must additionally work from any cwd.

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_data_worktree_seam]` **Before touching any resolution code**,
   add characterization tests that pin today's behaviour, so the change is a
   demonstrated flip rather than an untested green:
   - Pin `_ait_detect_data_worktree`'s current answer for every shape: repo root
     of a branch-mode project (`.aitask-data`), a subdirectory of one (today
     `"."` — the bug), inside `.aitask-data` itself (today `"."`), a linked
     worktree with no `.aitask-data` of its own (today `"."` — the crew case),
     and a genuine legacy project (`"."`, correct). Existing
     `tests/test_task_git.sh` Tests 1–3 already cover the root and legacy rungs;
     extend rather than duplicate them.
   - Assert every `$_AIT_DATA_WORKTREE` consumer resolves the **same physical
     location** when the value is absolute rather than `.aitask-data`:
     `artifact_manifest.sh:34`, `attachment_meta.sh:34`, `attachment_lock.sh:31`,
     `artifact_backends/local.sh:18`, `aitask_sync.sh:436`, plus
     `_ait_data_gitdir` (`task_utils.sh:50`), whose relative
     `.git/worktrees/-aitask-data` fast path must fall through to its
     `git -C … rev-parse --absolute-git-dir` branch off-root.
   - Record the **current failure** of the two non-root entry-point invocations
     in step 4 below (they die with "Model config not found" today), so their
     post-fix pass is a real flip.
   - Sweep for callers that rely on the entry scripts' cwd-relative resolution
     before the `cd` changes their contract:
     `grep -rn 'aitask_usage_update.sh\|aitask_verified_update.sh' --include='*.sh' --include='*.md' --include='*.py' .`
     The known call sites are the `satisfaction-feedback.md` renders, which
     invoke them as `./.aitask-scripts/…` from the repo root — a no-op under the
     new anchoring. Report anything else before proceeding.

### 1. The resolution ladder in `.aitask-scripts/lib/task_utils.sh`

Replace `_ait_detect_data_worktree()`'s single cwd-relative probe with four rungs
(first hit wins; the result is still cached in `_AIT_DATA_WORKTREE`, and the
`[[ -n "$_AIT_DATA_WORKTREE" ]] && return` guard at the top is unchanged, so
tests that set the global directly still short-circuit detection):

1. `./.aitask-data/.git` (directory **or** file) → `.aitask-data`. Today's fast
   path — byte-identical behaviour when cwd is the repo root, which is every
   `./ait`-dispatched invocation.
2. `<toplevel>/.aitask-data/.git`, where
   `toplevel="$(git rev-parse --show-toplevel 2>/dev/null)"` → that absolute
   path. Covers `website/`, `tests/`, any subdirectory, and a task worktree's own
   `.aitask-data` symlink.
3. `<main>/.aitask-data/.git`, where `main` comes from **the canonical
   `ait_main_worktree_root`** in `lib/data_symlinks.sh:96` (sets
   `AIT_WT_MAIN_ROOT`) → that absolute path. Covers a linked worktree that was
   never `--link-worktree`d — the crew-worktree case. **Reuse that helper; do
   not reimplement `--git-common-dir` handling** — it already deals with
   submodule gitdirs, `--separate-git-dir` refusal, and canonicalization, and it
   derives everything from its `<dir>` argument so no ambient cwd can select a
   different repository.
4. Otherwise `"."` — now reachable only from a genuinely legacy-mode project.

Use the **uncanonicalized** `<root>/.aitask-data` spelling (not `pwd -P`), so a
task worktree's symlinked data dir keeps its friendly path in messages; git
follows the symlink either way.

`task_utils.sh` gains, alongside its existing sources:

```bash
# shellcheck source=data_symlinks.sh
source "${SCRIPT_DIR}/lib/data_symlinks.sh"
```

`data_symlinks.sh` sources only `terminal_compat.sh` and guards against
double-sourcing, so there is no cycle.

**Source-on-startup ↔ test-scaffold rule (`aidocs/framework/shell_conventions.md`):**
`setup_fake_aitask_repo()` in `tests/lib/test_scaffold.sh:13` must copy
`data_symlinks.sh` **in the same commit** — every scaffolded test that sources
`task_utils.sh` breaks otherwise. Add it beside the existing `yaml_utils.sh` /
`atomic_write.sh` copies, with a comment naming the reason.

### 2. Consumer safety — why an absolute value is safe

Verified by `grep -rn '_AIT_DATA_WORKTREE' .aitask-scripts/`: every consumer is
either `git -C "$_AIT_DATA_WORKTREE" …` (`task_utils.sh:65,76,198`) or a
`"$_AIT_DATA_WORKTREE/<suffix>"` path prefix (`artifact_manifest.sh:34`,
`attachment_meta.sh:34`, `attachment_lock.sh:31`,
`artifact_backends/local.sh:18`, `aitask_sync.sh:92-93,435-436`) — both correct
with an absolute value. The only equality tests are against `"."`
(`aitask_remote_drift_check.sh:131`, `aitask_sync.sh:92,435`,
`task_utils.sh:52,75,154,197`), and legacy still yields exactly `"."`. **No site
compares against the literal `.aitask-data`.** Re-run that grep during
implementation and fail loudly if a new comparison has appeared.

### 3. `ait_cd_repo_root` and the entry scripts

Add to `task_utils.sh`, immediately beside the ladder:

```bash
# Anchor the process to the repository root — the same rule `ait` applies
# (`cd "$AIT_DIR"`, ait:9) so relative paths like aitasks/metadata/... and ./ait
# resolve. Call it ONCE, early, from an ENTRY-POINT script only; never from a
# library, and never from a sourced helper.
ait_cd_repo_root() {
    local script_dir="${1:?ait_cd_repo_root: script dir required}"
    cd "$(dirname "$script_dir")" || die "Cannot cd to repo root from $script_dir"
}
```

Call it once at the top of both `aitask_usage_update.sh` and
`aitask_verified_update.sh`, after `SCRIPT_DIR` is computed and after the libs
are sourced (it lives in `task_utils.sh`):

```bash
ait_cd_repo_root "$SCRIPT_DIR"
```

No-op in every existing test — they already `cd` to the fixture root, whose
`.aitask-scripts` is the one they invoke.

### 4. Tests

`tests/test_task_git.sh` (already sources `aitask_setup.sh --source-only` for
`setup_data_branch`, which builds a real `.aitask-data` worktree — see its
Test 5) — the resolution rungs:

- from `<root>/website/` in a branch-mode project → resolves to the data
  worktree, not `"."` (rung 2);
- from a linked worktree created **without** `--link-worktree` → resolves to the
  main checkout's data worktree (rung 3);
- legacy project from a subdirectory → still `"."` (rung 4);
- existing Tests 1–3 and 5 pass unchanged (rung 1 and legacy).

**Real entry points from a non-root cwd.** The resolution tests alone cannot see
a missing, misplaced, or later-regressed `ait_cd_repo_root` — that is exactly the
gap this bullet closes. Build on **t1658_1's shared fixture**
`tests/lib/metadata_update_fixture.sh` :: `setup_branch_mode_metadata_repo`
(do not fork a second branch-mode fixture), and add to **both**
`tests/test_usage_update.sh` and `tests/test_verified_update.sh` — each script
has its own `main()` and its own `cd` call site, so both must be driven:

- launch the real script from `<root>/website/`, and again from an unrelated cwd
  (`/tmp`) via an absolute path;
- assert stdout is exactly `UPDATED:<agent>:<skill>:<value>` and the exit status
  is `0` — not the `Model config not found` die, and not
  `UPDATED_REMOTE_ONLY:`;
- assert local-ref convergence in the data worktree: the pushed commit is an
  ancestor of local `HEAD`, and `git rev-list --count HEAD..@{u}` is `0`.

If any new test body runs inside a `( … )` subshell, opt into the file-backed
counters (`assert_counters_init` / `assert_counters_load`) per CLAUDE.md.

### Post-phase (risk mitigations)

None for this child.

## Verification

```bash
bash tests/test_task_git.sh
bash tests/test_usage_update.sh
bash tests/test_verified_update.sh
bash tests/test_remote_drift_check.sh   # shares _ait_detect_data_worktree
bash tests/test_init_data.sh            # shares data_symlinks.sh
bash tests/test_task_push.sh            # shares task_utils.sh
bash tests/run_all_python_tests.sh      # the scaffold change reaches Python tests
shellcheck .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/aitask_verified_update.sh
```

Read only the last line of a test file's output for its verdict; for the Python
suite read the final `PYTHON SUITE: PASSED|FAILED` banner, and remember that
piping discards the exit status — use `set -o pipefail` or check
`${PIPESTATUS[0]}`.

Live check on this repo: from `website/`, run

```bash
../.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent
```

and confirm it prints `UPDATED:` and exits `0` — today it dies with "Model
config not found". Then from the repo root confirm
`./ait git rev-list --count HEAD..@{u}` is `0`.

Step 9 (Post-Implementation) covers cleanup, archival and merge.

## Risk

### Code-health risk: medium
- `_ait_detect_data_worktree()` is sourced by essentially every framework script and 15 of them perform data-branch git ops; rungs 2/3 return an **absolute** path where today's value is the relative `.aitask-data`, so a consumer assuming the relative spelling could silently target a different branch. The new `data_symlinks.sh` dependency also reaches every scaffolded test · severity: medium · → mitigation: inline pre-phase characterize_data_worktree_seam
- `aitask_usage_update.sh` / `aitask_verified_update.sh` gain a `cd`, changing their cwd contract for any caller relying on cwd-relative resolution · severity: low · → mitigation: inline pre-phase characterize_data_worktree_seam

### Goal-achievement risk: low
- None identified beyond the above: the ladder's four rungs are each directly testable, and the entry-point tests drive the real scripts rather than the resolution function alone.

### Planned mitigations
- timing: pre-phase | name: characterize_data_worktree_seam | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: both code-health risks | desc: before touching the resolution, pin today's `_ait_detect_data_worktree` answer for every shape (repo root, subdirectory, inside `.aitask-data`, linked worktree, legacy), assert every `$_AIT_DATA_WORKTREE` consumer plus `_ait_data_gitdir` still resolves the same physical location under an absolute value, record the current failure of the two non-root entry-point invocations so the fix is a demonstrated flip, and sweep for callers relying on the entry scripts' cwd-relative resolution
