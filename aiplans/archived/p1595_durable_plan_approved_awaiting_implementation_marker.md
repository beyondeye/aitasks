---
Task: t1595_durable_plan_approved_awaiting_implementation_marker.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1595 — Durable "plan approved, awaiting implementation" marker

## Context

A task whose plan was approved and then stopped ("Approve and stop here" →
`plan-approved-stop.md`) is today indistinguishable from a never-touched task on
every surface: the stop reverts `status` to `Ready` and clears `assigned_to`, the
`plan_approved=pass` ledger entry is an audit record only (and is written **only**
under `record_gates: true`, which of the shipped profiles is just `fast`), and task
frontmatter has no "planned" state. So `ait ls` shows it as plain `Ready`, and on
re-pick under `default` the user gets the 3-way plan prompt with no hint that an
approved plan exists.

The downstream goal (thinking_app#320) is to plan several tasks in parallel, defer
their implementation phases, and re-pick later skipping planning. The mechanics
already work; the **state is invisible**. This task makes it visible.

**Hard constraint carried from `aidocs/gates/ledger-driven-reentry.md` §"Rejected
alternatives":** this is about *visibility and prompting, not routing*. The
§6.0 → Checkpoint → Remote Drift Check path stays exactly as it is; nothing here
lets a `Ready` task with an approved plan route around the drift check.

## Design decision (user-confirmed)

A single durable frontmatter scalar:

```yaml
plan_approved_at: 2026-08-25 10:24   # absent ⇒ no deferred approved plan
```

Its meaning is precise: *this plan was approved and **deliberately deferred**, and
has not since been invalidated.* That yields a strict lifecycle:

| Event | Effect on the marker |
|---|---|
| Checkpoint → "Approve and stop here" (`stop_reason=deferred`) | **set** to now |
| Drift check → "Stop and re-verify plan" (`stop_reason=drift`) | **cleared** — never refreshed: the flow stopped *because* re-verification is required |
| Step 7 → the implementation body is entered | cleared (consumed) |
| Step 7 → cross-repo demotion (parent becomes parent-of-children) | cleared |
| Step 7 → risk-mitigation "before" stop | **retained** — the plan is approved and still awaiting implementation, merely blocked |
| §6.0 "Create plan from scratch" (replan) | cleared (the approved plan is discarded) |
| Task abort (plan rejected) | cleared |

**The consumption boundary is the implementation body, not the top of Step 7.**
Step 7 has two gates that revert the task to `Ready` and end the session *before
any code is written* — Cross-Repo Child Assignment (`cross-repo-child-assignment.md`
Step 4) and the risk-mitigation "before" stop — and they need opposite treatment.
After a cross-repo demotion the local task is a parent-of-children and its
single-task plan no longer describes implementable work, so the marker must go.
After a mitigation stop the plan is intact and the task will be re-picked (with
§6.0a force-reverifying it because a mitigation landed), so the marker must stay —
that case is *exactly* "approved and deliberately deferred". The clear therefore
sits at the top of the "Follow the approved plan" body, past both gates, outside
every Jinja gate (profile-invariant), which is also where Re-entry Routing's
`IMPLEMENT` route resumes — so the resume path consumes it with no extra wiring.

The marker **never** skips or weakens the drift check: `planning.md`'s Checkpoint
runs the Remote Drift Check Procedure exactly as today, and §6.0a's force-reverify
is untouched.

Why frontmatter and not a derived state: plan-file existence + `plan_verified` is
ambiguous (an *aborted* task can legally keep its plan file), and the ledger route
is unavailable under `default` (`record_gates: false` ⇒ empty ledger). The marker
is a new fact — "a human approved this and chose to defer" — not a duplicate of an
existing one. Shape-wise it is byte-for-byte the `verification_baseline` (t1555_1)
precedent: a semantic scalar, update-only, no tombstone (clearing removes the key).

Board surfacing is explicitly **out of scope** (the task names it as a separate
dependent task); a follow-up is created at Step 8d.

## Implementation

### 1. Write path — `plan_approved_at` in `aitask_update.sh`

Mirror `verification_baseline` (t1555_1) at every layer of
`.aitask-scripts/aitask_update.sh`:

- `--plan-approved-at TS` batch flag (`BATCH_PLAN_APPROVED_AT` + `_SET`), documented
  in `show_help` beside `--followup-kind` / `--verification-baseline`.
- Frontmatter parse case → `CURRENT_PLAN_APPROVED_AT`, reset with the other
  `CURRENT_*` defaults.
- `write_task_file` **positional 35** (appended — never inserted mid-list), emitted
  only when non-empty, next to the `verification_baseline` emit block.
- Threaded through **all three** `write_task_file` call sites (`~1202` parent
  child-completion helper, `~1730` interactive, `~2190` batch) plus the
  save/restore pair in the parent helper. Missing one silently drops the field on
  the next update of that path.
- **Value validation (fail closed):** the literal `now` resolves to
  `get_timestamp` (so the timestamp format has exactly one home, in
  `lib/task_utils.sh`); `""` clears; anything else must match
  `^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}$` or the update is rejected.

### 2. Writer / clearers — task-workflow procedure sources

All edits go in `.claude/skills/task-workflow/` (the Claude-Code source of truth);
rendered variants and other agents are regenerated in step 7.

- **`plan-approved-stop.md`** — the single shared stop sequence, so the set/clear
  branch on `stop_reason` lands in exactly one file. Fold the marker into the
  *existing* revert call so it cannot be dropped:
  ```bash
  # stop_reason=deferred — plan approved, implementation postponed
  ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready \
      --assigned-to "" --plan-approved-at now
  # stop_reason=drift — re-verification required; invalidate any marker
  ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready \
      --assigned-to "" --plan-approved-at ""
  ```
  Add a Notes bullet: the marker is display/prompt-only, it is never a routing
  signal, and a drift stop **clears rather than refreshes** it.
- **`SKILL.md` Step 7** — a new unconditional bullet at the **top of the
  implementation body**, immediately before "Follow the approved plan, working in
  the directory specified in the plan metadata": `--plan-approved-at ""`
  (idempotent — a no-op when the key is absent). It is outside both
  `{%- if … risk_evaluated … %}` gates, so it is profile-invariant, and it is the
  exact point Re-entry Routing's `IMPLEMENT` route resumes at.
  Add a one-line note in the risk-mitigation "before" stop block stating that the
  marker is **deliberately left in place** there, so a later reader does not
  "helpfully" clear it: that task is approved-and-deferred-because-blocked, and
  §6.0a force-reverifies its plan on re-pick anyway.
- **`cross-repo-child-assignment.md` Step 4** — append `--plan-approved-at ""` to
  the existing demotion call: the local task is now a parent-of-children and its
  single-task plan no longer describes implementable work.
- **`planning.md` §6.0** — read `plan_approved_at` from the task frontmatter when a
  plan file exists, and clear it on the "Create plan from scratch" branch (both the
  profile-driven `create_new` value and the interactive option), which runs before
  `EnterPlanMode` and is therefore a legal write.
- **`task-abort.md`** — append `--plan-approved-at ""` to the existing revert call.

### 3. Read surface — the pick prompt (`planning.md` §6.0)

When the marker is present, enrich the interactive 3-way question (the `default`
path) and make the recommendation explicit:

- Question: "An implementation plan approved on `<plan_approved_at>` is awaiting
  implementation (`<plan_path>`). How would you like to proceed?"
- Options: "Use current plan (Recommended)" / "Verify plan" / "Create plan from
  scratch".

On the profile-driven paths (`use_current` / `verify` / `create_new`) the marker is
**display-only**: print "Approved plan from `<ts>` awaiting implementation" and
apply the profile preference unchanged. State explicitly that the Checkpoint's
Remote Drift Check still runs in every case.

**Precedence:** §6.0a runs *before* the preference logic and is unaffected. When it
sets `force_verify` (a risk mitigation landed since the last verification), the
recommendation flips to "Verify plan" even though the marker is present — the
marker records an approval, not freshness, and never suppresses a forced
re-verification.

### 4. Read surface — `ait ls`

**Decided contract: display is verbose-only; the filter is the non-verbose
affordance.** Plain `ait ls` prints filenames and nothing else — no metadata field
(status, priority, type, follow-up kind) has ever appeared there, and every script
consumer of the plain form parses it as a bare filename list. Adding the first-ever
metadata to it would be a behaviour change well beyond this task. So the state is
reachable without `-v` by *filtering* (`ait ls --plan-approved`) rather than by
decorating, and both directions are pinned by tests.

In `.aitask-scripts/aitask_ls.sh`:

- parse `plan_approved_at` into `plan_approved_at_text` (+ reset in
  `parse_task_metadata`);
- verbose segment `, Plan: approved <ts>`, emitted only when present, positioned
  after `${followup_info}` and before `${assigned_info}`;
- filters `--plan-approved` / `--no-plan-approved` (mutually exclusive), mirroring
  the `--followup-kind` / `--no-followup-kind` pair — applied in `process_task_file`
  so they work in **every** listing mode and in both plain and `-v` output — plus
  `show_help` entries.

`.claude/skills/aitask-pick/SKILL.md.j2` §2a documents the `-v` line shapes; add the
optional `, Plan: approved <ts>` segment there and require §2b/§2c task descriptions
to carry it (the description is the text a human actually reads when choosing).

### 5. Sync / fold

- `.aitask-scripts/board/aitask_merge.py`: add
  `"plan_approved_at": (_normalize_opaque_scalar, True)` to `_BASE_AWARE_FIELDS`,
  with a comment saying why both generic rules are wrong — one-sided presence would
  let a stale carrier resurrect a marker another checkout deliberately cleared, and
  minute-resolution task-wide `updated_at` would let an unrelated `--status` edit
  win a field it never touched. `deletion_aware=True` because clearing removes the
  key (a `None` would serialize as `plan_approved_at: null`).
- `.aitask-scripts/aitask_fold_mark.sh`: no-op comment beside the `followup_kind` /
  `boardgroup` ones (scalar, primary keeps its own; folded file is deleted at
  archival).

### 6. Documentation

- The five task-format blocks that carry the same YAML listing:
  `seed/aitasks_agent_instructions.seed.md`, plus its marker-wrapped mirrors
  `AGENTS.md`, `.codex/instructions.md`, `.opencode/instructions.md` (edited by hand
  to stay byte-identical to the seed block, so the next `ait setup` regeneration is
  a no-op), and the condensed `CLAUDE.md` "### Task File Format" block.
- `website/content/docs/development/task-format.md` — a `plan_approved_at` row.
- `aidocs/gates/ledger-driven-reentry.md` §"'Approved and stopped' is not a routing
  signal" — the state is now visible in frontmatter; say that the marker is
  display/prompt-only, that routing is unchanged, and that the drift stop clears it.
  (The neighbouring claim that the recorded ledger entry is the only trace of an
  approved-and-stopped task becomes untrue otherwise.)
- `aidocs/framework/aitasks_extension_points.md` — a worked-example bullet for
  `plan_approved_at` naming the layers it touched and the ones it deliberately did
  not (no `aitask_create.sh` flag — update-only; board layer 3 ships separately).

### 7. Regeneration

- `./.aitask-scripts/aitask_skill_verify.sh`
- `./.aitask-scripts/aitask_skill_rerender.sh <profile>` for `default`, `fast`,
  `remote` (one call per profile; it walks every agent root).
- Regenerate and review the goldens in the same commit:
  `tests/golden/procs/task-workflow/{SKILL,planning,plan-approved-stop,task-abort}-*.md`
  and `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md`.

### Post-phase (risk mitigations)

Both confirmed inline; they run after step 7 and before the change is considered
complete.

- **`pin_writer_call_site_fanout`** — in `tests/test_plan_approved_at_roundtrip.sh`,
  add a case that drives the **parent child-completion** write path: give a parent
  task a marker, run `aitask_update.sh --batch <child> --status Done`, and assert the
  parent's `plan_approved_at` survives. That call site
  (`handle_child_task_completion` → `write_task_file`, ~line 1202) is the one a
  plain batch-update test never exercises, and it is where a missed positional drops
  the field silently. Negative control: the assertion must fail if positional 35 is
  omitted from that call site.
- **`pin_marker_lifecycle_contract`** — a new
  `tests/test_plan_approved_marker_contract.sh` asserting the marker's lifecycle is
  still wired at every site, against the **rendered** procedure surfaces
  (`.claude/skills/task-workflow-default-/`): `--plan-approved-at now` present in
  `plan-approved-stop.md`'s deferred branch, `--plan-approved-at ""` present in its
  drift branch, in `SKILL.md` Step 7, in `planning.md`'s create-from-scratch branch,
  and in `task-abort.md`. Assert by hit count per file, so a silent zero-match cannot
  read as a pass. Pin the consumption boundary in **both** directions: the clear is
  present in `SKILL.md`'s implementation body and in `cross-repo-child-assignment.md`
  Step 4, and **absent** from the risk-mitigation "before" stop block — a
  presence-only test would pass on a version that clears the marker everywhere,
  which is the specific mistake this boundary exists to prevent.

## Verification

- `bash tests/test_ls_display_and_filters.sh` — extended with a marker-carrying
  fixture task: the pinned full display line (field order included), a marker-less
  negative control, and both filters asserted **by hit count**. Also pins the decided
  visibility contract in both directions — the `Plan: approved` segment appears under
  `-v` and does **not** appear in plain output, while `--plan-approved` narrows the
  plain listing (in every listing mode, per the existing Test 4 loop).
- `bash tests/test_plan_approved_at_roundtrip.sh` (new, modelled on
  `tests/test_followup_kind_roundtrip.sh`) — `--plan-approved-at now` writes a
  well-formed timestamp; the value survives an unrelated `--status` update through
  each `write_task_file` call site; `""` removes the key; a malformed value is
  rejected non-zero.
- `bash tests/run_all_python_tests.sh --test-dir tests` for
  `tests/test_aitask_merge.py`, extended with a `TestMergePlanApprovedAt` class
  mirroring `TestMergeVerificationBaseline`: clear-beats-stale-carrier **both ways
  round**, advance-beats-unchanged, stale-unrelated-edit-does-not-win, both-advanced
  ⇒ PARTIAL, no-base ⇒ PARTIAL, plus the `deletion_aware` guard. Read only the last
  line for the verdict.
- `bash tests/test_skill_render_task_workflow.sh` and
  `bash tests/test_skill_render_aitask_pick.sh` — golden diffs; review the diff, it
  must contain only the intended prose changes.
- `bash tests/test_plan_approved_marker_contract.sh` (new, post-phase mitigation) —
  every lifecycle site still carries its `--plan-approved-at` command, by hit count,
  **and the boundary is pinned in both directions**: the clear appears in `SKILL.md`'s
  implementation body and in `cross-repo-child-assignment.md` Step 4, and does **not**
  appear in the risk-mitigation "before" stop block.
- `bash tests/test_plan_approved_marker_drift.sh` (new) — drives the **drift stop**,
  the path the visibility-not-routing constraint is load-bearing on. It reuses the
  real origin/clone fixture shape from `tests/test_remote_drift_check.sh`
  (`make_branch_mode_pair`), on a task carrying the marker with an externalized plan:
  1. **Positive control first** — run
     `aitask_remote_drift_check.sh --unsynced <base> <plan>` against the fixture and
     assert it reports `AHEAD:<n>` plus an `OVERLAP:<file>` for a file the plan
     references. Without this the test could "pass" while the drift branch is
     unreachable and nothing was ever exercised.
  2. Apply the documented `stop_reason=drift` sequence (the revert call with
     `--plan-approved-at ""`).
  3. Assert the state a re-pick would see: the `plan_approved_at` key is **absent**
     from the task file; `ait ls -v` no longer emits the `Plan: approved` segment for
     it; `ait ls --plan-approved` returns **0** hits (and `--no-plan-approved`
     returns it); and no implementation fork was reached — `git branch --list
     'aitask/<task_name>'` and `git worktree list` are both empty of it, which is
     what "stopped before implementation" means concretely.
  4. **Negative control** — the same fixture driven through the `deferred` sequence
     instead keeps the marker and keeps being returned by `--plan-approved`, so step
     3's assertions are capable of failing.
- `shellcheck .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_update.sh`
- End-to-end acceptance (manual, on a scratch task), **both re-pick outcomes**:
  - *No drift* — approve-and-stop → `ait ls -v` shows `Plan: approved <ts>` and
    `ait ls --plan-approved` returns it; re-pick under `default.yaml` → the prompt
    names the approved plan and recommends "Use current plan"; the Remote Drift Check
    still runs before any worktree fork; "Create plan from scratch" clears the marker.
  - *Drift* — advance `origin/main` on a file the plan targets, re-pick, take "Stop
    and re-verify plan" at the drift prompt → the marker is gone, `ait ls -v` no
    longer advertises a deferred-approved plan, no `aitask/<task_name>` branch or
    worktree exists, and the following re-pick shows the plain (unenriched) 3-way
    prompt.

## Risk

*(Levels reassessed once after the two inline post-phases below were confirmed.)*

### Code-health risk: medium
- `write_task_file` in `aitask_update.sh` takes the new field as **positional 35**,
  read by three call sites. Any site not updated silently drops the marker on the
  next update through that path — the field disappears with no error, which is the
  exact failure mode the in-file comments already warn about · severity: medium ·
  → mitigation: inline post-phase pin_writer_call_site_fanout
- The lifecycle is carried by **prose** across four procedure files
  (`plan-approved-stop.md` set/clear, `SKILL.md` Step 7 clear, `planning.md` §6.0
  replan clear, `task-abort.md` clear). A later edit that drops one leaves a marker
  that actively lies — "an approved plan is awaiting implementation" for a plan that
  was discarded · severity: medium ·
  → mitigation: inline post-phase pin_marker_lifecycle_contract
- Residual after both guards: the change still fans out across `ait ls`, the merge
  rule, five task-format doc mirrors and the rendered-skill goldens — breadth the
  guards do not shrink, which is why this axis stays `medium` · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: low
- The marker's value depends on its invalidation being reliable; a missed clear site
  would display a stale approval, which is worse than today's silence. Now pinned by
  an executable contract rather than by prose discipline · severity: medium ·
  → mitigation: inline post-phase pin_marker_lifecycle_contract
- Requirement coverage is otherwise direct (marker + `ait ls` + pick prompt), works
  under `default` by construction (frontmatter, not the ledger), and leaves routing
  untouched · severity: low · → mitigation: none needed

### Planned mitigations
- timing: post-phase | name: pin_writer_call_site_fanout | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: positional-35 fan-out across `write_task_file` call sites | desc: round-trip case driving the parent child-completion write path, asserting the parent's marker survives a child `--status Done` update
- timing: post-phase | name: pin_marker_lifecycle_contract | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: prose drift across the four lifecycle sites / stale-marker risk | desc: executable contract test asserting each lifecycle site still carries its `--plan-approved-at` command in the rendered procedure surfaces, and that the consumption boundary holds in both directions (present in the implementation body and the cross-repo demotion, absent from the risk-mitigation "before" stop)

## Post-Review Changes

Round 1 — two blocking review findings, both CONFIRMED against the rendered
surfaces, plus one further defect the second fix exposed:

1. **`plan-approved-stop.md` had no mechanical branch.** It rendered both
   commands labelled only by `# stop_reason=…` comments, so a drift-stop agent
   could run the `deferred` command and refresh the marker on the very path that
   established re-verification is required. Rewritten as two explicit
   "If `stop_reason` is X, run **only** this" bullets plus a "never both" rule
   and a stated no-third-case. Pinned by a **positional** assertion in
   `tests/test_plan_approved_marker_contract.sh`: each reason's conditional
   header must precede its own command and precede the other reason's header
   (`deferred → now → drift → clear`), so rendering both commands without a
   selecting conditional fails.

2. **`planning.md`'s prompt never spelled out the recommended labels.** It said
   "mark it as recommended" while the concrete option list still read
   `"Use current plan"`, and the force-verify path named no label at all. The
   prompt is now a three-row table keyed on `force_verify` / marker presence,
   naming the exact literals `"Use current plan (Recommended)"` and
   `"Verify plan (Recommended)"`, with explicit "only one option may carry the
   suffix" and "force_verify outranks the marker" rules. Both literals and both
   rules are pinned in the contract test.

3. **Exposed while compressing (2): the "Clearing on replan" block lived inside
   the interactive-only Jinja branch.** Under `fast` / `remote` the profile-driven
   `create_new` bullet referenced a section that never rendered, and those
   profiles carried no clear command at all. Re-homed into the profile-invariant
   §6.0-marker section. The contract test now asserts the clear command renders
   in **all three** profile surfaces, not just `default` — the assertion that
   would have caught it.

The compression in (2) was required rather than optional: `test_skill_render_task_workflow.sh`
asserts the lean (`default`) render stays strictly smaller than the risk (`fast`)
render of both `SKILL.md` and `planning.md`, and the first, verbose three-variant
draft inverted it. The guard was preserved, not relaxed; fixing (3) moved eight
lines out of the interactive-only branch and restored the original 15-line margin.

## Final Implementation Notes

- **Actual work done:** `plan_approved_at` shipped exactly as planned — write path
  in `aitask_update.sh` (positional 35, `now` / `<ts>` / `""`, fail-closed
  validation, threaded through all three `write_task_file` call sites); the
  lifecycle across five task-workflow procedure sources; `ait ls -v` display plus
  `--plan-approved` / `--no-plan-approved`; the §6.0 prompt variants; the
  deletion-aware base-aware merge rule; the fold no-op comment; and the doc set
  (five task-format mirrors, two website pages, two aidocs). Rendered to all three
  profiles × three agents, goldens regenerated and reviewed.
- **Deviations from plan:** three, all additive.
  1. `get_timestamp` lives in `aitask_update.sh`, not `lib/task_utils.sh` as the
     plan assumed; the `now` resolution went there instead. Same single-home
     property.
  2. The commands in `plan-approved-stop.md` / `task-abort.md` /
     `cross-repo-child-assignment.md` are written on ONE line rather than
     backslash-wrapped: several existing suites pin `--status Ready --assigned-to ""`
     as a contiguous substring, and wrapping silently voided those guards.
     Unwrapping keeps every one of them meaningful and unmodified.
  3. Added `website/content/docs/workflows/parallel-planning.md` — a
     "Deferring a single task's implementation" section. Not in the plan's doc
     list, but it is the user-facing workflow this marker exists to enable; the
     field tables alone documented the mechanism and not the use.
- **Issues encountered:**
  - The first three-variant prompt draft inverted
    `test_skill_render_task_workflow.sh`'s leanness invariant (the `default`
    render must stay smaller than the `fast` one). The variants were compressed
    into a table rather than relaxing the guard.
  - That compression exposed a real defect: the "Clearing on replan" block sat
    inside the interactive-only Jinja branch, so `fast` / `remote` rendered a
    dangling "see Clearing on replan" reference with no command behind it.
    Re-homed to the profile-invariant §6.0-marker section; the contract test now
    asserts the clear renders in all three profile surfaces.
  - A concurrent session is working in this checkout (it committed t1590 mid-task
    and has t1275 in flight). The commit names paths explicitly and excludes
    `.aitask-scripts/aitask_remote_drift_check.sh`,
    `tests/test_remote_drift_check.sh` and
    `aidocs/framework/plan_path_reference_extraction_findings.md`.
    `tests/test_plan_approved_marker_drift.sh` is independent of that in-flight
    change: its fixture path (`.aitask-scripts/aitask_archive.sh`) satisfies both
    the old root allowlist and the new unfiltered extraction.
