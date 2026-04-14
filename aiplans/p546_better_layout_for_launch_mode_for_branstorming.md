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
