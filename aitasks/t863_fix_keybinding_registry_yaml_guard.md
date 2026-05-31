---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui]
created_at: 2026-05-31 08:35
updated_at: 2026-05-31 08:35
---

## Origin

Spawned from t832_8 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/keybinding_registry.py:50-52 — load_user_overrides() calls yaml.safe_load without catching yaml.YAMLError; a malformed (gitignored) aitasks/metadata/userconfig.yaml therefore propagates a ParserError that crashes every board/TUI at import. Should fall back to {} (and warn) on parse failure, matching the existing missing-file fallback.`

## Diagnostic context

While import-smoke-testing the t832_8 board changes, `import aitask_board`
(and even importing the untouched `tui_switcher`) crashed with
`yaml.parser.ParserError` from `aitasks/metadata/userconfig.yaml`. The file
had become malformed (a dangling `- agentcrew` block item after
`last_used_labels: [codexcli]`). The crash originates in `tui_switcher.py`'s
module-level `_register_shared_bindings(...)` → `register_app_bindings` →
`load_user_overrides()` → `yaml.safe_load(f)` (keybinding_registry.py:50-52),
which has no try/except around the parse. The existing code already guards
the missing-file case (`if not path.is_file(): return {}`) but not the
malformed-content case.

## Suggested fix

Wrap the `yaml.safe_load(f)` in `load_user_overrides()` in a
`try/except yaml.YAMLError`, returning `{}` (and emitting a one-line warning
to stderr) on parse failure — mirroring the existing missing-file fallback so
a corrupt per-user override file degrades to "no overrides" instead of
crashing every board/TUI at import.
