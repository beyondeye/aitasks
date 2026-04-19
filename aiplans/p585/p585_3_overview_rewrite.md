---
Task: t585_3_overview_rewrite.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_1_landing_page_redesign.md, aitasks/t585/t585_2_concepts_section.md, aitasks/t585/t585_4_coherence_audit.md, aitasks/t585/t585_5_readme_revamp.md
Archived Sibling Plans: aiplans/archived/p585/p585_*_*.md
Worktree: aiwork/t585_3_overview_rewrite
Branch: aitask/t585_3_overview_rewrite
Base branch: main
---

# t585_3 — Rewrite docs/overview.md

## Context

Rewrite `website/content/docs/overview.md` to align with the new "agentic IDE in your terminal" positioning, reflect the framework's actual scope (codebrowser, monitor, brainstorm, verified scores, multi-agent), and remove all Conductor/Beads references. The new Overview links into the Concepts section (sibling t585_2) for conceptual deep-dives.

Parent context: `aiplans/p585_better_frawework_desc_in_website.md`. Read archived sibling plans (`aiplans/archived/p585/p585_1_*.md`, `p585_2_*.md`) for canonical positioning copy and the Concepts page list.

## Implementation Plan

### Step 1 — Trim and reframe intro sections

- **The Challenge:** keep the intent-transfer framing but tighten to ~5 lines. Anchor on "agentic IDE in your terminal" + intent transfer.
- **Core Philosophy:** keep "Light Spec" framing, ~5 lines. Remove the Speckit reference (line 17) — confirm with user during implementation if uncertain. The user has already approved removing Conductor/Beads everywhere; Speckit is in the same family of misleading external references.

### Step 2 — Replace "Key Features & Architecture" with the 6-theme structure

Use the same 6 themes as the landing page. Each theme: short intro (1 paragraph) + 2-4 bullets of concrete capabilities + a "See also" line linking into Concepts/Workflows/Skills.

1. **Agentic IDE in your terminal** — TUIs (Board, Code Browser, Monitor, Minimonitor, Brainstorm, Settings) in tmux; `ait ide` boot; `j` switcher.
   See also: `{{< relref "concepts/ide-model" >}}`, `{{< relref "workflows/tmux-ide" >}}`, `{{< relref "tuis" >}}`.

2. **Long-term memory for agents** — Archived tasks+plans queryable as context; Code Browser line annotations; `/aitask-explain` evolution mode.
   See also: `{{< relref "concepts/agent-memory" >}}`, `{{< relref "skills/aitask-explain" >}}`.

3. **Tight git coupling, AI-enhanced** — `./ait git` wrapper, separate task-data branch; PR import/close, issue tracker integration, contribute flow, changelog generation, AI-assisted reverts.
   See also: `{{< relref "concepts/git-branching-model" >}}`, `{{< relref "workflows/pr-workflow" >}}`, `{{< relref "workflows/issue-tracker" >}}`, `{{< relref "workflows/revert-changes" >}}`.

4. **Task decomposition & parallelism** — auto-explode complex tasks into child tasks; sibling context propagation via archived plans; git worktrees + atomic locking.
   See also: `{{< relref "concepts/parent-child" >}}`, `{{< relref "workflows/task-decomposition" >}}`, `{{< relref "workflows/parallel-development" >}}`.

5. **AI-enhanced code review** — review guides per language, batched reviews, QA workflow with test-coverage analysis.
   See also: `{{< relref "concepts/review-guides" >}}`, `{{< relref "workflows/code-review" >}}`, `{{< relref "workflows/qa-testing" >}}`.

6. **Multi-agent support with verified scores** — Claude Code, Gemini CLI, Codex CLI, OpenCode unified via the codeagent wrapper; per-model/per-operation scores from user feedback.
   See also: `{{< relref "concepts/agent-attribution" >}}`, `{{< relref "concepts/verified-scores" >}}`, `{{< relref "commands/codeagent" >}}`, `{{< relref "skills/verified-scores" >}}`.

### Step 3 — Remove Conductor/Beads references

- Delete `(Inspired by [Conductor](https://github.com/gemini-cli-extensions/conductor))` parenthetical (line 24).
- Delete `(The [Beads](https://github.com/steveyegge/beads) Evolution)` parenthetical (line 28).
- Reword the surrounding sentences so the bullets stand on their own.

### Step 4 — Add coverage for currently-missing items

These should be naturally covered by the 6-theme structure above:

- Codebrowser, Monitor, Brainstorm TUIs (theme 1)
- Verified scores (theme 6)
- Multi-agent crew model (theme 6)

### Step 5 — Keep closing bullets

- "Battle tested" — keep, trim to 1 line.
- "Fully customizable workflow" — keep, mention `/aitask-contribute` and link to `{{< relref "skills/aitask-contribute" >}}`.

### Step 6 — Update trailing nav link

Keep `**Next:** [Installation]({{< relref "installation" >}})` as-is.

## Critical Files

- `website/content/docs/overview.md` — full rewrite

## Existing Patterns to Reuse

- `relref` shortcode pattern: `docs/overview.md:43,49` (current usage to preserve).
- Section structure / line counts — keep ~80-120 lines after rewrite. Overview is a navigation-and-orientation page, not a tutorial.

## Style Rules

- Describe current state only — no "previously…" / "this used to be…" framing.
- Theme order and terminology MUST match the landing page (sibling t585_1, see `aiplans/archived/p585/p585_1_*.md`).
- Avoid duplicating skill/workflow content — link to canonical pages.

## Verification

1. `cd website && ./serve.sh` — site builds with no Hugo errors.
2. Open `http://localhost:1313/docs/overview/` — page renders cleanly.
3. Click each cross-reference into Concepts/Workflows/Skills — confirm they resolve. Concepts links may warn if t585_2 hasn't merged yet; that is expected.
4. `Grep -n "Conductor\|Beads" website/content/docs/overview.md` — zero matches.
5. (If Speckit was decided for removal): `Grep -n "Speckit\|spec-kit" website/content/docs/overview.md` — zero matches.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit overview doc using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_3`, push.
