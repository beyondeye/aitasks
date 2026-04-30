---
priority: medium
effort: medium
depends: [t717_2]
issue_type: feature
status: Done
labels: [verifiedstats, statistics, ui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 00:19
updated_at: 2026-04-30 12:24
completed_at: 2026-04-30 12:24
---

## Context

Third child of t717. Updates the agent-command picker (the modal where users select an agent + LLM model for a launch / TUI action) to expose the new "recent" data layer added by t717_1 and t717_2:

1. The existing "Top verified models" mode currently sorts by `verifiedstats[op].all_time` average score. Change it to sort by **current+prev_month** aggregate score — so recently-released models compete fairly with older high-scoring incumbents.
2. Add a new mode "Top by usage (recent)" that ranks by `usagestats[op]` recent runs — surfaces models that get used in practice (including codex models, which never got a verified score recorded before t717_2).

User-confirmed: keep the existing `Shift+Left` / `Shift+Right` cycle binding; just add the new mode in the cycle.

## Key Files to Modify

- `.aitask-scripts/lib/agent_model_picker.py` — the only file with substantive changes.

No tests in this task — picker is TUI-only and verified manually + by the manual-verification sibling t717_5.

## Reference Files for Patterns

- Existing `_build_top_verified()` at `agent_model_picker.py:273-300` — model the new aggregation on it.
- Existing `_MODES` list at `agent_model_picker.py:233-240` — insert the new entry there.
- `_format_op_stats()` at `agent_model_picker.py:68-84` — the compact formatter; extend to surface prev_month if present.
- `_bucket_avg()` at `agent_model_picker.py:60-65` — keep as-is, reused for recent aggregate.
- `_build_options_top()` at `agent_model_picker.py:370-385` and `_placeholder_for_mode()` at `agent_model_picker.py:355-361` — patterns to follow for the new mode dispatcher.

## Implementation Plan

1. **Add `_recent_aggregate(op_buckets)` helper.**
   ```python
   def _recent_aggregate(op_buckets: dict) -> tuple[int, int]:
       """Return (runs, score_sum) summed across month + prev_month buckets."""
       month = op_buckets.get("month", {})
       prev = op_buckets.get("prev_month", {})
       runs = month.get("runs", 0) + prev.get("runs", 0)
       sum_ = month.get("score_sum", 0) + prev.get("score_sum", 0)
       return runs, sum_
   ```
   Place near `_bucket_avg`.

2. **Add `_recent_avg(op_buckets)` helper.** Returns the rounded average of `_recent_aggregate`. Returns 0 if recent runs are 0.

3. **Change `_build_top_verified`.** Replace the all-time read with `_recent_aggregate`:
   ```python
   recent_runs, recent_sum = _recent_aggregate(op_buckets)
   if recent_runs <= 0:
       # Fall through to flat verified
       score = m.get("verified", {}).get(self.operation, 0)
       if score > 0:
           candidates.append({..., "detail": f"score: {score} (no recent data)"})
       continue
   avg = round(recent_sum / recent_runs)
   detail = f"{avg} ({recent_runs} runs recent)"
   candidates.append({..., "score": avg, "detail": detail})
   ```
   Keep the fall-through to the flat `verified[op]` — but DO NOT fall back to `all_time` as a stronger signal. The whole point of the change is to drop the all-time-as-default behavior.

4. **Add `_build_top_usage(self) -> list[dict]`.** Mirrors `_build_top_verified`:
   - Iterate `self.all_models`, skip unavailable models.
   - Read `usagestats[self.operation]`.
   - Compute recent runs = `month.runs + prev_month.runs` (no score).
   - Skip models with `recent_runs == 0` (no flat fallback — usage is purely recent-window).
   - Sort by `(-recent_runs, agent, name)`.
   - Detail string: `f"{recent_runs} runs (recent)"`. If `usagestats[op].all_time.runs > 0`, append ` · {at_runs} all-time` for context.
   - Return top 5.

5. **Add `_build_options_top_usage(self) -> list[dict]`.** Mirrors `_build_options_top`. If empty, emit placeholder option `(no recent usage for this op)`.

6. **Update `_MODES`.** Insert new entry after `("top", ...)`:
   ```python
   _MODES: list[tuple[str, str]] = [
       ("top",        "Top verified models (recent)"),
       ("top_usage",  "Top by usage (recent)"),
       ("all",        "All models"),
       ("codex",      "All codex models"),
       ...
   ]
   ```
   Updating "Top verified models" label to clarify the window is now recent.

7. **Update `_build_options_for_mode`.** Add branch:
   ```python
   if mode_key == "top_usage":
       return self._build_options_top_usage()
   ```

8. **Update `_placeholder_for_mode`.** Add branch for `top_usage`: `"Type to filter top-used models..."`.

9. **Update `on_fuzzy_select_selected`.** Treat `top_usage` like `top` (both yield resolved `agent/name`):
   ```python
   if mode_key in ("top", "top_usage", "all"):
       self.dismiss({"key": self.operation, "value": event.value})
   else:
       ...
   ```

10. **Update `_format_op_stats(buckets, compact)`.** Surface prev_month if present. Extend to return e.g. `"96 (9 runs, 5 mo, 3 prev mo)"` (compact) or `"96 (9 runs, 5 this month, 3 last month)"` (full). Read `prev_month.runs` defensively (`.get(...)`).

11. **Update `_build_options_for_agent`.** When showing per-agent modes (codex / opencode / claudecode / geminicli), the score detail string already comes from `_format_op_stats`. Ensure the new prev_month info appears here too via the change in step 10.

## Verification Steps

Manual verification (no automated test for TUI):
1. `python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py` — must succeed.
2. Open the agent picker via a TUI flow that uses it (e.g., `ait board`, run-with dialog). Cycle through modes with `Shift+→` / `Shift+←`:
   - "Top verified models (recent)": models with recent month/prev_month runs appear, ranked by recent-window average score. A new model with 5 runs in current month and a 100 score outranks an old model with 100 all-time runs but 0 recent.
   - "Top by usage (recent)": models with usagestats[op] recent activity appear, ranked by recent runs. A codex model that has run 8 times in recent two months but never got a score should appear here even though it never appears in "Top verified".
3. Per-agent modes (codex / opencode / claudecode / geminicli): verify that detail strings now show "5 mo, 3 prev mo" when prev_month data exists.
4. Confirm the picker still selects correctly: enter, choose a model, confirm dismiss returns the `agent/name` value to the caller.

Edge cases to test:
- All models in current month have 0 runs → "Top by usage (recent)" shows the placeholder row.
- Only some models have prev_month — verify mixed display works.
- No models have ANY verifiedstats yet (cold-start) → "Top verified models (recent)" falls back to flat `verified[op]` correctly.

## Notes for sibling tasks (t717_4)

- The aggregation logic `month + prev_month` for the "recent" window is symmetric across picker and stats TUI — t717_4's `load_usage_rankings` and `load_verified_rankings` should produce parallel data. Consider extracting `_recent_aggregate` to a shared module (`stats_data.py` already exports `canonical_model_id`); however, picker uses Path-based module loading without stats_data dependency, so a duplicate one-line helper in stats_data is acceptable. Decide based on existing import patterns.
- Picker's "recent" semantics = `month + prev_month`. Stats TUI's window key is also `recent` (per parent plan). Keep the names aligned.
