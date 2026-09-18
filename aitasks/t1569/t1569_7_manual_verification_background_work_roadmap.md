---
priority: medium
effort: medium
depends: [t1569_4, t1569_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t1569_1, t1569_3, t1569_4, t1569_5, t1569_6]
anchor: 1569
followup_kind: manual_verification
created_at: 2026-08-27 11:34
updated_at: 2026-08-27 11:34
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1569_1] Run `ait board` By-Trail view on a trail gathered with --with-inflight and confirm the new in-flight facts are visible without breaking the existing rendering.
- [ ] [t1569_1] Confirm an ordinary trail refresh (no --with-inflight) is unchanged and does not touch the network.
- [ ] [t1569_3] Drive the checker on the live repo and confirm CLEAR_CAVEATED is rendered visibly differently from CLEAR, not collapsed into it.
- [ ] [t1569_3] Confirm an UNCHECKABLE result names the specific in-flight task it could not rule out, not an undifferentiated "something is unknown".
> **[t1569_4] items: use a profile that sets `parallel_admission: confirm`.**
> All three shipped profiles (`default`, `fast`, `remote`) ship
> `parallel_admission: "off"`, so the preflight is a no-op under every one of
> them and each check below would vacuously "pass" by never running. Copy a
> profile, set `parallel_admission: confirm`, and verify against that.
>
> Why they ship off: measured 2026-09-02, 9 of 16 `Implementing` tasks carry no
> plan file (56%), and an in-flight task's surface is read from its plan **only**
> — there is no task-body/origin fallback on that side — so 108 of 122 live
> candidates return `UNCHECKABLE`. Adding that fallback is the fix, owned by
> **t1688** (`t1688_parallel_admission_prepick_assessment_and_task_body_surface.md`).
> If t1688 has landed by the time these items are verified, re-check whether the
> shipped profiles have been flipped back to `warn` — in that case verify against
> them as shipped, not against a copy.

- [ ] [t1569_4] Run /aitask-pick on a real task and confirm the preflight appears AFTER the remote drift check, not before.
- [ ] [t1569_4] Confirm a freshly claimed candidate does NOT conflict with itself (task-workflow locks it at Step 4, long before the plan exists).
- [ ] [t1569_4] Confirm each of CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE presents its intended disposition, and that UNCHECKABLE prints an operator remedy the user can actually act on.
- [ ] [t1569_4] Confirm the preflight re-runs on implementation re-entry (resume an in-flight task via the IMPLEMENT route).
- [ ] [t1569_5] Confirm score components AND origin quality (exact/topic/unknown) are legible per entry in the rendered trail, and that a topic-quality entry does not read like an exact one.
- [ ] [t1569_5] Confirm an uncheckable run is visibly hedged rather than silently green, including the UNKNOWN_HISTORY cause which is the easiest to render as a false all-clear.
- [ ] [t1569_6] Run /aitask-backlog-roadmap end-to-end on the live repo and confirm it produces a usable ordering.
- [ ] [t1569_6] Confirm the lanes are visually distinct in the By-Trail view via the coordination_only glyph.
- [ ] [t1569_6] Confirm neither the preflight nor the roadmap ever describes a pass as "safe to run in parallel" - both must say "no known conflict at check time" - and that the residual race is discoverable from the workflow docs.
- [ ] [t1569_6] Confirm the run summary surfaces the resolution-quality histogram and states plainly that the lanes are an estimate that reserves nothing.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1688_2** id=2026-09-18T09:47:30Z.c7e0225c6f6c56e3d4d47e06 from=t1688_2 from_verified=yes at=2026-09-18T09:47:29Z base=2070c66aebb47673c80e887e0011c66bf5b70f98 base_branch=main dirty=yes host=omg16
>
> | Advisory from t1688_2 (code commit af5948e87) — not an instruction.
> | 
> | - Shipped profiles still set `parallel_admission: "off"` (C1 decision, measured
> |   2026-09-17: 34% prompt rate, 1 of 6 sampled CONFLICTs a real collision). The
> |   [t1569_4] checklist items therefore still need a profile that sets
> |   `confirm` (or `warn`) to exercise anything.
> | - The CLEAR_CAVEATED rendering item should now also cover the `task_declared`
> |   caveat: an in-flight task with no plan is read from its description, which
> |   grades CLEAR_CAVEATED (`CAVEAT:inflight:<ref>|task_declared`), and a shared
> |   path found that way appears as `task_declared_overlap` — advisory, not a
> |   conflict and not an all-clear.
> | - Steps 2-3 of parallel-admission.md (invocation + well-formedness) now live in
> |   parallel-admission-checker.md; the preflight references it.
