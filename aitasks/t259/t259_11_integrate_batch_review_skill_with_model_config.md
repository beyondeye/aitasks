---
priority: low
effort: low
depends: [t259_10]
issue_type: feature
status: Ready
labels: [aitask_review]
created_at: 2026-02-26 18:45
updated_at: 2026-02-26 18:45
---

## Context

Depends on: t259_8 (batch review skill), t265 (model configuration infrastructure)

NOTE: Task details are not fully defined yet. Implementation will depend on the model configuration infrastructure created in t265 and related tasks. This task should be refined once t265 is implemented.

## Planned Scope

- Update .claude/skills/aitask-review-batched/SKILL.md to read model from project/profile config
- Add review_batch_model profile key that uses claude/<model> format
- Fall back to project default model if not specified
