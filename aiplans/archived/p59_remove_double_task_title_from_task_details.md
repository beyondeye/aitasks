---
Task: t59_remove_double_task_title_from_task_details.md
Branch: main
Base branch: main
---

## Context

In the aitask_board Python TUI, when opening task details, the task title is displayed twice:
1. As a styled header label at the top of the dialog (line 742)
2. As a Markdown H1 heading inside the scrollable content area (line 792)

The user wants to keep only the top header and remove the one before the description.

## Plan

**File:** `aitask_board/aitask_board.py`

**Change (line 792):** Remove the duplicate title from the Markdown content.

Current:
```python
yield Markdown(f"# {display_title}\n\n{self.task_data.content}")
```

Change to:
```python
yield Markdown(self.task_data.content)
```

This keeps the styled header label (line 742: `Label(f"📄 {display_title}", id="detail_title")`) and removes the redundant H1 heading from the Markdown body.

## Verification

1. Run the TUI: `python aitask_board/aitask_board.py`
2. Open task details for any task
3. Confirm the title appears only once at the top header, not repeated in the description area
