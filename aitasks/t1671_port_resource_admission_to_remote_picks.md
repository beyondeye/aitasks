---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task-workflow, execution_profiles]
gates: [risk_evaluated]
anchor: 1595
followup_kind: risk_mitigation
created_at: 2026-09-01 16:47
updated_at: 2026-09-01 16:47
---

## Origin

Risk-mitigation ("after") follow-up for t1597, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement (autonomous picks start memory-bound phases unadmitted) — from
`aiplans/p1597_pre_implementation_resource_admission_hook.md` `## Risk`:

> The seam covers `task-workflow` only, so `aitask-pickrem` / `aitask-pickweb`
> keep starting memory-bound phases unadmitted — the stated goal is met for
> attended picks and deferred for autonomous ones (user-confirmed scope) ·
> severity: low

## Goal

Carry the resource-admission hook to `aitask-pickrem` and `aitask-pickweb`, whose
park semantics differ from `task-workflow`'s.

t1597 shipped the seam in `task-workflow` only (user-confirmed scope decision at
planning time). `aitask-pickrem` and `aitask-pickweb` are **self-contained
workflows** — their own `SKILL.md.j2`, their own implementation step, no remote
drift check and no interactive stop — so they do not inherit Step 7's dispatch
and today start their implementation phase without asking the host anything. That
is the surface where it matters most: those are the autonomous lanes an operator
runs several of at once.

### What already exists (reuse, do not re-implement)

- `.aitask-scripts/aitask_resource_admission.sh` — the helper. Unchanged: same
  `KEY:value` stdout, same exit codes (0 admit / 1 refuse / 2 error / 3
  usage-infrastructure with `DIAG:` and no `VERDICT:`), same scalar-only
  `resource_admission_command` key, same env contract.
- `.claude/skills/task-workflow/resource-admission.md` — the procedure. Read it
  first: the dispositions, the fail-closed rule, and the "observes, does not
  reserve" wording are settled and must not be re-litigated per surface.
- `.claude/skills/task-workflow/plan-approved-stop.md` — `stop_reason` is a
  **closed vocabulary** (`deferred` / `drift` / `resource_admission`) with an
  exhaustiveness guard. If either remote surface needs a different park shape, it
  must say which side of that file's marker-disposition table it belongs on
  rather than inventing a fourth reason silently.

### What has to be decided per surface

The park is the hard part, and it is NOT a copy:

- **`aitask-pickrem`** — non-interactive by construction (no `AskUserQuestion`).
  A refusal has to end the run cleanly with a machine-readable outcome, and the
  operator has to be able to tell "refused" from "failed" from its output alone.
  Decide whether it reuses the Approved-Plan Stop Sequence or its own Abort
  Procedure, and whether the deferred-plan marker is stamped (it should be — the
  plan is intact).
- **`aitask-pickweb`** — additionally cannot touch other branches and stores task
  data locally in `.aitask-data-updated/`. Whatever the park writes must survive
  `aitask-web-merge`, or the refusal is invisible after the merge.
- Where the call sits in each: after ownership/claim, before any implementation
  work — the same two anchors t1597 used, adapted to those files' step numbering.

### Deliverables

- The dispatch in both `SKILL.md.j2` templates + regenerated goldens under
  `tests/golden/skills/aitask-pickrem/` and `.../aitask-pickweb/` in the SAME
  commit.
- A rendered-prose contract test per surface, in the shape of
  `tests/test_resource_admission.sh` section 2: placement asserted positionally,
  and the exit-3 branch asserted inside its own extracted slice (a file-scoped
  `DIAG:` count is wrong — the contract recap legitimately names it above the
  branch).
- Website docs: `website/content/docs/skills/aitask-pick/resource-admission.md`
  currently describes `/aitask-pick` only; widen it, or link it from the pickrem /
  pickweb pages.
- No new whitelist entries — the helper is already allowlisted in all five
  touchpoints.

### Verification

- `bash tests/test_resource_admission.sh` (unchanged, must stay green)
- `bash tests/test_skill_render_aitask_pickrem.sh`
- `bash tests/test_skill_render_aitask_pickweb.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/run_all_python_tests.sh` (last line only)
