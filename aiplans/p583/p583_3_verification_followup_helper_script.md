---
Task: t583_3_verification_followup_helper_script.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md, aitasks/t583/t583_2_*.md, aitasks/t583/t583_4_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_3 — Verification Follow-up Helper

## Context

Creates a bug task when a manual-verification item is marked `Fail`. Reuses `detect_commits()` from `aitask_issue_update.sh`. Depends on t583_1 (parser) and t583_2 (`verifies:` field plumbing).

## Files to create/modify

**New:**
- `.aitask-scripts/aitask_verification_followup.sh`

**Modify (whitelist — 5 touchpoints):**
Same 5 files as t583_1. Codex: skip.

## CLI

```
aitask_verification_followup.sh --from <task_id> --item <index> [--origin <feature_task_id>]
```

## Behavior

1. Resolve `--from` task file; parse target item via `aitask_verification_parse.sh parse`.
2. Read `verifies:` frontmatter:
   - If `--origin` provided → use it.
   - Else if `verifies:` has exactly 1 entry → use it.
   - Else if `verifies:` empty → use `--from` itself.
   - Else → exit 2 with `ORIGIN_AMBIGUOUS:<csv>` (caller re-invokes with `--origin`).
3. Resolve commits: reuse `detect_commits()` from `aitask_issue_update.sh` (source it or replicate the `git log --oneline --grep "(t${origin})"` call).
4. Resolve touched files: `git show --name-only --format= <hash>` per commit; dedupe.
5. Compose description with failing-item text, commits, files, `deps: [<origin>]`.
6. Create bug task: `aitask_create.sh --batch --type bug --priority medium --effort medium --labels verification,bug --deps <origin> --desc-file <tmp> --commit`.
7. Annotate source item: `aitask_verification_parse.sh set <from> <index> fail --note "follow-up t<new>"`.
8. Back-reference origin's archived plan (best-effort, skip silently if not archived).
9. Output: `FOLLOWUP_CREATED:<new_id>:<path>`.

## Reference precedent

- `.aitask-scripts/aitask_issue_update.sh` `detect_commits()` ~line 246.
- `.aitask-scripts/aitask_create.sh --batch` backend.
- `.aitask-scripts/lib/task_utils.sh` `resolve_task_id_to_file()`, `read_frontmatter_field()`.

## Verification

- Synthetic test: create manual-verification task + real commit; run helper; confirm bug task content.
- Ambiguous origin: `verifies:[X,Y]` no `--origin` → exits 2 with `ORIGIN_AMBIGUOUS`.
- Full unit tests in t583_6 (`test_verification_followup.sh`).

## Final Implementation Notes

_To be filled in during implementation._
