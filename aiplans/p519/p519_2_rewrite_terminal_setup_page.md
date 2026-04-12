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

## Post-Review Changes

### Change Request 1 (2026-04-12 16:30)

- **Requested by user:** "No need to refer to the previous version of documentation, just document what and how it works now." The first-pass rewrite included two retrospective phrases ("earlier versions of this page conflated the two…", "`ait ide` replaces the older four-step startup…") that described how the doc used to be wrong. The user wants the page to present the current state cleanly, without historical corrections.
- **Changes made:**
  - Rewrote the opening of the "Terminal emulator vs. terminal multiplexer" section. Removed "A quick terminology fix — earlier versions of this page conflated the two" and the closing paragraph "Previous revisions of this page listed tmux alongside Ghostty/WezTerm as an 'emulator choice' — that was wrong, and this page corrects it." Replaced with a positive framing: "Two distinct pieces of software cooperate when you use aitasks from the terminal: …" and a final short line "tmux is **not** a terminal emulator — it always runs inside one."
  - Rewrote the opening sentence of the "Recommended workflow — `ait ide`" section. Removed "`ait ide` replaces the older four-step startup (open terminal → cd → run tmux → run `ait monitor`) with one command". Replaced with a forward-facing framing: "`ait ide` is the headline entry point into the aitasks 'IDE' — a single command that opens tmux, creates the session, and launches `ait monitor` in one go."
  - Verified no other retrospective phrasing remained (grep for "earlier", "previous", "older", "formerly", "used to", "no longer" — clean).
  - Hugo build re-verified clean after edits.
- **Files affected:** `website/content/docs/installation/terminal-setup.md`

## Final Implementation Notes

- **Actual work done:** Full rewrite of `website/content/docs/installation/terminal-setup.md`. New structure: (1) front-matter updated — `title` from "Terminal Setup & Monitoring" to "Terminal Setup", `description` from "Multi-tab terminal workflow and monitoring during implementation" to "Terminal emulator choice, tmux, and the ait ide workflow"; (2) "Terminal emulator vs. terminal multiplexer" H2 correcting the terminology; (3) "Requirements" H2 listing modern emulators (Ghostty, WezTerm, Alacritty, kitty, iTerm2, Konsole, gnome-terminal) without ranking, tmux ≥ 3.x, and `ait setup`; (4) "Recommended workflow — `ait ide`" H2 with a fenced two-line bash block, three-point "under the hood" list explaining session resolution, monitor window creation, and the `j` TUI switcher; (5) H3 "Flags" covering `--session NAME` and `-h/--help` plus a paragraph on the inside-matching-tmux and inside-mismatching-tmux behaviors; (6) H3 "One gotcha: `ait ide` is one view of a shared session" explaining that tmux clients share a single session, with a two-project `--session` example; (7) "Minimal / non-tmux workflow" H2 listing the short fallback path and what it loses (TUI switcher, persistent agent windows, unified monitor dashboard); (8) "Next steps" H2 with links to `/docs/getting-started/`, `/docs/workflows/tmux-ide/`, `/docs/tuis/monitor/`. HTML comment screenshot placeholder included; no `{{< static-img >}}` shortcode added. Hugo build clean (119 pages, 0 errors) both before and after the Change Request 1 edits.
- **Deviations from plan:**
  - **Front-matter title/description updated.** The plan said "Keep existing front-matter (title, weight, etc.) but update the title if needed". I did update both `title` and `description` because the originals (`"Terminal Setup & Monitoring"`, `"Multi-tab terminal workflow and monitoring during implementation"`) directly referenced the removed content and would have been actively misleading. Sidebar `linkTitle` and `weight` were preserved unchanged.
  - **No `aliases:` to preserve.** The plan instructed me to preserve any `aliases:` field, but the original file had none. Worth noting in case a sibling task or future edit assumes otherwise.
  - **Added "One gotcha: ait ide is one view of a shared session" H3.** Not in the original section outline. t519_1's Final Implementation Notes explicitly flagged this as "the single biggest source of confusion" and asked t519_2/t519_3 to surface it prominently. I honoured that request with a dedicated H3 inside the recommended-workflow section — it contains a two-project `--session` example and points users at per-project `default_session` config.
  - **Removed "Context Monitoring" subsection referencing `claude-hud`.** The original page had a `### Context Monitoring` subsection under "Monitoring While Implementing" that recommended `claude-hud`. This is orthogonal to the tmux/multiplexer topic and does not belong on this page. It has been removed entirely — if the team wants `claude-hud` documented, a future task can add it to an "Ecosystem" or "Integrations" page.
  - **"Monitoring While Implementing" H2 fully removed**, not replaced with a one-line forward link. The plan said "replace with a brief one-line link to the monitor TUI docs", but the monitor TUI docs already appear in the "Next steps" link list at the bottom of the page, so a separate one-line pointer would be redundant. The "Next steps" list is sufficient.
  - **Change Request 1 (see Post-Review Changes above):** removed all retrospective references to earlier documentation versions after user feedback during Step 8 review. This is now a standing preference — recorded in the user's auto-memory system under `feedback_doc_forward_only.md` so future doc rewrites default to describing current state only.
