---
Task: t519_3_update_getting_started_and_add_workflow.md
Parent Task: aitasks/t519_rewrite_of_website_for_tmux_integration.md
Sibling Tasks: aitasks/t519/t519_1_*.md, aitasks/t519/t519_2_*.md, aitasks/t519/t519_4_*.md, aitasks/t519/t519_5_*.md, aitasks/t519/t519_6_*.md
Archived Sibling Plans: aiplans/archived/p519/p519_1_*.md, aiplans/archived/p519/p519_2_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan — t519_3: Update `getting-started.md` + add `workflows/tmux-ide.md`

## Goal

Two deliverables:

1. **Update** `website/content/docs/getting-started.md` so the recommended startup uses `ait ide` and mentions the TUI switcher.
2. **Create** a new `website/content/docs/workflows/tmux-ide.md` page that walks through the daily end-to-end developer workflow: from `ait ide` startup → pick a task → watch agent progress → review changes → commit.

## Dependencies

- **t519_1** (ait ide subcommand) — required. References `ait ide` by name.
- **t519_2** (terminal-setup rewrite) — this page links to the updated terminal-setup page. Auto-sibling deps ensure t519_2 lands first.

## Step-by-step implementation

### Step 1 — Read current state

```bash
cat website/content/docs/getting-started.md
cat website/content/docs/workflows/_index.md 2>/dev/null
ls website/content/docs/workflows/
```

- Note current `getting-started.md` structure (6 steps: install, settings, create task, view board, pick, iterate).
- Check `workflows/_index.md` for existing `weight:` values in child pages so the new `tmux-ide.md` picks a sensible weight.
- List any existing workflow pages to avoid name collisions.

### Step 2 — Read archived t519_1 and t519_2 plans

```bash
cat aiplans/archived/p519/p519_1_*.md
cat aiplans/archived/p519/p519_2_*.md
```

Pick up:
- Final `ait ide` command semantics.
- The new structure of `terminal-setup.md` (so cross-links resolve).
- Any conventions or naming decisions (e.g., screenshot filename format) to reuse.

### Step 3 — Update `getting-started.md`

**Preserve** front-matter, existing H2 anchors (external links!), and any unrelated content.

Revise the startup section (currently step 2 "Review settings via TUI") so the primary recommendation becomes:

```markdown
## 2. Start the ait IDE

From your terminal:

```bash
cd /path/to/your/project
ait ide
```

This attaches to (or creates) a tmux session and opens the **monitor** TUI — the dashboard for all your running code agents, open TUIs, and other tmux panes.

From any TUI, press **`j`** to open the **TUI switcher** and jump to the board, settings, codebrowser, brainstorm, or minimonitor. The switcher only works inside tmux — if you can't use tmux, see the [minimal / non-tmux workflow](/docs/installation/terminal-setup/) for the fallback path.
```

Then adjust the later steps so they assume the user is already inside the tmux session and reaches other TUIs via the switcher (instead of opening new terminals):

- Step 3 (current: "Create first task") — unchanged in content, but mention that running `ait` commands from inside the tmux session is the expected context.
- Step 4 (current: "View tasks on Board") — tell the user to press `j` in monitor and select `board`, instead of running `ait board` in a separate terminal.
- Step 5 (current: "Pick and implement task") — slight rewording to note that the picked agent appears in the monitor dashboard.

Add an end-of-page link:
```markdown
For the full end-to-end daily workflow, see [The tmux IDE workflow](/docs/workflows/tmux-ide/).
```

### Step 4 — Create `website/content/docs/workflows/tmux-ide.md`

**Front-matter:**

```yaml
---
title: "The tmux IDE workflow"
linkTitle: "tmux IDE workflow"
description: "Daily end-to-end developer workflow using ait ide, the monitor TUI, and the TUI switcher"
weight: <pick based on existing workflows/ siblings; if workflows/ is empty, start at 10>
---
```

