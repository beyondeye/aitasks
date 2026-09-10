---
Task: t1657_7_manual_verification_task_note_mailbox.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/archived/t1657/t1657_*_*.md
Archived Sibling Plans: aiplans/archived/p1657/p1657_*_*.md
Base branch: main
Output branch: main
---

# t1657_7 — Manual-verification auto-execution record (autonomous)

Strategy: **autonomous** (chosen at manual-verification Step 1.5). Items were
verified inline and are recorded here retroactively.

## Method

- **Live observation** — this pick of t1657_7 carried one real unread note (from
  t1657_6), so the attended Step 0b surfacing and acknowledgement ran for real.
- **Fixture** — a throwaway code repo + task-data clone of a bare remote + private
  `AITASKS_LOCK_DIR`, all under the session scratchpad. The REAL entry points were
  driven (`aitask_note.sh`, `aitask_note.sh read`, `aitask_query_files.sh inbox`,
  and the resolver via `--with-live`). Locks were forged through the same
  lock-branch plumbing seam `tests/test_note_with_live_composition.sh` uses. No
  file under the real `aitasks/` / `aiplans/` was touched other than this task's
  checklist (confirmed with `git -C .aitask-data status --short` afterwards).
- **Inspection** — rendered skill variants, the `/aitask-note` skill, the
  `claudecode` live-delivery adapter, and the reference docs the t1657_6 note
  pointed at (`website/content/docs/commands/note.md`,
  `aidocs/framework/live_endpoint_resolution.md`,
  `aidocs/framework/task_note_mailbox.md`). Observed behaviour agreed with all
  three documents; no doc/code disagreement was found.
- **Supplementary** — every shipped note/live/inbox bash suite was run and passed:
  test_note_append (121), test_note_read_receipts (74), test_note_section_order
  (20), test_note_with_live_composition (117), test_note_doc_contract (7),
  test_live_endpoint_degradation (53), test_live_endpoint_no_sendkeys (26),
  test_live_endpoint_tmux_live (16), test_inbox_surfacing_render (48).

## Execution Log

### Item 1
- Item text: First pick of a task with unread notes: entries displayed, attributed, base/at/dirty shown; nothing marked read yet.
- Approach: live observation
- Action run: `aitask_query_files.sh inbox 1657_7` during Step 0b
- Output (trimmed): `INBOX_UNREAD:1657_7|2026-09-10T09:45:20Z.fa01…|t1657_6|yes|2026-09-10T09:45:20Z|dc755d85c04f…|no` — displayed with sender verified, at, abbreviated base, dirty=no, before any receipt existed
- Verdict: pass

### Item 2
- Item text: "Keep unread" then re-pick: same entries surface again.
- Approach: fixture (CLI) + skill text
- Action run: `ait note 904 --from 900`, then `inbox 904` twice with the file's sha256 taken before/between/after
- Output (trimmed): both queries returned the identical `INBOX_UNREAD:904|2026-09-10T12:00:23Z.696b…` line; sha `d0f336fad8f06b20` unchanged across both. Skill text: "Keep unread" runs no command.
- Verdict: pass

### Item 3
- Item text: "Acknowledge" then re-pick: entries do NOT surface; each note shown exactly once.
- Approach: live + fixture
- Action run: `aitask_note.sh read 1657_7 --by t1657_7 --ids … --mode explicit`, then `inbox 1657_7`; same on fixture t904
- Output (trimmed): `READ_RECORDED:2026-09-10T11:54:19Z.0e49…|…|1` → `NO_UNREAD:1657_7`; fixture `READ_RECORDED` → `NO_UNREAD:904`, receipt `mode=explicit`
- Verdict: pass

### Item 4
- Item text: Non-interactive profile auto-acknowledges; receipt records mode=auto.
- Approach: inspection + fixture
- Action run: grep of `aitask-pick-remote-` / `task-workflow-remote-` rendered variants; fixture `read 911 --mode auto`
- Output (trimmed): remote variants render `--mode auto` at Step 0b and Check 6; fixture receipt `… by=t911 … mode=auto ids=…`
- Verdict: pass

