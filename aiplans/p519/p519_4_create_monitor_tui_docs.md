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

Create a new `website/content/docs/tuis/monitor/` directory with three files (`_index.md`, `how-to.md`, `reference.md`) that fully document the `ait monitor` TUI — the orchestrator TUI of the ait tmux-based IDE workflow. There is currently ZERO documentation for this centerpiece TUI.

## Verification notes (from pre-implementation plan verification)

Sibling TUI docs at `website/content/docs/tuis/`:

| TUI | weight | title | linkTitle |
|-----|--------|-------|-----------|
| `board` | 10 | Kanban Board | Board |
| `codebrowser` | 20 | Code Browser | Code Browser |
| `settings` | 30 | Settings | Settings |

- No existing `monitor/` directory.
- Inner pages use `weight: 10` for how-to and `weight: 20` for reference (consistent).
- Shortcodes used: `{{< static-img src="imgs/aitasks_<tui>_<feature>.svg" alt="…" caption="…" >}}` for real screenshots; `<!-- SCREENSHOT: … -->` HTML comments for planned screenshots. Cross-links via `{{< relref "/docs/…" >}}`. Hugo docsy theme sorts by `weight` alone.
- `_index.md` structure uses a `## Tutorial` H2 with H3 subsections (Launching, Understanding layout, Navigating, …). `how-to.md` uses `### How to …` H3 sections. `reference.md` uses H3 sections with markdown tables.

Source-of-truth references (`.aitask-scripts/monitor/`):

- `monitor_app.py`
  - `BINDINGS` list at **lines 325–338** (12 bindings — see Step 4 table).
  - `Zone` enum at **lines 52–57** → `PANE_LIST`, `PREVIEW`.
  - `SessionRenameDialog` at **lines 118–182** (single block).
  - `_detect_tmux_session()` at **lines 1019–1032**; main() session-resolution logic at **lines 1049–1088**.
- `tmux_monitor.py`
  - `DEFAULT_TUI_NAMES` at **line 30**.
  - Pane classification in `discover_panes()` at **lines 99–107**.
- `lib/tui_switcher.py`
  - `KNOWN_TUIS` at **lines 59–65**: `board`, `monitor`, `codebrowser`, `settings`, `diffviewer`. Note: `brainstorm` is NOT a static entry — handled as a `brainstorm-*` prefix in `tmux_monitor.py`. `minimonitor` is a TUI via prefix/name.
- `aitask_ide.sh` — sibling t519_1 launcher, already archived. Takes `--session NAME`, resolves from `project_config.yaml → tmux.default_session` (default `"aitasks"`). Always passes an explicit session name, bypassing `SessionRenameDialog`.

Configuration (confirmed paths in `aitasks/metadata/project_config.yaml`):
- `tmux.default_session`, `tmux.default_split`, `tmux.prefer_tmux`, `tmux.git_tui`
- `tmux.monitor.refresh_seconds`, `tmux.monitor.idle_threshold_seconds`, `tmux.monitor.capture_lines`
- `tmux.monitor.agent_window_prefixes` (default `["agent-"]`)
- `tmux.monitor.tui_window_names` (default includes `board`, `codebrowser`, `settings`, `brainstorm`, `monitor`, `minimonitor`, `diffviewer`, `git`)

**Documentation policy:** per project memory (`project_diffviewer_brainstorm.md`), `diffviewer` must NOT be documented on the website even though it appears in the code-level TUI lists. Docs describe the config-driven classification rule without listing diffviewer by name.

## Step-by-step implementation

### Step 1 — Create directory

```bash
mkdir -p website/content/docs/tuis/monitor
```

### Step 2 — Write `_index.md` (weight: 15)

Weight `15` places monitor between `board` (10) and `codebrowser` (20) for prominent sidebar positioning without collisions.

Front-matter:

```yaml
---
title: "Monitor"
linkTitle: "Monitor"
description: "tmux pane monitor and orchestrator TUI — the dashboard of the ait tmux IDE"
weight: 15
---
```

Do NOT add `aliases:`.

Body outline (match `tuis/board/_index.md` conventions):

