---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow, gates, claudeskills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-08-03 11:21
updated_at: 2026-08-03 15:56
---

## Origin

Found during an `/aitask-explore` investigation of a user question: "when a plan
is approved, is `plan_approved` recorded so a crashed/stopped task can be
re-picked and resume after planning — and is that gate one of the DEFAULT gates
that are always active?"

Answer to the question itself (no fix needed, recorded here as context):
`resume_point()` (`.aitask-scripts/lib/gate_ledger.py:1337`) keys off the
**recorded** `## Gate Runs` ledger, explicitly *not* the declared `gates:` /
`active_gates` field. So `plan_approved` does not need to be a "default gate"
(and is not — no profile lists it in `default_gates`). The only switch that
governs whether it is recorded is the profile key `record_gates: true`, which
`fast.yaml` sets and `default.yaml` does not.

The exploration then surfaced four concrete defects on that resume path.

## Defect 1 — the drift-check "Stop and re-verify plan" branch drops the gate recording

`.claude/skills/task-workflow/remote-drift-check.md:70` says its branch runs
"the same release-and-revert sequence as the planning-checkpoint 'Approve and
stop here' branch (see `planning.md` Checkpoint, 'Approve and stop here')" — but
it then reproduces only that branch's **numbered steps 1–5** (commit plan,
release lock, revert to Ready, commit/push, display).

The Gate Recording Procedure call in `planning.md` sits *above* that numbered
list (`planning.md:402`, unnumbered), so the copy silently omits it.

Consequence: the user reached the drift check only by choosing "Start
implementation", i.e. the plan **was** approved. Yet no `plan_approved`
checkpoint is written before the workflow ends. The branch's own closing message
tells the user to pull the drifted branches and re-pick — and that re-pick finds
an empty ledger.

## Defect 2 — no drift check on any resumed task

The Remote Drift Check Procedure is invoked from exactly one place:
`planning.md`'s Checkpoint (both the `start_implementation` profile path,
`planning.md:374`, and the interactive "Start implementation" path,
`planning.md:388`).

**Re-entry Routing** (`SKILL.md:220-232`) bypasses Step 6 entirely: `IMPLEMENT`
routes straight to Step 7's "Follow the approved plan" body, re-running only the
pre-implementation ownership guard and the Agent Attribution Procedure;
`POSTIMPL` routes to Step 9. Neither path ever calls the drift check.

This inverts the risk: a resumed task is by construction the one whose plan is
*oldest* relative to `origin/<base>` and `origin/<output>`, and it is the only
one that gets no drift check at all.

The loop is also self-defeating once Defect 1 is fixed: "Stop and re-verify
plan" instructs the user to pull and re-pick, but a re-pick that now finds
`plan_approved` recorded would route to `IMPLEMENT` and skip the very check that
sent them away.

Note the resume path is not entirely unguarded — Re-entry Routing has a
plan-existence guard (`aitask_query_files.sh plan-file`, falling back to
re-plan). But that guards plan *existence*, not remote drift. Likewise
`planning.md` §6.0a's risk-mitigation force-verify only exists on the planning
path.

## Defect 3 — "Approve and stop here" records a resume signal that cannot route

`planning.md:402` records `plan_approved` `pass` with `fields="type=human
note=deferred"`, described in-line as "this is the resume signal". Ordering is
correct (recorded before the lock release).

But steps 3–4 of that same branch then revert the task's status to `Ready`, and
**Check 5 is gated on `status == Implementing`** (`SKILL.md:91`: "Read the task
file's frontmatter `status`. If it is **not** `Implementing`, skip this check").
So on re-pick the resume-point query is never run and `resume_point` is never
set — the recorded entry cannot drive routing.

What actually resumes that flow today is §6.0's existing-plan preference
(`plan_preference: use_current` reuses the plan and jumps to the Checkpoint).
That works, but it means the comment at `planning.md:402` describes a mechanism
that is inert, and the two paths ("approved + stopped" vs "approved + crashed")
resume through completely different machinery.

Decide and make consistent: either the recording is genuinely the resume signal
(and Check 5 / the status revert must accommodate it), or it is history-only and
the comment must stop claiming otherwise.

## Defect 4 — abort never demotes an already-recorded `plan_approved`

`task-abort.md` records nothing (correct — an abort is not an approval), but it
also never **re-opens** a `plan_approved` that a previous session recorded.
`gate_ledger.py` supports demotion (`_resume_point_from_state` is derived
back-to-front, so a `pass` → `fail` re-record correctly demotes the stage), and
nothing uses it here.

This is currently harmless only *incidentally*: abort reverts status to
`Ready`/`Editing`, so Check 5's status gate skips the stale entry. That makes
the safety a side effect of Defect 3's status gate rather than an intentional
invariant — if Check 5's status condition is ever relaxed (a plausible outcome
of fixing Defect 3), a task aborted at Step 8 review with a stale
`plan_approved` would resume straight into implementation, skipping planning,
even when the abort was chosen precisely because the plan was wrong.

