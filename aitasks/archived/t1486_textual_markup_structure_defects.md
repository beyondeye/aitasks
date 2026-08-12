---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tui, ui, aitask_monitor, minimonitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-11 19:54
updated_at: 2026-08-12 08:34
completed_at: 2026-08-12 08:34
---

## Origin

Spawned from t1453 during Step 8b review. t1453 fixed the *colour-resolution*
defect class (Textual silently drops style tokens it cannot parse). The scan it
built, plus incidental survey work, surfaced three defects of a **different**
class: markup **structure** — brackets that Textual parses as tags when they
were meant as literal text, and a closing tag that does not match its opening
tag. None is fixed by t1453.

All three were verified by mounting the literal string in a real Textual app
(textual 8.2.7) and reading the result, not inferred from the source.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:172,184 — the closing tags [/e24329] omit the '#' of the opening [#e24329]; Textual raises MarkupError("closing tag does not match any open tag") and the compositor crashes. Reachable from _issue_indicator/_pr_indicator for any task carrying a GitLab issue or MR URL.`
- `.aitask-scripts/monitor/monitor_app.py:1495 — "[bold yellow][AUTO][/]" renders as two spaces: the literal [AUTO] is consumed as an unknown tag, so the auto-switch badge is invisible exactly when auto-switch is on. Needs the bracket escaped.`
- `.aitask-scripts/logview/logview_app.py:74 — the header's [{state}] and " [raw]" are parsed as tags in a Static sink and vanish, so the live/paused/static and raw indicators never render.`

## Diagnostic context

Measured, one Static per case, size (70, 6):

| markup | result |
|---|---|
| `[#e24329]GL[/e24329]` | **CRASH** — `MarkupError: closing tag '[/e24329]' does not match any open tag` |
| `  [bold yellow][AUTO][/]` | renders `'  '` — the badge text is gone |
| `File: /var/log/x  [size: 4096]  [live] [raw]` | renders `'File: /var/log/x  [size: 4096]   '` — `[live]` and `[raw]` gone |

`[size: 4096]` survives because the space and colon make it an invalid tag, so
Textual leaves it alone — which is why the defect is easy to miss by eye: part
of the same string renders correctly.

The board case is the serious one: it is a hard crash on the compositor path,
not a silently-wrong pixel, and it fires on real data (any task whose `issue:`
frontmatter points at a GitLab host).

## Suggested fix

1. `aitask_board.py` — close with `[/]` (or the matching `[/#e24329]`) in both
   `_issue_indicator` and `_pr_indicator`.
2. `monitor_app.py` / `logview_app.py` — escape the literal brackets as `\[`,
   the convention already used at `tui_switcher.py:746,804` and
   `codebrowser/history_list.py:126`.
3. Consider extending `tests/test_textual_markup_colours.py` with a structural
   rule: t1453's Rule A validates a token's *style vocabulary* but not tag
   *pairing*, and it skips closing tags entirely, so none of these three is
   detectable by it today. A `Content.from_markup()` round-trip over the same
   candidate strings would catch the mismatched-close case; the
   literal-bracket cases need a heuristic (an all-caps or known-word token in a
   sink that renders markup) and may be better served by escaping conventions
   than by a scan.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-11T20:14:21Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-12T05:27:27Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-12T05:34:32Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:b7e6be04e834d1ab

> **✅ gate:risk_evaluated** run=2026-08-12T05:34:32Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1486/risk_evaluated_2026-08-12T05:34:32Z-risk_evaluated-a1.log`
