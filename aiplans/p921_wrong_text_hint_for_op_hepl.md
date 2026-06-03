---
Task: t921_wrong_text_hint_for_op_hepl.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
---

# Plan: Config-aware help-text hint for the op-definition wizard (t921)

## Context

In `ait brainstorm`, the Actions tab op-definition wizard shows a dim context
header for the operation being configured, ending in the hint `(? for details)`.
That `?` is stale: the op-help shortcut was moved to `H` and is now **dynamic** —
it is registered in the keybinding registry under scope `brainstorm`, action
`op_help`, and can be remapped by the user via the in-TUI shortcut editor (the
`?` key now opens the shortcut editor, not the op-help modal). The hint must
resolve the *effective* key at render time instead of hardcoding a literal.

A second, closely related instance of the same staleness lives in the
`OperationHelpModal` footer: `Esc / H close`. The `H` there is both hardcoded
and **wrong** — pressing `H` while the modal is open does not close it
(`action_op_help` raises `SkipAction` when a `ModalScreen` is on screen). Only
`Esc` closes the modal.

## Root cause

Two hardcoded literals reference the op-help shortcut instead of resolving it:

- `.aitask-scripts/brainstorm/brainstorm_app.py:5922` — `_mount_op_context_header`
  hardcodes `(? for details)`.
- `.aitask-scripts/brainstorm/brainstorm_app.py:1529` — `OperationHelpModal.compose`
  hardcodes `Esc / H close`.

The framework already provides the resolution primitive:
`resolve_key(scope, action_id, default_key)` in
`.aitask-scripts/lib/keybinding_registry.py:144`, which returns the user
override → recorded default → fallback. The brainstorm app sets
`_shortcuts_scope = "brainstorm"` (line 2356) and the `op_help` binding is
registered under that scope via `BINDINGS` (`Binding("H", "op_help", …)`,
line 3016).

## Changes

### 1. Import the resolver (brainstorm_app.py, import block ~line 16)

Add alongside the existing `shortcuts_mixin` import:

```python
from keybinding_registry import resolve_key  # noqa: E402
```

### 2. Config-aware wizard hint — `_mount_op_context_header` (~line 5919-5925)

Resolve the live `op_help` key and interpolate it into the hint:

```python
label_text, desc = info
help_key = resolve_key(self._shortcuts_scope, "op_help", "H") or "H"
container.mount(
    Label(
        f"[dim]{label_text} — {desc}  ({help_key} for details)[/dim]",
        classes="actions_op_context",
    )
)
```

`self._shortcuts_scope` is `"brainstorm"` on the app instance; `"H"` is the
fallback matching the registered default if resolution ever returns `None`.

### 3. Correct + de-stale the modal footer — `OperationHelpModal.compose` (line 1529)

`H` does not close the modal, so make the footer state only what is true:

```python
yield Label("[dim]Esc close[/]", id="op_help_footer")
```

(`OperationHelpModal` is a plain `ModalScreen`, not a `ShortcutsMixin`, and only
binds `escape` → `close`; there is no dynamic key to surface here.)

## Reuse notes

- `resolve_key` (`keybinding_registry.py:144`) is the canonical primitive for
  "literal key for a (scope, action)". No new helper needed.
- The render here is a plain inline string, not a wrapped mnemonic, so the
  `ShortcutsMixin.label()` / `render_label` path is intentionally *not* used —
  those wrap a key into a label (`E(X)port`), which is the wrong shape for an
  inline `(H for details)` hint.

## Verification

- `python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py` — syntax.
- Grep confirms no remaining stale literal:
  `grep -n "? for details" .aitask-scripts/brainstorm/brainstorm_app.py` → none.
- Manual (TUI): `ait brainstorm <task>` → Actions tab → start an op-definition
  wizard → context header reads `(H for details)`. Open the shortcut editor
  (`?`), remap `op_help` to another key, restart the wizard → hint reflects the
  new key. Open op help → footer reads `Esc close`; `Esc` closes it.

## Step 9

Post-implementation: commit on current branch (`bug:` prefix, `(t921)` suffix),
update + consolidate this plan, archive via `aitask_archive.sh 921`. No
separate branch/worktree to clean up (fast profile, current branch).

## Risk

### Code-health risk: low
- Two-line label-text change reusing an existing registry primitive; no logic
  or control-flow change, blast radius confined to one file's display strings.
  · severity: low · → mitigation: None needed.

### Goal-achievement risk: low
- Directly addresses the stale `(? for details)` hint with the documented
  dynamic-shortcut resolver; the footer fix is an in-scope correctness bonus.
  · severity: low · → mitigation: None needed.
