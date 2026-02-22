---
Task: t205_fix_install_missing_aireviewguides_dir.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Fixed a bug in `install.sh` where the `create_data_dirs()` function did not create the `aireviewguides/` directory. This caused the installer to fail silently when `install_seed_reviewtypes()`, `install_seed_reviewlabels()`, and `install_seed_reviewenvironments()` attempted to copy files into the non-existent directory.

## Files Modified

- **install.sh**: Added `mkdir -p "$INSTALL_DIR/aireviewguides"` to `create_data_dirs()` so the directory exists before the seed review metadata install steps run.

## Probable User Intent

The installer was failing silently on fresh installs (e.g., `curl -fsSL ... | bash`). The `cp` command in `install_seed_reviewtypes()` failed because `aireviewguides/` didn't exist yet, and `set -e` caused immediate exit with only a raw `cp` error on stderr — no formatted `[ait] Error:` message. The user wanted to fix this so the install completes successfully.

## Final Implementation Notes

- **Actual work done:** Added one line (`mkdir -p "$INSTALL_DIR/aireviewguides"`) to `create_data_dirs()` at line 185.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:** Chose to centralize the directory creation in `create_data_dirs()` rather than adding `mkdir -p` to each individual `install_seed_review*` function, keeping the pattern consistent with how other data directories are created.
