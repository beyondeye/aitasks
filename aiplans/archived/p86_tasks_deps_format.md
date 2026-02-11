---
Task: t86_tasks_deps_format.md
Worktree: (current directory)
Branch: main
Base branch: main
---

# Plan: Normalize Task Dependency ID Formats (t86)

## Context

When Claude Code writes task frontmatter manually (without using `aitask_create.sh`/`aitask_update.sh`), it often writes child task IDs without the `t` prefix — e.g., `depends: [85_2, 85_3]` instead of `depends: [t85_2, t85_3]`. This causes lookup failures and display bugs. Additionally, PyYAML (YAML 1.1) coerces `85_2` to integer `852` due to underscore digit separator rules, making the data completely wrong when read by the Python board.

## Normalization Rule

- Entries matching `^\d+_\d+$` (child task refs without `t` prefix) → prepend `t`
- Plain numbers like `16`, `77` → leave as-is (parent task refs)
- Already-prefixed entries like `t85_2` → leave as-is
- Applied to both `depends` and `children_to_implement` fields

## Changes

### 1. `aitask_update.sh` — Add normalization function and apply at parse + write time

- [x] Add `normalize_task_ids()` function before `format_yaml_list`
- [x] Apply in `parse_yaml_frontmatter()` after parsing depends and children_to_implement
- [x] Apply before `write_task_file` call in batch mode

### 2. `aitask_ls.sh` — Add same normalization function and apply at parse time

- [x] Add `normalize_task_ids()` function before `parse_yaml_frontmatter`
- [x] Apply in `parse_yaml_frontmatter()` after parsing depends and children_to_implement

### 3. `aitask_board/aitask_board.py` — Custom YAML loader + normalization at load time

- [x] Add custom `_TaskSafeLoader` to prevent `85_2` → `852` coercion
- [x] Add `_normalize_task_ids()` function
- [x] Update `Task.load()` to use custom loader and normalize
- [x] Keep existing ad-hoc normalizations as defensive code

## Verification
1. Run `./aitask_ls.sh -v 15` — verify t85 children show "Blocked (by t85_2,...)" not "Blocked (by 85_2,...)"
2. Run `./aitask_update.sh --batch 85_9 --status Ready` — verify rewritten file has `depends: [t85_2, ...]`
3. Verify parent task deps like `depends: [16, 77]` remain as plain numbers
4. Verify idempotency: running update on already-correct task changes nothing

## Final Implementation Notes
- **Actual work done:** Implemented normalization in all three files as planned. Added `normalize_task_ids()` bash function to both shell scripts, and `_TaskSafeLoader` + `_normalize_task_ids()` to the Python board.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** Confirmed the PyYAML YAML 1.1 integer coercion issue (`85_2` → `852`) was real and critical. The custom YAML loader with string resolver override was necessary.
- **Key decisions:** Normalize at load/parse time rather than at every usage site. This ensures writes also output normalized format. Kept existing ad-hoc normalizations in Python board as defensive code.
