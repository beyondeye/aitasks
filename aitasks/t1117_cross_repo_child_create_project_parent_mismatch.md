---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask-create, task_workflow, upstream_defect_followup]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1061
created_at: 2026-07-03 00:26
updated_at: 2026-07-03 12:48
---

Upstream defect surfaced during the t1061 cross-repo decomposition (2026-07-02):
the **Cross-Repo Child Assignment Procedure contradicts `aitask_create.sh`**.

## Defect

`.claude/skills/task-workflow/cross-repo-child-assignment.md` Step 2 ("If
owning side is cross-repo") documents this invocation as the canonical way to
create a child under the cross-repo parent:

```bash
./.aitask-scripts/aitask_create.sh --project <name> --parent <B_parent_id> --batch ...
```

but `aitask_create.sh` **rejects the combination**:

```
Error: --project cannot be combined with --parent
```

So any agent following the procedure verbatim hits a hard error mid-creation
(after the cross-repo parent and possibly some local children already exist)
and must improvise. The t1061 session worked around it by running the target
repo's own script from its root:

```bash
cd <B-root> && ./.aitask-scripts/aitask_create.sh --batch --parent <B_parent_id> ...
```

which behaves correctly (auto-sibling deps, `children_to_implement`
maintenance, `--commit` on the target repo's aitask-data branch all work).

## Fix — pick one direction and make doc + script agree

1. **Support `--project` + `--parent` in `aitask_create.sh`** (and verify the
   same for `aitask_update.sh` if it has an equivalent restriction): route the
   whole child-creation flow through the resolved project root, exactly like
   the run-from-B-root workaround. Keeps the procedure doc as-is and is
   symmetric with the already-supported `--project` parent creation
   (`--project <name> --batch --name ...` works — the mobile parent t31 was
   created that way).
2. **Or fix the procedure doc** (`cross-repo-child-assignment.md` Step 2, in
   the Claude tree first, then rerender/port per skill conventions) to
   prescribe the run-from-B-root form, with the cwd-reset caveat (each Bash
   call must re-`cd`).

Option 1 is preferred if cheap: the validator's both-or-neither rule for
`--xdeps`/`--xdeprepo` and `--silent` output contract must keep working
cross-repo; add a unit test for cross-repo child creation (tests/ has
aitask_create coverage to extend).

## Acceptance criteria

- The documented invocation in `cross-repo-child-assignment.md` Step 2 and the
  actual `aitask_create.sh` behavior agree (whichever direction is chosen).
- A test covers the cross-repo child-creation path (or, for the doc-only fix,
  the doc shows a command that is exercised by an existing test).
- `aitask_update.sh --project ... --batch <child_id> ...` (used by the same
  procedure's Step 3 back-fill) is checked for the same class of mismatch —
  note: in the t1061 session the local-side back-fill ran without `--project`,
  so the cross-repo update path is untested.

## Provenance

- Discovered while executing `aiplans/p1061_applink_outside_network_connectivity_roadmap.md`
  (cross-repo child assignment for t1061 / aitasks_mobile#31).
