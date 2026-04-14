---
Task: t546_better_layout_for_launch_mode_for_branstorming.md
Base branch: main
---

## Context

In the `ait settings` TUI on the **Agent Defaults** tab, the "Default Code Agents for Brainstorming" section lists each brainstorm agent type (explorer, comparator, synthesizer, detailer, patcher) with two rows:

1. The codeagent+llm setting (e.g., `brainstorm-explorer: claudecode/opus4_6`)
2. A `launch_mode` setting on the next line

The launch_mode row currently renders with the bold label `launch_mode:` for **every** brainstorm agent type. Since they all use the same label and they're not visually subordinated to the agent line above them, users cannot tell which brainstorm agent type a given launch_mode row belongs to.

The user requested two complementary fixes (apply both):

1. Add leading padding to the launch_mode label so it visually reads as a sub-setting of the codeagent row above it.
2. Make the label specific to the agent type — change `launch_mode` to `brainstorm-<atype> launch_mode` (e.g., `brainstorm-explorer launch_mode`).

## File to modify

- `.aitask-scripts/settings/settings_app.py`

## Implementation

### Background on the rendering

`ConfigRow.render()` (lines 764–776) renders non-subordinate rows as:

```python
return f"  {badge}  [bold]{self.key}:[/bold]  {self.value}"
```

So `self.key` is interpolated as the bold label and is **purely cosmetic**. The action handlers (lookup, edit, delete) all use `self.row_key`, not `self.key` (verified at lines 1601, 1640, 1659, 1668–1680, 1699, 1719, 1745). This means the displayed `key` argument can be changed freely without breaking anything.

The subordinate (user-layer) row uses a different render branch that does **not** include `self.key` at all — it just shows the badge + value indented with `      └`. So the user row already looks visually subordinate; only the project (top-level) launch_mode row needs the cosmetic fix.

### The change

In `_emit_launch_mode_rows()` (lines 1880–1922), the project-layer `ConfigRow` is mounted at line 1897 with `"launch_mode"` as the displayed key:

```python
container.mount(ConfigRow(
    "launch_mode", proj_display_lm,
    config_layer="project", row_key=lm_key,
    id=f"agent_proj_brainstorm_launch_{atype}_{rc}",
    raw_value=proj_raw_lm,
))
```

Change the first argument from `"launch_mode"` to:

```python
f"    brainstorm-{atype} launch_mode"
```

The four leading spaces add visual padding (so the row reads as indented under its parent codeagent row), and `brainstorm-{atype}` makes it explicit which brainstorm agent the launch_mode belongs to.

For the user-layer row at line 1910, also pass the same display key for consistency, even though `ConfigRow.render()` does not use it for subordinate rows. This keeps `self.key` in sync between the pair so any future code that introspects `row.key` sees the same value:

```python
container.mount(ConfigRow(
    f"    brainstorm-{atype} launch_mode", user_display_lm,
    config_layer="user", row_key=lm_key,
    id=f"agent_user_brainstorm_launch_{atype}_{rc}",
    subordinate=True,
    raw_value=user_raw_lm,
))
```

`row_key=lm_key` (which is `f"brainstorm-{atype}-launch-mode"`) stays unchanged, so all keyboard handlers and config lookups continue to work.

## What it looks like before/after

Before (each brainstorm agent block):

```
  [PROJECT]  brainstorm-explorer:  claudecode/opus4_6
      └ [USER]  (inherits project)
  [PROJECT]  launch_mode:  headless  (framework default)
      └ [USER]  (inherits project)
```

After:

```
  [PROJECT]  brainstorm-explorer:  claudecode/opus4_6
      └ [USER]  (inherits project)
  [PROJECT]      brainstorm-explorer launch_mode:  headless  (framework default)
      └ [USER]  (inherits project)
```

The label is now both visually indented and explicitly named for its agent type.

## Verification

1. Launch the settings TUI:
   ```bash
   ./ait settings
   ```
2. Navigate to the **Agent Defaults** tab (use the keyboard shortcut or arrow keys).
3. Scroll to the "Default Code Agents for Brainstorming" section.
4. For each brainstorm agent type (explorer, comparator, synthesizer, detailer, patcher), confirm:
   - The launch_mode row label now reads `brainstorm-<atype> launch_mode:` instead of `launch_mode:`
   - The label appears visually indented (4 extra spaces of padding) relative to the parent codeagent row above it
