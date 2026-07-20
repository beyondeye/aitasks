---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [shadow]
anchor: 1158
created_at: 2026-07-20 09:34
updated_at: 2026-07-20 09:34
---

Rename the shadow implementation-review effort tiers from
quick/basic/standard/deep to quick/**default**/**advanced**/deep, keeping the
old names as free-text aliases ("basic"/"legacy" → default, "standard"/"normal"
→ advanced); an unqualified "adversarial review" still routes to the
legacy-compatible Default tier, and the generic-ask chooser recommends
Advanced.

Remove the deterministic two-stage tier chooser that existed for
3-option-capped agents: a live tmux-driven Codex session (v0.144.6) verified
that `request_user_input` accepts 4 options per question (Codex renders an
extra auto-appended "None of the above" row), so the single 4-option chooser
works on every supported agent. Correct `.agents/skills/codex_tool_mapping.md`
accordingly (options limit lifted and dated; the 3-questions-per-call cap
retained as untested).

Document the tiered implementation review on the website shadow-agent page:
the four tiers with their pass structure and findings caps, the
blocking/follow-up disposition tags with blocking-first ordering, verdicts in
Advanced/Deep, cap-overflow disclosure, tier request phrases, and free-text
angle scoping.

Follow-up to t1158 (archived); also updates the t1168 live-check checklist to
the new tier names (committed separately on the data branch).
