---
priority: medium
effort: low
depends: [t258_4]
issue_type: documentation
status: Ready
labels: [codebrowser]
created_at: 2026-02-26 15:02
updated_at: 2026-02-26 15:02
---

## Context

After all implementation changes (t258_1 through t258_4) are complete, the website documentation needs updating to reflect the new naming convention, automatic cleanup behavior, and the new `ait explain-cleanup` command.

## Task

Update website documentation pages for the changed behavior and add documentation for the new cleanup command.

## Key Files to Modify

- `website/content/docs/commands/explain.md` — update existing command page + add explain-cleanup section
- `website/content/docs/skills/aitask-explain.md` — update skill page for new naming/cleanup
- `website/content/docs/workflows/explain.md` — update workflow page

## Reference Files

- `website/content/docs/commands/explain.md` — current explain command docs (format reference)
- `website/content/docs/skills/aitask-explain.md` — current skill docs (format reference)
- `website/content/docs/workflows/explain.md` — current workflow docs (format reference)
- `website/content/docs/commands/sync.md` — example of command doc page format

## Implementation Details

### commands/explain.md

- Add a new section for `ait explain-cleanup`:
  - Describe purpose: removes stale run directories keeping only newest per source key
  - Show modes: `--target DIR`, `--all`, `--dry-run`, `--quiet`
  - Show examples
- Update existing `ait explain-runs` section to mention:
  - New `--cleanup-stale` mode
  - Updated display showing dir_key alongside timestamp
  - New naming convention for run directories

### skills/aitask-explain.md

- Update "Run Management" section:
  - Note that runs now use `<dir_key>__<timestamp>` naming instead of bare timestamps
  - The dir_key identifies the source directory (e.g., `aiscripts__lib` for `aiscripts/lib/`)
  - Stale runs are automatically cleaned up when new data is generated
- Update any references to bare timestamp directory names

### workflows/explain.md

- In "How It Works" section: mention the automatic stale cleanup
- Update run directory naming references
- Add brief mention that cleanup happens automatically during analysis and at codebrowser startup

## Verification

1. `cd website && hugo build --gc --minify` — verify build succeeds (if Hugo available)
2. Review pages for consistent messaging about new naming and cleanup behavior
3. Verify all code examples use the new `<dir_key>__<timestamp>` format
