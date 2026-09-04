---
priority: medium
effort: medium
depends: [t1705_8]
issue_type: documentation
status: Ready
labels: [documentation, website, docs, minimonitor, aitask_monitor, tui, tui_switcher]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:10
updated_at: 2026-09-04 16:10
---

## Context

Ninth child of t1705 (frozen code agents). **TUI-surface documentation**
for everything children 4–7 shipped: the new `ait frozenagent` viewer, the
frozen row / counter / filter / keys in `ait minimonitor` and `ait monitor`,
the switcher entry, the dispatcher entry, and the `aidocs/framework`
conventions the implementation introduced (respawn-pane, `run-shell -b`,
the four `@aitask_*` pane options, the stand-in self-stamp rule). Per
`aidocs/framework/planning_conventions.md`, documentation is a first-class
child, created before the manual-verification sibling. The **workflow and
concept** docs (freeze/restore as a daily workflow, the framework-session
concept, the setup "Session hooks" section) are the *next* child
(t1705_10) — do not fold them in here. Document **current state only**
(`aidocs/framework/documentation_conventions.md`): no version history, no
"new in", generic agent wording where the supported agents are named.

Source of truth is the landed code, not this task or the parent plan —
re-read `frozenagent/frozenagent_app.py`, `minimonitor_app.py`,
`monitor_app.py`, `tui_switcher.py` for the real keys, glyphs, hint text and
messages before writing (memory: "doc the current source, not the stale
plan").

## Pages

1. **New** `website/content/docs/tuis/frozenagent/_index.md` (front matter
   like `tuis/applink/_index.md`: `title: "Frozen Agent"`, `linkTitle`,
   `weight` after monitor, `description`, `maturity: [experimental]`,
   `depth: [main-concept]`): purpose (what a frozen agent is, in two
   sentences, linking the workflow page from t1705_10 via `{{< relref >}}`
   — the link may point at a page that lands in the next child; run
   `check_links.py` after both), the standard "Customizable keys" callout,
   `## Launching` (`ait frozenagent` list mode; `--record <id>` viewer mode;
   the stand-in launch is automatic), `## Layout` (header fields: project ·
   window · task · agent · frozen_at · lines · state; log area; search box),
   `## Viewing` (`r` plain/ANSI, `m` markdown of all/selected, `g`/`G`),
   `## Searching`, `## Selecting and copying` (keyboard range vs mouse
   selection; `y`; where the text goes — OSC 52 + tmux buffer), `## Restore,
   re-pick and drop` (`R`/`p`/`k`, what "restoring…" then "restored,
   unverified — capture kept" / "restore failed: <reason>" mean),
   `## List mode`.
   `how-to.md` (`weight: 20`): "Read a frozen agent's summary", "Copy a
   spawned-task list out of a frozen transcript", "Bring an agent back",
   "Remove a frozen record".
   `reference.md` (`weight: 30`): `## Keybindings` table (incl. `j`
   switcher and `q`), `## Header fields`, `## States shown` (frozen /
   restoring / restored-unverified / failed), `## Exit codes` of the
   launcher.
2. **Edit** `website/content/docs/tuis/minimonitor/_index.md` and
   `how-to.md`: the frozen row (`<mark><F> name  frozen`, no state dot, no
   capture), coexistence with the priority/parked mark (glyph composition,
   what `space` does on a frozen row), the `Nf` session-bar term (always
   shown, independent of the filter — same wording pattern as the parked
   term), the `F` filter, freezing the followed agent (`z`, confirm text),
   Freeze-All (`Z`), `R`/`p`/`k` on a frozen row, the own-panel frozen
   render, and that the companion does **not** auto-despawn when its agent
   is frozen (update the "auto-despawn" sentence in `how-to.md:340`).
3. **Edit** `website/content/docs/tuis/monitor/reference.md` — keybinding
   rows (`z`, `Z`, `F`, `R`, `p`, `k` on frozen), the `N frozen` term in the
   session-bar section, the frozen preview placeholder; `monitor/_index.md`
   if it enumerates agent states.
4. **Edit** `website/content/docs/tuis/_index.md` — bullet
   `- **[Frozen Agent](frozenagent/)** (\`ait frozenagent\`) — …` and the
   "Navigating between TUIs" switcher paragraph (`f`).
5. **Edit** `website/content/docs/commands/_index.md` — `ait frozenagent`
   row; note whether an `ait frozen` verb exists (decided in t1705_4: default
   no).
6. **Edit** `aidocs/framework/tui_conventions.md` — a "Frozen stand-in
   panes" subsection: the self-stamp rule for `@aitask_standin_ready`, the
   companion/cleanup sibling rule, and a pointer to the parent plan's
   state machine; `aidocs/framework/tmux_gateway.md` — `respawn-pane` and
   `run-shell -b` are gateway-routed like everything else; the four options
   in the `@aitask_*` inventory (:112-129); `aidocs/framework/aitasks_extension_points.md`
   — the SessionStart hook install surface (seed → install.sh → setup merge
   → framework-path lists) as a checklist row.

## Reference patterns

- `website/content/docs/tuis/applink/{_index,how-to,reference}.md` — the
  Diátaxis triple and front matter.
- `website/content/docs/tuis/minimonitor/how-to.md` §parked (t1685's
  wording for a non-live row and an always-visible counter).
- `aidocs/framework/documentation_conventions.md`; `website/check_links.py`.

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build   # zero dead links / fragments
grep -rn 'frozen' website/content/docs/tuis/minimonitor/ website/content/docs/tuis/monitor/ | wc -l
grep -n 'frozenagent' website/content/docs/tuis/_index.md website/content/docs/commands/_index.md
```
No code, no tmux.
