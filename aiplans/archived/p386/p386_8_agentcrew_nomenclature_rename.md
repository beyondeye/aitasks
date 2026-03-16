---
Task: t386_8_agentcrew_nomenclature_rename.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md through t386_7_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: AgentCrew Nomenclature Rename

## Context
Rename "agentset" terminology to "agentcrew"/"crew" across all t386 task and plan files before implementation begins. No code files exist yet — this is purely a task/plan content update.

## Step 1: Update parent task

Edit `aitasks/t386_subagents_infra.md`:
- Change `labels: [brainstorming, subagents]` → `labels: [brainstorming, agentcrew]`
- In the description body, apply these replacements throughout:
  - `agentset` → `agentcrew` (in descriptive/conceptual text)
  - `agentset_init` → `crew init` (CLI command references)
  - `agentset_add` → `crew addtask` (CLI command references)
  - `agentset branch` → `agentcrew branch`
  - `agent_runner` → `crew runner`
  - `agen_runner` / `agenrunner` → `crew runner` (fix typos too)

## Step 2: Update all child task files

For each of `t386_1` through `t386_7`:

### Frontmatter changes (all tasks):
- `labels: [subagents]` → `labels: [agentcrew]`

### t386_1 content changes:
- Title: "Core Data Model & AgentSet Init/Add Scripts" → "Core Data Model & AgentCrew Init/AddTask Scripts"
- "AgentSet infrastructure" → "AgentCrew infrastructure"
- `agentset_utils.sh` → `agentcrew_utils.sh`
- `AGENTSET_PREFIX` → `AGENTCREW_PREFIX`
- `AGENTSET_DIR=.aitask-agentsets` → `AGENTCREW_DIR=.aitask-crews`
- `aitask_agentset_init.sh` → `aitask_crew_init.sh`
- `aitask_agentset_add.sh` → `aitask_crew_addtask.sh`
- `agentset branch` → `agentcrew branch`
- `.aitask-agentsets/agentset-<id>/` → `.aitask-crews/crew-<id>/`
- `_agentset_meta.yaml` → `_crew_meta.yaml`
- `_agentset_status.yaml` → `_crew_status.yaml`
- `test_agentset_init.sh` → `test_crew_init.sh`
- `agentset)` case routing → `crew)` case routing
- `.aitask-agentsets` → `.aitask-crews`
- `ait agentset init` → `ait crew init`
- `ait agentset add` → `ait crew addtask`
- `--agentset` flag → `--crew` flag
- `agentset: Initialize agentset` → `crew: Initialize crew`
- Structured output stays: `CREATED:<id>`, `ADDED:<name>`
- `agentset_id` → `crew_id`

### t386_2 content changes:
- "AgentSet infrastructure" → "AgentCrew infrastructure"
- `agentset_utils.py` → `agentcrew_utils.py`
- `agentset_status.py` → `agentcrew_status.py`
- `aitask_agentset_status.sh` → `aitask_crew_status.sh`
- `aitask_agentset_command.sh` → `aitask_crew_command.sh`
- `.aitask-scripts/agentset/` → `.aitask-scripts/agentcrew/`
- `AgentSet statuses` → `AgentCrew statuses` / `Crew statuses`
- `AGENTSET_STATUSES` → `CREW_STATUSES`
- `agentset status` → `crew status`
- `_agentset_meta.yaml` → `_crew_meta.yaml`
- `test_agentset_status.sh` → `test_crew_status.sh`
- `compute_agentset_status` → `compute_crew_status`
- `validate_agentset_transition` → `validate_crew_transition`

### t386_3 content changes:
- "AgentSet infrastructure" → "AgentCrew infrastructure"
- `agentset_runner.py` → `agentcrew_runner.py`
- `aitask_agentset_runner.sh` → `aitask_crew_runner.sh`
- `.aitask-scripts/agentset/` → `.aitask-scripts/agentcrew/`
- `--agentset <id>` → `--crew <id>`
- `agentset branch` → `crew branch`
- `_agentset_meta.yaml` → `_crew_meta.yaml`
- `_agentset_status.yaml` → `_crew_status.yaml`
- `agentset status` references → `crew status`
- `test_agentset_runner.sh` → `test_crew_runner.sh`
- `agentset Running` → `crew Running`
- `Transition agentset to Killing` → `Transition crew to Killing`

### t386_4 content changes:
- "AgentSet infrastructure" → "AgentCrew infrastructure"
- `agentset_report.py` → `agentcrew_report.py`
- `aitask_agentset_report.sh` → `aitask_crew_report.sh`
- `aitask_agentset_cleanup.sh` → `aitask_crew_cleanup.sh`
- `.aitask-scripts/agentset/` → `.aitask-scripts/agentcrew/`
- `--agentset <id>` → `--crew <id>`
- `ait agentset` → `ait crew` (in CLI references)
- `AgentSet:` → `Crew:` in report format examples
- `AGENTSET_ID`, `AGENTSET_STATUS`, `AGENTSET_PROGRESS` → `CREW_ID`, `CREW_STATUS`, `CREW_PROGRESS`
- `list_agentsets()` → `list_crews()`
- `.aitask-agentsets/` → `.aitask-crews/`
- `agentset-*` → `crew-*`
- `test_agentset_report.sh` → `test_crew_report.sh`
- `--all-completed` stays (unchanged)

