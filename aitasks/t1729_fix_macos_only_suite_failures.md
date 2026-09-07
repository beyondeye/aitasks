---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-07 18:16
updated_at: 2026-09-07 18:23
---

## Origin

Spawned from t1705_4 during Step 8b review. All three defects below are
**pre-existing**: each was verified to fail identically with t1705_4's changes
stashed (`git stash -u`), so none is a regression from that task. They are the
entire non-green residue of `bash tests/run_all_python_tests.sh` on macOS —
6840 tests, 3 failures / 6 errors, all in these four modules.

## Upstream defect

- `tests/test_agent_keys.py:43 — shutil.copy2 of /bin/sleep raises
  PermissionError (chflags) under macOS SIP, erroring 5 tests` (same helper
  shape in `tests/test_prompt_scoping_live.py`, which errors in `setUpClass`).
  `shutil.copy` would not copy the restricted flags.
- `tests/test_tmux_exec.py:512 — the fixture's TMUX_TMPDIR path exceeds the
  ~104-byte unix-socket limit on macOS ("File name too long")`.
- `tests/test_codebrowser_startup_focus_live.py —
  test_bare_q_quits_a_codebrowser_launched_outside_a_git_repo fails in
  isolation`. NOT the documented under-load flake: it fails with nothing else
  running, so the carve-out's boot-budget rationale does not explain it.

## Diagnostic context

From t1705_4's Final Implementation Notes. The task ran the full Python suite
twice (once mid-implementation, once clean at the end) plus each failing module
individually, and then re-ran the same modules against a stashed clean tree:

```
=== tests/test_tmux_exec.py (clean tree)          FAILED (failures=1)
=== tests/test_prompt_scoping_live.py (clean tree) FAILED (errors=1)
=== tests/test_agent_keys.py (clean tree)          FAILED (errors=5)
=== tests/test_codebrowser_startup_focus_live.py (clean tree) FAILED (failures=1)
```

The exact errors:

```
PermissionError: [Errno 1] Operation not permitted:
  '/var/folders/.../T/t1467-agentkeys-uh3046ye/codex'
  (shutil.copystat -> lookup("chflags"))

AssertionError: 1 != 0 : error connecting to
  /private/var/folders/.../T/ait_t952_1_tmux_grcwud9f/tmux-501/ait_t952_1_test
  (File name too long)
```

Both are macOS-specific: `chflags` on a SIP-protected source binary, and the
~104-byte `sun_path` limit that `$TMPDIR` under `/var/folders/...` already
half-consumes. Neither is visible on Linux CI, which is presumably why they
have persisted.

## Suggested fix

- `shutil.copy2` -> `shutil.copy` in both fixture helpers (the tests need the
  executable bit, not the source's flags/times). Confirm the copied file is
  still `chmod +x`.
- `test_tmux_exec.py`: build the fixture socket dir under a short path
  (e.g. `mkdtemp(dir="/tmp")`) rather than `$TMPDIR`, or point `-S` at a short
  socket path directly. `tests/lib/tmux_isolation.sh` already uses a fixed
  short per-user dir for the same reason — reuse that shape.
- `test_codebrowser_startup_focus_live.py`: diagnose separately; the isolation
  failure means the carve-out in CLAUDE.md is not the explanation.
