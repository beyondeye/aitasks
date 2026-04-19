---
Task: t585_1_landing_page_redesign.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_2_concepts_section.md, aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_4_coherence_audit.md, aitasks/t585/t585_5_readme_revamp.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 11:52
---

# t585_1 — Landing Page Redesign (Verified Plan)

## Context

Reposition aitasks via the website landing page (`website/content/_index.md`) from the low-level "AI-powered task management for code agents" tagline to **"A full agentic IDE in your terminal."** The current 3 hero feature cards (File-Based Tasks, Code Agent Integration, Parallel Development) understate the framework's actual scope (tmux IDE, archived-task memory, git/PR/issue integration, multi-agent verified scores). Visual cadence to mirror `website/content/about/_index.md` (multi-section white/light/dark alternation + lead pull-quotes).

This is child 1 of parent t585. Existing plan at `aiplans/p585/p585_1_landing_page_redesign.md` was reviewed against the current codebase and confirmed sound — entering as a verified plan.

## Verification of Plan Assumptions (against current codebase)

- `website/content/_index.md:9` — current tagline matches the replacement target.
- All four shortcodes used (`blocks/cover`, `blocks/section`, `blocks/feature`, `blocks/lead`) are confirmed present in the existing `_index.md` and `about/_index.md`.
- `about/_index.md` confirmed as the visual cadence reference (white → lead light → white-row → dark → light → white-row).
- SCSS override files exist: `website/assets/scss/_variables_project.scss` and `_styles_project.scss`.
- All deep-dive `relref` targets exist as `.md` files: `docs/workflows/{task-decomposition,parallel-development,code-review,qa-testing}.md`, `docs/commands/codeagent.md`, `docs/skills/verified-scores.md`, `docs/installation/_index.md`.
- `website/content/docs/concepts/` directory exists but is empty — sibling t585_2 will populate. `relref` to `concepts/*` will warn (acceptable transient state per plan).
- No `Conductor`/`Beads` references in `_index.md` (those are in `about/_index.md`, intentionally untouched).
- Existing `relref` style across the codebase uses `/docs/...` (leading slash, absolute) form — adopt this rather than `docs/...` for consistency with `tuis/_index.md`, `minimonitor/how-to.md`, etc.

## Critical Files

- `website/content/_index.md` — full redesign (only required edit)
- `website/assets/scss/_variables_project.scss` — *only if* a small visual override is needed (skip if Docsy stock styling looks fine)

## Implementation Steps

### Step 1 — Cover/hero block

Replace the existing `blocks/cover` block:
- Tagline: `<p class="lead mt-2">A full agentic IDE in your terminal.</p>`
- Subtagline (new line below lead): `<p>Kanban board, code browser, agent monitoring, and AI-enhanced workflows — all in tmux.</p>`
- Keep the logo image and the "Documentation" CTA.
- Replace GitHub button text with `⭐ Star on GitHub to support us!` (unicode star, same href `https://github.com/beyondeye/aitasks`).

### Step 2 — 3 hero highlights row

Replace the current `blocks/section type="row"` (3 features) with:

1. `fa-terminal` — **Agentic IDE in your terminal** — Kanban Board + Code Browser + Monitor + Brainstorm + Settings, all in one tmux session via `ait ide`. Press `j` to hop between TUIs without leaving the terminal.
2. `fa-brain` — **Long-term memory for agents** — Archived tasks and plans serve as queryable context. The Code Browser annotates each line back to the task and plan that introduced it.
3. `fa-code-branch` — **Tight git coupling, AI-enhanced** — PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.

### Step 3 — Deep-dive sections

Add three `blocks/section` blocks alternating `color="white"` / `color="light"`. Each gets a heading, 1 short paragraph, and a 3–4 bullet list of concrete capabilities. Optional `blocks/lead` pull-quote between sections for rhythm.

