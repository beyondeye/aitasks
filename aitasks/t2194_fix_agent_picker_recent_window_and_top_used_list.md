---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [model_selection, verifiedstats, codeagent, stats_ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-11-04 11:58
updated_at: 2026-11-04 12:52
---

## Problem

The agent/model picker (`AgentModelPickerScreen` in
`.aitask-scripts/lib/agent_model_picker.py`) cycles through six lists:
"Top verified models (recent)", "Top by usage (recent)", "All models", and
one list per agent. It opens from the settings TUI
(`settings_app.py` `_open_agent_model_picker`) and from the agent command
dialog (`agent_command_screen.py` `action_change_agent`, used by board /
monitor / minimonitor launches).

In the framework repo the first two lists are empty for most operations. When
they do have entries, those entries are stale or meaningless. An exploration
(2026-11-04) ran the picker's own builders (`_build_top_verified`,
`_build_top_usage`) against this repo's `aitasks/metadata/models_*.json` and
found two defects and one design gap.

### Defect 1: the "recent" window ignores the date

`_recent_aggregate()` adds the stored `month` and `prev_month` buckets and
never checks their `period` against today. The buckets roll over only when a
writer (`aitask_usage_update.sh` / `aitask_verified_update.sh`) next records a
run for that model and op, so a model that has not been used for months keeps
its old buckets and still counts as "recent".

Observed on 2026-11-04, op `pick`:
- `claudecode/opus4_8` shows "262 runs recent". Its buckets are 2026-07 and
  2026-06.
- Top-by-usage ranks `opus5` ("356 runs recent", buckets 2026-09/08) above
  `opus5_5` ("292 runs recent", buckets 2026-11/10). `opus5_5` is the only
  model with data from the current two months.

Other readers of the same buckets have the same flaw:
- `_format_op_stats()` labels the stored buckets "N this mo" / "N prev mo".
  It is used by the per-agent picker lists and by `settings_app.py` (~L2649,
  Agent Defaults / Models tab).
- `lib/stats_data.py` `recent_aggregate()` (a documented duplicate of the
  picker helper) and the `month` / `prev_month` / `week` / `recent` windows in
  `load_verified_rankings` / `load_usage_rankings`, which feed `ait stats` and
  the stats TUI.

Fix: a bucket counts toward a window only when its `period` matches that
window's period computed from today: current month, previous month, current
week, using the same week-start convention the writers use. `prev_month` must
be accepted from either slot: a model's stored `month` bucket can hold last
month's data because no run has rolled it over yet. Put this in one shared
helper; do not keep the two copies in the picker and stats_data. Old data with
a missing or empty `period` counts as not recent.

### Defect 2: the batch-review op never matches its counters

`aitask-review` records satisfaction feedback with `skill_name: "review"`
(`.claude/skills/aitask-review/SKILL.md.j2` ~L274). The picker looks the
counters up under the codeagent operation key `batch-review`, so review usage
and scores can never appear for that op. Decide on one fix: map
`batch-review` to `review` on the reader side, or align the recorded key.
Check every reader that is keyed by operation, not just the picker.

### Design gap: replace "Top verified" with "Top used (all ops)"

- The counters are written only by the Satisfaction Feedback procedure,
  keyed by skill name. Operations that never run that procedure (`raw`,
  `shadow`, `discuss`, `sitrep`, `learn`, `trail`, all `brainstorm-*`, and
  `explain` in practice) will always have empty per-op lists. For `raw` that
  is expected.
- "Top verified" does not discriminate: every recorded score in this repo is
  100, so ties fall back to alphabetical order (the `pick` list comes out as
  fable5, fable5_1, opus4_8, opus4_8_1m, opus5).

Requested change (user decision during the exploration):
1. Replace the first list, "Top verified models (recent)", with
   **"Top used models (recent, all ops)"**. It sums each model's usagestats
   runs across every op within the date-correct recent window, so it is
   populated for every operation, including `raw` / `shadow` / `discuss`.
2. Keep **"Top by usage (recent, this op)"** second, using the date-correct
   window.
3. Make the per-op empty state say why it is empty, e.g. "(no recorded usage
   for this op — only skills with satisfaction feedback record usage)", rather
   than implying a bug.
4. Scores can stay as secondary detail in the per-agent lists. Planning
   decides whether verified scores appear anywhere in the top lists.

Update the six-mode docstring, the `_MODES` table, the placeholders and the
selection handling (`on_fuzzy_select_selected` matches on the `top` /
`top_usage` mode keys). Also update every doc page that describes the picker
lists (grep `website/content/` for "Top verified").

## Tests

- `tests/test_agent_model_picker.py` pins the current top-verified ranking.
  Rewrite it for the new top-used list, and add fixtures where:
  - stale `month` / `prev_month` buckets (periods months old) are excluded
    from "recent";
  - a stored `month` bucket from last month counts as `prev_month`;
  - the all-ops sum ranks a model used across several ops above one used
    heavily in a single op, when the totals say so.
- Use a pinned "today" (injectable date or clock) so the tests do not depend
  on the wall-clock month.
- Cover the `batch-review` / `review` key resolution.
- stats_data has its own tests (`tests/test_stats_data.sh`,
  `tests/test_stats_verified_rankings.sh`, ...). Add stale-bucket cases there
  for the shared helper.

## Reproduction

```bash
~/.aitask/venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, ".aitask-scripts/lib")
from agent_model_picker import AgentModelPickerScreen, load_all_models
allm = load_all_models(".")
for op in ["pick", "raw", "shadow", "batch-review"]:
    s = AgentModelPickerScreen.__new__(AgentModelPickerScreen)
    s.operation, s.all_models = op, allm
    print(op, [(c["agent"] + "/" + c["name"], c["detail"]) for c in s._build_top_verified()])
    print(op, [(c["agent"] + "/" + c["name"], c["detail"]) for c in s._build_top_usage()])
EOF
```

## Sequencing / related

- **t1912** (move codeagent stats to a plumbing branch) changes where these
  counters are read from. Its "one shared read path" item names
  `agent_model_picker.py` (~L359, ~L396, ~L566) and `stats_data.py` as
  readers. Both tasks edit the same functions, so whichever lands second must
  rebase onto the other's reader. If this task adds a shared,
  date-correct window helper, t1912's shared read path should reuse it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T10:52:31Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-04T14:05:42Z status=pass attempt=1 type=human
