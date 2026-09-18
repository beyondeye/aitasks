---
priority: medium
effort: medium
depends: [t1823_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1823_1, 1823_2, 1823_3, 1823_4, 1823_5]
anchor: 1823
followup_kind: manual_verification
created_at: 2026-09-17 10:00
updated_at: 2026-09-17 10:00
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1823_1] On a real session: `./.aitask-scripts/aitask_brainstorm_context.sh --lineage <N> <synth_node>` lists ancestors from every parent branch, and `git -C .aitask-crews/crew-brainstorm-<N> status` stays clean
- [ ] [t1823_2] `/aitask-brainstorm-discuss <N> <node_a> <node_b>` in Claude Code lists `A`/`B` with titles and the `>` menu before reading proposals in depth
- [ ] [t1823_2] After a full `>cd` and `>f` round, `git status` in `.aitask-crews/crew-brainstorm-<N>` is clean
- [ ] [t1823_4] In `ait brainstorm <N>`: `A` on a single node shows an enabled Discuss row last in the list; with 2 marked nodes it is still enabled and the dialog's prompt lists both node ids
- [ ] [t1823_4] In the agent dialog, change the model, choose "Run in tmux" (new window): the launched pane runs the changed model and a minimonitor companion appears
- [ ] [t1823_4] In the agent dialog, change the model and choose "Run in terminal": the terminal runs the changed model, not the default
- [ ] [t1823_4] Split placement works; with tmux unavailable the terminal fallback launches
- [ ] [t1823_4] No crew agent appears in the Running tab and no node is created by Discuss
- [ ] [t1823_5] Rendered docs (brainstorm reference + how-to + the new skill page) read correctly in `./serve.sh` and describe what actually shipped (label, shortcodes, read-only guarantee)

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1823_4** id=2026-09-18T09:35:44Z.eadd31f753c6449664af42dc from=t1823_4 from_verified=yes at=2026-09-18T09:35:44Z base=04ae398bd956744a10b7737c666274a9c2f68072 base_branch=main dirty=yes host=omg16
>
> | t1823_4 landed (commit 04ae398bd) with two behaviours your checklist does not yet cover, both added in plan review:
> | 
> | 1. Stale-dismiss guard on the shared agent-launch dialogs. AgentCommandScreen, AgentModelPickerScreen, LaunchModePickerScreen, ProfileEditScreen and EditStringScreen now derive from the t1816 guarded-dismiss base. Suggested live check: in `ait brainstorm <N>` open Discuss, press Esc rapidly several times (also from the model picker `a` and the profile editor), brainstorm must stay up on the Browse tab. The guard applies in every TUI using these dialogs (board, codebrowser, monitor, minimonitor, syncer, settings), so a quick rapid-Esc on one other host is worthwhile too.
> | 
> | 2. Target resolution. Discuss validates its effective targets itself, before the cursor-exists check: with nodes A and B marked and the cursor on a node C that gets deleted while the Operations dialog is open, Discuss still launches for A and B. A partly vanished marked set launches the survivors and warns naming the dropped ids. Both are unit-tested (tests/test_brainstorm_discuss_launch.py); the live repro needs a node deleted mid-dialog, so it may be impractical to check by hand.
> | 
> | Advisory only.

> **👁 note:read** id=2026-09-18T13:22:46Z.d22fd99c0ab9207015b25c89 by=t1823_6 at=2026-09-18T13:22:46Z mode=explicit ids=2026-09-18T09:35:44Z.eadd31f753c6449664af42dc
