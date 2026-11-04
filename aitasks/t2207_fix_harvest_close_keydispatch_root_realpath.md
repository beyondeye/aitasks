---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [sitrep]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-04 22:56
updated_at: 2026-11-04 23:06
---

## Origin

Spawned from t2206 during Step 8b review.

## Upstream defect

- `tests/test_monitor_sitrep_harvest_close.py:985` — `KeyDispatchTests` sets `self.root = Path(self._tmp.name) / "repo"` without `realpath`, while `_strict_root_for_snap` canonicalizes through `agent_marks.mark_key` (realpath); on macOS the tempdir under `/var` resolves to `/private/var`, so `test_monitor_h_and_S_act_on_the_focused_card` and `test_minimonitor_h_and_S_act_on_the_followed_agent` (keys h and S, 4 subtests) fail on every run.

## Diagnostic context

While verifying t2206 (the live harvest-and-close smoke), the unit file was run as a regression neighbour with the venv interpreter (`~/.aitask/venv/bin/python tests/test_monitor_sitrep_harvest_close.py`): `Ran 66 tests … FAILED (failures=4)`. The same 4 failures reproduce on the `HEAD` copy of the file (before t2206's docstring-only edit), so they predate t2206. The assertion diffs read `'/private/var/folders/…/repo'` (what the app dispatched) vs `'/var/folders/…/repo'` (the expected `str(self.root)`). The other fixture class in the same file (line 779) already does `os.path.realpath(self._tmp.name)`.

Note: system `python3` lacks textual on this machine; the file needs the venv interpreter (or the python suite runner).

## Suggested fix

Canonicalize the fixture root at line 985, e.g. `self.root = Path(os.path.realpath(self._tmp.name)) / "repo"` (mirroring line 779), and confirm the 66 tests pass on macOS; keep the expectation strict (do not loosen the assertion to accept either spelling).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T21:06:38Z status=pass attempt=1 type=human
