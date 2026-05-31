---
Task: t848_10_case_aware_mnemonic_label_rendering.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_6_documentation_for_customizable_shortcuts.md, aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md, aitasks/t848/t848_8_cascade_reset_to_default.md
Archived Sibling Plans: aiplans/archived/p848/p848_1_shortcut_registry_and_overrides.md, aiplans/archived/p848/p848_2_label_renderer_and_board_pilot.md, aiplans/archived/p848/p848_3_sweep_remaining_tuis.md, aiplans/archived/p848/p848_4_in_tui_shortcut_editor_modal.md, aiplans/archived/p848/p848_5_settings_tui_shortcuts_tab.md, aiplans/archived/p848/p848_9_eager_subscope_registration.md
Base branch: main
plan_verified: []
---

# t848_10 — Case-aware mnemonic label rendering (global option)

## Context

The shortcut-label renderer `lib/shortcut_labels.py` (from t848_2) inlines the
active key into label text in the `(X)plore` style. In `_render_wrap` the
matched in-text character is **always uppercased**
(`f"{text[:i]}({ch.upper()}){text[i+1:]}"`), so `render_label("Export shortcuts",
"x")` yields `E(X)port shortcuts` even though the source letter is lowercase.

The user wants a **global, configurable option** to make the wrapped mnemonic
case-aware — preserve the matched character's actual case (`E(x)port shortcuts`)
across every TUI from one setting. **Default MUST stay uppercase** (back-compat,
so existing labels/goldens don't churn). `shortcut_labels.py` must stay a pure,
config-free, parameter-driven module; the config dependency lives in
`shortcuts_mixin.py`.

## Approach

A new per-user setting `shortcut_label_case: upper|preserve` (default `upper`)
in `aitasks/metadata/userconfig.yaml`. The pure renderer gains a boolean
parameter; the mixin resolves the setting once (cached, like
`keybinding_registry._OVERRIDES_CACHE`) and threads it into every render call.

### 1. `.aitask-scripts/lib/shortcut_labels.py` — pure param

- Add `uppercase_key: bool = True` to `render_label(...)` and pass it to
  `_render_wrap`.
- In `_render_wrap`, change the in-text match line to:
  ```python
  glyph = ch.upper() if uppercase_key else ch
  return f"{text[:i]}({glyph}){text[i + 1:]}"
  ```
- **Unchanged (intentionally out of scope):** the no-match prefix
  `({key.upper()})`, the multi-key `display_form(...)` branch, and the entire
  `_render_leading` style. The flag governs only the *matched-in-text character*
  — that is exactly the case the user complained about. `_render_leading`
  deliberately lowercases the key to preserve the pre-t848 `l Locked` look, and
  its key glyph is the binding key, not a character pulled from the text. (Note
  this scoping for the t848_6 docs sibling.)
- Update the module/`render_label` docstrings to describe `uppercase_key`.

### 2. `.aitask-scripts/lib/shortcuts_mixin.py` — config-aware layer

- Add a cached resolver mirroring `keybinding_registry`'s cache pattern, reading
  via `config_utils.load_yaml_config` (fail-soft → default uppercase, so a
  malformed gitignored userconfig never crashes a TUI):
  ```python
  from pathlib import Path
  from config_utils import load_yaml_config

  _LABEL_CASE_CACHE: bool | None = None

  def _resolve_uppercase_key() -> bool:
      global _LABEL_CASE_CACHE
      if _LABEL_CASE_CACHE is not None:
          return _LABEL_CASE_CACHE
      try:
          cfg = load_yaml_config(Path("aitasks/metadata/userconfig.yaml"))
          value = str(cfg.get("shortcut_label_case", "upper")).strip().lower()
      except Exception:
          value = "upper"
      _LABEL_CASE_CACHE = value != "preserve"   # only "preserve" flips it
      return _LABEL_CASE_CACHE

  def refresh_label_case() -> None:
      global _LABEL_CASE_CACHE
      _LABEL_CASE_CACHE = None
  ```
- Thread `uppercase_key=_resolve_uppercase_key()` into both render call-sites:
  `ShortcutsMixin.label()` and the module-level `get_label()`.
- Add a config-aware free function for literal-key callsites (no registry
  action_id):
  ```python
  def render_label_cfg(text: str, key: str, *, style: str = "wrap") -> str:
      return render_label(text, key, style=style,
                          uppercase_key=_resolve_uppercase_key())
  ```
- Update the module docstring to mention the global case setting.

### 3. `.aitask-scripts/settings/settings_app.py` — honor the global setting

- The only two direct `render_label(...)` callsites (button labels at
  ~line 2905-2906: `"Reset scope"`/`d`, `"Lint coherence"`/`l`) bypass the
  mixin. Switch them to `render_label_cfg(...)` so they honor the global
  setting too (true "global"). Update the import (line 30) from
  `from shortcut_labels import render_label` to import `render_label_cfg` from
  `shortcuts_mixin` (already imported there); drop the now-unused
  `render_label` import. *(Output is identical in both modes for these two
  specific strings, but routing through the config-aware path keeps the
  invariant and is future-proof.)*

### 4. Tests — `tests/test_shortcut_labels.sh` + goldens

- Extend the `CASES` format with an optional 5th `uppercase_key` field (`1`/`0`,
  default `1` when absent), parse via
  `IFS='|' read -r name style text key upper` + `[[ -z "$upper" ]] && upper=1`,
  and pass it into the python one-liner as
  `uppercase_key=(sys.argv[4] == '1')`. Existing cases stay unchanged (default
  `1`).
- Add cases + goldens (no trailing newline, matching existing files):
  - `wrap_export_x|wrap|Export shortcuts|x|1` → `E(X)port shortcuts`
  - `wrap_export_x_preserve|wrap|Export shortcuts|x|0` → `E(x)port shortcuts`
  - `wrap_save_changes_a_preserve|wrap|Save Changes|a|0` → `S(a)ve Changes`
  - `wrap_reset_scope_d_preserve|wrap|Reset scope|d|0` → `(D) Reset scope`
    (locks that the no-match prefix is unaffected by `preserve`)

### 5. New test — `tests/test_shortcut_label_case.py`

A `unittest` (auto-discovered by `run_all_python_tests.sh` via `test_*.py`)
covering the mixin config layer. chdir into a tmp dir, write
`aitasks/metadata/userconfig.yaml`, call `refresh_label_case()`, and assert:
- missing file / `upper` / garbage value → `_resolve_uppercase_key()` is `True`;
  `preserve` → `False`.
- `render_label_cfg("Export shortcuts", "x")` → `E(X)port shortcuts` (default)
  vs `E(x)port shortcuts` (preserve).
- `get_label(...)` end-to-end honors the setting (register a default binding via
  `keybinding_registry.register_app_bindings`, then resolve).
- Cache invalidation: changing the file without `refresh_label_case()` returns
  the stale value; after `refresh_label_case()` it re-reads.

Restore cwd and call `refresh_label_case()` in `tearDown`.

## Out of scope / deferred (note for sibling tasks)

- **Settings-TUI toggle** (task lists it as *Optional*): deferred to a follow-up
  to avoid churning the Shortcuts tab and its golden test
  `test_settings_shortcuts_tab.py`. Users opt in via `userconfig.yaml`. Surface
  in Final Implementation Notes so a follow-up can be queued.
- **Docs**: handled by the pending sibling **t848_6** (customizable-shortcuts
  docs) — add a "Notes for sibling tasks" entry there rather than writing
  user-facing docs here.
- **`_render_leading` case-preservation**: out of scope (rationale above).

## Verification

```bash
bash tests/test_shortcut_labels.sh          # all wrap/leading + new preserve cases
python3 tests/test_shortcut_label_case.py   # mixin config resolution + cache

# Manual:
#  - default: launch any TUI (e.g. ait board) → labels unchanged (E(X)port…)
#  - add `shortcut_label_case: preserve` to aitasks/metadata/userconfig.yaml,
#    relaunch → wrapped mnemonics preserve source case (E(x)port…)
```

See **Step 9 (Post-Implementation)** of the task-workflow for archival/cleanup.
