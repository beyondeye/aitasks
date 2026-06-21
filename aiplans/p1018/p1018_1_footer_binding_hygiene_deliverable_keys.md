---
Task: t1018_1_footer_binding_hygiene_deliverable_keys.md
Parent Task: aitasks/t1018_brainstorm_op_restart_dblclick_footer_hygiene.md
Sibling Tasks: aitasks/t1018/t1018_*.md
Archived Sibling Plans: aiplans/archived/p1018/p1018_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# p1018_1 — Per-screen footer binding hygiene + deliverable-key migration

Foundation child of t1018. Make `ait brainstorm` contextual shortcuts genuinely
scoped to the screen/tab that owns them, fix the genuinely-broken bindings, and
establish the deliverable-key approach that t1018_2 builds on.

## Verified current state (read before coding — confirm line numbers are still current)

`.aitask-scripts/brainstorm/brainstorm_app.py` (~7900+ lines):

- **App-level `BINDINGS`** at `:5516-5550` — `*TuiSwitcherMixin.SWITCHER_BINDINGS`,
  `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`, then 15 explicit bindings:
  `q`, `b`/`d`/`g` (tab/view, show=False), `v`, `space`, `c`, `s`, `r` (tabs/marks),
  `enter`/`A`/`f`, and the three retry-apply actions below.
- **`check_action()`** at `:5632-5670`. Gating today:
  - `:5637-5641` — when a non-`ModalScreen` is pushed, all App bindings hidden (`None`).
  - `:5644-5653` — `node_action`/`toggle_deferred` gated to `tab_browse` + a primary selection.
  - `:5656-5670` — `_TAB_SCOPED_ACTIONS` (`{"open_node_detail": "tab_browse"}`, dict at `:5555`).
  - `:5657-5658` — **default `return True`** → any other action shows/fires everywhere.
- **The three leaking retry-apply actions** (all default-`True`, ungated):
  - `ctrl+r` → `action_retry_initializer_apply` (`:5545`, **show=True** → visible leak),
    method `:6727-6729` (`_try_apply_initializer_if_needed(force=True)`).
  - `ctrl+shift+x` → `action_retry_explorer_apply` (`:5546`, show=False), method `:7237-7251`.
  - `ctrl+shift+y` → `action_retry_synthesizer_apply` (`:5548`, show=False), method `:7387-7398`.
- **Wizard preview chords** on `ActionsWizardScreen.BINDINGS` (`:3275`, chords `:3278-3279`):
  `ctrl+shift+b` → `cycle_preview_ratio`, `ctrl+shift+l` → `toggle_preview_numbered`.
  Already scoped-to-modal by t983_11 (comment `:5654-5655`) — but still undeliverable chords.
  The wizard hosts editable TextAreas (`ta_module_preview_steer`, module-op TextAreas
  `:4150,4272,...`) → a focused field consumes letter keys.
- Existing per-widget BINDINGS examples: `_PreviewMinimap` priority `tab`/`shift+tab`
  (`:953-957`), `NodeRow` `o` (`:2522-2524`).
- **Test** `tests/test_brainstorm_proposal_preview.py` calls action methods directly;
  only `pilot.press("tab")` at `:357`. No key-dispatch coverage for the preview actions —
  this is exactly why the undeliverable chords passed CI.

## Implementation steps

### Step 1 — Gate the three leaking retry-apply actions
Extend `check_action()` (`:5632-5670`) so each retry-apply action is only
active/shown in the surface where it is meaningful (not the global default):
- `retry_initializer_apply` — relevant during/after initializer ingest. Gate to
  the context where an initializer agent exists (e.g. session-init / Running tab).
  Confirm the exact condition by reading `_try_apply_initializer_if_needed`.
- `retry_explorer_apply` / `retry_synthesizer_apply` — relevant on the Running
  tab where the operation/agents live. Gate to `tab_running`.
- Implementation: add these action names to a gating branch returning `True` when
  the active tab/screen matches, else `None`. Use `self.screen.query_one(...)` not
  `self.query_one(...)` if a widget lookup is needed (priority/query-scope gotcha,
  tui_conventions.md). **Keep the `action_retry_*` / `_try_apply_*` methods
  intact** — t1018_2 re-homes the explorer/synthesizer ones onto the GroupRow.

