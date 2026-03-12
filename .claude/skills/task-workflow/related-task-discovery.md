# Related Task Discovery Procedure

This shared procedure finds pending tasks that overlap with a given context and presents them to the user for selection. It is referenced by aitask-explore (Step 2b), aitask-fold (Step 1), and aitask-contribution-review.

## Parameters

| Parameter | Description | Example values |
|-----------|-------------|----------------|
| `matching_context` | What to compare against for relevance. Not used when `selection_mode` is `all`. | Exploration findings, task description, contribution metadata |
| `purpose_text` | Displayed in the AskUserQuestion to explain what happens to selected tasks. | "will be fully covered by the new task (they will be folded in and deleted after implementation)" |
| `min_eligible` | Minimum number of eligible tasks required to proceed. If fewer exist, inform user and return empty. | 1 (explore, contribution-review), 2 (fold) |
| `selection_mode` | How tasks are presented: `ai_filtered` pre-filters by AI relevance; `all` shows every eligible task. | `ai_filtered` (explore, contribution-review), `all` (fold) |

## Procedure

### Step 1: List Pending Tasks

```bash
./.aitask-scripts/aitask_ls.sh -v --status all --all-levels 99 2>/dev/null
```

### Step 2: Filter Eligible Tasks

Filter the output to include only tasks that are eligible:
- Status must be `Ready` or `Editing`
- Must not have children (status shows "Has children") — too complex to fold
- Must not be a child task (filename pattern `t<parent>_<child>_*.md`) — too complex to fold
- Exclude tasks with status `Implementing`, `Postponed`, `Done`, or `Folded`

**Scope rule:** Only standalone parent-level tasks without children may be selected.

**Minimum count check:** If fewer than `min_eligible` eligible tasks exist:
- Inform user accordingly (e.g., "Need at least 2 eligible tasks to fold. Only \<N\> eligible task(s) found." for fold, or "No existing pending tasks appear related to this exploration." for explore/contribution-review)
- Return empty (no selected tasks). The calling skill decides whether to abort or continue.

### Step 3: Assess Relevance

**If `selection_mode` is `ai_filtered`:**

For each eligible task:
- Read the task file's title and first ~5 lines of body text
- Note the task's labels from frontmatter

Based on the `matching_context`, identify tasks whose scope overlaps significantly. A task is "related" if it covers the same goal, fixes the same problem, or implements the same feature as the matching context.

**If no related tasks are found:** Inform user (e.g., "No existing pending tasks appear related.") and return empty.

**If `selection_mode` is `all`:**

For each eligible task:
- Read the task file's title and first ~5 lines of body text
- Note the task's labels from frontmatter

**Identify related groups** by analyzing:
- **Shared labels:** Tasks that share one or more labels are likely related
- **Semantic similarity:** Tasks whose descriptions address the same topic, feature, or problem area

Present a summary of the eligible tasks and any detected relationships. All eligible tasks proceed to selection (no pre-filtering).

### Step 4: Present Results

Use `AskUserQuestion` with multiSelect to let the user choose tasks.

- Question: Constructed from `purpose_text`. Examples:
  - For explore: "These existing tasks appear related to your exploration findings. Select any that \<purpose_text\>:"
  - For fold: "Select tasks to \<purpose_text\>:"
  - For contribution-review: "These existing tasks appear related to the contribution. Select any that \<purpose_text\>:"
- Header: "Related tasks"
- Options: Each task with the task filename as label and a brief description (summary + labels + match reason). Include a "None — no tasks to fold in" option (for `ai_filtered` mode).

**Pagination:** Since `AskUserQuestion` supports a maximum of 4 options, implement pagination if there are more than 3 tasks to present:
- Start with `current_offset = 0` and `page_size = 3` (3 tasks per page + 1 "Show more" slot)
- For each page, show tasks from `current_offset` to `current_offset + page_size - 1`
- If more tasks exist beyond this page, add a "Show more tasks" option (description: "Show next batch of tasks (N more available)")
- On the last page, show up to 4 tasks
- Accumulate selections across pages

### Step 5: Return

**If user selects "None" or no tasks:** Return empty list.

**If user selects one or more tasks:** Return the list of selected task IDs (e.g., `[106, 129]`).

**Post-selection validation (for fold):** If `min_eligible` is 2 and fewer than 2 tasks were selected, inform user "Need at least 2 tasks to fold." and return empty.

The calling skill stores the returned IDs as `folded_tasks` (or equivalent) and handles subsequent processing (reading full task content, updating frontmatter, etc.).
