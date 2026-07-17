---
priority: medium
effort: high
depends: [t1157_5]
issue_type: enhancement
status: Ready
labels: [workflows, remote, aitask_explore, aitask_fold, project_groups]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 16:50
updated_at: 2026-07-17 16:50
---

## Context

Sixth child of t1157. After remote explore core is stable, add the advanced native `aitask-explore` capabilities that need Discord-appropriate UX and authoritative gateway mutations: file selection, related-task discovery/folding, and cross-repo exploration/task shaping. This is staged deliberately so the useful core ships before these wider surfaces.

## Key files to modify

- Remote-explore skill/handler/rendering from t1157_5.
- Gateway proposal schema/validation and task creation/fold integration.
- Multi-project workspace snapshot/launch routing from t1157_3.
- Existing `.aitask-scripts/aitask_fold_content.sh`, `aitask_fold_mark.sh`, project resolver/query helpers as consumed APIs.
- Relevant chatlink flow, create, fold, and cross-repo tests.

## Reference files

- Native `aitask-explore` cross-repo detection and related-task-discovery procedures.
- User-file-select behavior for keyword/name/functionality search.
- `aidocs/framework/cross_repo_references.md` and existing cross-repo task creation contracts.
- Parent merged t1127 requirements.

## Implementation plan

1. Adapt file selection to Discord: accept search terms/path descriptions in a modal, run read-only search in the attempt, and render paginated candidate selections. Preserve a free-text path route and validate selections inside mounted snapshots.
2. Run related-task discovery against the routed project's current task data, render eligible standalone tasks, and carry selected IDs in the unapproved proposal.
3. On explicit approval, re-read and validate selected task status/scope gateway-side, merge content with the primary description, create the task, and mark folds atomically/amended. Stale/ineligible selections return to proposal review rather than partially mutate.
4. Detect registered project names and `<project>#<id>` / `<project>:<path>` references. Create read-only committed snapshots only for selected registered projects and record each base commit.
5. Let the proposal select the target project and validated `xdeprepo`/`xdeps` intent. Route creation to the target repo without exposing git credentials to the sandbox.
6. Preserve one-bot/many-guild routing and no cross-project task/session leakage.

## Verification

- Search/pagination/free-text file selection works within capability limits and rejects forged paths.
- Related tasks exclude children, parents-with-children, and stale statuses; concurrent status drift fails before creation with no partial fold.
- Cross-repo fixtures mount only registered requested snapshots, resolve refs, route proposals/tasks correctly, and never mutate non-target repos.
- Single-project/core explore behavior remains unchanged when advanced features are unused.
