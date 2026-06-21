---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitormini, shadow, tui]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 11:41
updated_at: 2026-06-21 12:55
---

## Context

Foundation child of t1037 (minimonitor shadow concern picker). This task pins
the **concern-block format** — the contract shared by the shadow skill (the
producer, child t1037_2) and the minimonitor modal (the consumer, t1037_3 /
t1037_4) — and ships the **pure parser** that turns a captured shadow-pane
snapshot into structured concern items. Testability-first: the parser is the
pure headless unit, so it is pulled out first and unit-tested in isolation,
and the format's machine enforcement lives next to its written spec.

See the parent task t1037 for the end-to-end target flow and constraints.

## The agreed format (proposal — finalize with a round-trip test)

ASCII-sentinel-fenced block; one concern per `- [priority | region]` marker,
body wrap-joined onto continuation lines:

```
===AITASK-CONCERNS===
- [high | Step 7 ownership guard] The guard re-runs aitask_pick_own.sh which
  double-commits when the lock was already held...
- [medium | parser module] Multi-block accumulation is undefined when the
  shadow re-issues concerns.
===END-CONCERNS===
```

Design rationale / constraints (MUST hold):
- **Survives tmux capture.** `tmux capture-pane` returns *visually wrapped*
  lines, so a long concern is split across capture lines. The parser MUST
  rejoin: a line matching the item marker starts a new concern; any other
  non-blank line between the fences appends (space-joined) to the current
  concern's body. Add a round-trip test that wraps a long line at ~40 cols
  and asserts it rejoins.
- **ASCII sentinel fence** (`===AITASK-CONCERNS===` / `===END-CONCERNS===`) so
  it round-trips without escape damage and does NOT collide with markdown
  ``` fences common in agent output. (Rejected alternatives: unicode fences —
  escape risk; pure one-line `|`-delimited — wrapping splits the logical line;
  YAML-in-fence — heavier parser, more failure modes.)
- **Each concern carries:** priority (`high`/`medium`/`low`), region (free-text
  plan-region label), body (free text). Priority parsing is case-insensitive;
  an unknown priority degrades to `low` (do not drop the item).
- **Robustness:** ignore a block missing its closing fence's tail gracefully
  (parse to EOF), trim whitespace, skip blank lines, tolerate the marker with
  or without a leading list dash.

The exact sentinel string and grammar are this task's decision — finalize them
against a real `aitask_shadow_capture.sh` round-trip before locking.

## Key files to create

- `aidocs/framework/shadow_concern_format.md` — the canonical written spec:
  the fence, the per-item grammar, the wrap-join rule, priority/region/body
  semantics, and a worked example. This is the single source of truth that
  child t1037_2 (shadow prompt) and t1037_3/_4 (parser consumers) both cite.
  Add a pointer to it from `aidocs/framework/shadow_agent.md` (the shadow doc).
- `.aitask-scripts/monitor/concern_parser.py` — pure module, sibling to
  `prompt_patterns.py` / `monitor_shared.py`. NO tmux, NO Textual imports.
  - `Concern` as a `NamedTuple(priority: str, region: str, body: str)` (match
    the repo's NamedTuple registry-record convention, e.g. t1029).
  - `parse_concerns(capture_text: str) -> list[Concern]` — extract from a
    capture buffer (handles the wrap-join described above; returns `[]` when no
    block is present).
  - `build_clipboard_payload(concerns: list[Concern], preamble: str) -> str`
    — pure builder: preamble line + selected concern blocks verbatim, in order.
    Default preamble: `"I have some concerns: please verify them and if valid
    please address in the plan"`. Keeping it pure (no Textual) makes both the
    modal confirm path and the "copy ALL" fast path reuse one tested function.
  - Optional helper `has_concern_block(text) -> bool` for the auto-offer
    trigger in t1037_4 (cheap sentinel presence check).

## Reference files for patterns

- `.aitask-scripts/monitor/prompt_patterns.py` — module shape, `@dataclass`/
  frozen conventions, framework-constant style (no project_config surface).
- `.aitask-scripts/aitask_shadow_capture.sh` — produces the cleaned capture
  text the parser consumes (use it to generate the round-trip test fixture).
- Existing Python unit tests: `tests/test_board_*.py`,
  `tests/test_config_utils.py` — for the test harness shape (pytest-style).

## Implementation plan

1. Decide and document the format in `shadow_concern_format.md`.
2. Implement `concern_parser.py` with the three functions + `Concern` tuple.
3. Write `tests/test_concern_parser.py`:
   - parses a canonical block into the right Concerns;
   - wrap-join round-trip (long body split across ~40-col lines rejoins);
   - no-block input → `[]`;
   - unknown/missing priority → `low`, item retained;
   - `build_clipboard_payload` emits preamble + verbatim selected blocks in
     order;
   - multi-block input (document & test the chosen policy — accumulate vs
     last-wins; see parent open question, recommend "last block wins" since a
     re-issued review supersedes).
4. Run the test; run `shellcheck` only if any shell was touched (none expected).

## Verification steps

- `python3 -m pytest tests/test_concern_parser.py` (or the repo's invocation
  for `.py` tests) passes.
- Feed a real capture: run the shadow producer format by hand through
  `./.aitask-scripts/aitask_shadow_capture.sh -` and confirm
  `parse_concerns` extracts the items intact.

## Notes for sibling tasks

- The spec file and `Concern`/`build_clipboard_payload` signatures are the
  contract. t1037_2 must emit exactly this format; t1037_3 imports `Concern`
  and renders it; t1037_4 calls `has_concern_block` + `parse_concerns` +
  `build_clipboard_payload`. Record the final sentinel string prominently in
  the Final Implementation Notes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T09:55:16Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T09:55:17Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-21T10:20:11Z status=pass attempt=1 type=human