- **Key decisions:**
  - **The consumption boundary is the implementation body, not the top of Step 7.**
    Two Step-7 gates revert to `Ready` before any code is written and need
    opposite treatment — a cross-repo demotion clears the marker (no single-task
    plan remains), the risk-mitigation "before" stop keeps it (approved and
    awaiting, merely blocked). The boundary is pinned in BOTH directions, because
    a presence-only test passes on a build that clears everywhere.
  - **`ait ls` display is verbose-only; the filter is the non-verbose affordance.**
    No metadata has ever appeared in the plain listing and every script consumer
    parses it as a bare filename list. Both directions are pinned.
  - **The drift stop clears rather than refreshes** (the user's call at planning),
    and the branch is now mechanically explicit rather than comment-labelled.
  - **Upstream defects identified:** `.codex/instructions.md` and
    `.opencode/instructions.md` — the `>>>aitasks` task-format block in both
    mirrors is missing the `gates:` / `active_gates*` lines that
    `seed/aitasks_agent_instructions.seed.md` and `AGENTS.md` carry. Pre-existing
    drift from the `_is_agent_installed` gating that
    `aidocs/framework/aitasks_extension_points.md` warns about; untouched here
    beyond keeping the new field consistent across all four.

## Step 9 (Post-Implementation)

Standard closure: cleanup, `## Final Implementation Notes`, gate run
(`risk_evaluated` is the task's enforced active gate), merge and archival per
`SKILL.md` Step 9. A **board follow-up task** (surface the marker on the kanban card
and/or the in-flight view) is created at Step 8d with an explicit `depends: [1595]`.
