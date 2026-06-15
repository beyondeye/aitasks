---
priority: medium
effort: medium
depends: [t822_3]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t822_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-24 09:36
updated_at: 2026-06-15 18:22
completed_at: 2026-06-15 18:22
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t822_2] `bash tests/test_applink_smoke.sh` passes (PASS line) — PASS 2026-06-15 18:01 auto: bash tests/test_applink_smoke.sh exited 0; output reported Results: 1/1 passed, 0 failed
- [fail] [t822_2] `shellcheck .aitask-scripts/aitask_applink.sh` reports no warnings — FAIL 2026-06-15 18:01 follow-up t1002
- [x] [t822_2] `./ait applink` opens the TUI without a traceback — PASS 2026-06-15 18:01 auto: ./ait applink opened in tmux session aitverify8224 and rendered the Pair a device QR screen without traceback
- [x] [t822_2] QR scans cleanly with a phone QR reader and yields a URI matching `applink://<lan-ip>:<port>/pair?t=<base64url>&fp=<fp>` — PASS 2026-06-15 18:01 manual: user scanned the visible tmux QR and confirmed it produced the expected applink:// pairing URI
- [x] [t822_2] Pressing `r` regenerates the token — PASS 2026-06-15 18:01 auto: pressing r regenerated the pairing token and visibly changed the captured QR block
- [x] [t822_2] Pressing `s` switches to the Status screen, `p` switches back to Pairing — PASS 2026-06-15 18:02 auto: pressing s opened Devices/status with listener state; pressing p returned to Pairing
- [x] [t822_2] Pressing `j` switches to another TUI (e.g. brainstorm) and back — PASS 2026-06-15 18:02 auto: pressing j opened TUI Switcher; shortcut b switched to Board; from Board, j then a switched back to App Linker
- [x] [t822_2] Pressing `q` quits cleanly (exit code 0) — PASS 2026-06-15 18:02 auto: pressing q closed the App Linker tmux window and returned to the previous Board window
- [x] [t822_2] On a fresh venv, `ait setup` installs `segno` without errors — PASS 2026-06-15 18:02 manual/static: user accepted static evidence; aitask_setup.sh CPython install and import verification include segno>=1.5,<2
- [x] [t822_2] `cd website && ./serve.sh` shows the new applink pages under TUIs nav — PASS 2026-06-15 18:02 auto: Hugo build to /tmp/aitverify8224_site succeeded; generated TUI nav contains App Linker and applink pages
