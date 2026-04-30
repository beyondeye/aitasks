---
Task: t717_3_agent_picker_recent_modes.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_1_verifiedstats_prev_month_schema.md, aitasks/t717/t717_2_usagestats_live_hook.md, aitasks/t717/t717_4_stats_tui_window_selector_usage_pane.md
Archived Sibling Plans: aiplans/archived/p717/p717_*_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 12:16
---

# t717_3 — Agent picker: recent-window modes

## Context

The agent-command picker (modal where users pick an agent + LLM model for a TUI launch) currently ranks "Top verified models" by `verifiedstats[op].all_time` average — older models with high lifetime scores dominate even when newer, better models exist. After siblings t717_1 (prev_month bucket added to `verifiedstats`) and t717_2 (parallel `usagestats` block + live unconditional hook) landed, the data exists to:

1. Rank "Top verified" by **recent window** (`month + prev_month`) so newer models compete fairly.
2. Add a new "Top by usage (recent)" mode that ranks by `usagestats[op]` recent runs — surfaces models that get used in practice (including codex-class models which never reach the verified-score prompt).

User-confirmed: keep the existing `Shift+Left` / `Shift+Right` cycle binding; add the new mode in the cycle.

## Pre-requisites

- t717_1 archived (verifiedstats has prev_month). ✓
- t717_2 archived (usagestats block exists and is being populated). ✓

## Verification result (verify path, 2026-04-30)

Pre-existing plan checked against current codebase:

- `.aitask-scripts/lib/agent_model_picker.py` — line numbers in the original plan are slightly off (file is longer than originally noted) but the structure is exactly as described:
  - `_bucket_avg()` at lines 60-65 ✓
  - `_format_op_stats()` at lines 68-84 (currently emits `"96 (9 runs, 5 mo)"` — no prev_month support yet) ✓
  - `_MODES` at lines 256-263 (6 entries: `top, all, codex, opencode, claudecode, geminicli`) ✓
  - `_build_top_verified()` at lines 296-323 — currently reads `all_time`, falls back to flat `verified[op]` ✓
  - `_build_options_top()` at lines 399-414 ✓
  - `_build_options_for_mode()` at lines 392-397 ✓
  - `_placeholder_for_mode()` at lines 384-390 ✓
  - `_build_options_for_agent()` at lines 439-478 — calls `_format_op_stats` for the per-agent rows ✓
- `aitasks/metadata/models_claudecode.json` — confirmed schema is post-t717_1 / t717_2: `opus4_7_1m.verifiedstats.pick` has `all_time / prev_month / month / week`; `opus4_7_1m.usagestats.pick` exists with `all_time / prev_month / month / week`. Cold-start prev_month appears as `{"period": "", "runs": 0, "score_sum": 0}` (or `runs: 0` for usagestats).
- Picker callers — only two: `agent_command_screen.py:590` (run-with dialog) and `settings_app.py:1686` (Agent Defaults editor). Both use `AgentModelPickerScreen` and `load_all_models` directly; neither bypasses `_format_op_stats`. The format-string change in step 7 will surface in both.
- `_format_op_stats` is also called from `_build_top_verified` (line 317) and `_build_options_for_agent` (line 454) — same module; the prev_month extension propagates automatically.

Conclusion: plan is sound, no updates required. Implementation proceeds per the canonical plan below.

## Implementation

### 1. Add helpers

In `.aitask-scripts/lib/agent_model_picker.py`, near `_bucket_avg`:

```python
def _recent_aggregate(op_buckets: dict) -> tuple[int, int]:
    """Return (runs, score_sum) summed across month + prev_month buckets."""
    month = op_buckets.get("month", {})
    prev = op_buckets.get("prev_month", {})
    runs = month.get("runs", 0) + prev.get("runs", 0)
    sum_ = month.get("score_sum", 0) + prev.get("score_sum", 0)
    return runs, sum_


def _recent_avg(op_buckets: dict) -> int:
    runs, sum_ = _recent_aggregate(op_buckets)
    if runs <= 0:
        return 0
    return round(sum_ / runs)
```

