---
Task: t777_20_profile_modification_invalidation.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_27_recover_runtime_skills_and_parity_tests.md, aitasks/t777/t777_28_dedup_template_branches_common_proc_and_macros.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_12_convert_aitask_pr_import.md, aiplans/archived/p777/p777_13_convert_aitask_revert.md, aiplans/archived/p777/p777_14_convert_aitask_pickrem.md, aiplans/archived/p777/p777_15_convert_aitask_pickweb.md, aiplans/archived/p777/p777_16_extract_profile_editor_widget.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_29_fix_opencode_skill_legacy_pointers.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 12:06
---

# Plan: t777_20 — Profile-modification eager re-render

## Context

When a user edits an execution profile YAML through any framework TUI (the `ait settings` Profiles tab, or the per-run "Save persistent" branch in `AgentCommandScreen`), every per-profile rendered skill closure for that profile (`<agent>/skills/*-<profile>-/`) becomes stale. Today, staleness is caught only on the next wrapper invocation by `aitask_skill_render.sh`'s "skip-if-fresh" mtime check. That works for correctness, but the rendered files lingering on disk between save and next invocation are confusing if the user inspects the rendered dirs directly.

This child task adds **eager synchronous re-render** at the save sites so the on-disk view matches the saved YAML immediately. The lazy mtime check still covers the "user edits YAML by hand outside the TUI" case unchanged, and continues to cover cross-machine sync (a `git pull` of a new profile YAML never fires the eager path).

## Why re-render and not invalidate (rm -rf)

The original task description called for a `aitask_skill_invalidate.sh` helper that deletes every per-profile rendered directory. That approach has a real race against active agent sessions:

- The renderer (`aitask_skill_render.sh` → `skill_template.py walk-write`) uses **atomic per-file overwrites**. On Unix, an agent that already opened `SKILL.md` keeps reading the old inode through its existing file handle, so an overwrite mid-flow is safe.
- A `rm -rf` on the rendered directory is strictly **more destructive**: an agent that has not yet opened a referenced procedure file (e.g. `task-workflow-fast-/agent-attribution.md`) would get `ENOENT` the next time it tries.

Re-rendering through the regular renderer code path inherits the atomic-overwrite guarantee, so concurrently running agents are not affected.

**The helper is internal-only — no `ait` dispatcher entry, no policy whitelist.** It is shelled out from Python save hooks by its full path (`./.aitask-scripts/aitask_skill_rerender.sh`). The `ait` dispatcher is reserved for commands a human would plausibly type manually. The 7-touchpoint policy whitelist is required only for scripts called from inside an AI-agent skill — this one is called from Python TUI subprocess and from manual shell, neither of which consults the per-agent allow-lists.

## Critical files

| Action | Path |
|--------|------|
| Create | `.aitask-scripts/aitask_skill_rerender.sh` |
| Create | `tests/test_skill_rerender.sh` |
| Modify | `.aitask-scripts/settings/settings_app.py` (hook in `ConfigManager.save_profile`) |
| Modify | `.aitask-scripts/lib/agent_command_screen.py` (hook in `_on_profile_saved_persistent`) |

No edits to `ait`. No whitelist edits. `_on_profile_saved_one_shot()` is deliberately untouched: one-shot overrides write to `_skillrun_<pid>_<ts>.yaml` and do not represent edits to a base profile, so they must not trigger a re-render of base-profile dirs.

## Implementation

### 1. `aitask_skill_rerender.sh`

```bash
#!/usr/bin/env bash
# aitask_skill_rerender.sh - Refresh every rendered skill closure for one profile.
#
# Usage: aitask_skill_rerender.sh <profile_name>
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
    while IFS= read -r -d '' dir; do
        base="$(basename "$dir")"
        skill="${base%-"${profile}"-}"
        [[ "$skill" == "$base" ]] && continue
        template="$(agent_authoring_template "$skill")"
        if [[ ! -f "$template" ]]; then
            info "Skipping orphaned rendered dir (no template): $dir"
            continue
        fi
        info "Re-rendering: $skill (profile=$profile, agent=$agent)"
        "$SCRIPT_DIR/aitask_skill_render.sh" "$skill" \
            --profile "$profile" --agent "$agent"
        rerendered=$((rerendered + 1))
    done < <(find "$root" -maxdepth 1 -type d -name "*-${profile}-" -print0)
done
echo "RERENDERED:$rerendered (skill,agent) pairs for profile '$profile'"
```

