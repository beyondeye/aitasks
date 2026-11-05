---
Task: t2207_fix_harvest_close_keydispatch_root_realpath.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: canonicalize the KeyDispatchTests fixture root (t2207)

## Context

`tests/test_monitor_sitrep_harvest_close.py` `KeyDispatchTests.setUp` builds
`self.root = Path(self._tmp.name) / "repo"` without resolving symlinks. The apps
dispatch `h` / `S` with a root canonicalized through `agent_marks.mark_key`
(realpath). On macOS the tempdir lives under `/var`, which is a symlink to
`/private/var`, so the dispatched root reads `/private/var/…/repo` while the
expectation is `str(self.root)` = `/var/…/repo`. Result: 4 subtest failures
(`test_monitor_h_and_S_act_on_the_focused_card`,
`test_minimonitor_h_and_S_act_on_the_followed_agent`, keys h and S) on every
macOS run. Pre-fix control already run this session: `Ran 2 tests … FAILED
(failures=4)`, diffs exactly `/private/var` vs `/var`.

This is a fixture defect, not a product defect: the product correctly
canonicalizes. The sibling fixture `SitrepNowCounterTests` (line 779) already
uses `os.path.realpath(self._tmp.name)`.

## Change

Single file: `tests/test_monitor_sitrep_harvest_close.py`, `KeyDispatchTests.setUp`
(~line 985):

```python
self.root = Path(os.path.realpath(self._tmp.name)) / "repo"
```

`os` is already imported (line 29). Keep both assertions strict — expected
values stay `str(self.root)`; do not loosen to accept either spelling.
`self.root` flows into `_KeyMonitor(self.root)` (session→project mapping) and
`cls(project_root=self.root)`, so canonicalizing it at the source makes the
mapping, the app's project root, and the expectation all agree.
The `marks.json` path (`Path(self._tmp.name) / "marks.json"`) is unrelated to
the asserted values and stays as is.

## Verification

1. `~/.aitask/venv/bin/python tests/test_monitor_sitrep_harvest_close.py KeyDispatchTests`
   → `OK` (control was `FAILED (failures=4)`).
2. Whole module: `~/.aitask/venv/bin/python tests/test_monitor_sitrep_harvest_close.py`
   → `Ran 66 tests … OK`.

## Step 9

Post-implementation: commit (`test: … (t2207)`), archive task and plan per
task-workflow Step 9 (current-branch mode, no merge).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `tests/test_monitor_sitrep_harvest_close.py` `KeyDispatchTests.setUp` now builds `self.root = Path(os.path.realpath(self._tmp.name)) / "repo"`, mirroring `SitrepNowCounterTests` (line 779). Assertions unchanged and strict (`str(self.root)`).
- **Deviations from plan:** Commit subject uses `bug:` (the task's `issue_type`), not the `test:` the plan's Step 9 note suggested — the commit convention keys on `issue_type`.
- **Issues encountered:** None. Pre-fix control (venv interpreter): `KeyDispatchTests` → `Ran 2 tests … FAILED (failures=4)`, diffs exactly `/private/var/…` vs `/var/…`. Post-fix: `KeyDispatchTests` → `OK`; whole module → `Ran 66 tests … OK`.
- **Key decisions:** Canonicalize at the fixture source rather than at the assertion, so the `_KeyMonitor` session→project mapping, the app's `project_root`, and the expectation all share one spelling. The `marks.json` tempdir path is not asserted on and was left as is.
- **Upstream defects identified:** None
