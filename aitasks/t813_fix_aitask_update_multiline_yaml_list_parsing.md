---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_pick]
created_at: 2026-05-20 09:45
updated_at: 2026-05-20 09:45
---

## Bug: `aitask_update.sh` frontmatter parser truncates multi-line YAML flow lists

The line-by-line frontmatter parsing loop in `.aitask-scripts/aitask_update.sh`
(around lines 337-365) matches each line against `^([a-z_]+):(.*)$` and only
ever reads the **first physical line** of a value.

When a list-valued field — `children_to_implement`, `depends`, `verifies`,
`labels`, `folded_tasks` — is serialized as a YAML flow sequence wrapped across
multiple lines (Python `yaml.dump` wraps once the list exceeds ~80 chars), the
continuation lines start with whitespace, fail the key regex, and are dropped.
`parse_yaml_list` then sees only the first line's worth of entries. A subsequent
`--add-child` / `--remove-child` rewrites the field with that truncated subset,
**permanently losing the continuation entries**.

## Real-world impact

At commit `12420882` (archiving child `t777_3`), parent `t777`'s
`children_to_implement` held 18 wrapped entries `[t777_3..t777_20]`. The parser
read only the first line `[t777_3..t777_10]`; `--remove-child t777_3` wrote back
`[t777_4..t777_10]`, and `t777_11..t777_20` were silently lost. This later caused
`t777` to be archived prematurely (commit `119ce6e7`) because `aitask_archive.sh`
saw an empty children list and concluded all children were complete.

(The parent task + the dropped children were manually restored in a separate
commit; this task fixes the underlying parser bug.)

## Fix

Make the frontmatter parser join multi-line YAML flow sequences — accumulate
continuation lines until the closing `]` — before passing the value to
`parse_yaml_list`. The fix must cover **all** list-valued frontmatter fields,
not just `children_to_implement`.

## Acceptance / tests

- Add a test that round-trips a task whose `children_to_implement` (or
  `depends`) is long enough to wrap across multiple lines, runs
  `aitask_update.sh --remove-child`, and asserts no entries are lost.
- Verify `aitask_update.sh`, `aitask_archive.sh`, and the board (`task_yaml.py`)
  agree on list serialization/parsing so a board-written wrapped list survives
  a bash-side edit.
