---
Task: t585_3_overview_rewrite.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_4_coherence_audit.md, aitasks/t585/t585_5_readme_revamp.md
Archived Sibling Plans: aiplans/archived/p585/p585_1_landing_page_redesign.md, aiplans/archived/p585/p585_2_concepts_section.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 15:22
---

# t585_3 — Rewrite `website/content/docs/overview.md` (verified)

## Context

Rewrite `website/content/docs/overview.md` to align with the "agentic IDE in your terminal" positioning already shipped on the landing page (t585_1), cross-link into the new Concepts section (t585_2), and remove misleading external-framework references (Conductor/Beads/Speckit).

Existing plan at `aiplans/p585/p585_3_overview_rewrite.md` verified against the current codebase — the plan is sound and all assumptions still hold.

## Verification of Plan Assumptions (against current codebase, 2026-04-19)

- `website/content/docs/overview.md` is still the pre-rewrite version: `Speckit` (line 17), `Conductor` (line 24), `Beads` (line 28) references all present exactly as the plan documents.
- **All cross-link targets now exist** (sibling t585_2 shipped):
  - Concepts: `concepts/ide-model`, `concepts/agent-memory`, `concepts/git-branching-model`, `concepts/parent-child`, `concepts/review-guides`, `concepts/agent-attribution`, `concepts/verified-scores` ✓
  - Workflows: `workflows/tmux-ide`, `workflows/task-decomposition`, `workflows/parallel-development`, `workflows/code-review`, `workflows/qa-testing`, `workflows/pr-workflow`, `workflows/issue-tracker`, `workflows/revert-changes` ✓
  - Skills/Commands: `skills/aitask-explain`, `skills/aitask-contribute`, `skills/verified-scores`, `commands/codeagent`, `tuis` (section), `installation` (section) ✓
- `web_site` landing page (`website/content/_index.md`) uses the 6-theme terminology: **Agentic IDE in your terminal** · **Long-term memory for agents** · **Tight git coupling, AI-enhanced** · **Task decomposition & parallelism** · **AI-enhanced code review** · **Multi-agent support with verified scores** — will mirror exactly in the overview.
- **`relref` convention refinement:** the archived sibling plans (t585_1, t585_2) adopted **absolute** `/docs/<section>/<page>` form. The current overview uses bare/relative form (`tuis/board`, `installation`). Implementation will convert to absolute form for consistency with the rest of the new docs.

## Critical File

- `website/content/docs/overview.md` — full rewrite (only required edit)

## Implementation Steps

### Step 1 — Rewrite intro sections

- **The Challenge** — keep the intent-transfer framing, tighten. Anchor explicitly on the "agentic IDE in your terminal" positioning.
- **Core Philosophy** — keep the "Light Spec" framing, trim. Remove the `Speckit` external reference (same family of misleading refs as Conductor/Beads).

### Step 2 — Replace "Key Features & Architecture" with the 6-theme structure

Six themes, same order and terminology as the landing page. Each theme: short intro + 2–4 concrete-capability bullets + a "See also" line with `relref` links.

1. **Agentic IDE in your terminal** — Board · Code Browser · Monitor · Minimonitor · Brainstorm · Settings, all in tmux via `ait ide`; `j`-switcher.
   See also: `/docs/concepts/ide-model`, `/docs/workflows/tmux-ide`, `/docs/tuis`.
2. **Long-term memory for agents** — archived tasks+plans as queryable context; Code Browser line annotations; `/aitask-explain` evolution mode.
   See also: `/docs/concepts/agent-memory`, `/docs/skills/aitask-explain`.
3. **Tight git coupling, AI-enhanced** — `./ait git` wrapper + separate task-data branch; PR import/close; issue-tracker integration; contribute flow; changelog generation; AI-assisted reverts.
   See also: `/docs/concepts/git-branching-model`, `/docs/workflows/pr-workflow`, `/docs/workflows/issue-tracker`, `/docs/workflows/revert-changes`.
4. **Task decomposition & parallelism** — auto-explode complex tasks; sibling context propagation via archived plans; git worktrees + atomic locks.
   See also: `/docs/concepts/parent-child`, `/docs/workflows/task-decomposition`, `/docs/workflows/parallel-development`.
5. **AI-enhanced code review** — per-language review guides; batched reviews → follow-up tasks; QA workflow with test-coverage analysis.
   See also: `/docs/concepts/review-guides`, `/docs/workflows/code-review`, `/docs/workflows/qa-testing`.
6. **Multi-agent support with verified scores** — `codeagent` wrapper over Claude Code / Gemini CLI / Codex CLI / OpenCode; per-model/per-operation scores from user feedback.
   See also: `/docs/concepts/agent-attribution`, `/docs/concepts/verified-scores`, `/docs/commands/codeagent`, `/docs/skills/verified-scores`.

### Step 3 — Remove Conductor/Beads/Speckit references

- Delete the `(Inspired by [Conductor](...))` parenthetical (line 24 of the current file) and rewrite the surrounding bullet stand-alone.
- Delete the `(The [Beads](...) Evolution)` parenthetical (line 28) and rewrite the surrounding bullet stand-alone.
- Remove `(e.g., Speckit)` from the Core Philosophy section (line 17).

### Step 4 — Keep closing bullets, trim

- **Dual-Mode CLI** — keep explicitly as its own bullet (interactive-for-humans / batch-for-agents). Distinct value prop not subsumed by the 6 themes.
- **Battle tested** — keep, one line.
- **Fully customizable workflow** — keep, mention `/aitask-contribute` with `/docs/skills/aitask-contribute` relref.

### Step 5 — Trailing nav link

Keep `**Next:** [Installation]({{< relref "/docs/installation" >}})` (convert to absolute form).

## Style Rules

- Current state only — no "previously…" / "this used to be…" framing.
- Theme order and terminology MUST match the landing page.
- Absolute `{{< relref "/docs/..." >}}` form everywhere.
- Target length: ~80–120 lines. Overview is navigation + orientation, not a tutorial.

## Verification

1. `cd website && hugo --gc --minify` — strict build passes with no broken refs.
2. `cd website && ./serve.sh` — open `http://localhost:1313/docs/overview/` — page renders cleanly.
3. Click a sample of cross-reference links into Concepts/Workflows/Skills — all resolve.
4. `Grep -n "Conductor\|Beads\|Speckit" website/content/docs/overview.md` — zero matches.
5. Visual consistency check against the landing page — same 6 theme names, same order.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: user review → commit overview doc using `git`, commit updated plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_3`, push.
