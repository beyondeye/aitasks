---
priority: low
effort: low
depends: [t259_8]
issue_type: feature
status: Ready
labels: [aitask_review]
created_at: 2026-02-26 18:45
updated_at: 2026-02-26 18:45
---

## Context

Depends on: t259_3 (session orchestration), t265 (model configuration infrastructure)

NOTE: Task details are not fully defined yet. Implementation will depend on the model configuration infrastructure created in t265 and related tasks. This task should be refined once t265 is implemented.

## Planned Scope

- Replace hardcoded --model sonnet default with reading from aitasks/metadata/models_claude.txt
- Use claude/<model> naming convention (e.g. claude/sonnet4.6) consistent with t265
- Batch driver --model flag should accept the claude/<model> format
- Record the model used in manifest.yaml per session
- Ensure backward compatibility with existing manifests that used simple model names
