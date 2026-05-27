#!/usr/bin/env bash
# aitask_skill_rerender.sh - Refresh every rendered skill closure for one profile.
#
# Usage: aitask_skill_rerender.sh <profile_name>
#
# Walks each agent's skill root and, for every directory whose name ends in
# "-<profile_name>-" (the trailing-hyphen rendered-dir convention from
# t777_3 / agent_skills_paths.sh), runs
#   aitask_skill_render.sh <skill> --profile <profile> --agent <agent>
# so the renderer's atomic per-file overwrite refreshes the closure in place.
#
# Why re-render instead of `rm -rf`: rendered files may be open in active
# agent sessions. The renderer writes per-file atomically; on Unix the old
# inode keeps serving any already-opened file handles, so a running agent
# does not see ENOENT mid-flow. Deleting the directory tree would not have
# that guarantee.
#
# Skip-if-fresh in the renderer makes redundant calls cheap: when a skill
# is reached via another skill's closure walk it will not re-render on the
# subsequent direct call.
#
# Emits: "RERENDERED:<N> (skill,agent) pairs for profile '<name>'" on stdout.
# Internal helper. Invoked by Python save hooks (settings_app.py,
# agent_command_screen.py) via subprocess and by manual debug runs.
# Not exposed via the `ait` dispatcher and not whitelisted for skill use.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$SCRIPT_DIR/lib/agent_skills_paths.sh"
# shellcheck source=.aitask-scripts/lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

profile="${1:?usage: aitask_skill_rerender.sh <profile_name>}"

rerendered=0
for agent in claude codex gemini opencode; do
    root="$(agent_skill_root "$agent")" || continue
    [[ -d "$root" ]] || continue
    # Shared-root agents emit dirs of the form `<skill>-<profile>-<agent>-`
    # (t834); other agents use the simpler `<skill>-<profile>-` form.
    # The glob and suffix-strip pattern must match what was emitted.
    shared="$(agent_shared_skills_root "$agent")"
    if [[ "$shared" == "true" ]]; then
        find_glob="*-${profile}-${agent}-"
    else
        find_glob="*-${profile}-"
    fi
    while IFS= read -r -d '' dir; do
        base="$(basename "$dir")"
        if [[ "$shared" == "true" ]]; then
            skill="${base%-"${profile}"-"${agent}"-}"
        else
            skill="${base%-"${profile}"-}"
        fi
        [[ "$skill" == "$base" ]] && continue  # paranoia: no suffix match
        # Skip rendered dirs whose authoring template has been removed —
        # the renderer would error and we have nothing to refresh.
        template="$(agent_authoring_template "$skill")"
        if [[ ! -f "$template" ]]; then
            info "Skipping orphaned rendered dir (no template at $template): $dir"
            continue
        fi
        info "Re-rendering: $skill (profile=$profile, agent=$agent)"
        "$SCRIPT_DIR/aitask_skill_render.sh" "$skill" \
            --profile "$profile" --agent "$agent"
        rerendered=$((rerendered + 1))
    done < <(find "$root" -maxdepth 1 -type d -name "$find_glob" -print0)
done

echo "RERENDERED:$rerendered (skill,agent) pairs for profile '$profile'"