**Do not** add `aliases:` unless you've verified they don't collide with existing aliases in the site.

**Body outline:**

#### H2: Intro

One paragraph: what this walkthrough covers — a day in the life of an ait user, from `ait ide` startup through picking a task, watching an agent, reviewing changes, and committing.

#### H2: Before you start

Bullet list of prerequisites:
- tmux 3.x or newer installed.
- `ait setup` has been run in your project.
- Code agents configured via `ait settings` → Code Agents tab.

Link to [Terminal Setup](/docs/installation/terminal-setup/) and [Getting Started](/docs/getting-started/).

#### H2: 1. Start the IDE

```bash
cd /path/to/your/project
ait ide
```

Describe what appears: the monitor dashboard with an agent list, a preview panel, and the TUI list.

HTML comment placeholder: `<!-- TODO screenshot: aitasks_monitor_main_view.svg -->`

#### H2: 2. Jump to the board with `j`

Describe pressing `j` → the TUI switcher dialog appears → select `board`.

HTML comment placeholder: `<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->`

#### H2: 3. Pick a task

Walk through picking a task. Verify the board's pick binding against the source (e.g., `.aitask-scripts/board/aitask_board.py`) — it may be `p` or an enter-on-selection or a command palette entry. Document whatever the actual binding is at the time of writing.

Explain that picking a task launches a code agent in a new tmux window.

#### H2: 4. Watch the agent run

Press `j` → select `monitor` — you return to the dashboard and the new agent appears in the agent list with an idle indicator.

Mention the alternative: press `j` → `minimonitor` for a narrow sidebar view.

#### H2: 5. Review the changes

When the agent finishes:
- Press `j` → `codebrowser` — browse the diff and approve or request changes.
- Approval flows through the standard review loop.

#### H2: 6. Commit and iterate

Briefly describe how `aitask-pick` handles commit and archival. Point to `/docs/skills/aitask-pick/` if that doc exists.

#### H2: Key bindings at a glance

Small table:

| Key | Action | Where |
|-----|--------|-------|
| `j` | Open TUI switcher | All main TUIs |
| `q` | Quit current TUI | All main TUIs |
| `Tab` | Cycle zones | Monitor |
| Up/Down | Navigate list | All main TUIs |

Adjust to match what's actually documented in the TUI pages.

### Step 5 — Cross-linking pass

Ensure:
- `getting-started.md` links to `/docs/workflows/tmux-ide/` — yes (added in Step 3).
- `workflows/tmux-ide.md` links to: `/docs/installation/terminal-setup/`, `/docs/tuis/monitor/`, `/docs/tuis/board/`, `/docs/tuis/codebrowser/`, `/docs/tuis/minimonitor/`.
- Any broken links will show up in `hugo --gc --minify` output.

### Step 6 — Verification

```bash
cd website && hugo --gc --minify
```

No build errors or missing-image errors. HTML comment placeholders don't trigger Hugo warnings; `{{< static-img >}}` shortcodes would, so make sure none were added.

```bash
cd website && ./serve.sh
```

- `/docs/getting-started/` renders correctly with the new step 2.
- `/docs/workflows/tmux-ide/` renders in the sidebar with the chosen weight.
- Cross-links work (monitor, board, codebrowser, minimonitor, terminal-setup, getting-started — some will 404 until t519_4/5/6 land, which is expected during development).

### Step 7 — Final plan notes

Add Final Implementation Notes before archival:
- The exact weight value chosen for `workflows/tmux-ide.md` and why.
- Any existing `getting-started.md` headings you preserved for anchor compatibility.
- Any deviations from the outline above (e.g., the board's actual pick binding if it's not `p`).
- Notes for t519_4/5/6: any cross-link targets you created that those children must match exactly.

## Files to modify

- `website/content/docs/getting-started.md` (update step 2 + later cross-links).
- `website/content/docs/workflows/tmux-ide.md` (new).

## Out of scope

