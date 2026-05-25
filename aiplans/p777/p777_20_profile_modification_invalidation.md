---
Task: t777_20_profile_modification_invalidation.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_27_recover_runtime_skills_and_parity_tests.md, aitasks/t777/t777_28_dedup_template_branches_common_proc_and_macros.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_12_convert_aitask_pr_import.md, aiplans/archived/p777/p777_13_convert_aitask_revert.md, aiplans/archived/p777/p777_14_convert_aitask_pickrem.md, aiplans/archived/p777/p777_15_convert_aitask_pickweb.md, aiplans/archived/p777/p777_16_extract_profile_editor_widget.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_29_fix_opencode_skill_legacy_pointers.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 12:06
---

# Plan: t777_20 — Profile-modification eager invalidation (verification refresh)

## Context

When a user edits an execution profile YAML through any framework TUI (the `ait settings` Profiles tab, or the per-run "Save as persistent" path in `AgentCommandScreen`), every per-profile rendered skill directory for that profile (`<agent>/skills/*-<profile>-/`) becomes stale. Today, staleness is caught only on the next wrapper invocation by `aitask_skill_render.sh`'s "skip-if-fresh" mtime check. That works, but:

- Old rendered content lingers on disk between save and next invocation — confusing if the user inspects the rendered dirs directly.
- A stale-render bug masked by mtime drift would not surface until much later.

This child task (t777_20) adds **eager invalidation** as a belt-and-suspenders complement: when the framework writes a profile YAML, it immediately deletes the affected rendered directories. The lazy mtime check still covers the "user edits YAML by hand outside the TUI" case unchanged.

**The helper is internal-only — no `ait` dispatcher entry, no policy whitelist.** It is shelled out from Python save hooks by its full path (`./.aitask-scripts/aitask_skill_invalidate.sh`). The `ait` dispatcher is reserved for commands a human would plausibly type manually; this one fails that bar. The 7-touchpoint helper whitelist is required only for scripts called from agent skills under their sandboxed permission systems — this script is only ever called from Python TUI subprocess and from a manual shell, neither of which goes through agent allow-lists.

## Verification deltas from the existing plan

Three concrete deviations from the existing `aiplans/p777/p777_20_*.md` plan, surfaced by the codebase verification and user direction:

1. **No `ait skill invalidate` CLI.** The original task description mentions an `ait skill invalidate <profile>` CLI. Dropped: `ait` subcommands are reserved for user-facing commands. The helper is invoked only from Python save hooks via its full script path. Manual / debug runs use the same path.

2. **No 7-touchpoint policy whitelist.** The original plan listed (incorrectly, 5) whitelist files. Dropped entirely: the helper is never invoked from inside an agent skill — only from Python `subprocess.run([...])` and from manual shell invocation. Neither path consults the per-agent allow-lists, so the entries would be dead weight.

3. **Two save sinks, not one.** The original plan said to hook `ProfileEditScreen.on_save`. That widget doesn't write to disk itself — it dispatches to caller-supplied callbacks. The two actual save sinks are:
   - `.aitask-scripts/settings/settings_app.py::ConfigMgr.save_profile()` (line 447) — used by the Settings TUI Profiles tab inline editor.
   - `.aitask-scripts/lib/agent_command_screen.py::_on_profile_saved_persistent()` (line 786) — used by AgentCommandScreen's per-run "Save persistent" branch.

   Both write YAML directly via `yaml.dump` / `yaml.safe_dump`. The hook must be added in **both** places. (`_on_profile_saved_one_shot()` at line 810 writes one-shot overrides to a `_skillrun_<pid>_<ts>.yaml` filename — these MUST NOT trigger invalidation; we only patch the persistent path.)

## Critical files

| Action | Path |
|--------|------|
| Create | `.aitask-scripts/aitask_skill_invalidate.sh` |
| Create | `tests/test_skill_invalidate.sh` (automated tests) |
| Modify | `.aitask-scripts/settings/settings_app.py` (hook in `ConfigMgr.save_profile`, line 447) |
| Modify | `.aitask-scripts/lib/agent_command_screen.py` (hook in `_on_profile_saved_persistent`, line 786) |

