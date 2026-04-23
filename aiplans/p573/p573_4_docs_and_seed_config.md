---
Task: t573_4_docs_and_seed_config.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_1_*.md, aitasks/t573/t573_2_*.md, aitasks/t573/t573_3_*.md
Archived Sibling Plans: aiplans/archived/p573/p573_*_*.md
Worktree: (none — default profile works on current branch)
Branch: main
Base branch: main
---

# t573_4 — Docs + seed config for the `initializer` agent type

## Context

Keeps the design documentation and seed configs in lock-step with the
new agent type introduced in t573_1. Without the `brainstorm-initializer`
default in `codeagent_config.json`, `get_agent_types()` raises on session
init (see `brainstorm_crew.py:72-86`).

## Implementation steps

### 1. Runtime config

Edit `aitasks/metadata/codeagent_config.json`. Under `defaults`, add a
`brainstorm-initializer` key using the exact same value as
`brainstorm-explorer` (the initializer has the same analytical shape
— long-read + structured output).

Do not edit `codeagent_config.local.json` (that's the gitignored
per-user override).

### 2. Seed config

Edit `seed/codeagent_config.seed.json` with the identical key/value so
new projects bootstrapped via `ait setup` pick it up.

Sanity-check that the two files are aligned (no unexpected drift
outside of this key):

```bash
diff aitasks/metadata/codeagent_config.json seed/codeagent_config.seed.json
```

### 3. Design doc: `aidocs/brainstorming/brainstorm_engine_architecture.md`

Three edits:

(a) **§5 AgentCrew Integration** — add a subsection "Initializer agent"
describing the sixth agent type:
- Purpose: reformat an imported markdown file into a structured
  `n000_init` node at session init time.
- Defaults: `max_parallel: 1`, `launch_mode: interactive`.
- Input: path of the imported proposal + task file.
- Output: sectioned proposal (`br_proposals/n000_init.md`) + flat YAML
  node metadata (`br_nodes/n000_init.yaml`) with dimensions.

(b) **§7 Orchestration Flow** — new subsection "Initialization with an
imported proposal" walking through the two entry points (CLI
`--proposal-file` and TUI "Import Proposal…"), the placeholder-first
seeding, the interactive agent run, and `apply_initializer_output()`.

(c) **High-level architecture ASCII art** (lines 43-73) — insert
`initializer` in the agent-type list.

State the current behaviour **positively** — no "previously" /
"now" / "used to be" language (per CLAUDE.md Documentation Writing
section).

### 4. Crew `--add-type` consistency

Re-confirm that `aitask_brainstorm_init.sh:128-134` includes the
initializer `--add-type` line added in t573_2 (no change expected
here; this is a sanity check only).

## Verification

- `grep -n "initializer" aidocs/brainstorming/brainstorm_engine_architecture.md`
  shows the new subsections.
- `python3 -c "import json; d=json.load(open('aitasks/metadata/codeagent_config.json'));
  print(d['defaults']['brainstorm-initializer'])"` prints the expected value.
- `python3 -c "import json; d=json.load(open('seed/codeagent_config.seed.json'));
  print(d['defaults']['brainstorm-initializer'])"` prints the same value.
- `ait brainstorm init <fresh_task> --proposal-file /tmp/x.md` from
  t573_2 still succeeds (no regression from config changes).
- No "previously" / "now" / "used to be" phrasing in the doc diff
  (`./ait git diff aidocs/brainstorming/`).

## Notes for sibling tasks

- None. This is the last code/doc-touching child; the parent planner
  adds a manual-verification aggregate sibling (t573_5) after this
  child lands.
