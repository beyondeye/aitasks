---
priority: medium
effort: medium
depends: [t1823_5]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1823_1, t1823_2, t1823_3, t1823_4, t1823_5]
assigned_to: dario-e@beyond-eye.com
anchor: 1823
followup_kind: manual_verification
created_at: 2026-09-17 10:00
updated_at: 2026-09-18 17:05
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1823_1] On a real session: `./.aitask-scripts/aitask_brainstorm_context.sh --lineage <N> <synth_node>` lists ancestors from every parent branch, and `git -C .aitask-crews/crew-brainstorm-<N> status` stays clean — PASS 2026-09-18 16:24 auto: --lineage 1812 n006/n009 (3-4 parents) emitted full transitive ancestor closure incl. every parent branch; crew git status + diff hash unchanged
- [x] [t1823_2] `/aitask-brainstorm-discuss <N> <node_a> <node_b>` in Claude Code lists `A`/`B` with titles and the `>` menu before reading proposals in depth — PASS 2026-09-18 16:36 auto: live claude session (tmux) on 1812 n007/n008 printed A/B + titles and the >c/>cd/>e/>f/>q/>h/>? menu after only a title skim
- [x] [t1823_2] After a full `>cd` and `>f` round, `git status` in `.aitask-crews/crew-brainstorm-<N>` is clean — PASS 2026-09-18 16:36 auto: after >cd then >f A (Read/Bash only, 0 Write/Edit), crew-brainstorm-1812 git status + sha1 of every file identical to pre-session snapshot
- [x] [t1823_4] In `ait brainstorm <N>`: `A` on a single node shows an enabled Discuss row last in the list; with 2 marked nodes it is still enabled and the dialog's prompt lists both node ids — PASS 2026-09-18 16:39 auto: tmux-driven ait brainstorm 1812 -- single node (n000_init): enabled rows Explore/Fast-track/Discuss, Discuss last; 2 marked (n001,n002): Discuss enabled, dialog 'Discuss n001_explorer_001a, n002_explorer_001b', command carries both ids
- [x] [t1823_4] In the agent dialog, change the model, choose "Run in tmux" (new window): the launched pane runs the changed model and a minimonitor companion appears — PASS 2026-09-18 16:40 auto: model changed gpt5_6_terra→gpt5_4_mini, Run in tmux → new window agent-discuss-1812 pane cmd 'codex ... -m gpt-5.4-mini $aitask-brainstorm-discuss 1812 n001 n002' + second pane 'ait minimonitor'
- [x] [t1823_4] In the agent dialog, change the model and choose "Run in terminal": the terminal runs the changed model, not the default — PASS 2026-09-18 16:41 auto: model changed to gpt5_4_mini, Direct → Run in terminal spawned 'foot -e sh -c codex ... -m gpt-5.4-mini $aitask-brainstorm-discuss 1812 n001 n002' as child of brainstorm_app; no tmux window created
- [x] [t1823_4] Split placement works; with tmux unavailable the terminal fallback launches — PASS 2026-09-18 16:43 auto: Split -- chose existing window (throwaway av1823-split-target) → window split horizontally, codex discuss pane added, no new window; tmux hidden from PATH → dialog shows only Run in terminal, foot+codex launched
- [x] [t1823_4] No crew agent appears in the Running tab and no node is created by Discuss — PASS 2026-09-18 16:43 auto: after 4 Discuss launches (tmux window, split, 2x terminal), Running tab: 'No running processes', newest op group explore_004 (2026-09-16, pre-existing); br_nodes list + sha1 of every crew file identical to pre-session snapshot
- [x] [t1823_5] Rendered docs (brainstorm reference + how-to + the new skill page) read correctly in `./serve.sh` and describe what actually shipped (label, shortcodes, read-only guarantee) — PASS 2026-09-18 16:46 auto: hugo build + check_links --build PASSED; rendered skill page + how-to: tables render, all 7 shortcodes as code spans, no shortcode/markdown leak; content matches live behaviour (Discuss last row, skips wizard, agent-discuss-<N>+minimonitor, split w/o minimonitor, terminal fallback, read-only, codeagent discuss default codex/gpt5_6_terra). Rendered-HTML inspection, not a browser read
- [defer] [t1823_4] Rapid Esc (several presses) on the Discuss agent dialog, its model picker and its profile editor leaves `ait brainstorm <N>` running on the Browse tab; a rapid-Esc on the same dialogs in one other host TUI (e.g. board or codebrowser) also leaves that TUI up — DEFER 2026-09-18 17:05 brainstorm half PASSED (rapid Esc from Discuss dialog, model picker, profile editor → alive on Browse); other-host half (board p / codebrowser e) still to check by hand

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
