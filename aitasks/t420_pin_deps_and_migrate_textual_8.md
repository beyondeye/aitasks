---
priority: high
effort: high
depends: []
issue_type: chore
status: Ready
labels: [tui, dependencies]
created_at: 2026-03-19 09:26
updated_at: 2026-03-19 09:26
---

## Summary

Pin all Python dependency versions in `ait setup` and migrate all 5 TUI applications from Textual 7.5.0 to Textual 8.x (latest: 8.1.1).

## Background

Currently `ait setup` (`aitask_setup.sh` line 502) installs dependencies without version pinning:
```bash
"$VENV_DIR/bin/pip" install --quiet textual pyyaml linkify-it-py tomli
```

There is no `requirements.txt` or `pyproject.toml`. This means:
- Anyone running `ait setup` today gets Textual 8.x, but existing TUIs were built against 7.x
- Breaking changes in any dependency silently break TUI apps
- No way to reproduce a known-good environment

## Current Package Versions

| Package | Installed | Latest |
|---------|-----------|--------|
| textual | 7.5.0 | 8.1.1 |
| PyYAML | 6.0.3 | 6.0.3 |
| linkify-it-py | 2.0.3 | 2.1.0 |
| tomli | 2.4.0 | 2.4.0 |
| plotext | 5.3.2 | 5.3.2 |

## Tasks

### 1. Pin dependency versions in `ait setup`

Update `aitask_setup.sh` to install pinned versions:
```bash
"$VENV_DIR/bin/pip" install --quiet textual==8.1.1 pyyaml==6.0.3 linkify-it-py==2.1.0 tomli==2.4.0
```
(And `plotext==5.3.2` for the optional install.)

### 2. Migrate TUIs from Textual 7.5.0 → 8.x

Check Textual release notes and migration guides for breaking changes between 7.5.0 and 8.1.1. Apply necessary code changes to all 5 TUI apps:

- **Board** (`.aitask-scripts/board/aitask_board.py`, ~3,941 LOC) — heaviest user: App, Screen, ModalScreen, command palette (Provider/Hit/DiscoveryHit), Markdown, many widgets
- **Code Browser** (`.aitask-scripts/codebrowser/codebrowser_app.py`, ~628 LOC) — DirectoryTree, custom widgets
- **Diff Viewer** (`.aitask-scripts/diffviewer/diffviewer_app.py` + modules, ~223+ LOC) — Screen, ModalScreen, RadioButton/RadioSet, Checkbox
- **Settings** (`.aitask-scripts/settings/settings_app.py`) — TextArea, TabbedContent, Input
- **AgentCrew Dashboard** (`.aitask-scripts/agentcrew/agentcrew_dashboard.py`, ~771 LOC) — ProgressBar, containers

### 3. Test all TUI apps after migration

Verify each TUI launches and functions correctly with the new Textual version:
- `ait board`
- `ait codebrowser`
- `ait diffviewer`
- `ait settings`
- `ait crew dashboard`

### 4. Update documentation

Update `website/content/docs/installation/_index.md` and any other docs that reference Python package versions.

## References

- Textual changelog: check PyPI/GitHub releases for 7.5.0 → 8.1.1 migration notes
- Shell wrappers that check imports: `aitask_board.sh`, `aitask_codebrowser.sh`, `aitask_diffviewer.sh`, `aitask_settings.sh`, `aitask_crew_dashboard.sh`
