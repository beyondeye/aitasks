---
priority: medium
effort: medium
depends: [t583_8]
issue_type: test
status: Ready
labels: [framework, skill, task_workflow, verification, meta]
created_at: 2026-04-19 08:30
updated_at: 2026-04-19 08:30
---

## Context

Ninth and final child of t583. This is the **meta-dogfood aggregate** that validates the entire manual-verification module by running the module on itself. Per `feedback_manual_verification_aggregate`, parent tasks with 2+ TUI-touching or behavior-heavy siblings should have one aggregate manual-verification sibling rather than inline verification sections in each child. t583 qualifies.

Depends on t583_1 through t583_8 (entire module must be in place before dogfooding).

## Key Files to Create

- `aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md` — **this task itself is the deliverable** (but the task file needs to be authored in a specific way to drive the dogfood).

## Implementation Plan

### 1. Task file content (this file)

**Frontmatter:**
```yaml
---
priority: medium
effort: medium
depends: [t583_8]
issue_type: manual_verification
verifies: [t583_1, t583_2, t583_3, t583_4, t583_5, t583_6, t583_7, t583_8]
labels: [verification, manual, framework, skill, meta]
status: Ready
---
```

**Body:**
- Short context section explaining this task dogfoods the module itself.
- A `## Verification Checklist` H2 with one item per major behavior.

### 2. Checklist items

Each item is phrased as an actionable in-person step:

- [ ] **Parser round-trip:** create a synthetic manual-verification task with 5 items (one of each state); run `aitask_verification_parse.sh parse`, `set`, `summary`, `terminal_only`; verify output matches spec.
- [ ] **`verifies:` frontmatter in create/update:** `aitask_create.sh --batch --type manual_verification --verifies 10,11 --name test --desc test --commit` → file has `verifies: [10, 11]`; `aitask_update.sh --batch <id> --add-verifies 12 --remove-verifies 10` → `verifies: [11, 12]`.
- [ ] **`verifies:` in fold:** create 2 tasks with `verifies: [A, B]` and `[B, C]`; fold both into a third; confirm union `[A, B, C]`.
- [ ] **`verifies:` in board TUI:** launch `ait board`; pick a manual-verification task; confirm `verifies` field appears in `TaskDetailScreen` and accepts edits.
- [ ] **Follow-up on fail — single verifies:** pick a manual-verification task with `verifies: [X]` and one fail item; mark Fail; confirm a new bug task is created with origin=X, commits, files; failed item gets `— FAILED … follow-up tN` annotation.
- [ ] **Follow-up on fail — ambiguous origin:** same with `verifies: [X, Y]`; confirm origin-picker `AskUserQuestion` appears; picking X routes correctly.
- [ ] **Archival gate — pending:** try to archive a manual-verification task with 1 pending item → `aitask_archive.sh` exits 2 with `VERIFICATION_PENDING:1`.
- [ ] **Archival gate — deferred without flag:** all terminal except 1 defer → exits 2 with `VERIFICATION_DEFERRED:1`.
- [ ] **Archival carry-over:** re-run with `--with-deferred-carryover` → original archives; new manual-verification task created with only the deferred item; `verifies:` copied.
- [ ] **Generation — aggregate sibling:** `/aitask-pick` a parent task; create 2 children in plan mode; at the new prompt answer "Yes, aggregate sibling"; confirm a new sibling is created with correct `verifies:`.
- [ ] **Generation — single-task follow-up:** plan a single-task change; at the prompt answer "Yes"; confirm a standalone task is created with `verifies: [this_task]`.
- [ ] **Generation — explore path:** `/aitask-explore` path produces the follow-up prompt; answering "Yes" creates a follow-up task.
- [ ] **SKILL.md Step 3 dispatch:** pick any manual-verification task; confirm Step 3 Check 3 routes to `manual-verification.md` rather than continuing to Step 6.
- [ ] **Docs render:** `cd website && hugo build --gc --minify` completes without error; `/docs/workflows/manual-verification/` page is present.
- [ ] **CLAUDE.md whitelisting note:** open CLAUDE.md; "Adding a New Helper Script" subsection is present with the 5-touchpoint table and codex exception.
- [ ] **Unit tests pass:** `bash tests/test_verification_parse.sh && bash tests/test_verification_followup.sh && bash tests/test_verifies_field.sh` → all green.

### 3. Execution semantics

- This task is picked AFTER t583_1..t583_8 are all archived.
- When picked, Step 3 Check 3 routes to `manual-verification.md`, which runs the checklist.
- Failed items auto-create follow-up bugs against the relevant sibling (t583_1..t583_8).
- Deferred items can be carried over.
- Archival closes the parent t583.

## Verification Steps

- The entire task IS a verification step — executing the checklist validates the whole module.
- Completion means: every item has a terminal state, the parent t583 is archived, and any follow-up bugs created during dogfood are tracked for future work.

## Step 9 reminder

Commit: `test: Add meta-dogfood aggregate verification for t583 (t583_9)`.
