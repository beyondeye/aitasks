---
priority: medium
effort: medium
depends: [1702]
issue_type: bug
status: Implementing
labels: [git, task_metadata, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
plan_approved_at: 2026-09-03 23:44
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-03 12:22
updated_at: 2026-09-04 16:02
---

## Origin

Risk-mitigation ("after") follow-up for t1677, created at Step 8d after implementation landed.

## Risk addressed

`addresses: goal-achievement — apply_push writes another repo's tracked
codeagent_config.json and leaves it dirty there`

From p1677's `## Risk`:

> `lib/cross_repo_settings.py:400` (`apply_push`, via `syncer_app.py:1973`)
> writes **another repo's** tracked `codeagent_config.json` and is deliberately
> out of scope, because a repo-scoped seam cannot commit into a repo that may be
> mid-work. The goal "every tracked metadata write has an owner" is therefore
> met for this repo's own surfaces only · severity: medium

## Goal

Give the syncer's cross-repo config push an owner that commits **in the target
repo**, deciding safely what to do when that repo is mid-work.

t1677 gave every tracked `aitasks/metadata/*` write in *this* repo an owner that
clears it, via `.aitask-scripts/aitask_metadata_commit.sh`. That helper is
deliberately repo-scoped: it resolves paths against the current repo's data
branch and commits there. `apply_push` is the one remaining writer that leaves a
tracked metadata file dirty in a repo the pushing session does not own, so it is
listed in the inventory guard's `KNOWN_UNCOMMITTED` allowlist rather than wired.

The hard part is not the commit — it is deciding what is safe when the target
repo is mid-work. Enumerate and decide explicitly:

- the target repo has a dirty `codeagent_config.json` from its own session
- the target repo has other staged content (a scoped commit is mandatory, never
  a bare `git commit` — see t1702 for the same defect class)
- the target repo is on a task branch, or its data branch is behind its remote
- the target repo has no data branch at all (legacy mode)

Refusing with a clear report may well be the right answer for some of these; a
refusal the user can see beats a commit they did not authorize in a repo they
were working in. Whatever is chosen, the outcome must be *reported* — a silent
dirty file in someone else's repo is the ownerless state t1677 exists to end,
just relocated.

Re-derive the call path before starting; do not trust these line numbers.

## Verification

- push a config to a clean target repo → the file is committed there, scoped to
  that path, and the target worktree is clean afterwards
- push to a target repo with foreign staged content → that content is NOT in the
  resulting commit
- push to a target repo mid-work on the same file → the chosen outcome (refuse
  or commit) happens and is reported to the user, never silent
- negative control: each assertion must fail against today's write-without-commit
- when this lands, remove `cross_repo_settings.apply_push` from the
  `KNOWN_UNCOMMITTED` allowlist in `tests/test_metadata_writer_inventory.py`
  and add its wiring assertion instead

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-03T20:43:47Z status=pass attempt=1 type=human
>
> Note: deferred
