---
Task: t447_3_push_crew_worktree_after_addwork.md
Parent Task: aitasks/t447_add_crew_runner_control_to_brainstorm_tui.md
Sibling Tasks: aitasks/t447/t447_1_extract_runner_control_shared_module.md, aitasks/t447/t447_2_add_runner_ui_to_brainstorm_status_tab.md
Archived Sibling Plans: aiplans/archived/p447/p447_1_extract_runner_control_shared_module.md, aiplans/archived/p447/p447_2_add_runner_ui_to_brainstorm_status_tab.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Plan: Push crew worktree after addwork for cross-machine runner support

### Design Decision

**Option A (recommended): Modify `ait crew addwork` script.** This benefits all callers — brainstorm TUI, crew dashboard, CLI. The push is best-effort (doesn't block on failure).

### Step 1: Add push to `aitask_crew_addwork.sh`

After the git commit block (line 282), add a push:

```bash
    git push --quiet 2>/dev/null || warn "git push failed (offline?)"
```

The full block (lines 274-283) becomes:

```bash
(
    cd "$WT_PATH"
    # shellcheck disable=SC2086
    git add "${AGENT_NAME}_work2do.md" "${AGENT_NAME}_status.yaml" \
            "${AGENT_NAME}_input.md" "${AGENT_NAME}_output.md" \
            "${AGENT_NAME}_instructions.md" "${AGENT_NAME}_commands.yaml" \
            "${AGENT_NAME}_alive.yaml" "_crew_meta.yaml" $GIT_ADD_GROUPS
    git commit -m "crew: Add agent '${AGENT_NAME}' to crew '${CREW_ID}'" --quiet
    git push --quiet 2>/dev/null || warn "git push failed (offline?)"
)
```

### Step 2: Verify

1. Register an agent: `ait crew addwork --crew <id> --name test_agent --work2do /dev/null --type impl --batch`
2. Check: `git -C .aitask-crews/crew-<id> status` — should show "Your branch is up to date"
3. Test offline: disconnect network, run addwork — should warn but not fail

### Step 9: Post-Implementation

Archive task and plan per workflow.
