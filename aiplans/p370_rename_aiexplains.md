---
Task: t370_rename_aiexplains.md
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

## Context

The `aiexplains/` directory stores temporary generated data for the `/aitask-explain` skill (git history analysis, blame data, task mappings). Since this is internal framework data, it should use a dot-prefixed name (`.aitask-explain/`) to avoid cluttering the user's project root with a visible directory.

## Plan

Rename all references from `aiexplains` → `.aitask-explain` across the codebase. Also rename the `AIEXPLAINS_DIR` variable to `AITASK_EXPLAIN_DIR` to match the new naming convention.

### Files modified (16 files)

1. `.gitignore` — `aiexplains/` → `.aitask-explain/`
2. `ait` — help text descriptions
3. `.aitask-scripts/aitask_explain_extract_raw_data.sh` — variable + defaults + comments
4. `.aitask-scripts/aitask_explain_runs.sh` — variable + defaults + messages
5. `.aitask-scripts/aitask_explain_cleanup.sh` — variable + defaults + help text
6. `.aitask-scripts/codebrowser/explain_manager.py` — `CODEBROWSER_DIR` + env var
7. `.claude/skills/aitask-explain/SKILL.md` — all path references
8. `website/content/docs/skills/aitask-explain.md` — docs
9. `website/content/docs/commands/explain.md` — docs
10. `website/content/docs/commands/_index.md` — docs
11. `website/content/docs/tuis/codebrowser/how-to.md` — docs
12. `website/content/docs/tuis/codebrowser/reference.md` — docs
13. `tests/test_explain_cleanup.sh` — test fixture paths
14. `tests/test_explain_binary.sh` — env var references
15. `tests/test_extract_auto_naming.sh` — env var + temp dir paths
16. `tests/test_no_recurse.sh` — env var references

### Existing directory renamed

```bash
mv aiexplains/ .aitask-explain/
```

## Final Implementation Notes

- **Actual work done:** Renamed all 16 files containing `aiexplains` or `AIEXPLAINS_DIR` references to use `.aitask-explain` and `AITASK_EXPLAIN_DIR`. Also renamed the physical `aiexplains/` directory to `.aitask-explain/`.
- **Deviations from plan:** Found and updated `tests/test_no_recurse.sh` which was not discovered in the initial plan (5 `AIEXPLAINS_DIR` references).
- **Issues encountered:** None.
- **Key decisions:** Used `${AITASK_EXPLAIN_DIR:-${AIEXPLAINS_DIR:-.aitask-explain}}` as the default in all three shell scripts. This provides backward compatibility — if anyone has `AIEXPLAINS_DIR` set in their environment, it still works as a fallback before the new default `.aitask-explain` kicks in.
