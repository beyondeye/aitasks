---
Task: t716_improve_agent_chooser_in_agent_command_dialog.md
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

## Context

In the agent command dialog (used in `ait board`, codebrowser, monitor, and other
TUIs), users can press **A** to change the code agent/model that will run a command
and **U** to recall the "last used" agent for that operation. The current behavior
has two papercuts:

1. The **"use last"** button stores any agent the user picks — even if they pick
   the default. So pressing the picker, hitting Enter on the default-highlighted
   model, then closing the dialog leaves "(U)se last: <default>" — useless, since
   that's what the dialog opens with anyway.

2. The **agent picker** (Step 0) shows "Top verified models" mixed with a
   "Browse all models..." pseudo-option that drops the user into a 3-step flow
   (top → agent → model). The user wants the top list to stay clean and to
   switch *between* curated lists with a keyboard shortcut. Plain letter keys
   are unusable because the FuzzySelect Input is focused for filtering.

The work touches two files in `.aitask-scripts/lib/`:
- `agent_command_screen.py` — the dialog with the (A)/(U) buttons
- `agent_model_picker.py` — the picker invoked by (A)

The picker is **shared** with the Settings TUI's "edit defaults" flow, so the
new cycling UX applies there too (per user direction).

User decisions captured in clarifications:
- Cycling key: **Shift+Left / Shift+Right** (priority bindings to override Input).
- Scope: applies everywhere `AgentModelPickerScreen` is used (launch dialog +
  Settings TUI).
- "All models" cross-agent sort: **alphabetical by `agent/model`**.

---

## Plan

### Part 1 — `(U)se previous` rename + default-aware storage

File: `.aitask-scripts/lib/agent_command_screen.py`

Changes:

1. Rename the class-level dict to reflect new semantics (line 217):
   ```python
   _previous_agent_override: dict[str, str] = {}
   ```

2. Constructor (line 219–246): remember the original default for comparison.
   Add a single line near where `current_agent_string` is set:
   ```python
   self._default_agent_string: str | None = default_agent_string
   ```

3. `_on_agent_picked()` (line 600–609): only store the pick as "previous" when
   it differs from the original default:
   ```python
   if self.operation and new_agent_string != self._default_agent_string:
       AgentCommandScreen._previous_agent_override[self.operation] = new_agent_string
   ```
   No clearing of an existing previous entry when the user picks the default —
   the previous entry from an earlier override should still be recallable.

4. Rename action method (line 611) and update its references:
   ```python
   def action_use_previous_agent(self) -> None:
       ...
       previous = AgentCommandScreen._previous_agent_override.get(self.operation)
       if previous and previous != self.current_agent_string:
           self._apply_agent_override(previous)
           self._refresh_agent_row()
   ```
   Update the `u`/`U` key handler at line 680–684 to call
   `action_use_previous_agent`. Update `_btn_use_last_agent` handler at line 666
   to call the renamed action (the button id can stay the same to avoid CSS
   churn, but rename the python handler method to `_btn_use_previous_agent`
   for grep-ability).

5. `_refresh_agent_row()` (line 641–660): change the button label format and
   the lookup dict:
   ```python
   previous = AgentCommandScreen._previous_agent_override.get(self.operation)
   if previous and previous != self.current_agent_string:
       use_last_btn.label = f"(U)se previous: {previous}"
       use_last_btn.remove_class("hidden")
   else:
       use_last_btn.add_class("hidden")
   ```

No other places in the codebase grep-match `_last_agent_override` outside this
file (the per-project tmux state uses different dicts), so this rename is local.

### Part 2 — Six-list cycling picker

File: `.aitask-scripts/lib/agent_model_picker.py`

Replace the 3-step flow (top → agent → model) with a single screen that cycles
through six list modes via Shift+Left / Shift+Right.

**Mode table** (define near the top of `AgentModelPickerScreen`):

```python
_MODES: list[tuple[str, str]] = [
    ("top",        "Top verified models"),
    ("all",        "All models"),
    ("codex",      "All codex models"),
    ("opencode",   "All opencode models"),
    ("claudecode", "All Claude models"),
    ("geminicli",  "All Gemini models"),
]
```

**State changes** in `__init__`:

- Replace `self._step = 0` with `self._mode_idx = 0`.
- Drop `self.selected_agent` (no longer needed — agent is encoded per option).

**Bindings** (replace the existing `BINDINGS`):

```python
BINDINGS = [
    Binding("escape", "go_back", "Back/Cancel", show=False),
    Binding("shift+left",  "prev_list", "Prev list", show=True, priority=True),
    Binding("shift+right", "next_list", "Next list", show=True, priority=True),
]
```

