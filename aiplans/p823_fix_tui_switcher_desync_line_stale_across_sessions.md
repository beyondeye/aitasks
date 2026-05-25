---
Task: t823_fix_tui_switcher_desync_line_stale_across_sessions.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Fix TUI switcher desync line stale across sessions (t823)

## Context

When the TUI switcher overlay is open and the user cycles left/right between
two aitasks tmux sessions (e.g. `aitasks` ↔ `aitasks_mobile`), the
`#switcher_desync` line at the top of the dialog never updates to the newly
selected session's project — it shows whichever repo's state was computed
first, until the cache expires (then it shows the same wrong data again).

Root cause is **not** in the switcher. `tui_switcher.py:_cycle_session`
already re-calls `_render_desync_line` with the selected session's project
root (line 656), and the 30 s class-level cache `_desync_cache` is keyed on
`str(project_root)` so different projects don't collide. The defect is in
the helper they shell out to:

```python
# .aitask-scripts/lib/desync_state.py:45-46
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
```

`repo_root()` derives the inspected worktree from the *script's own
on-disk location*, not from the process cwd. `snapshot()` at line 158
calls `repo_root()` and inspects that fixed path regardless of how the
script was invoked. All callers that *want* per-project state pass
`cwd=project_root` to `subprocess.run(...)` and are silently defeated:

- `.aitask-scripts/lib/tui_switcher.py:521-535` (`_fetch_desync_summary`)
- `.aitask-scripts/monitor/desync_summary.py:41-54` (`_fetch`)

Reproduction (already verified during exploration): running the helper
with `cwd=/home/ddt/Work/aitasks_mobile` returns identical output to
running it with `cwd=/home/ddt/Work/aitasks`, including aitasks-only
`REMOTE_CHANGED_PATH:.agents/skills/aitask-pickweb-...` lines.

Tests pass today only because `tests/test_desync_state.py` always **copies**
the helper into the per-test project via `copy_helper()` and runs with
`cwd=project` — so `Path(__file__).parents[2]` coincidentally resolves to
the project root in that scaffold.

## Fix

Single-line change in `desync_state.py`, plus a regression test that
exposes the bug without relying on the copy-helper-then-cd scaffold.

### 1. `.aitask-scripts/lib/desync_state.py:45-46` — honor cwd

Change:

```python
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
```

to:

```python
def repo_root() -> Path:
    return Path.cwd().resolve()
```

No other source changes are needed: every existing caller already either
sets `cwd=project_root` on the subprocess (`tui_switcher.py:528`,
`monitor/desync_summary.py:47`) or runs from the project's cwd
in-process (`syncer/syncer_app.py` imports `snapshot` directly; `ait
syncer` runs with cwd at the project root) or invokes the script from the
project's cwd (`aitask_changelog.sh:73`).

### 2. `tests/test_desync_state.py` — regression test

Add one new test `test_repo_root_follows_cwd_not_helper_location` that
defeats the copy-helper-coincidence: install the helper in one directory,
invoke it with `cwd` of a *separate* project root, and assert the output
reflects the cwd project — not the helper's parent.

Sketch (uses existing helpers `git`, `config_identity`, `make_main_project`):

