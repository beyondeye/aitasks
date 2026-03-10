---
Task: t361_gemini_cli_global_allowlist_setup.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Gemini CLI global allowlist setup (t361)

## Context

Gemini CLI currently ignores per-project policy files referenced from `.gemini/settings.json`, so the aitasks allowlist only becomes effective when it also exists in `~/.gemini/policies/`. The setup flow should help users install that global allowlist, but only after an explicit consent step that explains what file will be copied or merged, where it will go, and why it is needed.

## Files To Update

### `/.aitask-scripts/aitask_setup.sh`
- Add a helper that installs or merges a Gemini policy file into `~/.gemini/policies/`
- Reuse `merge_gemini_policies()` so existing global files keep custom rules
- Add an explicit consent prompt in `setup_gemini_cli()` after the existing Gemini policy approval step
- In non-interactive mode, skip the global sync unless explicit consent can be gathered

### `/tests/test_gemini_setup.sh`
- Add helper-level coverage for create + merge behavior in a temporary HOME
- Verify the helper preserves existing custom rules while adding missing aitasks rules

### `/website/content/docs/installation/known-issues.md`
- Keep the documented Gemini CLI limitation
- Update the workaround text to explain that `ait setup` now offers the global allowlist install automatically, with an explicit confirmation step

## Implementation Steps

### Step 1: Add global policy install helper
Implement a helper near the existing Gemini policy merge logic:

```bash
install_gemini_global_policy() {
    local source_policy="$1"
    local global_dir="$HOME/.gemini/policies"
    local global_file="$global_dir/$(basename "$source_policy")"

    mkdir -p "$global_dir"

    if [[ ! -f "$global_file" ]]; then
        cp "$source_policy" "$global_file"
        success "  Created ~/.gemini/policies/$(basename "$source_policy")"
    else
        info "  Existing ~/.gemini/policies/$(basename "$source_policy") found — merging policies..."
        merge_gemini_policies "$source_policy" "$global_file"
    fi
}
```

### Step 2: Add explicit consent checkpoint in Gemini setup
Inside `setup_gemini_cli()`:
- keep the current project-local `.gemini/policies/` install flow unchanged
- after local policy install succeeds, show a second prompt explaining:
  - source file: `.gemini/policies/aitasks-whitelist.toml`
  - destination file: `~/.gemini/policies/aitasks-whitelist.toml`
  - behavior: create if missing, merge if already present
  - reason: Gemini CLI currently ignores per-project `policyPaths`
- preview the policy content before asking
- only call `install_gemini_global_policy()` when the user explicitly answers yes
- if stdin is non-interactive, log that global sync is skipped because explicit consent is required

### Step 3: Extend Gemini setup tests
In `tests/test_gemini_setup.sh`:
- extract and eval `install_gemini_global_policy`
- set `HOME` to a temp directory
- run the helper once and verify the global file is created
- seed the global file with a custom rule, run the helper again, and verify:
  - custom rule remains
  - aitasks rules are present
  - duplicate rules are not created unexpectedly

### Step 4: Refresh the Known Issues page
Revise the Gemini CLI workaround section so it no longer tells users to manually copy the file as the normal path. Instead, document that `ait setup` now offers to install or merge the global allowlist after showing what will be written.

## Verification

- `bash tests/test_gemini_setup.sh`
- `shellcheck .aitask-scripts/aitask_setup.sh`
- `git diff --stat`

## Post-Review Changes

### Change Request 1 (2026-03-10 16:31)
- **Requested by user:** Fix the Gemini whitelist syntax after Gemini CLI reported `Invalid regex pattern` for `(?i)aitask-review`, and update the installed global file so Gemini can start cleanly.
- **Changes made:** Replaced the unsupported inline case-insensitive regex flag with a portable character-class pattern in both the repo policy file and the seed policy file, added regression assertions to the Gemini setup test, and refreshed the global installed allowlist under `~/.gemini/policies/`.
- **Files affected:** `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, `tests/test_gemini_setup.sh`, `/home/ddt/.gemini/policies/aitasks-whitelist.toml`

### Change Request 2 (2026-03-10 16:31)
- **Requested by user:** Expand Gemini skill activation permissions so `activate_skill` auto-allows all `aitask-*` skills instead of only a single skill.
- **Changes made:** Generalized the Gemini `activate_skill` whitelist pattern from one skill-specific rule to a pattern that matches any `aitask-*` skill name, updated regression tests, and refreshed the installed global policy file.
- **Files affected:** `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, `tests/test_gemini_setup.sh`, `/home/ddt/.gemini/policies/aitasks-whitelist.toml`

### Change Request 3 (2026-03-10 16:31)
- **Requested by user:** Whitelist the specific Gemini shell command form `./.aitask-scripts/aitask_lock.sh --check <task> 2>/dev/null` so lock pre-checks during `aitask-pick` do not stop on the stderr redirection.
- **Changes made:** Added an explicit Gemini `commandRegex` rule for `aitask_lock.sh --check ... 2>/dev/null`, added regression assertions for both repo and seed policy files, and refreshed the installed global policy file.
- **Files affected:** `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, `tests/test_gemini_setup.sh`, `/home/ddt/.gemini/policies/aitasks-whitelist.toml`

### Change Request 4 (2026-03-10 16:31)
- **Requested by user:** Replace the broad regex that auto-allowed all `aitask-*` skill activations with explicit per-skill allowlist entries for better security.
- **Changes made:** Replaced the single broad `activate_skill` regex with 18 explicit `activate_skill` rules matching the installed aitask skill names one by one, updated regression tests to assert exact entry counts and sample skill names, and refreshed the installed global policy file.
- **Files affected:** `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, `tests/test_gemini_setup.sh`, `/home/ddt/.gemini/policies/aitasks-whitelist.toml`

## Final Implementation Notes

- **Actual work done:** Added an explicit opt-in global Gemini policy install flow to `ait setup`, updated the Gemini allowlist seed and repo policy files to fix invalid regex syntax, added a targeted lock-check redirection rule, and replaced the broad `aitask-*` skill activation regex with explicit per-skill `activate_skill` entries. Also updated the Known Issues documentation and expanded the Gemini setup regression test coverage.
- **Deviations from plan:** Extended the original scope after interactive review to address two Gemini runtime problems discovered during validation: unsupported inline regex syntax in the policy file and overly broad skill activation matching. Both fixes were folded into the same task because they directly affected the new global allowlist workflow.
- **Issues encountered:** A separate Gemini CLI trial run reverted parts of the repo-side whitelist changes, so the policy files and `aitask_setup.sh` global-install logic had to be restored before finalization. Gemini CLI also continues to prompt on `2>/dev/null` redirection despite the specific command rule being present, which appears to be a Gemini safety-layer limitation rather than a missing whitelist entry.
- **Key decisions:** Kept global policy installation behind explicit user consent with a preview of the copied content; preserved user custom global rules by merging instead of overwriting; used explicit `activate_skill` entries for each installed aitask skill instead of a broad regex for better security; and retained the lock-check redirection rule in the allowlist so the policy remains as specific as Gemini currently allows.

## Step 9 Reminder

Before archival, update this plan with final implementation notes, then follow the workflow's review, commit, and archive steps.
