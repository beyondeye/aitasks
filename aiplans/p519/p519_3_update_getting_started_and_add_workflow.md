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
