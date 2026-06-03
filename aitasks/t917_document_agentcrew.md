---
priority: medium
effort: high
depends: []
issue_type: documentation
status: Ready
labels: [documentation]
created_at: 2026-06-02 16:57
updated_at: 2026-06-02 16:57
boardcol: now
boardidx: 80
---

## Context

Spun out of t914 (command-reference docs audit). The entire **agentcrew** concept
(`ait crew`) is currently undocumented on the website. t914 explicitly carved it
out as a substantial separate effort.

## Goal

Document agentcrew for end users:

- A **concept page** explaining what agentcrews are and when to use them.
- A **`ait crew` subcommand reference** covering each subcommand:
  `init`, `addwork`, `setmode`, `status`, `command`, `runner`, `report`,
  `cleanup`, `dashboard`, `logview`.
- Wire it into the command reference index (`commands/_index.md`) and, if a new
  workflow/concept page is added, add the manual bullet to the relevant
  hand-curated `_index.md` grouping (workflows index body is not auto-generated).
- Consider whether the crew dashboard belongs in the TUIs section.

## Conventions

- Current-state-only prose; generic placeholder project names; no "sister" repo
  terminology.
- Source of truth is the `ait crew` dispatch in `ait` and the
  `aitask_crew_*.sh` scripts.
