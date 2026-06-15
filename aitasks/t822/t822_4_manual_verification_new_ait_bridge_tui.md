---
priority: medium
effort: medium
depends: [t822_3]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t822_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-24 09:36
updated_at: 2026-06-15 17:29
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t822_2] `bash tests/test_applink_smoke.sh` passes (PASS line)
- [ ] [t822_2] `shellcheck .aitask-scripts/aitask_applink.sh` reports no warnings
- [ ] [t822_2] `./ait applink` opens the TUI without a traceback
- [ ] [t822_2] QR scans cleanly with a phone QR reader and yields a URI matching `applink://<lan-ip>:<port>/pair?t=<base64url>&fp=<fp>`
- [ ] [t822_2] Pressing `r` regenerates the token — the on-screen QR visibly changes
- [ ] [t822_2] Pressing `s` switches to the Status screen, `p` switches back to Pairing
- [ ] [t822_2] Pressing `j` switches to another TUI (e.g. brainstorm) and back — TuiSwitcherMixin works
- [ ] [t822_2] Pressing `q` quits cleanly (exit code 0)
- [ ] [t822_2] On a fresh venv, `ait setup` installs `segno` without errors
- [ ] [t822_2] `cd website && ./serve.sh` shows the new applink pages under TUIs nav
