---
Task: t983_8_session_tab_split.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_10_manual_verification_brainstorm_ia.md, aitasks/t983/t983_11_wizard_rehost_actions_screen.md, aitasks/t983/t983_9_running_strip_deconflict_docs.md
Archived Sibling Plans: aiplans/archived/p983/p983_1_node_detail_panel_widget.md, aiplans/archived/p983/p983_2_node_selection_model.md, aiplans/archived/p983/p983_3_browse_tab_contentswitcher.md, aiplans/archived/p983/p983_4_operations_dialog_cardinality.md, aiplans/archived/p983/p983_5_node_hub_overlay.md, aiplans/archived/p983/p983_6_wizard_rehost_drop_node_select.md, aiplans/archived/p983/p983_7_compare_overlay_drop_tab.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-17 11:13
---

# p983_8 — Session tab split (verify-mode refresh)

## Context

Child of **t983** (brainstorm IA overhaul: collapse 5 peer tabs → Browse/Session/Running with contextual node ops). Today the five **session-lifecycle** ops (pause · resume · finalize · archive · delete) live inside the multi-step **Actions** wizard's first step (`op_select`). They are *not* node-contextual, so per the target IA they get their own dedicated **Session** tab. This is the structural "move ops out of the wizard" half; the wizard re-host itself is t983_11 and the Status→Running rename + header strip is t983_9.

**Verify-mode note:** this plan was re-checked against the current source (`brainstorm_app.py`, ~8,300 lines). The original child task body cited `_execute_session_op` at `:7415`; it is now **`:7808`**. All line numbers below are current as of this verification. The one substantive gap the original plan glossed over — the `s` keybinding currently belongs to the Status tab — is resolved below (user-confirmed).

## Decision: keybinding (`s` for Session)

`s` is currently `Binding("s", "tab_status", "Status")` (`:3844`). The Status→Running rename + final `b`/`s`/`r` deconflict is explicitly sibling **t983_9** (`depends: [t983_8]`). **User-confirmed approach:** t983_8 **claims `s` for the Session tab now** and **provisionally moves the Status tab to the free `r` key** (`r` was freed when t983_7 removed `compare_regenerate`). The Status tab keeps its id (`tab_status`), action (`action_tab_status`), and content untouched, but its TabPane label drops the `(S)` mnemonic → plain `"Status"`. t983_9 later renames it `tab_running` / `"(R)unning"` keeping `r`.

## Key files

- `.aitask-scripts/brainstorm/brainstorm_app.py` — all code changes.
- `tests/test_brainstorm_session_tab.py` — **NEW** pilot/unit test.

## Current state (verified)

- **Tabs** (`compose`, `:4013`): `tab_browse` (:4019), `tab_actions` (:4048), `tab_status` (:4050). No `tab_session`.
- **Op lists** (module-level): `_DESIGN_OPS` (`:220`), `_SESSION_OPS` (`:229`) = the 5 ops as `(op_key, label, desc)`. `_OP_LABELS` (`:240`) derives from both.
- **Op list render** `_actions_show_step1` (`:6519`): mounts Design rows from `_DESIGN_OPS` (`:6546`) then a **"Session Lifecycle"** section from `_SESSION_OPS` (`:6549-6553`), each `OperationRow(...)` disabled via `_is_session_op_disabled(op_key, status, head)` (`:6598`).
- **op_select dispatch (2 sites)** — both branch identically: `delete`→`DeleteSessionModal`/`_on_delete_result`; `pause|resume|finalize|archive`→`_wizard_config={"confirmed":True}`+`_actions_show_confirm()`; else→`_actions_show_step2()`:
  - keyboard Enter `on_key` (`:4143-4160`)
  - mouse click `on_operation_row_activated` (`:7771-7789`)
