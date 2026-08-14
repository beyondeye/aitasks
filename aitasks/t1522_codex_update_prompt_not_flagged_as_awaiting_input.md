---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor, codex]
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-14 16:21
updated_at: 2026-08-14 16:21
---

`ait monitor` / `ait minimonitor` do not flag a followed **Codex** pane parked
on the startup **update-available prompt** as awaiting user input. The pane is
genuinely blocked — it will not proceed until the user picks an option — but no
`codex` entry in `PROMPT_PATTERNS_BY_AGENT`
(`.aitask-scripts/monitor/prompt_patterns.py:137-161`) matches it, so
`awaiting_input` stays False and the pane reads as merely idle.

Found live during t1509 while capturing shadow-readiness fixtures. It is not a
corner case: it renders on **every** `codex` launch while a newer version
exists, i.e. routinely, and it is the first thing on screen for a freshly
spawned agent — exactly when a user is most likely to be waiting on it.

## Evidence (codex-cli 0.146.0, captured 2026-08-14 via `capture-pane -p -e`)

The dialog renders an "Update available!" header line with the old and new
versions, a release-notes line, three numbered option rows (the selected one
carrying Codex's `›` composer glyph), and a bottom hint line reading
"Press enter to continue". The existing `codex_permission` pattern
(`Press enter to confirm or esc to cancel`) is close but does not match this
wording.

A raw ANSI capture of the exact screen is already committed as
`CODEX_UPDATE_PROMPT_RAW` in `tests/review_loop_fixtures.py` — reuse it rather
than re-capturing.

## Scope

Add a `codex` pattern covering this dialog, honouring the three rules in
`aidocs/framework/monitor_idle_and_prompt_detection.md`:

- **bottom-anchor it** — matching runs against the last
  `_PROMPT_DETECTION_TAIL_LINES` (6) lines, and the hint line is the bottom
  element; the header renders far above and would fall outside the window;
- **anchor on dialog structure, not a quotable phrase** — a bare
  "Press enter to continue" is generic prose that will eventually fire on text
  *about* the dialog; pair it with a second element that only co-occurs in the
  real widget;
- **do not paste the option block verbatim** into this task, a doc, or a plan —
  a verbatim reproduction is indistinguishable from the dialog itself when
  displayed in a pane. Describe it inline, as above.

Add the unit test in `tests/test_prompt_detection.py` asserting
`awaiting_input is True` and `awaiting_input_kind == "<new_name>"`, plus the
cross-agent negative controls that file already keeps, and a negative control
for each way prose could reproduce the anchor.

## Not affected

The minimonitor auto-recheck loop is **already safe** here: t1509's shadow
readiness excludes this dialog *structurally* (its option row is rendered with
the composer glyph and carries visible non-dim text), and that exclusion is
pinned by
`tests/test_review_loop.py::CodexShadowReadinessTests::test_the_unpatterned_update_prompt_is_a_dialog_not_typed_text`
plus the isolated-positive-half tests. This task is only about the **followed**
pane's `awaiting_input` signal.

## Coordination

- **t1467** — owns cross-agent phase/prompt detection and the per-agent prompt
  pattern inventory; this is squarely its territory.
- **t1509** — where the defect was found; its archived plan records the capture
  session.
