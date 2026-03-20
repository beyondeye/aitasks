---
Task: t423_11_interactive_planning_mode_agent_refinement.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Add an interactive planning mode where a code agent (Detailer) runs interactively in the user's terminal to analyze and refine a plan. The TUI suspends via App.suspend(), yields the terminal to the agent, and resumes when the agent finishes. This bypasses the batch-only AgentCrew system for real-time conversational plan refinement.

Depends on: t423_1 (scaffold), t423_6 (actions wizard)

## Implementation

1. Add "Refine Plan (Interactive)" to Actions wizard operation list
2. When selected: user picks a node with an existing plan
3. Prepare input: plan content, node metadata, reference files, output path
4. Assemble work2do prompt: instruct agent to read plan, analyze for ambiguities, ask user questions, write refined plan to output path
5. self.app.suspend() to yield terminal
6. Launch: `./ait codeagent --agent-string <detailer_string> invoke raw -p <work2do>`
7. Agent runs interactively (full terminal access)
8. On agent exit: TUI resumes, reads output file
9. Update node's plan_file in DAG
10. Optionally run impact analysis

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Add "Refine Plan (Interactive)" action + suspend logic
- New file: `.aitask-scripts/brainstorm/templates/interactive_refine_work2do.md` -- Work2do template for interactive agent

### Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_crew.py` -- Agent string resolution from config
- `.aitask-scripts/brainstorm/brainstorm_dag.py` -- `read_node()`, `read_plan()`, `read_proposal()`

### Manual Verification
1. Select "Refine Plan (Interactive)" -- select node
2. TUI clears -- agent starts in terminal
3. Agent asks questions -- user answers
4. Agent writes plan -- session ends
5. TUI resumes -- plan updated

## Post-Implementation

Follow Step 9 of the task workflow (testing, verification, commit).
