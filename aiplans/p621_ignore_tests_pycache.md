---
Task: t621_ignore_tests_pycache.md
Base branch: main
plan_verified: []
---

# Plan for t621: ignore tests/__pycache__

## Context

`tests/__pycache__/` currently appears as an untracked directory in `git status`
because `.gitignore` only enumerates `__pycache__` paths under `.aitask-scripts/`.
The user noticed this during normal work and wants it fixed. Solution: replace
the four specific `.aitask-scripts/` `__pycache__` lines with a single repo-wide
`__pycache__/` rule — the conventional Python-project approach — which covers
`tests/__pycache__/` and any future `__pycache__` directory under any subtree.

## Files to modify

- `/home/ddt/Work/aitasks/.gitignore` — lines 3–5

## Change

**Current lines 3–5:**
```
.aitask-scripts/__pycache__/
.aitask-scripts/**/__pycache__/
.aitask-scripts/board/__pycache__/
.aitask-scripts/codebrowser/__pycache__/
```

**Replace with a single line:**
```
__pycache__/
```

The replacement sits in the same position (the "draft tasks / python bytecode"
cluster at the top of the file). Keep the existing leading `# Draft tasks`
comment group intact.

## Verification

Run from the repo root after the edit:

```bash
# tests/__pycache__/ must now match the new rule.
git check-ignore -v tests/__pycache__/

# The existing .aitask-scripts coverage must still hold via the broader rule.
git check-ignore -v .aitask-scripts/board/__pycache__/ \
                    .aitask-scripts/lib/__pycache__/ \
                    .aitask-scripts/codebrowser/__pycache__/

# tests/__pycache__/ must no longer appear in untracked list.
git status --short | grep __pycache__ || echo "OK: no __pycache__ untracked"
```

Each `git check-ignore` call should print the new `.gitignore:<line>:__pycache__/`
rule for each path.

## Scope notes

- 14 `__pycache__` directories currently exist across the repo — all covered
  by the single rule.
- No other Python artifacts need ignore rules (no `.pytest_cache`, no
  `*.egg-info`, no stray `.pyc` outside `__pycache__/`).
- Only `.gitignore` changes — no code changes.

## Step 9 (Post-Implementation)

After approval, implementation, and review:
- Commit `.gitignore` with message `chore: Ignore __pycache__ repo-wide (t621)`.
- Run archival via `./.aitask-scripts/aitask_archive.sh 621`.
- Push with `./ait git push`.
