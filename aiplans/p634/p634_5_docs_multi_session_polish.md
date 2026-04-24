---
Task: t634_5_docs_multi_session_polish.md
Parent Task: aitasks/t634_multi_session_tmux_support.md
Archived Sibling Plans: aiplans/archived/p634/p634_1_discovery_and_focus_primitives.md, aiplans/archived/p634/p634_2_multi_session_monitor.md, aiplans/archived/p634/p634_3_two_level_tui_switcher.md, aiplans/archived/p634/p634_4_minimonitor_multi_session.md
Base branch: main
plan_verified: []
---

# p634_5 — Multi-session docs polish for monitor and minimonitor

## Context

Parent task **t634** taught `ait monitor` and `ait minimonitor` to aggregate running code agents across every aitasks tmux session on the box (not just the attached one), with a matching `M` runtime toggle in both TUIs. The implementation shipped in sibling tasks:

- **t634_2** — main monitor multi-session (`TmuxMonitor.multi_session=True` default, session-tag prefix on each row, `── session ──` divider rows, `M` binding). Added the initial "Multi-session view" subsection to `website/content/docs/tuis/monitor/reference.md`.
- **t634_4** — minimonitor multi-session (divider-only rendering, no inline tag prefix, `M` binding, `m`→full-monitor handoff does NOT implicitly toggle the main monitor's state).

The current docs describe only the main-monitor half of the story. The minimonitor page (`_index.md` + `how-to.md`) still reads "lists the code agents running in the current tmux session", the relationship table says minimonitor shows agents "in the current tmux session", and `M` is not in the minimonitor Key Bindings quick reference. This task refreshes the website docs so they describe the full cross-TUI multi-session story end-to-end — both TUIs, both `M` bindings, and the relevant handoff behavior.

**Per CLAUDE.md docs rule:** current-state only. No "previously single-session" callouts, no migration notes, no version history. State correct behavior positively.

## Scope of edits (4 files)

1. `website/content/docs/tuis/monitor/reference.md` — expand the existing "Multi-session view" section to cover both TUIs and the cross-TUI handoff.
2. `website/content/docs/tuis/minimonitor/_index.md` — update intro, purpose, and relationship table; add a short "Multi-session view" section.
3. `website/content/docs/tuis/minimonitor/how-to.md` — update "How to Read the Agent List"; add a "How to Toggle the Multi-Session View" section; add `M` to the Key Bindings Quick Reference table.
4. `website/content/docs/tuis/_index.md` — update the one-line monitor and minimonitor descriptions to reflect multi-session as the default.

No workflow docs need updating — `grep` over `website/content/docs/workflows/` for monitor/minimonitor references turned up only `manual-verification.md`, and its mentions are unrelated to session scoping.

## Implementation

### 1. `website/content/docs/tuis/monitor/reference.md`

Replace the existing `### Multi-session view` section (lines 74–92) with an expanded version that also covers the minimonitor counterpart. Keep the keybinding-table row for `M` (line 47) as-is — the anchor `#multi-session-view` still resolves correctly.

New section body (verbatim intent; final wording may be tweaked):

```markdown
### Multi-session view

By default both `ait monitor` and `ait minimonitor` aggregate every active code agent across every aitasks tmux session on this tmux server into a **single unified list**. Sessions are auto-discovered via:

1. The `AITASKS_PROJECT_<session>` tmux global environment variable (set by `ait ide` on startup).
2. Pane-cwd walk-up: any pane whose current working directory has an ancestor containing `aitasks/metadata/project_config.yaml`.

Press `M` inside either TUI to toggle the multi-session view ON/OFF for that TUI instance. The toggle is in-memory only and applies to the current TUI process; it is not persisted to configuration and is not shared with the other TUI (toggling `M` in the main monitor does not affect a running minimonitor, and vice versa).

**How each TUI renders the unified list:**

- **`ait monitor`** — agents from the same session are grouped by a `── <session_name> ──` divider row, and each agent row is prefixed with a short magenta `[project]` tag derived from the project-root basename. Title bar example: `tmux Monitor — 2 sessions · 5 panes · multi (attached: aitasks)`. Single-session title: `tmux Monitor — session: aitasks (5 panes)`.
- **`ait minimonitor`** — agents from the same session are grouped by a `── <session_name> ──` divider row; rows themselves stay in default color with no inline tag prefix (the narrow sidebar layout favors vertical scanning of names). Title bar example: `multi: 2s · 5a  1 idle`. Single-session title: `aitasks  5 agents  1 idle`.

**Cross-session focus from the main monitor:** pressing `Enter` on a pane from another session teleports the attached tmux client to that pane via `switch-client` + `select-window` + `select-pane`.

**Handoff between the two TUIs:** pressing `m` inside a minimonitor switches tmux focus to the main monitor window but does not alter the main monitor's `multi_session` flag. Each TUI's `M` toggle is independent — if you want both TUIs in the same mode, toggle each one.

If no second aitasks session exists on the tmux server, both TUIs' multi-session view is visually identical to the single-session view (one project, one session's worth of agents).
```

**Notes:**
- The opening "every pane in the current tmux session" wording in `reference.md`'s existing `### Pane Classification` block (line 64) describes classification rules, not scoping, and is still accurate — every window in every enumerated session is classified. No change needed there.
- The `M` keybindings-table row on line 47 already points to this section. No change to the table.

### 2. `website/content/docs/tuis/minimonitor/_index.md`

Three edits:

**a. Intro sentence (line 9)** — replace "lists the code agents running in the current tmux session" with cross-session phrasing:

> `ait minimonitor` is a narrow (~40 column) sidebar TUI that lists every running code agent across every aitasks tmux session on this tmux server, with idle indicators and a companion-pane focus model. It is the agents-only cousin of [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}): no preview panel, no TUI/other pane categories — just the running agents in a compact column designed to sit next to a code pane while you work.

