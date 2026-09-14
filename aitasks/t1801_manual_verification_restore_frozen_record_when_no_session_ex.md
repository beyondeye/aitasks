---
priority: medium
effort: medium
depends: [1784]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1784]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-14 15:00
updated_at: 2026-09-14 15:08
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1784

## Verification Checklist

- [ ] Acceptance suite (unverified in t1784 — it refuses to run inside tmux): from a terminal OUTSIDE tmux, with the dedicated server stopped (`tmux -L ait kill-server` ends EVERY ait session — finish or freeze work first), run `bash tests/test_frozen_agents_acceptance.sh`. Expect ALL TESTS PASSED, including: t1784's new cases 6c (tmux restarted, only an unrelated session) and 6d (no tmux server at all); cases 7-10b, which run after 6c/6d restart the server (a failure confined to them points at `reestablish_fixture_server`); and both final real-$HOME checks (the shim is unchanged, and ~/.config/aitasks/projects.yaml never names the scratch project)
- [ ] Restore-flows suite (unverified in t1784): same preconditions (outside tmux, `-L ait` server stopped), run `bash tests/test_restore_flows_live.sh`. Expect ALL TESTS PASSED; case 7, where a session for the project exists, must still restore into a new window without bootstrapping a new session
- [ ] Manual end-to-end: run `ait ide` in this project, launch an agent (e.g. from the board) and freeze it, then run `tmux -L ait kill-server`. From a plain terminal outside tmux run `./ait frozen restore --all`. Expect a RESTORED line, and the agent back in the project's `aitasks` session beside a `monitor` window; `ait ide` then attaches to that session
- [ ] Manual collision check: freeze an agent in project B, close B's tmux session, then set B's `tmux.default_session` to the name of a live session belonging to project A, and restore the record. Expect `restore failed: respawn:no_session_for_root:<B root>|bootstrap:session_name_taken:<name> — capture kept`, and A's session unchanged: same windows, and `tmux -L ait show-environment -g AITASKS_PROJECT_<name>` still names A. Revert B's `tmux.default_session` afterwards