`priority=True` is required because the focused Input widget would otherwise
consume Shift+arrows for text selection. CLAUDE.md notes a priority-binding
gotcha when an App and Screen share an action name — that does not apply here
(no App-level binding for shift+left/right exists).

**`compose()`** simplifies to:

```python
def compose(self) -> ComposeResult:
    with Container(id="picker_dialog"):
        yield Label(
            f"Select model for: [bold]{self.operation}[/bold]",
            id="picker_title",
        )
        yield Label("", id="picker_step_label")  # populated by _apply_mode
        # FuzzySelect is mounted by _apply_mode; no widget here at compose time.
    # _apply_mode is called from on_mount to populate the initial mode.

def on_mount(self) -> None:
    self._apply_mode(0)
```

**New / replaced methods:**

```python
def action_prev_list(self) -> None:
    self._apply_mode((self._mode_idx - 1) % len(self._MODES))

def action_next_list(self) -> None:
    self._apply_mode((self._mode_idx + 1) % len(self._MODES))

def action_go_back(self) -> None:
    # Esc dismisses (the 3-step back-stepping no longer applies).
    self.dismiss(None)

def _apply_mode(self, idx: int) -> None:
    self._mode_idx = idx % len(self._MODES)
    mode_key, label_text = self._MODES[self._mode_idx]
    # Update header label with mode + keyboard hint
    self.query_one("#picker_step_label", Label).update(
        f"{label_text}  [dim](Shift+←/→ to switch)[/dim]"
    )
    options = self._build_options_for_mode(mode_key)
    # Replace any existing FuzzySelect with a fresh one
    container = self.query_one("#picker_dialog", Container)
    for fs in list(container.query(FuzzySelect)):
        fs.remove()
    fs = FuzzySelect(
        options,
        placeholder=self._placeholder_for_mode(mode_key),
        id="model_picker",
    )
    container.mount(fs)

def _placeholder_for_mode(self, mode_key: str) -> str:
    if mode_key == "top":
        return "Type to filter top models..."
    if mode_key == "all":
        return "Type agent/model..."
    return f"Type {mode_key} model name..."

def _build_options_for_mode(self, mode_key: str) -> list[dict]:
    if mode_key == "top":
        return self._build_options_top()
    if mode_key == "all":
        return self._build_options_all()
    return self._build_options_for_agent(mode_key)

def _build_options_top(self) -> list[dict]:
    # Reuse _build_top_verified() but stop appending the "__browse__" sentinel.
    out = []
    for c in self._build_top_verified():
        val = f"{c['agent']}/{c['name']}"
        out.append({
            "value": val, "display": val, "description": c["detail"],
        })
    if not out:
        out.append({"value": "", "display": "(no top-verified models for this op)", "description": ""})
    return out

def _build_options_all(self) -> list[dict]:
    # Cross-agent. Alphabetical by "agent/model".
    out = []
    for agent in sorted(self.all_models.keys()):
        pdata = self.all_models[agent]
        for m in pdata.get("models", []):
            if m.get("status", "active") == "unavailable":
                continue
            name = m.get("name", "?")
            notes = m.get("notes", "")
            out.append({
                "value": f"{agent}/{name}",
                "display": f"{agent}/{name}",
                "description": notes,
            })
    out.sort(key=lambda o: o["display"])
    if not out:
        out.append({"value": "", "display": "(no models found)", "description": ""})
    return out

def _build_options_for_agent(self, agent: str) -> list[dict]:
    # Per-agent: keep current sort (verified by score desc, then unverified).
    # This factors out the body of the old _show_step2 model-listing code.
    model_path = MODEL_FILES.get(agent, Path("nonexistent"))
    model_data = _load_json(model_path)
    models = model_data.get("models", []) if model_data else []
    scored, unscored = [], []
    for m in models:
        if m.get("status", "active") == "unavailable":
            continue
        name = m.get("name", "?")
        notes = m.get("notes", "")
        vs = m.get("verifiedstats", {})
        op_buckets = vs.get(self.operation, {})
        at = op_buckets.get("all_time", {})
        if at.get("runs", 0) > 0:
            detail = _format_op_stats(op_buckets, compact=True)
            sort_score = _bucket_avg(at)
            score_str = f"[{detail}]"
        else:
            verified = m.get("verified", {})
            op_score = verified.get(self.operation, 0)
            if op_score:
                sort_score = op_score
                score_str = f"[score: {op_score}]"
            elif self.operation in verified:
                sort_score, score_str = 0, "(not verified)"
            else:
                sort_score, score_str = -1, ""
        desc = f"{notes}  {score_str}".strip() if score_str else notes
        # Per-agent options return bare model names; on_fuzzy_select_selected
        # prepends the agent based on the active mode.
        opt = {"value": name, "display": name, "description": desc}
        (scored if sort_score > 0 else unscored).append((sort_score, opt))
    scored.sort(key=lambda x: -x[0])
    out = [o for _, o in scored] + [o for _, o in unscored]
    if not out:
        out.append({"value": "", "display": "(no models found)", "description": ""})
    return out
```

