---
Task: t1840_minimonitor_concern_preamble_phase_neutral.md
Base branch: main
Output branch: main
---

# t1840: Make the concern clipboard preamble phase-neutral

## Context

`ait minimonitor` / `ait monitor` copy selected shadow concerns to the clipboard
with a fixed preamble that ends "...please address in the plan". The same payload
carries concerns from plan-review rounds and from implementation-review
(impl-challenge) rounds. The plan-specific wording has at least once led an
agent that received post-implementation concerns to go back and rewrite the plan
instead of fixing the code. Changing the preamble to end with "address them"
makes it correct for both phases.

## Steps

1. `.aitask-scripts/monitor/concern_parser.py:243-246`: change `DEFAULT_PREAMBLE`:
   ```python
   DEFAULT_PREAMBLE = (
       "I have some concerns: please verify them and if valid "
       "please address them"
   )
   ```
   No caller passes its own `preamble=` (minimonitor_app.py:5061,
   monitor_shared.py:1844/5638/5677 all use the default of
   `build_clipboard_payload()`), so this one edit covers every copy path.

2. `tests/test_concern_parser.py:3086-3087`
   (`test_clipboard_payload_is_byte_identical`): update the literal to
   `"please address them\n"`. The assertion at line 193 references the
   `DEFAULT_PREAMBLE` constant, so it needs no edit.

## Verification

- `python3 -m pytest tests/test_concern_parser.py -q` (or unittest if pytest is
  unavailable) passes.
- `grep -rn "address in the plan" .aitask-scripts tests` returns nothing.

## Step 9 (Post-Implementation)

Current-branch mode (profile 'fast'): commit the code change with
`enhancement: Make concern clipboard preamble phase-neutral (t1840)`, then run
the standard archival.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Changed `DEFAULT_PREAMBLE` in `.aitask-scripts/monitor/concern_parser.py` to end with "please address them" instead of "please address in the plan". Updated the pinned literal in `tests/test_concern_parser.py` (`test_clipboard_payload_is_byte_identical`) to match.
- **Deviations from plan:** None.
- **Issues encountered:** None. `tests/test_concern_parser.py`: 184 passed.
- **Key decisions:** Changed only the shared constant. Every clipboard path (minimonitor, and monitor through `monitor_shared.py`) uses `build_clipboard_payload()`'s default preamble, so no caller needed an edit.
- **Upstream defects identified:** None
