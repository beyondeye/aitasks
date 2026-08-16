---
priority: medium
effort: low
depends: [t1159_2, t1159_3]
issue_type: documentation
status: Implementing
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
created_at: 2026-08-11 15:34
updated_at: 2026-08-16 10:58
---

Documentation and integration sweep for the shadow review-loop automation (t1159). Parent design: `aiplans/p1159_shadow_review_loop_automation.md`; child plan: `aiplans/p1159/p1159_4_docs_and_integration.md`. Depends on t1159_2 and t1159_3 (documents what they shipped — document the LANDED source, not the plans).

## Context

t1159_1..3 ship: the round metadata header (`Round: <N> @ <ts>` inside the concern fences, metadata-only blocks on clean reviews), the minimonitor auto-recheck loop (`L` key, `review_loop.py` controller, shadow-readiness detection, safety contract), and the picker spin-off arm (`t` key, draft creation with `--followup-of`/`--followup-kind review_finding`). This child consolidates user-facing and framework docs and suggests the cross-agent follow-ups.

## Key files to modify

- `aidocs/framework/shadow_agent.md` — new `## Review-loop automation` section (place between "Feedback freshness" and "Concern rejection store"): the controller states and edge-driven rationale, the FULL safety contract verbatim from the parent plan (8 points — including: the followed pane is never written; readiness is the three-part positive check, hash stability alone never sufficient; phase never gates firing), the round header and its consumer roles, the spin-off arm and its store interaction (`--producer spinoff`). No new pane options were introduced (loop state is in-process) — the pane-option family table stays untouched; verify that claim against the landed t1159_2 source before writing it.
- `.claude/skills/aitask-shadow/concern-format.md` — verify t1159_1's "Round header" section is complete and cross-linked; fix gaps only (t1159_1 owns the section).
- `website/content/docs/` minimonitor page (locate under docs/tuis/ or docs/workflows/ — check `website/content/docs/` layout): the `L` keybinding + banner states (armed / recheck #N sent / disarmed), the `t` triage key and draft finalization flow (`ait create`), the per-agent capability refusals (followed agent without prompt detection — t1467; unsupported shadow agent). Remember: the workflows `_index.md` bullet list is MANUAL — if a new page is added, add its bullet by hand.
- **`website/content/docs/tuis/monitor/how-to.md`** (added by **t1504**, the
  v0.31.0 docs-gap sweep, which deferred both shadow gaps to this child rather
  than writing prose this task would rewrite). The **full monitor** has its own
  concern-picker and auto-offer prose — "How to Pick Shadow Concerns" and the
  "Badge and auto-offer" callout — which needs the same round treatment as the
  minimonitor page: the `(round N)` toast suffix, and the fact that a **new
  round re-offers concerns you have already seen** (the dedup key is
  round-qualified, so a repeat round re-raising the same concerns is news, not
  noise). Most important: a block whose round header fails strict certification
  **warns and opens the raw block inspect view** rather than reporting a false
  "no concerns" all-clear — that is the single most misleading thing an
  undocumented round could cause, and it applies to both `c` paths.
- **`website/content/docs/workflows/shadow-agent.md`** (also from t1504): tie
  the round number to the re-derive-from-scratch behaviour that page already
  documents at "Every review round re-derives the shadow's findings from
  scratch" — the round header is what makes those rounds individually
  identifiable, and what the freshness key is built from (`(round,
  reviewed_at)` as a pair, never the round alone: a restarted shadow counts
  from 1 again).
- Cross-agent porting: per CLAUDE.md, suggest separate aitasks for Codex CLI (`.agents/skills/`) and OpenCode (`.opencode/skills/`) trees. The four concern producers are plain SHARED `.md` files consumed via the shared root, so this is likely a no-op — CONFIRM by checking whether those trees carry their own copies of the producer files, and only spawn follow-up tasks if they do.

## Reference

- Documentation conventions: `aidocs/framework/documentation_conventions.md` (current-state-only, no version history in doc bodies; genericize agent references).
- The parent plan's safety-contract text is the canonical wording to reproduce.

## Verification

- Docs build: `cd website && hugo build --gc --minify` succeeds (requires Hugo extended; skip with a note if the toolchain is absent).
- `shadow_agent.md` claims cross-checked against landed source (pane-option table accuracy; keybinding names; banner texts).
- No stale references: grep the docs for the pre-loop manual-only workflow description and update.
