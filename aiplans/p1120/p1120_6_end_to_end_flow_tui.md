---
Task: t1120_6_end_to_end_flow_tui.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_1_*.md … t1120_7_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_6_end_to_end_flow_tui
Branch: aitask/t1120_6_end_to_end_flow_tui
Base branch: main
---

Contracts: snapshot of parent plan §PINNED — FROZEN expected (verify).

# Plan: t1120_6 — End-to-end flow + minimal TUI

Deliverables, the fail-closed payload-validation contract text, and the pinned
reactions vocabulary are in the task file
(`aitasks/t1120/t1120_6_end_to_end_flow_tui.md`). Read ALL prior archived
sibling plans (`aiplans/archived/p1120/`) first — this child consumes every
seam.

## Step 1 — `chatlink/flow.py` (session orchestrator)

Per-session async task owned by the daemon loop:
1. ⏳ reaction on the bug-report message; post thread opener.
2. Build `SandboxSpec` (workspace copy via `lib/sandbox_launch.
   make_workspace_copy`, relay dir from `paths.relay_root()/<session_id>`,
   agent argv = `ait codeagent … invoke explore-relay --headless` env-threaded)
   and `launch(spec)`.
3. Pump loop: watch spool (`asyncio.to_thread` poll) — new question ⇒
   `render_question` → `send_message(thread, components)` → ❓ reaction;
   INTERACTION_RECEIVED ⇒ `policy.may_answer(initiator, actor)` (reject ⇒
   ephemeral, question stays pending) → `assemble_answer` → atomic answer
   write → persist outcome → disable components via `edit_message`; free-text
   button ⇒ `open_modal` immediately (contract 5).
4. Completion: handle exit + `payload.json` present ⇒ **validate fail-closed**
   (Step 2) ⇒ create + commit task ⇒ ✅ + thread summary (task id, title).
   Death/timeout/invalid ⇒ ❌ + reason + cancelled answers + audit; workspace
   copy cleanup in all terminal paths.

## Step 2 — payload validation (`chatlink/payload_guard.py`)

`validate_payload(raw: bytes, metadata_dir) -> ValidatedPayload | Rejection`
implementing the task file's contract-7 rules verbatim (schema, allowlists
from `task_types.txt`/`labels.txt`, size limits, control-char strip). Share
the schema dataclass with `relay.py` (single definition — no drift).
Rejection carries a machine-readable reason for thread + audit.

## Step 3 — task creation plumbing

`create_task_from_payload(vp)`: argv-list call to
`./.aitask-scripts/aitask_create.sh --batch --commit --name … --priority …
--effort … --type … --labels … --followup-of <none> --desc-file -` feeding the
description via stdin (never shell interpolation); parse `Created:` line for
the path/id; then best-effort `./ait git push`. Runs via `asyncio.to_thread`.

## Step 4 — minimal TUI

Read `aidocs/framework/tui_conventions.md` + `aidocs/framework/tmux_gateway.md`
first. `chatlink/chatlink_app.py`: single screen — daemon status, session
table (id, state, initiator, thread, age), audit tail. Register in
`lib/tui_registry.py` `TUI_REGISTRY` (launch cmd `ait chatlink`); headless
daemon remains `ait chatlink --headless` (no Textual import — guard test).
TUI switcher picks it up automatically from the registry.

## Step 5 — e2e tests

Against `MockChatAdapter` + `FakeLauncher` (scripted agent behavior via the
spool). Cover every bullet of the task file's Verification section, including
crash-restart-reconcile (drop the flow tasks, rebuild daemon over the same
store, assert startup actions) and multi-session custom_id routing no
cross-talk. This section seeds the aggregate MV sibling — keep bullets
verbatim testable.

## Step 9 reference

Post-implementation follows task-workflow Step 9. This is the last feature
child before docs (t1120_7).