Notes:
- No `--force` to the renderer: the profile YAML mtime was just bumped by the save, so the renderer's skip-if-fresh check naturally detects staleness and rebuilds. Subsequent calls for skills already refreshed via another skill's closure walk become no-ops.
- Orphaned rendered dirs (rendered tree present, authoring template missing) are explicitly skipped — re-rendering them would fail. The helper does not delete them either; they wait for a separate cleanup pass.
- 4-agent loop matches the framework convention (no separate agent-list constant exists; `_maybe_rerender_pickrem` uses the same literal list).

### 2. Hook in `ConfigManager.save_profile` (Settings TUI)

After the YAML write completes, call the helper via `subprocess.run` with `check=False, timeout=60`. `subprocess` is already imported in `settings_app.py` (used by `_maybe_rerender_pickrem`). Any OSError or timeout is silently ignored — the renderer's lazy mtime check is the correctness safety net.

### 3. Hook in `_on_profile_saved_persistent` (AgentCommandScreen)

`agent_command_screen.py` already has the persistent-save sink (added by t777_17). Add `import subprocess` to the stdlib imports, then call the helper right after the success notify and before the override-clear / row-refresh block. Failures notify the user but do not block.

`_on_profile_saved_one_shot()` is intentionally NOT hooked: one-shot overrides are throwaway YAMLs whose lifetime does not justify regenerating base-profile rendered closures.

### 4. Automated tests — `tests/test_skill_rerender.sh`

Modeled on `tests/test_skill_verify.sh`. The scratch workspace uses prefix `_t777_20_test_` and an `EXIT` trap for cleanup. Test coverage (8 cases, ~27 asserts):

1. Helper exists and is executable.
2. No-arg invocation fails with non-zero exit + usage message.
3. Empty state → `RERENDERED:0`.
4. **Orphaned rendered dirs (no authoring template) are skipped, not deleted.** Seeds `_t777_20_test_orphan_a-<profile>-/` etc. across all 4 agent roots; asserts dirs survive and helper reports `RERENDERED:0`.
5. Unknown profile name → no-op `RERENDERED:0`.
6. Missing agent root (rename one away) is handled gracefully; restored in cleanup.
7. **End-to-end real-skill re-render.** Uses the project's real `aitask-pick` skill and `fast` profile (skipped if either fixture missing). Bumps `fast.yaml` mtime, runs the helper, asserts the rendered `aitask-pick-fast-/SKILL.md` mtime moved forward — confirms the renderer was actually invoked end-to-end.
8. `shellcheck -x` clean.

Cleanup trap removes all `_t777_20_test_*` directories from every agent root, and restores `.opencode/skills` if test 6 renamed it.

## Verification

1. Automated tests pass: `bash tests/test_skill_rerender.sh` reports `FAIL: 0`.
2. Settings TUI end-to-end (manual): `ait settings` → Profiles tab → edit `fast` → Save. Watch the rendered files under `.claude/skills/*-fast-/`: their mtimes advance and content reflects the YAML edits.
3. AgentCommandScreen end-to-end (manual): in `ait board`, push an agent-command screen, edit profile, click "Save persistent". Same observation: rendered files refresh in place. "Save as one-shot" does NOT trigger a refresh.
4. Lazy check still works: hand-edit `aitasks/metadata/profiles/fast.yaml` outside any TUI; do not run rerender; trigger a wrapper — renderer's skip-if-fresh still catches the mtime change and re-renders.
5. `shellcheck -x .aitask-scripts/aitask_skill_rerender.sh` clean.

## Pitfalls