- Creating the TUI-specific docs (t519_4 / t519_5).
- Updating `tuis/_index.md` (t519_6).
- Screenshots (follow-up task).

## Post-Review Changes

### Change Request 1 (2026-04-12 17:00)
- **Requested by user:** The first pass described the TUI switcher as a way to jump to `minimonitor`, and listed `minimonitor`/`brainstorm` as always-present destinations. That is wrong — `minimonitor` runs as a side panel inside code agent windows (spawned by `maybe_spawn_minimonitor` in `agent_launch_utils.py`) and is not an entry in the switcher's destination list. The switcher's main-TUI registry (`KNOWN_TUIS` in `.aitask-scripts/lib/tui_switcher.py`) is actually `board`, `monitor`, `codebrowser`, `settings`, `diffviewer` (+ optional `git` when configured). Brainstorm entries appear dynamically per running `brainstorm-<task>` session. Code agent windows appear grouped under a **Code Agents** section. The user wanted Step 4 of the new workflow page to describe switching to the agent's own tmux window via the switcher (where `minimonitor` is already visible as a side panel), not to a standalone `minimonitor` TUI.
- **Changes made:**
  - `website/content/docs/getting-started.md` — Step 2: switcher destination list updated to `ait board`, `ait monitor`, `ait codebrowser`, `ait settings`, `ait diffviewer` and "(or a running code agent window)". `minimonitor` / `brainstorm` removed from the primary list.
  - `website/content/docs/workflows/tmux-ide.md` — Step 2 description of the switcher dialog updated to list `board`, `monitor`, `codebrowser`, `settings`, `diffviewer` and to mention the Code Agents / brainstorm groups underneath. Step 4 rewritten: the second paragraph no longer proposes `j` → `minimonitor`. Instead it tells the user to press `j` again, pick the agent window from the **Code Agents** group, and explains that `ait minimonitor` runs automatically as a side panel inside that agent window. Key bindings table's `j` row scope updated to "Board, monitor, minimonitor, codebrowser, settings, brainstorm" (the TUIs where pressing `j` opens the switcher — `minimonitor` is included here because it mixes in `TuiSwitcherMixin` too, so `j` works from it even though it is not itself a destination). Added a short clarifying paragraph after the table explaining the switcher's three destination groups and stating explicitly that `minimonitor` is not a switcher destination.
  - Hugo build re-verified clean (120 pages, 0 errors) after edits.
- **Files affected:** `website/content/docs/getting-started.md`, `website/content/docs/workflows/tmux-ide.md`

### Change Request 2 (2026-04-12 17:05)
- **Requested by user:** Don't mention `diffviewer` in the list of TUIs reachable with `j`. The `diffviewer` TUI is being folded into brainstorm and should not be surfaced in user-facing docs.
- **Changes made:**
  - `website/content/docs/getting-started.md` — removed `ait diffviewer` from the step 2 switcher destination list.
  - `website/content/docs/workflows/tmux-ide.md` — removed `diffviewer` from the step 2 TUI list and from the clarifying paragraph below the key-bindings table. Hugo build clean (120 pages).
- **Files affected:** `website/content/docs/getting-started.md`, `website/content/docs/workflows/tmux-ide.md`

## Final Implementation Notes