Note the abort procedure also offers "Keep for future reference" for the plan
file, so the plan-existence guard would not catch this case either.

## Cross-cutting note — `record_gates` is off under the `default` profile

All of the recording behavior above is gated behind `record_gates: true`
(`gate-recording.md:9`: "Invoked only when the active profile sets
`record_gates: true`"). `aitasks/metadata/profiles/fast.yaml` sets it;
`aitasks/metadata/profiles/default.yaml` sets no gate keys at all.

So under `default`, no checkpoint is ever recorded, `resume_point` always
returns `PLAN`, and every crashed task re-plans from scratch. `SKILL.md:93`
acknowledges this ("This is the common case for profiles that do not record
gates ... so they are behaviorally unchanged").

Whether that default is intentional is **out of scope for this task** — flipping
it is a behavior change for every default-profile user and deserves its own
decision. It is recorded here so the fix for Defects 1–4 is understood to be
inert under `default` until that separate decision is made. If the plan
concludes it should change, split it out rather than folding it in.

Also worth stating explicitly in whatever docs this touches: recording is gated
on `record_gates` **alone**, not on `plan_approved` appearing in the task's
`gates:` / `active_gates` set. The user's question assumed active-set membership
mattered; it does not, and the distinction is easy to get wrong.

## Acceptance criteria

- [ ] The drift-check "Stop and re-verify plan" branch records `plan_approved`
      (Defect 1), or the plan explicitly justifies why it must not — with the
      `planning.md` cross-reference updated so the two branches cannot drift
      apart again by partial copy.
- [ ] Resumed tasks (`IMPLEMENT`, and `POSTIMPL` if applicable) either run the
      Remote Drift Check or the plan documents why re-entry is exempt
      (Defect 2). If they do run it, the "Stop and re-verify plan" → pull →
      re-pick loop must terminate rather than re-triggering itself.
- [ ] The "Approve and stop here" resume story is made internally consistent
      (Defect 3): either routing honors the recorded checkpoint, or the
      "this is the resume signal" claim is corrected to match reality.
- [ ] Abort's interaction with a previously recorded `plan_approved` is made an
      explicit, tested invariant rather than an accident of Check 5's status
      gate (Defect 4).
- [ ] Behavior under `record_gates: false` / the `default` profile is unchanged.
- [ ] Any `.md.j2` / closure edits regenerate the affected goldens in the same
      commit, and `./.aitask-scripts/aitask_skill_verify.sh` passes.
- [ ] Tests cover: the drift-check stop branch writing the checkpoint, a resumed
      task's drift-check behavior, and the abort-then-re-pick path. Each new
      guard must be proven to fail before the fix (negative control).

## Key files

- `.claude/skills/task-workflow/remote-drift-check.md` (Defects 1, 2)
- `.claude/skills/task-workflow/planning.md` (Checkpoint, ~:374/:388/:402)
- `.claude/skills/task-workflow/SKILL.md` (Check 5 ~:91, Re-entry Routing
  ~:220-232, Step 7 `plan_approved` recording ~:350)
- `.claude/skills/task-workflow/task-abort.md` (Defect 4)
- `.claude/skills/task-workflow/gate-recording.md` (`record_gates` gating)
- `.aitask-scripts/lib/gate_ledger.py` (`resume_point`,
  `_resume_point_from_state`, ~:1337-1369)
- `aitasks/metadata/profiles/default.yaml`, `fast.yaml`

Source-of-truth reminder: edit the Claude Code versions under
`.claude/skills/` first, then suggest separate aitasks for the Codex CLI
(`.agents/skills/`) and OpenCode (`.opencode/skills/`) ports if their surfaces
actually change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T12:56:48Z status=pass attempt=1 type=human