**b. Purpose section (line 17)** — update "all running agents in the session" phrasing:

> Minimonitor is the persistent sidebar companion of a code agent pane. It gives you an at-a-glance status view of every running code agent across every aitasks tmux session on this server without giving up screen real estate to the full monitor dashboard, so you can keep watching the agent next to you (and all the others on the box) while you stay focused on the agent's output.

**c. Relationship to monitor table (lines 21–29)** — add a new "Multi-session view" row and tweak the "Shows agents" wording to be symmetric:

```markdown
| Aspect | `ait monitor` | `ait minimonitor` |
|--------|---------------|-------------------|
| Width | Full window | ~40 columns (configurable) |
| Shows agents | Yes, across all aitasks tmux sessions (default) | Yes, across all aitasks tmux sessions (default) |
| Shows TUIs and other panes | Yes | No |
| Preview zone with keystroke forwarding | Yes | No |
| Multi-session toggle | `M` (in-memory, per-TUI) | `M` (in-memory, per-TUI) |
| Session grouping | `── session ──` dividers + inline `[project]` tag on each row | `── session ──` dividers only |
| Intended placement | Its own tmux window | A side split inside an agent window |
| TUI switcher (`j`) | Yes | Yes |
```

**d. Link to multi-session reference** — after the relationship table and the existing short paragraph that follows it (around line 30), add one sentence:

> For the full cross-TUI multi-session story — auto-discovery, `M` toggle, rendering differences, and handoff behavior — see [Multi-session view]({{< relref "/docs/tuis/monitor/reference" >}}#multi-session-view) in the monitor reference.

### 3. `website/content/docs/tuis/minimonitor/how-to.md`

Three edits:

**a. "How to Read the Agent List" (lines 34–46)** — replace the first sentence so it reflects multi-session aggregation, and note the session dividers:

> Minimonitor shows a single scrollable list of **agent panes** (windows whose names match the configured agent prefix — default `agent-`). By default the list aggregates agents from every aitasks tmux session on the current tmux server; `── <session_name> ──` divider rows separate agents that belong to different sessions. TUIs, shells, and other panes are deliberately filtered out; for the full categorized view use [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}).

Also update the "session name and the running/idle count" sentence at the end of that section so it mentions the multi-mode title format:

> The header bar at the top of the pane shows either `multi: Ns · Ma N idle` in multi-session mode or `<session>  N agents N idle` when the view is restricted to the attached session.

**b. Add a new "How to Toggle the Multi-Session View" section** (inserted between the current "How to Refresh the Agent List" and "How to Quit" sections, lines 102–108):

