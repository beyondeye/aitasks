---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [chat_surface, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1074
implemented_with: claudecode/fable5
created_at: 2026-07-05 12:38
updated_at: 2026-07-10 19:05
completed_at: 2026-07-10 19:05
---

## Origin

Spawned from t1074_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2655-2678 — non-interactive setup auto-accepts the "commit framework files" prompt and sweeps ALL uncommitted framework-path changes (including other sessions' in-progress work) into an "ait: Add aitask framework" commit; running any ait-setup invocation mid-implementation on a dirty tree silently commits foreign work`
- `.aitask-scripts/chat/discord_adapter.py:880 — send_message accepts the ABC's attachments parameter and silently drops it (same partial-send-as-success gap fixed for Slack in t1074_3; Discord should also reject loudly or implement the file path)`

## Diagnostic context

During t1074_3 verification, `ait setup --with-chat` was run in the aitasks framework repo to verify the opt-in chat-SDK install. Because the Bash tool is non-interactive (`[[ -t 0 ]]` false), the "Commit framework files to git? [Y/n]" prompt at `aitask_setup.sh:2655` auto-accepted, and the `changed_files` list (computed from working-tree state, not from what setup itself wrote) included a concurrent session's uncommitted work (`applink/pusher.py`, `monitor/minimonitor_app.py`, `monitor_app.py`, `monitor_core.py`, `.opencode/package-lock.json`) plus the in-flight t1074_3 implementation. All were committed as `ait: Add aitask framework` (91b0c3dfa, since reset away with `git reset --mixed HEAD~1`). The detection cannot distinguish "setup wrote this file" from "developer has uncommitted work here".

The second defect was found while fixing the identical issue in the new Slack adapter (review finding on t1074_3): `SlackAdapter.send_message` now raises base `ChatError` on non-empty `attachments` (no Slack API attaches pre-existing file handles to chat.postMessage); `DiscordAdapter.send_message` still accepts and silently ignores the parameter, so a text+files send partially succeeds with no error while `capabilities().supports_files=True`.

## Suggested fix

For the setup sweep: track the exact set of files setup itself writes/updates during the run and commit only those (path-scoped), or in non-interactive mode default to NOT committing pre-existing dirty paths (list-and-warn instead). For the Discord adapter: mirror t1074_3's Slack fix — reject non-empty `attachments` with base `ChatError` pointing at `upload_attachment` (plus a construction-spy test), or implement the file path.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-10T15:13:26Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-10T16:01:02Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-10T16:05:45Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:fb45885658d6bb9d

> **✅ gate:risk_evaluated** run=2026-07-10T16:05:45Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1128/risk_evaluated_2026-07-10T16:05:45Z-risk_evaluated-a1.log`
