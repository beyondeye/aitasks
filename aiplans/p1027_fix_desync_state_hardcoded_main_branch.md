---
Task: t1027_fix_desync_state_hardcoded_main_branch.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# Plan: Fix desync_state.py + syncer hardcoded `main` primary branch (t1027)

## Context

In a repo whose primary branch is `master` (e.g. the sibling `aitasks_mobile`
project), `desync_state.py snapshot` reports `main: missing_remote` even when
the repo is fully in sync. The cause: `snapshot_ref()` hardcodes
`local_ref = "main"` / `remote_ref = "origin/main"` for the logical `"main"`
ref; in a `master`-default repo `origin/main` does not exist, so the status
falls through to `missing_remote`.

**Blast-radius finding (from plan review):** fixing only the *status display*
is insufficient. The syncer TUI (`syncer/syncer_app.py`) consumes the same
snapshot and would show the row as healthy, but its **pull/push actions remain
hardcoded to `main`** and would refuse to act or push the wrong ref in a
master-default repo:
- `_main_pull_worker` (line 383) guards on `head_name != "main"`.
- `_main_push_worker` (line 423) runs `git push origin main:main`.

So this task fixes both the producer (`desync_state.py`) **and** the consumer
that performs git operations (`syncer_app.py`), keeping `"main"` as the
**logical / user-facing** row name (no CLI break) while resolving the *physical*
branch dynamically.

## Approach

### Part A — `.aitask-scripts/lib/desync_state.py`

**A1. Add `detect_primary_branch(worktree: Path) -> str`** (next to
`ref_exists` / `has_remote`; reuses `run_git` + `ref_exists`). Resolution order:

1. `git symbolic-ref --quiet --short refs/remotes/origin/HEAD` → strip a leading
   `origin/`; return the remainder if non-empty. Authoritative for any clone
   (master, trunk, develop, …) since it reflects the real remote default.
2. Local-branch probe: first of `main`, then `master`, whose local ref exists.
3. Fallback: literal `"main"`.

```python
def detect_primary_branch(worktree: Path) -> str:
    proc = run_git(worktree, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
    if proc.returncode == 0:
        head = proc.stdout.strip()
        if head.startswith("origin/"):
            head = head[len("origin/"):]
        if head:
            return head
    for candidate in ("main", "master"):
        if ref_exists(worktree, candidate):
            return candidate
    return "main"
```

**A2. Use it in `snapshot_ref` for the `"main"` case** (lines 103-107):

```python
    if name == "main":
        worktree = root
        worktree_label = "."
        local_ref = detect_primary_branch(worktree)
        remote_ref = f"origin/{local_ref}"
```

`worktree` here is always `root` (the repo cwd, always exists), so calling
`detect_primary_branch` before the `worktree.exists()` check is safe — no
`FileNotFoundError` risk. The `aitask-data` path and the logical CLI surface
(`--ref` choices line 215, default ref list line 157) are untouched.

**A3. Add `physical_main_branch(snapshot: dict) -> str`** — a tiny pure helper,
also in `desync_state.py` (no textual dependency, co-located with the RefState
producer, importable by both the syncer and the test without pulling in
Textual):

```python
def physical_main_branch(snapshot: dict) -> str:
    """Physical branch backing the logical 'main' row (local_ref, else 'main')."""
    for ref in snapshot.get("refs", []):
        if ref.get("name") == "main":
            return ref.get("local_ref") or "main"
    return "main"
```

### Part B — `.aitask-scripts/syncer/syncer_app.py`

Import `physical_main_branch` alongside the existing `from desync_state import
snapshot` (line 22). The syncer already stores `self._last_snapshot`, so the
physical branch is derivable with no extra git calls.

**B1. `_main_pull_worker`** — replace the hardcoded guard:
```python
    branch = physical_main_branch(self._last_snapshot)
    ...
    if head_name != branch:
        ... f"Switch to {branch} to pull (currently on {head_name})."
```
(`git pull --ff-only` takes no branch arg — it pulls the current branch's
upstream — so only the guard is hardcoded.)