```markdown
### How to Toggle the Multi-Session View

By default, minimonitor aggregates agents from every aitasks tmux session on the current tmux server. Press **M** (uppercase, Shift+m) to toggle to a single-session view that shows only the agents in the session this minimonitor is running in. Press **M** again to restore the aggregated view.

The toggle is in-memory only — it applies to the current minimonitor process and is not persisted to configuration. It is also independent of the main monitor's `M` toggle; switching modes in one TUI does not affect the other.

When multi-session is ON, agents are grouped by `── <session_name> ──` divider rows. The divider rows are display-only — they cannot be focused, and Up/Down navigation skips over them.

For the full cross-TUI story (auto-discovery, rendering details, cross-session focus from the main monitor), see [Multi-session view]({{< relref "/docs/tuis/monitor/reference" >}}#multi-session-view) in the monitor reference.
```

**c. Key Bindings Quick Reference table (lines 136–146)** — add an `M` row immediately after the `s` row (keeps related focus/switch keys adjacent; `M` is conceptually a mode toggle, grouped with `r` is also reasonable — placing after `s` matches the display order in the source footer hint `"m:full monitor  M:multi"`):

```markdown
| `M` | Toggle multi-session view ON/OFF |
```

Insert between the `s` row and the `i` row so it sits alongside session-related actions.

### 4. `website/content/docs/tuis/_index.md`

Small tweaks to the one-line descriptions at lines 16–17 so the default multi-session aggregation is not contradicted:

- **Monitor (line 16)** — replace "every pane in the current tmux session" with "every pane across every aitasks tmux session on the current tmux server":

  > **[Monitor](monitor/)** (`ait monitor`) — Dashboard of every pane across every aitasks tmux session on the current tmux server by default, categorized into code agents, TUIs, and other panes, with a live preview of the focused pane and keystroke forwarding. This is the home screen of the ait IDE.

- **Minimonitor (line 17)** — keep the essence but drop the implicit single-session framing:

  > **[Minimonitor](minimonitor/)** (`ait minimonitor`) — Narrow sidebar variant of monitor, designed to sit next to a code agent pane so you can watch every running agent (across every aitasks session) and launch follow-up work without giving up screen real estate.

**Do not** change the rest of `_index.md` — the existing "single tmux session per project" framing at line 12 is still accurate as the invariant, and the TUI switcher multi-session paragraph at line 34 is unrelated to monitor/minimonitor.

## Reuse / reference

- Existing "Multi-session view" section in `monitor/reference.md` (lines 74–92) — the new expanded version replaces it in place; most of the current text is retained and extended rather than rewritten.
- Archived sibling plan `aiplans/archived/p634/p634_2_multi_session_monitor.md` — canonical description of main-monitor behavior (rendering, title bar text, cache TTL).
- Archived sibling plan `aiplans/archived/p634/p634_4_minimonitor_multi_session.md` — canonical description of minimonitor rendering (divider-only), compact title bar format, and `m`→main-monitor handoff semantics.
- No code changes, no tests, no new config keys.

## Verification

```bash
cd website
hugo build --gc --minify
```

Checks:

1. Hugo build succeeds with no broken-link warnings. In particular, the `#multi-session-view` anchor is resolvable from `minimonitor/_index.md` and `minimonitor/how-to.md`.
2. `grep -rn 'single.session\|current tmux session' website/content/docs/tuis/minimonitor/` — confirm no lingering single-session-only phrasing on the minimonitor pages.
3. `grep -rn '^| .M. ' website/content/docs/tuis/minimonitor/how-to.md` — confirm the `M` row was added to the Key Bindings Quick Reference table.
4. Visual spot-check: `./serve.sh` (if Hugo is not running already), navigate to `/docs/tuis/monitor/reference/#multi-session-view` and `/docs/tuis/minimonitor/` and confirm content renders, tables align, cross-reference link resolves.

## Post-implementation

Standard workflow:

- **Step 8** — review `git status` / `git diff --stat`, commit the four changed docs files with subject `documentation: Polish multi-session docs for monitor and minimonitor (t634_5)`, commit the plan file separately via `./ait git`.
- **Step 8c** — manual-verification follow-up is not relevant here (docs-only change with nothing for a human to exercise in a TUI). Decline unless profile forces it.
- **Step 9** — archive t634_5. Parent t634 should auto-archive since this is the last pending child (t634_1, t634_2, t634_3, t634_4 already archived).
