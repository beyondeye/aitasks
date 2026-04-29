---
Task: t717_3_agent_picker_recent_modes.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_1_verifiedstats_prev_month_schema.md, aitasks/t717/t717_2_usagestats_live_hook.md, aitasks/t717/t717_4_stats_tui_window_selector_usage_pane.md
Archived Sibling Plans: aiplans/archived/p717/p717_*_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
---

# t717_3 — Agent picker: recent-window modes

## Goal

Update `agent_model_picker.py` so the agent-command-dialog surfaces "recent" (current+prev_month) data:

1. Existing "Top verified models" mode switches from all-time average → recent-window average.
2. New mode "Top by usage (recent)" added — ranks models by recent usagestats runs.

User-confirmed: keep `Shift+Left` / `Shift+Right` cycle binding. Just add a new entry in `_MODES`.

## Pre-requisites

- t717_1 archived (verifiedstats has prev_month).
- t717_2 archived (usagestats block exists and is being populated).

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

Critical: do NOT fall back to all-time bucket when recent is zero. The whole point of the change is "old high-score models stop dominating".

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

Note the relabel of "top" → "Top verified models (recent)" — clarifies the window.

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

Per-agent picker rows automatically pick this up via `_build_options_for_agent`.

## Verify

1. Syntax: `python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py`.
2. Open the picker via a path that mounts it (e.g. `ait board` → run-with dialog or settings TUI agent-defaults editor).
3. Cycle modes with `Shift+→`:
   - "Top verified models (recent)" — ranking should differ from all-time when recent windows are uneven (older models with old high scores drop, newer models with recent scores rise).
   - "Top by usage (recent)" — codex models with recent runs should now appear here.
   - "All models" — unchanged.
   - Per-agent modes — model rows now show e.g. `"96 (9 runs, 5 this mo, 3 prev mo)"`.
4. Selection still works: choose a model, verify the dialog dismisses with the correct `agent/name` value.
5. Cold-start: temporarily zero out usagestats in a test model file, confirm "Top by usage" shows the placeholder row.

## Verification (manual checklist for t717_5)

- [ ] Picker shows "Top verified models (recent)" as the first mode after "top" pill.
- [ ] Picker shows "Top by usage (recent)" as the second mode.
- [ ] Shift+→ / Shift+← cycle between all 7 modes (was 6).
- [ ] At least one codex model appears in "Top by usage (recent)" if usage data has been recorded.
- [ ] Per-agent mode rows display prev_month info when present.
- [ ] Selection-and-dismiss still returns `agent/name` to caller.

## Notes for sibling tasks (t717_4)

- The recent-window aggregation `month + prev_month` is parallel to t717_4's stats-TUI window selector. Keep the term "recent" consistent across both surfaces.