- **One-shot overrides are intentionally excluded.** Saved-as-one-shot files use `_skillrun_<pid>_<ts>` filenames; rerendering for those throwaway profiles would create transient rendered dirs that the next prune cycle would remove anyway.
- **Cross-machine sync still relies on the lazy path.** A `git pull` that brings in a new profile YAML never triggers the eager hook — only the user who *typed the save* gets the synchronous refresh. The lazy mtime check covers the puller.
- **Orphaned rendered dirs are preserved, not cleaned up.** If a skill's authoring template is removed but its rendered dirs persist, the helper logs and skips them. A separate cleanup pass (or a future enhancement) would be needed to garbage-collect orphans.
- **Trailing-hyphen glob is load-bearing.** The `*-<profile>-` suffix ensures the helper never iterates authoring directories (which by design never end with `-`, gitignored as `*-/`). Do NOT relax the glob.

## Post-implementation

Step 9 (post-implementation) of the task-workflow handles archival, branch cleanup, and push. Per profile 'fast' on current branch — no worktree created, no branch to merge.

## Post-Review Changes

### Change Request 1 (2026-05-25)
- **Requested by user:** Concern raised about the original `aitask_skill_invalidate.sh` design — race against running agents that have rendered procedure files open, plus the realization that eager invalidation does not provide correctness (the lazy mtime check already does).
- **Changes made:** Replaced the rm-rf-based invalidation helper with `aitask_skill_rerender.sh`, which calls the regular renderer (atomic per-file overwrites). Updated both save hooks. Rewrote test suite with an end-to-end test that verifies real re-render of `aitask-pick-fast-/SKILL.md`.
- **Files affected:** Created `.aitask-scripts/aitask_skill_rerender.sh` and `tests/test_skill_rerender.sh`; removed the never-committed `aitask_skill_invalidate.sh` and `test_skill_invalidate.sh`; updated hooks in `.aitask-scripts/settings/settings_app.py` and `.aitask-scripts/lib/agent_command_screen.py` (the latter's prior `aitask_skill_invalidate.sh` reference came in via the t777_17 commit).

## Final Implementation Notes

- **Actual work done:** New helper `aitask_skill_rerender.sh` (61 lines, shellcheck-x clean). Two save-hook patches: 11-line block in `settings_app.py::ConfigManager.save_profile`, 14-line block in `agent_command_screen.py::_on_profile_saved_persistent` (which already had its `import subprocess` and the old hook from t777_17 — converted in place). Test suite `tests/test_skill_rerender.sh` (8 test groups, 27 asserts including end-to-end re-render of `aitask-pick` against the real `fast` profile, all pass).
- **Deviations from plan:** The mid-implementation pivot from invalidate (rm-rf) to re-render (synchronous renderer call) was driven by recognizing the race against running agents. See Post-Review Changes. Also dropped the original task description's `ait skill invalidate` CLI surface and 7-touchpoint whitelist entirely (the helper is never invoked from inside an agent skill, only from Python TUI subprocess).
- **Issues encountered:** `shellcheck -x` flagged `SC2295` on `${base%-${profile}-}` — fixed by quoting the inner expansion: `${base%-"${profile}"-}`. First test draft had a decoy "authoring directory" with a real `SKILL.md.j2` that made an "orphan" test case appear non-orphaned and trigger a render error — renamed orphans to use a distinct `_t777_20_test_orphan_*` prefix so they could never collide with seeded templates.
- **Key decisions:** No `--force` to the renderer: the profile YAML mtime was just bumped by the save, so skip-if-fresh naturally rebuilds stale files and avoids redundant work when a skill is reached transitively via another skill's closure walk. Hook timeout raised from the original 10 s to 60 s to give the renderer enough time across all skills × 4 agents on the first uncached run.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The orphan-rendered-dir cleanup (rendered tree present, authoring template gone) is not handled — a future task could add a periodic prune. The 4-agent loop literal `claude codex gemini opencode` recurs across multiple helpers (`_maybe_rerender_pickrem`, `_pickrem_rendered_paths`, this helper, the test). If a 5th agent is ever added, all of those need updating; a shared bash array constant in `lib/agent_skills_paths.sh` would consolidate that.
