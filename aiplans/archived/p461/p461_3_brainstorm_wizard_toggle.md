---
Task: t461_3_brainstorm_wizard_toggle.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_1_*.md, aitasks/t461/t461_2_*.md, aitasks/t461/t461_4_*.md, aitasks/t461/t461_5_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md, aiplans/archived/p461/p461_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_3 — Brainstorm wizard "Launch mode" toggle

## Context

Parent task t461 adds interactive launch mode for agentcrew code agents
(runner + `ait crew addwork --launch-mode` flag shipped in t461_1; an
`ait crew setmode` CLI shipped in t461_2). This child task exposes that
capability in the **brainstorm TUI wizard** so users can pick
interactive vs headless when creating a new brainstorm operation —
avoiding the need to edit yaml or call `ait crew setmode` after the
fact.

t461_5 (per-type defaults) has **not** landed. The implementation must
gracefully fall back to `headless` when `BRAINSTORM_AGENT_TYPES` does
not carry a `launch_mode` key.

## Design choice — one toggle on the confirm screen

The original draft plan proposed per-op mounting (config step for
explore/compare/hybridize/patch, inline on confirm for detail, because
detail has no config step). After verification against the current
code, a uniform approach is cleaner:

- **One place to mount**: `_actions_show_confirm()` adds the
  launch-mode widget for all design ops
  (explore/compare/hybridize/detail/patch), just above the Launch/Back
  buttons.
- **One place to read**: `_execute_design_op()` queries the widget on
  the UI thread (before spawning the `@work(thread=True)` worker) and
  stashes the value in `self._wizard_config["launch_mode"]`.
- **No per-op toggle mounting, no detail special-case.**

Rationale: the launch mode is the last decision before launching, so
the confirm screen is where users expect it. Session ops
(pause/resume/finalize/archive) continue to skip it — they don't
register agents.

## Widget choice — `CycleField`, not `Switch`

The existing wizard already uses `CycleField` for two-state selection
(`_config_explore_no_node` uses it for "Parallel explorers"). Reusing
it keeps the style consistent and avoids a new `Switch` import. The
class is defined at `brainstorm_app.py:429` and has the needed
`current_value` property and `id=` kwarg.

## Files to modify

1. `.aitask-scripts/brainstorm/brainstorm_app.py`
   - New helper: map wizard op → brainstorm agent type, and resolve
     the effective default via
     `BRAINSTORM_AGENT_TYPES.get(type, {}).get("launch_mode",
     "headless")`.
   - `_actions_show_confirm()` — mount
     `CycleField("Launch mode", ["headless", "interactive"],
     initial=<default>, id="launch-mode-field")` for design ops only
     (not session ops), plus a small `Static` hint if
     `is_tmux_available()` is False.
   - `_execute_design_op()` — before calling `_run_design_op()`, read
     the `CycleField` value on the UI thread and store it in
     `self._wizard_config["launch_mode"]`.
   - `_run_design_op()` — read `cfg.get("launch_mode", "headless")` and
     pass it as a kwarg to each `register_*` call.
   - `_build_summary()` — add one line for design ops: `[bold]Launch
     mode:[/] <default> (editable below)`.
   - Add `from agent_launch_utils import is_tmux_available`. The
     `.aitask-scripts/lib` path is inserted by `brainstorm_crew.py`
     which is imported earlier, so `agent_launch_utils` resolves
     directly; add a local `sys.path.insert` as a defensive fallback
     if the import fails during py_compile.

2. `.aitask-scripts/brainstorm/brainstorm_crew.py`
   - `register_explorer`, `register_comparator`,
     `register_synthesizer`, `register_detailer`, `register_patcher` —
     add `launch_mode: str = "headless"` kwarg, forward to
     `_run_addwork`.
   - `_run_addwork()` — add `launch_mode: str = "headless"` parameter.
     Append `["--launch-mode", launch_mode]` to `cmd` **only when
     `launch_mode == "interactive"`**. This keeps the common case
     (headless) lean and matches the addwork default, and avoids
     depending on a t461_5-style per-type default comparison that
     doesn't exist yet.

