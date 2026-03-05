---
Task: t315_document_ait_stats_plot_option_and_setup_dependency.md
Worktree: /home/ddt/Work/aitasks
Branch: main
Base branch: main
---

## Summary

Document `ait stats --plot` end-to-end: usage examples, optional dependency expectations, and setup flow integration.

## Implementation Plan

1. Update `website/content/docs/commands/board-stats.md`:
   - Add clearer `--plot` examples.
   - Document warning/fallback behavior when `plotext` is missing.
   - Clarify that `--plot` depends on optional `plotext`.
2. Update `website/content/docs/commands/setup-install.md`:
   - Expand the Python venv step to identify where optional plot support is enabled.
   - Document the exact setup prompt and yes/no outcome.
   - State that rerunning `ait setup` can enable it later.
3. Validate docs against script behavior in `aiscripts/aitask_stats.py` and `aiscripts/aitask_setup.sh`.
4. Complete Step 9 cleanup: archive task with `./aiscripts/aitask_archive.sh 315` and push metadata.

## Final Implementation Notes

- **Actual work done:** Updated `board-stats.md` with clearer `--plot` examples, added explicit missing-`plotext` warning/fallback behavior, and documented the setup prompt location. Updated `setup-install.md` Python venv step with exact prompt wording and yes/no outcomes, plus guidance to rerun setup to enable later.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Kept scope strictly documentation-only and matched wording to current runtime behavior in `aiscripts/aitask_stats.py` and `aiscripts/aitask_setup.sh`.
