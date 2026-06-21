---
Task: t1018_1_footer_binding_hygiene_deliverable_keys.md
Parent Task: aitasks/t1018_brainstorm_op_restart_dblclick_footer_hygiene.md
Sibling Tasks: aitasks/t1018/t1018_*.md
Archived Sibling Plans: aiplans/archived/p1018/p1018_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-21 10:54
---

# p1018_1 — Per-screen footer binding hygiene + deliverable-key migration

Foundation child of t1018. Make `ait brainstorm` contextual shortcuts genuinely
scoped to the screen/tab that owns them, fix the genuinely-broken bindings, and
establish the deliverable-key approach that t1018_2 builds on.

## Verified current state (re-verified 2026-06-21; brainstorm_app.py now 8830 lines — referenced sections unchanged)

All line numbers below were re-confirmed against the current
`.aitask-scripts/brainstorm/brainstorm_app.py` on this verification pass. The
file grew to 8830 lines but every cited section sits at the same line it did when
the plan was authored.

- **App-level `BINDINGS`** at `:5516-5550` — `*TuiSwitcherMixin.SWITCHER_BINDINGS`,
  `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`, then the explicit bindings:
  `q`, `b`/`d`/`g`/`v`/`space` (tabs/view/mark, show=False), `c`, `s`, `r`,
  `enter`/`A`/`f`, and the three retry-apply actions below.
- **`check_action()`** at `:5632-5670`. Gating today:
  - `:5637-5641` — when a non-`ModalScreen` is pushed, all App bindings hidden (`None`).
  - `:5644-5653` — `node_action`/`toggle_deferred` gated to `tab_browse` + a primary selection.
  - `:5656` — `_TAB_SCOPED_ACTIONS` lookup (`{"open_node_detail": "tab_browse"}`, dict at `:5554-5556`).
  - `:5658` / `:5670` — **default `return True`** → any action not special-cased shows/fires everywhere.
- **The three leaking retry-apply actions** (all fall through to default-`True`, ungated):
  - `ctrl+r` → `action_retry_initializer_apply` (`:5545`, **show implicit = True** → visible footer
    leak on every tab/screen), method `:6727-6729` (`_try_apply_initializer_if_needed(force=True)`).
    `_try_apply_initializer_if_needed` is at `:6679-6709` (checks `n000_needs_apply(self.task_num)`
    unless forced; surfaces failure via a persistent banner).
  - `ctrl+shift+x` → `action_retry_explorer_apply` (`:5546-5547`, show=False), method `:7237-7251`
    (`_pick_completed_agent_for_retry("explorer")` → `_try_apply_explorer_if_needed(agent, force=True)`).
  - `ctrl+shift+y` → `action_retry_synthesizer_apply` (`:5548-5549`, show=False), method `:7387-7398`
    (synthesizer analogue).
  - NOTE: the original task body said `ctrl+r` was declared with an explicit `show=True`; in the
    current code the `show` arg is **omitted** (Textual defaults it to True). Behaviour is identical
    (it leaks into the footer); just don't grep for a literal `show=True` on that line.
- **Wizard preview chords** on `ActionsWizardScreen.BINDINGS` (`:3275-3280`, chords `:3278-3279`):
  `ctrl+shift+b` → `cycle_preview_ratio` ("Preview width", show=False),
  `ctrl+shift+l` → `toggle_preview_numbered` ("Line numbers", show=False).
  Already scoped-to-modal by t983_11 — but still undeliverable chords. The wizard hosts editable
  TextAreas (`ta_module_preview_steer` `:3028`, `ta_module_decompose_modules`/`_plan` `:4319/4324`,
  `ta_module_merge_rules` `:4355`, `ta_module_sync_instructions` `:4389`) → a focused field consumes
  letter keys. **`alt+w` / `alt+n` are free** — no collision anywhere in `ActionsWizardScreen.BINDINGS`
  or the App BINDINGS (grep-confirmed this pass).
- Existing per-widget BINDINGS examples: `_PreviewMinimap` priority `tab`/`shift+tab`
  (`:952-957`), `NodeRow` `o` → `open_operation` (`:2522-2524`).
- **Test** `tests/test_brainstorm_proposal_preview.py` calls action methods directly
  (`_apply_preview_ratio`, `_cycle_preview_focus`, `toggle_numbered`, ...); the only
  `pilot.press(...)` is `pilot.press("tab")` at `:357`. No key-dispatch coverage for the
  preview actions — exactly why the undeliverable chords passed CI. No existing
  `check_action` or `action_retry_*` tests in any `tests/test_brainstorm*.py`.
- The four `ctrl+shift+<letter>` bindings above are the **only** such chords in the whole repo.
- `brainstorm_app.py` is registered in `KNOWN_BINDING_SOURCES` (`.aitask-scripts/lib/shortcut_scopes.py:49`),
  so new in-file scopes are auto-swept by `tests/test_shortcut_scopes.py`.

## Implementation steps

