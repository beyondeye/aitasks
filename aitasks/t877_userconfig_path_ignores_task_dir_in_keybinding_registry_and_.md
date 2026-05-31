---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [custom_shortcuts, tui, python]
file_references: [.aitask-scripts/lib/keybinding_registry.py:32-33, .aitask-scripts/lib/shortcuts_mixin.py:59, .aitask-scripts/lib/userconfig_persist.py:63-72]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 16:03
updated_at: 2026-05-31 16:08
---

## Problem

The `userconfig.yaml` path is resolved inconsistently across the lib modules
that read it. `userconfig_persist._userconfig_path()` honors the `TASK_DIR`
env override (defaulting to `aitasks`), but two sibling readers hardcode a
cwd-relative path and ignore `TASK_DIR`:

- `.aitask-scripts/lib/keybinding_registry.py:32-33` — `_userconfig_path()`
  returns `Path("aitasks/metadata/userconfig.yaml")`.
- `.aitask-scripts/lib/shortcuts_mixin.py:59` —
  `load_yaml_config(Path("aitasks/metadata/userconfig.yaml"))`.

In normal operation this is harmless: TUIs `cd` to the repo root and `TASK_DIR`
is unset (→ defaults to `aitasks`), so all three resolvers agree. The
divergence only surfaces when `TASK_DIR` is set (tests, non-default layouts):
`keybinding_registry` / `shortcuts_mixin` then read the *wrong* file while
`userconfig_persist` (and `shortcut_persist`, which routes through it) read the
right one.

Discovered during the t868 manual verification of t865: a scratch-workspace
smoke that set `TASK_DIR` saw `keybinding_registry.load_user_overrides()` read
the real repo config instead of the scratch file, masking the override under
test.

## Suggested fix

Make `keybinding_registry._userconfig_path()` and the `shortcuts_mixin` read
delegate to `userconfig_persist._userconfig_path()` — the module that documents
itself as the single persistence layer for `userconfig.yaml`. There is no
circular-import risk: `userconfig_persist` imports only stdlib + `yaml` and
does NOT import `keybinding_registry`. (Alternatively, replicate the
`os.environ.get("TASK_DIR", "aitasks")` logic in both, but delegating to the
canonical resolver is preferable — single source of truth.)

## Notes / scope

- Low priority: no impact on default production TUIs; this is a latent
  test-isolation / non-default-layout correctness issue.
- Keep existing tests green: the modal/registry test fixtures `chdir` into a
  tmp workspace (cwd-relative still resolves) and do not set `TASK_DIR`, so the
  default `aitasks` continues to resolve correctly under the chdir'd cwd.
- Possibly also review `config_utils.py:247,380` for the same pattern, though
  those derive `meta_path` from a caller-provided base and may already be
  correct.
