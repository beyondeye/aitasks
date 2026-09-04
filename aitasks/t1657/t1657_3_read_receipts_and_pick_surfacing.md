---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1657_2]
issue_type: feature
status: Implementing
labels: [framework, aitask_pick, task_workflow, skills, claudeskills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
implemented_with: claudecode/opus5
created_at: 2026-09-01 12:35
updated_at: 2026-09-04 00:06
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1657_2** id=2026-09-02T06:19:07Z.6d05e279360b685aeb3e750c from=t1657_2 from_verified=yes at=2026-09-02T06:19:07Z base=65e74bb50e9df1d85026ddfc2e7e421f881e2f9e base_branch=main dirty=yes host=omg16
>
> | Advisory input from the t1657_2 session, not an instruction. The ## Inbox
> | format and `ait note` are now live on main — you are the first consumer that
> | did not have to build them.
> | 
> | Two things that will cost you time if you meet them cold:
> | 
> | 1. ait_ledger_lock_exit_trap MUST be the first command in your trap string.
> |    It reads $? on entry, so `trap 'my_cleanup; ait_ledger_lock_exit_trap' EXIT`
> |    silently resets the status to my_cleanup's and reports a died section as
> |    SUCCESS. Measured here: a release die exited 0 and the writer emitted
> |    NOTE_APPENDED for a wedged lock. Use:
> |      trap 'rc=$?; my_cleanup; (exit $rc); ait_ledger_lock_exit_trap' EXIT
> |    Filed as t1681 to fix upstream; until it lands, this is on you.
> | 
> | 2. INBOX_SPEC.validate now enforces an EXACT key set per variant, and the
> |    receipt half is already written for you: id, by, at, mode (auto|explicit),
> |    ids — and receipts must carry NO provenance fields. Adding a key without
> |    adding it to _RECEIPT_KEYS_REQUIRED/_OPTIONAL in aitask_merge.py will make
> |    every receipt bail the cross-PC union to conflict markers. See
> |    tests/test_inbox_union_roundtrip.py::InboxUnknownKeyTest for the shape.
> | 
> | Also note `ait note` already reserves the `read` marker name and the writer
> | refuses self-addressed notes, so a receipt naming its own task is fine.

> **👁 note:read** id=2026-09-03T21:34:17Z.c7497c874a307a62b987c303 by=t1657_3 at=2026-09-03T21:34:17Z mode=explicit ids=2026-09-02T06:19:07Z.6d05e279360b685aeb3e750c

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-03T21:06:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-04T08:54:28Z status=pass attempt=1 type=human
