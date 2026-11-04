---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [monitor]
gates: [risk_evaluated]
anchor: 2034
followup_kind: carry_over
created_at: 2026-11-04 12:33
updated_at: 2026-11-04 12:33
---

## Origin

Carried over from t2034_3. Plan step 7 was skipped by the user's choice, and recorded as such.
When t2034_3 was ready to commit, `CLAUDE.md` held another live session's uncommitted
sitrep pointer (8 lines) in the same "TUI Development" block. Editing the file then would
have let that session's whole-file commit absorb this line.

## Do

Add one pointer to the "TUI Development" block of `CLAUDE.md`, in the same blockquote style
as its neighbours (for example the `shadow_agent.md` / `sitrep.md` pointers):

> **Read `aidocs/framework/monitor_status_protocol.md`** when editing
> `monitor/status_protocol.py` or `monitor/status_recording.py`, the recorded fixtures
> under `tests/fixtures/monitor_status/`, or the monitor status server or client (or
> anything that speaks that protocol in another language). It is the wire between the one
> shared monitor producer and its clients — NDJSON over a Unix socket, snapshot + per-
> generation deltas — and its member tables are pinned to the codec by
> `tests/test_monitor_status_protocol.py`.

## Gate (shared file)

Run `git diff --quiet HEAD -- CLAUDE.md` immediately before the first edit. If it reports
uncommitted changes from another session, wait for them to be committed, or ask. Commit
`CLAUDE.md` by path only.

## Verification

`bash tests/test_agent_instructions.sh` (CLAUDE.md must stay marker-less) passes.
