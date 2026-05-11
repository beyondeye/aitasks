---
Task: t749_5_operation_detail_screen.md
Parent Task: aitasks/t749_report_operation_that_generated_nod.md
Sibling Tasks: aitasks/t749/t749_1_*.md, aitasks/t749/t749_2_*.md, aitasks/t749/t749_3_*.md, aitasks/t749/t749_4_*.md, aitasks/t749/t749_6_*.md, aitasks/t749/t749_7_*.md
Archived Sibling Plans: aiplans/archived/p749/p749_*_*.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-11 09:45
---

# Plan: Operation Detail Screen (t749_5)

## Context

Largest child of t749. Adds the `OperationDetailScreen(ModalScreen)`
class to `brainstorm_app.py`. Built from the same `Header +
TabbedContent + Close` pattern as `NodeDetailModal`.

Depends on: t749_1 (br_groups.yaml populated) and t749_2 (`OpDataRef`
helpers).

## Implementation Steps

### Step 1 — Class skeleton

Add `OperationDetailScreen` near `NodeDetailModal` (around
brainstorm_app.py:380). Bindings: `escape` and `q` close. Constructor
takes `(group_name, session_path)`.

### Step 2 — `compose()`

Standard modal layout (Container > Label title > TabbedContent >
Horizontal[Button Close]).

### Step 3 — `on_mount()`

1. `_read_groups(self.session_path)` (helper from t749_4) → look up
   `group_info`. If missing: mount a single placeholder Label
   "(no group entry recorded for `<group_name>`)" and return early.
2. Build the title: `[bold]Operation: <op>[/] (<group_name>)
   [<status>]` with op-color from `OP_BADGE_STYLES`.
3. Mount the Overview tab (Step 4).
4. For each agent in `group_info["agents"]`, mount a per-agent tab
   (Step 5).

### Step 4 — Overview tab

Inside `TabPane("Overview", id="op_overview")`, mount in order:

- `Created at: <created_at>`
- `HEAD at creation: <head_at_creation>` (plain Static, no link in v1)
- `Nodes created: n1, n2, ...` (or `(none yet)` if empty)
- An "Input" sub-section: render
  ```python
  refs = list_op_inputs(group_info)
  if not refs:
      mount Label("(no agents registered yet — input pending)")
  else:
      ref = refs[0]
      content = resolve_ref(self.session_path, ref)
      if not content:
          mount Label("(no input found)")
      else:
          mount Label(f"## Input — {ref.section or '(whole file)'}")
          mount Markdown(content)
  ```
- An "Agent statuses" sub-section: for each agent, read
  `<agent>_status.yaml` and mount a one-line Static (re-use the
  per-agent line format from `_mount_agent_row` in
  brainstorm_app.py:2772).

### Step 5 — Per-agent tab

For each agent name `n` in `group_info["agents"]`:

```python
with TabPane(n, id=f"tab_agent_{n}"):
    yield VerticalScroll(
        Label("[bold]Input[/]"),
        Markdown(resolve_ref(session_path, OpDataRef("agent_input", n))),
        Label("[bold]Output[/]"),
        Markdown(resolve_ref(session_path, OpDataRef("agent_output", n))
                 or "*(agent has not produced output yet)*"),
        Label("[bold]Log (last 200 lines)[/]"),
        Static(read_log_tail(session_path / f"{n}_log.txt", max_lines=200)
               or "*(no log)*"),
    )
```

### Step 6 — CSS

Add a `OperationDetailScreen.DEFAULT_CSS` block sized like
`NodeDetailModal.DEFAULT_CSS` (90% width / 90% height, centered).

### Step 7 — Tests

Add `tests/test_brainstorm_operation_detail_screen.py` using Textual
`Pilot`. Setup:

- Tmp session, `record_operation("explore_001", "explore",
  ["explorer_001a", "explorer_001b"], "n000_init")`.
- Write fixture `explorer_001a_input.md` with a `## Exploration
  Mandate\nGo big or go home.` block; output and log fixtures.
- Push `OperationDetailScreen("explore_001", session_path)`.
- Assert title contains `Operation: explore`, tab count == 3
  (Overview + 2 agents), and the Overview tab's mandate text equals
  the fixture content.
- Press `escape` and assert dismiss.

## Files Modified

- `.aitask-scripts/brainstorm/brainstorm_app.py` — ~150 LOC
- `tests/test_brainstorm_operation_detail_screen.py` — NEW

## Step 9 (Post-Implementation)

Standard archival flow. Manual verification of the screen layout is
deferred to the parent's manual-verification sibling.

## Verification

(Aggregated under the parent task's manual-verification sibling.)