```python
def test_repo_root_follows_cwd_not_helper_location(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Two independent projects with distinct remote states.
        project_a, origin_a = make_main_project(root / "a")
        project_b, origin_b = make_main_project(root / "b")

        # Make project_a remote ahead by 1 (so its REMOTE_CHANGED_PATH
        # is distinctive).
        other_a = root / "a-other"
        git(root, "clone", "--quiet", str(origin_a), str(other_a))
        config_identity(other_a)
        (other_a / "a_only.txt").write_text("a\n", encoding="utf-8")
        git(other_a, "add", "a_only.txt")
        git(other_a, "commit", "--quiet", "-m", "a remote change")
        git(other_a, "push", "--quiet", "origin", "main")

        # Place the helper inside project_a's lib dir (the legacy
        # path Path(__file__).parents[2] would point at) — but invoke
        # it with cwd=project_b.
        helper_in_a = project_a / ".aitask-scripts" / "lib" / "desync_state.py"
        self.assertTrue(helper_in_a.is_file())  # copy_helper ran in make_main_project

        data = json.loads(run(
            ["python3", str(helper_in_a), "snapshot", "--ref", "main",
             "--fetch", "--json"],
            cwd=project_b,
        ).stdout)
        ref = data["refs"][0]
        # If repo_root() honored cwd: project_b has no remote drift → behind=0.
        # If repo_root() used __file__: would inspect project_a → behind=1
        # and remote_changed_paths would include "a_only.txt".
        self.assertEqual(ref["behind"], 0)
        self.assertNotIn("a_only.txt", ref["remote_changed_paths"])
```

This is the canonical "helper-location ≠ cwd" scenario. Without the fix
it fails with `behind=1`; with the fix it passes.

### 3. Out of scope — explicitly NOT touched

- The user's secondary observation that
  `/home/ddt/Work/aitasks_mobile/.aitask-scripts/lib/` is stale (missing
  `desync_state.py` entirely, last updated 2026-04-29) is a per-install
  upgrade concern, not a framework bug. The user-side resolution is
  `ait upgrade` (or re-running `ait setup`) inside that project. The task
  description already calls this out as out of scope.
- No changes to `tui_switcher.py`, `monitor/desync_summary.py`,
  `syncer_app.py`, `aitask_changelog.sh`, or any caller. Their existing
  `cwd=` plumbing becomes load-bearing instead of cosmetic.
- No new CLI flag (`--repo-root`). `Path.cwd()` is sufficient for every
  current caller; adding a flag is YAGNI.

## Verification

1. Run the existing test suite to confirm no regression:
   ```bash
   python3 -m unittest tests.test_desync_state -v
   ```
   All previously-passing tests must still pass (the copy-helper-then-cd
   scaffold continues to work because `Path.cwd()` in the subprocess
   equals the test project root).

2. Run the new regression test specifically:
   ```bash
   python3 -m unittest tests.test_desync_state.DesyncStateTests.test_repo_root_follows_cwd_not_helper_location -v
   ```
   Must pass after the one-line fix.

3. Smoke check against the real repos that surfaced the bug:
   ```bash
   python3 /home/ddt/Work/aitasks/.aitask-scripts/lib/desync_state.py snapshot --format lines
   (cd /home/ddt/Work/aitasks_mobile \
     && python3 /home/ddt/Work/aitasks/.aitask-scripts/lib/desync_state.py snapshot --format lines)
   ```
   Outputs MUST differ (the first reports aitasks state; the second
   reports aitasks_mobile state — or "missing_remote" / "missing_local"
   if aitasks_mobile's local main isn't set up that way, but in any
   case not the aitasks-specific `.agents/skills/aitask-pickweb-...`
   path list).

4. Lint pass (shell scripts only; no new shell touched, but standard hygiene):
   ```bash
   shellcheck .aitask-scripts/aitask_*.sh
   ```

5. Manual TUI verification is **out of scope** for this task because
   reproducing it end-to-end requires the user's stale aitasks_mobile
   install to first be upgraded (so the script exists). The unit-test
   regression in step 2 is the load-bearing verification — it proves
   the bug class can no longer regress regardless of which project the
   switcher is invoked from. A separate manual-verification follow-up
   task should NOT be created.

## Step 9 — Post-Implementation

Standard task-workflow Step 9 cleanup:
- Working on the current branch (profile 'fast', no worktree).
- No build verification configured (`verify_build` absent from
  `aitasks/metadata/project_config.yaml`).
- `./.aitask-scripts/aitask_archive.sh 823` to archive the task.
- `./ait git push` after archival.
