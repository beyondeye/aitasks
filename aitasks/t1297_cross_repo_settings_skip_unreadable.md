---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [tui, ait_settings]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-28 17:28
updated_at: 2026-07-28 17:28
boardidx: 64512
---

## Origin

Risk-mitigation ("after") follow-up for t1223_5, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement risk 1 of `aiplans/archived/p1223/p1223_5_settings_tab_and_push_action.md`
(severity: medium), verbatim:

> The per-repo degradation the AC requires is **not** what the seam provides —
> `diff_across_repos` aborts globally — so it is delivered by a syncer-side
> two-phase fallback. If that is wrong, one corrupt repo blanks the whole tab,
> the exact failure the AC forbids.

## Goal

`cross_repo_settings.diff_across_repos(roots)` reads every root's layers in one
unguarded loop, so **one corrupt repo aborts the entire call** and returns no
matrix at all. Its own docstring tells callers wanting per-repo degradation to
loop `read_operation_defaults` themselves — which is what t1223_5 does, in
`syncer_app._read_settings_matrix`, as a bounded shrink-and-retry loop.

That logic is in the wrong layer: it is value logic living in the UI, and any
second consumer of the seam would have to reimplement it.

Move it into the seam:

1. Add `diff_across_repos(roots, *, skip_unreadable: bool = False)`. When true it
   returns `(matrix, unreadable: dict[repo_key, str])` instead of raising, doing
   the per-root probe internally and in **one** fan-out rather than the syncer's
   worst-case two.
2. Delete `_read_settings_matrix`'s loop from `syncer_app.py` and call the new
   form; `_apply_settings` already takes `(diff, unreadable, unattributed)`.
3. Preserve both properties t1223_5's tests pin, and keep those tests passing:
   - a repo that breaks **between** the probe and the read costs only its own
     column (the survivors keep their data);
   - a failure the probe cannot attribute to any repo marks **no** repo
     unreadable and is reported as a scope-level reason.
4. Keep the default (`skip_unreadable=False`) raising, so the 40 existing
   `tests/test_cross_repo_settings.py` tests stay valid unchanged.

## Key files

- `.aitask-scripts/lib/cross_repo_settings.py` — `diff_across_repos`.
- `.aitask-scripts/syncer/syncer_app.py` — `_read_settings_matrix` (delete),
  `_settings_worker`, `_on_settings_error`.
- `tests/test_cross_repo_settings.py`, `tests/test_syncer_rows.py` — the
  raced-corruption and unattributable-failure tests must keep passing (they are
  the behavioural contract being relocated, not rewritten).

## Verification

```bash
python3 tests/test_cross_repo_settings.py
python3 tests/test_syncer_rows.py
```
