---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [documentation, setup, skills]
created_at: 2026-04-30 08:56
updated_at: 2026-04-30 08:56
---

## Goal

Eliminate the duplication of the `issue_type` vocabulary across 32+ files so adding a new value (like `enhancement` in commit `d7a96896`) becomes a single edit to `aitasks/metadata/task_types.txt` followed by a one-shot regeneration step.

## Background

`aidocs/issue_type_vocabulary_duplication.md` documents the problem in detail. The list lives in:

- 1 runtime data file (the source of truth) + 1 seed mirror
- 4 agent-instruction mirrors (`CLAUDE.md`, `seed/aitasks_agent_instructions.seed.md`, `.codex/instructions.md`, `.opencode/instructions.md`) — each enumerates the list twice (frontmatter sample + commit-format paragraph)
- 3 Claude Code skill docs
- 5 website pages
- 17 test fixtures (synthetic `task_types.txt` setups)
- 1 `aitask_ls.sh` help text

Each location uses one of three rendering styles:

- **pipe**: `bug|feature|enhancement|chore|...`
- **backtick-comma**: `` `bug`, `feature`, `enhancement`, `chore`, ... ``
- **plain-comma**: `bug, chore, documentation, enhancement, ...`

Adding `enhancement` required 31 file edits (commit `d7a96896`) plus the runtime/seed pair. This is exactly what `feedback_single_source_of_truth_for_versions.md` warns about.

## Approach

### Phase 1 — Render helper

Create `.aitask-scripts/aitask_render_type_list.sh` (whitelisted across all agent permission systems per CLAUDE.md "Adding a New Helper Script" — 5 touchpoints):

- Reads `aitasks/metadata/task_types.txt`.
- Subcommand or flag selects render style: `--style pipe|backtick|plain`.
- Optional `--separator-suffix` for the trailing-`manual_verification` test-fixture pattern (or just emit the value via the same renderer).
- Prints to stdout. Zero side effects.

### Phase 2 — Marker-based injection

Use HTML-comment markers in markdown / shell-comment markers in scripts:

```markdown
<!-- BEGIN_ISSUE_TYPES style=pipe -->
bug|feature|enhancement|chore|documentation|performance|refactor|style|test
<!-- END_ISSUE_TYPES -->
```

Add `.aitask-scripts/aitask_sync_type_lists.sh` that:

- Walks all marked files (use a manifest file or a glob list).
- For each marker pair, calls the render helper with the requested style and rewrites the content between the markers.
- Idempotent: running twice produces no changes.
- `--check` mode: exit non-zero if any file is out of sync (for CI / pre-commit).

### Phase 3 — Migrate existing locations

For each of the 32 hardcoded locations from `aidocs/issue_type_vocabulary_duplication.md`:

1. Wrap the enumeration in BEGIN/END markers with the appropriate `style=` attribute.
2. Run the sync script to verify it produces the same content.

Skip the test fixtures in this phase if the marker syntax doesn't fit cleanly inside `printf` strings — instead, change the fixtures to copy `seed/task_types.txt` rather than synthesizing the list (cleaner, more representative of real installs).

### Phase 4 — Wire into workflows

- `ait setup` runs sync at the end of the install (so seed + project files agree).
- Optional pre-commit hook or CI check runs `aitask_sync_type_lists.sh --check`.
- Document the marker pattern in `CLAUDE.md` so future skill authors use it.

## Out of scope

- Solving the same duplication problem for other controlled vocabularies (`status` enum, `priority`, `effort`). These have similar shape; deferred to a follow-up task that reuses the same machinery if Phase 1-2 prove out.
- Auto-discovery of marker locations (start with a manifest file; auto-discovery can come later).

## Acceptance Criteria

- Adding a new value to `aitasks/metadata/task_types.txt` and running `./.aitask-scripts/aitask_sync_type_lists.sh` updates **all** documented locations consistently. No manual edits required to mirror files.
- `aitask_sync_type_lists.sh --check` passes on a clean tree, fails when any marked location drifts.
- Helper script is whitelisted across `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json` (Codex exempt — prompt-only model).
- The next time a `task_types.txt` value is added, the diff touches only `aitasks/metadata/task_types.txt` + auto-generated content between markers (verifiable by re-doing the `enhancement` addition as a regression test).

## References

- `aidocs/issue_type_vocabulary_duplication.md` — problem statement, full file list, sed/grep patterns, generation sketch.
- Commit `d7a96896` — ground-truth list of files touched for the `enhancement` addition.
- `feedback_single_source_of_truth_for_versions.md` (user memory) — the principle this fixes.
- CLAUDE.md "Adding a New Helper Script" — 5-touchpoint whitelist checklist for any new `.aitask-scripts/` script.
