---
Task: t982_upgrade_merge_new_seed_models.md
Worktree: /home/ddt/Work/aitasks
Branch: main
Base branch: main
---

# Plan: Merge New Seed Models on Upgrade

## Summary

Fix `ait upgrade` so existing projects receive new entries from `seed/models_*.json` without overwriting local model verification or usage stats. Keep the change scoped to install-time model config merging.

## Implementation

- Add a `json-models` mode to `.aitask-scripts/aitask_install_merge.py`.
- Merge top-level JSON objects with destination values winning, except for the top-level `models` arrays.
- Union model entries by `name`, then `cli_id`, then canonical JSON for entries without either field.
- Preserve destination model entries unchanged and in order; append seed-only model entries in seed order.
- Keep malformed top-level JSON or non-list `models` values as merge errors so the destination is left untouched.
- Update `install.sh` so only `install_seed_models()` uses `json-models`; keep `codeagent_config.json` on plain `json`.
- Extend `tests/test_install_merge.sh` with model union, idempotence, fallback identity, and invalid-shape regression coverage.
- Add lightweight install-path coverage in `tests/test_install_merge.sh` by sourcing `install.sh` and invoking `install_seed_models()` in `FORCE=true` mode against a temp project.

## Verification

- `bash tests/test_install_merge.sh`
- `bash tests/test_t644_branch_mode_upgrade.sh`
- `python3 -m py_compile .aitask-scripts/aitask_install_merge.py`
- `bash -n install.sh .aitask-scripts/aitask_install_merge.py tests/test_install_merge.sh tests/test_t644_branch_mode_upgrade.sh`
- `git diff --check`

## Risk

### Code-health risk: low

The new behavior is isolated to a new merge mode and one install call site. Existing `yaml`, `json`, and `text-union` modes are unchanged.

### Goal-achievement risk: low

The focused tests cover the reported upgrade failure mode: destination model stats remain intact, seed-only models are appended, and repeated merges are idempotent.

### Planned mitigations

None.

## Post-Implementation

Follow Step 9 of the aitask workflow after review: commit implementation files separately from plan/task files, archive `t982`, and release its lock.

## Post-Review Changes

### Change Request 1 (2026-06-14 09:58)

- **Requested by user:** Confirm the change does not break `ait install` / `ait upgrade`, and add or run more tests if useful.
- **Changes made:** Added install-path regression coverage that invokes `install_seed_models()` through `install.sh` in forced upgrade mode, then ran the existing branch-mode upgrade integration test.
- **Files affected:** `tests/test_install_merge.sh`, `aiplans/p982_upgrade_merge_new_seed_models.md`

## Final Implementation Notes

- **Actual work done:** Added `json-models` merge mode, wired model seed installation to use it, and added regression tests for preserving local model entries while appending new seed models. Added an install-path regression that exercises `install_seed_models()` via `install.sh` in forced upgrade mode.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Model identity uses `name` first, `cli_id` second, and canonical JSON only for entries without either stable identifier.
- **Upstream defects identified:** None.
