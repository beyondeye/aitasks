---
priority: medium
effort: low
depends: [2, 16]
issue_type: feature
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:11
updated_at: 2026-05-17 12:12
---

## Context

Depends on t777_2 (renderer) and t777_16 (extracted `ProfileEditScreen` widget).

When a profile YAML is modified (e.g. via `ait settings` profile editor, or via the per-run `AgentCommandScreen` editor in t777_17, or by hand-editing the file), all per-profile rendered skill directories for that profile become stale. The framework needs both:

1. **Lazy invalidation** (already covered by t777_2's "skip-if-fresh" mtime check — render re-runs when profile YAML mtime > rendered SKILL.md mtime). This handles the "user edits profile YAML by hand" case and the "wrapper invocation after a settings edit" case.

2. **Eager invalidation** (this child): when the profile is modified through any UI in the framework (settings TUI, AgentCommandScreen edit-modal), immediately delete the affected per-profile rendered directories. Belt-and-suspenders on top of the lazy check. Surfaces stale-render bugs immediately and avoids confusion from old content lingering on disk.

This child adds:
- A helper script that deletes per-profile rendered directories for one profile
- A `ProfileEditScreen.on_save` hook (extracted widget from t777_16) that calls the helper automatically
- An `ait skill invalidate <profile>` CLI for manual use

## Key Files to Modify

- `.aitask-scripts/aitask_skill_invalidate.sh` (new) — deletes `<each-agent>/skills/*-<profile>/` directories
- `./ait` (modify) — add `invalidate` subcommand under existing `skill)` case
- `.aitask-scripts/lib/profile_editor.py` (modify — from t777_16) — extend `ProfileEditScreen.on_save` (or equivalent save callback path) to invoke the invalidation helper with the modified profile name
- 5-touchpoint whitelist for `aitask_skill_invalidate.sh`

## Reference Files for Patterns

- `.aitask-scripts/aitask_skill_render.sh` (from t777_2) — the existing "skip-if-fresh" logic stays; this child is complementary
- `.aitask-scripts/lib/agent_skills_paths.sh` (from t777_1) — use `agent_skill_root` + `agent_skill_dir` to compute deletion targets
- `.aitask-scripts/lib/profile_editor.py` (from t777_16) — the save-hook integration point

## Implementation Plan

### 1. `aitask_skill_invalidate.sh`

```bash
#!/usr/bin/env bash
# aitask_skill_invalidate.sh - Delete per-profile rendered skill directories.
#
# Args: <profile_name>
# Walks each agent's skill root and deletes any directory whose name ends in
# "-<profile_name>". Idempotent. Logs each deletion.
set -euo pipefail
# shellcheck source=lib/agent_skills_paths.sh
source "$(dirname "$0")/lib/agent_skills_paths.sh"
# shellcheck source=lib/terminal_compat.sh
source "$(dirname "$0")/lib/terminal_compat.sh"

profile="${1:?usage: aitask_skill_invalidate.sh <profile_name>}"
deleted=0
for agent in claude codex gemini opencode; do
    root="$(agent_skill_root "$agent")"
    [[ -d "$root" ]] || continue
    # Trailing-hyphen rendered-dir convention per t777_3 — match *-<profile>-/,
    # NOT *-<profile>/. The trailing hyphen ensures we never accidentally
    # match an authoring dir (authoring dirs never end with `-`).
    while IFS= read -r -d '' dir; do
        info "Invalidating: $dir"
        rm -rf -- "$dir"
        deleted=$((deleted + 1))
    done < <(find "$root" -maxdepth 1 -type d -name "*-${profile}-" -print0)
done
echo "INVALIDATED:$deleted directories for profile '$profile'"
```

### 2. `ait skill invalidate` dispatch
Extend the existing `skill)` case (from t777_2 + t777_4):
```bash
invalidate) exec "$SCRIPTS_DIR/aitask_skill_invalidate.sh" "$@" ;;
```

### 3. `ProfileEditScreen` save hook
In `lib/profile_editor.py` (extracted by t777_16), the save callback already writes the profile YAML to disk. After the write succeeds, shell out to:
```bash
./.aitask-scripts/aitask_skill_invalidate.sh <profile_name>
```
Use `subprocess.run([...], check=False)` — invalidation failure should not block the save (it's belt-and-suspenders). Log invalidation failures to the TUI's notification area but don't error-out.

This hook fires regardless of which TUI uses `ProfileEditScreen` — both `ait settings` profile edits and `AgentCommandScreen` per-run edits (t777_17) get the eager invalidation for free.

### 4. 5-touchpoint whitelist
Per CLAUDE.md "Adding a New Helper Script" — entries for `aitask_skill_invalidate.sh` in:
- `.claude/settings.local.json`
- `.gemini/policies/aitasks-whitelist.toml`
- `seed/claude_settings.local.json`
- `seed/geminicli_policies/aitasks-whitelist.toml`
- `seed/opencode_config.seed.json`

## Verification Steps

1. `./.aitask-scripts/aitask_skill_invalidate.sh fast` deletes all `<agent>/skills/*-fast-/` directories (trailing-hyphen convention from t777_3).
2. Idempotent: running twice in a row exits cleanly with `INVALIDATED:0` on the second run.
3. `ait skill invalidate fast` works via the dispatcher.
4. End-to-end through `ait settings`: edit a profile, save, observe that the related per-profile directories are deleted; next invocation of the wrapper re-renders fresh.
5. End-to-end through `AgentCommandScreen` per-run edit (after t777_17): edits trigger the same hook (only if the edit saves back to the profile YAML — for per-run overrides written to /tmp, invalidation does NOT fire because the project profile YAML is unchanged).
6. Lazy check from t777_2 still works for the "user edits profile YAML by hand outside the TUI" case.
7. `shellcheck .aitask-scripts/aitask_skill_invalidate.sh` clean.
8. The 5 whitelist files contain the new entries.

## Pitfalls

- **Per-run overrides vs profile saves** — `AgentCommandScreen` writes overrides to `/tmp/ait-run-override-<pid>.yaml`, NOT to the project profile YAML. These do NOT trigger invalidation (and shouldn't — they're one-shot). Only TRUE profile saves (the project YAML being modified) trigger eager invalidation.
- **Concurrency** — if another agent is currently reading a per-profile SKILL.md when invalidation deletes it, the agent's read might fail mid-execution. Mitigation: document "do not edit profiles while agent sessions are actively running skills" in CLAUDE.md.
- **`*-<profile>-` glob (trailing hyphen)** — t777_3's convention requires rendered dirs to end with `-`, so the find glob targets that suffix specifically. Authoring dirs never end with `-` (load-bearing rule audited in t777_3 Step 5), so the glob cannot accidentally hide authoring directories. No additional collision check is needed.
