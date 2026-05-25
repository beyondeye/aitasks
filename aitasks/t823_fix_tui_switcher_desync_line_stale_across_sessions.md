---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui, bug]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-25 11:34
updated_at: 2026-05-25 11:48
---

## Symptom

When the TUI switcher overlay is open and the user cycles between tmux
sessions with Left/Right (e.g. between an `aitasks` and `aitasks_mobile`
session), the "desync with remote" status line at the top of the dialog
does NOT update to reflect the newly selected session's project — it
keeps showing whatever desync state was computed first.

## Root cause

`.aitask-scripts/lib/desync_state.py:45-46`:

```python
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
```

`repo_root()` derives the inspected worktree from the *script's own
location* (`__file__`), not from the process cwd. `snapshot()` at
line 158 then calls `repo_root()` and inspects that fixed path
regardless of how the script was invoked.

All callers that *want* per-project state pass `cwd=project_root` to
`subprocess.run(...)` — and are silently defeated by `repo_root()`:

- `.aitask-scripts/lib/tui_switcher.py:521-535` (`_fetch_desync_summary`)
- `.aitask-scripts/monitor/desync_summary.py:41-54` (`_fetch`)

Verified reproduction:

```
$ python3 .aitask-scripts/lib/desync_state.py snapshot --format lines
REF:main
... aitasks-specific REMOTE_CHANGED_PATH lines (.agents/skills/aitask-pickweb-...)

$ (cd /home/ddt/Work/aitasks_mobile && python3 \
    /home/ddt/Work/aitasks/.aitask-scripts/lib/desync_state.py \
    snapshot --format lines)
# Identical output — same aitasks-specific paths.
```

The TUI-switcher side already does the right thing: `_cycle_session`
re-calls `_render_desync_line(self._project_root_for_session(self._session))`
(tui_switcher.py:656), and the 30 s cache is keyed on `str(project_root)`
so different projects get fresh lookups. The cache is fine — the
subprocess just returns the wrong project's data.

## Fix

Change `repo_root()` to honor the invocation cwd:

```python
def repo_root() -> Path:
    return Path.cwd().resolve()
```

Optionally add a `--repo-root <path>` CLI flag (default: `Path.cwd()`)
for explicit-override callers. Either way, the subprocess invocations
in tui_switcher and monitor/desync_summary already set `cwd=project_root`
correctly and need no change.

### Compatibility check for other callers

- `.aitask-scripts/syncer/syncer_app.py` imports `from desync_state import
  snapshot` and runs in the project's own process. `ait syncer` runs
  with cwd at the project root, so `Path.cwd()` is correct.
- `.aitask-scripts/aitask_changelog.sh:73` runs the helper without
  changing cwd, so cwd is still the project root.
- `tests/test_desync_state.py` always copies the helper into the test
  project and runs with `cwd=project`, so `Path.cwd()` also resolves
  correctly.

## Acceptance criteria

1. Running `desync_state.py snapshot --format lines` with two different
   `cwd=` values (two distinct project roots) returns DIFFERENT output
   (verifies behaviour switches with cwd, not script location).
2. With the TUI switcher open across two real aitasks sessions whose
   projects have different remote states, Left/Right updates the
   "desync: …" line within one cache TTL.
3. Existing `tests/test_desync_state.py` still passes.
4. Add a regression test that copies the helper into a *different*
   directory than the test project root and invokes it with
   `cwd=<project_root>` — must report the project's state, not the
   helper directory's.

## Out of scope (notable side-finding)

`/home/ddt/Work/aitasks_mobile/.aitask-scripts/lib/` is missing
`desync_state.py` entirely (that install hasn't been upgraded since
2026-04-29, predating t713_1 which added the helper). That is a
user-side `ait upgrade` issue, not a framework bug, and is NOT covered
by this task.
