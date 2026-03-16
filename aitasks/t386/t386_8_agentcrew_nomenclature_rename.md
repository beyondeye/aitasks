---
priority: high
effort: low
depends: []
issue_type: chore
status: Ready
labels: [agentcrew]
created_at: 2026-03-16 15:59
updated_at: 2026-03-16 16:00
---

## AgentCrew Nomenclature Rename

### Context
The t386 child tasks and plans were originally written using "agentset" / "AgentSet" terminology. After review, the feature is being renamed to "agentcrew" / "crew". This task applies the rename across all existing task files, plan files, and the parent task — before any implementation begins.

No code files exist yet (all scripts are to-be-created by t386_1 through t386_7), so this is purely a task/plan metadata and content update.

### Goal
Systematically rename all "agentset" terminology to "agentcrew" / "crew" across all t386 task and plan files, following the approved naming convention.

### Naming Convention

| Context | Old | New |
|---------|-----|-----|
| CLI commands | `ait agentset` | `ait crew` |
| CLI subcommand | `ait agentset add` | `ait crew addtask` |
| Full form (code, docs, descriptions) | `agentset` / `AgentSet` | `agentcrew` / `AgentCrew` |
| Script filenames | `aitask_agentset_*` | `aitask_crew_*` |
| Python package dir | `.aitask-scripts/agentset/` | `.aitask-scripts/agentcrew/` |
| Python filenames | `agentset_*.py` | `agentcrew_*.py` |
| Bash library | `agentset_utils.sh` | `agentcrew_utils.sh` |
| Constants | `AGENTSET_*` | `AGENTCREW_*` |
| Guard variable | `_AIT_AGENTSET_UTILS_LOADED` | `_AIT_AGENTCREW_UTILS_LOADED` |
| Branch prefix | `agentset-<id>` | `crew-<id>` |
| Worktree dir | `.aitask-agentsets/agentset-<id>/` | `.aitask-crews/crew-<id>/` |
| .gitignore entry | `.aitask-agentsets` | `.aitask-crews/` |
| YAML meta/status files | `_agentset_meta.yaml` | `_crew_meta.yaml` |
| YAML meta/status files | `_agentset_status.yaml` | `_crew_status.yaml` |
| Test files | `test_agentset_*.sh` | `test_crew_*.sh` |
| Internal docs | `aidocs/agentset_*.md` | `aidocs/agentcrew_*.md` |
| Website paths | `agentset.md`, `agentset-dashboard/` | `crew.md`, `crew-dashboard/` |
| Functions | `agentset_branch_name()`, `validate_agentset_id()`, `resolve_agentset()` | `crew_branch_name()`, `validate_crew_id()`, `resolve_crew()` |
| Functions | `list_agentsets()`, `load_agentset()` | `list_crews()`, `load_crew()` |
| Classes | `AgentSetManager`, `AgentSetDetailScreen` | `CrewManager`, `CrewDetailScreen` |
| Status constants | `AGENTSET_STATUSES` | `CREW_STATUSES` |
| CLI flag | `--agentset <id>` | `--crew <id>` |
| Labels (frontmatter) | `subagents` | `agentcrew` |
| Commit prefix | `agentset:` | `crew:` |

**Unchanged terms:**
- "agent" in agent-level concepts (`agent_name`, `agent_type`, `validate_agent_name()`, individual `<name>_status.yaml` files)
- `_runner_alive.yaml` (about the runner process)
- `work2do` (already renamed from "task" per original spec)

### Files to Modify

**Parent task:**
- `aitasks/t386_subagents_infra.md` — Update labels from `subagents` to `agentcrew`, update all "agentset" references in description

**Child tasks (content + labels):**
- `aitasks/t386/t386_1_core_data_model_init_add.md`
- `aitasks/t386/t386_2_status_heartbeat_command_system.md`
- `aitasks/t386/t386_3_agent_runner_orchestrator.md`
- `aitasks/t386/t386_4_reporting_cli_cleanup.md`
- `aitasks/t386/t386_5_tui_dashboard.md`
- `aitasks/t386/t386_6_architecture_docs_work2do_guide.md`
- `aitasks/t386/t386_7_website_documentation.md`

**Plan files (content):**
- `aiplans/p386/p386_1_core_data_model_init_add.md`
- `aiplans/p386/p386_2_status_heartbeat_command_system.md`
- `aiplans/p386/p386_3_agent_runner_orchestrator.md`
- `aiplans/p386/p386_4_reporting_cli_cleanup.md`
- `aiplans/p386/p386_5_tui_dashboard.md`
- `aiplans/p386/p386_6_architecture_docs_work2do_guide.md`
- `aiplans/p386/p386_7_website_documentation.md`

### Implementation Steps

1. For each file listed above, apply the naming convention table:
   - Replace `agentset` → `agentcrew` in descriptive text, titles, class names, Python module names, docs paths
   - Replace `agentset` → `crew` in CLI commands, script filenames, function names, branch prefixes, worktree paths, YAML file names, test file names, CLI flags, constants (use `AGENTCREW_` prefix)
   - Replace `AgentSet` → `AgentCrew` in title case
   - Replace `AGENTSET_` → `AGENTCREW_` in constant names
   - Replace `ait agentset add` → `ait crew addtask` (and corresponding script `aitask_agentset_add.sh` → `aitask_crew_addtask.sh`)
   - Replace label `subagents` → `agentcrew` in frontmatter
   - Replace commit prefix `agentset:` → `crew:` in commit message examples
2. Update `aitasks/metadata/labels.txt` if it contains `subagents` — replace with `agentcrew`
3. Commit all changes: `./ait git add aitasks/ aiplans/ && ./ait git commit -m "ait: Rename agentset→agentcrew nomenclature in t386 tasks and plans"`

### Verification
- Grep all modified files for any remaining `agentset` (case-insensitive) to catch missed instances
- Verify frontmatter YAML is still valid (no broken formatting)
- Verify all file references in task descriptions match the new naming convention
