---
Task: t249_verify_seed_whitelist_content.md
Worktree: N/A (current branch)
Branch: main
Base branch: main
---

## Context

The `seed/claude_settings.local.json` file provides the baseline whitelist for new project installations via `ait setup`. It needs to include all `aiscripts/*.sh` scripts referenced by skills (`.claude/skills/*/SKILL.md`) so users don't get permission prompts when running skill workflows.

## Findings

**Currently whitelisted (10 scripts + 1 library):**
1. `aitask_ls.sh`
2. `aitask_update.sh`
3. `aitask_create.sh`
4. `aitask_zip_old.sh`
5. `aitask_stats.sh`
6. `aitask_issue_update.sh`
7. `aitask_changelog.sh`
8. `aitask_archive.sh`
9. `aitask_pick_own.sh`
10. `aitask_scan_profiles.sh`
11. `source aiscripts/lib/repo_fetch.sh`

**Missing — referenced by skills but not in seed:**
| Script | Used by |
|--------|---------|
| `aitask_query_files.sh` | aitask-create, aitask-pick, aitask-fold, aitask-pickrem, aitask-pickweb, task-workflow |
| `aitask_lock.sh` | task-workflow, aitask-pickrem, aitask-pickweb |
| `aitask_lock_diag.sh` | task-workflow, aitask-pickrem |
| `aitask_init_data.sh` | aitask-pickrem, aitask-pickweb |
| `aitask_find_files.sh` | user-file-select |
| `aitask_review_commits.sh` | aitask-review |
| `aitask_review_detect_env.sh` | aitask-review |
| `aitask_reviewguide_scan.sh` | aitask-reviewguide-classify, aitask-reviewguide-merge |
| `aitask_web_merge.sh` | aitask-web-merge |
| `aitask_explain_extract_raw_data.sh` | aitask-explain |
| `aitask_explain_runs.sh` | aitask-explain |

**In seed but not referenced by any skill (keep anyway):**
- `aitask_zip_old.sh` — CLI utility (`ait zip-old`), useful even without a skill

## Plan

1. **Edit `seed/claude_settings.local.json`**: Add the 11 missing script entries, keeping alphabetical order among the script entries.
2. **Reorder** existing script entries alphabetically for consistency.

## Final Implementation Notes

- **Actual work done:** Added 11 missing aiscript whitelist entries and alphabetized all 21 script entries (+ 1 library source). Total entries went from 39 to 50.
- **Deviations from plan:** None — straightforward addition and reorder.
- **Issues encountered:** None.
- **Key decisions:** Kept `aitask_zip_old.sh` even though no skill references it (it's a useful CLI utility). Did not add scripts that exist in `aiscripts/` but aren't referenced by any skill (e.g., `aitask_board.sh`, `aitask_claim_id.sh`, `aitask_codebrowser.sh`, `aitask_install.sh`, `aitask_issue_import.sh`, `aitask_setup.sh`, `aitask_sync.sh`) — those are either internal/helper scripts or used via `./ait` subcommands rather than direct `./aiscripts/` invocation from skills.
