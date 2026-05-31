---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 13:02
updated_at: 2026-05-31 15:20
---

## Context

Follow-up surfaced during t848_5 review. The shortcut-label renderer
`lib/shortcut_labels.py` (from t848_2) renders button/footer labels with the
active key inlined in the `(X)plore` style. In `_render_wrap` the matched
character is **always uppercased**:
`f"{text[:i]}({ch.upper()}){text[i + 1:]}"`. So `render_label("Export shortcuts",
"x")` yields `E(X)port shortcuts` even though the source letter is lowercase.
This matches the legacy `(P)ick` / `e(X)plore` convention, but the user wants an
**option to make the rendering case-aware globally** — i.e. preserve the matched
character's actual case (`E(x)port shortcuts`) across every TUI, configurable in
one place.

## Goal

Add a configurable option that controls whether the wrapped mnemonic letter is
uppercased (current behavior) or preserves the matched character's case. "Global"
means a single setting that affects every TUI's labels, not just a per-call
override. **Default MUST remain uppercase** (back-compat) so existing labels and
goldens don't churn unless the user opts in.

## Key Files to Modify

- `.aitask-scripts/lib/shortcut_labels.py` — `_render_wrap` (the `ch.upper()`
  call) and `render_label`'s signature. Add a parameter (e.g.
  `uppercase_key: bool = True`) so the pure function stays parameter-driven.
  Consider whether `_render_leading` (which lowercases the key) needs a parallel
  option or is out of scope.
- `.aitask-scripts/lib/shortcuts_mixin.py` — `get_label()` and
  `ShortcutsMixin.label()` are the callsites that pass `text`+`key` to
  `render_label`. Resolve the global flag here (cached) and thread it into
  `render_label`, keeping `shortcut_labels.py` free of any config dependency.
- The setting's home: recommend per-user `aitasks/metadata/userconfig.yaml`
  (it's a personal display preference), key e.g.
  `shortcut_label_case: upper|preserve` (default `upper`). Read via
  `config_utils.load_yaml_config`.
- Optional: expose the toggle in the Settings TUI
  (`.aitask-scripts/settings/settings_app.py`) — can be deferred/separate.

## Reference Files for Patterns

- `.aitask-scripts/lib/shortcut_labels.py` — `render_label`, `_render_wrap`,
  `_render_leading`, `display_form`.
- `.aitask-scripts/lib/shortcuts_mixin.py` — `get_label` / `ShortcutsMixin.label`.
- `.aitask-scripts/lib/keybinding_registry.py` — `load_user_overrides` shows the
  cached-read-from-userconfig pattern to mirror for the new flag.

## Implementation Plan

1. Add `uppercase_key: bool = True` to `render_label` / `_render_wrap`
   (default = current behavior; when `False`, emit `({ch})` preserving case).
2. In `shortcuts_mixin`, resolve `shortcut_label_case` from `userconfig.yaml`
   once (cache like `keybinding_registry._OVERRIDES_CACHE`), map to the bool,
   and pass it into every `render_label` call.
3. (Optional) Add a Settings-TUI toggle.
4. Update `tests/test_shortcut_labels.sh` and the goldens in
   `tests/test_shortcut_labels_golden/` to cover BOTH modes (upper + preserve)
   — per the golden-file convention, commit a golden per (input x option) combo.

## Verification Steps

```bash
bash tests/test_shortcut_labels.sh
# Manual: set shortcut_label_case: preserve in userconfig.yaml, launch a TUI,
# confirm labels render e.g. E(x)port instead of E(X)port; default unchanged.
```

## Notes

- This only changes the casing of the parenthesized mnemonic in the label text;
  it does not affect which key is bound.
- Keep the default uppercase to avoid silently restyling every TUI + churning
  all shortcut-label goldens.
