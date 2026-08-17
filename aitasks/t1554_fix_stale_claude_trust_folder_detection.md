---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [shadow, aitask_monitormini]
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-17 18:57
updated_at: 2026-08-17 18:57
---

## Origin

Spawned from t1540 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/prompt_patterns.py:118-120` — `claude_trust_folder` no
  longer matches Claude Code 2.1.233's workspace-trust dialog, so an agent blocked
  on the trust gate reads as **IDLE** in `ait monitor` / `ait minimonitor`. Two
  independent causes, either fatal on its own: the confirm/cancel options now
  render as a **numbered** list, which the adjacency pattern cannot match; and the
  pre-TUI trust screen draws **top-aligned**, so the whole dialog falls outside
  `_PROMPT_DETECTION_TAIL_LINES`. The existing unit tests still pass because they
  exercise synthetic snippets in the old geometry.

## Diagnostic context

Measured live during t1540 at 120x30 against 2.1.233, on a fresh untrusted
directory. The production classifier returned `awaiting_input=False` and
`awaiting_input_kind=''` for a fully-rendered trust dialog. Indexed layout: the
option rows sat at −17/−16, the footer at −14, and rows −13..−1 were blank — so
every one of the last six lines the matcher reads was empty.

t1474 anchored this pattern on the two option lines precisely *because* they were
then the bottom-most lines of the dialog and would land inside the tail window
whichever way the question wrapped. That premise no longer holds: this is the
pre-TUI boot screen, and it renders at the top of the pane.

This blocked t1540 from measuring a native-dialog boundary for the kind — a
boundary can never be consulted for a kind that is never reported — so
`("claude", "claude_trust_folder")` keeps its `DELIBERATELY_UNANCHORED_KINDS`
entry, now with this measurement as its reason instead of a placeholder. Fixing
the detection here is what would unblock a boundary row later, if one is wanted.

## Suggested fix

Re-measure the dialog live and re-anchor. Note the geometry problem is the harder
half: no wording change helps while the dialog renders outside the 6-line window,
so this may need the matcher's window to be revisited for pre-TUI screens rather
than only the regex. Capture requires a path that has **never** been opened by
Claude — the dialog renders once per untrusted path, and t1540 could not persist
a fixture for it for exactly that reason.

Keep the t1474 documentation rule: describe the option labels inline in prose,
never as a copied adjacent two-line block.