**B2. `_main_push_worker`** — derive the refspec:
```python
    branch = physical_main_branch(self._last_snapshot)
    rc, out, err = self._git(["push", "origin", f"{branch}:{branch}"], cwd)
    cmd = f"git -C <main> push origin {branch}:{branch}"
```

The logical row key `"main"` (`self._row_keys`, `check_action`, `_find_ref("main")`,
table row) is unchanged — it stays the user-facing label.

### Display label — unchanged

`_format_desync_lines` (tui_switcher.py) and `emit_text` key off `ref['name']`
(stays `"main"`). A synced master-default repo now renders `main: up to date` —
exactly the task's stated expected output. No change to `tui_switcher.py`.

## Tests

### `tests/test_desync_state.py`
- `make_master_project()` fixture (mirrors `make_main_project` but checks out
  `master` and runs `git remote set-head origin master`).
- `test_master_default_repo_reports_up_to_date` covering **both** detection
  paths: (a) origin/HEAD set → `local_ref == "master"`, `remote_ref ==
  "origin/master"`, `status == "ok"`, text `main: up to date`; (b) after
  `git symbolic-ref --delete refs/remotes/origin/HEAD`, re-snapshot still
  resolves `local_ref == "master"` via the local-branch probe.
- `test_physical_main_branch` (pure-unit): master snapshot → `"master"`,
  main snapshot → `"main"`, missing `main` row → `"main"`, empty/None
  `local_ref` → `"main"`.

All existing tests stay green by construction: `make_main_project` has no
origin/HEAD set, so the probe resolves `main`; the missing_local /
missing_remote / no_remote / fetch_error fixtures keep `local_ref = "main"`.

### Syncer pull/push behavior
The pull/push workers are Textual `@work(thread=True)` methods that wrap
`self._git(...)` + `self.call_from_thread(...)`, which are impractical to drive
without a live app. The branch-derivation seam they depend on is
`physical_main_branch`, which is fully unit-tested above; B1/B2 are thin
wrappers that feed its result into the git command. The push refspec string
construction (`f"{branch}:{branch}"`) is asserted via the helper test. (Honest
scope note: the thread bodies themselves are not directly exercised — the
testable decision logic is extracted into the pure helper.)

## Scope decision: `base_branch` profile lookup omitted (explicit)

The task lists reading the profile's `base_branch` as an **optional** step. It
is deliberately omitted, for two reasons:
1. **Ill-defined coupling.** `base_branch` is a per-*profile* key resolved at
   skill-runtime; there is no single "active base_branch" a standalone git
   helper can read (`base_branch` is only consumed in `profile_editor.py` and
   `aitask_pr_import.sh`, both skill-runtime contexts). Wiring profile resolution
   into a lean helper that today only shells out to `git` adds real coupling.
2. **origin/HEAD is strictly better and the residual gap is inert.** For any
   clone, `origin/HEAD` reflects the true remote default (trunk/develop/master)
   — more authoritative than `base_branch`. The only gap is a repo with a remote
   but *unset* origin/HEAD *and* a non-main/master default — which requires a
   manual `git remote add` (not a clone). And for a repo with **no** remote,
   `snapshot_ref` returns `no_remote` before branch detection matters, so the
   probe's main→master bias has no effect on output. If a real
   trunk/develop-with-manual-remote case appears, `base_branch` can slot in as
   resolution step 1.5 without touching callers.

## Out of scope — separate follow-up candidates (logged, not fixed here)

These are real but live in unrelated scripts; t1027 is scoped to the
desync/syncer surface. Will be recorded in Final Implementation Notes (and
offered as a follow-up task at Step 8b):
- `aitask_plan_externalize.sh:307` — always emits `Base branch: main` in plan
  metadata headers (plan-externalization concern, separate feature).
