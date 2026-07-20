---
priority: medium
effort: medium
depends: [t1186_2]
issue_type: refactor
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1149
created_at: 2026-07-20 19:30
updated_at: 2026-07-20 19:30
---

## Context

Third slice of t1186 (chatlink wizard live allowlist pickers), after t1186_1
(authorization modes) and t1186_2 (Discord fetch surface). Structural wizard refactor so
the allowlist step can fetch live data: the bot token (and the optional live check) must
come BEFORE the allowlist step. Also removes the two coupling points that make
reordering fragile: hardcoded per-class "Step N/7" title strings and the hardcoded class
tuple in `make_step()` that decides which screens receive seams.

New `_STEPS` order: `IntakeChannelScreen(1), TokenScreen(2), LiveCheckScreen(3),
AllowlistScreen(4), DenyRepoScreen(5), CeilingsScreen(6), SummaryScreen(7)`.
`LiveCheckScreen` reads only `provider/token/workspace_id/conversation_id/thread_id`,
all set by steps 1-2, so the move is safe.

## Current state (verified 2026-07-20)

- `_STEPS` tuple: `wizard.py:697-698` — currently
  `IntakeChannelScreen, AllowlistScreen, DenyRepoScreen, CeilingsScreen, TokenScreen,
  LiveCheckScreen, SummaryScreen`.
- Navigation `start_wizard()` :665-694 is purely index-based (BACK/NEXT/DONE sentinels
  :48-50); `make_step(idx)` :674-679 passes the `seams` arg only to a hardcoded tuple
  `(TokenScreen, LiveCheckScreen, SummaryScreen)`.
- Hardcoded `step_title` literals, one per class: IntakeChannelScreen :224-225,
  AllowlistScreen :256, DenyRepoScreen :291, CeilingsScreen :312, TokenScreen :346,
  LiveCheckScreen :385, SummaryScreen :510. Base `_WizardStep.compose()` renders
  `self.step_title` into `Label(id="wizard_title")` at :181.
- `WizardSeams` dataclass :68-79; `resolve_seams()` :82-94.
- TUI tests assert step progression by SCREEN CLASS `isinstance`, not title strings
  (`tests/test_chatlink_tui.sh:290-563`).

## Key files to modify

- `.aitask-scripts/chatlink/wizard.py`:
  1. `_WizardStep` gains class attr `step_name: str` (title text WITHOUT numbering) and
     keyword args `step_no: int = 0`, `step_total: int = 0` on `__init__`; base
     `compose()` renders `f"Step {step_no}/{step_total} — {step_name}"` into
     `#wizard_title`. Replace all 7 `step_title` literals with `step_name` (keep the
     descriptive text; AllowlistScreen keeps its current wording — t1186_4 revises it).
  2. Seam needs declared on the class: `needs_seams: bool = False` on `_WizardStep`;
     `True` on `TokenScreen`, `LiveCheckScreen`, `SummaryScreen` (t1186_4 adds
     `AllowlistScreen`). `make_step()` branches on `cls.needs_seams` and derives
     `step_no=idx+1`, `step_total=len(_STEPS)` — delete the hardcoded class tuple.
  3. Reorder `_STEPS` to the order above.
- `tests/test_chatlink_tui.sh`: reorder the pilot walkthrough input sequences and the
  `isinstance` progression assertions (:290-563) to the new step order (intake →
  token → live check → allowlist → deny/repo → ceilings → summary); add one assertion
  that a rendered `#wizard_title` shows the derived `Step N/7` string for a
  representative screen (e.g. TokenScreen → "Step 2/7").

## Reference files for patterns

- `_ReplaceConfirmScreen` (:459) is a bare ModalScreen, not in `_STEPS` — no numbering.
- Existing walkthrough fakes and app seam wiring: `tests/test_chatlink_tui.sh:229-275`,
  `chatlink_app.py:109-129,167-175` (unchanged in this child).

## Implementation plan

1. Base-class numbering + `step_name` conversion (all 7 screens).
2. `needs_seams` declaration + `make_step()` rewrite.
3. `_STEPS` reorder.
4. Test walkthrough reorder + derived-title assertion.

## Verification

- `bash tests/test_chatlink_tui.sh` green with the new order: escape-abort, restart,
  Back-retains-state, empty-allowlist double-Next, live-check spy (not called before
  validate; skip path; advisory failure; mid-run dismiss generation guard app4), save /
  replace-confirm / token-write failure paths — all still pass reordered.
- `bash tests/test_chatlink_wizard.sh` green (headless helpers untouched).
- Manual sanity: wizard walk shows derived numbering on every screen with no "N/7"
  drift (aggregate manual-verification sibling covers the live walkthrough).
