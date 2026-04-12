---
Task: t519_2_rewrite_terminal_setup_page.md
Parent Task: aitasks/t519_rewrite_of_website_for_tmux_integration.md
Sibling Tasks: aitasks/t519/t519_1_*.md, aitasks/t519/t519_3_*.md, aitasks/t519/t519_4_*.md, aitasks/t519/t519_5_*.md, aitasks/t519/t519_6_*.md
Archived Sibling Plans: aiplans/archived/p519/p519_1_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan — t519_2: Rewrite `installation/terminal-setup.md`

## Goal

Fully rewrite `website/content/docs/installation/terminal-setup.md` to:

1. Correct the mischaracterization of tmux as a terminal emulator.
2. Remove the Warp-centric "multi-tab terminal workflow" table.
3. Introduce the recommended workflow built around the new `ait ide` command from t519_1.
4. Preserve a minimal non-tmux fallback for users who can't use tmux.

## Dependencies

- **t519_1** must be complete. This page references `ait ide` by name. Check the archived plan `aiplans/archived/p519/p519_1_ait_ide_subcommand.md` for final command semantics before writing content.

## Step-by-step implementation

### Step 1 — Read current state

```bash
cat website/content/docs/installation/terminal-setup.md
```

Note:
- Existing front-matter (preserve title, weight, and any aliases — do NOT remove aliases).
- Existing H2 heading structure (any external links may point at anchors).
- Any existing `{{< ... >}}` shortcodes or internal links.

### Step 2 — Read archived t519_1 plan for `ait ide` specifics

```bash
cat aiplans/archived/p519/p519_1_*.md
```

Confirm:
- Exact command name (`ait ide`).
- Supported flags (`--session NAME`, `-h`/`--help`).
- Behavior in each environment (inside tmux matching / not matching / not in tmux session exists / not in tmux no session).
- Any "Final Implementation Notes" section with deviations.

### Step 3 — Rewrite the page

Full rewrite, preserving front-matter.

**Front-matter:**
- Keep `title:`, `weight:`, `description:` as they are (update `description:` if the new content changes the page's focus significantly).
- **Preserve** any existing `aliases:` — do not add or remove aliases.

**Body outline:**

#### H2: Terminal emulator vs. terminal multiplexer

Short section correcting the misconception. Key sentence:
> tmux is a terminal **multiplexer**. It runs inside a terminal emulator (like Ghostty, WezTerm, Alacritty, kitty, iTerm2, Konsole, or gnome-terminal) and divides your terminal window into multiple independent sessions, windows, and panes.

Mention explicitly that earlier versions of this documentation conflated the two, and this revision corrects that.

#### H2: Requirements

- **Terminal emulator** — any modern choice works (list examples without ranking: Ghostty, WezTerm, Alacritty, kitty, iTerm2, Konsole, gnome-terminal).
- **tmux** — version 3.x or newer. Required for the recommended workflow.
- **ait** — installed and `ait setup` already run in your project. Link to `installation/` index.

#### H2: Recommended workflow — `ait ide`

Headline section. Show:

````markdown
```bash
cd /path/to/your/project
ait ide
```
````

Explain what happens in 2–3 short paragraphs:

1. `ait ide` attaches to (or creates) a tmux session using the name from `aitasks/metadata/project_config.yaml` → `tmux.default_session` (default: `aitasks`). It always passes an explicit session name, so the session-rename fallback dialog in `ait monitor` never fires on the happy path.
2. A `monitor` window is created (or focused) inside the session, running `ait monitor`. From there you have a full dashboard of running code agents, open TUIs, and other panes.
3. The `j` key in any TUI opens the **TUI switcher** dialog, letting you jump between `ait board`, `ait monitor`, `ait minimonitor`, `ait codebrowser`, `ait settings`, and `ait brainstorm` without leaving tmux.

HTML comment placeholder (for the screenshot follow-up task):

```markdown
<!-- TODO screenshot: aitasks_ait_ide_startup.svg — the monitor dashboard immediately after running `ait ide` -->
```

**Do not** emit a `{{< static-img src="..." >}}` shortcode for the missing SVG — Hugo will warn/fail.

#### H2: Flags

Short reference of `ait ide` flags:
- `--session NAME` — use `NAME` instead of the configured default.
- `-h` / `--help` — show usage.

#### H2: Minimal / non-tmux workflow

Keep this short. For users who can't or won't use tmux:

1. Open your terminal emulator.
2. `cd` to your project.
3. Run individual `ait` commands directly: `ait board`, `ait monitor`, etc. Each opens a new UI in the current terminal.

State clearly that this path loses:
- The TUI switcher (`j` key).
- Persistent agent windows (agents terminate when you close their terminal).
- The unified monitor dashboard.

#### H2: Next steps

Bulleted link list:
- [Getting Started](/docs/getting-started/) — a 10-minute walkthrough.
- [The tmux IDE workflow](/docs/workflows/tmux-ide/) — end-to-end daily use.
- [Monitor TUI](/docs/tuis/monitor/) — full details of the monitor.

### Step 4 — What to delete from the current file

- The H2 section titled "Multi-Tab Terminal Workflow" and its table.
- Any line listing tmux alongside Ghostty/WezTerm/Warp as a terminal emulator.
- The Warp-centric discussion.
- The "Monitoring While Implementing" section if its content is now better served by `ait monitor` docs — replace with a single one-line link.

**Do NOT delete** any existing H2 headings that other pages might link to via anchors. If you need to restructure, keep the old anchor by adding a compatible H2 or note that the content moved.

### Step 5 — Verification

```bash
cd website && hugo --gc --minify
```

- No Hugo build errors.
- No broken-link warnings.
- No missing-image warnings.

```bash
cd website && ./serve.sh
```

- Navigate to `/docs/installation/terminal-setup/`.
- Spot-check:
  - No mention of tmux as a terminal emulator.
  - No Warp tab layout.
  - `ait ide` is the headline recommendation.
  - Links to `/docs/tuis/monitor/`, `/docs/getting-started/`, `/docs/workflows/tmux-ide/` exist (they may 404 until their creating siblings land — that's fine during solo dev).

### Step 6 — Final plan notes

Add Final Implementation Notes before archival:
- Summary of what was removed vs. added.
- Any existing headings that were preserved for anchor compatibility.
- Any deviations from the outline above.
- Notes useful for t519_3 (e.g., if you discovered the workflows page already had a stub).

## Files to modify

- `website/content/docs/installation/terminal-setup.md` (full rewrite, preserving front-matter).

## Out of scope

- Adding a separate page for `ait ide` beyond what's in `terminal-setup.md`.
- Documenting `ait monitor` internals (that's t519_4).
- Documenting the TUI switcher beyond a one-paragraph mention (that's t519_6).
- Capturing the SVG screenshot (follow-up task at parent archival time).
