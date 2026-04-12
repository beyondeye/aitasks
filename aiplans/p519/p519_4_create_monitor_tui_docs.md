---
Task: t519_4_create_monitor_tui_docs.md
Parent Task: aitasks/t519_rewrite_of_website_for_tmux_integration.md
Sibling Tasks: aitasks/t519/t519_1_*.md, aitasks/t519/t519_2_*.md, aitasks/t519/t519_3_*.md, aitasks/t519/t519_5_*.md, aitasks/t519/t519_6_*.md
Archived Sibling Plans: aiplans/archived/p519/p519_1_*.md, aiplans/archived/p519/p519_2_*.md, aiplans/archived/p519/p519_3_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan — t519_4: Create `tuis/monitor/` docs

## Goal

Create a new `website/content/docs/tuis/monitor/` directory with three files (`_index.md`, `how-to.md`, `reference.md`) that fully document the `ait monitor` TUI. There is currently ZERO documentation for this centerpiece TUI.

## Step-by-step implementation

### Step 1 — Inspect existing TUI docs structure

```bash
ls website/content/docs/tuis/
ls website/content/docs/tuis/board/
cat website/content/docs/tuis/board/_index.md
cat website/content/docs/tuis/board/how-to.md
cat website/content/docs/tuis/board/reference.md
```

Note:
- Front-matter fields used (title, description, weight, aliases).
- H2 heading conventions.
- Shortcode usage (`{{< static-img >}}`, tables, code blocks).
- Existing `weight:` values in sibling `_index.md` files — pick a value for monitor that places it deliberately in the sidebar order.

### Step 2 — Read the source of truth

Read carefully:
- `.aitask-scripts/monitor/monitor_app.py` — especially:
  - Top of file for app class layout.
  - `BINDINGS` list for key bindings.
  - Lines 118–165, 402–435 for `SessionRenameDialog`.
  - Lines 1019–1074 for session-name resolution.
- `.aitask-scripts/monitor/tmux_monitor.py` — `discover_panes()` and pane classification logic.
- `.aitask-scripts/lib/tui_switcher.py` — the `j` key integration (monitor uses the mixin too).
- `.aitask-scripts/aitask_monitor.sh` — the launcher.

Build a mental model of exactly what the user sees and what each key does. Do NOT rely on the earlier exploration summary alone — the code is the source of truth.

### Step 3 — Create the directory

```bash
mkdir -p website/content/docs/tuis/monitor
```

### Step 4 — Write `_index.md`

Front-matter:

```yaml
---
title: "Monitor"
linkTitle: "Monitor"
description: "tmux pane monitor and orchestrator TUI"
weight: <pick deliberately; verify against board/codebrowser/settings weights>
---
```

**Do not** add `aliases:` unless you've verified uniqueness.

Body outline:

- **H2 Purpose** — what monitor is, why you want it. Key phrase: "the dashboard of the ait tmux-based IDE".
- **H2 When to use** — you're inside tmux and want a live overview of running code agents, open TUIs, and other panes.
- **H2 At a glance** — bullets:
  - Two-zone layout: session list + live preview.
  - Classifies tmux panes as agents, TUIs, or others.
  - Preview panel shows live content and forwards keystrokes to the pane.
  - `j` opens the TUI switcher (navigate to board, minimonitor, codebrowser, settings, brainstorm).
- HTML comment placeholder: `<!-- TODO screenshot: aitasks_monitor_main_view.svg -->`
- **H2 Next steps** — link to how-to and reference.

### Step 5 — Write `how-to.md`

Body outline:

1. **H2 Starting monitor**
   - Recommended: `ait ide` (creates/attaches to the session and opens monitor in one step).
   - Standalone: from inside tmux, run `ait monitor`.
   - Brief mention of the session-rename fallback dialog + link to the reference page for details.

2. **H2 Understanding the panels**
   - The session list zone (left/top) — shows agents, TUIs, and others with idle indicators.
   - The preview zone (right/main) — live view of the currently-selected pane. Verify layout against `monitor_app.py`.
   - Pane classification:
     - **Agents** — windows matching agent naming patterns (check `tmux_monitor.py` for exact regex).
     - **TUIs** — windows named `board`, `monitor`, `codebrowser`, `settings`, `brainstorm`, `minimonitor`. **Do not document diffviewer** per project direction.
     - **Others** — shells, logs, anything else.

