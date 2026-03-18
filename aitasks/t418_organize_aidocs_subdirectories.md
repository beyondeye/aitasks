---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: []
created_at: 2026-03-18 12:29
updated_at: 2026-03-18 12:29
---

## Organize aidocs into subdirectories

Move documents in `aidocs/` into topic-specific subdirectories for better organization.

### Changes

1. **Create `aidocs/brainstorming/`** and move:
   - `aidocs/aitask_redesign_spec.md` → `aidocs/brainstorming/aitask_redesign_spec.md`
   - `aidocs/building_an_iterative_ai_design_system.md` → `aidocs/brainstorming/building_an_iterative_ai_design_system.md`

2. **Create `aidocs/agentcrew/`** and move:
   - `aidocs/agentcrew_architecture.md` → `aidocs/agentcrew/agentcrew_architecture.md`
   - `aidocs/agentcrew_work2do_guide.md` → `aidocs/agentcrew/agentcrew_work2do_guide.md`

### Notes

- The brainstorming docs are currently untracked (use `mv` + `git add`)
- The agentcrew docs are tracked (use `git mv`)
- Check for references to moved files in task files and update paths if needed (e.g., `aitasks/t399_aitaskredesign.md` references agentcrew docs by filename)
