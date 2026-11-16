---
priority: low
effort: low
depends: [t2278_7]
issue_type: chore
status: Ready
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 8 of t2278 (docs TUI screenshot generator): the retrospective evaluation.
It runs last, after the other children. Child 7 (real pixels) is optional;
evaluate whatever state it ended in.

The parent plan `aiplans/p2278_docs_tui_screenshot_generator.md` was revised
on 2026-11-15, before any capture existed, from headless adapters to an agent
driving the real TUI in an isolated tmux session. This child checks that
design against what the two real passes (child 5 on the placeholders, child 6
on the 18 older images) actually needed. The implemented design is the
baseline; each item below is a question with a pass / change verdict, decided
from evidence in the archived child plans and the repository.

The questions were rewritten together with the design revision, before any
evidence existed. Do not add or drop questions to fit what is found.

## Questions to answer

1. **Recipe replay rate.** Run `replay --all`. How many recipes reach their
   expected texts without an edit? List each that does not, and why.
2. **Repairs.** How many recipes were repaired in children 5 and 6? For each:
   was it a failed replay, or a passing one that no longer matched its page?
   Did the skill repair it, or report it?
3. **Missing primitives.** Which things did the agent need that the verbs did
   not offer (recorded in the notes of children 3-6)? Which verbs were never
   used?
4. **Setup contract.** How many recipes use `setup` commands, and how many
   needed a new dataset? Did `recipe save` ever refuse a state that depended
   on unrecorded preparation? Did any scene get reported because its data
   could not be built?
5. **The agent's choice of state.** At the user's reviews in children 5 and
   6, how often was the chosen state accepted as is, and how often did the
   user ask for a different one?
6. **No byte identity.** Did images differ between a reviewed batch and a
   later replay in ways that caused review churn? List the sources (clocks,
   timers, cursor).
7. **Apply safety.** Did any `REFUSED:` outcome occur in the two passes, and
   was the refusal correct?
8. **Marker grammar.** Did doc authors or the skill hit a limit (the `"` and
   `--` rule, one line only)?
9. **Realism of multi-pane scenes.** Do the stand-in agent panes look like
   real use, per the user's review?
10. **Isolation.** Was a tmux server, a temp project or a headless output
    ever left behind? Did anything from the user's own config reach a screen?
11. **Port tasks.** Were the Codex CLI and OpenCode port tasks created?

## Key Files

Read-only for the evaluation: `aiplans/archived/p2278/`,
`website/screenshots/`, `website/check_screenshots.py`,
`aidocs/framework/docs_screenshots.md`. Changes that a verdict calls for
become new tasks; small doc corrections may land here.

## Verification Steps

- Each of the eleven questions has a written verdict with its evidence in the
  plan's Final Implementation Notes.
- Every "change" verdict has a follow-up task, or a stated reason for none.
- `python3 website/check_screenshots.py --strict` and
  `cd website && python3 check_links.py --build` pass.
