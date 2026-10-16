---
priority: medium
effort: medium
depends: [t2034_5]
issue_type: test
status: Ready
labels: [monitor, tmux]
anchor: 2034
created_at: 2026-10-16 08:02
updated_at: 2026-10-16 08:02
---

The gate for making the Go monitor status server (child 5) the default: a
differential test that runs the Python classifier
(`monitor_core.classify_content` with the `prompt_patterns` registry) and the Go
classifier over the same inputs and requires identical results.

## Why

`lib/pane_state_probe.py` (the sync sweep's commit gate) and other Python paths
keep classifying in Python, so both implementations must agree exactly on
`awaiting_input`, `awaiting_input_kind`, `agent_key` / `scoped`, and the compare
value the idle clock uses. (The alternative — `pane_state_probe.py` asks the
server instead — can be weighed during planning.)

## Do

- Corpus: every fixture in `tests/test_prompt_detection.py`, plus the recorded
  streams from child 3. Include trailing-blank-row geometries and non-ASCII
  whitespace and text, where Go's `\s` and Python's `\s` differ.
- Harness: a Go entry point (e.g. an `ait-monitord classify` verb, or a
  test-only one) that reads the fixtures and prints results, compared against
  Python in a bash or Python test.
- Negative control: a deliberately diverging Go pattern must make the test fail.
- When it passes, make the Go server the default (the Python server stays the
  fallback) and document the switch.