- **Actual work done:**
  - `website/content/docs/getting-started.md` — rewrote step 2 from "Review Settings" to "Start the ait IDE", making `ait ide` + tmux the primary path. Renumbered the remaining sections: old-step-2 content moved to step 3 ("Review Settings", now reached via `j` → settings), old-step-3 moved to step 4 (ait create in a new tmux window), old-step-4 moved to step 5 (board via `j`). Step 5 "Pick and Implement a Task" became step 6 and picked up a lead-in that mentions the board's `p` pick binding and the new agent window appearing in `ait monitor`. Step 6 "Iterate" became step 7 and now mentions that the core loop runs inside a single `ait ide` tmux session with `j` as the one keystroke that moves between TUIs. The end-of-page bullet list now includes a link to `/docs/workflows/tmux-ide/` and the final `{{< relref >}}` footer was retargeted to `workflows/tmux-ide`.
  - `website/content/docs/workflows/tmux-ide.md` (new) — created end-to-end daily walkthrough with `weight: 5` (slotted above `capturing-ideas.md` at 10 because the tmux IDE workflow is the canonical entry point for daily use). Sections: intro, "Before you start" (tmux ≥3.x, `ait setup`, code agents configured), "1. Start the IDE", "2. Jump to the board with `j`", "3. Pick a task", "4. Watch the agent run", "5. Review the changes", "6. Commit and iterate", "Key bindings at a glance" table, and a "Related" links section. Two HTML-comment screenshot placeholders (monitor dashboard, TUI switcher dialog). No `{{< static-img >}}` shortcodes — kept the plan's convention to avoid breaking the build on missing SVGs.
  - Cross-links: getting-started → workflows/tmux-ide + installation/terminal-setup; workflows/tmux-ide → installation/terminal-setup (incl. the `#one-gotcha-ait-ide-is-one-view-of-a-shared-session` anchor), getting-started, tuis/monitor, tuis/board, tuis/codebrowser, tuis/settings. Cross-links to tuis/monitor/ intentionally 404 until t519_4 lands — expected during solo dev.
  - Hugo build verified clean (`hugo --gc --minify`) — went from 119 pages (pre-task) to 120 pages (post-task, the new workflow page is the single added entry). 0 errors, 0 broken-link warnings.

- **Deviations from plan:**
  - **Workflows weight chosen as `5`** (not the plan-suggested 10-if-empty). Existing workflow pages range from 10 (capturing-ideas) to 90 (revert-changes). The tmux IDE workflow is the "where daily work happens" page and should appear at the top of the sidebar; weight 5 places it above capturing-ideas without requiring any renumbering of existing siblings.
  - **Key bindings table expanded** beyond the plan's four rows. Added explicit rows for `p` (pick on board) and `Shift+arrows` (move task between columns), since the surrounding prose references both and readers scanning the table expect them.
  - **Change Request 1 (interactive correction):** first pass mistakenly described `minimonitor` and `brainstorm` as always-present TUI switcher destinations and proposed `j` → `minimonitor` in Step 4. Verification against `.aitask-scripts/lib/tui_switcher.py` revealed the actual `KNOWN_TUIS` registry is `board`, `monitor`, `codebrowser`, `settings`, `diffviewer` (+ optional `git`); brainstorm entries are dynamic per running session; code agent windows appear under a **Code Agents** group; `minimonitor` is a side panel spawned automatically inside agent windows via `maybe_spawn_minimonitor()` in `agent_launch_utils.py`. Rewrote the step-2 switcher lists and the step-4 "watch the agent run" paragraph accordingly — readers now press `j` → pick the agent window from **Code Agents** to get a live view of the agent + its minimonitor side panel.
  - **Change Request 2 (interactive correction):** Removed `diffviewer` from both the getting-started step-2 switcher list and the tmux-ide page's step-2 list + post-table clarifying paragraph. `diffviewer` is being folded into `brainstorm` per `project_diffviewer_brainstorm.md` auto-memory, so it must not appear in user-facing website docs.

- **Issues encountered:**
  - None blocking. The first pass contained the `minimonitor` / `brainstorm` factual errors noted above — caught at Step 8 review by the user and corrected in two short iterations. Verification against the actual `tui_switcher.py` source was the fix. No Hugo build or rendering issues at any point.