3. **H2 Navigating**
   - `Tab` — cycle between session-list and preview zones.
   - `Up`/`Down` — move within the session list.
   - `Enter` (in preview) — send an Enter keystroke to the focused pane.
   - In preview, all other keystrokes are forwarded — you can interact with whatever is running in the pane.

4. **H2 Jumping to another TUI**
   - Press `j` → TUI switcher dialog appears.
   - Select any of: board, monitor, minimonitor, codebrowser, settings, brainstorm.
   - The switcher either selects an existing tmux window or creates a new one.
   - HTML comment placeholder: `<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->`

5. **H2 Session-name mismatch**
   - Short explanation: if you launched tmux without a session name (or with a mismatched one), monitor offers to rename the session to match the configured `default_session`.
   - Recommendation: use `ait ide` to avoid the dialog entirely.

6. **H2 Quitting**
   - `q` — quit.

### Step 6 — Write `reference.md`

Body outline:

1. **H2 Key bindings**

   Table format — cross-reference `monitor_app.py` `BINDINGS` list for completeness:

   | Key | Action | Scope |
   |-----|--------|-------|
   | `Tab` | Cycle zones | Global |
   | `Up` / `Down` | Navigate pane list | Session list zone |
   | `Enter` | Send Enter to focused pane | Preview zone |
   | `j` | Open TUI switcher | Global |
   | `q` | Quit monitor | Global |
   | (any others from BINDINGS) | ... | ... |

2. **H2 Configuration**

   Settings that affect monitor, from `aitasks/metadata/project_config.yaml`:
   - `tmux.default_session` — the session name monitor expects and uses.
   - `tmux.default_split` — how new panes are split.
   - `tmux.prefer_tmux` — whether tmux-based workflows are the default.
   - `tmux.git_tui` — which git TUI the switcher jumps to.

   Mention that these can be edited interactively via `ait settings` → Tmux tab.

3. **H2 Session-name fallback dialog**

   Describe `SessionRenameDialog`:
   - **When it fires:** the current tmux session name differs from the configured `default_session`, AND the configured session does not already exist.
   - **What it does:** offers to rename the current tmux session to the configured name.
   - **How to avoid it:** use `ait ide`, which always passes an explicit session name.
   - **Manual workaround:** `tmux rename-session -t $OLD $NEW`.

4. **H2 Pane classification rules**

   Describe briefly how `discover_panes()` categorizes panes. Verify against `tmux_monitor.py`:
   - Pattern-based window name matching for agents.
   - Known-TUI list for TUIs.
   - Everything else falls into "others".

   Keep this section short — link to the source file for exact logic.

### Step 7 — Verification

```bash
cd website && hugo --gc --minify
```

- No build errors.
- No broken internal links.
- No missing-image warnings.

```bash
cd website && ./serve.sh
```

- `/docs/tuis/monitor/` renders correctly.
- `/docs/tuis/monitor/how-to/` renders.
- `/docs/tuis/monitor/reference/` renders.
- Sidebar weight places monitor where expected.
- HTML comment placeholders are NOT rendered as visible text.
- All cross-links resolve (where target pages exist).

### Step 8 — Final plan notes

Add Final Implementation Notes before archival:
- The exact weight value chosen.
- Any BINDINGS discovered in `monitor_app.py` that weren't in the outline above.
- Any session-rename or pane-classification nuances discovered while reading the source.
- Notes for t519_5 (minimonitor shares conventions; point out reusable copy).
- Notes for t519_6 (the `tuis/_index.md` update must link to these new pages — give the exact URL paths).

## Files to create

- `website/content/docs/tuis/monitor/_index.md`
- `website/content/docs/tuis/monitor/how-to.md`
- `website/content/docs/tuis/monitor/reference.md`

## Out of scope

- Documenting minimonitor (t519_5).
- Documenting the TUI switcher itself (t519_6).
- Documenting diffviewer (explicitly excluded).
- Screenshots (follow-up task).
