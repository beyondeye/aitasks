---
Task: t770_refresh_opencode_models_and_sync_seed.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Refresh OpenCode models and sync to seed (t770)

## Context

`aitasks/metadata/models_opencode.json` (44 active models, last touched April 2026) is current relative to the locally connected OpenCode providers, but `seed/models_opencode.json` is badly out of date — it only has 6 models, so new projects bootstrapped via `ait setup` get a tiny stale starting list. The fix is to re-run discovery against the current `opencode` binary (v1.14.48, installed) and sync the refreshed local file to seed.

The existing skill (`aitask-refresh-code-models`) and helper script (`aitask_opencode_models.sh`) already do this end-to-end. The helper exposes `--sync-seed` so both the runtime metadata file and the seed template can be updated in one invocation. The helper's merge logic preserves existing `verified` scores and marks no-longer-discovered models as `status: unavailable` rather than deleting them.

## Approach

Drive the refresh through the existing `.aitask-scripts/aitask_opencode_models.sh` helper — do not bypass it or write parallel logic. Two-pass: dry-run first to preview, then write + sync.

### Step 1 — Dry-run preview

```bash
bash .aitask-scripts/aitask_opencode_models.sh --dry-run
```

Expected output lines `[ACTIVE] <name> (<cli_id>)` and `[UNAVAILABLE] <name> (<cli_id>)`. Confirm:
- Some `[ACTIVE]` lines appear (discovery succeeded).
- The total count is sane (the local file currently has 44 — expect similar order of magnitude).
- No surprising `[UNAVAILABLE]` lines that indicate provider auth was lost (would lose all of a provider's models).

If dry-run fails (e.g. `opencode models --verbose` errors), stop and surface the failure — do not proceed to write.

### Step 2 — Write + sync seed

```bash
bash .aitask-scripts/aitask_opencode_models.sh --sync-seed
```

This invocation:
- Runs `opencode models --verbose`, parses the verbose JSON blocks (`process_model` in `.aitask-scripts/aitask_opencode_models.sh:128`).
- Merges with `aitasks/metadata/models_opencode.json` preserving `verified` scores (`merge_with_existing` at `.aitask-scripts/aitask_opencode_models.sh:167`).
- Writes the merged result sorted by name with 2-space indent (`.aitask-scripts/aitask_opencode_models.sh:270`).
- Copies the resulting file to `seed/models_opencode.json` because `seed/` exists in the source repo (`.aitask-scripts/aitask_opencode_models.sh:273-281`).

### Step 3 — Verify

```bash
jq '.models | length' aitasks/metadata/models_opencode.json seed/models_opencode.json
jq '.models | group_by(.status // "active") | map({status: (.[0].status // "active"), count: length})' aitasks/metadata/models_opencode.json
diff <(jq -S . aitasks/metadata/models_opencode.json) <(jq -S . seed/models_opencode.json)
```

Pass criteria:
- The two `length` outputs match.
- `diff` is empty (modulo whitespace) — confirms seed is an exact copy.
- Active count is reasonable; any `unavailable` count is explainable (a connected provider going dark since the previous April run).
- Spot-check: a previously-verified entry's `verified` scores survived (e.g. `jq '.models[] | select(.verified.pick > 0)' aitasks/metadata/models_opencode.json`).

### Step 4 — Commit (deferred to Step 8 of task-workflow)

Per `aitask-refresh-code-models/SKILL.md:144-156` and CLAUDE.md "Git Operations on Task/Plan Files":

```bash
# Metadata file lives on task-data branch — use ./ait git
./ait git add aitasks/metadata/models_opencode.json
./ait git commit -m "ait: Refresh opencode model configurations (t770)"

# Seed file lives on main — use plain git
git add seed/models_opencode.json
git commit -m "chore: Sync refreshed opencode models to seed template (t770)"
```

The seed commit's `chore:` prefix matches the task's `issue_type: chore`. Both messages include the `(t770)` suffix per CLAUDE.md commit format.

> Per the task-workflow convention: code files (seed/) and task-data files (aitasks/metadata/) must never be mixed in one `git add` / commit.

## Files affected

- `aitasks/metadata/models_opencode.json` — refreshed by the helper (Step 2)
- `seed/models_opencode.json` — overwritten by the helper's `--sync-seed` step

No source code is modified; no skill or script files change.

## Out of scope

- Refreshing claude / codex / gemini models (use web research, not CLI discovery — separate concern).
- Switching the other agents to CLI-based discovery (tracked in t408).
- Whitelisting changes for `aitask_refresh_code_models.sh` / `aitask_add_model.sh` (tracked in t701).
- Editing the seed when `seed/` is absent (only the source repo has it; user installs don't).

## Verification

End-to-end:
1. Dry-run preview shows a plausible list of active models (Step 1).
2. After the real run, `jq '.models | length' aitasks/metadata/models_opencode.json seed/models_opencode.json` yields matching counts.
3. `diff <(jq -S . aitasks/metadata/models_opencode.json) <(jq -S . seed/models_opencode.json)` is empty.
4. Any existing `verified` scores in the local file before the run are still present after.
5. Two commits land: one on the task-data branch (via `./ait git`), one on main (plain `git`).

## Reference: Step 9 (Post-Implementation)

After Step 8 approval and commits, task-workflow Step 9 will archive t770 via `./.aitask-scripts/aitask_archive.sh 770` and push.
