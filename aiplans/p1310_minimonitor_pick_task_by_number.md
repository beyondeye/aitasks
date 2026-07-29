---
Task: t1310_minimonitor_pick_task_by_number.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1310 — Minimonitor: pick a task by number (`p`)

## Context

At the end of a codeagent run the agent reports follow-up tasks it created, or a
task to pick next — as bare numbers. Acting on that today means leaving the
agent's window, opening `ait board`, finding the card, pressing `p`. The
minimonitor is already docked beside the agent but has **no way to target an
arbitrary task**: `n` only ever resolves the followed pane's next *Ready sibling*
(`find_next_sibling`), and every other picker in the repo is list-based. This
adds a direct "type a task number → confirm → launch" path, with an opt-in
"also kill the followed agent" checkbox.

Kill semantics are deliberately **`n`'s mechanism, unchanged** — no idle/busy
probe (user decision). The difference is that the kill is driven by an explicit
checkbox instead of `n`'s task-status heuristic.

## Design

Key `p` → `action_pick_task_by_number`:

1. Resolve the followed agent (`_find_own_agent_snapshot`, may be `None`), its
   project root (`_root_for_snap`) and session.
2. **Dialog 1** — `TaskNumberInputModal` (new, `monitor_shared.py`): one `Input`
   + OK/Cancel. Dismisses the raw string or `None`.
3. Normalize + **validate before any downstream use**, then resolve via
   `TaskInfoCache.get_task_info`.
4. **Dialog 2** — `TaskPickConfirmDialog(TaskDetailDialog)` (new subclass): the
   inherited detail body plus a `Checkbox` and OK/Cancel. Dismisses
   `(True, kill_bool)` or `None`.
5. On OK → shared `_launch_pick(target_id, target_root, kill_pane_id)`, extracted
   from today's `_launch_pick_for_own` so `n` and `p` share one implementation.

### Why a subclass, not kwargs on `TaskDetailDialog`

`TaskDetailDialog` (`monitor_shared.py:147`) is used by `i`/`I`
(`minimonitor_app.py:1525`) and the full monitor (`monitor_app.py:2326`).
Subclassing makes "existing `i`/`I` behaviour unchanged" true **by
construction** — the base keeps its exact BINDINGS, CSS, `AUTO_FOCUS`, compose
order and `None` dismissal, and both existing call sites are literally untouched.
It also gives one dismissal type per class instead of `if self._confirm:`
branching through `compose` / `on_mount` / `action_dismiss_dialog`.

Textual cooperates: type selectors match base classes, so
`TaskDetailDialog { align: center middle; }` and `#task-detail-dialog {…}` apply
to the subclass automatically; `DEFAULT_CSS` merges along the MRO with the
subclass winning ties, so the `.narrow` and confirm-row rules live **only** in
the subclass. That also makes the negative control clean — patch the
*subclass's* `DEFAULT_CSS` and re-run the width assertion.

Extract the base's `compose` body into a `_detail_widgets()` generator that both
classes drive, so `action_toggle_plan` (which queries `#task-detail-scroll` /
`#task-detail-header`) is inherited verbatim and works unchanged.

---

## Files to modify

| File | Change |
|---|---|
| `.aitask-scripts/monitor/monitor_core.py` | Add `TaskInfo.depends` (defaulted) + `TaskInfoCache.blocking_dependencies()` |
| `.aitask-scripts/monitor/monitor_shared.py` | Add `TaskNumberInputModal`, `TaskPickConfirmDialog`; refactor `TaskDetailDialog.compose` → `_detail_widgets()` |
| `.aitask-scripts/monitor/minimonitor_app.py` | New binding + action; extract `_launch_pick`; key-hints line |
| `tests/test_minimonitor_pick_next_characterization.py` | **New — written and passing BEFORE the refactor** |
| `tests/test_minimonitor_pick_by_number.py` | New — the feature |
| `tests/test_minimonitor_own_task_info.py` | Key-hints assertion unchanged; verify still passes |
| `website/content/docs/tuis/minimonitor/how-to.md` (key table ~`:202-216`) | Add `p`; fix existing drift |

---

## Step 1 — Characterization tests for `n` (do this first)

`_launch_pick_for_own` has **no unit coverage today** (only a `hasattr` smoke at
`tests/test_multi_session_minimonitor.sh:56`). Write
`tests/test_minimonitor_pick_next_characterization.py` against the **current**
code; it must pass unchanged after the refactor.

App stub via `MiniMonitorApp.__new__` (pattern:
`tests/test_minimonitor_own_task_info.py:91-104`), spies for
`push_screen`/`notify`, a fake `_monitor`, and patches on
`mm.resolve_dry_run_command`, `mm.resolve_agent_string`, `mm.resolve_skill_profile`,
`mm.launch_in_tmux`, `mm.maybe_spawn_minimonitor`, `mm.AgentCommandScreen`.

