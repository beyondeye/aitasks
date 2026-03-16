---
priority: medium
effort: high
depends: [t386_8]
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-15 10:51
updated_at: 2026-03-16 16:33
---

## Core Data Model & AgentCrew Init/Add Scripts

### Context
This is the foundational child task for the AgentCrew infrastructure (t386). It establishes the data model, file formats, and the two essential scripts for creating and populating agentcrews. All subsequent child tasks depend on this one.

### Goal
Create the shared utility library (`agentcrew_utils.sh`), the `crew_init` and `crew_addtask` scripts, and integrate the `agentcrew` command into the `ait` dispatcher.

### Key Files to Create
- `.aitask-scripts/lib/agentcrew_utils.sh` — Shared bash functions: constants (`AGENTCREW_PREFIX`, `AGENTCREW_DIR=.aitask-crews`), branch/worktree path helpers, agent name validation (`[a-z0-9_]+`), YAML read/write helpers, `detect_circular_deps()` (DFS cycle detection)
- `.aitask-scripts/aitask_crew_init.sh` — Create agentcrew branch + worktree. Args: `--id <id>`, `--batch`, `--add-type <id>:<agent_string>`. Creates branch from current HEAD, `git worktree add` at `.aitask-crews/crew-<id>/`, initializes `_crew_meta.yaml` (config) and `_crew_status.yaml` (initial status: Initializing). Output: `CREATED:<id>`
- `.aitask-scripts/aitask_crew_addtask.sh` — Register subagent. Args: `--crew <id> --name <name> --work2do <file> --depends <a,b> --type <agent_type_id> --batch`. Creates 7 agent files from templates (_work2do.md, _input.md, _output.md, _status.yaml, _instructions.md, _commands.yaml, _alive.yaml). Validates deps exist + no cycles + type exists in agent_types. Output: `ADDED:<name>`
- `tests/test_crew_init.sh` — Tests for init/add/DAG validation

### Key Files to Modify
- `ait` — Add `crew)` case routing to dispatcher
- `.gitignore` — Add `.aitask-crews`

### File Format Definitions

**_crew_meta.yaml** (static config):
```yaml
id: <crew_id>
name: <display_name>
created_at: <timestamp>
created_by: <email>
agents: []
agent_types:
  <type_id>:
    agent_string: <agent>/<model>
    max_parallel: <N>  # 0 = unlimited
```

**_crew_status.yaml** (dynamic state):
```yaml
status: Initializing
progress: 0
started_at:
updated_at: <timestamp>
```

**<agentname>_status.yaml**:
```yaml
agent_name: <name>
agent_type: <type_id>
status: Waiting
depends_on: [agent1, agent2]
created_at: <timestamp>
started_at:
completed_at:
progress: 0
pid:
error_message:
```

### Reference Files for Patterns
- `.aitask-scripts/aitask_lock.sh` — Git branch creation via plumbing, atomic operations
- `.aitask-scripts/aitask_create.sh` — Batch mode argument parsing, structured output
- `.aitask-scripts/aitask_init_data.sh` — Worktree creation pattern
- `.aitask-scripts/lib/terminal_compat.sh` — Guard variables, die/warn/info helpers

### Verification
- `bash tests/test_crew_init.sh`
- `shellcheck .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addtask.sh .aitask-scripts/lib/agentcrew_utils.sh`
- Manual: `./ait crew init --id test1 --add-type impl:claudecode/sonnet4_6 --batch` then `./ait crew addtask --crew test1 --name agent_a --type impl --work2do /dev/null --batch`