- **Key decisions:**
  - **Weight 5 for tmux-ide.md** — tmux IDE is the top-of-sidebar "daily use" workflow page.
  - **Press `j` from inside agent windows to return to the dashboard** (via the `Code Agents` group in the switcher) — better than documenting raw tmux shortcuts (`Ctrl-b <num>`, `prefix+n/p`) because it keeps the doc focused on the one shortcut (`j`) that is already the page's throughline.
  - **Every `ait` command in getting-started.md from step 3 onwards is framed as "inside the tmux session opened by `ait ide`"** — matches the new-as-of-t519_1 reality that `ait ide` is the recommended entry point and the rest of the docs should assume the tmux session is already running.
  - **Screenshots as HTML comments** — consistent with the `t519_2` convention (Hugo fails on missing `{{< static-img >}}` references, HTML comments are invisible at render time).
  - **diffviewer omitted from user-facing switcher lists** — matches the `project_diffviewer_brainstorm.md` auto-memory: diffviewer is transitional and should not appear in website docs even though it is technically in the `KNOWN_TUIS` registry.

- **Notes for sibling tasks (t519_4 / t519_5 / t519_6):**
  - **TUI switcher destination list (canonical)** — if any sibling documents the switcher, the accurate main-TUI list is `board`, `monitor`, `codebrowser`, `settings`. **Do not include `minimonitor` or `diffviewer` in user-facing docs.** `minimonitor` is a side panel, not a destination; `diffviewer` is being folded into brainstorm (auto-memory `project_diffviewer_brainstorm.md`). Dynamic groups that do appear in the switcher: **Code Agents** (any running `agent-*` window) and per-task brainstorm sessions. The optional `git` entry is configured via `tmux.git_tui` and only shows when set.
  - **`minimonitor` is spawned automatically** in every code agent tmux window by `maybe_spawn_minimonitor()` in `.aitask-scripts/lib/agent_launch_utils.py`. It runs as a right-hand split pane inside the agent's window, not as a top-level tmux window. Documentation for minimonitor (t519_5) should make this absolutely clear and should NOT describe it as "another TUI you launch" — it is a companion side panel that appears on its own when an agent window is created. Also document that pressing `j` inside the minimonitor pane does open the switcher (because `MiniMonitorApp` inherits `TuiSwitcherMixin`), but there is no way to switch *to* minimonitor — you always reach it by switching to the parent agent window.
  - **Shared-session gotcha anchor** — when any sibling needs to mention parallel IDEs, the canonical link is `/docs/installation/terminal-setup/#one-gotcha-ait-ide-is-one-view-of-a-shared-session`. Do not re-explain the gotcha inline; `getting-started` and this workflow page both just link to that anchor.
  - **Flags reference anchor** — the canonical `ait ide` flag reference lives at `/docs/installation/terminal-setup/#flags` (established by t519_2). t519_3 did not duplicate it — siblings should link there instead of documenting `--session NAME` / `--help` again.
  - **`getting-started.md` step numbering changed** from 6 → 7. External sites or other pages that linked to `#2-review-settings`, `#3-create-your-first-task`, etc., will now resolve differently (step 3 is still Review Settings but step 2 is now "Start the ait IDE"). Hugo slug generation from headings means the anchors update automatically; incoming links from within the website are all `{{< relref >}}` calls to full page URLs, not to fragment anchors, so nothing in the repo breaks. External inbound fragment links (e.g., from blog posts) would silently 404 — worth noting in any release notes for t519 but not actionable from this task.
  - **Workflow page weight 5** — t519_4/5/6 should not also claim weight 5. If those tasks add workflow pages, they should pick weights that slot around existing siblings (10 capturing-ideas, 15 retroactive-tracking, 20 task-decomposition, etc.). t519_4/5 are `tuis/*` pages not workflows, so this only matters if t519_6 (TUI switcher footer label + tuis/_index.md updates) decides to add a workflow entry.
  - **Forward-only documentation preference** — per Change Request 1's history-free framing (and the `feedback_doc_forward_only.md` feedback memory), the new page deliberately contains no phrases like "previously", "earlier versions", "used to be". It describes the current behavior positively. Sibling tasks should follow the same convention.
