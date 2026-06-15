---
Task: t991_whitelist_aitask_project_resolve_for_code_agents.md
Worktree: /home/ddt/Work/aitasks
Branch: current
Base branch: current
---

# Whitelist `aitask_project_resolve.sh`

## Summary

Fix only the primary autonomous helper, `aitask_project_resolve.sh`. Leave the
secondary `aitask_projects.sh` gap out of scope per user choice.

Use the framework injector rather than manual JSON/rules edits:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_project_resolve.sh
```

## Implementation

- Add `aitask_project_resolve.sh` to all five missing permission touchpoints:
  - `.claude/settings.local.json`
  - `.codex/rules/default.rules`
  - `seed/claude_settings.local.json`
  - `seed/codex_rules.default.rules`
  - `seed/opencode_config.seed.json`
- Preserve each file's existing entry shape and alphabetical ordering by relying
  on `aitask_audit_wrappers.sh`.
- Do not add `aitask_projects.sh`; it remains a separate lower-priority gap.
- After implementation, follow task-workflow Step 9 for archival and cleanup.

## Verification

Before and after the change, verify the primary helper:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_project_resolve.sh
```

Expected after fix: no `MISSING:` lines.

Confirm helper discovery still includes the autonomous helper:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh discover-helpers | rg '^HELPER:aitask_project_resolve.sh$'
```

Review the touched permission files:

```bash
git diff --stat
git diff -- .claude/settings.local.json .codex/rules/default.rules seed/claude_settings.local.json seed/codex_rules.default.rules seed/opencode_config.seed.json
```

Optional out-of-scope check:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_projects.sh
```

Expected: it may still report `MISSING:` because it is intentionally out of
scope.

## Risk

### Code-health risk: low

- The injector already owns this permission format and ordering. The change is
  limited to allowlist entries; severity: low; mitigation: none

### Goal-achievement risk: low

- The current audit reports the exact five missing touchpoints, and the planned
  verification directly checks those entries; severity: low; mitigation: none

## Assumptions

- The existing untracked `.antigravitycli/` and `.opencode/package-lock.json`
  are unrelated and will not be touched.
- No child tasks are needed; this is a single low-effort config bug.

## Final Implementation Notes

- **Actual work done:** Ran the framework whitelist injector for
  `aitask_project_resolve.sh`, adding one allow entry to each of the five planned
  code-agent permission touchpoints.
- **Deviations from plan:** None. `aitask_projects.sh` was intentionally left
  out of scope.
- **Issues encountered:** The primary audit passed after the injector ran. The
  repository also had unrelated local changes in
  `tests/test_skillrun_codex_planmode.sh`, `.agents/skills/aitask-shadow/`,
  `.antigravitycli/`, `.opencode/package-lock.json`, and
  `aiplans/p988_port_aitask_shadow_codex.md`; those were not included in this
  task.
- **Key decisions:** Used `aitask_audit_wrappers.sh apply-helper-whitelist`
  rather than hand-editing the permission files, preserving each touchpoint's
  established format and ordering.
- **Upstream defects identified:** None