5. Focus the launch_mode row and press Enter to verify the editor still opens correctly (proves `row_key` lookup is unaffected).
6. Set a user-layer override on a launch_mode row, then press `d` to clear it — verify clearing still works (proves the delete handler that reads `row_key` is unaffected).
7. No tests reference `ConfigRow` or the launch_mode label rendering (verified via grep), so no test updates are needed.

## Step 9 (Post-Implementation)

After implementation: review changes with the user, commit with `feature: <description> (t546)`, archive with `./.aitask-scripts/aitask_archive.sh 546`, push with `./ait git push`.

## Post-Review Changes

### Change Request 1 (2026-04-14 14:10)
- **Requested by user:** Add left padding also to the help/description label below the launch_mode row, not just the row itself.
- **Changes made:** Prepended 4 spaces to the `desc_lm` label string at line 1922 so the dim italic help text aligns with the indented launch_mode label above it.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`

### Change Request 2 (2026-04-14 14:14)
- **Requested by user:** The "(inherits project)" subordinate row of the launch_mode setting also needs the left padding — currently only the project row was indented.
- **Changes made:** Replaced the ad-hoc 4-space prefix in the launch_label string with a new explicit `extra_indent: int = 0` parameter on `ConfigRow`. `ConfigRow.render()` now prepends `" " * extra_indent` to the rendered output for both the project (non-subordinate) and user (subordinate) branches. Both launch_mode `ConfigRow` mounts now pass `extra_indent=4`. The `launch_label` string was simplified back to `f"brainstorm-{atype} launch_mode"` (no leading spaces) since the parameter handles the padding uniformly.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`

### Change Request 3 (2026-04-14 14:17)
- **Requested by user:** The `└` (L-shape) corner glyph at the start of the subordinate row still does not move right with the rest of the launch_mode indent — the padding was inserted between the glyph and the badge, not before the glyph.
- **Changes made:** Moved `{pad}` to before `\u2514` in the subordinate render branch, so the entire L corner shifts right by `extra_indent` spaces. The fixed 6-space prefix that aligns the L under the parent row is still preserved.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`

## Final Implementation Notes

- **Actual work done:** Added an explicit `extra_indent: int = 0` parameter to `ConfigRow` (lines 753–763, 776, 778, 783) and rendered it as `" " * extra_indent` prepended to both the subordinate and non-subordinate render branches. In the subordinate branch the padding is placed BEFORE the `└` corner glyph so the entire glyph shifts right with the indent. The two `ConfigRow` mounts in `_emit_launch_mode_rows()` now use `launch_label = f"brainstorm-{atype} launch_mode"` (specific per agent type) and `extra_indent=4`. The dim-italic help text label (`desc_lm`) below them is also prepended with 4 spaces of literal padding so it aligns with the indented row above. `row_key=lm_key` is unchanged for both rows so all keyboard handlers and config lookups continue to work.
- **Deviations from plan:** The original plan only added cosmetic leading spaces inside the `key` argument string and only to the project row. After three review iterations the user asked for the help label, the user-layer subordinate row, and the L-glyph itself to all shift right too. The cleanest way to handle all three was to introduce a generic `extra_indent` parameter on `ConfigRow` rather than continue prepending whitespace ad-hoc. This is a slightly larger surface change (two new lines on `ConfigRow.__init__`, two-line tweak to `render()`) but the call site is now declarative and all four affected glyphs (bold key, badge, value on the project row; L-corner, badge, value on the user row) line up consistently.
- **Issues encountered:** None. Each change request was a small additive fix. Python AST syntax was verified after every edit with `python3 -c "import ast; ast.parse(...)"`.
- **Key decisions:** Chose an explicit `extra_indent` int parameter over auto-detecting leading whitespace from `self.key`, for clarity at the call site and to keep the displayed key string clean. `extra_indent` defaults to 0 so all existing `ConfigRow` callers (agent-string rows, codeagent rows, env var rows, etc.) are unaffected.
