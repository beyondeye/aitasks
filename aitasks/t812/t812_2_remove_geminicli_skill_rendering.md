---
priority: medium
effort: medium
depends: [t812_1]
issue_type: chore
status: Implementing
labels: [geminicli, skills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 12:06
updated_at: 2026-05-27 16:24
---

## Context

Second child of t812 (remove all geminicli support). Companion to t812_1
(agent infrastructure removal). This child strips geminicli from the
**skill rendering and templating** layer, deletes the rendered `.gemini/`
output tree, removes geminicli-specific shared helper docs, and cleans
related aidocs.

This child does NOT touch agent identity registrations (t812_1),
setup/install/release infrastructure (t812_3), or user-facing docs
(t812_4).

## Key files to modify

- `.aitask-scripts/lib/skill_template.py` — remove `.gemini` path
  registration (lines 38, 53, 121).
- `.aitask-scripts/lib/agent_skills_paths.sh` — drop the `gemini` →
  `.gemini/skills` path mapping (lines 14, 36).
- `.aitask-scripts/aitask_skill_render.sh` — drop the `geminicli`
  agent branch (line 37).
- `.aitask-scripts/aitask_skillrun.sh` — remove geminicli execution
  paths (lines 18, 62, 231).
- `.aitask-scripts/aitask_skill_rerender.sh` — drop gemini branches.
- `.aitask-scripts/aitask_skill_verify.sh` — drop gemini branches.
- `.aitask-scripts/aitask_audit_wrappers.sh` — remove gemini command
  rendering and policy logic (lines 6–11, 32, 36, 99, 111, 137–209,
  298, 334, 419, 422, 696, 709, 714).
- `.aitask-scripts/aitask_contribute.sh` — drop gemini from the
  contribution-area enum (lines 49, 712).
- `.aitask-scripts/aitask_codemap.sh` — remove the `.gemini` exclude
  entry (line 18) along with the directory deletion below.

## Files / directories to delete

- `.gemini/` directory tree (entire) — `commands/`, `policies/`,
  `settings.json`, `skills/`.
- `.agents/skills/geminicli_planmode_prereqs.md`.
- `.agents/skills/geminicli_tool_mapping.md`.
- `aidocs/geminicli_tools.md`.
- `aidocs/extract_geminicli_tools.sh`.

## Files to RETAIN (do NOT delete in this child)

- `aidocs/geminicli_to_agy.md` — needed by t814 as the migration spec.
  Delete only as part of t814 post-implementation cleanup.

## Reference files for patterns

- For each Python/shell branch removed, locate the codex equivalent
  in the same file. That's the pattern t814 will reuse for agy.

## Implementation plan

1. Read each target file, identify the geminicli touchpoints (use
   the line numbers above as starting anchors — they may have drifted
   slightly).
2. Remove each touchpoint cleanly; do not leave dangling references
   or empty `if/elif/else` branches.
3. Delete the directories and files listed above.
4. Run `./.aitask-scripts/aitask_skill_verify.sh` to confirm the
   remaining agents (claude, codex, opencode) still render without
   error.
5. Regenerate any skill goldens affected by the agent-list change
   (per `aidocs/skill_authoring_conventions.md` golden-regen rule).
6. Verify no references remain:

```bash
grep -rn 'geminicli\|\.gemini/' \
  .aitask-scripts/ .agents/ aidocs/ \
  --include='*.sh' --include='*.py'
# Expect: empty (or only references in the retained
# aidocs/geminicli_to_agy.md)
```

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` — passes for all
   remaining agents.
2. `shellcheck .aitask-scripts/aitask_*.sh` — no new warnings.
3. `tests/test_skill*.sh` (any skill-rendering tests) pass.
4. The `.gemini/` directory is gone from the working tree.
5. `ait skill render` / `aitask_skill_rerender.sh` runs cleanly
   without crashing on the missing gemini agent.

## Final implementation notes — REQUIRED subsection

Include a top-level subsection titled exactly:

```
### For t814 (add-agy): inverse instructions
```

Contents:
- **Files re-touched by agy:** repeat the file list with absolute
  line ranges where modified.
- **Pattern removed (anchor example):** the shape of the geminicli
  templating code that was deleted (function name, agent enum,
  path-mapping table entry).
- **Inverse instruction:** "to add agy: register `.agents/skills/`
  path mapping for `agy` in `agent_skills_paths.sh`, mirroring the
  existing codex entry; render-target filename gets agent suffix per
  t813's enhancement (e.g., `.agents/skills/<name>-<profile>-agy-/SKILL.md`)".
- **Hidden coupling discovered during removal:** golden files
  regenerated, any cross-references between `skill_template.py` and
  `agent_skills_paths.sh`, etc.
