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
It runs last, after the other children. Child 7 (the real-pixel backend) is
optional; evaluate whatever state it ended in.

The parent plan `aiplans/p2278_docs_tui_screenshot_generator.md` took several
decisions before any capture existed. This child checks each against what the
two real passes (child 5 on the 17 placeholders, child 6 on the 18 older
images) actually needed. The implemented design is the baseline; each item
below is a question with a pass / change verdict, decided from evidence in the
archived child plans and the repository.

## Questions to answer

1. **Scene spec format.** Which fields were used by no scene? Which needs were
   met by adapter code instead of a spec field? Count the scenes that needed a
   one-off adapter hook.
2. **Pinned look.** Did one theme and the default sizes suit all images, or do
   some scenes override them? List the overrides.
3. **Coupling to test fixtures.** The tool imports `tests/lib/board_fixture.py`
   and copies patterns from individual test modules. Did any fixture change
   since child 2 break a capture, and did a test catch it?
4. **Byte stability.** Run `capture --all` twice and compare. List any scene
   that differs and why.
5. **Apply safety.** Did any `REFUSED:` outcome occur in the two passes, and
   was the refusal correct?
6. **Marker grammar.** Did doc authors or the skill hit a limit (the `"` and
   `--` rule, one line only)?
7. **Composite realism.** Do the tmux composites look like the real thing, per
   the user's review in child 5?
8. **Port tasks.** Were the Codex CLI and OpenCode port tasks created?

## Key Files

Read-only for the evaluation: `aiplans/archived/p2278/`,
`website/screenshots/`, `website/check_screenshots.py`,
`aidocs/framework/docs_screenshots.md`. Changes that a verdict calls for
become new tasks; small doc corrections may land here.

## Verification Steps

- Each of the eight questions has a written verdict with its evidence in the
  plan's Final Implementation Notes.
- Every "change" verdict has a follow-up task, or a stated reason for none.
- `python3 website/check_screenshots.py --strict` and
  `cd website && python3 check_links.py --build` pass.