### t386_5 content changes:
- "AgentSet TUI Dashboard" → "AgentCrew TUI Dashboard"
- `agentset_dashboard.py` → `agentcrew_dashboard.py`
- `aitask_agentset_dashboard.sh` → `aitask_crew_dashboard.sh`
- `.aitask-scripts/agentset/` → `.aitask-scripts/agentcrew/`
- `AgentSetManager` → `CrewManager`
- `AgentSetDetailScreen` → `CrewDetailScreen`
- `list_agentsets()` → `list_crews()`
- `load_agentset(id)` → `load_crew(id)`
- `.aitask-agentsets/` → `.aitask-crews/`
- `agentset-*` → `crew-*`
- `ait agentset runner` → `ait crew runner`
- `aitask_agentset_command.sh` → `aitask_crew_command.sh`
- all "agentset" in descriptive text → "agentcrew" or "crew" as appropriate

### t386_6 content changes:
- "AgentSet architecture" → "AgentCrew architecture"
- `agentset_architecture.md` → `agentcrew_architecture.md`
- `agentset_work2do_guide.md` → `agentcrew_work2do_guide.md`
- "AgentSet concept" / "AgentSet lifecycle" → "AgentCrew concept" / "AgentCrew lifecycle"
- `.aitask-agentsets/agentset-<id>/` → `.aitask-crews/crew-<id>/`
- `_agentset_meta.yaml` → `_crew_meta.yaml`
- `_agentset_status.yaml` → `_crew_status.yaml`
- "AgentSet status" → "Crew status"
- all other "agentset" → "agentcrew" or "crew" as appropriate

### t386_7 content changes:
- "AgentSet" → "AgentCrew" in titles and headings
- `ait agentset init/add/status/command/runner/report/cleanup` → `ait crew init/addtask/status/command/runner/report/cleanup`
- `agentset.md` → `crew.md`
- `agentset-dashboard/` → `crew-dashboard/`
- `workflows/multi-agent.md` stays (this name is fine)
- all descriptive "agentset" → "agentcrew"

## Step 3: Update all plan files

Apply the same naming changes from Step 2 to the corresponding plan files:
- `aiplans/p386/p386_1_core_data_model_init_add.md`
- `aiplans/p386/p386_2_status_heartbeat_command_system.md`
- `aiplans/p386/p386_3_agent_runner_orchestrator.md`
- `aiplans/p386/p386_4_reporting_cli_cleanup.md`
- `aiplans/p386/p386_5_tui_dashboard.md`
- `aiplans/p386/p386_6_architecture_docs_work2do_guide.md`
- `aiplans/p386/p386_7_website_documentation.md`

Each plan file has the same content patterns as its corresponding task, plus additional implementation detail. Apply the same find/replace rules.

## Step 4: Update labels.txt (if needed)

Check `aitasks/metadata/labels.txt` — if it contains `subagents`, replace with `agentcrew`.

## Step 5: Commit

```bash
./ait git add aitasks/ aiplans/
./ait git commit -m "ait: Rename agentset→agentcrew nomenclature in t386 tasks and plans"
```

## Step 6: Verify

- `grep -ri "agentset" aitasks/t386/ aiplans/p386/` — should return zero matches
- `grep -ri "subagents" aitasks/t386/ aiplans/p386/` — should return zero matches (except possibly the parent task original brainstorm text where the user wrote it)
- Verify YAML frontmatter parses correctly

## Step 7: Post-Implementation (Step 9)

Archive task, push.

## Final Implementation Notes
- **Actual work done:** Renamed all "agentset" terminology to "agentcrew"/"crew" across 16 files (7 child tasks, 7 plans, parent task, labels.txt). Used a comprehensive sed script with carefully ordered replacements (most specific first) plus manual edge-case fixes.
- **Deviations from plan:** Added fix for `agentcrew)` → `crew)` dispatcher case routing in t386_1 and p386_1 (CLI commands use short form `crew`). Fixed `Agentset-Agnostic` → `Crew-Agnostic` in p386_6. Fixed typo `agenset` → `agentcrew` in parent task.
- **Issues encountered:** Context-dependent replacements needed careful ordering — `agentset` maps to `crew` in CLI/function contexts but `agentcrew` in descriptive text. Resolved by handling all specific patterns before the generic catch-all.
- **Key decisions:** Report format header `AgentSet:` → `Crew:` (short form for output display). Structured output constants (`AGENTSET_ID` etc.) → `CREW_*` (not `AGENTCREW_*`), matching the plan's per-file specifications. Parent task "subagents" in body text left unchanged (refers to individual agents, not the system name).
- **Notes for sibling tasks:** The naming convention is now fully applied. When implementing t386_1-t386_7, use these names: CLI command `ait crew`, scripts `aitask_crew_*.sh`, Python package `.aitask-scripts/agentcrew/`, Python files `agentcrew_*.py`, worktree dir `.aitask-crews/crew-<id>/`, YAML files `_crew_meta.yaml`/`_crew_status.yaml`, constants `AGENTCREW_*` (except structured output which uses `CREW_*`).
