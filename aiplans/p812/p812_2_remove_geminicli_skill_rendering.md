---
Task: t812_2_remove_geminicli_skill_rendering.md
Parent Task: aitasks/t812_remove_gemini_support.md
Sibling Tasks: aitasks/t812/t812_1_*.md, aitasks/t812/t812_3_*.md, aitasks/t812/t812_4_*.md, aitasks/t812/t812_5_*.md
Archived Sibling Plans: aiplans/archived/p812/p812_1_*.md (after t812_1 archived)
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified: []
---

# Plan: Remove geminicli from skill rendering & templating (t812_2)

## Context

Second child of t812. Strips geminicli from the **skill rendering /
templating** layer, deletes the rendered `.gemini/` output tree, removes
geminicli-specific shared helper docs, and cleans related aidocs. The
migration spec `aidocs/geminicli_to_agy.md` is intentionally retained
(needed by t814).

## Key files to modify

| File | Lines (from inventory; verify on read) | Change |
|------|----------------------------------------|--------|
| `.aitask-scripts/lib/skill_template.py` | 38, 53, 121 | Remove `.gemini` path registration |
| `.aitask-scripts/lib/agent_skills_paths.sh` | 14, 36 | Drop `gemini` → `.gemini/skills` mapping |
| `.aitask-scripts/aitask_skill_render.sh` | 37 | Drop `geminicli` agent branch |
| `.aitask-scripts/aitask_skillrun.sh` | 18, 62, 231 | Remove geminicli execution paths |
| `.aitask-scripts/aitask_skill_rerender.sh` | TBD | Drop gemini branches |
| `.aitask-scripts/aitask_skill_verify.sh` | TBD | Drop gemini branches |
| `.aitask-scripts/aitask_audit_wrappers.sh` | 6–11, 32, 36, 99, 111, 137–209, 298, 334, 419, 422, 696, 709, 714 | Remove gemini command rendering + policy logic |
| `.aitask-scripts/aitask_contribute.sh` | 49, 712 | Drop gemini from contribution-area enum |
| `.aitask-scripts/aitask_codemap.sh` | 18 | Remove `.gemini` exclude entry |

## Files / directories to delete

- `.gemini/` (entire tree: `commands/`, `policies/`, `settings.json`,
  `skills/`).
- `.agents/skills/geminicli_planmode_prereqs.md`.
- `.agents/skills/geminicli_tool_mapping.md`.
- `aidocs/geminicli_tools.md`.
- `aidocs/extract_geminicli_tools.sh`.

## Files to RETAIN

- `aidocs/geminicli_to_agy.md` — needed by t814.

## Step-by-step

1. Read each target file at the anchor lines. Update line numbers if
   they have drifted.
2. Remove gemini branches surgically.
3. Delete the listed files and `.gemini/` tree (use `rm -rf .gemini/`
   for the directory; the directory deletion will be committed via
   `./ait git`).
4. Run `./.aitask-scripts/aitask_skill_verify.sh` — confirm remaining
   agents (claude, codex, opencode) render without error.
5. Regenerate any skill goldens affected by the agent-list change.
6. Final grep check:
   ```bash
   grep -rn 'geminicli\|\.gemini/' \
     .aitask-scripts/ .agents/ aidocs/ \
     --include='*.sh' --include='*.py'
   # Expect: only aidocs/geminicli_to_agy.md mentions
   ```

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` — passes for all remaining
   agents.
2. `shellcheck .aitask-scripts/aitask_*.sh` — no new warnings.
3. Any `tests/test_skill*.sh` pass.
4. The `.gemini/` directory is gone from the working tree.
5. `ait skill render` / `aitask_skill_rerender.sh` runs cleanly.

## Step 9 (Post-Implementation)

Standard archival. Final Implementation Notes **must** include the
`### For t814 (add-agy): inverse instructions` subsection.

## Final Implementation Notes (template)

- **Actual work done:** …
- **Deviations from plan:** …
- **Issues encountered:** …
- **Key decisions:** …
- **Upstream defects identified:** None (or list)
- **Notes for sibling tasks:** …

### For t814 (add-agy): inverse instructions

- **Files re-touched by agy:** (fill with file list + line ranges).
- **Pattern removed (anchor example):** (e.g., the `geminicli` case in
  `agent_skills_paths.sh` that mapped to `.gemini/skills`).
- **Inverse instruction:** to add agy, mirror the codex entry in
  `agent_skills_paths.sh` — agy maps to `.agents/skills` (same as
  codex). The rendered file location collides with codex; rely on
  t813's agent-suffix mechanism to disambiguate (e.g.,
  `.agents/skills/<name>-<profile>-agy-/SKILL.md`). Update tool-name
  references per `aidocs/geminicli_to_agy.md`:
  `run_shell_command` → `run_command`, `web_fetch` →
  `read_url_content`.
- **Hidden coupling discovered during removal:** (golden regens,
  cross-references between skill_template.py and
  agent_skills_paths.sh, etc).