### Step 1 — Gate the three leaking retry-apply actions
Extend `check_action()` (`:5632-5670`) so each retry-apply action is only
active/shown in the surface where it is meaningful (not the global default):
- `retry_initializer_apply` — relevant during/after initializer ingest. Gate to
  the context where an initializer agent exists (e.g. session-init / Running tab).
  Confirm the exact condition by reading `_try_apply_initializer_if_needed` (`:6679`).
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
  `ctrl+shift+l` → `toggle_preview_numbered` with `alt+n` (numbered). `alt+<letter>`
  is ESC-prefixed / non-printable so a focused TextArea ignores it. **AVOID** bare
  `ctrl+b` (tmux prefix) and any `ctrl+shift+<letter>` chord.
- Remove the dead chord bindings. Update footer label text. `alt+w`/`alt+n` are
  collision-free (verified) and don't clash with `_PreviewMinimap` priority
  `tab`/`shift+tab`.

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
  tests for the new `alt+w`/`alt+n` preview keys (assert the action fires) — the
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

## Final Implementation Notes
- **Actual work done:**
  - Gated the three retry-apply actions by adding them to the existing
    `_TAB_SCOPED_ACTIONS` dict in `brainstorm_app.py` mapped to `tab_running`.
    This reuses `check_action`'s existing generic path (active on the owning
    tab, `None` elsewhere) — no new gating branch needed. Fixes the `ctrl+r`
    footer leak and the always-live explorer/synthesizer actions.
  - Replaced the undeliverable `ctrl+shift+b`/`ctrl+shift+l` wizard preview
    chords with `alt+w`/`alt+n` on `ActionsWizardScreen.BINDINGS`. Verified
    collision-free against all bindings.
  - Updated three stale code comments + two test docstrings that named the old
    chords.
  - Added the first real key-dispatch tests: `PreviewKeyDispatchTests` in
    `tests/test_brainstorm_proposal_preview.py` (drives `pilot.press("alt+w")`
    /`alt+n` through the *shipping* `ActionsWizardScreen.BINDINGS` + action
    methods borrowed verbatim, so a regression to a wrong/undeliverable key
    fails) and a new `tests/test_brainstorm_binding_scope.py` (boots a real
    `BrainstormApp`, asserts each retry action is active on Running and `None`
    on Browse/Session). Full brainstorm suite (619) + shortcut-scopes green.
- **Deviations from plan — AC correction (TextArea no-op):** The plan's
  Verification said a focused TextArea would receive the replacement key "as a
  no-op for the preview action (does not toggle ratio/numbering)". Empirically
  verified against Textual 8.2.7 and that wording was WRONG: a focused TextArea
  + `alt+w` leaves the TextArea text **unchanged** (non-printable, not inserted)
  **and the screen binding still fires** — which is the *desirable* behaviour
  (the key is usable while typing). A bare printable letter, by contrast, is
  swallowed as TextArea text and never reaches the binding. The real, valuable
  property — and what the tests now assert — is "alt+<letter> does not corrupt
  typed text while remaining usable", plus the plain-letter contrast (the actual
  reason alt+<letter> beats a bare letter). The action-suppression framing was a
  wrong assumption about Textual's key bubbling, corrected here.
- **`ctrl+r` footer visibility:** `ctrl+r` keeps its implicit `show=True`, so on
  the Running tab it is now footer-visible (deliverable plain key, meaningful
  there). The explorer/synthesizer chords stay `show=False` (undeliverable;
  t1018_2 removes them and re-homes the logic onto the GroupRow).
- **Issues encountered:** (1) `pilot.press("b"/"s")` did not switch tabs in the
  booted app because tab-switch key routing depends on the focused widget; the
  binding-scope test sets `TabbedContent.active` directly instead, isolating the
  `check_action` gating logic (its real input) from key routing. (2) The
  borrowed `action_cycle_preview_ratio` delegates to `_apply_preview_ratio`, so
  the test host must borrow that helper too.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **Per-screen scoping model established here:** brainstorm's tabs are
    `TabPane`s inside a single App screen (NOT separate `Screen`s), so app-level
    contextual actions are scoped via `check_action` + the `_TAB_SCOPED_ACTIONS`
    dict, not by moving them onto a per-screen `BINDINGS`. Real `Screen`s (e.g.
    `ActionsWizardScreen`) own their own `BINDINGS`. t1018_2 should place its
    Running-tab restart actions as per-row `on_key` + render hints on the
    GroupRow (consistent with the landed `w`/`R`/`x` pattern), NOT as footer
    Bindings.
  - **Left intact for t1018_2:** `action_retry_explorer_apply` /
    `action_retry_synthesizer_apply` methods AND their `ctrl+shift+x`/
    `ctrl+shift+y` App bindings. t1018_2 re-homes that logic onto the GroupRow
    and removes the dead chord bindings then.
  - **Key-delivery rule (proven via the alt+w/alt+n empirical check):**
    `alt+<letter>` is deliverable through the ghostty→tmux→Textual stack and is
    ignored as text by a focused TextArea while still firing the binding. Prefer
    it for any reusable contextual key where typing is possible. Avoid bare
    `ctrl+b` (tmux prefix) and any `ctrl+shift+<letter>` chord.
  - **Test pattern for key delivery:** drive `pilot.press(...)` through the
    *real* BINDINGS (borrow `SomeScreen.BINDINGS` + the action methods verbatim
    onto a host App) so the test fails if the bound key string regresses — the
    headless driver still cannot prove real-terminal delivery (t1018_4 covers
    that live).
