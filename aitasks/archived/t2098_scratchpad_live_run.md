---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: [bash_scripts, testing, macos, tests]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 1681
followup_kind: risk_mitigation
created_at: 2026-10-21 14:44
updated_at: 2026-10-21 15:13
completed_at: 2026-10-21 15:13
---

## Origin

Risk-mitigation ("after") follow-up for t2095, created at Step 8d after implementation landed.

## Risk addressed

#4's cwd change unverified by a live run (tmux refusal in-session)

- #4 cannot be executed in this session (tmux refusal), so the cwd change to `test_scratchpad_spawn_live.sh` is verified only by lint, `bash -n` and code inspection, not by a live run. Severity: medium. Mitigation: scratchpad_live_run.

## Goal

t2095 (commit b08780dd4) changed `tests/test_scratchpad_spawn_live.sh` in two ways:
it now calls `enter_scratch_cwd` right after `PROJECT_DIR` is derived, so the
test starts in an empty read-only scratch directory instead of the invoking
one; and `key_for` now uses `(cd "$1" || exit 1` + `if … fi)` instead of a
`cd "$1" && if …` chain. Inspection suggests neither changes behaviour (every
pane gets `-c "$ROOT"`, `spawn_scratchpad` passes an explicit cwd, the driver's
PYTHONPATH is absolute), but the file was never run after the change.

## Verification Steps

- From a terminal that is NOT inside tmux, and with the `-L ait` server stopped (`require_clean_ait_server` refuses otherwise), run `bash tests/test_scratchpad_spawn_live.sh` from the repo root — it exits 0 with no `FAIL:` lines.
- Run it again from a directory outside the repo (e.g. `cd ~ && bash <repo>/tests/test_scratchpad_spawn_live.sh`) — same result, proving the test no longer depends on the invoking cwd.
- After the runs, `git status` in the repo shows nothing new (no stray fixture writes).

## Verification Checklist

- [defer] From a terminal NOT inside tmux, with the -L ait server stopped, run `bash tests/test_scratchpad_spawn_live.sh` from the repo root — exits 0 with no FAIL: lines — DEFER 2026-10-21 14:49
- [defer] Run it again from a directory outside the repo (`cd ~ && bash <repo>/tests/test_scratchpad_spawn_live.sh`) — same result, proving the test no longer depends on the invoking cwd — DEFER 2026-10-21 14:52
- [defer] After the runs, `git status` in the repo shows nothing new (no stray fixture writes) — DEFER 2026-10-21 14:52