## Implementation steps

### 1. `brainstorm_app.py`: import + helper

Add near the `brainstorm.brainstorm_crew` imports block:

```python
from agent_launch_utils import is_tmux_available
```

Add a small module-level helper (near the top of the file, after the
constants block):

```python
_WIZARD_OP_TO_AGENT_TYPE = {
    "explore": "explorer",
    "compare": "comparator",
    "hybridize": "synthesizer",
    "detail": "detailer",
    "patch": "patcher",
}

def _brainstorm_launch_mode_default(wizard_op: str) -> str:
    from brainstorm.brainstorm_crew import BRAINSTORM_AGENT_TYPES
    agent_type = _WIZARD_OP_TO_AGENT_TYPE.get(wizard_op, "")
    return BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get(
        "launch_mode", "headless"
    )
```

### 2. `_actions_show_confirm()` — mount the toggle

In `_actions_show_confirm()` (around 2064), after the summary Static
mount but before the Horizontal(Button, Button) row, add:

```python
is_session_op = self._wizard_op in ("pause", "resume", "finalize", "archive")
if not is_session_op:
    default_mode = _brainstorm_launch_mode_default(self._wizard_op)
    container.mount(
        CycleField("Launch mode", ["headless", "interactive"],
                   initial=default_mode, id="launch-mode-field")
    )
    if not is_tmux_available():
        container.mount(
            Static(
                "[dim]tmux not installed — interactive will fall back "
                "to a standalone terminal (no monitor integration)[/]",
                classes="actions_hint",
            )
        )
```

### 3. `_execute_design_op()` — read the value on the UI thread

```python
def _execute_design_op(self) -> None:
    status = self.session_data.get("status", "")
    if status == "init":
        save_session(self.task_num, {"status": "active"})
        self.session_data["status"] = "active"
    try:
        field = self.query_one("#launch-mode-field", CycleField)
        self._wizard_config["launch_mode"] = field.current_value
    except Exception:
        self._wizard_config["launch_mode"] = "headless"
    self._run_design_op()
```

### 4. `_run_design_op()` — thread the value through

At the top of `_run_design_op()`:

```python
launch_mode = cfg.get("launch_mode", "headless")
```

Then each `register_*` call gets `launch_mode=launch_mode`:

```python
agent = register_explorer(
    self.session_path, crew_id, cfg["mandate"],
    cfg["base_node"], group_name, agent_suffix=suffix,
    launch_mode=launch_mode,
)
```

Same pattern for `register_comparator`, `register_synthesizer`,
`register_detailer`, `register_patcher`.

### 5. `_build_summary()` — show the default in the summary

At the end of `_build_summary()`, if the op is a design op, append:

```python
if op not in ("pause", "resume", "finalize", "archive"):
    default_mode = _brainstorm_launch_mode_default(op)
    lines.append(f"[bold]Launch mode:[/] {default_mode} (editable below)")
```

### 6. `brainstorm_crew.py`: extend `_run_addwork` and `register_*`

`_run_addwork` signature:

```python
def _run_addwork(
    crew_id: str,
    agent_name: str,
    agent_type: str,
    group_name: str,
    work2do_path: Path,
    launch_mode: str = "headless",
) -> str:
    ...
    cmd = [
        "./ait", "crew", "addwork",
        "--crew", crew_id,
        "--name", agent_name,
        "--work2do", str(work2do_path),
        "--type", agent_type,
        "--group", group_name,
        "--batch",
    ]
    if launch_mode == "interactive":
        cmd.extend(["--launch-mode", "interactive"])
    ...
```

Each `register_*` function adds `launch_mode: str = "headless"` to its
signature and forwards it to `_run_addwork(... launch_mode=launch_mode)`.

