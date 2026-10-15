---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 08:50
updated_at: 2026-10-15 10:42
completed_at: 2026-10-15 10:42
---

## Origin

Spawned from t1977 during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/deps/kotlin.go:172` — `fun interface X` is recorded twice, as `fun:X` and `interface:X`. The declaration-keyword gate in `scanKotlin` also fires on the `interface` token that follows `fun`.

## Diagnostic context

t1977 rewrote `ktDeclName`'s fun/val/var name walk. While listing the declaration forms the change must leave alone, `fun interface X` was examined.

- `ktDeclName` already handles it: for keyword `fun` it skips the `interface` token and returns `X` with kind `fun`.
- `scanKotlin`'s loop then visits the `interface` token itself. It is at brace depth 0 and paren depth 0, not after a dot, and is in `declKeywordsKt`, so `ktDeclName` runs again and returns `X` with kind `interface`.

Measured on commit 4940de5dc (t1977's fix), probe source `package x\n\nfun interface Listener { fun on() }\n`:

```
fun:Listener:3
interface:Listener:3
```

Impact is limited. `buildKtIndex` dedups `ix.decls` per file (`slices.Contains`), so resolution and edges are unaffected. The file's symbol facts (`Facts(path).Symbols`, consumed by the review packets) carry a duplicate entry for the one declaration. This predates t1977: the `interface` keyword path is unchanged by that task.

## Suggested fix

In `scanKotlin`, skip the declaration-keyword match for `interface` when the previous token is `fun` (it is the `fun interface` form `ktDeclName` already consumed). Add a fixture asserting `[fun:Listener]` for `fun interface Listener { fun on() }`, plus a control that a plain `interface Foo` is still `[interface:Foo]`. Bump the cache `schemaVersion` to HEAD + 1 at commit time, since raw Kotlin extraction changes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T06:32:27Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T07:00:36Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-15T07:42:31Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:cf02ce868a12e7a7

> **✅ gate:risk_evaluated** run=2026-10-15T07:42:31Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1997/risk_evaluated_2026-10-15T07:42:31Z-risk_evaluated-a1.log`
