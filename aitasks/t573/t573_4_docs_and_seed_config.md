---
priority: medium
effort: low
depends: [t573_3]
issue_type: documentation
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 11:01
updated_at: 2026-04-23 17:54
---

## Context

Finalizes t573 by keeping the design docs and seed configs in sync with
the new `initializer` agent type. Depends on t573_1 (the new agent type
must exist in code before it can be documented).

## Key Files to Modify

- `aidocs/brainstorming/brainstorm_engine_architecture.md` — document
  the sixth agent type and the import-file init flow.
- `aitasks/metadata/codeagent_config.json` — add a default
  `brainstorm-initializer` entry under `defaults`. Without it,
  `get_agent_types()` (`brainstorm_crew.py:72-86`) raises at startup.
- `seed/codeagent_config.seed.json` — mirror of the above, so new
  projects bootstrapped via `ait setup` get the key.

## Reference Files for Patterns

- Existing documentation of the five agent types in
  `aidocs/brainstorming/brainstorm_engine_architecture.md` — §5
  (AgentCrew Integration) and §7 (Orchestration Flow).
- High-Level Architecture ASCII art —
  `brainstorm_engine_architecture.md:43-73`.
- Existing `brainstorm-<type>` keys in
  `aitasks/metadata/codeagent_config.json` (read the file to pick
  the same default value used for explorer, since initializer does
  analytical markdown reformatting, similar in shape).
- Seed config — `seed/codeagent_config.seed.json` (mirror of above
  for new projects).

## Implementation Plan

1. **Config keys** (runtime + seed):
   - Read the current `brainstorm-explorer` value in
     `aitasks/metadata/codeagent_config.json` — reuse that exact
     model as the default for `brainstorm-initializer`. Rationale:
     the initializer agent needs strong reading / summarization
     capabilities, same as explorer.
   - Add the same key to `seed/codeagent_config.seed.json` so
     `ait setup` picks it up for new projects.

2. **Design doc** — add:
   - A new subsection under §5 "AgentCrew Integration" describing
     the `initializer` agent, its single-purpose mandate, its
     `max_parallel: 1` / `launch_mode: interactive` defaults.
   - A new subsection under §7 "Orchestration Flow" titled
     "Initialization with an imported proposal" that walks the user
     through:
     `ait brainstorm init <task> --proposal-file <path>` or
     TUI "Import Proposal…" → placeholder n000_init → agent runs
     → `apply_initializer_output()` → user sees structured
     n000_init.
   - An updated ASCII block diagram including the initializer.

3. **User-facing docs stay in "current state" form** — no "this used
   to be different" language per CLAUDE.md Documentation Writing
   section. State the current behaviour positively.

## Verification

- `grep -rn "initializer" aidocs/brainstorming/` returns the new
  subsections.
- `python3 -c "import json; d=json.load(open('aitasks/metadata/codeagent_config.json'));
  print(d['defaults']['brainstorm-initializer'])"` prints the value.
- `diff aitasks/metadata/codeagent_config.json seed/codeagent_config.seed.json`
  — only expected divergences remain (no `brainstorm-initializer`
  skew).
- Re-running `ait brainstorm init <task> --proposal-file <file>` from
  t573_2 still works (no regression from the config change).

## Notes for Sibling Tasks

- None — this is the last code-touching child before the manual-
  verification sibling (t573_5, to be added by the parent planner).