**`on_fuzzy_select_selected()`** replaces the 3-step routing with a mode-aware
dispatch:

```python
def on_fuzzy_select_selected(self, event: FuzzySelect.Selected) -> None:
    if not event.value:
        return  # placeholder rows ("(no models found)", etc.)
    mode_key = self._MODES[self._mode_idx][0]
    if mode_key in ("top", "all"):
        # value is already "agent/model"
        self.dismiss({"key": self.operation, "value": event.value})
    else:
        # per-agent mode: value is bare model name; prepend the agent
        self.dismiss({
            "key": self.operation,
            "value": f"{mode_key}/{event.value}",
        })

def on_fuzzy_select_cancelled(self, event: FuzzySelect.Cancelled) -> None:
    self.dismiss(None)
```

**Delete** the old `_show_step0` / `_show_step1` / `_show_step2` methods —
their behavior is fully covered by `_apply_mode` + the per-mode builders.

**Fallback for the no-top-verified case** (currently at compose() lines 316–328
where `_step` is forced to 1): not needed anymore. If `_build_top_verified()`
returns nothing, `_build_options_top()` shows a single "(no top-verified
models for this op)" placeholder — the user simply Shift+Right's to the next
mode. This is cleaner than the current implicit step-skip.

### Part 3 — No changes needed in callers

Both call sites pass `(operation, current_agent, current_model, all_models=...)`
and read `result["value"]`:

- `agent_command_screen.py:587–598` (action_change_agent)
- Settings TUI invocation (Models tab "edit defaults" flow)

Both keep working because the dismissal contract (`{"key", "value"}`) is
preserved.

---

## Files to Modify

- `.aitask-scripts/lib/agent_command_screen.py` — Part 1 (rename, default-aware
  storage, button label).
- `.aitask-scripts/lib/agent_model_picker.py` — Part 2 (single-screen mode
  cycling, Shift+Left/Right bindings, mode-keyed option builders).

---

## Verification

End-to-end manual checks (TUI behavior — automated coverage is not feasible):

1. **(U)se previous storage rule**
   - `ait board` → pick a task → trigger the Pick command (key bound to `p`).
   - In the dialog, the "(U)se previous: …" button must be hidden initially.
   - Press `A`. Without changing the highlighted model (the default), press
     Enter. Reopen the dialog (Esc and re-trigger pick): button still hidden.
     ✅ Picking the default does not populate "previous".
   - Press `A` again, this time pick a *non-default* model. Reopen the dialog:
     button now reads `(U)se previous: <agent>/<model>`.
   - Press `U`: command updates to that agent.
   - Press `A`, pick the original default. Reopen: button still shows the
     previous non-default (because we only *write* on non-default picks; we do
     not clear).

2. **Mode cycling**
   - In the picker, the header reads `Top verified models  (Shift+←/→ to switch)`.
   - Confirm there is **no** "Browse all models..." item in the list.
   - Shift+Right cycles: All models → All codex → All opencode → All Claude →
     All Gemini → wraps to Top.
   - Shift+Left cycles in reverse.
   - In each mode, typing in the Input filters the list. Up/Down navigates,
     Enter selects, Esc dismisses.
   - Shift+Left/Right while the Input is focused must override Input's default
     selection-extension behavior. If during testing the Shift+arrows are
     consumed by Input despite `priority=True`, fall back to PageUp/PageDown
     and update the header hint and bindings accordingly. (Mark this in the
     Final Implementation Notes if it happens.)

3. **Selection result is correct**
   - From "All models" mode, pick `claudecode/sonnet4_6`: dialog shows
     `Agent: claudecode/sonnet4_6` and the command line updates.
   - From "All codex models" mode, pick a bare model name: result is
     `codex/<model>`.

4. **Settings TUI defaults editor**
   - Open Settings TUI, go to Agent Defaults, select an operation, trigger
     the picker (existing UX).
   - Confirm the same six-list cycling works there too.

5. **Lint / smoke**
   - `python -c "import ast; ast.parse(open('.aitask-scripts/lib/agent_model_picker.py').read())"`
   - `python -c "import ast; ast.parse(open('.aitask-scripts/lib/agent_command_screen.py').read())"`

A dedicated `manual_verification` follow-up sibling task is appropriate and
will be offered at Step 8c.

---

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: archive the task and plan via
`./.aitask-scripts/aitask_archive.sh 716`, then push.
