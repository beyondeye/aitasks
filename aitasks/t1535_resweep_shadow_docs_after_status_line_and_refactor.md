---
priority: medium
effort: low
depends: [t1159_6, t1159_7]
issue_type: documentation
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1159
followup_kind: risk_mitigation
created_at: 2026-08-16 23:26
updated_at: 2026-08-16 23:27
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1687** id=2026-09-10T18:36:33Z.91aa4c2ea23a1c32e809416c from=t1687 at=2026-09-10T18:36:33Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names a related task,
> | not an agent working on it, so it is unverified. Advisory only — tree-relative
> | claims are dated by this note's base SHA; `~` line numbers are approximate.
> | 
> | Your anchors all still match as of this sweep: the banner table at
> | tuis/minimonitor/how-to.md ~260-271 (the four strings match their emitters in
> | minimonitor_app.py), the `L` Quick Reference row ~432, tuis/minimonitor/_index.md
> | ~83, aidocs/framework/shadow_agent.md `## Review-loop automation (auto-recheck)`
> | ~612 and `### Spin-off triage arm` ~1026.
> | 
> | Added since this task was created, and worth covering in the re-sweep: t1734's
> | `### The round header` and `### "Where this is heading"` inside the Review-loop
> | section (shadow_agent.md ~923, ~951), and t1771's shadow shortcodes (e16f9a27c).
> | 
> | t1687 (Concepts gap sweep) may write a shadow-agent concept page linking
> | workflows/shadow-agent, which you do not edit — no conflict.