- **Confirm step** `_actions_show_confirm` (`:7583`): for session ops shows a summary (`_build_summary`, session lines `:7690-7698`) + a "Confirm" button; `_on_actions_launch` (`:7718`) routes `pause|resume|finalize|archive`→`_execute_session_op()` else `_execute_design_op()`.
- **`_execute_session_op`** (`:7808`): reads `self._wizard_op`; runs save/finalize/archive helpers; ends with `self._load_existing_session()` (`:5151`). `delete` is NOT here — it runs via `DeleteSessionModal`→`_on_delete_result` (`:8026`)→`_run_delete_session` subprocess (`:8033`).
- **Bindings** (`:3830-3856`): `a`→`action_tab_actions` (`:4869`), `s`→`action_tab_status` (`:4874`). `_TAB_SCOPED_ACTIONS` (`:3860`) only scopes `open_node_detail`→`tab_browse`. Row nav uses `_navigate_rows(direction, container_id, (OperationRow,))`.
- **Status tab layout reference** `_refresh_status_tab` (`:5908`): `VerticalScroll(id="status_content")` + section-title `Label`s + row widgets.

## Implementation

### 1. Add the Session tab (`compose`, after `tab_actions`, ~`:4049`)
```python
with TabPane("(S)ession", id="tab_session"):
    yield VerticalScroll(id="session_content")
```
Relabel the Status pane (`:4050`): `TabPane("Status", id="tab_status")` (drop the `(S)` mnemonic — `s` now belongs to Session; t983_9 will make it `(R)unning`).

### 2. Bindings (`:3843-3844`)
- Add `Binding("s", "tab_session", "Session", show=False)`.
- Change `Binding("s", "tab_status", "Status", show=False)` → `Binding("r", "tab_status", "Status", show=False)` (provisional; t983_9 finalizes to `tab_running`).
- Add action (beside `action_tab_status`, `:4874`):
```python
def action_tab_session(self) -> None:
    if isinstance(self.screen, ModalScreen):
        return
    self.query_one(TabbedContent).active = "tab_session"
    self._refresh_session_tab()
```

### 3. Render the Session-op list — new `_refresh_session_tab()` (near `_actions_show_step1`)
Mirror the status-tab/op-row pattern; reuse `_SESSION_OPS` + `_is_session_op_disabled`:
```python
def _refresh_session_tab(self) -> None:
    """Render the Session-lifecycle op list (pause/resume/finalize/archive/delete)."""
    container = self.query_one("#session_content", VerticalScroll)
    container.remove_children()
    if self.read_only:
        container.mount(Label("[italic]Session is read-only. No operations available.[/]"))
        return
    container.mount(Label("Session Lifecycle  (↑↓ Navigate  Enter Select)",
                          classes="actions_step_indicator"))
    status = self.session_data.get("status", "")
    head = get_head(self.session_path)
    for op_key, label, desc in _SESSION_OPS:
        disabled = self._is_session_op_disabled(op_key, status, head)
        container.mount(OperationRow(op_key, label, desc, disabled=disabled))
    self.call_after_refresh(self._focus_first_session_op)
```
Add `_focus_first_session_op` (clone of `_focus_first_operation` `:6561`, scoped to `tab_session`/`#session_content`). Also call `_refresh_session_tab()` from `_load_existing_session` (`:5151`, beside the existing `_actions_show_step1()` re-render at `:5171`) so the list re-derives disabled-state after every reload, and from `on_mount`/initial-load alongside the first `_actions_show_step1`.

### 4. Dispatch — new `_dispatch_session_op(op_key)` and Session-tab nav
```python
def _dispatch_session_op(self, op_key: str) -> None:
    if op_key == "delete":
        self.push_screen(DeleteSessionModal(self.task_num), self._on_delete_result)
        return
    self._session_confirm_op = op_key           # consequential ops get an inline confirm
    self._show_session_confirm(op_key)
```
- **Confirm UX (faithful port):** non-delete ops currently get a lightweight confirm (summary + Confirm/Back). Port that into the session tab: `_show_session_confirm(op_key)` replaces `#session_content` with a one-line summary (reuse the `_build_summary` session-op lines / `_OPERATION_HELP[op_key]["summary"]`) + `Confirm`/`Cancel` buttons. `Confirm` → `self._execute_session_op(op_key)` → `_refresh_session_tab()`; `Cancel` → `_refresh_session_tab()`. (Keeps the existing safety gate for finalize/archive.)
- **Navigation** in `on_key` (add a `tab_session` branch mirroring the `tab_actions` op_select nav): `up`/`down` → `_navigate_rows(dir, "session_content", (OperationRow,))`; `enter` on a non-disabled `OperationRow` → `_dispatch_session_op(row.op_key)`. Add a mouse path in `on_operation_row_activated` (`:7771`): when `tabbed.active == "tab_session"`, call `_dispatch_session_op(row.op_key)`.

