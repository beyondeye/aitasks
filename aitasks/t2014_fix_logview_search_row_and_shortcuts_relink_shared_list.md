---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui, textual, shortcuts]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2003
followup_kind: upstream_defect
created_at: 2026-10-15 23:01
updated_at: 2026-10-15 23:51
---

## Origin

Spawned from t2003 during Step 8b review.

## Upstream defect

- `.aitask-scripts/logview/logview_app.py:48` — `#search-box { display: none; height: 1; }` on a
  stock `Input` leaves a 0-row content area. This is the same defect as frozenagent's `/` box
  (fixed in t2003): typed search text is received into `Input.value` but never drawn.
- `.aitask-scripts/lib/shortcuts_mixin.py:140` — `_relink_live_bindings` does
  `mapping.setdefault(new_key, []).append(active_b)`. `BindingsMap.copy()` is shallow, so when a
  user override moves a binding onto a key the App already binds, this appends to the CLASS-level
  `_merged_bindings` list. The moved binding then leaks into every later instance of that App in
  the process: tests, the second app in one process, and so on.

## Diagnostic context

From t2003 (archived plan `aiplans/archived/p2003_frozenagent_selection_search_copy_fixes.md`),
measured on Textual 8.2.7:

- **Search row.** With `height: 1` the Input region is 2 rows: just the `tall` border's top and
  bottom lines. `content_region.height == 0`. Both `height: 1; border: none` and `height: 3`
  give a 1-row text area. frozenagent copied this CSS from logview. t2003 chose the compact
  `border: none` form, and pins it with a test that presses `/`, types, and asserts the text in
  `export_screenshot()`. Checking `Input.value` is not enough.
- **Shared list.** `BindingsMap.copy()` is `copy.key_to_bindings = self.key_to_bindings.copy()`,
  a dict copy whose per-key lists are the class-level ones. t2003's footer toggle
  (`FrozenAgentApp._sync_copy_keys`) therefore assigns NEW lists. `_relink_live_bindings`
  removes from the old key correctly (it builds a new list), but `setdefault(...).append` on an
  existing key mutates the shared list.

## Suggested fix

- logview: `#search-box { display: none; height: 1; border: none; }`, plus a pilot test that
  presses `/`, types, and checks the rendered screen (see t2003's `SearchBoxTests`).
- shortcuts_mixin: `mapping[new_key] = [*mapping.get(new_key, []), active_b]`, plus a test that
  rebinds onto an already-bound key, then asserts that `type(app)._merged_bindings` is unchanged
  and that a second instance without the override is unaffected.