Assert:

1. **Golden `AgentCommandScreen` kwargs** — `Pick Task t<id>`, `prompt_str`,
   `default_window_name=agent-pick-<id>`, `project_root=_root_for_snap(snap)`,
   `operation="pick"`, `operation_args=[id]`, `skill_name="pick"`, `narrow=True`.
   This is what later proves `n` and `p` share one implementation.
2. **`screen.full_command` wins** — mutate the constructed screen's
   `full_command` after construction; assert `launch_in_tmux` got the *mutated*
   value, not the pre-resolved `full_cmd`. (`minimonitor_app.py:1034` reads
   `screen.full_command`; the user can change agent/model in the dialog.)
3. **Kill heuristic table** — `("123", Implementing) → kill`,
   `("123_4", Done) → kill`, `("123_4", info=None) → kill`,
   `("123_4", Implementing) → no kill`; assert the pane id passed.
4. **Ordering** — one shared call log; `launch_in_tmux` index < 
   `kill_agent_pane_smart` index (the `:991-998` docstring invariant).
5. **Non-launch results** — `None` (cancel), `"run"`, and `err != None`: no
   `kill_agent_pane_smart`, no `maybe_spawn_minimonitor`. Refresh **is**
   scheduled for `None` and `"run"`, and **is not** for the `err` path
   (`:1036-1037` returns before `call_later`) — preserve this asymmetry.
6. **`maybe_spawn_minimonitor` only when `pick_result.new_window`.**
7. **`_focused_pane_id = None` only on the kill branch** (`:1049`).
8. **Guards** — `resolve_dry_run_command → None` ⇒ error notify + no push;
   missing snapshot ⇒ `"Followed agent no longer exists"` + no push;
   `self._monitor is None` ⇒ **silent** return (no notify), unlike
   `action_pick_next_for_own:930-932` which does notify.