**Ordering note**: `launch_mode` goes at the end of each signature
(kwarg with default), so existing callers in other modules (if any)
remain source-compatible.

## Verification

1. Static checks:
   - `python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py`
   - `python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_crew.py`

2. Manual smoke test inside a brainstorm session:
   - `./ait brainstorm <task>`
   - Confirm screen shows `Launch mode: [headless] | interactive`
   - For each of explore/compare/hybridize/detail/patch:
     - Launch with default → agent's `_status.yaml` has
       `launch_mode: headless`
     - Flip toggle, launch → `_status.yaml` has
       `launch_mode: interactive`
   - With `tmux` not in PATH, the hint line appears.

3. Runner path: inside a tmux session, run the crew runner. Interactive
   agents spawn `agent-<name>` windows; headless agents spawn via
   `Popen` as before.

4. Regression: no brainstorm-specific test file exists today; the
   py_compile checks plus manual smoke test cover the change.

## Dependencies & notes

- **t461_1** (merged): provides the `--launch-mode` flag consumed by
  `_run_addwork`, and the runner's interactive branch.
- **t461_2** (merged): provides `ait crew setmode` for post-creation
  edits; not used here but relevant context for t461_4.
- **t461_5** (not yet landed): will add `launch_mode` keys to
  `BRAINSTORM_AGENT_TYPES`. This task's helper gracefully degrades to
  `"headless"` until that ships. Once t461_5 lands, the default simply
  picks up the new value with no code change here.

## Post-Review Changes

### Change Request 1 (2026-04-13 — during review)
- **Requested by user:** Up/down arrow keys did not navigate the Launch
  mode toggle or other focusable widgets on the confirm screen (as they
  do on the operation/node-select wizard pages).
- **Changes made:**
  - `_actions_show_confirm()` now calls
    `self.call_after_refresh(self._focus_confirm_start)` so the first
    focusable widget on the confirm screen (the CycleField, or the
    Launch button on session ops) is focused on entry.
  - New `_focus_confirm_start()` helper finds the first focusable
    descendant of `#actions_content` and focuses it.
  - New `_cycle_confirm_focus(direction)` helper cycles focus among
    all focusable descendants of `#actions_content` (CycleField +
    Launch/Back buttons).
  - `on_key()` gained a new branch for the confirm step:
    `if event.key in ("up","down") and self._wizard_step ==
    self._wizard_total_steps: self._cycle_confirm_focus(...)`.
    Cycling wraps (down from Back goes to CycleField, up from
    CycleField goes to Back) — a deliberate difference from
    `_navigate_rows`, which does not wrap. Wrapping is better on the
    confirm step because the focus chain is short (3 widgets) and the
    user may want to flip the toggle after first seeing the Launch
    button.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`

## Notes for sibling tasks

- `_run_addwork` only emits `--launch-mode` for `interactive`. If
  t461_5 wants more sophisticated emission (e.g. drop `--launch-mode`
  when the value matches the per-type default), it can add that logic
  on top of the simple conditional here — not a breaking change.
- The CycleField id `#launch-mode-field` is the contract for
  `_execute_design_op` to read the value. Keep the id stable if
  t461_4 (brainstorm status edit) wants to reuse the same widget
  pattern on the status tab.