- Short intro paragraph: monitor is the dashboard of the ait tmux-based IDE — a single live view of all running code agents, open TUIs, and other tmux panes, with keystroke forwarding into the focused pane.
- `<!-- SCREENSHOT: aitasks_monitor_main_view.svg — monitor dashboard showing agents and TUIs -->`
- `## Tutorial`
  - `### Launching` — recommended path: `ait ide` starts/attaches to the configured tmux session and opens monitor in one step. Standalone: `ait monitor` from inside an existing tmux session. Link to how-to via `{{< relref "/docs/tuis/monitor/how-to" >}}` for details.
  - `### Understanding the layout` — two zones (pane list + preview). The pane list classifies tmux panes as **agents**, **TUIs**, or **others**. The preview panel shows the live content of the focused pane and forwards keystrokes directly into it.
  - `### Navigating` — `Tab` cycles zones; `Up`/`Down` move within the pane list; `Enter` in the preview sends an Enter keystroke.
  - `### Jumping between TUIs` — pressing `j` opens the TUI switcher overlay (list of known TUIs). Brief mention; deep dive in how-to and reference.
- `## See also` — links to `how-to.md` and `reference.md` via `{{< relref >}}`.

### Step 3 — Write `how-to.md` (weight: 10)

Front-matter:

```yaml
---
title: "How-to"
linkTitle: "How-to"
description: "Task-oriented guide for using ait monitor"
weight: 10
---
```

Body outline (H3 `### How to …` sections):

1. **How to start monitor**
   - Recommended: `ait ide` — it resolves the session name from config and avoids the rename dialog.
   - Standalone: from inside tmux, run `ait monitor`.
   - Mention that launching inside a tmux session whose name differs from `tmux.default_session` triggers the session-rename dialog; cross-link to reference for details.

2. **How to read the pane list**
   - Three groups: **agents** (running code agents), **TUIs** (board, monitor, minimonitor, codebrowser, settings, brainstorm), **others** (shells, logs, anything else).
   - Idle indicators highlight panes that haven't produced new output recently.
   - Classification is config-driven — see reference for exact rules.

3. **How to navigate**
   - `Tab` — cycle between pane list and preview zones.
   - `Up`/`Down` — move within the pane list.
   - `Enter` (preview zone) — send an Enter keystroke to the focused pane.
   - In the preview zone, other keystrokes are forwarded directly to the pane so you can interact with whatever is running in it.

4. **How to jump to another TUI**
   - Press `j` → TUI switcher dialog appears.
   - Pick a target from the list (board, monitor, minimonitor, codebrowser, settings, brainstorm). The switcher either selects an existing tmux window or creates a new one running that TUI.
   - `<!-- SCREENSHOT: aitasks_tui_switcher_dialog.svg -->`
   - Do NOT list `diffviewer` here (per project direction).

