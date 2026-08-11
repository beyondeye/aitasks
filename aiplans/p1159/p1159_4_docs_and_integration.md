---
Task: t1159_4_docs_and_integration.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_1_round_metadata_concern_block.md, aitasks/t1159/t1159_2_auto_recheck_loop.md, aitasks/t1159/t1159_3_spinoff_triage_arm.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
---

# Plan — t1159_4: Docs and integration sweep

Parent design: `aiplans/p1159_shadow_review_loop_automation.md`. Depends on t1159_2 and t1159_3. **Document the landed source, not the plans** — siblings may have deviated; re-derive keybindings, banner texts, and contracts from the code and the archived sibling plans' Final Implementation Notes.

## Steps

1. **`aidocs/framework/shadow_agent.md`** — consolidate the `## Review-loop automation` section (t1159_2 seeded at least the safety contract; place between "Feedback freshness" and "Concern rejection store"): controller states + edge-driven rationale, full 8-point safety contract (verify wording against the landed `review_loop.py`), round header + consumer roles, spin-off arm + `--producer spinoff` store interaction. Verify the "no new pane options" claim against the landed t1159_2 source before asserting it (the pane-option family table stays untouched only if that held).
2. **`concern-format.md`** — verify t1159_1's "Round header" section is complete and cross-linked; fix gaps only.
3. **Website** — locate the minimonitor page under `website/content/docs/` (check the tuis/workflows layout): document `L` (arm/disarm + banner states: armed / waiting for shadow / recheck #N sent), `t` (spin off as task, draft finalization via `ait create`), and the capability refusals (followed agent without prompt detection — t1467; unsupported shadow agent). If a new page is added under workflows, add its bullet to the **manual** `_index.md` list by hand.
4. **Cross-agent porting check**: the four concern producers are plain shared `.md` files. Confirm whether `.agents/skills/` and `.opencode/skills/` trees carry their own copies of the producer files; only if they do, suggest separate aitasks for the ports (per CLAUDE.md convention). Closure/`.j2` changes auto-render — cross-agent follow-ups are usually no-ops.
5. Follow `aidocs/framework/documentation_conventions.md`: current-state-only prose (no "previously the loop was manual…" version history), genericized agent references.

## Verification

- `cd website && hugo build --gc --minify` succeeds (skip with a note if the Hugo toolchain is absent).
- Doc claims cross-checked against landed source: keybindings (`L`, `t`), banner texts, safety-contract wording, pane-option table accuracy.
- Grep docs for stale descriptions of the manual-only recheck workflow and update them.
- Reference **Step 9 (Post-Implementation)** of the task-workflow skill for cleanup, archival, and merge.
