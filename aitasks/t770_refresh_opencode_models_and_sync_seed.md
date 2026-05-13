---
priority: medium
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [modelvrapper, opencode]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-13 10:15
updated_at: 2026-05-13 10:16
---

Refresh the OpenCode supported-models list in both the local config (`aitasks/metadata/models_opencode.json`) and the seed template (`seed/models_opencode.json`), then commit both.

## Why

- Local `aitasks/metadata/models_opencode.json` currently has 44 active models (last touched April 2026).
- Seed `seed/models_opencode.json` only has 6 models — it is badly out of date and will give new projects bootstrapped via `ait setup` a stale starting list.
- `opencode` v1.14.48 is installed locally, so CLI-based discovery via `opencode models --verbose` is available.

## How

Use the existing `aitask-refresh-code-models` skill, scoped to OpenCode only:

1. Run `/aitask-refresh-code-models` and select only `opencode` when prompted (or invoke the helper directly: `bash .aitask-scripts/aitask_opencode_models.sh`).
2. The script runs `opencode models --verbose`, merges with the existing local config (preserves `verified` scores, marks gone models `status: unavailable`), and writes back to `aitasks/metadata/models_opencode.json`.
3. Sync the refreshed local file to the seed: either via the skill's Step 6 (auto-copies when `seed/` exists) or `bash .aitask-scripts/aitask_opencode_models.sh --sync-seed`.
4. Commit both per the skill's Step 8:
   - Metadata file via `./ait git add aitasks/metadata/models_opencode.json && ./ait git commit -m "ait: Refresh opencode model configurations"`
   - Seed file via plain `git add seed/models_opencode.json && git commit -m "ait: Sync refreshed opencode models to seed template"`

## Verification

- `jq '.models | length' aitasks/metadata/models_opencode.json` matches `jq '.models | length' seed/models_opencode.json` after the sync.
- No `verified` scores are lost for models that already existed in the local config (the merge logic in `aitask_opencode_models.sh` preserves them).
- Run `bash .aitask-scripts/aitask_opencode_models.sh --dry-run` first to preview the changes before writing.

## Out of scope

- Refreshing claude/codex/gemini models (those use web research, not CLI discovery — separate concern).
- Switching the other agents to CLI-based discovery (covered by t408).
- Whitelisting changes for the helper scripts (covered by t701).
