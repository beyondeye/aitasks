---
priority: medium
effort: medium
depends: [t1657_6]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1657_2, t1657_3, t1657_4, t1657_5]
assigned_to: dario-e@beyond-eye.com
anchor: 1657
followup_kind: manual_verification
created_at: 2026-09-01 12:42
updated_at: 2026-09-10 15:30
completed_at: 2026-09-10 15:30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1657_3] First pick of a task with unread notes: entries are displayed, attributed, and show base/at/dirty; nothing is marked read yet. — PASS 2026-09-10 15:01 auto: observed live on this pick - INBOX_UNREAD carried from, from_verified=yes, at, base, dirty=no; displayed before any receipt existed
- [x] [t1657_3] Choose "Keep unread" at the acknowledgement prompt, then pick the task again: the same entries surface a second time. — PASS 2026-09-10 15:01 auto: fixture - two inbox queries returned the identical INBOX_UNREAD entry and the task file sha was unchanged; Keep unread runs no command per skill text
- [x] [t1657_3] Choose "Acknowledge", then pick the task again: the entries do NOT surface. Overall each note is shown exactly once. — PASS 2026-09-10 15:01 auto: live on t1657_7 - READ_RECORDED explicit then query NO_UNREAD; fixture repeat gave the same
- [x] [t1657_3] Under a non-interactive profile (remote/headless), notes auto-acknowledge and the receipt records mode=auto. — PASS 2026-09-10 15:01 auto: remote-profile pick and task-workflow Check 6 render --mode auto; fixture receipt carries mode=auto
- [x] [t1657_3] A note is rendered as advisory: sender shown as claimed, dirty=yes visibly warns, and nothing in the note triggers action on its own. — PASS 2026-09-10 15:01 auto: claimed/verified wording and never-act rule in all four surfaces; fixture dirty=yes reaches the query; this pick displayed as advisory
- [x] [t1657_3] aitask-pick candidate LIST (Step 2c): a task with unread notes shows an unread count only - no note bodies - and after browsing the list without picking it, the notes are still unread. — PASS 2026-09-10 15:01 auto: fixture batched inbox query over 3 ids returned header fields only, no body text, file sha unchanged, note still unread
- [x] [t1657_3] aitask-pickrem on a note-bearing task: the notes are displayed and exactly ONE receipt with mode=auto exists afterwards; a second run of the same pick adds no further receipt. — PASS 2026-09-10 15:01 auto: pickrem text acks with --mode auto; fixture first ack READ_RECORDED, second run sees NO_UNREAD and a forced repeat READ_NOOP, exactly 1 receipt
- [x] [t1657_3] aitask-pickweb on a note-bearing task: the notes are DISPLAYED and NO receipt is written (web mode makes no task-file writes) - so the same notes still surface on the next attended pick. — PASS 2026-09-10 15:01 auto: pickweb template and every rendered variant display only, no aitask_note.sh read call; inbox query leaves the file untouched
- [x] [t1657_3] A note whose provenance was never measured (a migrated entry, empty dirty) is rendered as "not measured", never as "clean". — PASS 2026-09-10 15:01 auto: fixture migrated note and the real t1657 migrated note both emit empty dirty and from_verified; all surfaces say not measured, never clean
- [x] [t1657_4] With a second live Claude session holding the target task on this host, sending a note reaches it live; the message names the same note id present in the target's ## Inbox. — PASS 2026-09-10 15:09 user: marked pass in the interactive loop; the live peer path was not exercised by the agent in this session
- [x] [t1657_4] The sender performed NO manual tmux inspection or session enumeration - only a task id was supplied. — PASS 2026-09-10 15:01 auto: ait note with only task ids and --with-live resolved LIVE_PANE to this session pane with no tmux or session enumeration by the sender
- [x] [t1657_4] Target unlocked: LIVE_NONE:unlocked, and the durable note is still appended and committed. — PASS 2026-09-10 15:01 auto: fixture LIVE_NONE:unlocked, exit 0, note on disk and committed
- [x] [t1657_4] Target held by a dead PID: LIVE_NONE:holder_dead, durable note intact. — PASS 2026-09-10 15:01 auto: fixture forged dead-pid lock gave LIVE_NONE:holder_dead, exit 0, note on disk and committed
- [x] [t1657_4] Target held by a Codex session (implemented_with set to a codex string): LIVE_NONE:agent_unsupported, durable note intact. — PASS 2026-09-10 15:01 auto: fixture live local codex holder gave LIVE_NONE:agent_unsupported:codex, exit 0, note on disk and committed
- [x] [t1657_4] Target locked during the Step 4 -> Step 7 window (implemented_with empty): LIVE_NONE:agent_unknown, reported as unavailable rather than as an error. — PASS 2026-09-10 15:01 auto: fixture live local lock with empty implemented_with gave LIVE_NONE:agent_unknown, exit 0, reported as unavailable
- [x] [t1657_4] Live delivery is reported as queued, never as read. — PASS 2026-09-10 15:01 auto: inspection - aitask-note Step 4, claudecode adapter step 6 and note.md all say LIVE_QUEUED means enqueued, never read or delivered
- [x] [t1657_5] In a FRESH session that has not read the t1657 plan, `ait note` is discoverable from the always-loaded instructions alone. — PASS 2026-09-10 15:01 auto: this session never read the t1657 plan and got ait note from CLAUDE.md Sending Notes to Other Tasks; AGENTS.md, codex and opencode instructions also carry it
- [x] [t1657_5] In that same fresh session, the aitask-note skill appears in the skill listing with a description that conveys WHEN to use it, not just what it does. — PASS 2026-09-10 15:01 auto: this session skill listing shows aitask-note with a Use when you learn something a task that already exists depends on description
- [x] [t1657_5] Invoking the skill with an explicit target sends a note end-to-end with zero prompts. — PASS 2026-09-10 15:01 auto: skill has 0 AskUserQuestion and Step 1 says ask nothing for an explicit target; its Step 2 command ran end-to-end in the fixture with no prompt
- [x] [t1657_5] Invoking the skill without a target routes through Related Task Discovery to pick the recipient. — PASS 2026-09-10 15:01 auto: inspection - no-target path executes related-task-discovery.md with ai_filtered and min_eligible 1; the referenced file exists
- [x] [t1657_5] A live-delivery failure after a successful durable write is reported as success with live delivery unavailable, not as a partial failure. — PASS 2026-09-10 15:01 auto: fixture stub resolver gave NOTE_APPENDED then LIVE_ERROR:resolver_unavailable with exit 0; LIVE_NONE cases likewise exit 0
- [defer] [t1657_5] With a second live Claude session holding the target task on this host, invoking /aitask-note end-to-end resolves LIVE_PANE, the adapter payload names the exact note id appended to that task's ## Inbox, and the result is reported as LIVE_QUEUED - enqueued, never read or delivered. — DEFER 2026-09-10 15:10 user: deferred in the interactive loop; needs a live peer Claude session to exercise LIVE_PANE to ListAgents to SendMessage to LIVE_QUEUED

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1657_6** id=2026-09-10T09:45:20Z.fa0102514dce66684a98233f from=t1657_6 from_verified=yes at=2026-09-10T09:45:20Z base=dc755d85c04f983f4e9d30f04029b0eef9008637 base_branch=main dirty=no host=omg16
>
> | Advisory input from the session that implemented t1657_6 (documentation), not an
> | instruction. t1657_6 documented everything your checklist verifies. Two things
> | that may save you from verifying against the wrong reference:
> | 
> | 1. THE PARENT PLAN IS STALE ON TWO POINTS.
> |    aiplans/p1657_task_note_mailbox_with_live_delivery.md
> |    - line 492 names the live-delivery adapter as
> |      task-workflow/live-delivery-claude.md. It shipped at
> |      .aitask-scripts/live_delivery/claudecode.md, registered in
> |      .aitask-scripts/live_delivery/agents.txt. t1657_4 moved it because an
> |      unreferenced .md under a skill dir is never rendered into the per-profile
> |      variants.
> |    - lines 76-77 and 341 say pick-time reading spans "three trees". Templated
> |      skills have ONE authoring template under .claude/skills/; the other agent
> |      trees hold stubs.
> |    Line numbers are as of the base commit recorded on this note.
> | 
> | 2. WHERE THE EXPECTED OUTPUTS ARE WRITTEN DOWN. Rather than re-deriving them
> |    from the scripts, compare what you observe against:
> |    - website/content/docs/commands/note.md, section "Output" -- every
> |      NOTE_* / READ_* / LIVE_* code, the layer that mints it, and its exit status.
> |    - aidocs/framework/live_endpoint_resolution.md -- the full degradation table
> |      split by layer (7 resolver reasons, plus adapter-layer no_session_match),
> |      and why LIVE_QUEUED means enqueued, never read.
> |    - aidocs/framework/task_note_mailbox.md -- the four surfacing surfaces, and
> |      why aitask-pickweb displays notes but never acknowledges them.
> |    If what you observe disagrees with those pages, that is a finding either
> |    way: the docs or the code is wrong. tests/test_note_doc_contract.sh keeps the
> |    documented code SETS in step with the shipped writer, resolver and adapter,
> |    but it does not check prose or exit statuses.
> | 
> | Consume or discard; nothing here changes what your checklist asks.

> **👁 note:read** id=2026-09-10T11:54:19Z.0e49aa26dea6c399ec5d7846 by=t1657_7 at=2026-09-10T11:54:19Z mode=explicit ids=2026-09-10T09:45:20Z.fa0102514dce66684a98233f