### Step 2 — Replace the undeliverable wizard preview chords
On `ActionsWizardScreen.BINDINGS` (`:3278-3279`):
- Replace `ctrl+shift+b` → `cycle_preview_ratio` with `alt+w` (width) and
  `ctrl+shift+l` → `toggle_preview_numbered` with `alt+n` (numbered) — or other
  free `alt+<letter>` keys. `alt+<letter>` is ESC-prefixed / non-printable so a
  focused TextArea ignores it. **AVOID** bare `ctrl+b` (tmux prefix) and any
  `ctrl+shift+<letter>` chord.
- Remove the dead chord bindings. Update any footer label text.
- Confirm the chosen keys don't collide with the wizard's other bindings or the
  `_PreviewMinimap` priority `tab`/`shift+tab`.

### Step 3 — Per-screen scoping model (the foundation)
- Prefer moving contextual bindings onto the owning Screen/widget `BINDINGS`
  (bound/unbound with the surface) over global-declare + `check_action`-hide.
  Where a move is impractical, extend `check_action` so no action leaks.
- Document the resulting model in `## Notes for sibling tasks` so t1018_2 places
  its restart actions consistently (per-row `on_key` + render hint).

### Step 4 — Footer-coverage audit
Per tui_conventions.md "TUI footer must surface every operation": on each
tab/screen, confirm every operation is footer-visible OR deliberately hidden with
justification. Flip wrongly-hidden `show=False` bindings; gate leaking ones. Note
the Running-tab row actions stay as render-hints (not footer) by design.

### Step 5 — Shortcut manifest
brainstorm_app.py is already in `KNOWN_BINDING_SOURCES`, so in-file scope changes
are auto-swept. If a brand-new scope/dialog is introduced, register it
(`_shortcuts_scope` / `register_app_bindings`) and confirm
`tests/test_shortcut_scopes.py` stays green.

### Step 6 — Tests
- Extend `tests/test_brainstorm_proposal_preview.py` with **real `pilot.press(...)`**
  tests for the new `alt+<letter>` preview keys (assert the action fires) — the
  first key-dispatch coverage for these actions.
- Add a pilot test asserting a focused wizard TextArea receives the replacement
  key as a no-op for the preview action (does not toggle ratio/numbering).
- Add `check_action` assertions: each retry-apply action is hidden/inactive on
  irrelevant tabs/screens, active on its owning surface.

## Risk
### Code-health risk: medium
- `check_action` is load-bearing; an over-broad gate could hide a still-needed
  binding. · mitigation: per-action pilot assertions (in-task).
### Goal-achievement risk: low
- Headless pilot cannot prove the `alt+<letter>` keys survive the real
  ghostty→tmux→Textual stack. · mitigation: covered by t1018_4 live verification.

## Verification
- `python -m pytest tests/test_brainstorm_proposal_preview.py` green incl. new key-dispatch tests.
- Focused wizard TextArea: replacement keys are no-ops for the preview action (pilot).
- `check_action` assertions: retry-apply actions gated to their owning surface; no global footer leak.
- Full brainstorm suite green: `python -m pytest tests/test_brainstorm*.py`.
- Live-stack verification of the new `alt+<letter>` keys through real tmux — deferred to t1018_4.

## Notes for sibling tasks
- The per-screen binding model lands here; t1018_2 must place its restart actions
  as per-row `on_key` + render hints on the Running-tab GroupRow (NOT footer
  Bindings), consistent with the landed `w`/`R`/`x` pattern.
- This child **gates but does not delete** `action_retry_explorer_apply` /
  `action_retry_synthesizer_apply` and their methods — t1018_2 re-homes that
  logic onto the GroupRow and removes the dead `ctrl+shift+x`/`ctrl+shift+y`
  global bindings. Do not delete those two action methods here.

## Step 9 — Post-implementation
Archive via `./.aitask-scripts/aitask_archive.sh 1018_1`. Parent t1018 stays
active (siblings t1018_2/t1018_3 + the t1018_4 verification sibling remain).
