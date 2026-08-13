---
priority: medium
effort: medium
depends: [1420]
issue_type: feature
status: Implementing
labels: [shadow, monitor, codex, opencode]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
created_at: 2026-08-10 08:42
updated_at: 2026-08-13 14:34
---

Extend the advisory workflow-phase signal after t1420 so native Codex and OpenCode prompts have phase-aware detection comparable to Claude. Inventory real current prompt surfaces and stable version variants; add narrowly scoped, ordered patterns only where wording is distinctive; keep framework-authored task-workflow checkpoint phrases as the shared cross-agent baseline; retain UNKNOWN and graceful degradation when a native prompt is unrecognized; do not alter existing awaiting_input_kind semantics unless compatibility impact is documented and tested. Verify Codex and OpenCode planning/review/merge prompts are classified when observable, unrelated confirmations do not receive a workflow phase, and every detected or wrong phase remains advisory-only and cannot block any shadow capability.
