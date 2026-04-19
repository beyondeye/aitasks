---
priority: medium
effort: medium
depends: [t585_4]
issue_type: documentation
status: Done
labels: [web_site, positioning]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 11:19
updated_at: 2026-04-19 16:24
completed_at: 2026-04-19 16:24
---

## Context

Update the project root `README.md` to mirror the new website positioning ("A full agentic IDE in your terminal"), restructure the feature highlights to match the website's 6 high-level themes, and remove all Conductor/Beads references.

This is child 5 of parent task t585. See parent plan `aiplans/p585_better_frawework_desc_in_website.md`. Read the **archived plan files** for completed siblings (`aiplans/archived/p585/p585_1_*.md`, `p585_3_*.md`) for the canonical positioning copy and 6-theme structure.

## Key Files to Modify

- `README.md` (repo root) — restructured

## Reference Files for Patterns

- Archived sibling plans `aiplans/archived/p585/p585_1_*.md` (landing page) and `p585_3_*.md` (overview rewrite) — the canonical positioning copy and theme structure to mirror
- Current `README.md` lines 36-65 — existing "Key Features & Architecture" structure being replaced
- Current `README.md` lines 67-75 — Platform Support table (keep unchanged)
- Current `README.md` lines 77-130 — Quick Install + What Gets Installed (keep unchanged)

## Implementation Plan

1. **Update tagline (line 8):**
   - Replace "*File-based task management for AI coding agents. No backend. Just markdown and git.*" with the new positioning: "*A full agentic IDE in your terminal. File-based, git-native, multi-agent.*" (or similar — match the wording used on the landing page).

2. **Update intro paragraph (lines 20-23):**
   - Reframe around "agentic IDE in your terminal" — keep mention of supported agents (Claude Code, Gemini CLI, Codex CLI, OpenCode), but lead with the IDE positioning rather than "kanban-style workflow".

3. **Remove "Inspired by Conductor, and beads" (line 24):**
   - Delete this line entirely. Do not replace with anything — README is shorter than the website overview.

4. **Restructure "Key Features & Architecture" (lines 36-65) to mirror the website's 6 themes:**
   - Agentic IDE in your terminal — TUIs (Board, Code Browser, Monitor, Brainstorm, Settings) in tmux, switchable with `j`.
   - Long-term memory for agents — archived tasks+plans queryable as context.
   - Tight git coupling, AI-enhanced — PR/issue/contribute/changelog/revert workflows.
   - Task decomposition & parallelism — child tasks, worktrees, atomic locking.
   - AI-enhanced code review — review guides, batched reviews, QA workflow.
   - Multi-agent support with verified scores — Claude Code, Gemini CLI, Codex CLI, OpenCode + per-model/per-operation scores.
   - Each theme: 1-2 lines (README is much shorter than the website overview).

5. **Remove "Claude Code optimized." (line 63):**
   - Multi-agent support is now first-class. Fold into the multi-agent theme.

6. **Remove the Beads bullet (line 42):**
   - "Daemon-less & Stateless (The Beads Evolution)…" → reword as a standalone bullet about the file-based, daemon-less architecture, no Beads reference.

7. **Remove the "Repository-Centric (Inspired by Conductor)" sub-bullets (lines 37-40):**
   - Reword "Tasks as Files" and "Self-Contained Metadata" without the Conductor reference, OR fold them into the new theme structure.

8. **Update GitHub references where applicable:**
   - Optional: rephrase any "GitHub" link text to "⭐ Star on GitHub to support us!" if it appears as a CTA. The README badges at top should remain.

9. **Keep these sections unchanged (they are accurate):**
   - Platform Support table
   - Quick Install
   - What Gets Installed
   - Documentation links
   - License

## Verification Steps

1. `Grep "Conductor\|Beads" README.md` — zero matches.
2. Render the README via `glow README.md` (if available) or visit GitHub preview — confirm structure, links, and tone match the website.
3. Confirm all relative links and badges still resolve.
4. Cross-check theme order and terminology against the latest landing page (`website/content/_index.md`) — should be identical.

## Step 9 (Post-Implementation)

Follow standard task-workflow Step 9: review → commit `README.md` using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_5`, push. The parent task t585 will auto-archive after this child completes (since it is the last child).