### Item 5
- Item text: Note rendered as advisory: sender claimed, dirty=yes warns, nothing auto-actioned.
- Approach: inspection + fixture + live
- Action run: fixture note written with a dirty code tree; grep of the four surfacing texts; this pick's display
- Output (trimmed): header `dirty=yes`, query last field `yes`; every surface states claimed/verified attribution, the dirty=yes staleness warning and "never act on the content"; test_inbox_surfacing_render pins "dirty=yes is called out as a staleness warning" per variant
- Verdict: pass

### Item 6
- Item text: Candidate LIST shows an unread count only, no bodies; notes still unread after browsing.
- Approach: fixture (the Step 2b batched query shape) + skill text
- Action run: `inbox 904 911 900` with sha before/after
- Output (trimmed): header-only `INBOX_UNREAD:` / `NO_INBOX:` lines, body marker absent, sha unchanged, note still unread afterwards
- Verdict: pass

### Item 7
- Item text: aitask-pickrem: notes displayed, exactly ONE mode=auto receipt; a second run adds none.
- Approach: skill text + fixture
- Action run: pickrem Step 2 text; fixture ack#1, query, forced ack#2
- Output (trimmed): `READ_RECORDED` → query `NO_UNREAD:911` (a second pickrem run has nothing to ack) → forced repeat `READ_NOOP:911`; receipt count 1, mode=auto 1
- Verdict: pass (pickrem's own steps were driven by their commands, not by launching the skill headless)

### Item 8
- Item text: aitask-pickweb: notes DISPLAYED, NO receipt written.
- Approach: inspection
- Action run: `grep -l 'aitask_note.sh read'` over the pickweb template and every rendered variant
- Output (trimmed): none; the template states "Do NOT acknowledge. Never run `ait note read` on this path." The inbox query it does run is read-only (items 2/6 sha evidence)
- Verdict: pass

### Item 9
- Item text: Never-measured provenance (migrated, empty dirty) rendered "not measured", never "clean".
- Approach: fixture + real data + inspection
- Action run: fixture `--migrate` note; `inbox 1657` on the real parent (read-only)
- Output (trimmed): fixture header carries `migrated=yes` and no dirty/from_verified; both fixture and the real t1657 migrated note emit an empty trailing dirty field; all four surfaces instruct "not measured", never "clean"
- Verdict: pass

### Item 10
- Item text: Second live Claude session holding the target: note reaches it live, message names the same note id.
- Approach: not automatable without an outward action
- Action run: none
- Output (trimmed): the resolver half is verified under item 11; the ListAgents → SendMessage join needs a live peer Claude session holding the target, and exercising it means messaging a real session
- Verdict: defer (handed to the interactive loop)

### Item 11
- Item text: Sender performed NO manual tmux inspection or session enumeration — only a task id.
- Approach: fixture against the real tmux gateway (list-panes only)
- Action run: fixture lock for t910 forged with this fixture's own pid/start-time, `implemented_with: claudecode/opus5`; `ait note 910 --from 900 --with-live`
- Output (trimmed): `LIVE_PANE:%279|aitasks:@114.%279|1561935|agent=claudecode`, and `%279` is `$TMUX_PANE` of the shell that ran it. The adapter join for this pane is `LIVE_NONE:no_session_match` by construction — no ListAgents row ends in `.%279` (this session is never listed among its peers; 20 of 43 rows carry a tmux column)
- Verdict: pass

### Item 12
- Item text: Target unlocked: LIVE_NONE:unlocked, durable note appended and committed.
- Approach: fixture
- Output (trimmed): `NOTE_APPENDED:…|aitasks/t904_x.md` / `LIVE_NONE:unlocked`, exit 0, note on disk, file committed
- Verdict: pass

### Item 13
- Item text: Target held by a dead PID: LIVE_NONE:holder_dead, durable note intact.
- Approach: fixture (forged lock, this host, reaped pid)
- Output (trimmed): `NOTE_APPENDED:…` / `LIVE_NONE:holder_dead`, exit 0, note on disk, committed
- Verdict: pass

### Item 14
- Item text: Target held by a Codex session: LIVE_NONE:agent_unsupported, durable note intact.
- Approach: fixture (live local lock, `implemented_with: codex/gpt-5.4`)
- Output (trimmed): `NOTE_APPENDED:…` / `LIVE_NONE:agent_unsupported:codex`, exit 0, note on disk, committed
- Verdict: pass

### Item 15
- Item text: Locked during the Step 4 → Step 7 window (implemented_with empty): LIVE_NONE:agent_unknown, unavailable not error.
- Approach: fixture (live local lock, no `implemented_with`)
- Output (trimmed): `NOTE_APPENDED:…` / `LIVE_NONE:agent_unknown`, exit 0
- Verdict: pass

### Item 16
- Item text: Live delivery is reported as queued, never as read.
- Approach: inspection
- Output (trimmed): `/aitask-note` Step 4 ("LIVE_QUEUED means enqueued, never read"), `claudecode.md` step 6, `note.md` Output section all agree; test_note_with_live_composition §6 pins the SKILL.md wording
- Verdict: pass (a live LIVE_QUEUED is item 22's subject)

### Item 17
- Item text: A FRESH session that has not read the t1657 plan finds `ait note` from always-loaded instructions alone.
- Approach: live observation + inspection
- Output (trimmed): this session never opened the t1657 plan and had `ait note` from CLAUDE.md "Sending Notes to Other Tasks"; `AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md` carry it as well
- Verdict: pass

### Item 18
- Item text: The aitask-note skill appears in the listing with a description conveying WHEN to use it.
- Approach: live observation
- Output (trimmed): this session's skill listing shows "aitask-note: Send a durable note to an existing aitask — … Use when you learn something a task that already exists depends on, such as a stale assumption in its body, a wider blast radius, or a decision that changes its approach."
- Verdict: pass

### Item 19
- Item text: Invoking the skill with an explicit target sends a note end-to-end with zero prompts.
- Approach: inspection + fixture
- Output (trimmed): 0 `AskUserQuestion` in the skill; Step 1 "The target is named, so ask nothing"; its single Step 2 command ran end-to-end in the fixture with no prompt (not invoked against a real task, to avoid writing a real inbox)
- Verdict: pass

### Item 20
- Item text: Invoking the skill without a target routes through Related Task Discovery.
- Approach: inspection
- Output (trimmed): Step 1 no-target path executes `.claude/skills/task-workflow/related-task-discovery.md` (`ai_filtered`, `min_eligible 1`); the file exists
- Verdict: pass

### Item 21
- Item text: A live-delivery failure after a successful durable write is reported as success with live delivery unavailable.
- Approach: fixture (documented `AIT_LIVE_ENDPOINT_SH` seam, silent exit-2 stub) + skill text
- Output (trimmed): `NOTE_APPENDED:…` / `LIVE_ERROR:resolver_unavailable`, exit 0, note on disk, committed; every `LIVE_NONE` case above also exited 0
- Verdict: pass

### Item 22
- Item text: Second live Claude session: /aitask-note end-to-end resolves LIVE_PANE, payload names the note id, reported LIVE_QUEUED.
- Approach: not automatable without an outward action
- Action run: none
- Output (trimmed): same blocker as item 10
- Verdict: defer (handed to the interactive loop)

## Cleanup

- Removed the scratch fixture (`scratchpad/av/fx_*`) and its private lock base
  (`scratchpad/av/lockbase_*`). The fixture's forged locks lived only on the
  fixture's own bare remote; no tmux session, window or pane was created.
