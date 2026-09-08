---
priority: medium
effort: medium
depends: [1725_1]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1599
followup_kind: verification_failure
created_at: 2026-09-08 17:16
updated_at: 2026-09-08 17:16
---

## Failed verification item from t1725_1

> Run the full suite without piping away the exit status (`set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -20`); expect `PYTHON SUITE: PASSED`, and note whether the parallel (pytest+xdist) or serial unittest lane ran — t1729 was verified on the serial lane only.

### Source

- **Manual-verification task:** `aitasks/t1737_verify_macos_fixes_on_linux.md` (item #1)
- **Origin feature task:** t1725_1
- **Origin archived plan:** `aiplans/archived/p1725/p1725_1_abort_conflicted_pull_rebase_in_task_utils.md`

### Commits that introduced the failing behavior

- 42ee07791 bug: Abort a conflicted pull --rebase, but only ever our own (t1725_1)

### Files touched by those commits

- .aitask-scripts/aitask_pick_own.sh
- .aitask-scripts/lib/task_utils.sh
- tests/lib/test_scaffold.sh
- tests/test_task_push.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1737 item #1.

## Measured evidence (t1737, Linux) — this is NOT a t1729 defect

The suite verdict was `PYTHON SUITE: FAILED (runner=pytest, exit=1)` with exactly
**one** failing test out of 7035 passed / 2 skipped, plus 11 serial-carve-out
tests all passing:

```
FAILED tests/test_desync_state.py::DesyncStateTests::
       test_changelog_warns_for_data_desync_and_ignores_bad_helper_output
E  AssertionError: Command failed in /tmp/tmpt2yk58kz/project:
   bash .aitask-scripts/aitask_changelog.sh --gather
E  stderr=…/.aitask-scripts/lib/task_utils.sh: line 31:
        …/.aitask-scripts/lib/stale_lock.sh: No such file or directory
```

**Attribution — the origin is t1725_1 (42ee07791), not t1729.** t1729's commit
`ce3a10af3` touches none of `tests/test_desync_state.py`, `task_utils.sh`, or
`stale_lock.sh`.

`42ee07791` added `source "${SCRIPT_DIR}/lib/stale_lock.sh"` to
`.aitask-scripts/lib/task_utils.sh:31` and correctly updated the **shared**
scaffold (`tests/lib/test_scaffold.sh:59`, +7 lines) — but
`tests/test_desync_state.py` keeps its **own private copy list** at line 60:

```python
for name in ["desync_state.py", "task_utils.sh", "terminal_compat.sh",
             "python_resolve.sh", "archive_utils.sh", "yaml_utils.sh",
             "data_symlinks.sh"]:
```

`stale_lock.sh` is missing from it, so the fixture project it builds cannot
source what `task_utils.sh` now requires at startup. The fixture's own comment
(lines 53–58) warns that it keeps a separate list and must be kept in step — the
warning was there and was not acted on.

This is the "source-on-startup ↔ test-scaffold rule" in
`aidocs/framework/shell_conventions.md`.

**Platform-agnostic.** Nothing here is Linux-specific; it fails identically on
macOS. It did not surface during t1729 because t1729 ran the **serial** unittest
lane on a tree that predates 42ee07791.

**Fix:** add `"stale_lock.sh"` to the list at `tests/test_desync_state.py:60`.
Then sweep for any other fixture carrying a private copy list that has drifted
from `task_utils.sh`'s startup source chain — a per-fixture list is the recurring
hazard here, and a shared helper would remove the class.

**Consequence for t1737's headline claim:** every one of the six modules t1729
touched passes individually and inside the suite; this single failure is
independently attributable and does not bear on t1729's Linux-invariance
argument.
