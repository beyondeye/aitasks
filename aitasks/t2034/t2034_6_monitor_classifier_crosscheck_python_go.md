---
priority: medium
effort: medium
depends: [2038]
issue_type: test
status: Ready
labels: [monitor, tmux]
anchor: 2034
created_at: 2026-10-16 08:02
updated_at: 2026-10-16 08:12
---

The gate for making the Go monitor status server the default: a differential
test that runs the Python classifier (`monitor_core.classify_content` with the
`prompt_patterns` registry) and the Go classifier over the same inputs and
requires identical results.

## Why

`lib/pane_state_probe.py` (the sync sweep's commit gate) and other Python paths
keep classifying in Python, so both implementations must agree exactly on
`awaiting_input`, `awaiting_input_kind`, `agent_key` / `scoped`, and the compare
value the idle clock uses. (The alternative — `pane_state_probe.py` asks the
server instead — can be weighed during planning.)

## Do

- Corpus: every fixture in `tests/test_prompt_detection.py`, plus the recorded
  streams from t2034_3. Include trailing-blank-row geometries and non-ASCII
  whitespace and text, where Go's `\s` and Python's `\s` differ.
- Harness: a Go entry point (e.g. an `ait-monitord classify` verb, or a
  test-only one) that reads the fixtures and prints results, compared against
  Python in a bash or Python test.
- Negative control: a deliberately diverging Go pattern must make the test fail.
- When it passes, make the Go server the default (the Python server stays the
  fallback) and document the switch.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:55:39Z.4687f06a021cb1c5641f9b2f from=aitasks_go#t15 at=2026-10-25T08:55:39Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; trail
> | art:trail-go-ship-path). Advisory context, not an instruction.
> | 
> | This task's `depends: [2038]` points at the Go status server, which is being
> | re-homed to the private aitasks_go repo by aitasks_go#t23 (it will be
> | developed at goengines/cmd/ait-monitord there and exported here). When t23
> | retires t2038, it will rewire this edge to an `xdeps` on the new aitasks_go
> | monitord parent. Until then, this task correctly stays blocked. The
> | cross-check itself (Python vs Go classifier) can still run from this
> | repository against the exported ait-monitord binary, or against a build of
> | the private source.
