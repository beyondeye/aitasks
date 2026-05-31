---
priority: medium
effort: medium
depends: [t848_4]
issue_type: feature
status: Implementing
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-30 22:50
updated_at: 2026-05-31 16:45
---

## Context

Follow-up to **t848_4** (the in-TUI `?` shortcut editor modal). In t848_4 a
**reset-to-default** (and any rebind) that would collide with another binding
*within the same scope* is **blocked at edit time** with an error toast
("Cannot reset: default key 'X' is already bound to '<other>' in <scope>. Rebind
that first."). The user must manually move the conflicting binding before the
reset is allowed.

This task implements the richer **cascade** resolution the user asked for:
when resetting a binding to its default would land on a key currently held by
another in-scope action, offer to also reset (or relocate) that conflicting
binding — following the conflict chain until the scope is collision-free — behind
a single preview + confirm.

## Key Files to Modify

- `.aitask-scripts/lib/shortcut_editor_modal.py` — the editor from t848_4.
  - Today `action_reset_default` calls `_would_collide(...)` and, on a clash,
    only `notify(...)`s an error and returns. Replace that dead-end with an
    offer to resolve via cascade (e.g. push a `CascadePreviewScreen`).
  - Reuse the existing `_effective_key` / `_would_collide` / `_pending`
    machinery; the cascade computes a *set* of pending edits, not just one.
- **NEW** `.aitask-scripts/lib/cascade_resolve.py` (or inline) — pure logic:
  - Given `(scope, action_id)` being reset to its default key and the current
    effective key-map for that scope, compute the chain of bindings that must
    also change to make the scope collision-free.
  - **Cycle handling:** an A↔B swap (A wants B's key, B wants A's key) must be
    detected and either resolved as a swap or surfaced as unresolvable — do not
    loop forever.
  - Return an ordered list of `(scope, action_id, new_key | RESET)` edits for
    the preview.
- **NEW** `CascadePreviewScreen(ModalScreen[bool])` (in `shortcut_editor_modal.py`
  or its own `lib/` module) — shows every binding the cascade will touch
  (action, old key → new key) and a single confirm/cancel. Carries its own
  `DEFAULT_CSS` (per `feedback_modal_self_contained_css`).

## Reference Files for Patterns

- `.aitask-scripts/lib/shortcut_editor_modal.py` — `_would_collide`,
  `_effective_key`, `_colliding_pairs`, the `_pending` sentinel model (`_CLEAR`).
- `.aitask-scripts/lib/keybinding_registry.py` — `iter_scope_bindings`,
  `resolve_key`, `_DEFAULTS`.
- `.aitask-scripts/lib/shortcut_persist.py` — `save_override` / `clear_override`
  (the cascade persists multiple edits, then `keybinding_registry.refresh(scope)`).
- `tests/test_shortcut_editor_modal.py` — the Pilot + direct-method test harness
  to extend.

## Implementation Plan

1. Implement the pure cascade-chain computation with cycle detection; unit-test
   it in isolation (no Textual needed) — table-driven cases incl. a 3-link chain
   and an A↔B swap.
2. Build `CascadePreviewScreen` (multi-row preview + confirm).
3. Wire `action_reset_default`: on a clash, compute the chain; if resolvable,
   push the preview; on confirm, apply all edits into `_pending` and refresh the
   table; on cancel, leave state untouched. If unresolvable (e.g. a cycle that
   can't be swapped), keep the current block-with-message behavior.
4. Decide whether cascade also applies to a colliding **rebind** (not just
   reset) — default: reset only, matching the user's framing; note the decision.

## Verification Steps

```bash
python3 tests/test_shortcut_editor_modal.py     # extended with cascade cases
bash tests/test_keybinding_registry.sh
# Manual: ait board → ? → reset a binding whose default is taken → preview lists
#         the cascade → confirm → scope is collision-free after save.
```

## Notes

- Depends on **t848_4** (must reuse its editor + helpers). Not a dependency of
  t848_5/t848_6/t848_7.
- Keep the t848_4 block-with-message path as the fallback for the unresolvable
  case.
