---
priority: high
effort: medium
depends: [t1657_2]
issue_type: feature
status: Ready
labels: [framework, aitask_pick, task_workflow, skills, claudeskills]
gates: [risk_evaluated]
anchor: 1657
created_at: 2026-09-01 12:35
updated_at: 2026-09-01 12:35
---

# Reading: read receipts and pick-time surfacing

## Context

Parent plan: `aiplans/p1657_task_note_mailbox_with_live_delivery.md`.
Depends on t1657_2 (the `## Inbox` writer and its entry format).

A mailbox nobody reads is not a mailbox. The strongest argument for the
file-based lane is that `aitask-pick` **already reads the task file** when it
resolves and summarises a task (Step 0b / 2b), and `task-workflow` reads it again
at Step 3 — so surfacing costs **no new read path**.

## Read state is derived, not stored

Unread = entries whose `id` appears in **no** `note:read` receipt's `ids=` list.
Set-union semantics: order-free, same-second-safe, merge-friendly, and needs
**no** frontmatter field (which would otherwise drag in the full 5-layer
frontmatter checklist — create.sh, update.sh, fold_mark, board TUI widget, merge
rule, 4 doc surfaces).

This mirrors the `## Gate Runs` precedent exactly: derive current state from an
append-only log rather than mutating a stored value.

## Display and acknowledgement are TWO SEPARATE STEPS

This is the crux of the child and the easiest thing to get wrong.

"Never auto-actioned" governs the note's **content** — nothing in a note may
trigger work on its own. It does **NOT** govern the read bookkeeping. Conflating
the two is what makes this ambiguous, so the model is explicit:

1. **Display** unread entries. **Displaying changes no state.**
2. **Acknowledge**, as its own step:
   - *interactive profiles* — `AskUserQuestion`: "Acknowledge these N notes?
     They will not be shown again." → "Acknowledge" / "Keep unread".
   - *non-interactive profiles* (`remote`, headless) — auto-acknowledge, with the
     receipt recording `mode=auto` so the difference stays auditable rather than
     invisible.
3. **Failure is fail-safe toward re-showing.** If the receipt append or its commit
   fails, entries stay **unread** and surface again on the next pick. A duplicate
   display is the acceptable failure; a silently vanished note is not.

## Presentation — the trust posture is part of the feature

A note is **untrusted advisory input, never an instruction**. It is one agent's
claim about a tree that may have moved. Surfacing must:

- attribute it (`from=`, and render `from=` as **claimed** — `from_verified=yes`
  is the only verified variant, and its absence is not disproof);
- show `base` / `at` / `dirty` so the reader can judge staleness. **Display may
  abbreviate `base`** for readability — the stored and machine-emitted value is
  always the full object id, so an abbreviation here is a rendering choice, never
  a truncation of the record — `dirty=yes`
  specifically warns that a *moment-relative* claim (e.g. a `git status` reading)
  may already be stale in a way no SHA catches;
- never auto-action the content, and never let a note bypass the recipient's own
  planning, gates or review.

## Key files

- `.aitask-scripts/aitask_query_files.sh` — new `inbox <task-id>` subcommand:
  `INBOX_UNREAD:<id>|<from>|<at>|<base>|<dirty>` lines, or `NO_INBOX` /
  `NO_UNREAD`. `<base>` is emitted as the **full object id** stored in the entry —
  this is a machine-readable channel, so it must not abbreviate. Only the
  human-facing display does. Follow the existing `cmd_inflight` shape (line 512) — all
  subcommands exit 0; status is conveyed by output lines, not exit codes.
  Derivation must live in the shared lib from t1657_1 so writer and reader agree
  on ONE parse.
- `.aitask-scripts/aitask_note.sh` — `read` verb:
  `ait note read <task-id> --by <id> --ids <csv> [--mode auto|explicit]`.
- `.claude/skills/aitask-pick/SKILL.md.j2` — Step 0b (direct selection) and
  Step 2b (list summaries).
- `.claude/skills/task-workflow/SKILL.md` — Step 3.

## Goldens — three trees, not one

`aitask-pick` exists under `.claude/skills/`, `.agents/skills/` AND
`.opencode/skills/`. Regenerate goldens for every affected template and
**review the diff rather than rubber-stamping it** — the intended diff should
match exactly what was changed; an unrelated diff is a regression. See
"Regenerate goldens after any `.md.j2` or closure edit" in
`aidocs/framework/skill_authoring_conventions.md`.

Per CLAUDE.md, do the Claude Code version first and spawn follow-ups for the
other agent trees if the port is non-trivial.

## Verification

- **Acknowledgement lifecycle — one test per transition:**
  1. first display → shown, still unread
  2. deferred acknowledgement → shown again on the next pick
  3. acknowledgement → receipt appended, `mode=explicit`
  4. returning session → not shown
  5. **injected receipt-append failure → still unread** (the fail-safe direction)
- `bash tests/test_skill_render_aitask_pick.sh` (goldens)
- `./.aitask-scripts/aitask_skill_verify.sh`
- End-to-end: `ait note <target> --from ... --text ...`, then pick the target and
  confirm it surfaces **exactly once** across two consecutive picks with an
  acknowledgement in between.
