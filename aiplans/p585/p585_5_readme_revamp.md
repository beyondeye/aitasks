---
Task: t585_5_readme_revamp.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_1_landing_page_redesign.md, aitasks/t585/t585_2_concepts_section.md, aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_4_coherence_audit.md
Archived Sibling Plans: aiplans/archived/p585/p585_*_*.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 16:19
---

# t585_5 — README.md Revamp (Verified Plan)

## Context

Update the project root `README.md` to mirror the new website positioning ("A full agentic IDE in your terminal"), restructure the feature highlights to match the website's 6 high-level themes, and remove all Conductor/Beads/Speckit references.

This is child 5 of parent task t585. Existing plan at `aiplans/p585/p585_5_readme_revamp.md` was reviewed against the current codebase — plan is largely sound but had two gaps:
1. **Speckit reference at line 32** was not called out (sibling t585_3 removed it from the overview; t585_4 confirmed zero matches across `website/content/`).
2. **Challenge/Core Philosophy sections** (lines 26-29, 31-34) were not explicitly scoped. User decision: keep both but tighten to 2-3 lines each and strip the Speckit reference.

## Verification of Plan Assumptions (against current codebase, 2026-04-19)

- `README.md:8` — tagline matches the replacement target.
- `README.md:20-23` — intro paragraph matches; leads with "AI code agents" and "kanban-style workflow" (to be reframed around agentic IDE).
- `README.md:24` — "Inspired by [Conductor]…, [beads]…" exactly as the plan documents.
- `README.md:26-29` — 🎯 The Challenge section. **Gap in original plan** — now scoped (see Step 4).
- `README.md:31-34` — 💡 Core Philosophy section, contains `(e.g., [Speckit](...))` parenthetical at line 32. **Gap in original plan** — now scoped (see Step 4, Step 5).
- `README.md:36-65` — Key Features & Architecture matches plan description. Line 37 "Repository-Centric (Inspired by Conductor)", Line 42 "The Beads Evolution", Line 63 "Claude Code optimized." all present.
- `README.md:67-160` — Platform Support / Quick Install / What Gets Installed / Documentation / License — all confirmed unchanged targets.
- Landing page `website/content/_index.md` uses the 6-theme terminology verified in t585_1: **Agentic IDE in your terminal** · **Long-term memory for agents** · **Tight git coupling, AI-enhanced** · **Task decomposition & parallelism** · **AI-enhanced code review** · **Multi-agent support with verified scores**. README will mirror exactly.
- Sibling t585_4 confirmed `Conductor|Beads|Speckit` are zero across `website/content/` — README is the last place these references live.
- Emoji section-header style (🎯 💡 🏗️ 🖥️ ⚡ 📦 📖 📄) already used in current README — preserve this style.

## Critical File

- `README.md` (repo root) — restructured (only required edit)

## Implementation Plan

### Step 1 — Update tagline (line 8)

Replace:
> *File-based task management for AI coding agents. No backend. Just markdown and git.*

With the landing-page canonical tagline:
> *A full agentic IDE in your terminal. File-based, git-native, multi-agent.*

### Step 2 — Update intro paragraph (lines 20-23)

Reframe around "agentic IDE in your terminal". Keep the supported-agents list ([Claude Code](...), [Gemini CLI](...), [Codex CLI](...), [OpenCode](...)) intact. Drop the "kanban-style workflow" framing — promote IDE positioning. The "Built for maximizing development speed 🚀 AND human-to-agent intent transfer efficiency 💬" line can stay (it is core positioning).

Draft:
> A full agentic IDE in your terminal — kanban board, code browser, agent monitoring, and AI-enhanced git workflows — integrated with AI code agents ([Claude Code](...), [Gemini CLI](...), [Codex CLI](...), [OpenCode](...)) via skills. Tasks are markdown files with YAML frontmatter stored in your repo alongside your code. No backend. No database. Just git.
>
> Built for maximizing development speed 🚀 AND human-to-agent intent transfer efficiency 💬.

### Step 3 — Remove line 24 (Conductor/Beads attribution)

Delete the "Inspired by [Conductor]…, [beads]…" line entirely. Do not replace.

### Step 4 — Tighten 🎯 The Challenge section (lines 26-29)

Trim to 2-3 lines. Current text is already close to good — preserve the intent-transfer framing, just tighten prose. Anchor explicitly on the "agentic IDE in your terminal" positioning so it connects to the new tagline.

Draft:
> ## 🎯 The Challenge
> AI coding agents are proficient enough to handle real development tasks. The bottleneck is **intent transfer** — getting structured, contextual instructions to the agent without the human becoming the slowdown. **aitasks** optimizes both the context the agent sees and the speed at which a human can steer it.

### Step 5 — Tighten 💡 Core Philosophy section (lines 31-34) and remove Speckit

Trim to 2-3 lines. Remove `(e.g., [Speckit](https://github.com/github/spec-kit))` entirely — keep the "rigid Spec-Driven Development" contrast without naming a specific external framework.

Draft:
> ## 💡 Core Philosophy
> "Light Spec" engine: unlike rigid Spec-Driven Development, tasks here are **living documents**.
> - **Raw Intent:** a task starts as a simple Markdown file capturing the goal.
> - **Iterative Refinement:** an AI workflow refines task files in stages — expanding context, adding technical details, and verifying requirements — before code is written.

### Step 6 — Restructure "🏗️ Key Features & Architecture" (lines 36-65) to the 6-theme block

Mirror the website's 6 themes. Each theme = 1-2 lines (README is shorter than the website overview). Use the exact canonical terminology.

