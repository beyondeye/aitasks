---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, project_groups]
gates: [risk_evaluated]
anchor: 1544
followup_kind: upstream_defect
created_at: 2026-08-18 12:29
updated_at: 2026-08-18 12:29
---

## Origin

Spawned from t1544_1 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_launch_utils.py:1052-1100` — `cross_group_ring` /
  `cross_group_step` locate the current entry by *first* `.key` match, so any
  caller that hands them two entries sharing a key gets a livelocked ring with
  other repos unreachable. t1544_1 removed the only known producer of such
  input (session discovery), but the helpers remain duplicate-fragile by
  construction and would break again for any future duplicate source.

## Diagnostic context

t1544_1 fixed session discovery so one repository yields one
`AitasksSession` record for `include_registered=True` consumers. While
characterizing the switcher, the ring behaviour under duplicate input was
measured directly:

```
ring: [('sess_a','/tmp/repo_one'), ('sess_b','/tmp/repo_one'), ('sess_c','/tmp/repo_two')]
6 right-steps from repo_one: ['sess_b','sess_b','sess_b','sess_b','sess_b','sess_b']
repo_two reachable? False
```

`cross_group_step` computes `idx = next(i for i,e in enumerate(entries) if
e.key == current_key)` — the FIRST match. Stepping off index 0 lands on index
1, whose key is identical, so the next step re-resolves `idx` to 0 and the
cursor oscillates inside the pair forever. Every repo past the duplicate is
unreachable by left/right cycling.

Two rows also both satisfy `selected = s.key == self._selected_key`, so both
render as selected simultaneously, and `_selected_entry()` (also first-match)
means opening the switcher from the second session silently operates on the
first.

t1544_1 deliberately fixed this **upstream** in discovery rather than in these
helpers, because that is where the duplicate was created and because the
switcher's identity model (t1099) is repo-based by design. The helpers
themselves were left unchanged and are still fragile.

## Suggested fix

Give the helpers an explicit contract rather than a silent failure mode.
Either:

- document the precondition ("`entries` must have distinct `.key` values")
  and add a cheap assertion / dev-mode guard in `cross_group_ring`; or
- make `cross_group_ring` itself dedupe on `.key` as a defensive belt, which
  makes the livelock unreachable regardless of caller.

Prefer whichever keeps `cross_group_step` a pure index-wrap. Add a regression
test with a hand-built duplicate list — note that
`tests/test_switcher_ring_dedupe.py` deliberately drives these helpers from
real discovery output, so it does NOT cover the hand-built case.
