---
priority: medium
effort: medium
depends: [t1120_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1120_1, 1120_2, 1120_3, 1120_4, 1120_5, 1120_6, 1120_7]
anchor: 1120
created_at: 2026-07-05 12:11
updated_at: 2026-07-05 12:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1120_1] Re-run the recorded headless-relay spike invocation once: agent blocks on the relay question file and continues after a hand-written answer, writing payload output.
- [ ] [t1120_2] After `ait setup`, seeded `aitasks/metadata/chatlink_config.yaml` template exists; token file is 0600 inside a 0700 `chatlink_sessions/` dir; `git check-ignore` confirms the token path is ignored.
- [ ] [t1120_3] `ait chatlink --headless` starts with a real Discord bot token, connects, and an authorized user's message in the configured intake channel produces a thread + audit log entries.
- [ ] [t1120_4] Live headless `ait codeagent … invoke explore-relay --headless` run round-trips at least one clarifying question via the relay and writes a schema-valid payload.json.
- [ ] [t1120_5] Docker smoke: sandbox container launches with ait.chatlink.* labels and resource limits applied (`docker inspect`); after killing the daemon mid-session, restarting it reaps the orphaned container (`reap_orphans`).
- [ ] [t1120_6] Full live e2e on a test Discord server: authorized message → thread → select answer + free-text modal (initiating user only; a second account's click is rejected with an ephemeral notice) → aitask committed → thread summary + ✅ reaction.
- [ ] [t1120_6] Unauthorized user's message is ignored (or ephemeral denial per config) and spawns nothing; reactions legend (⏳ ❓ ✅ ❌) matches each state transition.
- [ ] [t1120_6] Chatlink TUI shows daemon status, the live session row, and audit tail; reachable via the TUI switcher.
- [ ] [t1120_7] Website docs page builds (`hugo build --gc --minify`) and renders correctly; `_index.md` bullet present and link resolves.