```markdown
## 🏗️ Key Features & Architecture

- **🖥️ Agentic IDE in your terminal** — Board, Code Browser, Monitor, Brainstorm, and Settings TUIs in one tmux session via `ait ide`. Press `j` to hop between them.
- **🧠 Long-term memory for agents** — archived tasks and plans become queryable context; the Code Browser annotates each line back to the task/plan that introduced it.
- **🔀 Tight git coupling, AI-enhanced** — PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.
- **🧩 Task decomposition & parallelism** — auto-explode complex tasks into child tasks; sibling context propagates via archived plans; git worktrees + atomic locks for parallel agent work.
- **🔍 AI-enhanced code review** — per-language review guides, batched multi-file reviews producing follow-up tasks, QA workflow with test-coverage analysis.
- **🤖 Multi-agent support with verified scores** — unified `codeagent` wrapper over Claude Code / Gemini CLI / Codex CLI / OpenCode; per-model/per-operation scores accumulated from user feedback.
```

Keep the Dual-Mode CLI bullet immediately below the 6-theme block (it's a distinct value prop — interactive-for-humans vs batch-for-agents — and sibling t585_3 overview preserved it as its own bullet):

```markdown
- **Dual-Mode CLI** — Interactive mode for humans (optimized for flow, no context switching) and batch mode for agents (programmatic task/status updates).
```

Keep the closing bullets trimmed:
- **Battle tested** — actively developed and used in real projects. (drop the "Not a research experiment" framing)
- **Fully customizable workflow** — scripts and skills live in your project repo; modify them for your needs and contribute back via `/aitask-contribute`. ([Contribute workflow](https://aitasks.io/docs/workflows/contribute-and-manage/))

### Step 7 — Remove "Claude Code optimized." (line 63)

Multi-agent support is now first-class — folded into theme 6. Delete the standalone line.

### Step 8 — GitHub CTA refresh (optional, minor)

The README already uses GitHub badges at the top (stargazers / last-commit / issues) — keep those unchanged. If a prose CTA for "star the repo" is added elsewhere, use "⭐ Star on GitHub to support us!" (matching landing page wording, Unicode star). This is optional — only add if a natural spot presents during editing.

### Step 9 — Keep these sections unchanged

- 🖥️ Platform Support table (lines 67-75)
- ⚡ Quick Install (lines 77-115)
- 📦 What Gets Installed (lines 115-130)
- 📖 Documentation (lines 132-148)
- 📄 License (lines 150-160)

## Style Rules

- README is shorter than website overview — theme bullets stay to 1-2 lines each.
- Theme order and terminology MUST match the landing page (`website/content/_index.md`) and the overview (`website/content/docs/overview.md`).
- Emoji section-header style preserved: 🎯 💡 🏗️ 🖥️ ⚡ 📦 📖 📄.
- Current state only — no "previously…" / "this used to be…" framing.

## Verification

1. `Grep -n "Conductor\|Beads\|Speckit\|spec-kit" README.md` — **zero** matches.
2. Render the README with `glow README.md` (if available) or via the GitHub preview — structure, links, and tone match the website.
3. Confirm all relative links, badges, and image srcsets still resolve.
4. Cross-check theme order and terminology against `website/content/_index.md` (landing) and `website/content/docs/overview.md` (overview) — identical vocabulary in identical order.
5. Sanity-scan the Key Features section — exactly 6 theme bullets, each 1-2 lines.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit `README.md` using regular `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_5`, push. Parent task t585 will auto-archive after this child completes (it is the last child).

## Final Implementation Notes

- **Actual work done:** `README.md` restructured in-place (15 insertions / 35 deletions). Tagline (line 8) replaced with the landing-page canonical "A full agentic IDE in your terminal. File-based, git-native, multi-agent." Intro paragraph (line 20) reframed to lead with "A full agentic IDE in your terminal — kanban board, code browser, agent monitoring, and AI-enhanced git workflows" and retains the 4-agent supported-agents list. Conductor/Beads "Inspired by" line removed entirely. 🎯 The Challenge trimmed to one tight paragraph anchored on intent transfer. 💡 Core Philosophy trimmed to intro sentence + 2 bullets, Speckit reference removed. 🏗️ Key Features & Architecture replaced end-to-end with the 6-theme block mirroring the landing page (Agentic IDE / Long-term memory / Tight git coupling / Task decomposition / AI-enhanced code review / Multi-agent support with verified scores). Dual-Mode CLI preserved as a distinct bullet under the 6-theme block (per sibling t585_3 precedent). Battle tested + Fully customizable workflow closing bullets retained and trimmed. "Claude Code optimized." standalone line removed (folded into theme 6). Platform Support table, Quick Install, What Gets Installed, Documentation, License — all untouched.
- **Deviations from plan:** None. All 9 steps executed exactly as planned. Step 8 (GitHub CTA refresh) was no-op as expected — the README already uses badges for GitHub links, no prose CTA needed adjustment.
- **Issues encountered:** None. Conductor/Beads/Speckit grep returns zero matches. All relative links, image srcsets, and badges remain intact. Emoji section-header style preserved (🎯 💡 🏗️ 🖥️ ⚡ 📦 📖 📄).
- **Key decisions:**
  - Retained the 🏗️ section header from the original README and added theme-specific emojis (🖥️, 🧠, 🔀, 🧩, 🔍, 🤖) to each bullet label for visual rhythm, consistent with the landing page's emoji-decorated style.
  - Kept the "Built for maximizing development speed 🚀 AND human-to-agent intent transfer efficiency 💬" tagline below the intro paragraph — it's core positioning copy and survived sibling edits.
- **Notes for sibling tasks:** None — this is the last child of t585. Parent auto-archives after this task completes.