- `aitask_contribute.sh:448` — `git diff --name-only main` in clone/project
  contribution mode (contribution feature, separate).
- `create_new_release.sh:30` — release script hardwired to `main`. This repo
  (aitasks framework) is itself main-default and this is a root-level release
  tool, not part of distributed `.aitask-scripts/`; likely intentional. Noted,
  not recommended for change.

## Risk

### Code-health risk: medium
- Touches the syncer's git **write** path (`push origin <branch>:<branch>`).
  The change is small and the refspec derives from snapshot data, but a wrong
  branch resolution would push the wrong ref. Mitigated by the
  `physical_main_branch` unit tests and the origin/HEAD-authoritative
  resolution. · severity: medium · → mitigation: covered by tests (no separate task)
- `desync_state.py` change itself is contained (one pure helper + a two-line
  edit, no new imports, aitask-data path untouched). · severity: low

### Goal-achievement risk: low
- The fix produces the task's stated expected output and extends correctness to
  the syncer actions the status row implies are safe; both detection paths and
  the resolution seam are tested. · severity: low · → mitigation: none

No before/after mitigation **tasks** are warranted — the medium code-health risk
is addressed in-task by the unit tests, not by a follow-up.

## Verification

1. `python3 -m unittest tests.test_desync_state -v` — new + existing pass.
2. Manual cross-check in a master-default checkout:
   `python3 .aitask-scripts/lib/desync_state.py snapshot --format text`
   → `main: up to date` (not `main: missing remote ref`).
3. `shellcheck` is N/A (Python changes); confirm syncer still imports cleanly:
   `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import syncer_app"`
   (from repo root) does not error on the new import.

## Step 9 (Post-Implementation)

Profile 'fast', current branch — no worktree/merge. After review approval,
commit code (`bug: ... (t1027)`) and run `./.aitask-scripts/aitask_archive.sh 1027`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned.
  - `desync_state.py`: added `detect_primary_branch(worktree)` (origin/HEAD
    symbolic-ref → local `main`→`master` probe → `"main"` fallback) and the pure
    `physical_main_branch(snapshot)` helper; `snapshot_ref` now sets
    `local_ref = detect_primary_branch(worktree)` / `remote_ref =
    f"origin/{local_ref}"` for the logical `"main"` ref.
  - `syncer_app.py`: imported `physical_main_branch`; `_main_pull_worker` guards
    on the resolved branch and `_main_push_worker` pushes `f"{branch}:{branch}"`.
  - `test_desync_state.py`: `make_master_project` fixture +
    `test_master_default_repo_reports_up_to_date` (both detection paths) +
    `test_physical_main_branch` unit test.
- **Deviations from plan:** None.
- **Issues encountered:** None. All 8 desync tests pass; existing 5 stay green;
  `test_sync_action_runner` (18) green; `syncer_app` imports cleanly with the new
  symbol; live snapshot on this main-default repo still reports `main` correctly.
- **Key decisions:** Kept `"main"` as the logical row/CLI label (no display
  change to `tui_switcher.py`). Deliberately omitted the optional `base_branch`
  profile lookup — `base_branch` is a per-profile, skill-runtime key with no
  generic accessor for a standalone git helper, and `origin/HEAD` is the more
  authoritative source; the residual gap (remote present but origin/HEAD unset
  and a non-main/master default) is inert because remote-less repos report
  `no_remote` before branch detection matters.
- **Upstream defects identified:** None. (Three *related* hardcoded-`main`
  references exist in unrelated scripts but are pre-existing design choices in
  separate features, not defects seeding this symptom: `aitask_plan_externalize.sh:307`
  always emits `Base branch: main` in plan headers; `aitask_contribute.sh:448`
  uses `git diff --name-only main` in clone/project contribution mode;
  `create_new_release.sh:30` hardwires releases to `main` — this repo is itself
  main-default so likely intentional. These are out of scope for t1027 — a
  follow-up could generalize plan-externalize/contribute for master-default
  repos if needed.)
