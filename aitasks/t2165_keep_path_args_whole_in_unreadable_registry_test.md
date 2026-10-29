---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [monitor, tui, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2163
followup_kind: upstream_defect
created_at: 2026-10-29 22:28
updated_at: 2026-10-29 22:48
---

## Origin

Spawned from t2164 during Step 8b review.

## Upstream defect

- `tests/test_projects_unreadable_registry.sh:121-123` (as of t2164's commit `354197c47`) — the VERBS table flattens `$ALPHA_ROOT` / `$BETA_ROOT` into a space-split argline (`read -r -a args`), so under a `TMPDIR` containing whitespace the `add` and `update` rows die at the earlier "Path does not exist" check instead of the unreadable-registry read; fails loud (assert_contains "Cannot read…" misses), not silent.

## Diagnostic context

t2164 added `tests/test_projects_lock_released_on_die.sh`, modelled on this
file's scaffold. Step 8 review caught that the new test's case table split its
flattened command string on whitespace, including whitespace inside the
fixture paths (`mktemp -d` honours `TMPDIR`). With a space-containing `TMPDIR`
the rows carrying a path hit "Path does not exist" before reaching the code
they were meant to exercise; the reviewer reproduced 35/38. t2164 fixed its own
file by carrying `@ALPHA@` / `@BAD@` placeholders in the table and substituting
them per element after the split.

The sibling `test_projects_unreadable_registry.sh` has the same pattern in its
VERBS table:

```
"add|-|add $ALPHA_ROOT"
"update|-|update alpha $BETA_ROOT"
```

Under a spaced `TMPDIR` those two rows (× 3 shapes) would fail
`assert_contains "$CANNOT_READ"` — a false red, never a false green. Not
reproduced in t2164 (inferred from the identical construct); verify by running
`TMPDIR="<dir with a space>" bash tests/test_projects_unreadable_registry.sh`.

## Suggested fix

Use the same placeholder-substitution loop as
`tests/test_projects_lock_released_on_die.sh` section 1 (`@ALPHA@` / `@BETA@`
tokens replaced per array element after `read -r -a`), then confirm the
spaced-`TMPDIR` run passes.