(`_recent_avg` is exported for symmetry with `_bucket_avg`; `_build_top_verified` uses `_recent_aggregate` directly so it can reuse the runs count for the detail string.)

### 2. Change `_build_top_verified`

Replace all-time-based scoring with recent-based:

```python
def _build_top_verified(self) -> list[dict]:
    """Build ranked list of top verified models for the operation, recent window."""
    candidates = []
    for agent, pdata in self.all_models.items():
        for m in pdata.get("models", []):
            if m.get("status", "active") == "unavailable":
                continue
            name = m.get("name", "?")
            vs = m.get("verifiedstats", {})
            op_buckets = vs.get(self.operation, {})
            recent_runs, recent_sum = _recent_aggregate(op_buckets)
            if recent_runs <= 0:
                # Fall back to flat verified — but mark as no-recent
                score = m.get("verified", {}).get(self.operation, 0)
                if score > 0:
                    candidates.append({
                        "agent": agent, "name": name,
                        "score": score,
                        "detail": f"score: {score} (no recent data)",
                    })
                continue
            avg = round(recent_sum / recent_runs)
            detail = f"{avg} ({recent_runs} runs recent)"
            candidates.append({
                "agent": agent, "name": name,
                "score": avg, "detail": detail,
            })
    candidates.sort(key=lambda c: (-c["score"], c["agent"], c["name"]))
    return candidates[:5]
```

Critical: do NOT fall back to `all_time` when recent is zero. The whole point of the change is "old high-score models stop dominating".

### 3. Add `_build_top_usage`

```python
def _build_top_usage(self) -> list[dict]:
    """Build ranked list of top-used models for the operation, recent window."""
    candidates = []
    for agent, pdata in self.all_models.items():
        for m in pdata.get("models", []):
            if m.get("status", "active") == "unavailable":
                continue
            name = m.get("name", "?")
            us = m.get("usagestats", {})
            op_buckets = us.get(self.operation, {})
            recent_runs, _ = _recent_aggregate(op_buckets)
            if recent_runs <= 0:
                continue
            at_runs = op_buckets.get("all_time", {}).get("runs", 0)
            if at_runs > recent_runs:
                detail = f"{recent_runs} runs recent · {at_runs} all-time"
            else:
                detail = f"{recent_runs} runs recent"
            candidates.append({
                "agent": agent, "name": name,
                "runs": recent_runs, "detail": detail,
            })
    candidates.sort(key=lambda c: (-c["runs"], c["agent"], c["name"]))
    return candidates[:5]
```

### 4. Add `_build_options_top_usage`

```python
def _build_options_top_usage(self) -> list[dict]:
    out: list[dict] = []
    for c in self._build_top_usage():
        val = f"{c['agent']}/{c['name']}"
        out.append({
            "value": val,
            "display": val,
            "description": c["detail"],
        })
    if not out:
        out.append({
            "value": "",
            "display": "(no recent usage for this op)",
            "description": "",
        })
    return out
```

### 5. Update `_MODES`

```python
_MODES: list[tuple[str, str]] = [
    ("top",        "Top verified models (recent)"),
    ("top_usage",  "Top by usage (recent)"),
    ("all",        "All models"),
    ("codex",      "All codex models"),
    ("opencode",   "All opencode models"),
    ("claudecode", "All Claude models"),
    ("geminicli",  "All Gemini models"),
]
```

Note the relabel of `"top"` → `"Top verified models (recent)"` — clarifies the window.

### 6. Wire dispatchers

In `_build_options_for_mode`:

```python
def _build_options_for_mode(self, mode_key: str) -> list[dict]:
    if mode_key == "top":
        return self._build_options_top()
    if mode_key == "top_usage":
        return self._build_options_top_usage()
    if mode_key == "all":
        return self._build_options_all()
    return self._build_options_for_agent(mode_key)
```

In `_placeholder_for_mode`:

