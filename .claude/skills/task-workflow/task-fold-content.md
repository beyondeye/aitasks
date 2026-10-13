# Task Fold Content (reference)

Building the merged description body is handled by `.aitask-scripts/aitask_fold_content.sh`. See that script for the canonical implementation.

## Usage

**Merging into an existing primary task** (aitask-fold, planning ad-hoc fold):

```bash
./.aitask-scripts/aitask_fold_content.sh <primary_task_file> <folded_file1> <folded_file2> ...
```

**Building content for a new primary task** (aitask-explore, aitask-pr-import, aitask-contribution-review):

```bash
printf '%s\n' "<description from exploration>" | \
  ./.aitask-scripts/aitask_fold_content.sh --primary-stdin <folded_file1> <folded_file2> ...
```

With `--primary-stdin`, the input may be a plain description or a whole task file. A recognizable, closed task frontmatter block is stripped. Any other text, including a description that opens with a `---` rule, is kept verbatim.

The script writes the merged description body to stdout in a structured format:
- Primary declared body preserved at the top
- `## Merged from t<N>: <name>` section for each folded task (its declared body)
- `## Folded Tasks` reference section
- `## Folded History`, only when a folded task carried an `## Inbox`, `## Gate Runs` or earlier `## Folded History`:
  - Each such task gets one `### t<N>: <name>` entry, with headings shifted down two levels.
  - Its ledger markers are neutralized with the `> | ` sentinel, so the gate and note parsers never read them as the primary's.
  - The section is a framework section: `plan_paths.cut_task_framework_sections` cuts it like the ledgers, so its paths are not task-declared.
  - A primary that already has the section gets the new entries appended to it.
- The primary's own `## Inbox` / `## Gate Runs`, kept last

The output is printed only once it is complete. On any failure the script exits non-zero with empty stdout, so a piped `--desc-file -` keeps the current description and never receives a truncated body. Neutralizing markers needs python (`ledger_block.neutralize_markers`), and only when a body contains `**`.

Callers typically pipe the output into `aitask_update.sh --batch <id> --desc-file -` (for existing primaries) or pass it as the `description` argument to the **Batch Task Creation Procedure** (for new primaries).
