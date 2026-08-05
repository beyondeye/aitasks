---
Task: t1427_4_rejection_docs.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_1_rejection_store_helper.md, aitasks/t1427/t1427_2_picker_reject_tristate.md, aitasks/t1427/t1427_3_producer_suppression_rule.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# p1427_4 — Documentation for concern rejection + suppression

Documents the t1427 feature across the website and aidocs. Depends on
t1427_1..3 all landed. **Document CURRENT SOURCE, not this plan or the parent
plan** — behavior may have drifted during implementation; re-verify keybindings,
helper output lines, and store paths against the landed code and the archived
sibling plans (`aiplans/archived/p1427/`) before writing.

## Steps

1. **`website/content/docs/workflows/shadow-agent.md`** — in the concern
   block / selective-forwarding sections: the reject action (`r` per-row
   tri-state), the rejected-store view (`R`, with un-reject), the per-task
   persistence, and the next-round suppression: the shadow drops
   substantively-matching rejected concerns, reports
   "Suppressed N previously-rejected concern(s)." visibly, keeps unsure
   matches with a stated reason (fail-open), and states when suppression was
   skipped for lack of a task id.
2. **`website/content/docs/tuis/minimonitor/how-to.md`** — "How to Pick
   Shadow Concerns" + the keybinding table: add `r` / `R`; REMOVE every
   mention of the deleted `a` / `A` bulk shortcuts.
3. **`website/content/docs/tuis/monitor/how-to.md`** and
   **`reference.md`** — equivalent updates + the same `a`/`A` scrub.
4. **`aidocs/framework/shadow_agent.md`** — new `## Concern rejection store`
   section between `## Feedback freshness` (ends ~:339) and
   `## Configuration` (~:341): store path/format, helper subcommands as used
   by the TUIs and producers, the TUI write path, the producer consult path,
   archive-time pruning. FRAME AS PRODUCER-SIDE FILTERING, NEVER A GATE — the
   doc's no-gating principle (~:366-390: "Anything that inspects the followed
   agent's state to decide whether the user may proceed is the shape this
   rule forbids") must not be violated by the wording. Add one sentence to
   the Step 2 bullet (~:107) and to the sub-procedure list (~:110-142).

## Constraints

- Un-reject is TUI-only: do NOT document the helper's `remove` subcommand as
  a user-facing CLI (it is TUI machinery).
- `aidocs/framework/documentation_conventions.md`: current-state-only prose
  (no version history / "previously" narration); genericize agent naming
  where the passage would otherwise enumerate supported agents.
- Website workflows `_index.md` is a manually-maintained list — this task
  adds no new page, so no index bullet is needed; verify no new page is
  accidentally required.

## Verification

- `cd website && hugo build --gc --minify` clean.
- Sweep for stale content:
  `grep -rn "copy all\|toggle all" website/content/docs/tuis/ website/content/docs/workflows/shadow-agent.md`
  and a grep for `[a]`/`[A]` in the picker keybinding tables — no hits tied
  to the concern picker remain. (Test the grep finds hits BEFORE the edit so
  the zero-hit result after is meaningful.)
- Re-read the four updated pages end-to-end for coherence with the landed
  behavior.

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
