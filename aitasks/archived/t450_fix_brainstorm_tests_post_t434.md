---
priority: high
effort: low
depends: []
issue_type: test
status: Done
labels: [brainstorm, testing]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-24 10:25
updated_at: 2026-03-24 10:33
completed_at: 2026-03-24 10:33
---

## Update brainstorm tests to match post-t434 init behavior

Commit `d12df7f9` (t434) changed `init_session()` to create a root node (`n000_init`), set head, increment `next_node_id`, and transition status to `"active"` during init — but didn't update the unit tests.

### Failing tests (5 total)

**`tests/test_brainstorm_dag.py` (4 failures):**

1. **`test_init_session_creates_structure`** — expects `status == "init"`, gets `"active"`; expects empty graph state (`current_head: None`, `history: []`, `next_node_id: 0`), now gets populated values
2. **`test_list_nodes_sorted`** — expects only 3 manually-created nodes, but `init_session` now auto-creates `n000_init`
3. **`test_next_node_id_increments`** — expects counter starts at `0`, but init already increments it to `1`
4. **`test_set_head_updates_state`** — expects history `["n000_init"]` after one `set_head()` call, but init already added `"n000_init"` to history, causing a duplicate

**`tests/test_brainstorm_cli_python.py` (1 failure):**

5. **`test_status_shows_session_info`** — expects `"status: init"` and `"nodes: 0"` in output, now gets `"status: active"` and `"nodes: 1"`

### Fix approach

Update test expectations to match the new init behavior:
- `status` after init is now `"active"` (not `"init"`)
- `current_head` is `"n000_init"` (not `None`)
- `history` is `["n000_init"]` (not `[]`)
- `next_node_id` is `1` (not `0`)
- `list_nodes()` after init includes `n000_init`
- `set_head` tests need to account for head already set by init
- CLI status test should expect `"status: active"` and `"nodes: 1"`

All failures are test expectation mismatches — the new init behavior is intentional and correct.