No edits to `ait` (see deviation #1) and no whitelist edits (see deviation #2).

## Implementation steps

### 1. `aitask_skill_invalidate.sh`

```bash
#!/usr/bin/env bash
# aitask_skill_invalidate.sh - Delete per-profile rendered skill directories.
#
# Usage: aitask_skill_invalidate.sh <profile_name>
#
# Walks each agent's skill root and removes every directory whose name ends
# in "-<profile_name>-" (the trailing-hyphen rendered-dir convention from
# t777_3 / agent_skills_paths.sh). Authoring directories never end with `-`,
# so this glob cannot accidentally hit them.
#
# Emits: "INVALIDATED:<N> directories for profile '<name>'" on stdout.
# Idempotent: second run on the same profile emits INVALIDATED:0.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/agent_skills_paths.sh
source "$SCRIPT_DIR/lib/agent_skills_paths.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

profile="${1:?usage: aitask_skill_invalidate.sh <profile_name>}"
deleted=0
for agent in claude codex gemini opencode; do
    root="$(agent_skill_root "$agent")" || continue
    [[ -d "$root" ]] || continue
    while IFS= read -r -d '' dir; do
        info "Invalidating: $dir"
        rm -rf -- "$dir"
        deleted=$((deleted + 1))
    done < <(find "$root" -maxdepth 1 -type d -name "*-${profile}-" -print0)
done
echo "INVALIDATED:$deleted directories for profile '$profile'"
```

Notes:
- Reuses the same 4-agent loop convention used elsewhere (no separate agent-list constant exists in the framework).
- Uses `agent_skill_root` from `lib/agent_skills_paths.sh` instead of hard-coding paths.
- `info()` comes from `terminal_compat.sh` (matches existing helper style).
- `chmod +x` after creation.

### 2. Hook into `ConfigMgr.save_profile` (Settings TUI)

In `.aitask-scripts/settings/settings_app.py`, `ConfigMgr.save_profile` (line 447) is the canonical sink for the Settings TUI Profiles tab. `subprocess` is already imported (used by `_maybe_rerender_pickrem`).

After the `with open(path, "w") ... yaml.dump(...)` block (line 454-455), before `self.profiles[filename] = data`, insert:

```python
# Eager invalidate per-profile rendered skill directories so the next
# wrapper invocation forces a fresh render. Lazy mtime check still
# covers hand-edits outside the TUI.
profile_name = Path(filename).stem  # "fast.yaml" -> "fast"
try:
    subprocess.run(
        ["./.aitask-scripts/aitask_skill_invalidate.sh", profile_name],
        check=False, capture_output=True, text=True, timeout=10,
    )
except (OSError, subprocess.TimeoutExpired):
    pass  # Belt-and-suspenders: lazy check still catches staleness.
```

`Path` is already imported (used in `_pickrem_rendered_paths`).

### 3. Hook into `_on_profile_saved_persistent` (AgentCommandScreen)

In `.aitask-scripts/lib/agent_command_screen.py`, `_on_profile_saved_persistent` (line 786). After the successful YAML write (line 799) and the success notify (line 803), before the override-clear / refresh block:

```python
# Eager invalidate per-profile rendered skill directories (t777_20).
import subprocess  # add at top if not present
try:
    subprocess.run(
        ["./.aitask-scripts/aitask_skill_invalidate.sh", name],
        check=False, capture_output=True, text=True, timeout=10,
    )
except (OSError, subprocess.TimeoutExpired):
    self.app.notify(
        "Profile saved but invalidation helper failed — next render "
        "will still re-check freshness.",
        severity="warning", timeout=5,
    )
```

Check whether `subprocess` is already imported at the top of the file; if not, add it next to other stdlib imports. (`_on_profile_saved_one_shot` at line 810 is **deliberately untouched** — one-shot overrides write to `_skillrun_<pid>_<ts>.yaml` and the rendered dirs use the resolved base profile name, not the one-shot suffix.)

### 4. Automated tests — `tests/test_skill_invalidate.sh`

Model on `tests/test_skill_verify.sh` (same `assert_eq` / `assert_contains` / `assert_zero_exit` / `assert_nonzero_exit` helpers, same scratch-workspace pattern with a `_t777_20_test_` prefix and an `EXIT` trap cleanup). The script is hermetic — it creates scratch directories under each of the four real agent roots, runs the helper, and tears down on exit.

Test cases (numbered for the test output):

1. **Helper exists and is executable.** `[[ -x .aitask-scripts/aitask_skill_invalidate.sh ]]`.
2. **No-arg usage fails.** Invoke without arguments → non-zero exit, stderr contains `usage`.
3. **Idempotent on empty state.** Run with a profile name that has no rendered dirs → exits 0, stdout matches `INVALIDATED:0 directories`.
4. **Deletes only trailing-hyphen dirs for the requested profile.** Pre-create across all 4 agent roots:
   - Targets to delete: `<root>/_t777_20_test_skill_a-<profile>-/SKILL.md`, `<root>/_t777_20_test_skill_b-<profile>-/SKILL.md` — touch a file inside each so we know the whole tree got removed (not just the directory shell).
   - Decoys that must survive: `<root>/_t777_20_test_skill_a/` (authoring — no trailing hyphen), `<root>/_t777_20_test_skill_a-<otherprofile>-/` (different profile, same prefix). Use `<profile>=t77720tfast` and `<otherprofile>=t77720tslow` — uncommon enough not to collide with real profiles.
   - Run the helper; assert `INVALIDATED:8` (2 dirs × 4 agents), targets gone, decoys intact.
5. **Second run is idempotent.** Re-run on the same profile after step 4 → `INVALIDATED:0`.
6. **Skips missing agent roots gracefully.** Temporarily rename one agent root to a side path (e.g. `.opencode/skills` → `.opencode/skills.bak_t77720`), run the helper, assert zero exit and no error. Restore the directory in cleanup.
7. **Unknown profile name is a no-op.** Run with a clearly non-existent profile name → exits 0, `INVALIDATED:0`.
8. **`shellcheck` clean.** `shellcheck .aitask-scripts/aitask_skill_invalidate.sh` exits 0.

The cleanup trap MUST run on every exit path:
```bash
cleanup() {
    rm -rf .claude/skills/_t777_20_test_* .agents/skills/_t777_20_test_* \
           .gemini/skills/_t777_20_test_* .opencode/skills/_t777_20_test_*
    # Restore opencode/skills if it was renamed in test 6
    [[ -d .opencode/skills.bak_t77720 && ! -d .opencode/skills ]] && \
        mv .opencode/skills.bak_t77720 .opencode/skills
}
trap cleanup EXIT
```

This test runs standalone via `bash tests/test_skill_invalidate.sh` and prints a `PASSED: M / TOTAL: M` summary in the same shape as sibling test scripts.

## Verification

The automated tests in step 4 are the primary correctness gate. The checks below are end-to-end / manual:

1. **Automated tests pass:** `bash tests/test_skill_invalidate.sh` reports `FAIL: 0` for all 8 cases.

2. **Re-render restores deleted dirs:** After running `./.aitask-scripts/aitask_skill_invalidate.sh fast`, invoke any `/aitask-pick`-like wrapper that targets the `fast` profile — the renderer must recreate the deleted `<agent>/skills/*-fast-/` directories on first invocation.

3. **Settings TUI end-to-end (manual):** Open `ait settings` → Profiles tab → edit `fast` → Save. Confirm the matching `*-fast-/` directories are gone. Next wrapper invocation re-renders them.

4. **AgentCommandScreen end-to-end (manual):** In `ait board`, trigger an agent-command screen, edit profile, click "Save persistent". Confirm invalidation fired (`*-<profile>-/` dirs removed). The "Save as one-shot" button must NOT trigger invalidation (verify by saving a one-shot and confirming the base-profile rendered dirs are untouched).

5. **Lazy check still works:** Hand-edit `aitasks/metadata/profiles/fast.yaml` outside any TUI; do not run invalidate; trigger a wrapper — the renderer's skip-if-fresh check must still detect the mtime change and re-render.

## Pitfalls (carried forward, refined)

- **One-shot overrides are intentionally excluded.** Saved-as-one-shot files use `_skillrun_<pid>_<ts>` filenames; invalidating their rendered dirs (which don't exist as separate entries — one-shots reuse the resolved base profile's render at runtime) would needlessly destroy other users' cache. Hook ONLY in the persistent paths.
- **Concurrent agent reads.** If a skill is mid-execution reading a per-profile SKILL.md when invalidation deletes the directory, that read may fail. This is a documented limitation in CLAUDE.md (already flagged in parent t777 plan).
- **Trailing-hyphen glob is load-bearing.** The `*-<profile>-` suffix ensures we never hit authoring directories (which by design never end with `-`, gitignored as `*-/`). Do NOT relax the glob.

## Post-implementation

Step 9 (post-implementation) of the task-workflow handles archival, branch cleanup, and push. Per profile 'fast' on current branch — no worktree created, no branch to merge.
