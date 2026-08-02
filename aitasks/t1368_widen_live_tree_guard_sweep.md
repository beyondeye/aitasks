---
priority: low
effort: low
depends: []
issue_type: test
status: Postponed
labels: [test, tui, board]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1111
created_at: 2026-08-02 12:15
updated_at: 2026-08-02 12:42
---

## Origin

Risk-mitigation ("after") follow-up for t1354_2, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement, from t1354_2's `## Risk`:

> Scope grew 9 -> 15 files during verification; further unlisted coupling would
> weaken the guard's completeness claim · severity: low

t1354_2's tier-1 sweep is exhaustive over `tests/test_board_*.py` — but only
over that glob. The same live-tree coupling can appear in any other TUI test
module, and would not be caught.

## Goal

Widen the tier-1 live-tree sweep in `tests/test_board_fixture_harness.py` from
`tests/test_board_*.py` (25 files) to all `tests/test_*.py` (~175 files).

## Why this is worth doing

Verified during t1354_2 that no non-board test currently chdirs to `REPO_ROOT`
at import/test time — every other `os.chdir` in `tests/` targets a tmpdir. So
the widening is expected to be near-free today. Its value is prospective: it
closes the glob as an escape hatch before a new `test_settings_*` /
`test_brainstorm_*` / `test_monitor_*` module reintroduces the coupling.

It also gives the allowlist its first entry that is provable on the *real*
tree rather than only on synthetic fixtures:
`tests/test_shortcut_scopes.py:322` has `os.chdir(REPO_ROOT)` inside an
`if __name__ == "__main__":` block (benign — not executed under discovery),
which is exactly the "justified exception, pinned with a reason" case the
mechanism exists for.

## Key Files to Modify

- `tests/test_board_fixture_harness.py` — `LiveTreeSweepTests._board_test_sources`
  (change the glob), `CHDIR_ALLOWED` (add the `test_shortcut_scopes.py` entry
  with its reason).

## Cautions

- **Re-run the whole sweep before assuming it is free.** The prediction above
  was measured on 2026-08-02; new modules land weekly.
- The canonical-import half of the rule will also widen. Any non-board module
  that imports `aitask_board` canonically needs the same judgement call as
  `test_board_movement` / `test_board_persistence_seam` did: exempt with a
  written reason, or migrate it.
- Keep the exemption **per-expression**, never per-module — that property is
  pinned by `test_exemption_cannot_hide_a_repo_root_chdir` and is the reason
  the guard cannot rot into a rubber stamp.

## Verification Steps

- Sweep green over all `tests/test_*.py`.
- Every new allowlist entry proven load-bearing by the existing removal control
  (`test_allowlist_entries_are_load_bearing`) — which iterates the dict, so new
  entries are covered automatically.
- `test_sweep_covers_more_than_the_migrated_set` still holds.
- Full suite green; no measurable wall-clock change (the sweep is a source scan).
