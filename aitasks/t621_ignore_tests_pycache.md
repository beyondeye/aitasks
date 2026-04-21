---
priority: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [maintenance]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-21 16:44
updated_at: 2026-04-21 16:47
---

`tests/__pycache__/` is currently untracked but visible in `git status` because
`.gitignore` has no rule that covers it. The existing lines cover only
`.aitask-scripts/` subtrees:

```
.aitask-scripts/__pycache__/
.aitask-scripts/**/__pycache__/
.aitask-scripts/board/__pycache__/
.aitask-scripts/codebrowser/__pycache__/
```

## Fix

Replace those four specific lines with a single repo-wide rule that covers
every `__pycache__/` directory (Python's standard bytecode cache convention):

```
__pycache__/
```

This ignores `tests/__pycache__/` and any future `__pycache__/` dir that
appears under any subtree, without needing to enumerate paths.

## Verification

After the change:
- `git check-ignore -v tests/__pycache__/` must report the new rule.
- `git status` must no longer list `tests/__pycache__/` as untracked.
- `git check-ignore -v .aitask-scripts/board/__pycache__/ .aitask-scripts/lib/__pycache__/`
  must still report the rule (confirming the previous coverage is retained
  via the broader pattern).

## Scope notes

- 14 `__pycache__` dirs currently exist across the repo — all will be covered
  by the single rule.
- No other Python artifacts were found needing ignore rules (no `.pytest_cache`,
  `*.egg-info`, or stray `.pyc` outside `__pycache__/`).
- No functional code changes — `.gitignore` only.
