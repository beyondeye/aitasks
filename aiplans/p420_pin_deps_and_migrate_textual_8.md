---
Task: t420_pin_deps_and_migrate_textual_8.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Pin Python Dependencies and Migrate to Textual 8.x

## Context

`ait setup` installs Python packages without version pinning. Textual is now at 8.1.1 but our TUIs were built against 7.5.0. New users running `ait setup` would get Textual 8.x which has breaking changes. This task pins all dependency versions and migrates the codebase to Textual 8.1.1.

## Breaking Changes Analysis (Textual 7.5.0 → 8.1.1)

All breaking changes are in 8.0.0. Versions 8.0.1–8.1.1 are bug fixes only.

**Affects our code:**
1. **Container scrollbar defaults changed** — `Container` no longer shows scrollbars by default; `VerticalScroll`/`HorizontalScroll` no longer show cross-axis scrollbar. May affect layouts in all TUI apps.
2. **All containers now have `1fr` default dimensions** — May change sizing behavior.
3. **RadioSet is now single-focusable** — Individual RadioButtons no longer focusable. Used in `plan_manager_screen.py`.
4. **TextArea defaults changed** — `soft_wrap` now `True`, `show_line_numbers` now `False`. Used in `settings_app.py:1403`.
5. **DirectoryTree threading + larger click targets** — Used in `codebrowser/file_tree.py`. Behavioral change, unlikely to break.

**Does NOT affect our code (verified by grep):**
- `Select.BLANK` → `Select.NULL` (not used)
- `Label(renderable=...)` → `Label(content=...)` (not used)
- `Markdown.code_dark_theme` / `code_light_theme` / `code_indent_guides` (not used)
- `OptionList(wrap=...)` / `OptionList(tooltip=...)` (not used)
- `containers.Content` removed (not used)
- `action_add_class_` / `action_remove_class_` renamed (not used)
- `DataTable` behavior changes (not used)
- `Widget.anchor` semantics (not used)

## Dependency Versioning Research

Not all packages follow semver. Research into each package's history:

| Package | Follows Semver | Breaking in Minors | Evidence | Pin Strategy |
|---------|---------------|-------------------|----------|-------------|
| **Textual** | Yes (post-1.0) | No | Breaking changes only in major: 7→8. Minors within a major are safe. | `>=8.1.1,<9` |
| **PyYAML** | No | Yes | 5.1 broke `yaml.load()`, 5.4 moved python tags, 6.0 made Loader mandatory | `==6.0.3` |
| **linkify-it-py** | Unclear | Yes | 2.1.0 dropped Python 3.7-3.9 support in a minor version | `==2.1.0` |
| **tomli** | Yes (strict) | No | All breaking changes in 2.0.0 only. Minor versions add features/deprecate. | `>=2.4.0,<3` |
| **plotext** | No | Yes | 5.2→5.3 renamed `datetimes_to_string()` → `datetimes_to_strings()` | `==5.3.2` |

**Strategy:** Use `>=X,<Y` (major ceiling) for semver-compliant packages (Textual, tomli). Use exact `==` pins for packages with breaking changes in minor versions (PyYAML, linkify-it-py, plotext).

## Implementation Steps

### Step 1: Pin dependency versions in `ait setup`

**File:** `.aitask-scripts/aitask_setup.sh` (lines 501-508)

Change unpinned `pip install` to pinned versions with differentiated strategy.

### Step 2: Update local venv to Textual 8.1.1

### Step 3: Migrate TUI code for Textual 8.x compatibility

- 3a. TextArea defaults — `settings_app.py` — No code change needed (new defaults are desirable)
- 3b. RadioSet focus — `plan_manager_screen.py` — No code change needed (API compatible)
- 3c. Container scrollbar defaults — Test and fix if content clipped
- 3d. Container `1fr` defaults — Test and fix layout issues
- 3e. DirectoryTree threading — `codebrowser/file_tree.py` — Verify works

### Step 4: Test all TUI apps

### Step 5: Update documentation

## Key Files

- `.aitask-scripts/aitask_setup.sh` (lines 501-508)
- `.aitask-scripts/board/aitask_board.py`
- `.aitask-scripts/codebrowser/codebrowser_app.py` + `file_tree.py`
- `.aitask-scripts/diffviewer/plan_manager_screen.py`
- `.aitask-scripts/settings/settings_app.py`
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py`
- `website/content/docs/installation/_index.md`
- `website/content/docs/commands/setup-install.md`
- `website/content/docs/commands/board-stats.md`

## Verification

1. `~/.aitask/venv/bin/pip list | grep textual` → 8.1.1
2. `ait board` → loads, renders, command palette works
3. `ait settings` → tabs and TextArea work
4. `ait codebrowser .` → file tree and code display work
5. Review setup script changes

## Step 9 Reference

After implementation, proceed to Post-Implementation: commit, archive task, push.
