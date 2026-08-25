---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1605
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-25 17:38
updated_at: 2026-08-25 18:57
---

## Origin

Spawned from t1605 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/yaml_utils.sh:304` — `read_yaml_list`'s BLOCK-list branch
  emits items with their surrounding quotes intact, while its inline `[a, b]` branch
  (line 278) strips them. A project writing `verify_build:` / `  - "make -j4"` gets
  `bash -c '"make -j4"'` → exit 127 "command not found", recorded as a gate FAIL.
  Single-word items (`- "true"`) survive by accident because bash strips the quotes,
  which is why `tests/test_gate_verifiers.sh` Test 2 never caught it: its multi-word
  item sits after a short-circuiting failure and never runs.

## Diagnostic context

While implementing t1605, three new multi-command aggregation fixtures in
`tests/test_gate_verifiers.sh` failed with exit 127 instead of the expected exit
codes. The commands were written the way the file's existing Test 2 writes them —
as quoted block-list items:

```yaml
verify_build:
  - "true"
  - "exit 2"
  - "touch RAN_THIRD"
```

`run_command_gate` resolves that list through `read_yaml_list`, whose block branch
captures `${BASH_REMATCH[1]}` verbatim (`yaml_utils.sh:304`) and therefore returns
`"exit 2"` **with** the double quotes. `bash -c '"exit 2"'` looks for a command whose
name is literally `exit 2` and exits 127. The inline flow form is not affected: that
branch strips `[`, `]`, `'` and `"` explicitly (`yaml_utils.sh:278`).

The fixtures were rewritten unquoted and t1605's tests pass, but the asymmetry is a
real trap for user-authored `project_config.yaml`: the two YAML list forms are
documented as interchangeable (`seed/project_config.yaml` shows both), yet only the
inline one accepts quoted multi-word commands.

## Scope

`read_yaml_list` is a shared reader with many callers, so the fix is deliberately
NOT local to the gate verifiers — t1605 explicitly declined to patch it inside
`_gate_config_values`, because doing so would have changed the command resolution
that task's pre-phase mitigation had just pinned as unchanged.

Design points for planning:

1. **Where the strip belongs.** In `_read_yaml_list_impl`'s block branch, matching
   what the inline branch already does — versus a shared `_yaml_scalar_value`-style
   helper (that function, `yaml_utils.sh:320`, already implements careful
   quote-stripping for the block-mapping reader and may be reusable here).
2. **Blast radius.** Enumerate the existing `read_yaml_list` callers and confirm
   none depends on receiving quotes. Values that are *identifiers* (label lists,
   gate names, `folded_tasks`) are unaffected in practice because they are rarely
   quoted; values that are *commands* or *paths* are where this bites.
3. **Asymmetry as the test oracle.** The strongest assertion is a parity test: the
   same list expressed inline and in block form must resolve to identical values,
   for quoted and unquoted items alike. That fails today and cannot pass vacuously.
4. **Escaped/inner quotes.** `_yaml_scalar_value`'s docstring notes it does not
   handle escaped quotes inside double-quoted strings. Decide whether that residual
   is accepted (and pin it as a test) or in scope.

## Acceptance

- A block-list item written `- "make -j4"` resolves to `make -j4` and runs.
- An inline/block parity test asserts identical resolution for both forms, and is
  observed FAILING against the current code before the fix.
- An item containing a quote that is not a surrounding pair (e.g. `- echo "hi"`) is
  not mangled — a reachable rejection probe against over-eager stripping.
- Every existing `read_yaml_list` caller still passes its own tests; the sweep of
  callers is recorded, not assumed.
- `tests/test_gate_verifiers.sh` Test 2's `- "touch SHOULD_NOT_RUN"` item stays a
  valid fixture (it currently only works because it never executes).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T15:57:12Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-25T19:08:35Z status=pass attempt=1 type=human