5. **How to refresh, zoom, and manage panes**
   - `r` (or `F5`) — refresh the pane list.
   - `z` — cycle preview size (zoom in/out on the preview panel).
   - `k` — kill the focused pane.
   - `s` — switch tmux to the focused pane.
   - `i` — show task info for the focused pane (if it's a code agent working on a task).
   - `n` — pick the next sibling task.
   - `a` — toggle auto-switch.

6. **How to quit**
   - `q` — quits monitor; the tmux window closes.

7. **How to handle a session-name mismatch**
   - What triggers it: running `ait monitor` in a tmux session whose name differs from `tmux.default_session` AND the configured session does not already exist.
   - What it does: `SessionRenameDialog` offers to rename the current session.
   - Recommended fix: use `ait ide` which always passes an explicit session name.

### Step 4 — Write `reference.md` (weight: 20)

Front-matter:

```yaml
---
title: "Reference"
linkTitle: "Reference"
description: "Complete reference for ait monitor keybindings and configuration"
weight: 20
---
```

Body outline (H3 sections + tables):

1. **Keyboard shortcuts**

   Complete table — verify against `monitor_app.py:325-338` while writing:

   | Key | Action | Scope |
   |-----|--------|-------|
   | `Tab` | Cycle zones | Global |
   | `Up` / `Down` | Navigate pane list | Pane list zone |
   | `Enter` | Send Enter keystroke to focused pane | Preview zone |
   | `j` | Open TUI switcher | Global |
   | `s` | Switch to focused pane | Pane list zone |
   | `i` | Show task info for focused pane | Pane list zone |
   | `r` / `F5` | Refresh pane list | Global |
   | `z` | Cycle preview size (zoom) | Global |
   | `k` | Kill focused pane | Pane list zone |
   | `n` | Pick next sibling task | Global |
   | `a` | Toggle auto-switch | Global |
   | `q` | Quit monitor | Global |

   In the preview zone, all non-bound keystrokes are forwarded to the focused tmux pane.

2. **Configuration**

   Settings from `aitasks/metadata/project_config.yaml`:

   - `tmux.default_session` — expected tmux session name; monitor refuses to rename if absent.
   - `tmux.default_split` — how new panes are split.
   - `tmux.prefer_tmux` — whether tmux-based workflows are the default.
   - `tmux.git_tui` — which git TUI (e.g., `lazygit`) the switcher opens.
   - `tmux.monitor.refresh_seconds` — pane-list refresh cadence.
   - `tmux.monitor.idle_threshold_seconds` — idle-marker threshold for the pane list.
   - `tmux.monitor.capture_lines` — preview capture depth.
   - `tmux.monitor.agent_window_prefixes` — window-name prefixes that mark a pane as an agent.
   - `tmux.monitor.tui_window_names` — window names classified as TUIs.

   All editable interactively via `{{< relref "/docs/tuis/settings" >}}` → Tmux tab.

3. **Pane classification**

   `discover_panes()` categorizes each tmux window:

   - **Agent** — window name starts with any prefix from `tmux.monitor.agent_window_prefixes` (default `agent-`).
   - **TUI** — window name is listed in `tmux.monitor.tui_window_names`, OR starts with `brainstorm-` (prefix-based special case for brainstorm workspaces).
   - **Other** — anything else (shells, logs, ad-hoc windows).

   Document the rule only; do not enumerate the default TUI name list verbatim and do not mention `diffviewer`.

4. **Session-name fallback dialog**

   - **When it fires:** the current tmux session name differs from `tmux.default_session`, AND the configured session does not already exist.
   - **What it does:** `SessionRenameDialog` offers to rename the current tmux session to the configured name.
   - **Avoid it:** use `ait ide`, which always passes an explicit session name.
   - **Manual workaround:** `tmux rename-session -t $OLD $NEW`.

### Step 5 — Verification

```bash
cd website && hugo --gc --minify
```

- Zero build errors or warnings (missing-image, broken `relref`, etc.).

```bash
cd website && ./serve.sh
```

- `/docs/tuis/monitor/`, `/docs/tuis/monitor/how-to/`, `/docs/tuis/monitor/reference/` all render.
- Sidebar places monitor between board and codebrowser (weight 15).
- HTML comment placeholders are NOT rendered as visible text.
- All internal `relref` links resolve (board/codebrowser/settings targets exist).
- No missing-image warnings (we don't add any live `{{< static-img >}}` without matching asset files).

### Step 6 — Final implementation notes

Append to this plan under "Final Implementation Notes" before archival, including:

- Final weight chosen (15).
- Any additional `BINDINGS` found in `monitor_app.py` beyond the 12 listed above.
- Any nuances in `SessionRenameDialog` or `_detect_tmux_session()` discovered while writing.
- Reusable conventions for sibling tasks:
  - **t519_5** (minimonitor): same three-file structure and shortcode conventions. Pick an adjacent weight (16 or 17).
  - **t519_6** (TUI switcher + footer label): exact relref paths for the new monitor pages: `/docs/tuis/monitor/`, `/docs/tuis/monitor/how-to/`, `/docs/tuis/monitor/reference/`.

## Files to create

- `website/content/docs/tuis/monitor/_index.md`
- `website/content/docs/tuis/monitor/how-to.md`
- `website/content/docs/tuis/monitor/reference.md`

## Out of scope

- Documenting `minimonitor` (t519_5).
- Documenting the TUI switcher itself (t519_6).
- Documenting `diffviewer` (explicitly excluded per project memory).
- Updating `tuis/_index.md` landing page prose to introduce monitor (t519_6).
- Capturing actual screenshots (follow-up task — HTML comment placeholders mark where they go).

## Final Implementation Notes

- **Actual work done:** Created three new files under `website/content/docs/tuis/monitor/`:
  - `_index.md` (75 lines) — Tutorial: Launching, Understanding the Layout, Navigating, Jumping to Another TUI.
  - `how-to.md` (157 lines) — 14 `### How to …` sections covering start/stop, pane list reading, zone navigation, preview-zone keystroke forwarding, send-enter shortcut, switch/kill/info/next-sibling agent actions, preview zoom, refresh, auto-switch, and session-name mismatch handling.
  - `reference.md` (164 lines) — Keyboard shortcuts (split into Zone Navigation / Pane Interaction / Monitor Controls), Zone Model, Pane Classification, Preview Size Presets (S/M/L with exact heights from `PREVIEW_SIZES`), full Configuration table, Command-line Options (`--session`, `--interval`, `--lines`), Session-Name Fallback Dialog decision logic (6 steps), Environment Variables, Related Commands and TUIs.
- **Weight chosen:** `15`. Rendered sidebar order (verified via generated HTML): board(10) → **monitor(15)** → codebrowser(20) → settings(30).
- **Deviations from plan:**
  - `_index.md` layout list changed from "four areas" to five: Header, Session bar, Pane list, Preview, Footer (the plan's outline missed the SessionBar widget — confirmed present via `monitor_app.py:373`).
  - `{{< relref "/docs/commands/ide" >}}` was changed to `{{< relref "/docs/workflows/tmux-ide" >}}` in three places because no dedicated `ait ide` command page exists yet; the tmux-ide workflow page (from sibling t519_3) is the canonical cross-reference for the ide launcher. If t519_6 or a later task creates `/docs/commands/ide`, these relrefs can be re-pointed.
- **Issues encountered:**
  - First Hugo build failed with three `REF_NOT_FOUND` errors for `/docs/commands/ide`. Fixed by retargeting the cross-references to `/docs/workflows/tmux-ide` (which exists).
- **Key decisions:**
  - Documented all 12 BINDINGS exhaustively in the reference — plan's initial outline only listed 5. Split the key table into three logical sub-tables (Zone Navigation, Pane Interaction, Monitor Controls) for readability.
  - Followed project memory `project_diffviewer_brainstorm.md` strictly: `diffviewer` is NOT mentioned in any of the three new pages, even though it is present in `DEFAULT_TUI_NAMES` and `KNOWN_TUIS`. The TUI classification rule is described without enumerating the default list.
  - `brainstorm-` prefix behavior is explicitly called out in both how-to (pane list section) and reference (Pane Classification), so readers understand that brainstorm workspaces match by prefix rather than by literal name.
  - Described the "Send Enter to a Blocked Agent" pattern as its own how-to section because it is a very common workflow pattern that deserves dedicated visibility (rather than being buried in the zone-navigation section).
- **Notes for sibling tasks:**
  - **t519_5 (minimonitor docs):** The three-file structure, shortcode conventions, and weight scheme used here are directly reusable. Pick weight `16` or `17` to place minimonitor adjacent to monitor in the sidebar. Copy the configuration table format from `reference.md`. Minimonitor shares the same pane-classification rules via `tmux_monitor.py`, so that entire section can be near-identically reproduced. The `j` TUI switcher shortcut is also present in minimonitor (via `TuiSwitcherMixin`), so the "How to Jump to Another TUI" section can be lifted almost verbatim.
  - **t519_6 (TUI switcher docs + footer label):** Exact relref paths for the new monitor pages:
    - `{{< relref "/docs/tuis/monitor" >}}` — overview
    - `{{< relref "/docs/tuis/monitor/how-to" >}}` — how-to guides
    - `{{< relref "/docs/tuis/monitor/reference" >}}` — reference
    Updating `tuis/_index.md` to introduce monitor in the landing-page prose is still pending and belongs to t519_6. The parent `tuis/_index.md` currently only describes board, codebrowser, and settings.
  - **`ait ide` command page:** There is no `/docs/commands/ide` page. All current mentions of `ait ide` in the docs (getting-started, workflows/tmux-ide, commands/_index) link to `workflows/tmux-ide` or `installation/terminal-setup`. If a later task creates a dedicated command reference page, update the three `relref` calls in `tuis/monitor/_index.md`, `tuis/monitor/reference.md` (×2) from `/docs/workflows/tmux-ide` to `/docs/commands/ide`.
- **Build verification:** `hugo --gc --minify` reports 124 pages, zero errors, zero warnings. HTML comment screenshot placeholders are stripped from the rendered HTML by the minifier (verified: `grep -c SCREENSHOT public/docs/tuis/monitor/*.html` returns 0). All internal `relref` links resolve.
