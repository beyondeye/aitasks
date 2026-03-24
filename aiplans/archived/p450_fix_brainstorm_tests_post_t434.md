---
Task: t450_fix_brainstorm_tests_post_t434.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Commit `d12df7f9` (t434) changed `init_session()` to create a root node (`n000_init`), set head, increment `next_node_id`, and transition status to `"active"` during init. The tests were not updated to reflect this behavioral change, causing 5 failures.

## Plan: Update test expectations

### File 1: `tests/test_brainstorm_dag.py`

**1. `test_init_session_creates_structure` (line 93-111)**
Update expectations to match post-init state:
- `session["status"]` → `"active"` (was `"init"`)
- `gs["current_head"]` → `"n000_init"` (was `None`)
- `gs["history"]` → `["n000_init"]` (was `[]`)
- `gs["next_node_id"]` → `1` (was `0`)
- Add assertions for the auto-created node and proposal files

**2. `test_set_head_updates_state` (line 166-182)**
Init already sets head to `n000_init` and adds it to history. The test then calls `set_head(wt, "n000_init")` again, causing a duplicate.
- After init, history is already `["n000_init"]`
- After explicit `set_head("n000_init")`, history becomes `["n000_init", "n000_init"]`
- After `set_head("n001_alt")`, history becomes `["n000_init", "n000_init", "n001_alt"]`
- Update expected history values accordingly

**3. `test_next_node_id_increments` (line 206-209)**
Init already consumed ID 0 and incremented to 1.
- First call returns `1` (was `0`)
- Second call returns `2` (was `1`)
- Third call returns `3` (was `2`)

**4. `test_list_nodes_sorted` (line 215-221)**
Init creates `n000_init` automatically, which appears in `list_nodes()`.
- Expected result includes `n000_init` alongside the 3 manually created nodes
- Result: `["n000_a", "n000_init", "n001_b", "n002_c"]`

### File 2: `tests/test_brainstorm_cli_python.py`

**5. `test_status_shows_session_info` (line 128-133)**
- Change `"status: init"` → `"status: active"`
- Change `"nodes: 0"` → `"nodes: 1"`

## Verification

```bash
python3 -m unittest tests/test_brainstorm_dag.py -v
python3 -m unittest tests/test_brainstorm_cli_python.py -v
```

All 26 tests (16 + 10) should pass.

## Final Implementation Notes
- **Actual work done:** Updated test expectations in 2 files (5 test methods) to match post-t434 `init_session()` behavior — exactly as planned
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Updated assertions in-place rather than restructuring tests; added brief comments explaining why expected values differ from the pre-t434 defaults
