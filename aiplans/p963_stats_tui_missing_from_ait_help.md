---
Task: t963_stats_tui_missing_from_ait_help.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Add `stats-tui` to the `ait` help TUI section (t963)

## Context

`ait stats-tui` is a fully-fledged TUI: it is dispatched in `ait` (line 195 →
`aitask_stats_tui.sh` → `stats/stats_app.py`), registered in
`.aitask-scripts/lib/tui_registry.py:22` as
`("stats", "Statistics", "ait stats-tui", True)`, and therefore appears in the
`j` TUI switcher modal. Yet it is **missing from the TUI section of `ait`
help** (`ait` lines 28-37). Only the non-TUI CLI reporter `ait stats` is shown,
under the **Reporting** section (line 54).

The help text is a hand-maintained heredoc in `show_usage()`; nothing links it
to `tui_registry.py`, so it drifted — `stats-tui` was added to the dispatcher
and registry but never to the help. The user noticed the omission and asked
why. The outcome: surface `stats-tui` in help, consistent with how every other
switcher TUI is listed.

## Approach

A single-line addition to the TUI section of `show_usage()` in `ait`. No
auto-generation, no website changes (the docs already cover it).

### Change: `ait` (TUI section, lines 28-37)

Insert a `stats-tui` line, kept alphabetically between `settings` and `syncer`,
matching the existing column alignment (description starts at column 18):

```
  settings       Launch the settings TUI
  stats-tui      Launch the statistics TUI
  syncer         Launch the remote-desync syncer TUI
```

The description ("Launch the statistics TUI") deliberately differs from the
Reporting entry `stats  Show task completion statistics`, so the TUI vs CLI
distinction is clear in the help.

## Rejected: auto-generating the help TUI list from `tui_registry.py`

The task description floated reconciling the help against the registry so they
can't drift again. **Rejected as out of scope**, for three reasons:

1. **The help is intentionally curated, not a registry mirror.** Lines 203-204
   of `ait` show `migrate-archives` is *deliberately* omitted from help (t918).
   The two surfaces legitimately diverge — e.g. `ide` is listed as a TUI in
   help but isn't a switcher TUI (it's a tmux/monitor launcher), and
   `diffviewer` is in help but CLAUDE.md keeps it out of *website* TUI lists.
   A 1:1 generator would fight these deliberate choices.
2. **Latency cost.** `show_usage()` is a pure bash heredoc with zero startup
   cost. Sourcing `tui_registry.py` (Python import) on every `ait help` /
   bad-command invocation adds interpreter startup for no real benefit.
3. **Blast radius / "edited unaware" safety.** A generator couples a
   user-facing CLI surface to an internal Python module; a future edit to the
   registry would silently reshape help output. The one-line fix keeps the
   help self-contained and obvious to the next editor.

The clean, low-risk resolution is to fix the actual drift (the missing line)
and leave the curated heredoc as-is.

## Out of scope (no changes needed)

- **Website docs** — `website/content/docs/commands/_index.md:29` already lists
  `ait stats-tui`; the TUI doc page exists at `docs/tuis/stats/`. No edits.
- **Other code agents** — this change touches only the `ait` bash dispatcher,
  not any skill surface, so no Codex/OpenCode port is implied.

## Risk

### Code-health risk: low
- Single descriptive line added to a static help heredoc; no logic, no control
  flow, no callers. · severity: low · → mitigation: none

### Goal-achievement risk: low
- The user's question is fully answered and the fix is the obvious one-liner;
  alignment verified against the existing column format. · severity: low ·
  → mitigation: none

No before/after mitigation tasks needed.

## Verification

1. Run `./ait help` (or `./ait --help`) and confirm the TUI section now lists
   `stats-tui      Launch the statistics TUI`, alphabetically between
   `settings` and `syncer`, with columns aligned to the other entries.
2. Confirm `./ait stats-tui --help` (or launching it) still works — unchanged
   dispatch, sanity check only.
3. `shellcheck .aitask-scripts/aitask_*.sh` is unaffected (change is in `ait`
   itself, a heredoc string); optionally `bash -n ait` to confirm no syntax
   regression.

## Step 9 (Post-Implementation)

Profile 'fast': work is on the current branch (no worktree/merge). After review
and commit, archive via `./.aitask-scripts/aitask_archive.sh 963`, then
`./ait git push`.