### 5. Refactor `_execute_session_op` to take an explicit op (`:7808`)
The wizard caller is going away, so stop reading `self._wizard_op`:
```python
def _execute_session_op(self, op: str | None = None) -> None:
    op = op or self._wizard_op   # back-compat default; session tab passes explicitly
    ...
    self._load_existing_session()
```
(`_load_existing_session` already re-renders both tabs per step 3.)

### 6. Remove session ops from the wizard (the "split")
- `_actions_show_step1` (`:6549-6553`): delete the **"Session Lifecycle"** section + the `_SESSION_OPS` loop. The wizard op list becomes design-ops-only.
- **op_select dispatch:** in `on_key` (`:4143-4160`) and `on_operation_row_activated` (`:7777-7789`) drop the `delete` and `pause|resume|finalize|archive` branches; op_select now only ever advances design ops (`_actions_show_step2()`).
- **Dead wizard confirm code (now unreachable for session ops):** remove the `is_session_op` branches in `_actions_show_confirm` (`:7597-7598`, `:7617` button label), the session-op lines in `_build_summary` (`:7690-7698`, `:7704`), and the session branch in `_on_actions_launch` (`:7721-7722`) — the wizard confirm/launch path is now design-ops-only.
- **Delete result paths:** `_on_delete_result` (`:8026`) and `_run_delete_session` failure path (`:8049`) currently fall back to `_actions_show_step1()`. Repoint them to `_refresh_session_tab()` (delete now originates from the Session tab).

### 7. Bidirectional coordination note → t983_9 (post-approval, Step 7+)
Per the bidirectional-coordination convention, add a short note to `aitasks/t983/t983_9_running_strip_deconflict_docs.md` recording that t983_8 already: bound `s`→Session, moved Status to `r` (plain "Status" label), so t983_9's "final b/s/r deconflict" only needs the `tab_status`→`tab_running` rename + `(R)unning` relabel (key already `r`) and the scoped-action re-scope. Commit via `./ait git`.

## Verification

- **Pilot/unit — `tests/test_brainstorm_session_tab.py` (NEW):** brainstorm tests use `unittest` + stub/`__new__` hosts (no Textual `run_test()` pilot). Assert: (a) `_refresh_session_tab` mounts one `OperationRow` per `_SESSION_OPS` with the right `disabled` per `_is_session_op_disabled` across statuses (init/active/paused/completed); (b) `_dispatch_session_op("delete")` pushes `DeleteSessionModal`; (c) `_dispatch_session_op("pause")` routes through the confirm → `_execute_session_op("pause")` (spy) → no longer reads `_wizard_op`; (d) the wizard `_actions_show_step1` no longer mounts any session OperationRow (regression guard for the split).
- **Suite:** `bash tests/run_all_python_tests.sh` — all `tests/test_brainstorm*.py` green (esp. existing wizard/session tests; confirm no wizard step-model regression).
- **Manual:** `ait brainstorm <session>` → press `s` → Session tab lists the 5 ops with correct enabled/disabled per status; pause/resume/finalize/archive show a confirm then apply (status refreshes); delete shows `DeleteSessionModal` (double-confirm) and exits on success; `r` now opens the (still-labeled "Status") tab; the Actions wizard's op list no longer shows session ops.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_8`.

## Risk

### Code-health risk: medium
- Touches load-bearing wizard op_select dispatch in 3 sites + removes now-dead wizard confirm branches; a missed edge (e.g. a lingering session-op reference in the wizard path) could break design-op flow. · severity: medium · → mitigation: regression guard (d) + full `test_brainstorm*` suite.
- Provisional `s`→Session / Status→`r` key move is a small but cross-cutting binding change that t983_9 must finalize; an unaware editor could double-bind or mislabel. · severity: low · → mitigation: explicit reverse-coordination note added to t983_9 (step 7) + plain "Status" label avoids a misleading mnemonic.

### Goal-achievement risk: low
- Approach reuses proven primitives (`OperationRow`, `_is_session_op_disabled`, `_execute_session_op`, `DeleteSessionModal`, `_navigate_rows`) and every touch point is verified against current source; requirements fully covered. · severity: low · → mitigation: n/a.
