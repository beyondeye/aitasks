---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [minimonitor, shadow]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-18 12:50
updated_at: 2026-09-18 12:52
---

## Context

When the user copies selected shadow concerns to the clipboard from `ait minimonitor`
(or `ait monitor`), the payload starts with a fixed preamble:

> I have some concerns: please verify them and if valid please address in the plan

The same preamble is used for concerns raised against a **plan** and for concerns
raised during **implementation** (shadow impl-challenge rounds). "address in the
plan" is plan-specific wording. Agents usually understand it anyway, but at least
once an agent that received implementation concerns after implementing went back
to rewrite the plan instead of fixing the code.

## Change

Make the preamble work for both phases by ending it with "address them":

> I have some concerns: please verify them and if valid please address them

## Where

- `.aitask-scripts/monitor/concern_parser.py:243`: the `DEFAULT_PREAMBLE`
  constant. It is used only as the default of `build_clipboard_payload()`
  (line ~916), and every caller takes that default:
  `minimonitor_app.py:~5061`, `monitor_shared.py:~1844, ~5638, ~5677` (the
  monitor goes through the shared module). Changing the constant covers every
  copy path.
- `tests/test_concern_parser.py:~3087`: `test_clipboard_payload_is_byte_identical`
  contains the old text as a literal. Update it to the new wording. The
  assertion at line ~193 compares against the `DEFAULT_PREAMBLE` constant, so it
  follows the change without an edit.

The exact wording appears nowhere in the website docs or the skills.

## Verification

- `python3 -m pytest tests/test_concern_parser.py` (or
  `bash tests/run_all_python_tests.sh --test-dir ...`) passes.
- `grep -rn "address in the plan" .aitask-scripts tests` finds nothing.
