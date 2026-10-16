---
priority: medium
effort: high
depends: [t2038_2]
issue_type: feature
status: Ready
labels: [monitor]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

The classifier in the Go server (parent: Go monitor status server task).

## Source

- `monitor/ansi_utils.py` `strip_ansi` (SGR + OSC 8); compare modes
  (`COMPARE_MODE_STRIPPED` / `RAW`).
- `monitor/prompt_patterns.py`: the per-agent registry, per-pattern
  `skip_trailing_blank_rows`, the 6-line tail (`_PROMPT_DETECTION_TAIL_LINES`),
  `scope_patterns`; `classify_content` (`monitor_core.py:272`).
- `lib/agent_keys.py`: the agent-key ladder (pane command, then one level of
  children via `pgrep -P` + `ps -o comm=`), with provenance (`agent_key`,
  `scoped`).

## Pitfalls

See the parent: RE2 vs Python `re` (`\s`, `\w`, `\b`, `splitlines`). The 6-line
tail makes line splitting part of the contract.

## Verification

Unit tests per pattern from `tests/test_prompt_detection.py`'s fixtures. The
full Python↔Go differential is t2034_6.
