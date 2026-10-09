---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent, models]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1916
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 17:01
updated_at: 2026-10-09 00:12
---

## Origin

Spawned from t1916 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_codeagent.sh:167 — format_claude_model_label only matches claude-<family>-<maj>-<min>[-date], so [1m] ids (claude-opus-5-5[1m], claude-sonnet-5-5[1m], now claude-haiku-5-5[1m]) and major-only ids (claude-opus-5) yield the raw cli_id as the Co-Authored-By name, e.g. "Claude Code/claude-opus-5-5[1m]"`

## Diagnostic context

While registering `claudecode/haiku5_5` / `haiku5_5_1m` (t1916), a read-only check
of `ait codeagent coauthor` on the existing registry gave (2026-10-08):

- `claudecode/sonnet5_5`    → `Claude Code/Sonnet 5.5` (correct)
- `claudecode/haiku4_5`     → `Claude Code/Haiku 4.5` (correct; date suffix stripped)
- `claudecode/sonnet5_5_1m` → `Claude Code/claude-sonnet-5-5[1m]` (raw id)
- `claudecode/opus5_5_1m`   → `Claude Code/claude-opus-5-5[1m]` (raw id)
- by the regex, `claude-opus-5` / `claude-sonnet-5` / `claude-opus-5[1m]` (no minor)
  also fall through to the raw id.

The regex in `format_claude_model_label()` is
`^claude-([a-z]+)-([0-9]+)-([0-9]+)(-[0-9]+)?$`: it requires a minor version and
rejects any `[1m]` suffix. The resulting raw id lands in the `Co-Authored-By`
trailer of every commit made by a 1M-context or major-only Claude session.

`aitask_codeagent.sh` had another session's uncommitted edits at the time
(27 added lines), so the fix was not folded into t1916. Check the file's
state before editing.

## Suggested fix

Make the minor version optional and accept an optional `[1m]` suffix, e.g.
`^claude-([a-z]+)-([0-9]+)(-([0-9]+))?(-[0-9]{8})?(\[1m\])?$`. Label `[1m]` ids
as `<Family> <ver> (1M)` (or decide on a label that matches Claude Code's own
"(1M context)" wording), and keep `haiku4_5`'s date-suffix stripping
(tests/test_codeagent.sh Test 21). Add assertions for the `_1m` and major-only
cases in tests/test_codeagent.sh.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-08T21:12:04Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-09T04:52:41Z status=pass attempt=1 type=human
