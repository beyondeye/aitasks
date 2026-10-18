---
Task: t2049_frozenagent_repick_key_shift_p.md
Base branch: main
Output branch: main
---

# t2049 — frozenagent Re-pick key `p` → `P`

## Context

Re-pick in `ait frozenagent` relaunches the frozen task with a fresh agent and
asks for no confirmation. Moving it from `p` to `P` makes an accidental press
less likely and pairs it with `R` (Restore). Scope is the frozenagent TUI only:
`ait monitor` / `ait minimonitor` keep `p`, because `P` is their Parked/frozen
visibility filter there.

## Steps

### 1. Binding — `.aitask-scripts/frozenagent/frozenagent_app.py:242`

`Binding("p", "repick", "Re-pick")` → `Binding("P", "repick", "Re-pick")`.
Keep the action id `repick` so `(scope="frozenagent", action="repick")` user
overrides keep applying. `P` is free in `FrozenAgentApp` (uppercase keys are `G`,
`R`; mixins add only `j`, `?`). Nothing else in the app names the key literal
(`check_action` at :962 and `action_repick` at :988 are keyed by action).

### 2. Tests — `tests/test_frozenagent_app.py` (`ActionArgvTests`)

- `test_repick_is_refused_without_a_task_id` (~:1436): press `"P"` instead of
  `"p"`, so it still exercises the refusal and not an unbound key.
- Add `test_shift_p_repicks_with_the_task_id`: default record (task_id `1705`),
  press `"P"` → exactly one `run_shell_argvs()` entry containing
  `aitask_frozen.sh restore <RECORD_ID> --repick`. (There is currently no
  positive re-pick dispatch test.)
- Add `test_plain_p_no_longer_repicks`: same default record (it HAS a task id,
  so a still-bound `p` would dispatch), press `"p"` → `run_shell_argvs() == []`.
  This proves the old key is unbound, not just the new one bound.

### 3. Docs — every frozenagent-context `p` re-pick mention → `P`

- `website/content/docs/tuis/frozenagent/reference.md`: key-table row (:27)
  `` `p` `` → `` `P` ``; :38 "`R`, `p` and `k`" → "`R`, `P` and `k`". Add to the
  `P` row's Notes: "`p` in `ait monitor` / `ait minimonitor`, where `P` is the
  frozen filter" — a short, current-state note.
- `website/content/docs/tuis/frozenagent/_index.md`: :121 "**p — re-pick.**",
  :128 "**R** and **p** do not confirm", :135 "press **R** or **p**", :163
  "**R**, **p** and **k**".
- `website/content/docs/tuis/frozenagent/how-to.md`: :50 "**p — re-pick**",
  :73 and :114 "**R** or **p**".
- `website/content/docs/workflows/freeze-and-restore-agents.md`: :64
  "**p — re-pick**" (viewer context) and :162 "**R** / **p** act on the
  highlighted row" (frozenagent list mode). At :64 the surrounding paragraph is
  about the viewer; add a brief clause that the monitors use **p** on a frozen
  card, since this page covers both surfaces. Leave :99–:100 (`ait ide` offer
  `R`/`P`) untouched — already `P`, different surface.
- `website/content/docs/commands/_index.md`: no key mention — no change.
- Monitor/minimonitor docs and `monitor_shared.py:1145` toast: unchanged
  (out of scope).

## Verification

- `python3 -m pytest tests/test_frozenagent_app.py -q` (or
  `bash tests/run_all_python_tests.sh --test-dir …`) passes, including the two
  new tests.
- `bash tests/test_shortcuts_registry_coverage.sh` passes.
- `grep -rn '\*\*p\*\*\|`p`' website/content/docs/tuis/frozenagent/` → no
  re-pick mentions left.
- `cd website && python3 check_links.py --build` passes.
- Live check (footer `P Re-pick`, `p` inert, `?` editor lists Re-pick under `P`)
  is covered by the pilot tests above; note in Final Implementation Notes if not
  run interactively.

## Step 9

Post-implementation: commit code (`enhancement: … (t2049)`), commit plan via
`aitask_task_commit.sh`, archive per Step 9 (current-branch mode, no merge).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `FrozenAgentApp` binding `p` → `P` (action id `repick` kept). Tests: the no-task-id refusal test presses `P` and now also asserts the refusal toast; added `test_shift_p_repicks_with_the_task_id` (positive `restore <id> --repick` dispatch) and `test_plain_p_no_longer_repicks`. Docs: every frozenagent-context re-pick key mention moved to `P` across `tuis/frozenagent/{_index,how-to,reference}.md` and `workflows/freeze-and-restore-agents.md`.
- **Deviations from plan:** Docs touched more lines than the task listed (`_index.md` :128/:135/:163, `how-to.md` :73/:114, workflow :162) — all were frozenagent-context `p` mentions. The refusal test gained a notify spy so pressing an unbound key cannot pass it vacuously.
- **Issues encountered:** None.
- **Key decisions:** The monitor/frozenagent key divergence is noted in the reference key table and in the workflow page's restore/re-pick bullet, as current-state text. Negative control: with the old `p` binding restored, all three repick tests failed. Live interactive check was not run; footer/key behaviour is covered by the pilot tests.
- **Upstream defects identified:** None
