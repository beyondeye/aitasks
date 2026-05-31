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

## Post-Review Changes

### Change Request 1 (2026-05-31 16:06)
- **Requested by user:** Set `shortcut_label_case` to `preserve` in the local
  config and in the seed (so new installs default to case-preserving labels).
- **Changes made:**
  - Added `shortcut_label_case: preserve` to this project's local
    `aitasks/metadata/userconfig.yaml` (gitignored — not part of the code
    commit; applied so this project's TUIs render `E(x)port`-style labels).
  - Seeded `shortcut_label_case: preserve` (with an explanatory comment) into
    the userconfig template generated by `setup_userconfig()` in
    `.aitask-scripts/aitask_setup.sh`, so fresh `ait setup` installs default to
    preserve. The **code fallback default stays `upper`** in
    `shortcuts_mixin._resolve_uppercase_key` — existing installs without the
    key are unaffected (back-compat preserved); only newly-bootstrapped and
    opted-in configs get `preserve`.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`,
  `aitasks/metadata/userconfig.yaml` (local, gitignored).

## Final Implementation Notes

- **Actual work done:**
  - `lib/shortcut_labels.py` — added pure keyword-only `uppercase_key: bool =
    True` to `render_label`, threaded to `_render_wrap`. When `False`, the
    matched in-text character keeps its source case (`E(x)port`) instead of
    being uppercased (`E(X)port`). Module remains config-free.
  - `lib/shortcuts_mixin.py` — added the config-aware layer: cached
    `_resolve_uppercase_key()` (reads `shortcut_label_case` from
    `userconfig.yaml` via `config_utils.load_yaml_config`, fail-soft → default
    uppercase, only literal `preserve` flips it), `refresh_label_case()` cache
    invalidator, and `render_label_cfg()` for literal-key callsites. Threaded
    the resolved flag into `ShortcutsMixin.label()` and `get_label()`.
  - `settings/settings_app.py` — switched the two direct `render_label(...)`
    button labels to `render_label_cfg(...)`; dropped the now-unused
    `render_label` import.
  - `aitask_setup.sh` — seeded `shortcut_label_case: preserve` into the
    userconfig template generated by `setup_userconfig()` (per user request,
    Change Request 1).
  - Tests: extended `tests/test_shortcut_labels.sh` with an optional 5th
    `uppercase_key` case field + 4 new goldens (upper/preserve/prefix-unaffected);
    new `tests/test_shortcut_label_case.py` (13 unittests) covering the config
    resolver, cache invalidation, `render_label_cfg`, and `get_label` end-to-end.
- **Deviations from plan:**
  - Original plan said "Default MUST remain uppercase". Per Change Request 1 the
    user asked to seed `preserve` as the bootstrap default. Resolved by seeding
    `preserve` into newly-created userconfigs (`setup_userconfig`) **and** the
    project-local userconfig, while keeping the **code fallback default
    `upper`** in `_resolve_uppercase_key`. Net effect: existing installs without
    the key are unchanged (back-compat intact); only fresh installs / opted-in
    configs get `preserve`.
- **Issues encountered:** None. All targeted tests pass; no regressions in the
  shortcut/settings/registry suites.
- **Key decisions:**
  - Kept `shortcut_labels.py` pure/parameter-driven; the config dependency lives
    only in `shortcuts_mixin.py` (single global resolution point, cached like
    `keybinding_registry._OVERRIDES_CACHE`).
  - Scoped `uppercase_key` to the **matched-in-text** character only; the
    no-match prefix `({key.upper()})`, multi-key `display_form`, and the
    `leading` style are intentionally unaffected.
  - Routed the two literal-key settings buttons through `render_label_cfg` for
    true global consistency even though their rendered output is identical in
    both modes today (future-proofing).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t848_6 (docs):** document the `shortcut_label_case: upper|preserve`
    userconfig setting. Note: the **code default is `upper`** but fresh
    `ait setup` installs are **seeded with `preserve`** (via `setup_userconfig`).
    The flag affects only the wrapped in-text mnemonic of the `wrap` style — not
    the no-match prefix, multi-key combos, or the `leading` filter-bar style.
  - **Deferred follow-up (Settings TUI toggle):** the optional in-app toggle for
    `shortcut_label_case` on the Settings → Shortcuts tab was not implemented
    (kept scope tight, avoids churning `test_settings_shortcuts_tab.py`).
    Reusable hooks now exist: `shortcuts_mixin.refresh_label_case()` to
    invalidate the cache after a write, and the setting key
    `shortcut_label_case` in `userconfig.yaml`. Worth a small standalone task.
  - For any new literal-key (non-registry) label callsite, use
    `shortcuts_mixin.render_label_cfg(text, key)` rather than importing
    `render_label` directly, so the global setting is honored.
