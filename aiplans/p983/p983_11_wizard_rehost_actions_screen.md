---
Task: t983_11_wizard_rehost_actions_screen.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_10_manual_verification_brainstorm_ia.md
Archived Sibling Plans: aiplans/archived/p983/p983_5_node_hub_overlay.md, aiplans/archived/p983/p983_6_wizard_rehost_drop_node_select.md, aiplans/archived/p983/p983_8_session_tab_split.md, aiplans/archived/p983/p983_9_running_strip_deconflict_docs.md
Base branch: main
---

# p983_11 — Physically re-host the Actions wizard into a dedicated `ModalScreen`

## Context

Parent **t983** collapses the brainstorm TUI from 5 peer tabs to 3
(BROWSE / SESSION / RUNNING) and moves every node operation into **contextual
dialogs** launched from the Browse selection. Sibling **t983_6** delivered the
*seeding* half (the wizard is pre-seeded from the contextual selection and its
`node_select` step is skipped), but deliberately left the wizard physically
hosted inside the `(A)ctions` `TabPane` because verify-mode analysis showed the
re-host is far larger than the original plan assumed. Siblings **t983_8**
(Session tab) and **t983_9** (Running rename + runtime strip) have since landed,
so the current tab set is BROWSE · **ACTIONS** · SESSION · RUNNING — the Actions
tab is the **last vestige** of the old IA.

This task removes the Actions tab and re-hosts the wizard as a dedicated
`ActionsWizardScreen(ModalScreen)`, pushed contextually from `A` (Operations
dialog) / `Enter` (Node Hub), dismissed on launch or `Esc`. **Architecture
decision (user-confirmed):** the *clean Screen-owned* end-state — the wizard's
rendering methods, `@on` handlers, key-nav, and per-flow state move **onto** the
screen, even where tests need updating. App-level compatibility shims are kept
**only where genuinely needed** during migration (the disk-readers and op
executor stay on the App and are called via `self.app`). This is the idiomatic
Textual pattern — the file already has **15 `ModalScreen` subclasses**
(`NodeDetailModal`, `NodeActionSelectModal`, `ModulePreviewScreen`, …) using the
same `push_screen(…, callback)` + `dismiss(result)` contract — and it lets us
delete the `tab_actions` special-casing rather than retarget it.

All code is in `.aitask-scripts/brainstorm/brainstorm_app.py` (+ tests).

## Why a Screen, not an in-screen overlay

`App.on_key` already early-returns under any `ModalScreen` (`:4203`), and `@on`
message handlers on the `BrainstormApp` do **not** fire for widgets inside a
pushed screen. A `ModalScreen` therefore gives focus-trap, `Esc`, key routing,
and background-blocking for free — exactly the machinery an in-screen overlay
would have to hand-roll. The cost is that the wizard's key handling and `@on`
handlers must live **on the screen**, which is precisely what the Screen-owned
approach does anyway.

## Target shape

```
BrainstormApp (default screen)
  ├─ action_node_action / Node Hub  → push_screen(ActionsWizardScreen(seed), cb)
  ├─ _on_node_action_result(node, op): build seed dict, push the screen
  ├─ _on_wizard_result(result):  result is None → cancelled;
  │                              else self._execute_design_op(result)   ← stays on App
  └─ keeps: _node_sections/_node_has_sections/_node_module (disk, tested via __new__),
            _execute_design_op + _run_operation worker, _selection, session data

ActionsWizardScreen(ModalScreen)
  ├─ __init__(app-facing seed: op, node_id, marked, subgraph, fast_track, pre_seeded)
  ├─ owns wizard state: _wizard_step/_total/_step_id/_op/_config/_has_sections/
  │                     _subgraph_count/_subgraph/_fast_track/_cmp_section_checks
  ├─ compose(): yield VerticalScroll(id="actions_content")   (id kept → CSS reused)
  ├─ on_mount(): render the seeded starting step
  ├─ on_key():  the relocated 4277-4358 nav block (tab_actions guard dropped)
  ├─ @on(Button.Pressed, ".btn_actions_launch/back/next"), @on(Checkbox.Changed,".chk_node")
  ├─ on_descendant_focus(): node_select feedback (relocated 6716)
  └─ all _actions_show_*/_config_*/_refresh_compare_*/_navigate_rows/_cycle_*/
            _focus_*/_mount_*/_build_summary/_preseed_multi_node_checklist
```

## Implementation

### 1. Create `ActionsWizardScreen(ModalScreen)`
- New class near the other `ModalScreen`s (e.g. after `NodeActionSelectModal`,
  ~`:2979`). `BINDINGS = [Binding("escape", "close", …), Binding("H","op_help",…)]`.
- `__init__(self, app, *, op_key, node_id, marked, subgraph, fast_track, pre_seeded)`
  — store the seed; initialise the `_wizard_*` attributes here (moved verbatim
  from `BrainstormApp.__init__` `:4005-4024`).
