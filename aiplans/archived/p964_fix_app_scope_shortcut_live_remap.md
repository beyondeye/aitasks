---
Task: t964_fix_app_scope_shortcut_live_remap.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Fix App-scope shortcut live remap (t964)

## Context

Per-TUI key rebinds made in the Shortcuts editor never reach Textual's *live*
keymap for bindings registered through `ShortcutsMixin.__init__`. The editor
row, registry, footer hints, and tab titles all show the new key, but pressing
the new key does nothing — the original default key keeps firing (even after
restart, despite the editor's "restart to apply" message). This undermines the
whole customization feature for these scopes and is confusing to users.

**Root cause (empirically confirmed).** Textual's `DOMNode.__init__`
(`textual/dom.py:218`) builds the live keymap once:
`self._bindings = self._merged_bindings.copy()`. `_merged_bindings` is a
`ClassVar` computed by the metaclass at *class-definition* time from the
**default** keys. `ShortcutsMixin.__init__`
(`.aitask-scripts/lib/shortcuts_mixin.py:83-91`) calls `super().__init__()`
first (which builds `self._bindings` from defaults) and only *then* substitutes
the override keys into `self.BINDINGS` via `register_app_bindings`. Nothing
re-reads `self.BINDINGS` afterward, so the live `self._bindings` keeps the
default keys.

**Scope correction (verified, broader than the task states).** The task claims
"Widget/Screen/Modal scopes are unaffected because they register at class-body
load time." That is inaccurate: the modal scopes that use the mixin
(`AgentCommandScreen` scope `shared.agent_cmd`, `StaleEntryModal` scope
`shared.stale_entry`) register in `ShortcutsMixin.__init__` exactly like Apps,
so they have the *same* bug. A scratch reproduction confirmed both an App and a
`ModalScreen` keep the default key live after an override. The fix therefore
lives in the mixin and repairs every subclass at once (user-approved scope:
"cover all subclasses"). No scope currently does class-body
`BINDINGS = register_app_bindings(...)`; the editor-only modal
(`ShortcutEditorModal`) deliberately does not use the mixin and is unaffected.

## Approach

Reflect the override into the already-built live keymap (`self._bindings`)
right after `register_app_bindings` substitutes the keys. **Do not** rebuild
`self._bindings` wholesale from `self.BINDINGS` — the live map also holds
framework bindings absent from `self.BINDINGS` (e.g. `ctrl+c` help-quit,
`ctrl+p` command palette, inherited Screen `tab`/`shift+tab`), and a naive
rebuild would drop them. Instead, move only the bindings whose key actually
changed, key-by-key, leaving everything else intact.

### File 1 — `.aitask-scripts/lib/shortcuts_mixin.py`

In `ShortcutsMixin.__init__`, capture the default-keyed list before
substitution, then relink the live map:

```python
def __init__(self, *args, **kwargs) -> None:
    super().__init__(*args, **kwargs)
    if not self._shortcuts_scope:
        raise RuntimeError(
            "ShortcutsMixin subclass must set _shortcuts_scope"
        )
    default_bindings = self.BINDINGS
    self.BINDINGS = register_app_bindings(
        self._shortcuts_scope, default_bindings
    )
    self._relink_live_bindings(default_bindings, self.BINDINGS)
```

New private helper (mirrors the move-key surgery Textual's own
`BindingsMap.apply_keymap` performs, but keyed on `(default_key, action)`
because our bindings carry no `Binding.id`):

```python
def _relink_live_bindings(self, defaults, overridden) -> None:
    """Move remapped keys into the live keymap Textual built from defaults.

    Textual copies the class-level ``_merged_bindings`` (computed from the
    *default* keys at class-definition time) into ``self._bindings`` during
    ``super().__init__()``. Because the mixin substitutes override keys into
    ``self.BINDINGS`` *after* that copy, the live keymap would keep firing the
    default key. For each binding whose key was remapped, move it from its
    default key to its override key in ``self._bindings`` — without disturbing
    the framework bindings (quit, command palette, screen tab-nav, ...) that
    live alongside in the same map and are absent from ``self.BINDINGS``.

    ``register_app_bindings`` returns one entry per input binding in order, so
    ``defaults`` and ``overridden`` align by index.
    """
    live = getattr(self, "_bindings", None)
    if live is None:  # defensive: non-DOMNode use (tests / future scopes)
        return
    mapping = live.key_to_bindings
    for default_b, active_b in zip(defaults, overridden):
        old_key = getattr(default_b, "key", None)
        new_key = getattr(active_b, "key", None)
        action = getattr(active_b, "action", None)
        if not old_key or not new_key or old_key == new_key:
            continue
        bucket = mapping.get(old_key)
        if bucket is not None:
            remaining = [
                b for b in bucket if getattr(b, "action", None) != action
            ]
            if remaining:
                mapping[old_key] = remaining
            else:
                del mapping[old_key]
        mapping.setdefault(new_key, []).append(active_b)
```

Notes on correctness / blast radius:
- **Index alignment** holds because `register_app_bindings`
  (`keybinding_registry.py:102-141`) appends exactly one result per input
  binding, in order (whether unchanged, scope-overridden, or shared-scope
  overridden). So shared bindings (`?`, `j`) spliced into App `BINDINGS` are
  relinked too.
- **Framework bindings preserved**: only keys present in `defaults` with a
  changed override are touched; `ctrl+c`/`ctrl+p`/`tab` etc. are never in
  `defaults`, so they stay put. (A scratch test showed `ctrl+q`/`ctrl+c`/
  `ctrl+p` present in an App's live map and `tab`/`shift+tab` in a modal's.)
- **Same-key collisions** (two actions sharing a default key) are handled by
  filtering the removal on `action`.
- **No `Binding.id` requirement** and no use of `app._keymap` — keeps the fix
  self-contained and avoids assigning ids across the whole binding corpus.
- **Idempotent / no-op when no override**: the `old_key == new_key` guard skips
  unchanged bindings, so a TUI with no overrides is unaffected.
- `super().__init__()` finishes the full `DOMNode.__init__` chain before the
  mixin regains control, so `self._bindings` exists. `App.__init__` only
  *augments* `self._bindings` (adds the command palette at `app.py:874-889`)
  and never resets it afterward, so the relink persists through mount and key
  resolution (`Screen._binding_chain` copies `node._bindings` per keypress).

### File 2 — `tests/test_settings_shortcuts_tab.py` (update stale test)

`test_override_flows_into_bindings_like_every_app_binding`
(`:451-473`) currently documents the limitation in its docstring and asserts
the override reaches `app.BINDINGS` *but not* a live key-press. After the fix
that assumption is obsolete. Update it to:
- Drop the "not a live key-press" caveat from the docstring.
- Keep the existing `app.BINDINGS`/footer-hint assertions.
- Add a live-key assertion: confirm `app._bindings.key_to_bindings` contains
  the override key `z` for `switch_tab_tmux` and no longer the default `t`
  for that action.

### File 3 — `tests/test_shortcuts_mixin_live_remap.py` (new)

A focused e2e test mirroring the `run_test`/`Pilot` pattern already used in
`test_settings_shortcuts_tab.py` (temp workspace + `keybinding_registry._reset_for_tests()`
in setUp/tearDown). Defines minimal `ShortcutsMixin` subclasses with an
observable action so a real key-press can be asserted:

- **App-scope live press**: a tiny `App` subclass, scope `demo`, with
  `Binding("e", "do_thing", ...)` that sets `self.fired = True`. Override
  `demo.do_thing -> x` in userconfig, `refresh_all()`, then under `run_test`:
  - press `x` → assert `app.fired is True` (override key now fires);
  - reset, press `e` → assert it does **not** fire (default key retired).
- **Modal-scope live press**: an analogous `ModalScreen` subclass pushed onto a
  host app, proving the broadened scope (the bug the task under-diagnosed).
- **Framework binding preserved**: assert the relink leaves an unrelated
  framework binding (e.g. command palette `ctrl+p`, or `ctrl+c`) still present
  in `app._bindings.key_to_bindings`.
- **No-override no-op**: with no userconfig override, assert the default key
  still fires.

## Verification

```bash
# New focused e2e test (App + modal live press, framework-binding preservation)
/home/ddt/.aitask/venv/bin/python tests/test_shortcuts_mixin_live_remap.py

# Updated settings test (live-key assertion replaces the stale limitation note)
/home/ddt/.aitask/venv/bin/python tests/test_settings_shortcuts_tab.py

# Regression sweep of the shortcuts suite
/home/ddt/.aitask/venv/bin/python tests/test_shortcut_scopes.py
/home/ddt/.aitask/venv/bin/python tests/test_shortcut_editor_modal.py
bash tests/test_keybinding_registry.sh

# Manual (optional): launch a TUI, rebind an App-scope key (e.g. settings `e`
# export) in the Shortcuts editor, restart, press the new key — it now fires.
```

Step 9 (Post-Implementation): no separate branch (profile 'fast' works on the
current branch); commit code + plan separately, then archive via
`aitask_archive.sh 964`.

## Risk

### Code-health risk: medium
- The fix lives in `ShortcutsMixin.__init__`, the shared path every
  registry-backed TUI (board, monitor, settings, brainstorm, modals, ...) flows
  through; a regression in key-resolution here would reach all of them ·
  severity: medium · → mitigation: covered by the new e2e test + the
  shortcuts-suite regression sweep in Verification (no separate task needed).
- Live-keymap surgery mutates `self._bindings.key_to_bindings` directly rather
  than via a public Textual API (no `Binding.id` available to use
  `apply_keymap`); a future Textual upgrade could change that internal shape ·
  severity: low · → mitigation: TBD (guarded with `getattr`/defensive checks;
  pinned by tests that would fail loudly on shape change).

### Goal-achievement risk: low
- Root cause and reproduction are empirically confirmed (App + modal); the
  relink mechanism mirrors Textual's own `apply_keymap` move-key surgery and is
  validated by the required e2e key-press test · severity: low · → mitigation:
  None needed.

## Final Implementation Notes

- **Actual work done:** Added `ShortcutsMixin._relink_live_bindings()` in
  `.aitask-scripts/lib/shortcuts_mixin.py` and invoked it from `__init__` right
  after `register_app_bindings`. It moves each remapped binding from its
  default key to its override key in the live `self._bindings.key_to_bindings`,
  preserving co-resident framework bindings. Added a new e2e test
  `tests/test_shortcuts_mixin_live_remap.py` (6 tests) and updated the stale
  `test_override_flows_into_bindings_like_every_app_binding` in
  `tests/test_settings_shortcuts_tab.py` to assert the live keymap now carries
  the override.
- **Deviations from plan:** None. Implemented exactly as approved.
- **Issues encountered:** None. The relink works for App and modal scopes;
  `App.__init__` only augments `_bindings` (command palette) after the mixin
  runs and never resets it, so the relink persists.
- **Key decisions:** Chose direct key-by-key move surgery over (a) a wholesale
  rebuild of `self._bindings` from `self.BINDINGS` — which would drop framework
  bindings (`ctrl+c`/`ctrl+p`/screen `tab`) — and (b) Textual's `app._keymap` /
  `apply_keymap`, which requires assigning `Binding.id` across the whole binding
  corpus. The move-surgery is self-contained and matched on `(default_key,
  action)`. Scoped the fix to the shared mixin (user-approved) so it repairs
  modal scopes (`shared.agent_cmd`, `shared.stale_entry`) too, not just Apps —
  empirically confirmed both were broken, contradicting the task's original
  "only Apps affected" diagnosis.
- **Upstream defects identified:** None.

