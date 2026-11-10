---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [trails]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-10 08:59
updated_at: 2026-11-10 13:41
completed_at: 2026-11-10 13:41
---

## Origin

Spawned from t2211_10 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/artifact_manifest.py:58` — `HANDLE_RE` ends in `$`, so it also matches a handle with a trailing newline (`"art:a\n"`). Its validators (`launch_or_focus_trails`, `trails_app.main --trail`) therefore accept a newline-terminated handle.

## Diagnostic context

t2211_10 added a trails mailbox payload grammar, `_TRAILS_TARGET_RE` in `lib/agent_launch_utils.py`, that is meant to be "`HANDLE_RE`'s handle grammar plus an optional task id". A grammar-equality test (`tests/test_trails_focus_writer.py::TrailsTargetParseTests::test_the_target_grammar_is_the_handle_and_task_id_grammars`) found the one difference: Python's `$` also matches just before a final `\n`, while the new grammar ends in `\Z`.

```python
HANDLE_RE.match("art:a\n")          # matches
_TRAILS_TARGET_RE.match("art:a\n")  # None
```

The test now pins that difference as deliberate. The new grammar is the stricter one, because the value is untrusted input. `HANDLE_RE` itself was left alone, as out of scope.

Where `HANDLE_RE.match` is the gate for untrusted or user-supplied handles:
- `launch_or_focus_trails` (`lib/agent_launch_utils.py`) validates the handle and then writes `"<id> <handle>"` into a tmux pane option;
- `board/trails_app.py` `main()` validates `--trail`.

There are likely more (`grep -rn "HANDLE_RE" .aitask-scripts`). The sibling regexes there (`HASH_RE`, `BACKEND_RE`) use the same `$` form.

## Suggested fix

Anchor with `\Z` (or use `fullmatch`) in `artifact_manifest.HANDLE_RE`, and check `HASH_RE` / `BACKEND_RE` the same way.
- Grep every `HANDLE_RE` consumer, including ones that match on stored or frontmatter values where a newline may be legitimately stripped first.
- Add a regression case per consumer for `"art:a\n"`.
- Keep `tests/test_trails_focus_writer.py`'s grammar-equality test in step: once `HANDLE_RE` is fixed, the special-case assertion there flips (both refuse).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T09:41:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-10T11:18:15Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-10T11:41:01Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:2134107bf6c3768e

> **✅ gate:risk_evaluated** run=2026-11-10T11:41:01Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2269/risk_evaluated_2026-11-10T11:41:01Z-risk_evaluated-a1.log`