- `compose()` → `with Container(id="actions_wizard_dialog"): yield VerticalScroll(id="actions_content"); yield Footer()`.
  **Keep the `#actions_content` id** so existing CSS rules and the ~23 internal
  queries port unchanged (they become `self.query_one("#actions_content", …)`
  resolved against the screen's own DOM).
- `on_mount()` → reproduce the per-op routing currently in `_on_node_action_result`
  (`:4857-4959`): seed `_wizard_config`, then call the right first renderer
  (`_actions_show_config` / `_actions_advance_from_node_select` / `_actions_show_step1`
  for the no-seed path) + the compare/synthesize `_preseed_multi_node_checklist`
  `call_after_refresh`.

### 2. Move the wizard methods onto the screen
Relocate (cut from `BrainstormApp`, paste into the screen, `self` semantics
unchanged) the cohesive unit identified in exploration:
- Renderers: `_actions_show_step1/_step2/_subgraph_select/_node_select/_section_select/_config/_confirm`, `_render_wizard_step`, `_enter_wizard_step`, `_set_total_steps`, `_wizard_ctx`.
- Config builders: `_config_explore_no_node/_compare/_synthesize/_module_decompose/_module_merge/_module_sync`, `_refresh_compare_sections/_dimensions`, `_actions_collect_config`, `_collect_target_sections`, `_actions_advance_from_node_select`, `_build_summary`, `_mount_op_context_header/_mount_recent_ops`, `_preseed_multi_node_checklist`.
- Nav/focus: `_navigate_rows`, `_cycle_confirm_focus`, `_cycle_wizard_groups`, `_cycle_preview_focus`, `_focus_first_operation`, `_focus_operation_row`, `_focus_confirm_start`, `_focus_fcl_filter`.
- `@on` handlers: `_on_cmp_node_changed`, `_on_actions_launch`, `_on_actions_back`, `_on_actions_next`, `on_operation_row_activated` (`:8113-8148, :8172`).
- The node_select-feedback branch of `on_descendant_focus` (`:6716-6725`) becomes the screen's own `on_descendant_focus`.

**Calls into App-retained infra** become `self.app.…`: `_node_has_sections`,
`_node_sections`, `_node_module`, `self.app._selection`, `self.app.session_path`.
The disk-readers `_node_sections`/`_node_has_sections`/`_node_module` **stay on
the App** (tested directly via `BrainstormApp.__new__` in
`test_brainstorm_wizard_sections.py`).

### 3. Launch = dismiss-with-result; op execution stays on the App
- `_on_actions_launch` (screen) → build a result object/dict carrying everything
  `_execute_design_op` reads from `_wizard_*` today (op, config, subgraph,
  fast_track, target node(s), sections), then `self.dismiss(result)`.
- Refactor `BrainstormApp._execute_design_op` to take that result (instead of
  reading `self._wizard_*`) and keep spawning `_run_operation` in a worker.
- `_on_node_action_result` callback chain: the `push_screen(ActionsWizardScreen(...),
  self._on_wizard_result)` callback runs `_execute_design_op(result)` when result
  is non-None.
- **Delete the two `call_from_thread(self._actions_show_step1)` resets**
  (`:8403, :8409`): the modal is already dismissed at launch, so there is no
  in-tab wizard to reset — the worker just notifies. (This resolves the
  "background-thread refresh needs guarding" finding by removing the calls.)

### 4. Remove the Actions tab and its App-side glue
- compose: delete the `tab_actions` `TabPane` + `yield VerticalScroll(id="actions_content")` (`:4184-4185`).
- Delete `_enter_actions_tab` (`:5060`) and `action_tab_actions` (`:5079`); remove the `Binding("a","tab_actions",…)` (`:3970`). `A → action_node_action` already opens the Operations dialog → wizard, so the entry point is preserved.
- `on_key` (App): drop the Actions-only branches — the Tab/Shift+Tab preview block (`:4210`) and the `"tab_actions": ("actions_content", …)` map entry (`:4239`) — and the whole wizard nav block (`:4277-4358`) moves to the screen.
- `action_op_help` (`:5095-5114`): the wizard branch moves to the screen's `action_op_help`; keep an App version only if a non-wizard caller remains (verify during impl — likely fully moves).
- Sweep the remaining `tab_actions` guards (`can_perform_action` `:4086/:4104`, `_focus_first_operation` `:6854`, `_focus_operation_row` `:6998`, `on_operation_row_activated` `:8181`): these move with their methods to the screen, where the guard is unnecessary (the screen's existence *is* the guard) — delete the `tabbed.active == "tab_actions"` conditions there.
- Delete the session-load pre-render `self._actions_show_step1()` (`:5387` in `_load_existing_session`) — the wizard is on-demand now, not pre-populated.

### 5. Tests (update per the chosen approach)
- **Unaffected (pure/`__new__`):** `test_brainstorm_wizard_steps.py` (module-level resolver), `test_brainstorm_wizard_filter.py`, `test_brainstorm_wizard_subgraph.py`, and the disk-reader cases in `test_brainstorm_wizard_sections.py` (still call `app._node_sections` on an App built via `__new__`).
- **Update — `test_brainstorm_node_action_modal.py`:** its `OnNodeActionResultTests` assert seeding into `app._wizard_config`. Rewrite to assert `_on_node_action_result` constructs/pushes `ActionsWizardScreen` with the expected **seed** (op, `_selected_node`, `pre_seeded_node`, marked set), e.g. by spying `app.push_screen` and inspecting the screen instance's seed/initial `_wizard_config`. The `PreseedChecklistPilotTests` pilot moves to drive the pushed screen.
- **Add — a small `ActionsWizardScreen` pilot** (extend `test_brainstorm_wizard_sections.py` or a new `test_brainstorm_wizard_screen.py`): push the screen via a Pilot for each op (explore / compare / synthesize / module_decompose / fast_track), assert it renders the seeded starting step (no `node_select` for seeded ops), `Esc`/Back navigates, and Launch dismisses with a result whose fields match the collected config.
- Run the whole brainstorm suite: `bash tests/run_all_python_tests.sh` filtered to `tests/test_brainstorm*.py`.

### 6. Migration ordering (single commit, but staged to keep the suite green)
1. Add `ActionsWizardScreen` skeleton + move state/methods (file still compiles; App keeps thin pass-through only if a mid-move caller needs it).
2. Rewire `_on_node_action_result` → push; refactor `_execute_design_op(result)`.
3. Remove the tab, bindings, App-side guards, and the two bg resets.
4. Update/add tests; iterate to green.

## Reference patterns (mirror these)
- `NodeActionSelectModal` (`:2814`) — `__init__` receives computed state (testable, session-free), custom `on_key` nav, `dismiss(op_key|None)`, nested `push_screen(OperationHelpModal)` for `H`.
- `NodeDetailModal` (`:1162`) — `compose` shell + `on_mount` data load + `action_close → dismiss(None)`.
- `ModulePreviewScreen` (`:2981`) — `dismiss({...})` rich-dict result (model for the launch result object).
- Push idiom: `self.push_screen(Modal(...), lambda result, …: self._cb(...))` (`:4813`).

## Verification
- `bash tests/run_all_python_tests.sh` (filter `tests/test_brainstorm*.py`) green; `shellcheck` n/a (Python).
- Manual (covered by the aggregate MV sibling **t983_10**): `ait brainstorm <session>` → Browse → focus a node → `A` → run **every** op (explore / compare / synthesize / module_decompose|merge|sync / fast_track / delete) to completion; wizard host opens seeded, runs, dismisses cleanly; `Esc`/Back nav works; launching an op returns to Browse and the op runs in the background **without** crashing now that the host is closed; `Enter` → Node Hub → Operations routes the same way; confirm there is no longer an Actions tab and `a` no longer switches to it.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_11` (child archival; parent
t983 auto-archives once `children_to_implement` is empty — t983_10 is the only
other remaining child).

## Risk

### Code-health risk: medium
- **Wide mechanical blast radius in one file:** ~30 methods, ~23 internal query
  sites, ~11 `tab_actions` guards, the `on_key` nav block, and 5 `@on` handlers
  relocate from `BrainstormApp` to `ActionsWizardScreen`. A missed handler or a
  wrong `self.app.` delegation silently breaks one op's flow. · severity: medium
  · → mitigation: staged migration (§6) keeping the suite green at each stage +
  the new per-op screen pilot (§5) + t983_10 manual verification.
- **Launch result wiring:** `_execute_design_op` must read every field it
  currently pulls from `self._wizard_*` off the dismiss-result instead; an
  omitted field corrupts an op launch. · severity: medium · → mitigation:
  enumerate the `_wizard_*` reads in `_execute_design_op`/`_run_operation` before
  cutting; assert result fields in the screen pilot.
- **Net:** this *removes* the `tab_actions` special-casing and conforms to the
  15 existing `ModalScreen` precedents, so the end-state is cleaner than today.

### Goal-achievement risk: medium
- **Live-behavior correctness (focus/key/background-op):** focus-trap, `Esc`,
  and "op completes while the modal is closed" are runtime behaviors that unit
  tests cover only partially. · severity: medium · → mitigation: this is exactly
  the surface **t983_10** (aggregate manual-verification sibling) was created to
  cover — no new before/after mitigation task needed; t983_10 is the backstop.
- **Requirement coverage:** the approach matches the parent target design
  (contextual modal, no Actions tab) and the t983_6 seeding contract is already
  in place; no requirement appears unaddressed. · severity: low.
