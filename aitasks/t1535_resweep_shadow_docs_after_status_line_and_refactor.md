---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1159
followup_kind: risk_mitigation
created_at: 2026-08-16 23:26
updated_at: 2026-08-16 23:26
---

## Origin

Risk-mitigation ("after") follow-up for t1159_4, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement: banner, keybinding and controller prose goes stale when t1159_6 adds the status line and t1159_7 refactors the loop.

From `aiplans/archived/p1159/p1159_4_docs_and_integration.md` `## Risk`:

- Documenting surfaces that t1159_6's status line and t1159_7's refactor will move · severity: low

## Goal

Re-sweep the shadow review-loop documentation once **t1159_6** (always-on concern/loop status line) and **t1159_7** (review-loop refactor) have landed, refreshing the prose t1159_4 pinned against the then-current source.

**This task is gated on both siblings — do not start it before they are Done.**

### What t1159_4 pinned that these siblings will move

- `website/content/docs/tuis/minimonitor/how-to.md` → `### How to Run the Auto-Recheck Loop` carries a **table of the four loop banner states quoted verbatim** (`⟳ auto-recheck ARMED`, `⟳ waiting for shadow to settle`, `⟳ auto-recheck: delivering…`, `⟳ recheck #N sent — waiting for shadow`). t1159_6 adds a **third always-on widget** beside `#mini-shadow-stale` and `#mini-loop-status`; decide whether the table still describes what a user sees, and whether the always-on line subsumes the transient banner.
- The same page's `_index.md` loop paragraph and the Key Bindings Quick Reference row for `L`.
- `aidocs/framework/shadow_agent.md` → `## Review-loop automation (auto-recheck)` is the **contract of record** (10 numbered points plus `5b`). Its preamble states that `review_loop.py`'s module docstring carries a **five-item digest** — keep that claim true if t1159_7 reshapes the docstring.
- `aidocs/framework/shadow_agent.md` → `### Spin-off triage arm` is back-linked from a comment in `monitor_shared.py._spawn_concern_tasks`, and both heading names are asserted by t1159_4's verification. Renaming either heading requires updating the comment.

### Verification

- Re-derive every quoted banner / toast / refusal string from its emitter; none may be a paraphrase.
- Capability matrix still matches the live registry:
  `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/monitor'); import review_loop as r; print(sorted(r.SHADOW_READY_DETECTORS), r.REVIEW_LOOP_AGENTS)"`
- Back-link headings still resolve (the check must **exit non-zero** on a miss, not merely print).
- `cd website && hugo build --gc --minify` succeeds.
