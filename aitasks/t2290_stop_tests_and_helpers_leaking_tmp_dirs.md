---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tests, test_infrastructure, tmp_cleanup]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-13 00:43
updated_at: 2026-11-13 00:59
---

## Problem

`/tmp` on this machine is a tmpfs capped at 32G **and 1,048,576 inodes**. It
filled up twice in a few days. The failure is most likely inode exhaustion
(ENOSPC while `df -h` still shows free bytes). On 2026-11-13, 11 days after
boot, it stood at 80% of bytes and 86% of inodes. Most of the volume comes from
other sources (Claude Code session scratchpads, headless-Chrome profiles from a
sibling repo; those have their own tasks). But the aitasks test suite and some
helpers also leave directories behind on every run. Fix those here.

## Measured leftovers (2026-11-13, owner = this user, all since the 2026-11-02 boot)

| prefix | count | size | source |
|---|---|---|---|
| `roadmap_run_*` | 972 | ~2MB, 972 inodes | **confirmed:** `tests/test_roadmap_run.py:119`, where `_RunHarness.setUp` does `tempfile.mkdtemp(prefix="roadmap_run_")` and `tearDown` (line ~124) never removes it |
| `tmp.*` | 242 | ~1.3G, ~55k inodes | bare `mktemp -d`. Not attributed yet. Contents seen: `admit*` fixtures, Android `classes*.dex`. Some are from other repos or from agents. Attribute before fixing |
| `ait_txn_snap_*` | 69 | small | `.aitask-scripts/lib/txn_snapshot.sh:112`. Cleanup at :228 runs only on the normal path |
| `ait_assert_counters_*` | 58 | small | `tests/lib/asserts.sh:65`. `rm` at ~:88 skipped when a test is killed or exits early |
| `ait_ril_pending_*` | 28 | small | `.aitask-scripts/lib/release_issue_ledger.sh:687`, EXIT-trap cleanup. Find which path skips it |
| `t79_2_driver*`, `t45_*` | 540 / 129 | ~8MB / ~?MB | **not found** in any repo's tracked source. Probably ad-hoc agent driver scripts. Confirm and drop if they don't come from aitasks |

Heuristic, unverified: of 223 `tests/*.sh` files that use `mktemp -d`, about 114
contain no `trap … rm -rf` / `trap … cleanup` line. Some of those clean up
inline, which is fine unless a test aborts. Treat this as a list to audit, not
as 114 bugs.

## Scope

1. Fix the confirmed leak in `test_roadmap_run.py` (`addCleanup(shutil.rmtree, …)`).
2. Attribute `tmp.*` / `t45_*` / `t79_2_driver*`: run the suites under a private
   `TMPDIR` and diff what's left. Fix the aitasks-owned producers; list the rest
   as not-ours.
3. Helpers (`txn_snapshot.sh`, `release_issue_ledger.sh`, `asserts.sh`): make
   cleanup cover error and signal exits, not only the success path.
4. **Guard so it stays fixed:** `tests/run_all_python_tests.sh`, and a wrapper
   for shell tests if practical, run under a per-run `TMPDIR`, report any leftovers
   by name at the end, then remove it. Decide whether leftovers fail the run or
   only warn. Warn-first is probably right until step 2 is done. Note that the
   pytest-xdist lane has several workers, and ~39 modules chdir.

## Out of scope

- Claude Code's own session scratchpads (`/tmp/claude-<uid>/…`): covered by the
  local cleanup-skill task.
- Sibling repos (animeless smoke.js Chrome profiles; aitasks_go scratch repo
  exports): each has its own task in its own repo.
