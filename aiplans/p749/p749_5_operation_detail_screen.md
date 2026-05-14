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

## Final Implementation Notes

- **Actual work done:**
  - Added `OperationDetailScreen(ModalScreen)` to `.aitask-scripts/brainstorm/brainstorm_app.py` (~160 lines + ~40 lines of modal CSS), placed next to the other modal screens.
  - Reads `br_groups.yaml` via the existing `_read_groups` helper; renders Overview + one tab per agent. Overview shows created_at, head_at_creation, nodes_created, resolved user-input Markdown (via `list_op_inputs` + `resolve_ref` from `brainstorm_op_refs`), and per-agent status lines with the same colored-dot convention used by `_mount_agent_row`. Per-agent tabs render Input / Output as `Markdown`, and a 200-line tail of `<agent>_log.txt` as `Static` via `read_log_tail`.
  - Missing-group case mounts a single placeholder `Label("#op_detail_missing")` and skips `TabbedContent` entirely — keeps the test surface predictable.
  - Bindings: `escape` shown in footer, `q` hidden, both → `dismiss(None)`. A `Footer()` is mounted in the dialog so the close hint is visible at the bottom.
  - Imported `OpDataRef`, `list_op_inputs`, `resolve_ref` from `brainstorm.brainstorm_op_refs` (no other new imports — `Markdown`, `Static`, `Footer`, `TabbedContent`, `TabPane`, `Button`, `read_log_tail`, `read_yaml`, `AGENT_STATUS_COLORS`, `OP_BADGE_STYLES`, `UNKNOWN_OP_STYLE` were already in scope).
  - Added `tests/test_brainstorm_operation_detail_screen.py` (Pilot-driven): three tests covering the happy path (Overview + 2 agent tabs, title/colors, escape dismiss), the missing-group placeholder, and the empty-agents bootstrap case (single Overview tab, "no agents registered yet" placeholder).

- **Deviations from plan:**
  - `read_log_tail` is called with `lines=200`, not `max_lines=200` — the helper's keyword is `lines`. (Plan snippet had `max_lines`.)
  - The plan listed a candidate `SectionMinimap` reuse from `section_viewer.py`; not wired in v1 because the per-agent Markdown documents are short enough in practice and the minimap would add another binding-conflict surface. Can be added later if long agent inputs become common.
  - Title built as a single Rich-markup string passed to `Label` (with op-color from `OP_BADGE_STYLES`) instead of constructing a separate `Static` per fragment — keeps the title centered as one widget with `dock: top`.

- **Issues encountered:**
  - The first iteration of the missing-group branch tried to mount `TabbedContent` with zero tabs, which Textual rejects at compose time. Fixed by short-circuiting before the tabs are yielded and emitting only `op_detail_title`, `op_detail_missing`, and the Close button. The `test_missing_group_shows_placeholder` test pins this behavior.

- **Key decisions:**
  - Used `Static` (not `RichLog`) for the log block. Log files are read-once snapshots here; `RichLog` would add complexity (queue, auto-scroll) with no payoff at this layer.
  - Modal sized 80%×90% (slightly narrower than `NodeDetailModal` at 90%×90%) — the per-agent tabs benefit from the tighter Markdown column width.
  - Manual-verification of the live "press 'o' on a focused node" flow is intentionally deferred to t749_6 (which wires the keybinding) and the parent's aggregate manual-verification sibling. For this child the automated Pilot tests are the verification surface.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t749_6** can push the screen with `self.app.push_screen(OperationDetailScreen(group_name, session_path))`. The group name is the `operation_id` recorded on the focused node (e.g., `explore_001`); `session_path` is the brainstorm dashboard's existing `self.session_path`. No new construction-time validation is needed — missing groups are handled by the screen itself.
  - The screen does NOT subscribe to file-watchers — content snapshots are taken at compose time. If a future task needs live refresh (agent status flipping while the screen is open), it would need a periodic `set_interval` reload or a Textual reactive backed by `br_groups.yaml`. Out of scope for v1.
  - `OperationDetailScreen` exposes `self.group_info` after compose — sibling tasks can subclass and reach into it for navigation features (e.g., clicking a node id to push `NodeDetailModal`). The current node-id rendering is a plain `Static` with no click handler.
  - A throwaway preview launcher (`scratch_op_detail.py`, gitignored) was used during implementation to visually verify the screen against synthetic and real brainstorm sessions; it was deleted before commit. Future siblings can recreate the same pattern if they need an interactive preview before the 'o' keybinding lands.
