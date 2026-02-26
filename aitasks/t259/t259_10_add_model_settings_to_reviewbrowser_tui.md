---
priority: low
effort: low
depends: [t259_5]
issue_type: feature
status: Ready
labels: [aitask_review, ui]
created_at: 2026-02-26 18:45
updated_at: 2026-02-26 18:46
---

## Context

Depends on: t259_5 (TUI app shell), t265 (settings screen patterns)

NOTE: Task details are not fully defined yet. Implementation will depend on the settings screen patterns established in t265 and related tasks. This task should be refined once t265 is implemented.

## Planned Scope

- Add settings screen to reviewbrowser TUI (same pattern as codebrowser settings from t265)
- Model selector for batch review invocations from TUI
- Read available models from aitasks/metadata/models_claude.txt
- Store selected model preference in TUI settings
