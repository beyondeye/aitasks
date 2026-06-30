---
priority: medium
effort: medium
depends: [t1071_2, t1071_5]
issue_type: documentation
status: Ready
labels: [shadow, claudeskills]
anchor: 1071
created_at: 2026-06-30 11:16
updated_at: 2026-06-30 11:16
---

Add website documentation covering the t1071 capabilities. Depends on t1071_2 (learn
skill) and t1071_5 (shadow spawn-learner integration).

## Cover three things
1. **`/aitask-learn-skill`** — the standalone command: sources (tmux pane id, local file,
   URL, repo file/dir), the read-only incremental pane capture, multi-part selection, and
   generalization Q&A.
2. **Shadow → learner spawn integration** (t1071_5) — how the shadow spawns a dedicated
   learner agent pointed at the followed pane, staying advisory-only.
3. **Shadow diagnose-errors / troubleshooting** (t1071_1, already landed) — the
   `plan-diagnose-errors.md` capability: detect tool-call errors/retries on the followed
   agent's screen and offer to spin fix-tasks.

## Conventions (per repo doc rules)
- Document the **current skill source** (read `.claude/skills/aitask-learn-skill/` and
  `.claude/skills/aitask-shadow/`), NOT these plans, which may drift.
- Follow `aidocs/framework/documentation_conventions.md` (current-state-only; generic
  example project names; no "sister repo" terminology).
- If a new `website/content/docs/workflows/*.md` page is added, also add its bullet to the
  hand-curated `_index.md` grouping (the sidebar auto-builds but the index body does not).

## Verification
- `cd website && hugo build --gc --minify` succeeds.
- New/updated pages render and are linked from the relevant `_index.md`.
