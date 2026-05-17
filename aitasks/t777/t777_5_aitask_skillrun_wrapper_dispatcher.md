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
2. `exec`s the agent CLI with the **user-facing slash-command form** `'/<skill> --profile <profile> <args>'`. The stub at the no-suffix path handles the `--profile` override per the t777_3 design (`stub-skill-pattern.md` §3h). The wrapper does NOT invoke the rendered slash command (`/<skill>-<profile>-`) directly — that path is only auto-discoverable in Claude and not in Gemini/OpenCode/Codex, so dispatching through the stub is the only cross-agent-compatible mechanism.

This wrapper is the entry point for shell users and for the `AgentCommandScreen` TUI (t777_17). It does NOT use `claude -p` (per [[feedback_avoid_claude_p_for_skill_invocation]]).

Also supports `--profile-override <yaml>` for the AgentCommandScreen per-run editor (t777_17). The override mechanism writes a tempfile under `aitasks/metadata/profiles/local/<unique>.yaml` (auto-discovered by `aitask_scan_profiles.sh`), invokes the stub with `--profile <unique>`, and registers an EXIT trap to delete the tempfile after the agent process exits.

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
- `--profile-override <yaml>`: merge the override YAML on top of the resolved profile, write the merged profile as `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` (auto-discovered by `aitask_scan_profiles.sh`), and pass `--profile _skillrun_<unique>` to the stub via ARGUMENTS. Register an EXIT trap to delete the tempfile after the agent process exits.
- (Pre-warming render is optional — the stub itself runs `ait skill render` on every invocation; skip-if-fresh makes the second render a no-op.)
- Construct the launch command (user-facing slash form; stub handles the `--profile` override):
  ```bash
  # Forwarded args include the optional --profile pair the stub will strip.
  forwarded="--profile ${profile} ${args}"
  case "$agent" in
      claude)   exec claude   "/${skill} ${forwarded}" ;;
      gemini)   exec gemini   "/${skill} ${forwarded}" ;;
      opencode) exec opencode "/${skill} ${forwarded}" ;;
      codex)    exec codex    "/${skill} ${forwarded}" ;;  # see Codex note below
  esac
  ```
  Codex note: Codex CLI has no slash commands; the wrapper instead synthesizes a one-shot prompt prefix that instructs Codex to load `.agents/skills/<skill>/SKILL.md` and follow it with the forwarded args. Verify the exact Codex prompt-prefix syntax at impl time.
- `--dry-run`: print the synthesized launch command, do NOT exec.

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
   - The synthesized launch command `claude '/aitask-pick --profile fast 777'`
2. `ait skillrun pick --profile fast 777` end-to-end (after t777_6) launches claude with the user-facing slash command; the stub dispatches to the rendered fast variant.
3. Profile autodetection: `ait skillrun pick 777` (no --profile) uses the resolver and forwards `--profile <resolved>` through ARGUMENTS.
4. Agent autodetection: `ait skillrun pick 777` (no --agent) tries claude → codex → gemini → opencode based on PATH.
5. `--profile-override` correctly merges to `profiles/local/_skillrun_*.yaml`, the agent process picks it up via the stub, and the tempfile is deleted on EXIT.
6. `shellcheck .aitask-scripts/aitask_skillrun.sh` clean.
7. The 5 whitelist files contain the new entries.
