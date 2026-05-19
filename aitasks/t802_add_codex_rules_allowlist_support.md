---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitasks, codexcli]
implemented_with: codex/gpt5_5
created_at: 2026-05-19 16:17
updated_at: 2026-05-19 16:18
---

Codex CLI now supports command allow rules through `.rules` files, but aitasks still treated Codex as prompt-only in setup, helper allowlist audits, tests, and documentation. This caused Codex users to keep seeing approvals for trusted aitask helper scripts such as the skill profile resolver and renderer.

Update aitasks to install and audit Codex `.rules` allowlists alongside the existing Claude, Gemini, and OpenCode permission touchpoints. Correct the stale documentation and tests so future helper scripts include Codex runtime and seed rules coverage.