9. **Decision timing** — `get_task_info` is called *before* `push_screen`, and
   `_launch_pick_for_own` performs **no** `invalidate` (it deliberately reuses
   the cache warmed at `action_pick_next_for_own:942-943`; adding one would
   change `n`'s kill decision).

## Step 2 — `monitor_core.py`: eligibility inputs

`find_ready_siblings`' `blocking_ids` (`monitor_core.py:2694-2707`) is **not**
reusable here — it is scoped to one parent directory and deliberately drops
cross-parent deps. Two small additions instead:

### 2.1. `TaskInfo.depends`

Add `depends: list[str] = field(default_factory=list)` after the existing
defaulted `task_file_abs` (`monitor_core.py:2418`), populated in `_resolve` from
the already-parsed `metadata` with the same normalization
`find_ready_siblings` uses (`[str(d).lstrip("t") for d in metadata.get("depends", []) or []]`).

Defaulted so **every** existing construction is untouched — including the
keyword-arg stub at `tests/test_minimonitor_own_task_info.py:47-58`, which must
keep working unchanged.

### 2.2. `TaskInfoCache.blocking_dependencies(info, session_name="", *, refresh=True) -> list[str]`

Takes an **already-resolved `TaskInfo`**, not an id — the caller has just
invalidated and re-read the target for the dialog body, so this signature makes
each task file read exactly once and keeps the dep-freshness contract entirely
inside the method.

For each entry in `info.depends`, resolve it and keep it when **not** satisfied:

- resolved and `status != "Done"` → blocking;
- unresolvable (`None`) → blocking, so a dangling dep is visible rather than
  silently treated as satisfied (fail-closed);
- resolved with `status == "Done"` (this includes archived tasks — `_resolve`
  searches `aitasks/archived/`) → not blocking.

**Freshness is load-bearing — `refresh=True` invalidates each dep before
resolving it.**

```python
for dep in info.depends:
    if refresh:
        self.invalidate(dep, session_name)
    dep_info = self.get_task_info(dep, session_name)
    if dep_info is None or dep_info.status != "Done":
        blocking.append(dep)
```

`TaskInfoCache` entries are **process-lifetime**: `_refresh_data` clears only
`_gate_cache` (`minimonitor_app.py:438`), and `update_session_mapping` (`:433`)
clears only when the session→root mapping actually changes. The sole
invalidations are the explicit per-task ones at `:942` and `:1520`. A minimonitor
docked beside an agent runs for hours, and a dependency flipping `Ready → Done`
while it is open (a sibling agent finishing) is the *normal* case — so a cached
read would show `⛔ blocked by t<x>` for a dependency that completed long ago,
and the `Launch anyway` relabel would fire on a task that is in fact pickable.

This also keeps the new badge at parity with the surface it imitates:
`find_ready_siblings` (`monitor_core.py:2657-2686`) computes its `blocking_ids`
by reading every sibling file **from disk on each call**, never through the
cache. `refresh=False` exists only so the tests can exercise the stale path as a
negative control.

Cost is bounded and paid once per `p` press: one small file read per dependency
(typically 0–3).

## Step 3 — `monitor_shared.py`

### 3a. `TaskDetailDialog` — extract, do not change

Split `compose` (`:177-196`) into:

```python
def _detail_widgets(self):        # yields header, meta, scroll, (no footer)
    ...
def compose(self) -> ComposeResult:
    with Container(id="task-detail-dialog"):
        yield from self._detail_widgets()
        plan_hint = "  [dim]p: switch plan/task[/]" if self._info.plan_content else ""
        yield Static(f"[dim]q/Esc: close[/]{plan_hint}", id="task-detail-footer")
```

Nothing else in the class moves. Rendered output must be byte-identical.

### 3b. `TaskNumberInputModal(ModalScreen)`

Follow `_RepointInputScreen` (`lib/stale_entry_modal.py:31-87`) for the Input
pattern and `NextSiblingDialog` (`monitor_shared.py:313-326`) for the `.narrow`
CSS shape.

- `__init__(self, narrow: bool = False)`.
- `compose`: `Container(id="task-num-dialog")` → header
  `[bold]Pick Task by Number[/]`, `Input(placeholder="task number, e.g. 1310 or 1310_2", id="task-num-input")`,
  hint `[dim]Enter: OK   Esc: cancel[/]`, then
  `Container(id="task-num-buttons")` with OK (primary) / Cancel.
- `on_mount`: focus the Input.
- `on_input_submitted` → `dismiss(value)`; `on_button_pressed` → OK dismisses the
  Input's value, Cancel dismisses `None`;
  `Binding("escape", "dismiss_dialog")` → `dismiss(None)`.
- `.narrow` CSS: `width: 90%; min-width: 30;` and vertical button stack
  (`layout: vertical; Button { width: 1fr; margin: 0 0 1 0; }`) — same shape as
  `NextSiblingDialog.narrow`.

### 3c. `TaskPickConfirmDialog(TaskDetailDialog)`

```python
def __init__(self, info, *, kill_target_label: str | None = None,
             already_running: str | None = None,
             blocking: list[str] | None = None, narrow: bool = False) -> None
```

- `compose`: `if narrow: self.add_class("narrow")`; then
  `Container(id="task-detail-dialog")` → `yield from self._detail_widgets()`;
  then, **before** the footer, a `Container(id="pick-confirm-row")` holding:
  - **Eligibility warnings** (`id="pick-eligibility"`, styled `$warning` /
    `$error`), rendered when either applies:
    - `info.status != "Ready"` →
      `⚠ t<id> is <status> — not Ready to pick`
      (covers `Done`, archived, `Implementing`, `Postponed`, `Editing`,
      `Folded`);
    - `blocking` non-empty → `⛔ blocked by t<a> t<b>` (same glyph and shape as
      `_SiblingRow.render`, `monitor_shared.py:406-411`, so the two surfaces read
      identically);
  - an optional `Static` warning when `already_running` is set;
  - the `Checkbox` **only when `kill_target_label` is not None**, `value=False`
    (always unchecked — user decision), with a **short** label
    `"kill followed agent"` plus a separate `Static` giving the detail
    (`t<id> · <status> · <window>`);
  - `Button("OK", …)` / `Button("Cancel", id="btn-pick-cancel")`. When **either**
    eligibility warning fired, the OK button is
    `Button("Launch anyway", variant="warning", id="btn-pick-ok")` instead of
    `Button("OK", variant="primary", id="btn-pick-ok")` — the override is
    explicit and visible in the control the user actually presses, without a
    second dialog. `p` still *permits* the launch (the user asked to pick by
    number); it just never lets it happen silently.
- `on_mount`: **confirm-mode only** — focus the OK button. The base's default
  `AUTO_FOCUS = "*"` lands on `#task-detail-scroll` (a focusable `VerticalScroll`),
  which is correct for `i`/`I` (arrows scroll the body) and must not change.
- `on_button_pressed`: OK → `dismiss((True, checkbox.value if present else False))`;
  Cancel → `dismiss(None)`.
- Override `action_dismiss_dialog` → `dismiss(None)` so the inherited `q`/`Esc`
  mean **cancel**, not a truthy tuple.
- `.narrow` CSS on the subclass only: widen the dialog, stack the buttons
  vertically, and give the checkbox `width: 1fr`.

**Label width trap.** `ToggleButton` is `width: auto; text-wrap: nowrap;
text-overflow: ellipsis` with a `tall` border. At 40 cols the dialog is ~36 wide,
minus `padding: 1 2` → 32 content cols, minus checkbox chrome (~8) → ~24 cols of
label. `"also kill the followed codeagent"` (32 chars) silently renders as
`also kill the followed c…` — **inside** the dialog region, so a region-based
test passes. Hence the short label + separate `Static`, and hence the rendered-
text assertion in Step 5.

## Step 4 — `minimonitor_app.py`

### 4a. Extract `_launch_pick`

```python
def _launch_pick(self, target_id: str, target_root: Path,
                 kill_pane_id: str | None) -> None:
```

Move the body of `_launch_pick_for_own` from the `resolve_dry_run_command` call
(`:1006`) through `push_screen(screen, on_pick_result)` (`:1052`) verbatim,
replacing only the kill decision:

```python
if kill_pane_id and self._monitor is not None:
    self._monitor.kill_agent_pane_smart(kill_pane_id)
    self._focused_pane_id = None
```

Keep, unchanged: `self._monitor is None` silent guard; `screen.full_command` at
the `launch_in_tmux` call; the early `return` on `err` (before `call_later`);
`maybe_spawn_minimonitor` gated on `pick_result.new_window`; all notify strings.

`_launch_pick_for_own` keeps its snapshot lookup, the `"Followed agent no longer
exists"` stale guard, and its **existing** `current_info` read at `:1005` (do not
move it into the callback — a task completing while `AgentCommandScreen` is open
would otherwise flip the decision). It computes `should_kill` from the unchanged
heuristic and calls
`self._launch_pick(target_id, target_root, pane_id if should_kill else None)`.

### 4b. Binding + key hints

- `Binding("p", "pick_task_by_number", "Pick task", show=False)` in `BINDINGS`
  (`:185-202`). Registration with `keybinding_registry` is automatic via
  `ShortcutsMixin.__init__` → `register_app_bindings("minimonitor", BINDINGS)`.
- `#mini-key-hints` (`:271-278`): last line becomes
  `"c:concerns  p:pick task"` (23 cols, within the 38-col budget asserted by
  `tests/test_minimonitor_own_task_info.py:125`). *Convention note:* the hint
  strings hardcode literal keys for every existing action; keep that convention
  rather than resolving through `resolve_key` for this one entry.

**No `check_action`.** Minimonitor has none, and none is needed: Textual's
`_modal_binding_chain` truncates the chain at the first modal screen, so the
app-level `p` cannot fire from inside `TaskDetailDialog` (whose own `p` toggles
the plan) or `AgentCommandScreen` (whose `p` copies the prompt). This is pinned
by a test in Step 5.

### 4c. `action_pick_task_by_number`

```python
_PICK_ID_RE = re.compile(r"\d+(?:_\d+)?")   # module-level, matches _TASK_ID_RE's shape
```

0. **Upfront monitor guard — mirror `action_pick_next_for_own:930-932` exactly:**
   ```python
   if self._monitor is None:
       self.notify("Monitor not ready", severity="warning")
       return
   ```
   Without this the user completes *both* dialogs and `_launch_pick`'s inherited
   silent `self._monitor is None` return (`:999-1000`, preserved verbatim so the
   `n` characterization keeps passing) makes the confirmation appear to do
   nothing. The guard belongs at the **entry** of the action, before any dialog
   is pushed — this is the one place `p` must not simply inherit `n`'s
   deep-and-silent behaviour.
1. `snap = self._find_own_agent_snapshot()` (may be `None`).
   `root = self._root_for_snap(snap) if snap else self._project_root`;
   `sess = snap.pane.session_name if snap else self._session`.
2. `self.push_screen(TaskNumberInputModal(narrow=True), callback=…)`.
3. Callback:
   - `raw` falsy → return silently (user cancelled).
   - `tid = raw.strip().lstrip("t")`; `if not _PICK_ID_RE.fullmatch(tid):`
     → `notify(f"Not a task number: {raw!r}", severity="warning")`, **return
     before any resolution**.
   - `self._task_cache.invalidate(tid, sess)`;
     `info = self._task_cache.get_task_info(tid, sess)`;
     `None` → `notify(f"Task t{tid} not found", severity="warning")`, return.
   - `blocking = self._task_cache.blocking_dependencies(info, sess)` — pass the
     `TaskInfo` just resolved above; the method refreshes each dependency itself.
   - `already` — scan `self._snapshots` for an `AGENT` snapshot whose
     `get_task_id_for_pane(...) == tid`, **scoped to the same session**:
     ```python
     if s.pane.category is PaneCategory.AGENT and s.pane.session_name in ("", sess)
     ```
     Task ids are derived from the window name alone
     (`monitor_core.py:2530-2545`), so an unscoped scan warns about an unrelated
     `t<id>` in another project whenever multi-session mode (`M`) is on. One
     tmux session maps to exactly one project root
     (`get_session_to_project_mapping`), so session scope is the correct
     project scope, and it matches `_find_own_agent_snapshot`'s own
     `session_name in ("", self._session)` rule (`:509`). Warning text names the
     window unambiguously:
     `⚠ t<id> is already running in this session, window <index>:<name>`.
   - `kill_label` = `None` when `snap is None`, else
     `f"t{own_tid or '?'} · {own_status} · {snap.pane.window_name}"`.
   - push `TaskPickConfirmDialog(info, kill_target_label=kill_label,
     already_running=already, blocking=blocking, narrow=True)`.
4. Confirm callback: `result` falsy → return. Else
   `ok, kill = result`; if `kill` re-check `self._snapshots.get(kill_pane_id)` and
   `notify("Followed agent no longer exists — launching without kill",
   severity="warning")` when gone; then
   `self._launch_pick(tid, root, kill_pane_id if kill else None)`.

**Why validate before resolving.** `TaskInfoCache._resolve`
(`monitor_core.py:2727-2742`) interpolates the id straight into
`Path.glob(f"t{task_id}_*.md")`. A metacharacter (`12*`, `1[0-9]`) matches an
*unrelated* task file, so the dialog would show one task while
`/aitask-pick 12*` launches on the literal string. This is a **correctness**
guard, not a shell-injection one: `aitask_codeagent.sh` emits its dry-run command
with `printf ' %q'` (`:601-605`), so each argv element reaching `tmux new-window`
is already shell-quoted.

**Deliberate scope decisions** (state in the plan, don't discover at review):
- `p` **permits** targeting a non-`Ready` or dependency-blocked task — `_resolve`
  searches `aitasks/archived/` too, and the user explicitly asked to pick "an
  aitask by number". `n` cannot (it filters `Ready`). The permissiveness is
  intended; the *silence* is not, so both conditions raise an explicit warning
  and relabel OK to `Launch anyway` (Step 3 §3c). This is no longer deferred.
- `blocking_dependencies` reports **all** unsatisfied deps, including
  cross-parent ones — a superset of the sibling-only `blocking_ids` that
  `ChooseSiblingModal` shows. The glyph and wording are kept identical so the
  two surfaces read the same.

## Step 5 — Docs

`website/content/docs/tuis/minimonitor/how-to.md` key table (~`:202-216`) is
already stale: it lists an `r` refresh key that has no binding and omits
`k`, `n`, `E`, `d`, `m`. Add `p` and fix the drift in the same pass, deriving the
table from `MiniMonitorApp.BINDINGS` (`:185-202`).

## Step 6 — Tests for the new path

`tests/test_minimonitor_pick_by_number.py` (stub style as Step 1):

- **Binding** — `("p", "pick_task_by_number")` in `BINDINGS`; negative control:
  `("n", "pick_next_for_own")` still present.
- **Key hints** — `"p:pick"` present; every line ≤ 38 cols.
- **Validation** — accepted: `1310`, `t1310`, `" 1310 "`, `1310_2`. Rejected:
  `""`, `abc`, `12*`, `1[0-9]`, `13-10`, `1;id`. For each rejection assert
  `notify(severity="warning")` **and zero calls** to `get_task_info` /
  `resolve_dry_run_command`.
- **Monitor not ready** — `self._monitor is None` ⇒ `notify("Monitor not ready",
  severity="warning")` and **zero** `push_screen` calls. Negative control: with
  `_monitor` set, the input modal *is* pushed. (This is the "confirmation appears
  to do nothing" failure mode; assert it at the entry, not at launch.)
- **Unknown id** → warning, no second dialog.
- **Valid id** → `TaskPickConfirmDialog` pushed with the resolved `TaskInfo`.
- **Eligibility** — `status="Done"` ⇒ warning text present and the OK button
  reads `Launch anyway`; `blocking=["1200"]` ⇒ `⛔ blocked by t1200` present;
  `status="Ready"` + no deps ⇒ **neither** present and OK reads `OK`
  (the negative control that proves the warning is conditional).
- **`blocking_dependencies`** (unit, `monitor_core`) — against a **real
  `TaskInfoCache` over real files in a temp dir**, not a stub: dep `Done` ⇒ not
  blocking; dep `Ready` ⇒ blocking; dep that does not resolve ⇒ blocking
  (fail-closed); empty `depends` ⇒ `[]`.
- **Dependency freshness (the staleness regression)** — warm the cache by
  resolving the dependency while its file says `status: Ready`, then rewrite that
  file on disk to `status: Done`, then call `blocking_dependencies(info, sess)`
  and assert `[]`. **Negative control:** the same scenario with `refresh=False`
  must still report the dep as blocking — a passing negative control would mean
  the test never exercised the cache at all. Also assert the target task itself
  is read once (no double `_resolve` from a redundant re-invalidation).
- **`TaskInfo.depends` default** — constructing `TaskInfo(...)` with the exact
  keyword set used at `tests/test_minimonitor_own_task_info.py:47-58` still
  works and yields `depends == []`.
- **Duplicate scan is session-scoped** — two AGENT snapshots in *different*
  sessions both named `agent-pick-1310`: selecting `1310` from session `s1`
  warns about the `s1` pane only, and warns **not at all** when the only match
  lives in another session. This is the cross-project false positive.
- **OK, unchecked** → `_launch_pick` with `kill_pane_id=None` — *even when the
  followed task is `Done`* (proves the checkbox, not `n`'s heuristic, decides).
- **OK, checked** → `kill_pane_id == followed pane id`.
- **Cancel / `q` / `Esc`** → no launch.
- **No followed agent** → no `Checkbox` in the composed dialog, and
  `kill_pane_id is None` reaches `_launch_pick`.
- **`"run"` and launch-`err` with the box ticked** → `kill_agent_pane_smart`
  **not** called.
- **Already-running** → the warning `Static` is present when another AGENT pane
  maps to the same task id.
- **Modal gating** — push `TaskDetailDialog`, press `p`, assert the plan toggled
  and no `TaskNumberInputModal` was pushed.
- **Shared implementation** — assert `n` and `p` produce identical
  `AgentCommandScreen` kwargs for the same target id (reuse the Step-1 golden).

Render level (`tests/test_agent_command_dialog_narrow.py` pattern):

- `run_test(size=(40, 50))` **and** `size=(40, 20)`: every `Button` / `Checkbox`
  / `Input` region sits inside `#task-detail-dialog` / `#task-num-dialog`.
- **Rendered-text assertion** (`_screen_text(app)` helper as in
  `tests/test_concern_picker_modal.py:74-82`): the full checkbox label and both
  button labels appear un-ellipsised. A region check alone passes on a truncated
  label — this is the assertion that actually discriminates.
- **Negative control** — patch `TaskPickConfirmDialog.DEFAULT_CSS` to drop the
  `.narrow` rules and assert the width/text test **fails**. A passing negative
  control means the test is not discriminating.

## Verification

```bash
python3 tests/test_minimonitor_pick_next_characterization.py   # must pass BEFORE and AFTER the refactor
python3 tests/test_minimonitor_pick_by_number.py
python3 tests/test_minimonitor_own_task_info.py                # i/I unchanged
bash tests/run_all_python_tests.sh                             # read ONLY the last line
```

Live check inside tmux (the only thing that proves visibility — a Textual test
does not):

```
ait minimonitor      # in a window beside a running agent
# press p → type 1310 → Enter → detail dialog → OK (box unchecked)
# confirm: new agent-pick-1310 window; followed agent still alive
# repeat with the box ticked; confirm the followed window dies AFTER the launch
```

---

## Risk

### Code-health risk: medium
- `_launch_pick_for_own` (`minimonitor_app.py:988-1052`) is a live agent-launch +
  pane-kill path with **zero unit coverage** today; extracting `_launch_pick`
  from it can silently change `n` in six documented ways (`screen.full_command`
  vs `full_cmd`, `current_info` read timing, the missing `invalidate`, the
  refresh asymmetry on launch failure, the silent `_monitor is None` guard, and
  `_focused_pane_id` scoping) · severity: medium · → mitigation: characterization
  suite in Step 1, written and passing against the *current* code before any
  refactor, and unchanged after.
- Touching `TaskDetailDialog`, shared with the full monitor
  (`monitor_app.py:2326`), risks regressing `i`/`I` · severity: low ·
  → mitigation: subclass instead of adding kwargs, so both existing call sites
  are literally untouched; `_detail_widgets()` extraction must leave rendered
  output byte-identical.
- A narrow-width regression is the repeat failure mode of this dialog family
  (t998, t1012, t1122, t1187) and region-only assertions do not catch the
  `text-overflow: ellipsis` case · severity: medium · → mitigation: rendered-text
  assertion at 40×50 **and** 40×20, plus a negative control that removes the
  `.narrow` CSS and proves the test fails.

- Adding `TaskInfo.depends` + `TaskInfoCache.blocking_dependencies` widens the
  blast radius into `monitor_core.py`, shared with the full monitor ·
  severity: low · → mitigation: the field is `field(default_factory=list)` at the
  end of the dataclass, so every existing construction — including the
  keyword-arg stub at `tests/test_minimonitor_own_task_info.py:47-58` — is
  unchanged; the new method is additive and has its own unit tests.
- The eligibility badge reads through `TaskInfoCache`, whose entries are
  **process-lifetime** in the minimonitor (only `_gate_cache` is cleared per
  refresh, `minimonitor_app.py:438`); a dependency completing while the TUI is
  open would otherwise be reported as still blocking, firing `Launch anyway` on
  a pickable task · severity: medium · → mitigation: `blocking_dependencies`
  invalidates each dependency before resolving it (`refresh=True` default),
  matching `find_ready_siblings`' read-from-disk-every-call behaviour; pinned by
  a real-files staleness test with a `refresh=False` negative control.

### Goal-achievement risk: low
- `p` permits `Done`/archived and dependency-blocked targets, unlike `n` — a
  user could launch one without noticing · severity: low · → mitigation:
  **in-scope** (Step 2 + Step 3 §3c): explicit `⚠ not Ready` / `⛔ blocked by`
  warnings and a `Launch anyway` OK button. Previously proposed as the deferred
  follow-up `minimonitor_pick_task_eligibility_signals`; pulled into this task,
  so **no `### Planned mitigations` subsection is recorded** and Step 8d creates
  nothing.
- Picking a task already running in another pane creates a duplicate
  `agent-pick-<id>` window, which can misdirect `maybe_spawn_minimonitor`
  (it keeps the *last* name match) · severity: low · → mitigation: a
  session-scoped "already running in this session, window N" warning in dialog 2
  so the user chooses knowingly; not blocked.

---

## Final Implementation Notes

- **Actual work done:** Implemented as planned, in plan order. `p` →
  `action_pick_task_by_number` → `TaskNumberInputModal` → validation →
  `TaskPickConfirmDialog` → shared `_launch_pick`. `_launch_pick` was extracted
  from `_launch_pick_for_own` behind a 19-test characterization suite written
  first; all 19 pass unchanged after the extraction. `monitor_core` gained
  `TaskInfo.depends` (defaulted) and `TaskInfoCache.blocking_dependencies`.
  Docs: added `p` to the minimonitor how-to plus a "How to Pick a Task by
  Number" section, and fixed the pre-existing key-table drift.

- **Deviations from plan:**
  - **Confirm row is docked, not flow-laid.** The plan sized the dialog with
    `height: 90%` and let the confirm row sit in normal flow. A live check at
    40x20 showed the buttons rendering *below* the dialog and off-screen
    entirely — the minimonitor pane is only as tall as the tmux window. Fixed
    structurally: `#pick-confirm-row` and the footer are `dock: bottom`, so the
    body scroll is what gives up space (`min-height: 1`). Also dropped the
    `tall` borders on the checkbox and buttons in narrow mode (two rows each in
    a pane with none to spare). Verified at 40x50, 40x20 and 40x16.
  - **Region-fit assertions now check both axes.** The planned test copied
    `test_agent_command_dialog_narrow.py`, which asserts x only — that is
    exactly why the vertical overflow above got through. `_assert_controls_inside`
    checks x *and* y; a second negative control (removing `dock: bottom`) proves
    it discriminates.
  - **Added a text restatement of the kill checkbox state.** Textual's
    `Checkbox` draws the same `X` slider glyph ticked or not — only the colour
    differs. For a control that closes down a running agent in a ~40-column
    pane that is too weak, so `#pick-kill-detail` now reads
    `keeps t<id> · …` / `KILLS t<id> · …` and updates on toggle.
  - **Validation framing corrected.** The plan called strict id validation a
    guard against a shell sink. It is not: `aitask_codeagent.sh` emits its
    dry-run command with `printf ' %q'` (`:601-605`), so every argv element
    reaching `tmux new-window` is already shell-quoted. The real defect it
    prevents is a *correctness* one — `TaskInfoCache._resolve` interpolates the
    id into `Path.glob`, so `12*` would display one task while
    `/aitask-pick 12*` launched on the literal string. Comment and tests say so.

- **Issues encountered:**
  - The characterization suite initially failed on `TmuxLaunchConfig` requiring
    `new_session`; fixed in the test.
  - The `.narrow`-removal negative control first raised a Textual `TokenError`
    (dropping only the lines containing `narrow` orphans the declaration
    bodies) — which would have satisfied `assertRaises` without proving
    anything. Replaced with a block-aware `_drop_narrow_rules` helper, and the
    control now fails on a real overflow (`Cancel` right edge 39 > 38).
  - Screen-text assertions had to become wrap- and chrome-tolerant: at 40
    columns a phrase wraps and the dialog border lands mid-phrase.
  - The "n and p share one implementation" test was first written as an
    `inspect.getsource` string scan. It passed standalone but failed inside the
    aggregate run, because `getsource` uses the line numbers recorded at import
    time and the file had been edited since — it silently asserted against the
    wrong slice. Replaced with a behavioural check: drive both keys at the same
    target and compare the resulting `AgentCommandScreen` construction, plus a
    second test pinning what that construction is so two identically-wrong
    paths cannot satisfy the equality. Verified sensitive (different target ids
    compare unequal).

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_core.py:2806-2812` — `_resolve`'s title
    extraction takes the first line starting with `# ` **without skipping
    fenced code blocks**, so a Python comment inside a ``` fence becomes the
    task title. Observed live: t1310 renders as `t1310: on confirm:` because
    its description contains `# on confirm:` inside a code fence. Affects every
    consumer of `TaskInfo.title` (monitor and minimonitor `i`/`I`, the new
    confirm dialog), not just this task.
  - `.aitask-scripts/monitor/monitor_shared.py:227` — `TaskDetailDialog.action_toggle_plan`
    writes its view indicator as `… [/] [{label}]`, unescaped, so Rich parses
    `[Plan]` / `[Task]` as a markup tag and it never reaches the screen.
    Pressing `p` in the task-detail dialog silently gives no visual confirmation
    of which view is showing. Pre-existing; `_showing_plan` does flip.
  - Risk-mitigation "before" task creation can emit a task file with **no
    number** in its name: `aitasks/t_refresh_codeagent_suite_default_model_expectations.md`
    was committed at 10:15 today by a concurrent session
    (`9e7f18326 ait: Revert t1311 to Ready (risk mitigation pending)`). The
    board lists it but nothing can address it by id, and it breaks
    `test_board_work_report.test_hidden_cards_still_listed` (the board counts
    it, the work-report screen's `t(\d+(?:_\d+)?)` extraction drops it).
    Belongs to another session's in-flight t1311 work, so left untouched here.

- **Key decisions:**
  - `TaskPickConfirmDialog` subclasses `TaskDetailDialog` rather than adding
    flags to it, so "`i`/`I` unchanged" holds by construction — both existing
    call sites are untouched, and the base keeps one dismissal type.
    `_detail_widgets()` is the shared seam, which lets `action_toggle_plan` be
    inherited verbatim.
  - `blocking_dependencies` takes a resolved `TaskInfo` and refreshes each
    dependency itself (`refresh=True`), because `TaskInfoCache` is
    process-lifetime in the minimonitor. `refresh=False` exists solely as the
    negative control for the staleness test.
  - The **followed agent's** status is refreshed on the same grounds before it
    is shown in the kill-checkbox label. It is not a dependency, but it is what
    the user reads before arming the kill, and a stale `Done` would actively
    encourage closing down an agent that is still working. Not in the original
    plan; added for consistency with the dependency-freshness rule.
  - The already-running scan is session-scoped; one tmux session maps to one
    project root, so session scope is project scope.
  - `p` still permits launching a non-`Ready` or blocked task — the user asked
    to pick *by number* — but relabels OK to `Launch anyway` so it is never
    silent.

- **Build verification / test suite:** `bash tests/run_all_python_tests.sh` —
  2622 tests, **one failure, pre-existing and unrelated to this task**:
  `test_board_work_report.WorkReportFullColumnUnderSearchTests.test_hidden_cards_still_listed`
  (`AssertionError: 131 != 132`). Proven independent by re-running it with all
  three t1310 source files stashed out — it fails identically. Root cause: a
  stray **un-numbered** task file,
  `aitasks/t_refresh_codeagent_suite_default_model_expectations.md`, committed
  by a concurrent session at 10:15 (`9e7f18326 ait: Revert t1311 to Ready (risk
  mitigation pending)`). `TaskManager.get_column_tasks` counts it, while the
  work-report screen's `t(\d+(?:_\d+)?)` id extraction drops it, so the two
  counts differ by exactly one. No `verify_build` is configured for this
  project, so this is reported rather than gate-enforced. Every suite that
  imports the changed modules was additionally re-run directly against the
  final code and passes.

- **Live verification (tmux, isolated socket `-L t1310check`):** confirmed in a
  real 40-column pane that the `p:pick task` hint renders, the number dialog
  accepts input, and the confirm dialog shows the task detail, the
  `⚠ t1310 is Implementing — not Ready to pick` warning and the `Launch anyway`
  button, all within the pane. The kill-checkbox branch could **not** be
  exercised live: `ait minimonitor` talks to the default tmux server, so it
  never saw the isolated test session's agent and reported no followed agent.
  That branch is covered by unit tests only.