- **Task decomposition & parallelism** — auto-explode complex tasks into child tasks; sibling context propagation; git worktrees + atomic locks for parallel agent work. Links: `{{< relref "/docs/workflows/task-decomposition" >}}`, `{{< relref "/docs/workflows/parallel-development" >}}`.
- **AI-enhanced code review** — review guides per language, batched reviews, QA workflow, code explanations with task traceability. Links: `{{< relref "/docs/workflows/code-review" >}}`, `{{< relref "/docs/workflows/qa-testing" >}}`.
- **Multi-agent support with verified scores** — Claude Code, Gemini CLI, Codex CLI, OpenCode unified via the codeagent wrapper; per-model/per-operation scores accumulated from user feedback. Links: `{{< relref "/docs/commands/codeagent" >}}`, `{{< relref "/docs/skills/verified-scores" >}}`.

Cross-link to Concepts pages (`{{< relref "/docs/concepts/ide-model" >}}`, `concepts/agent-memory`, `concepts/git-branching-model`) wherever natural — Hugo will warn until t585_2 lands; acceptable.

### Step 4 — Platform-support strip

`blocks/section type="row"` with 5 small `blocks/feature` items (icons: `fa-linux`, `fa-ubuntu`, `fa-fedora`, `fa-apple`, `fa-windows`; fall back to `fa-desktop` if any are unavailable in Docsy's FontAwesome set). One-word body each. Section header links to `{{< relref "/docs/installation" >}}`.

### Step 5 — Reposition existing trailing sections

User decision: **move Quick Install higher**, keep Latest Releases at the bottom.

Final section order (top → bottom):

1. Hero cover
2. 3 hero highlights row (Step 2)
3. **Quick Install** (light) — moved up so newcomers see the install snippet right after the hero highlights, before the deeper sections. Content unchanged.
4. Deep-dive: Task decomposition & parallelism (white)
5. Optional `blocks/lead` pull-quote (light)
6. Deep-dive: AI-enhanced code review (light)
7. Deep-dive: Multi-agent support with verified scores (white)
8. Platform-support strip (Step 4)
9. **Latest Releases** (dark) — kept at the bottom; content unchanged.

Watch for color-cadence transitions when reordering — keep alternation natural (white→light→white→light→white→white-row→dark is fine; avoid two `dark` blocks in a row).

### Step 6 — Visual modernization (optional, minimal)

Only add custom CSS if a stock Docsy block looks visibly weak after the rewrite. Likely targets: bigger hero h1, accent color on hero CTA buttons. Use `_variables_project.scss` first; do NOT introduce a new shortcode.

## Verification

1. `cd website && ./serve.sh` — site builds, no Hugo errors (only acceptable warnings: `concepts/*` relref misses).
2. Open `http://localhost:1313/` — visually confirm hero, 3 hero cards, deep-dive sections, platform strip, "⭐ Star on GitHub to support us!" CTA.
3. Resize to mobile viewport (≤768px) — cards stack vertically, remain readable.
4. `Grep -n "Conductor\|Beads" website/content/_index.md` — zero matches.
5. Click each deep-dive link into existing pages (`workflows/`, `skills/`, `commands/`) — should resolve. `concepts/*` warnings are expected.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit code (`website/content/_index.md`, optional SCSS) using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_1`, push.

## Notes for Sibling Tasks

- Concepts pages referenced from this landing page (in Step 3): `ide-model`, `agent-memory`, `git-branching-model`. Sibling t585_2 should ensure those slugs exist, OR coordinate with this task to use slugs the t585_2 plan already commits to.
- `relref` style adopted: absolute `/docs/...` (matches existing codebase pattern).
- About page (`about/_index.md`) still references Conductor/Beads — that text is intentionally outside this task's scope; the user will decide separately whether to revise.
- **Docsy `blocks/feature` icon gotcha:** the shortcode auto-prepends `fas ` (solid) unless the icon string already starts with `fas ` or `fab `. **Brand icons** (`fa-linux`, `fa-apple`, `fa-windows`, `fa-github`, etc.) **must be passed as `fab fa-...`** — passing them as `fa-...` alone produces a broken-glyph rectangle. Sibling tasks editing other pages with brand icons should follow the same convention.

## Final Implementation Notes

- **Actual work done:** `website/content/_index.md` rewritten end-to-end. New section order: hero (with revised tagline + ⭐ Star CTA) → 3 hero highlights row → Quick Install (light, moved up per user) → Task decomposition (white) → lead pull-quote (light) → Code review (white) → Multi-agent (light) → 3-platform strip (white) → Latest Releases (dark). No SCSS overrides were needed — Docsy stock styling looked fine after the rewrite.
- **Deviations from plan:**
  - Platform strip dropped from 5 features to 3 (Linux / macOS / Windows-via-WSL) per user post-review feedback.
  - Hero subtagline reworded to remove the "all in tmux" reference (tmux is now mentioned only inside the "Agentic IDE in your terminal" feature card).
  - `concepts/*` cross-links from Step 3 of the plan were intentionally **omitted** from the implementation — the plan said they would warn but build, but since concept slugs (`ide-model`, `agent-memory`, `git-branching-model`) are not yet committed by sibling t585_2, leaving them out keeps the build warning-free. Sibling t585_3 / t585_4 (the coherence audit) can revisit and add cross-links once concepts pages exist.
  - Step 6 visual-modernization SCSS tweaks were not needed — visual rhythm and emoji-decorated headings (`⚡ Quick Install`, `🧩 Task decomposition`, `🔍 AI-enhanced code review`, `🤖 Multi-agent support`, `📦 Latest Releases`) provided enough modernization on their own.
- **Issues encountered:**
  - **Brand-icon rendering bug:** initial implementation used `icon="fa-linux"` etc. for the platform strip, which rendered as broken-glyph rectangles. Root cause: Docsy's `blocks/feature` shortcode auto-prepends `fas ` (solid) unless the icon argument starts with `fas ` or `fab `. Fix: pass brand icons as `icon="fab fa-linux"` etc. — see the gotcha note in "Notes for Sibling Tasks" below.
- **Key decisions:**
  - Adopted absolute `/docs/...` form for `relref` (matches existing codebase pattern in `tuis/_index.md`, `minimonitor/how-to.md`, etc.).
  - Each platform card got a `url=` so the strip doubles as installation-platform navigation.
  - Kept the "About" page reference to Conductor/Beads untouched — out of scope for this task; the user will decide separately.
- **Notes for sibling tasks:** see the "Notes for Sibling Tasks" section above (concepts slug coordination, `relref` style, Docsy `fab `-prefix gotcha, About-page Conductor/Beads cleanup).

## Post-Review Changes

### Change Request 1 (2026-04-19 12:01)
- **Requested by user:**
  1. Drop the "all in tmux" reference from the hero subtagline — keep tmux mentions confined to the "Agentic IDE in your terminal" feature card.
  2. Platform strip icons rendered as broken-glyph rectangles.
  3. Simplify the platform strip to just Linux / macOS / Windows (via WSL) instead of the original 5-platform layout.
- **Changes made:**
  1. Hero subtagline rewritten to `Kanban board, code browser, agent monitoring, and AI-enhanced git workflows.` (no tmux reference).
  2. **Root cause** — Docsy's `blocks/feature` shortcode auto-prepends `fas ` (solid) unless the icon argument already starts with `fas ` or `fab `. Brand icons must use the `fab ` prefix. Fixed by passing `icon="fab fa-linux"`, `icon="fab fa-apple"`, `icon="fab fa-windows"`.
  3. Platform strip collapsed from 5 features (Arch / Ubuntu / Fedora / macOS / WSL) to 3 (Linux / macOS / Windows-via-WSL). Each card links to the appropriate installation page (`docs/installation/` for Linux/macOS, `docs/installation/windows-wsl/` for Windows).
- **Files affected:** `website/content/_index.md`
