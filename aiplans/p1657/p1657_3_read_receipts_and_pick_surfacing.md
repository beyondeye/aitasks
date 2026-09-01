---
Task: t1657_3_read_receipts_and_pick_surfacing.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_1_*.md, aitasks/t1657/t1657_2_*.md, aitasks/t1657/t1657_4_*.md, aitasks/t1657/t1657_5_*.md, aitasks/t1657/t1657_6_*.md
Base branch: main
Output branch: main
---

# p1657_3 — Reading: read receipts and pick-time surfacing

## Goal

Unread notes are shown when a task is picked, and a returning session is not
re-shown what it already consumed. Costs **no new read path**: `aitask-pick`
already reads the task file at Step 0b / 2b, and `task-workflow` again at Step 3.

## Main steps

### 1. Derivation in the shared lib (t1657_1 seam)

Unread = entries whose `id` appears in **no** `note:read` receipt's `ids=` list.
Set-union semantics: order-free, same-second-safe, merge-friendly, and needs
**no** frontmatter field. Mirrors the `## Gate Runs` precedent — derive state
from an append-only log rather than mutating a stored value.

Writer and reader must share **one** parse; do not add a second.

### 2. `aitask_query_files.sh inbox <task-id>`

Follow the `cmd_inflight` shape (line 512). All subcommands exit 0; status is
conveyed by output lines:

```
INBOX_UNREAD:<id>|<from>|<at>|<base>|<dirty>
NO_INBOX          # no ## Inbox section
NO_UNREAD         # section present, everything acknowledged
```

Add it to `show_help` and the header usage comment.

### 3. `ait note read`

`ait note read <task-id> --by <id> --ids <csv> [--mode auto|explicit]` appends
the receipt block via the seam and commits path-scoped, exactly as the write path
does.

### 4. Display and acknowledgement are TWO SEPARATE STEPS

The crux of this child.

"Never auto-actioned" governs the note's **content** — nothing in a note may
trigger work on its own. It does **not** govern read bookkeeping. Conflating them
is what makes this ambiguous.

1. **Display** unread entries. **Displaying changes no state.**
2. **Acknowledge**, its own step:
   - interactive profiles — `AskUserQuestion`: "Acknowledge these N notes? They
     will not be shown again." → "Acknowledge" / "Keep unread";
   - non-interactive (`remote`, headless) — auto-acknowledge, receipt records
     `mode=auto` so the difference is auditable rather than invisible.
3. **Fail-safe toward re-showing.** If the receipt append or its commit fails,
   entries stay **unread** and surface again next pick. A duplicate display is
   the acceptable failure; a silently vanished note is not.

### 5. Presentation — the trust posture is part of the feature

- attribute the sender, and render `from=` as **claimed**; `from_verified=yes` is
  the only verified variant, and its absence is not disproof;
- show `base` / `at` / `dirty` so staleness is judgeable — `dirty=yes` warns that
  a *moment-relative* claim may already be stale in a way no SHA catches;
- never auto-action content; a note never bypasses the recipient's own planning,
  gates or review.

### 6. Skill edits + goldens

- `.claude/skills/aitask-pick/SKILL.md.j2` — Step 0b and Step 2b
- `.claude/skills/task-workflow/SKILL.md` — Step 3

Regenerate goldens for every affected template and **review the diff rather than
rubber-stamping it**: the intended diff should match exactly what changed; an
unrelated diff is a regression. See "Regenerate goldens after any `.md.j2` or
closure edit" in `aidocs/framework/skill_authoring_conventions.md`.

`aitask-pick` exists under `.claude/skills/`, `.agents/skills/` and
`.opencode/skills/`. Per CLAUDE.md, do the Claude Code version first and spawn
follow-ups for the other trees.

## Verification

- **Acknowledgement lifecycle, one test per transition:** first display (shown,
  unread) · deferred acknowledgement (shown again next pick) · acknowledgement
  (receipt appended, `mode=explicit`) · returning session (not shown) ·
  **injected receipt-append failure (still unread)**
- `bash tests/test_skill_render_aitask_pick.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests`
- end-to-end: send a note, pick the target twice with an acknowledgement in
  between, confirm it surfaces **exactly once**

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **low**

- Goldens across three agent trees and three profiles drift independently ·
  severity: low · → mitigation: existing `test_skill_render_*` +
  `aitask_skill_verify.sh`

### Goal-achievement risk: **low**

- The acknowledgement model is specified per-transition and each transition has a
  test, so "surfaces exactly once" is falsifiable rather than asserted.
- Residual: the receipt model assumes a note consumed on one PC should not
  resurface on another · severity: low · → mitigation: recorded as a decision in
  `aidocs/` (t1657_6)
