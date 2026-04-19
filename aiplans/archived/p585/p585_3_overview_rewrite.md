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

## Final Implementation Notes

- **Actual work done:** `website/content/docs/overview.md` rewritten end-to-end. Final file is 95 lines. Kept frontmatter (weight, description) intact. Retained the "The Challenge" and "Core Philosophy" framing from the original file but tightened them (Challenge condensed to one ~4-line paragraph anchored on "agentic IDE in your terminal"; Core Philosophy reduced to intro sentence + 2 bullets with the Speckit reference removed). Replaced the entire mid-section bullet list (`Repository-Centric` / `Daemon-less & Stateless` / `Remote-Ready` / `Dual-Mode CLI` / `Hierarchical Execution` / `Visual Management` / `Multi-Agent Support`) with the 6-theme "Key Features" block mirroring the landing page (t585_1) in both order and terminology. Closing bullets (Battle tested, Fully customizable workflow) kept and trimmed; the Dual-Mode CLI bullet was **preserved** (per user review mid-plan) as its own bullet under a new "Additional properties" section since it's a distinct value prop not subsumed by any of the 6 themes. All `relref` shortcodes converted to absolute `/docs/...` form to match t585_1 / t585_2 convention.
- **Deviations from plan:** (1) Added a small "Additional properties" section header to group Dual-Mode CLI + Battle tested + Fully customizable workflow — the plan said "keep closing bullets" without a section heading, but unheaded bullets after the 6-theme block felt orphaned, so a short section label was added for visual rhythm. (2) The plan's "Core Philosophy" step said to "trim to ~5 lines" — the final version is 4 lines (intro + 2 bullets) which still covers the Raw intent / Iterative refinement points.
- **Issues encountered:** None. Hugo strict build (`hugo --gc --minify`) passed on first try with 148 pages, 0 warnings, 0 broken refs. Conductor/Beads/Speckit grep returns zero matches.
- **Key decisions:**
  - Preserved Dual-Mode CLI as an explicit standalone bullet (user call during plan review). Not subsumed into any 6-theme because the dual-audience framing (humans + agents) is orthogonal to the themes.
  - Grouped remaining non-theme bullets under an "Additional properties" heading rather than leaving them floating.
  - Absolute `{{< relref "/docs/..." >}}` form used everywhere, including the trailing "Next: Installation" link.
  - Did NOT add `concepts/*` cross-links to the `See also` lines where concepts overlapped with workflows — always included the concepts link first (definitional), then the workflow link (how-to), then the skill/command link (entry point) where applicable.
- **Notes for sibling tasks:**
  - **t585_4 (coherence audit):** the overview now fully aligns with the landing page's 6-theme structure and terminology. Any remaining docs pages that still reference Conductor/Beads/Speckit or use the old 3-feature framing (Tasks-as-Files / Code Agent Integration / Parallel Development) should be brought in line. Particularly check `about/_index.md` (flagged by t585_1 as still containing Conductor/Beads references, intentionally out-of-scope for that task).
  - **t585_5 (README revamp):** use the same 6-theme structure + section ordering as the landing page and this overview. The top-level `README.md` in the repo root is the logical target.
  - **Absolute-relref convention now confirmed across 3 pages** (landing, concepts, overview). Sibling tasks should adopt without hesitation.
  - **"Additional properties" section label** is a minor deviation — sibling tasks should feel free to use or drop it; it's not an established pattern.