```python
@staticmethod
def _placeholder_for_mode(mode_key: str) -> str:
    if mode_key == "top":
        return "Type to filter top-verified models..."
    if mode_key == "top_usage":
        return "Type to filter top-used models..."
    if mode_key == "all":
        return "Type agent/model..."
    return f"Type {mode_key} model name..."
```

In `on_fuzzy_select_selected`:

```python
mode_key = self._MODES[self._mode_idx][0]
if mode_key in ("top", "top_usage", "all"):
    self.dismiss({"key": self.operation, "value": event.value})
else:
    self.dismiss({
        "key": self.operation,
        "value": f"{mode_key}/{event.value}",
    })
```

### 7. Update `_format_op_stats` for prev_month

Existing function shows `"96 (9 runs, 5 this mo)"`. Extend to surface prev_month if present:

```python
def _format_op_stats(buckets: dict, compact: bool = False) -> str:
    at = buckets.get("all_time", {})
    runs = at.get("runs", 0)
    if runs <= 0:
        return ""
    avg = _bucket_avg(at)
    mo = buckets.get("month", {})
    pm = buckets.get("prev_month", {})
    mo_runs = mo.get("runs", 0)
    pm_runs = pm.get("runs", 0)
    mo_label = "mo" if compact else "month"
    pm_label = "prev mo" if compact else "last month"
    parts = [f"{runs} runs"]
    if mo_runs > 0:
        parts.append(f"{mo_runs} this {mo_label}")
    if pm_runs > 0:
        parts.append(f"{pm_runs} {pm_label}")
    return f"{avg} ({', '.join(parts)})"
```

Per-agent picker rows automatically pick this up via `_build_options_for_agent`. The change is additive — `prev_month` is only displayed when `pm_runs > 0`, so cold-start models continue to show the existing terse output.

## Key Files to Modify

- `.aitask-scripts/lib/agent_model_picker.py` — only file with substantive changes.

No new files. No tests in this task — picker is TUI-only. Manual verification is captured by sibling t717_5.

## Verify

1. Syntax: `python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py`.
2. Open the picker via a path that mounts it (e.g. `ait board` → run-with dialog or settings TUI Agent Defaults editor).
3. Cycle modes with `Shift+→`:
   - "Top verified models (recent)" — ranking should differ from all-time when recent windows are uneven (older models with old high scores drop, newer models with recent scores rise).
   - "Top by usage (recent)" — codex models with recent runs should now appear here even though they never accrued verifiedstats.
   - "All models" — unchanged.
   - Per-agent modes — model rows now show e.g. `"96 (9 runs, 5 this mo, 3 prev mo)"` when prev_month data exists.
4. Selection still works: choose a model, verify the dialog dismisses with the correct `agent/name` value.
5. Cold-start: temporarily zero out usagestats in a test model file, confirm "Top by usage" shows the placeholder row `(no recent usage for this op)`.

## Verification (manual checklist for t717_5)

- [ ] Picker shows "Top verified models (recent)" as the first mode in the cycle.
- [ ] Picker shows "Top by usage (recent)" as the second mode.
- [ ] Shift+→ / Shift+← cycle between all 7 modes (was 6).
- [ ] At least one codex model appears in "Top by usage (recent)" if usage data has been recorded.
- [ ] Per-agent mode rows display prev_month info when present.
- [ ] Selection-and-dismiss still returns `agent/name` to caller.

## Notes for sibling tasks (t717_4)

- The recent-window aggregation `month + prev_month` is parallel to t717_4's stats-TUI window selector. Keep the term "recent" consistent across both surfaces.
- If t717_4 needs the same `_recent_aggregate` helper, consider whether to extract to a shared module. Picker uses Path-based module loading without `stats_data` dependency, so a duplicate one-line helper in `stats_data.py` is acceptable. Decide based on existing import patterns at t717_4 implementation time.

## Step 9: Post-Implementation

Standard archival via `./.aitask-scripts/aitask_archive.sh 717_3`. Folded tasks: none.