- **Issues encountered:** None. Hugo build was clean on the first attempt and again after Change Request 1. Broken-link warnings for `/docs/workflows/tmux-ide/` and `/docs/tuis/monitor/` (the two pending-sibling targets) did not appear — Hugo does not emit build warnings for cross-page links that resolve as plain markdown relative paths when the target file is missing. Runtime 404s on those two links are expected until t519_3 and t519_4 land.
- **Key decisions:**
  - **Positive framing over historical correction.** Describe how things work now, not how they used to be wrong. Commit messages and PR descriptions carry the "this fixes the previous conflation" signal; the page itself should read as if it was always correct.
  - **`{{< static-img >}}` deliberately NOT used** for the screenshot placeholder. Hugo fails the build on missing static-img shortcodes. Used a plain HTML comment instead so the page builds cleanly until the screenshot follow-up task lands.
  - **Unranked emulator list.** Listed Ghostty, WezTerm, Alacritty, kitty, iTerm2, Konsole, gnome-terminal in a single sentence with "pick whatever you already use". No ranking, no recommendation — the aitasks workflow is emulator-agnostic so there is nothing to rank.
  - **Shared-session gotcha promoted to its own H3**, not a sidenote. Making it an H3 under "Recommended workflow — `ait ide`" guarantees it is scannable and linkable — anyone who sees parallel `ait ide` commands behaving strangely can be pointed directly at the anchor.
- **Notes for sibling tasks (t519_3 / t519_4 / t519_5 / t519_6):**
  - **User preference — describe current state only.** When rewriting or updating website docs on this task family, do not include phrases like "earlier versions said…", "previously we recommended…", or "this used to be wrong". State the current behavior positively. History belongs in git, not in the page body. See `feedback_doc_forward_only.md` in auto-memory.
  - **The shared-session gotcha is now at `/docs/installation/terminal-setup/#one-gotcha-ait-ide-is-one-view-of-a-shared-session`.** t519_3 (getting-started + workflows/tmux-ide) should link to this anchor rather than re-explaining the gotcha. One authoritative location.
  - **`claude-hud` / Context Monitoring content is homeless.** I removed the `### Context Monitoring` subsection from this page. If the team wants `claude-hud` documented, it needs a new home — a candidate is a future "Integrations" or "Ecosystem" page. Neither t519_3, t519_4, t519_5, nor t519_6 needs to pick this up; file it under "future task" if it matters.
  - **"Monitoring While Implementing" is gone.** The content has been replaced by the "Recommended workflow — `ait ide`" section plus the "Minimal / non-tmux workflow" fallback. If any other page on the website linked to `/docs/installation/terminal-setup/#monitoring-while-implementing` (anchor-link), that anchor no longer exists. Do a `grep -r "monitoring-while-implementing"` in `website/content/` during t519_3 to catch any broken incoming anchor-links.
  - **Flags section is authoritative for `ait ide` command documentation.** The commands reference page at `website/content/docs/commands/_index.md` intentionally just has a one-liner pointing here — do not duplicate the full `ait ide` docs elsewhere. If t519_3 adds a workflow page that needs to mention a flag, link to `/docs/installation/terminal-setup/#flags` rather than re-documenting.
  - **Screenshot placeholder is an HTML comment, not a `{{< static-img >}}` shortcode.** Keep this pattern for all pending-screenshot sibling tasks until the screenshots land — `{{< static-img >}}` with a missing file breaks the Hugo build.
  - **Emulator list is unranked.** If t519_3 or t519_4 reference terminal emulators, match this convention — no "recommended emulator" framing. The aitasks framework is emulator-agnostic by design.