- The focus-cycling helper `_cycle_confirm_focus` and the
  `call_after_refresh(self._focus_confirm_start)` pattern in
  `_actions_show_confirm` are generic — they operate on any focusable
  descendant of `#actions_content`. If t461_4 adds new focusable
  widgets to the confirm step (e.g., an edit-mode CycleField for
  changing an existing agent's launch mode), they'll pick up
  arrow-key navigation for free.

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/brainstorm/brainstorm_app.py` (~+100 lines): added
    `from agent_launch_utils import is_tmux_available`, the
    `_WIZARD_OP_TO_AGENT_TYPE` map + `_brainstorm_launch_mode_default`
    helper, a CycleField mount in `_actions_show_confirm` (with
    optional tmux-unavailable hint), a widget read in
    `_execute_design_op` that stashes `launch_mode` into
    `self._wizard_config` on the UI thread, a kwarg pass-through in
    `_run_design_op` for all 5 register_* calls, and one line in
    `_build_summary` showing the default launch mode. Added
    `_focus_confirm_start` and `_cycle_confirm_focus` helpers plus a
    new `on_key` branch so up/down cycles focus among the confirm
    screen's focusable widgets (CycleField + Launch + Back).
  - `.aitask-scripts/brainstorm/brainstorm_crew.py` (~+33 lines): all
    5 `register_*` functions plus `_run_addwork` now accept
    `launch_mode: str = "headless"` as a trailing kwarg. `_run_addwork`
    appends `["--launch-mode", "interactive"]` to the `./ait crew
    addwork` command only when the value is `"interactive"`, matching
    the addwork default for headless.

- **Deviations from plan:**
  - Used `CycleField` (existing wizard widget) instead of Textual's
    `Switch` — documented in the plan design section. Avoids a new
    widget import and matches the visual style of the "Parallel
    explorers" picker in the config step.
  - Toggle is mounted on the confirm screen for ALL design ops, not
    split per-op (config step for explore/compare/hybridize/patch,
    inline for detail as the archived-draft plan suggested). One mount
    site, one read site — no detail special-case.
  - Did NOT add a `Static` hint when tmux is available — the hint is
    only shown when `is_tmux_available()` returns False.

- **Issues encountered:**
  - During user review, the CycleField on the confirm screen could not
    be focused via up/down arrows (the user expected arrow navigation
    to work as it does on the operation/node-select wizard pages).
    Root cause: `on_key` only handled up/down in wizard steps 1-2 for
    `OperationRow` widgets; the confirm step had no arrow navigation
    and relied on Tab-based focus traversal. Fixed by adding
    `_focus_confirm_start` (called via `call_after_refresh` when the
    confirm screen is shown) and `_cycle_confirm_focus` (called from
    a new `on_key` branch guarded by
    `self._wizard_step == self._wizard_total_steps`).

- **Key decisions:**
  - **`_run_addwork` keeps the command lean for headless.** Since
    addwork's default is headless, we only pass `--launch-mode
    interactive` when that's the chosen value. t461_5 can later add
    "drop when matches per-type default" on top of this without a
    behavioral break.
  - **Helper degrades to `"headless"`** when `BRAINSTORM_AGENT_TYPES`
    has no `launch_mode` key (t461_5 not yet landed). No code change
    needed here when t461_5 merges; the helper picks up the new key
    automatically via the `.get(... "headless")` fallback.
  - **Confirm-step focus cycling wraps.** `_navigate_rows` (used for
    operation/node lists) does not wrap — it stops at the bottom and
    sends the user to the Tabs bar when going up past the top. The
    confirm-step equivalent `_cycle_confirm_focus` wraps instead,
    because the focus chain is short (at most 3 widgets) and users
    may want to flip the toggle after seeing the Launch button.
  - **Kwarg ordering**: `launch_mode` goes at the end of each
    `register_*` signature so existing positional callers (if any in
    other modules) stay source-compatible.

- **Verification results:**
  - `python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py`
    — OK
  - `python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_crew.py`
    — OK
  - Runtime import smoke test: `import brainstorm.brainstorm_app as
    ba` succeeds; `_brainstorm_launch_mode_default('explore')` returns
    `'headless'`; `_brainstorm_launch_mode_default('detail')` returns
    `'headless'` (t461_5 not yet landed); `is_tmux_available()`
    returns True on this host; `BrainstormApp` has both the new
    `_cycle_confirm_focus` and `_focus_confirm_start` helpers.
  - Manual end-to-end TUI verification (brainstorm wizard confirm
    screen: toggle visible, arrow navigation working, launch writes
    correct yaml, tmux window spawn) was performed by the user during
    the review loop.
