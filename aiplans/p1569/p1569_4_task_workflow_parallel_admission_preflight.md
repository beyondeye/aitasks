---
Task: t1569_4_task_workflow_parallel_admission_preflight.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_6_backlog_roadmap_skill_and_trail_authoring.md, aitasks/t1569/t1569_7_manual_verification_background_work_roadmap.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_1_gatherer_inflight_and_planned_surface_facts.md, aiplans/archived/p1569/p1569_2_batch_task_file_sets_and_origin_resolution.md, aiplans/archived/p1569/p1569_3_shared_parallel_admission_checker.md, aiplans/archived/p1569/p1569_5_roadmap_scoring_freshness_and_lanes.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-02 11:40
---

# t1569_4 — `task-workflow` parallel-admission preflight

**Verification pass — 2026-09-01/02.** The plan below is the 2026-08-27 plan
re-verified against today's codebase. Everything in "What verification changed"
is a correction to the original; the rest stands.

## Context

`t1569_3` landed the shared parallel-admission checker
(`.aitask-scripts/aitask_parallel_admission.sh` + `lib/parallel_admission*.py`).
It has one consumer today (`t1569_5`, the roadmap's advisory preview) and no
required one. This task is consumer #1: wire the *same* checker into
`task-workflow` as a required preflight so the framework has an authoritative
check against other active tasks, not just ownership locks and a remote-drift
comparison.

Order is load-bearing: the drift check can pull the base branch, which changes
what is in flight. The preflight runs **after** it, never before.

> **Direction change — read finding 7 first.** This task ships the preflight
> **advisory-only**: no verdict ever stops the workflow on its own. That is a
> deliberate, user-directed deviation from the task file's "CONFLICT's
> disposition is stop-and-replan in both `block` and `warn` — that is the design
> and it does not change", and the task file is corrected as part of the work.
> There is **no blocking prerequisite**; this plan is implementable as it stands.

---

## What verification changed

Seven findings. Each is a correction the original plan cannot be implemented
correctly without. Finding 7 is the one that changes the design, and is placed
last because it depends on the live evidence recorded just above it.

### 1. The `UNCHECKABLE_CAUSE` recovery table named codes that do not exist

The original plan keyed the operator remedy table on `no_plan_file`,
`all_phantom`, `locks|unavailable` and `candidate|<reason>`. The real closed
vocabulary is `.aitask-scripts/lib/parallel_admission_vocab.py`
(`UNCHECKABLE_REASONS`), and only `all_phantom` was right.

Record grammar is `UNCHECKABLE_CAUSE:<scope>|<reason>`, split on the **first**
`|`. Scopes are `candidate`, `locks`, `inflight:<task-ref>` and
`inflight:<source>` where source ∈ `gate|lock|status`
(`parallel_admission.py:246-256, 300-306`).

| scope | reason codes | remedy to print |
|---|---|---|
| `inflight:<ref>` | `no_plan` | plan it, or `ait lock --unlock <ref>`, or override for that task |
| `inflight:<ref>` | `all_phantom` | that plan is stale — refresh or release it |
| `inflight:<ref>` | `no_tokens`, `unreadable`, `unclassified`, `no_extractable_paths` | that plan declares no usable surface — add concrete paths, or release the claim |
| `inflight:<ref>` | `unknown_history`, `unknown_origin` | no reachable commits for that id — it may predate the history in this checkout; `git fetch`, or override for that task |
| `candidate` | any `SURFACE_RESOLUTIONS` value | **this** plan declares no resolvable surface — add concrete repo paths to it |
| `locks` | `no_local_ref`, `unreadable_tree`, `no_reflog`, `clock_skew`, `timeout`, `scan_error` | the lock ref could not be read — check the network and re-run |
| any | `source_unavailable:<gate\|lock\|status>` | that probe did not answer — re-run; if it persists, `ait lock --list` / `ait gates` diagnose it |

Do **not** hand-write these strings anywhere but the procedure's table; parse
with the grammar above so an unlisted code is reported verbatim rather than
silently swallowed.

### 2. A user-elected stop needs a **fourth** `stop_reason`, and the vocabulary is guarded

`plan-approved-stop.md` closed its `stop_reason` vocabulary at three
(`deferred`, `drift`, `resource_admission`) with an explicit exhaustiveness
sentence, and `tests/test_plan_approved_marker_contract.sh:132` asserts that
sentence verbatim. The procedure offers "Stop and re-plan" as a **user choice**
on any non-CLEAR verdict (finding 7: nothing stops automatically), and that
choice must release the lock and revert cleanly — so it reuses the sequence, and
therefore has to register itself.

**New reason: `parallel_admission`, on the *clearing* side.** It joins `drift`,
not `resource_admission`: this stop establishes that the plan must be re-checked
against what else is in flight before it may be implemented, so leaving
`plan_approved_at` stamped would advertise a plan as implementation-ready on
exactly the path that just established it is not. (`resource_admission` stamps
because the *host*, not the plan, was the problem — the plan stayed intact.)

### 3. `remote.yaml` must be `off`, not `warn`

`remote` is `headless: true` — "no interactive prompts". Under `warn`,
UNCHECKABLE still prompts for explicit confirmation, which a headless profile may
not do. The original plan said "add the knob to `{default,fast,remote}.yaml`"
without naming values. Values are `default: warn`, `fast: warn`, `remote: off`.

### 4. Website docs were omitted

t1597 — the structural twin, landed after this plan was written — shipped
`website/content/docs/skills/aitask-pick/resource-admission.md`, a `_index.md`
step-8 sentence, and lives in the profile-knob table. Introducing
`parallel_admission` falsifies the neighbouring knob table if it is not added.
Scope: the new knob's own row and page only. (The table is *already* stale —
missing `remote_drift_check`, `default_gates`, `rendered_gates`,
`max_parallel_gates`, `headless`, and still listing the removed
`risk_evaluation`. Out of scope; spawn a documentation follow-up.)

