---
priority: medium
effort: medium
depends: [1374]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1374]
created_at: 2026-08-03 16:09
updated_at: 2026-08-03 16:09
boardidx: 15360
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1374

## Verification Checklist

- [ ] On a genuinely network-disconnected machine (interface down, not just a bad index URL) with a healthy venv and all installed tiers: `ait setup` completes with exit 0. Warnings about failed pip calls are acceptable; an abort is not.
- [ ] Same disconnected machine, with a core dependency deliberately removed (`~/.aitask/venv/bin/pip uninstall -y pyyaml`): `ait setup` must still fail, but with the actionable message "CPython venv still bad (missing: ...). Check pip/network and re-run 'ait setup'." — NOT a bare pip traceback. Restore afterwards with `ait setup`.
- [ ] Same disconnected machine, with a chat-tier dependency removed: `ait setup` must warn "Chat deps could not be installed ... Re-run 'ait setup --with-chat' to retry." and still reach "Setup complete!" with exit 0.
- [ ] Same disconnected machine, with a PyPy-venv dependency removed: setup must warn, remove ~/.aitask/pypy_venv, continue to "Setup complete!", and `ait board` must then run on the CPython venv.
- [ ] Confirm the failure mode matches the measured premise: with the network down but every dependency already satisfied, pip short-circuits and setup is clean. The guards matter when a dependency is genuinely unsatisfied (e.g. right after a version bump in AIT_PIP_SPECS_*).
