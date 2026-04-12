---
priority: high
effort: medium
depends: [t519_1]
issue_type: documentation
status: Implementing
labels: [website, tmux, documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 15:14
updated_at: 2026-04-12 16:07
---

## Context

Part of t519 (website docs rewrite for tmux integration). The current `website/content/docs/installation/terminal-setup.md` is wrong in two important ways:

1. It lists tmux as a "terminal emulator" alongside Ghostty/WezTerm/Warp. tmux is a terminal **multiplexer** that runs **inside** a terminal emulator — it is NOT itself an emulator.
2. It describes a Warp-centric generic "multi-tab terminal workflow" with a table of tab layouts. This is no longer the recommended workflow — the new recommendation is a tmux-based session driven by `ait monitor`, and ideally launched via the new `ait ide` subcommand from t519_1.

This child task fully rewrites the page.

## Key Files to Modify

- `website/content/docs/installation/terminal-setup.md` — full rewrite.

## Reference Files for Patterns

- `website/content/docs/installation/_index.md` and `windows-wsl.md` — for tone, structure, and Docsy conventions.
- `website/content/docs/tuis/board/_index.md` — shows the `{{< static-img >}}` shortcode pattern (not used directly here — screenshots are deferred to follow-up task).
- t519_1 child plan (`aiplans/p519/p519_1_ait_ide_subcommand.md`) — for exact semantics and command-line flags of `ait ide`.

## Implementation Plan

Replace the existing content entirely. The new page should have roughly this outline:

### Front-matter

Keep existing front-matter (title, weight, etc.) but update the title if needed to better reflect the new content. Do NOT rename or remove existing `aliases:` — they may be externally linked.

### Section 1 — Terminal emulator vs. terminal multiplexer (correcting the misconception)

Short explanatory paragraph. Key line: "tmux is a terminal multiplexer. It runs inside a terminal emulator (like Ghostty, WezTerm, Alacritty, kitty, iTerm2, or gnome-terminal) and splits your single terminal window into multiple independent sessions, windows, and panes."

Explicitly acknowledge this corrects earlier documentation that conflated the two.

### Section 2 — Requirements

- Any modern terminal emulator. List examples (Ghostty, WezTerm, Alacritty, kitty, iTerm2, gnome-terminal, Konsole) without ranking them.
- tmux 3.x or newer (required for the recommended workflow).
- Platform-specific install hints (link to OS sections as needed; don't re-document).

### Section 3 — Recommended workflow: `ait ide`

This is the headline section. Describe the one-command startup:

```bash
cd /path/to/your/project
ait ide
```

Explain what happens:
- `ait ide` attaches to (or creates) a tmux session with the configured name (from `aitasks/metadata/project_config.yaml` → `tmux.default_session`).
- A `monitor` window is created (or focused) running `ait monitor`.
- From the monitor, the TUI switcher (`j`) jumps between board, monitor, minimonitor, codebrowser, settings, and brainstorm.
- Agents launched from the board run in their own tmux windows, visible and navigable from monitor.

Include a HTML comment placeholder: `<!-- TODO screenshot: aitasks_ait_ide_startup.svg — the initial monitor view after ait ide -->`. Do not emit a `{{< static-img >}}` shortcode for missing files (Hugo will warn).

Mention briefly that if tmux is started without a session name (i.e., not via `ait ide`), `ait monitor` falls back to offering a `SessionRenameDialog`. This is why `ait ide` is recommended.

### Section 4 — Minimal / non-tmux workflow

Keep a short section documenting the old path for users who can't or won't use tmux:
- Open your terminal.
- `cd` to the project.
- Run individual `ait` commands directly (`ait board`, `ait monitor`, etc.).

State clearly that without tmux, you lose the cross-TUI `j` switcher, the persistent session, and the agent-window navigation — so this is a fallback, not a recommendation.

### Section 5 — Next steps

Links:
- `/docs/tuis/monitor/` — the monitor TUI docs (created in t519_4).
- `/docs/getting-started/` — the getting-started walkthrough.
- `/docs/workflows/tmux-ide/` — the end-to-end workflow page (created in t519_3).

## What to remove

- The entire "Multi-Tab Terminal Workflow" section with its Warp-centric tab layout table.
- Any mention of Warp as a required or recommended tool.
- The line(s) listing tmux as a "terminal emulator".
- The "Monitoring While Implementing" section's generic content if it's superseded by `ait monitor` docs — replace with a brief one-line link to the new monitor docs.

## Verification

- `cd website && hugo --gc --minify` builds cleanly.
- `cd website && ./serve.sh` — navigate to `/docs/installation/terminal-setup/` and verify:
  - No mention of tmux as a terminal emulator.
  - No Warp-centric tab layout.
  - `ait ide` is the headline recommendation.
  - Links to `/docs/tuis/monitor/`, `/docs/getting-started/`, and `/docs/workflows/tmux-ide/` resolve (even if the target pages haven't been created yet in sibling tasks — they will be, and sibling auto-deps ensure this child runs after t519_3/t519_4).
- No broken internal links (Hugo reports these).

## Notes for sibling tasks

This rewrite assumes `ait ide` exists (from t519_1) — the doc references it by name. Do not merge this child before t519_1 lands.

## Step 9 — Post-Implementation

Part of t519 — follow the shared task-workflow post-implementation flow.