### 5. The golden test carries hardcoded lists and counts

`tests/test_skill_render_task_workflow.sh` names every wrapped file in
`WRAPPED_FILES_VARYING` / `WRAPPED_FILES_INVARIANT`, and its header and Test-1
banner state "17 wrapped .md files", "33 golden files", "8 profile-varying".
`parallel-admission.md` is profile-**varying** (finding 3 makes `remote` diverge),
so: 18 files, 36 goldens, 9 varying, and three new goldens
`parallel-admission-{default,fast,remote}.md`.

### 6. `planning.md` has **three** textual drift-check sites, not two

`planning.md:490` and `:499` are the two arms of one Jinja `if/else` over
`post_plan_action`; `:514` is the interactive "Start implementation" branch. All
three need the preflight inserted in source; any single rendered profile shows
two. "Two call sites" in the acceptance criteria means *(planning Checkpoint,
SKILL.md IMPLEMENT re-entry)* — unchanged.

### Considered and rejected: a single Step-7 call site

`resource-admission.md:428` proves one Step-7 site covers both routes ("reaching
Step 7 at all means the plan was approved and the Remote Drift Check returned
'Continue anyway'"), which would be simpler. Rejected: the procedure offers
"Stop and re-plan" as a user choice (finding 7), and the planning Checkpoint is
where the "Revise plan" loop lives — a Step-7 site has no replan affordance to
offer. The task file's t1597 coordination note reaffirms the Checkpoint
placement, and the ordering it mandates — parallel (correctness) before resource
(capacity) — holds because the Checkpoint precedes Step 7.

### Live evidence has moved on (record, do not act on)

The plan's "Deviation, with evidence" cites a 2026-08-27 measurement of "100%
UNCHECKABLE". Re-measured today against the same candidate:

```
$ aitask_parallel_admission.sh check --candidate 1569_4 --from plan \
    --plan aiplans/p1569/p1569_4_*.md --lock-freshness allow-cached
VERDICT:CONFLICT
DISPLAY:conflict with 1663_1 on 1 file(s): .aitask-scripts/aitask_audit_wrappers.sh
```

13 in-flight tasks; 3 `no_plan`; 2 `dead`; t259 now `lock_only` at 186d.
Self-exclusion works live — `1569_4` is claimed and locked yet absent from every
`INFLIGHT:` row.

**The CONFLICT is a false positive, and instructively so.** Neither this plan nor
`t1663_1`'s *edits* `aitask_audit_wrappers.sh`; both merely *invoke*
`apply-helper-whitelist` (`p1663_1:294`). Meanwhile the five files both tasks
genuinely edit — `.claude/settings.local.json`, `seed/claude_settings.local.json`,
`seed/codex_rules.default.rules`, `.codex/rules/default.rules`,
`seed/opencode_config.seed.json` — were demoted to `hub` caveats (57–65 touches
each). The checker hard-stopped on a tool path and caveated the real collision.

### 7. Direction change — advisory-only, and no mandatory hard stop

**This supersedes the original plan's CONFLICT disposition, by explicit user
decision.** Recorded here rather than applied silently, because it contradicts an
acceptance criterion the task file states in bold.

The chain that got us here:

1. The `warn` default does **not** soften a CONFLICT — stop-and-replan was
   unconditional in both modes, by the task's own design. So the false hard stop
   measured above survived the shipped default in full.
2. Making the hard stop safe would mean teaching the extractor Markdown fences,
   shell command grammar, argument positions, a closed list of "safe runner"
   binaries, redirection and heredoc forms, **and** threading that provenance
   through `plan_paths.extract()` → `Surface.paths` (both of which are today just
   strings), **and** a further consumer layer in the checker to act on it.
3. That is a custom shell/Markdown parser built to preserve one policy choice.
   The machinery is disproportionate to the false alarm it fixes, and each layer
   is a new place to be wrong.

**Decision: drop the mandatory stop, not build the parser.** With no verdict able
to stop the workflow by itself, heuristic plan parsing can no longer cost a user
a forced replan — the false-positive rate stops being a safety question and
becomes a noise question, which is the right register for a heuristic.

**This is not a lone exception — it matches the family.** `t1343`
(`t1343_parallel_agent_file_conflict_advisory.md`, `Ready`, high/high) is the
owner of the declared-claims registry that this checker's own module docstring
defers to for closing the residual race. Its stated goal is *"An **advisory**
(never blocking, never auto-acting) signal"* answering "is this task safe to
progress from planning into implementation right now?" — the **same** verdict at
the **same** boundary. A mandatory-stop t1569_4 was the outlier in its own family;
advisory-only makes the two consistent.

**The structured "files this task will edit" declaration — the preferred
long-term basis for any hard conflict — is t1343's, and is not re-spawned here.**
t1343 already establishes exactly that: *"Each running task must **declare** what
it intends to touch. That declaration is the core new artifact."* The finding
belongs to the owning task. What t1569_4 owes it is a **coordination note in
both directions**: when a declared, structured edit list exists, it — not
regex-scraped plan prose — becomes the only admissible basis for a hard conflict,
and an absent or unclear declaration requires confirmation rather than a guess.

**`admission_surface_invoked_vs_edited` is withdrawn**, not deferred: it exists
only to make a mandatory stop safe, and there is no longer a mandatory stop. The
false CONFLICT it addressed remains real and is now simply noise in an advisory
signal, recorded in the Final Implementation Notes as calibration evidence.

**Deliverables this adds — see Step 7, which enumerates every site.** The
retraction is not one sentence: the task file states the old policy normatively
in thirteen places, the parent's flow diagram in one, and a **shipped** procedure
(`resource-admission.md`) implies it in one more. An acceptance criterion that is
no longer the design must not be left standing anywhere, or the correct
implementation reads as a regression.

## Implementation

### Pre-phase (risk mitigations)

Both run **before** Step 1. Each is a test-harness hardening that must be green
on the pre-change tree, so it also serves as the negative control for the change
that follows.

- **`pin_procedure_and_golden_inventory`** — in
  `tests/test_skill_render_task_workflow.sh`, replace the counts-in-header-prose
  with executable assertions: the union of `WRAPPED_FILES_VARYING` and
  `WRAPPED_FILES_INVARIANT` must equal the actual `*.md` inventory of
  `.claude/skills/task-workflow/`, and every listed file must have its expected
  goldens present in `tests/golden/procs/task-workflow/` (3 for a varying file, 1
  for an invariant one). Verify it **fails** on the pre-change tree once
  `parallel-admission.md` exists but is unlisted — that is the regression it
  exists to catch.
- **`pin_stop_reason_branch_position`** — in
  `tests/test_plan_approved_marker_contract.sh`, derive the reason list from the
  exhaustiveness sentence in `plan-approved-stop.md` rather than restating it,
  and assert generically that every named reason appears in exactly one branch
  clause and on the correct side of the stamp/clear commands. This replaces
  adding a fourth hardcoded block, and makes required test #5 fall out of the
  generic assertion.

### Step 1 — `.claude/skills/task-workflow/parallel-admission.md` (new)

Shaped like `remote-drift-check.md`: title, one-paragraph statement of both call
sites, an **Input context** table (`task_id`, `task_num`, `plan_file`,
`active_profile`), the invocation, output parsing, a disposition per verdict, and
Notes.

Three-way Jinja gate on the knob, mirroring `remote-drift-check.md`'s
`{% if %}/{% else %}` shape (the `else` arm keeps a runtime "Profile check"
sentence so a user-authored profile still works):

- `parallel_admission == "off"` → return immediately, no display.
- `parallel_admission == "confirm"` → CLEAR_CAVEATED also requires confirmation.
- otherwise (**default `warn`**) → CLEAR_CAVEATED renders a visible note.

**Invocation** (bind `plan_file`; never paste a literal):

```bash
./.aitask-scripts/aitask_parallel_admission.sh check \
  --candidate <task_id> --from plan --plan "<plan_file>" \
  --lock-freshness require-fresh
```

State in the procedure text *why* each part is non-negotiable:

- `require-fresh` — a cached lock ref hides a lock another agent took seconds
  ago: a false CLEAR at exactly the admission point this exists to defend.
- The checker excludes the candidate itself. `task-workflow` set the task
  `Implementing` and locked it at **Step 4**, long before the plan existed, so
  without exclusion every pick conflicts with its own plan. Verified live above.
- Re-read live state at call time; never reuse a roadmap snapshot.
- Every content state exits 0 — read `VERDICT:`, never the exit status.

**Invalid or unusable output is UNCHECKABLE, never a pass.** The procedure
accepts a result only when stdout carries **exactly one** `VERDICT:` line whose
token is one of `CLEAR`, `CLEAR_CAVEATED`, `CONFLICT`, `UNCHECKABLE`. Everything
else takes the **UNCHECKABLE disposition** — explicit confirmation or abort,
never an auto-proceed:

| observed | treated as |
|---|---|
| exit 2 (CLI misuse) | UNCHECKABLE · report it as a **wiring error**, naming the stderr line |
| any other non-zero exit, or a crash | UNCHECKABLE · report the exit status |
| empty stdout, or no `VERDICT:` line | UNCHECKABLE |
| more than one `VERDICT:` line | UNCHECKABLE · never pick one |
| a `VERDICT:` token outside the closed set | UNCHECKABLE · quote the token verbatim |
| an `UNCHECKABLE_CAUSE:` code the table above does not list | still UNCHECKABLE · print the raw reason field verbatim rather than swallowing it |

Label these `checker unusable` and say plainly that the cause is
**procedure-originated, not a checker verdict** — it is not a member of
`UNCHECKABLE_REASONS` and must not be reported as one. Capture stdout with the
`if`-form (`if out="$(…)"; then rc=0; else rc=$?; fi` — a bare `out="$(…)"; rc=$?`
dies under `set -e` before `rc` is read) and **never merge stderr into stdout**:
every line parsed here is `KEY:value`, and merging corrupts the parse. Both rules
are `resource-admission.md`'s, for the same reasons.

Fail-safe, not fail-open: a lock fetch that cannot reach the remote, a parser
change, or a helper crash must never read as "no known conflict".

**Dispositions:**

| verdict | disposition |
|---|---|
| `CLEAR` | proceed, worded **"no known conflict at check time"** — never "safe to run in parallel" |
| `CLEAR_CAVEATED` | `confirm`: confirmation naming the unverified source. `warn`: a visible note. **Rendered distinctly from CLEAR in both modes.** |
| `CONFLICT` | **advisory** — name the overlapping task(s) and file(s) from `OVERLAP:` and require explicit confirmation to continue. **Continuing is the default action**; stopping is offered, never imposed |
| `UNCHECKABLE` | **explicit confirmation**, naming *why*, with the finding-1 remedy for each cause. Never auto-proceed |

Prompt shape mirrors `remote-drift-check.md` step 4/5 — options
"Continue anyway" / "Stop and re-plan" / "Abort task", **in that order** —
continuing is listed first because the signal is advisory and its false-positive
rate is measured, not assumed. "Stop and re-plan" executes the **Approved-Plan
Stop Sequence** with `stop_reason=parallel_admission`; "Abort task" executes the
**Task Abort Procedure**. Neither is ever selected automatically.

Notes must state: the **residual race** (this observes, it does not reserve —
overlapping work can begin the instant after it passes; closes only with t1343);
that it is **not a gate** (`MANUAL_VERIFICATION_REACHABLE_GATES` is an allowlist
and `filter_gates_for_issue_type()` would silently strip one — precedent:
plan-verification staleness, a step in `planning.md`); and that it is **distinct
from resource admission** (correctness before capacity), reciprocating
`resource-admission.md`'s existing pointer.

### Step 2 — Register the fourth `stop_reason`

In `plan-approved-stop.md`:

- Header call-site list: three → four, adding
  `parallel-admission.md` → `stop_reason=parallel_admission`.
- Input-context table: add `parallel_admission` to the `stop_reason` row.
- Marker-disposition table: new row — `parallel_admission` | *must be re-checked
  against in-flight work before it can be implemented* | **clear**.
- The `drift` branch clause becomes "**If `stop_reason` is `drift`** … **or
  `parallel_admission`**", positioned **after** `now_cmd` and before
  `clear_cmd` so the existing positional guard still holds.
- Exhaustiveness sentence: "exactly `deferred`, `drift`, `resource_admission` or
  `parallel_admission`".
- Notes: no worktree exists at the planning-Checkpoint call site (pre-Step-7
  fork); on the IMPLEMENT re-entry route a worktree from the earlier session
  **may** exist and is left in place, as with the risk-mitigation stop.

### Step 3 — Wire the two call sites

**`planning.md` Checkpoint** — after each of the three drift-check invocations
(`:490`, `:499`, `:514`), on the path where the drift check returned "Continue
anyway" and before proceeding to Step 7:

> Then execute the **Parallel-Admission Preflight Procedure** (see
> `parallel-admission.md`) with `task_id`, `task_num`, `plan_file` and
> `active_profile`. It never ends the workflow on its own; if the **user** chose
> to stop or abort, do NOT proceed to Step 7.

**`SKILL.md` Re-entry Routing, `IMPLEMENT` route** — a new labelled paragraph
immediately after "**Remote drift check (re-entry).**" (`:312`) and before the
"Then re-run **only** …" sentence (`:316`), which is amended to say the preflight
precedes that list. Do **not** add it to `POSTIMPL`: the code is already
committed and the only actionable branch would revert reviewed work.

For a child task, `task_num` is the **child** id (`1569_4`) — the rule
`resource-admission.md` and `plan-approved-stop.md` both state.

### Step 4 — Profile knob

`parallel_admission: confirm | warn | off` in
`aitasks/metadata/profiles/{default,fast,remote}.yaml` **and** the `seed/profiles/`
mirrors — `default: warn`, `fast: warn`, `remote: off` (finding 3). Note
`fast.yaml` and `seed/profiles/fast.yaml` already differ in five keys; add the
new key to both without reconciling the rest.

Document the knob in `.claude/skills/task-workflow/profiles.md`'s schema table
(next to `remote_drift_check`, its model).

**What `profiles.md` must say — this is the whole of it.** The paragraph an
earlier draft carried here was inherited from the pre-advisory design and said
the opposite; it is deleted, not amended, because a half-corrected instruction is
the one an implementer copies verbatim.

- **No value of this knob ever stops the workflow.** It governs only how loudly a
  non-CLEAR verdict is surfaced. Every stop is a user choice made at the prompt.
- `confirm` — every non-CLEAR verdict requires explicit confirmation to continue.
- `warn` (**the default**) — CONFLICT and UNCHECKABLE require confirmation;
  CLEAR_CAVEATED renders as a visible note, distinct from CLEAR.
- `off` — whole-step no-op.
- **There is deliberately no `block` value.** A value named for a behaviour the
  procedure does not have would be a lie. Any future hard-stop mode is gated on
  t1343's structured per-task declaration — not on this knob, and not on
  heuristic extraction from plan prose.
- `warn` is the default because the signal is heuristic: it reads paths scraped
  from plan text, and a measured false positive is on record (finding 7). Say
  that plainly rather than implying the check is authoritative.

Carry **no** promotion criterion, no `block` entry condition, and no threshold
tuning guidance into `profiles.md`: t1643's grading curve selected which verdict
hard-stopped, and no verdict hard-stops any more. Those figures live in this
task's Final Implementation Notes, labelled superseded, for t1343.

Everything above is a **claim about behaviour** and must therefore agree with the
rendered procedure, not merely with this plan — see required test #4, which
asserts the agreement in both files.

### Step 5 — Renders, goldens, whitelist

```bash
./.aitask-scripts/aitask_skill_rerender.sh
./.aitask-scripts/aitask_skill_verify.sh
```

Regenerate `tests/golden/procs/task-workflow/` in the **same commit**, and update
`tests/test_skill_render_task_workflow.sh` per finding 5.

**No Codex / OpenCode port task.** `parallel-admission.md` is shared-closure
content with no `{% if agent %}` gates and Claude is the single source
(`SOURCE_AGENT_ROOT = ".claude/skills"`), so the other trees auto-render.
Procedures are discovered by reference, not a manifest — no registration needed
beyond the call sites.

**The helper whitelist is** an agent-specific surface and is **not yet present**
for this helper (verified: zero hits across all five touchpoints):

```bash
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_parallel_admission
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_parallel_admission
```

Five touchpoints, confirmed against
`aidocs/framework/aitasks_extension_points.md:300-306`:
`.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`. `discover-helpers` only finds a helper whose
literal path appears in a skill closure, so this step runs **after** Step 1.

> **Coordination:** `t1663_1` is in flight and will append to the same five
> files for its own helper. Appends to distinct lines — mergeable — but expect
> to rebase.

### Step 6 — Website docs

- New `website/content/docs/skills/aitask-pick/parallel-admission.md`, modelled
  on the sibling `resource-admission.md`: what it asks, the four verdicts, the
  knob, and the honest statement that CLEAR means "no known conflict at check
  time".
- `website/content/docs/skills/aitask-pick/_index.md`: extend the step-7/8
  prose so the preflight is named alongside the resource-admission hook, and add
  a "Related"-style pointer to the new page.
- `website/content/docs/skills/aitask-pick/execution-profiles.md`: one new knob
  row for `parallel_admission`. Do not fix the table's pre-existing staleness.

---

### Step 7 — Retract every superseded normative statement

The advisory-only redesign invalidates far more than one sentence. Left standing,
these read as **live acceptance criteria**, and a future reader or test author
would reasonably treat the correct implementation as a regression. All of it
lands in the **same commit** as the procedure.

**Rule:** every *normative* statement of the old policy is replaced with the
`confirm | warn | off` and user-choice semantics. Historical measurements are
**kept**, but only where explicitly relabelled as superseded evidence — the
numbers stay useful to t1343, the conclusions drawn from them do not.

**`aitasks/t1569/t1569_4_*.md` — thirteen sites, verified by inspection:**

| line | stale statement | replacement |
|---|---|---|
| `:35` | flow diagram ends `proceed / confirm / stop-and-replan` | `proceed / confirm / stop (user choice)` |
| `:65` | CLEAR_CAVEATED "require explicit confirmation under `block`" | under `confirm` |
| `:69` | CONFLICT "**stop-and-replan by default**" | advisory: name the tasks/files, require confirmation, continue listed first |
| `:98` | `parallel_admission: block \| warn \| off` | `confirm \| warn \| off` |
| `:101` | bold "CONFLICT's disposition is stop-and-replan in both `block` and `warn` — that is the design and it does not change" | **struck**, with a one-line reason and a pointer to this plan's finding 7 |
| `:105-110` | "Deviation, with evidence": ships `warn` not `block`; "only the hard stop is deferred" | there is no `block` value and no deferred hard stop; the 2026-08-27 rates are relabelled **superseded evidence** |
| `:165-167` | required test 4: rates are "the evidence for any later promotion of the default to `block`" | calibration evidence handed to **t1343** |
| `:172` | t1643 "supersedes t1569_3's rates as the input to this task's `warn` → `block` decision" | no such decision exists; relabel as superseded input |
| `:185-192` | t1643 grading: "Because `CONFLICT` stops and `CLEAR_CAVEATED` merely confirms, the threshold decides which of the two a real collision gets… Any `block` criterion has to name an acceptable point on that curve" | **premise no longer holds** — both verdicts confirm, so the hub threshold now selects only prompt wording. Keep the ~32% / ~67% figures, labelled superseded |
| `:216` | knob quoted as `block\|warn\|off` in the t1597 note | `confirm\|warn\|off` |
| `:221` | "The parallel preflight — **which can stop-and-replan** — runs first" | "which is advisory and never stops on its own" — the *ordering* claim (correctness before capacity) still holds and stays |
| `:224` | "A CONFLICT stops and replans; a resource refusal parks with the plan intact" | "A CONFLICT confirms; a resource refusal parks" — the contrast survives and sharpens |
| `:231` | "If the parallel preflight's **stop-and-replan** reuses that sequence…" | still true, but only for the **user-elected** stop; reword and keep the obligation |

**`aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md` (parent),
`:74`** — the same flow diagram, same fix. The parent's "required preflight"
wording elsewhere stays correct: the preflight still always runs; only its
disposition changed.

**`.claude/skills/task-workflow/resource-admission.md` — one shipped clause.**
Its last Note contrasts its own availability with "a checker that reads shared
state it does not control… before letting it **block**". That premise is now
false and, in a *shipped* procedure, is the version of this claim a reader is
most likely to meet. Reword to name the advisory disposition. Its two Notes about
ordering and non-foldability are unaffected and stay verbatim.
`resource-admission.md` is already in `WRAPPED_FILES_INVARIANT`, so
`tests/golden/procs/task-workflow/resource-admission-default.md` regenerates with
the rest in Step 5.

**Bidirectional coordination with t1343** (`.aitask-data/aitasks/t1343_*.md`):
t1569_4 ships the advisory preflight at the planning→implementation boundary
t1343 also targets; when t1343's structured declaration exists it — not
regex-scraped plan prose — becomes the only admissible basis for a hard conflict,
and an absent or unclear declaration requires confirmation rather than a guess.
Add the reciprocal pointer in t1569_4's own file.

Use `./ait git` for every task file — they live on the data branch.

**Guard:** after the sweep, `grep -n 'block' ` over both task files must return
only occurrences inside a passage explicitly labelled superseded, or the
"deliberately no `block` value" statement. A bare normative `block` surviving
anywhere is the regression this step exists to prevent, and it is cheap enough to
assert in `tests/test_task_workflow_reentry_drift.sh` alongside the ordering
contract.

## Verification

```bash
./.aitask-scripts/aitask_skill_verify.sh
bash tests/test_skill_render_task_workflow.sh
bash tests/test_plan_approved_marker_contract.sh
bash tests/test_task_workflow_reentry_drift.sh
bash tests/run_all_python_tests.sh --test-dir tests      # last line only
git diff --stat tests/golden/procs/task-workflow/        # empty after regeneration
```

Piping discards the status — use `set -o pipefail` or `${PIPESTATUS[0]}`.

### Required tests

1. **`tests/test_parallel_admission_preflight.sh`** (new) — drive the **real**
   helper over synthetic roots for each of CLEAR / CLEAR_CAVEATED / CONFLICT /
   UNCHECKABLE and assert the procedure's disposition text for each. Reuse the
   fixture shape of `CollectIntegrationTests`
   (`tests/test_parallel_admission_collect.py:254`), which already produces
   CONFLICT / CLEAR / UNCHECKABLE from a synthetic root. Assertions run inside
   `( … )` subshells ⇒ `assert_counters_init` / `assert_counters_load`.

   **Plus the unusable-output path, driven for real, not asserted in prose:**
   invoke the helper into exit 2 (`check --from plan`, no `--candidate`) and into
   a `--plan` target that does not exist, and assert the procedure's
   *UNCHECKABLE / checker unusable* disposition — never a proceed. Add a stub on
   `PATH` emitting two `VERDICT:` lines, and one emitting an out-of-vocabulary
   token, to reach the duplicate and malformed rows of Step 1's table: the real
   helper cannot produce those states, and a table row no test can reach is not a
   guard.
2. **Self-exclusion end-to-end** — claim a task exactly as Step 4 does
   (`./.aitask-scripts/aitask_pick_own.sh <id> --email …`), write a plan, run the
   preflight, assert `CLEAR` and **no `INFLIGHT:` row for the candidate**. This
   drives the *real* claim path; the existing
   `test_the_candidate_is_excluded_from_its_own_comparison` injects
   `_LOCK_PROBE`/`_STATUS_PROBE` replicas and cannot see a Step-4 regression.
   Fresh fixture per invocation.
3. **Ordering contract** — extend `tests/test_task_workflow_reentry_drift.sh`
   (its `slice_between` + negative-control harness is exactly this shape): pin
   that the preflight reference appears **after** the drift-check reference at
   **both** call sites, and that `POSTIMPL` carries neither. One mutation per
   negative control, reversed by its exact inverse — never `git checkout`; a
   concurrent session has uncommitted work in this tree.
4. **Rendered-branch disposition contract** (extends
   `tests/test_skill_render_task_workflow.sh`) — the render is what the agent
   actually executes, so the mapping must be asserted **on the generated text**,
   not inferred from the source template. For each of `default`, `fast`, `remote`
   and a **synthetic `confirm` profile** (no committed profile sets `confirm`, so
   this is that branch's only executable coverage — the Test-4b precedent),
   assert on the rendered `parallel-admission.md`:
   - each of `CLEAR` / `CLEAR_CAVEATED` / `CONFLICT` / `UNCHECKABLE` maps to its
     own required disposition text, and no two collapse into one;
   - `CLEAR_CAVEATED` renders **distinctly from `CLEAR`** in both `confirm` and
     `warn`, and **differently between them** (`confirm` = a confirmation prompt,
     `warn` = a visible note) — asserted in both directions, so a template that
     rendered `confirm`'s text under `warn` fails;
   - `CONFLICT` renders a confirmation with **continue listed first** under every
     non-`off` profile, and **no** render in any profile states that the
     procedure stops the workflow on its own — the executable form of finding 7;
   - the **invalid-output clause** (Step 1's table) is present in every
     non-`off` render;
   - `off` (synthetic) **and** `remote` render no invocation, no
     `AskUserQuestion`, and no disposition table — the whole step is absent, not
     merely quiet. This asserts finding 3's headless requirement directly rather
     than inferring it.

   **The same no-automatic-stop assertion runs over
   `.claude/skills/task-workflow/profiles.md`.** It carries no Jinja (verified:
   zero `{%`/`{{`) and is in neither `WRAPPED_FILES_*` list, so **no golden
   covers it** — a contradiction between the knob's documentation and the
   procedure it documents is invisible to the entire existing suite. Assert that
   its `parallel_admission` row names exactly `confirm | warn | off`, states that
   no value stops the workflow, and contains no `block` value, no promotion
   criterion and no threshold-tuning guidance. Negative control: reintroduce the
   old sentence, require the assertion to fail, reverse it exactly.

   Use the Test-4 synthetic-profile harness verbatim (`mktemp` + `$RENDER` +
   `assert_contains` / `assert_not_contains`). Every assertion gets a negative
   control: mutate the source, re-render, require the assertion to fail, and
   reverse the mutation with its exact inverse — never `git checkout`; a
   concurrent session has uncommitted work in this tree.
5. **Marker disposition** — extend
   `tests/test_plan_approved_marker_contract.sh` with the positional assertion
   for `parallel_admission` on the **clearing** side (mirror of the
   `resource_admission` block at `:104-127`), and update the exhaustiveness
   assertion at `:132`.

### Recorded in the Final Implementation Notes

Live CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE rates at implementation
time — calibration evidence for t1343, which owns any future structured-declaration
basis for a hard conflict — plus a note that t1643's grading analysis assumed a
hard/soft split this task no longer has (both verdicts now confirm), so its
~32% / ~67% figures survive as measurements while the conclusion drawn from them
does not — plus the
false-CONFLICT observation above (hard-stop on an invoked tool path while the
genuinely shared files were demoted to hub caveats), which is a grading data
point t1643 explicitly left to this task.

### Follow-ups to spawn

- **documentation** — `website/.../execution-profiles.md` knob table is stale
  independently of this change (see finding 4).
- **No follow-up is spawned for the false CONFLICT.** It is now noise in an
  advisory signal, and the structured-declaration fix belongs to **t1343**, which
  already owns it — a coordination note in both directions, not a new task.

---

## Risk

### Code-health risk: medium

- The checker demonstrably false-CONFLICTs today — it flagged
  `aitask_audit_wrappers.sh`, a path neither task edits, while demoting the five
  files both tasks genuinely edit to `hub` caveats. Residual after finding 7:
  the signal is advisory, so a false positive now costs an extra confirmation
  rather than a forced replan, but enough of them still trains the user to set
  the knob to `off` and the seam becomes dead · severity: medium ·
  → mitigation: the advisory-only design itself (finding 7), plus the calibration
  evidence handed to t1343 · **no code mitigation is spawned — building one was
  the escalation finding 7 rejected**
- Wide blast radius for a wiring change: 3 procedure files, 6 profile YAMLs, 5
  whitelist touchpoints, 36 goldens, 3 website pages, 4 test files.
  `tests/test_skill_render_task_workflow.sh` carries its inventory as hardcoded
  arrays **and its counts as header prose**, so a missed golden degrades
  silently rather than failing · severity: medium · → mitigation: inline pre-phase pin_procedure_and_golden_inventory
- The retraction sweep is wide (15 sites across 3 task files and 1 shipped
  procedure) and is the kind of edit that is easy to do partially. A surviving
  normative `block` or "stop-and-replan" turns the correct implementation into an
  apparent regression for the next reader · severity: medium ·
  → mitigation: Step 7's `grep`-based completeness guard, asserted in
  `tests/test_task_workflow_reentry_drift.sh`
- The fourth `stop_reason` — reached only by an explicit user choice — extends a
  closed vocabulary whose branch/command
  interleaving is asserted **positionally**
  (`test_plan_approved_marker_contract.sh:94-127`). A clause placed on the wrong
  side of `drift_hdr` would stamp or clear the wrong marker with the tests still
  green · severity: medium · → mitigation: inline pre-phase pin_stop_reason_branch_position

### Goal-achievement risk: medium

- The task ships **deviating from its own stated acceptance criterion** (the
  bold "stop-and-replan … does not change"). The deviation is user-directed and
  therefore assented to, but a reader who finds the old AC still standing in the
  task file will conclude the implementation is wrong · severity: medium ·
  → mitigation: finding 7's first deliverable — retract the AC in the task file
  in the same commit, and say why
- t1643's threshold work assumed a hard/soft grading split (`CONFLICT` stops,
  `CLEAR_CAVEATED` confirms) that this task no longer has: both now confirm, so
  the hub threshold decides only prompt wording. The measurement is not wrong,
  but its stated consequence no longer applies here · severity: low ·
  → mitigation: none (record it in the Final Implementation Notes so t1343 does
  not inherit a stale premise)
- `parallel_admission: off` must make the **whole step** a no-op, not just the
  prompt. If the Jinja gate wraps only the `AskUserQuestion` and leaves the
  invocation rendered, the headless `remote` profile shells out to the checker on
  every pick — a silent cost with no consumer · severity: low · → mitigation: none (covered by required test #4)

### Planned mitigations
- timing: pre-phase | name: pin_procedure_and_golden_inventory | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (blast radius / silent golden drift) | desc: assert the render test's file arrays equal the real task-workflow .md inventory and that every listed file has its goldens on disk, replacing the counts held in header prose
- timing: pre-phase | name: pin_stop_reason_branch_position | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 3 (a mis-placed fourth stop_reason clause passing green) | desc: derive the stop_reason list from plan-approved-stop.md's exhaustiveness sentence and assert generically that each reason sits in exactly one branch clause on the correct side of the stamp/clear commands

---

## Final Implementation Notes

### Live verdict rates at implementation time (2026-09-02)

```
$ aitask_parallel_admission.sh replay --candidates auto --from plan \
    --lock-freshness require-fresh
RATES:122|0|0|14|108          # n | CLEAR | CLEAR_CAVEATED | CONFLICT | UNCHECKABLE
CAUSE_RATE:no_plan|122
CAUSE_RATE:stale_claim|122
CAUSE_RATE:hub_overlap_only|10
CAUSE_RATE:no_extractable_paths|9
CAUSE_RATE:all_phantom|5
```

Over 122 live candidates: **0% CLEAR, 0% CLEAR_CAVEATED, 11.5% CONFLICT, 88.5%
UNCHECKABLE.** `no_plan` and `stale_claim` fire on **all 122** — one in-flight
task without a plan poisons every candidate's evidence, exactly the availability
problem t1643 described and left undecided.

**This is the decisive argument for shipping advisory-only.** Under the original
mandatory design, 88.5% of picks would have hit a blocking confirmation and 11.5%
a hard stop — friction on 100% of picks, which is how a guard gets switched off
permanently. These numbers are **calibration evidence for t1343**, which owns the
structured declaration that could make a hard stop defensible. They are **not** a
promotion criterion: there is nothing to promote to.

### Why all three shipped profiles ship `parallel_admission: "off"`

Advisory-only fixes the *consequence* of a bad verdict. It does not fix the
availability that produces one, and at 88.5% UNCHECKABLE an advisory prompt on
nine picks in ten is still the fastest way to teach a user to dismiss the check.
So `default`, `fast` and `remote` each **opt out explicitly**. `warn` remains the
default for an absent key — this is an opt-out by the shipped profiles, not a
change of default, and `tests/test_skill_render_task_workflow.sh` pins both
halves (every shipped profile carries the quoted opt-out; an absent key renders
the same body as an explicit `warn`).

**The root cause, measured and located.** 9 of 16 `Implementing` tasks carry no
plan file (**56%**, 2026-09-02: t1555_2 t1576 t1669 t1675 t1677 t1681 t1685 t1686
t1687). An in-flight claim's file surface is derived from its **plan file only**
— `parallel_admission_collect.py:558-561` falls straight to
`Surface(..., "no_plan")` when `plan_path_for` returns `None`, with **no**
`origin_surface` fallback. The *candidate* has one (`--from auto`,
`:812-818`); the in-flight side does not. One unplanned in-flight task therefore
poisons every candidate's evidence, which is why `CAUSE_RATE:no_plan` is 122 of
122.

**The fix is a task-body / origin fallback on the in-flight side**, giving a
claimed-but-unplanned task a usable surface instead of a blanket `no_plan`. That
is owned by follow-up **t1688**
(`t1688_parallel_admission_prepick_assessment_and_task_body_surface.md`), which
also moves the first safety question before the pick. Forward pointers are in the
parent task t1569 and in t1569_7's `[t1569_4]` checklist. Once t1688 lands,
re-measure with `replay --candidates auto` and flip the shipped profiles to
`warn` if the UNCHECKABLE rate has fallen far enough to be worth a prompt.

### The false CONFLICT, reproduced and understood

`check --candidate 1569_4` returned `CONFLICT` against `t1663_1` on
`.aitask-scripts/aitask_audit_wrappers.sh` — a path **neither task edits**. Both
plans merely *invoke* `apply-helper-whitelist` inside a fenced `bash` block
(`p1663_1:294`). Meanwhile the five files both tasks genuinely edit
(`.claude/settings.local.json`, the three seed mirrors, `.codex/rules/default.rules`)
were demoted to `hub` caveats at 57–65 touches each. The checker hard-stopped on a
tool path and caveated the real collision.

Cause: `plan_paths.extract()` (`lib/plan_paths.py:75`) is a pure regex over the
whole plan body with **no code-fence awareness** (zero occurrences of "fence" in
the module), and it is shared by three consumers — `aitask_remote_drift_check.sh`
via `plan_paths_sh.sh`, `lib/trail_gather.py`, and this checker. Fixing it would
have meant a provenance channel through `extract()` → `Surface.paths` (both bare
strings today) plus a shell/Markdown classifier plus a consumer layer. That was
rejected as disproportionate machinery to preserve one policy choice.

### Deviations from the approved plan

1. **Advisory-only, by explicit user decision.** Retracts the task file's bold
   "CONFLICT's disposition is stop-and-replan in both `block` and `warn` — that
   is the design and it does not change". Swept from 13 sites in the task file,
   1 in the parent, and 1 shipped clause in `resource-admission.md` (Step 7).
2. **Knob values are `confirm | warn | off`, not `block | warn | off`.** Nothing
   blocks, so a `block` value would have been a lie.
3. **`admission_surface_invoked_vs_edited` was withdrawn, not deferred.** It
   existed only to make a mandatory stop safe. The structured-declaration fix
   belongs to **t1343**, which already owns it; bidirectional coordination notes
   were added instead of a new task.
4. **All three shipped profiles ship `"off"`, which the plan did not call for.**
   The approved plan had `default: warn`, `fast: warn`, `remote: off`. The
   measured 88.5% UNCHECKABLE rate made `warn` untenable as a shipped value — see
   the section above. `warn` is still the absent-key default, so this is an
   opt-out by the shipped profiles rather than a change of default, and both
   halves are pinned executably.
5. **The Step-7 completeness grep is a one-time verification, not a committed
   test.** The plan proposed asserting it in
   `tests/test_task_workflow_reentry_drift.sh`, but a task file moves to
   `aitasks/archived/` at completion, so the assertion would fail the moment this
   task lands. The **durable** surfaces are guarded instead: Test 4e asserts that
   no rendered profile of `parallel-admission.md`, and no line of `profiles.md`,
   claims a stop-and-replan default or offers a `block` value. The task-file
   sweep was verified once by grep; all surviving `block` mentions are inside a
   passage explicitly labelled superseded.

### Found during implementation

- **`parallel_admission: off` is a YAML boolean.** YAML 1.1 parses a bare `off`
  as `false`, so the Jinja gate never fired and `remote` rendered the full
  procedure. Fixed on both sides: the shipped profiles quote `"off"`, and the
  gate accepts `false` too, so a user's unquoted value cannot silently mean
  `warn`. Documented in `profiles.md` and the website page.
- **A first draft of the continue-first order assertion was vacuous.** It matched
  the bare label `"Continue anyway"`, whose first occurrence is the intro's quote
  of the drift check's option — so `head -n1` always landed above the option list
  and the comparison held whatever the real order was. Caught by its own negative
  control; the needle is now anchored to the option-list shape
  (`- "Continue anyway" (description:`), and the mutation now fails as it should.
  The `planning.md` ordering guard uses **byte** offsets rather than line numbers
  for the same class of reason: two of the three call sites put the preflight in
  the same line as the drift-check reference, where a line comparison ties.

### Upstream defects identified

None.

(`plan_paths.extract()`'s fence-unawareness is a design limitation of the shared
extractor, not a latent bug — it is documented above and owned by t1688/t1343,
not reported here. The `../../workflows/…` link depths in
`website/.../execution-profiles.md` were checked and resolve clean under
`check_links.py`.)

### Verification

- `aitask_skill_verify.sh` — OK (13 templates × 3 agents, 4 stub surfaces).
- `bash tests/run_all_python_tests.sh --test-dir tests` — `PYTHON SUITE: PASSED`.
- 30 profile-, whitelist- and workflow-dependent bash suites — all pass, incl.
  `test_skill_render_task_workflow.sh` (267), `test_task_workflow_reentry_drift.sh`
  (71, with 4 new negative controls), `test_plan_approved_marker_contract.sh` (37),
  `test_parallel_admission_preflight.sh` (38, new).
- `shellcheck -S warning` clean on all four edited/added test files.
- `hugo build --gc --minify` — exit 0; the new page renders and all four of its
  outbound links resolve to real pages.
