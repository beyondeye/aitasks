---
priority: high
effort: medium
depends: [t777_4]
issue_type: feature
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 11:58
updated_at: 2026-05-17 11:58
---

## Context

Depends on t777_2. Adds the `ait skillrun` wrapper script that:

1. Resolves agent + profile.
2. Calls `ait skill render` to materialize the per-profile SKILL.md on disk (the wrapper bypasses the stub-dispatch path).
3. `exec`s the agent CLI with the natural slash-command form `'/<skill>-<profile> <args>'`.

This wrapper is the entry point for shell users and for the `AgentCommandScreen` TUI (t777_17). It does NOT use `claude -p` (per [[feedback-avoid-claude-p-for-skill-invocation]]).

Also supports `--profile-override <yaml>` for the AgentCommandScreen per-run editor (t777_17).

## Key Files to Modify

- `.aitask-scripts/aitask_skillrun.sh` (new) — wrapper script
- `./ait` (modify) — add `skillrun)` case-statement entry
- 5-touchpoint whitelist for `aitask_skillrun.sh`

## Reference Files for Patterns

- `.aitask-scripts/lib/python_resolve.sh` — `require_ait_python`
- `.aitask-scripts/lib/agent_skills_paths.sh` (from t777_1)
- `.aitask-scripts/aitask_skill_resolve_profile.sh` (from t777_1)
- `.aitask-scripts/aitask_skill_render.sh` (from t777_2)
- `.aitask-scripts/lib/agent_launch_utils.py` — pattern for agent autodetection + launch command construction

## Implementation Plan

### 1. aitask_skillrun.sh
Args: `<skill> [--profile <name>] [--agent <name>] [--profile-override <yaml>] [--dry-run] [-- <skill-args>...]`

Behavior:
- `--agent` defaults to `$AIT_AGENT` env, else PATH-autodetect (try `claude` → `codex` → `gemini` → `opencode`)
- `--profile` defaults to `./.aitask-scripts/aitask_skill_resolve_profile.sh <skill>`
- `--profile-override <yaml>`: merge the override YAML on top of the resolved profile before render. After merging, write the merged profile to a tempfile and pass to renderer. Delete the override file after render.
- Call `./.aitask-scripts/aitask_skill_render.sh <skill> --profile <name> --agent <agent>` (renders into the per-profile dir + any referenced shared procs)
- Construct the launch command:
  ```bash
  case "$agent" in
      claude)   exec claude   "/${skill}-${profile} ${args}" ;;
      codex)    exec codex    "/${skill}-${profile} ${args}" ;;
      gemini)   exec gemini   "/${skill}-${profile} ${args}" ;;
      opencode) exec opencode "/${skill}-${profile} ${args}" ;;
  esac
  ```
  (Verify exact CLI launch syntax for each agent at impl time — codex/gemini/opencode may differ slightly.)
- `--dry-run`: print the render command + the launch command, do NOT exec.

### 2. ait dispatcher
Add near `settings)`, before `setup)`:
```bash
skillrun)    shift; exec "$SCRIPTS_DIR/aitask_skillrun.sh" "$@" ;;
```
Update `show_usage` to mention `skillrun`.

### 3. 5-touchpoint whitelist
Per CLAUDE.md "Adding a New Helper Script" — entries for `aitask_skillrun.sh`.

## Verification Steps

1. `ait skillrun pick --profile fast --agent claude --dry-run 777` prints:
   - The `ait skill render pick --profile fast --agent claude` invocation
   - The `claude '/aitask-pick-fast 777'` launch command
2. `ait skillrun pick --profile fast 777` end-to-end (after t777_6) launches claude with the rendered profile-specific skill.
3. Profile autodetection: `ait skillrun pick 777` (no --profile) uses the resolver.
4. Agent autodetection: `ait skillrun pick 777` (no --agent) tries claude → codex → gemini → opencode based on PATH.
5. `--profile-override` correctly merges and the override file is deleted after render.
6. `shellcheck .aitask-scripts/aitask_skillrun.sh` clean.
7. The 5 whitelist files contain the new entries.
