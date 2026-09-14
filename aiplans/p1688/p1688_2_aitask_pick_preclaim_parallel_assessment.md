---
Task: t1688_2_aitask_pick_preclaim_parallel_assessment.md
Parent Task: aitasks/t1688_parallel_admission_prepick_assessment_and_task_body_surface.md
Sibling Tasks: aitasks/t1688/t1688_1_parallel_admission_task_declared_surface.md
Archived Sibling Plans: aiplans/archived/p1688/p1688_*_*.md
Base branch: main
Output branch: main
---

# t1688_2 — opt-in pre-claim parallel assessment in `aitask-pick`; shipped default; docs

Parent plan (design record): `aiplans/p1688_parallel_admission_prepick_assessment_and_task_body_surface.md`.
Sibling t1688_1 (depends): its archived plan
`aiplans/archived/p1688/p1688_1_*.md` holds the measured BEFORE/AFTER `replay`
census this task decides C1 on. This plan is self-contained.

## Context

Before picking a task, users used to ask an agent "given what is in flight, is
it safe to pick t<N>?". Nothing in `aitask-pick` does this today; the checker's
post-plan preflight (`.claude/skills/task-workflow/parallel-admission.md`) runs
one plan later than the question is asked. This task adds an **opt-in**,
agent-judgement assessment **before Step 4 claims the task**, decides the
shipped `parallel_admission` default on measured numbers, and updates the docs.

## PINNED contracts

From t1688_1 (landed before this task — verify they are present, do not
re-decide): `task_declared` provenance and bare `CAVEAT:…|task_declared`; the
checker's `INFLIGHT:` row is
`INFLIGHT:<ref>|<sources>|<liveness>|<n_paths>|<path_state>|<provenance>`;
`check --from plan` for a task **without** a plan resolves the candidate from
its task description.

From the user (PINNED): **`parallel_assessment` is opt-in.** `"off"` in every
shipped profile and seed mirror; a **missing key is off**; when disabled the
templates emit nothing — no checker invocation, no extra reading, no prompt.
`"show"` and `"ask"` are the enabled values. Test disabled and enabled
renderings.

## B0. NEW `.claude/skills/task-workflow/parallel-admission-checker.md` (ungated)

`parallel-admission.md` renders its steps 2-3 away under
`parallel_admission: off` (`:29-33`), and `remote` ships `off`, so the
assessment cannot borrow them. Move steps 2-3 of `parallel-admission.md`
(`:37-88`) **verbatim** into this new file, which carries **no profile
conditionals**:
- the capture form (`if out="$(./.aitask-scripts/aitask_parallel_admission.sh
  check --candidate <task_id> --from plan [--plan "<plan_file>"]
  --lock-freshness require-fresh)"; then rc=0; else rc=$?; fi`; never merge
  stderr), with `--plan` documented as **optional**: the post-plan preflight
  passes it; the pre-claim assessment omits it;
- the three non-preferences (require-fresh mandatory; the checker's
  self-exclusion; read live state at call time);
- the well-formedness table, relabelled as the definition of **"checker
  unusable"** (exit 2 = wiring error; other non-zero / crash; empty stdout or no
  `VERDICT:`; more than one `VERDICT:`; a token outside
  `CLEAR|CLEAR_CAVEATED|CONFLICT|UNCHECKABLE`; an unlisted
  `UNCHECKABLE_CAUSE:` code), and the sentence that this is fail-safe, not
  fail-open.
- One closing paragraph: this file **classifies**; each caller owns the
  disposition.

In `parallel-admission.md`: steps 2-3 become "Run the checker per
`.claude/skills/task-workflow/parallel-admission-checker.md` **with**
`--plan "<plan_file>"`; a "checker unusable" result takes the **UNCHECKABLE**
disposition (below)". Everything else unchanged. The reference lives only in the
enabled branch, so an `off` render still pulls nothing.

## B1. NEW `.claude/skills/task-workflow/parallel-assessment.md`

Jinja: the enabled test is `profile.parallel_assessment is defined and
profile.parallel_assessment in ["show", "ask"]` (strict renderer — never test
an undefined key bare). The disabled branch is one line and interpolates
nothing (so every shipped profile renders byte-identically).

Content of the enabled branch (write it as procedure prose in the style of
`parallel-admission.md`):

- **Inputs:** `task_id`, `task_file`, `active_profile`.
- **1. Skip** if the task's `status` is `Implementing` (resume path: already
  claimed; the post-plan preflight covers it) or its `issue_type` is
  `manual_verification` (writes no code). Display one line with the reason and
  return.
- **2. Run the checker** per `parallel-admission-checker.md`, **without
  `--plan`**. If it classifies the output as checker unusable, keep the reason
  and continue on reading alone.
- **3. Population** = the checker's `INFLIGHT:` rows (ref, liveness, 6th-field
  provenance). `dead` rows are listed as excluded.
- **4. Read** the candidate's description and, for each non-dead row, its task
  description (up to the first `## Inbox` / `## Gate Runs`) and its plan if
  `./.aitask-scripts/aitask_query_files.sh plan-file <id>` returns
  `PLAN_FILE:`. **Read budget:** with more than 12 live rows, read in full only
  rows named in `OVERLAP:` lines or sharing a label / topic anchor with the
  candidate; the rest are skimmed by title and graded `not assessed`.
- **5. Grade** each live row `overlaps` / `adjacent` / `unrelated` /
  `not assessed`. `not assessed` is mandatory where evidence was not read
  (title-only skim, unreadable file) and says which; a title never establishes
  `unrelated`. The other grades name the concrete reason (same file; same
  procedure or template; same seed mirror / golden set; same subsystem; one
  consumes the other's record format).
- **Recommendation:** any `overlaps` → name them. Otherwise it is
  **"incomplete"**, naming each gap, whenever either coverage has one — never
  "no overlap found":
  - reading coverage: any `not assessed` row;
  - deterministic coverage, from the checker's **well-formed** output:
    `VERDICT:UNCHECKABLE` (list each `UNCHECKABLE_CAUSE:` verbatim, e.g.
    `candidate|no_plan`, `locks|<reason>`, `inflight:<ref>|<reason>`), and any
    `INFLIGHT_SOURCE:<gate|lock|status>` whose status is not `ok` → "in-flight
    enumeration incomplete (<source>: <status>)" (tasks missing from the
    `INFLIGHT:` rows cannot be graded at all);
  - separately, "checker unavailable" (B0's classification).
  Never write "safe to run in parallel". Then print the checker's `DISPLAY:`
  verbatim as **"Deterministic view (checker): …"**, or
  `Deterministic view (checker): unavailable — <reason>`.
- **6. Prompt.** `ask`: always. `show`, attended: when any row is `overlaps` or
  the checker was unusable; `not assessed` rows, a well-formed UNCHECKABLE and
  an incomplete enumeration do **not** prompt by themselves — they are named in
  the display and in any question. Headless (`{% if profile.headless is defined
  and profile.headless %}`), either mode: never prompt; display and continue.
  `AskUserQuestion` — findings **inside the question text**; header
  "Parallel"; options in this order: "Pick anyway" (description: "Continue to
  claim this task — the assessment is advisory") / "Pick a different task"
  (description: "Return to task selection; nothing has been claimed") / "Stop"
  (description: "End the workflow; nothing has been claimed").
- **7. Branches.** Nothing is claimed yet, so nothing is reverted. "Pick anyway"
  → return; "Pick a different task" → Step 2a of `aitask-pick` (Step 1 when the
  task came from a Step 0b argument); "Stop" → end the workflow.
- **Notes:** advisory agent judgement, never a guard (t1343's declared manifest
  remains the only basis for a hard stop); two call sites, two evidence
  qualities, one checker; ordering vs. `resource-admission.md` unchanged.

## B2. `.claude/skills/aitask-pick/SKILL.md.j2`

In `### Step 3: Hand Off to Shared Workflow` (`:337-351`), insert **before**
"At this point, a task has been selected and confirmed. Set the following
context variables…":

```jinja
{% if profile.parallel_assessment is defined and profile.parallel_assessment in ["show", "ask"] -%}
**Pre-claim parallel-safety assessment (profile '{{ profile.name }}': `parallel_assessment: {{ profile.parallel_assessment }}`).** Before anything below, execute the **Parallel-Safety Assessment Procedure** (see `.claude/skills/task-workflow/parallel-assessment.md`) with `task_id` and `task_file`. If it returns "Pick a different task", go back to task selection; if "Stop", end the workflow. Otherwise continue below.

{% endif -%}
```

Full path, not a bare filename (a bare one resolves against `aitask-pick/` and
is silently skipped by the closure walker). Every route into Step 3 (0b
macros, 2c, 2d, 2.0) passes through it. Add one Notes bullet (opt-in; off by
default; see `profiles.md`).

## B3. Profile key `parallel_assessment`

- `aitasks/metadata/profiles/{default,fast,remote}.yaml` and
  `seed/profiles/{default,fast,remote}.yaml`: `parallel_assessment: "off"`
  (quoted — bare `off` is YAML boolean false; both are treated as disabled).
  **Commit split:** the `aitasks/metadata/…` files live on the task-data branch
  → `./.aitask-scripts/aitask_task_commit.sh -m "ait: …" <paths>`; the `seed/`
  files are code → the Step 8 code commit.
- `.claude/skills/task-workflow/profiles.md`: a table row after the
  `parallel_admission` row (`:50`): `| parallel_assessment | string | no |
  "off" (the default, also when omitted), "show" or "ask". Opt-in …`, and a
  section after `:69-108` with a `| value | behaviour |` table, the headless
  rule (`ask` must not be set in a headless profile; `show` never prompts
  there), and the opt-in rationale (no default pick-time cost).

## C1. Shipped `parallel_admission` default — decide on the prompt rate

1. Re-run `./.aitask-scripts/aitask_parallel_admission.sh replay --candidates
   auto --from plan --lock-freshness require-fresh`; compare with t1688_1's
   AFTER census.
2. **Prompt-producing rate** = (CONFLICT + UNCHECKABLE) / candidates — `warn`
   asks for both (`parallel-admission.md` step 6), so availability alone is not
   the criterion.
3. **Precision sample:** up to 5 CONFLICT verdicts whose `OVERLAP:` involves a
   `task_declared` surface (either side); read both descriptions and classify
   the shared path as **edit collision** or **context mention**; put the table
   in this plan.
4. Ask the user (`AskUserQuestion`, numbers in the question text). Recommended
   rule (orders the options only): flip `default` + `fast` (+ seed mirrors) to
   `"warn"` when the rate is **≤ 30%** and at most half of the sample are
   context mentions; otherwise keep `"off"`. `remote` stays `"off"`.
5. Record the decision and the numbers here; everything in C2 / Tests follows
   it.

## C2. Docs (current-state only)

- `.claude/skills/task-workflow/parallel-admission.md` Notes: "two call sites,
  two evidence qualities, one checker"; the "regex-extracted from plan prose"
  bullet also covers task descriptions; step-5 `no_plan` remedy → "no plan and
  no path-bearing description — plan it, name its files in the description, or
  release its lock".
- `profiles.md`: `parallel_admission` row (`:50`) and rationale (`:98-107`) per
  C1's outcome.
- `website/content/docs/skills/aitask-pick/parallel-admission.md`: `:16-17`
  ("once"), `:24-26` ("plan's prose"), `:78-91` ("Why all three ship off", per
  C1), `:100` remedy row; add a `task_declared` CLEAR_CAVEATED example and a
  short "Pre-claim assessment (opt-in)" section.
- `website/content/docs/skills/aitask-pick/execution-profiles.md` `:44` + a new
  `parallel_assessment` row; `website/content/docs/skills/aitask-pick/_index.md`
  `:32`, `:58-64`; `website/content/docs/workflows/parallel-development.md`
  `:44-46`; `website/content/docs/skills/aitask-backlog-roadmap.md` `:30-31`.
- `aidocs/framework/background_work_roadmap.md` (`:341-343` and nearby): before
  t1688 the parallel-safe lane was empty by construction; `CLEAR_CAVEATED`
  (incl. `task_declared`) lands in the core lane at medium/low confidence
  (`roadmap_policy.py:91-92`, `:432-433`).
- `cd website && python3 check_links.py --build`.

## C3. Step 8e notes (`./ait note`, advisory — re-check each target is active first)

- t1569 (status section `:311-335`) and t1569_7 (`:27`, `:44-47`): C1's
  outcome; the CLEAR_CAVEATED rendering item gains the `task_declared` caveat.
- t1343 (`:399-401`): `task_declared` is a description heuristic, not a
  declaration; hard stops remain t1343's.
- t1470: cross-reference (consumer of the same verdicts).

## Tests

- `tests/test_skill_render_aitask_pick.sh`, new Test 7 (scratch YAMLs in
  `mktemp -d`: `fast.yaml` with the key removed; set `"show"`; set `"ask"`;
  `remote.yaml` set `"show"`), rendered with
  `"$PYTHON" .aitask-scripts/lib/skill_template.py .claude/skills/aitask-pick/SKILL.md.j2 <profile.yaml> claude`:
  - disabled (`default`, `fast`, `remote`, key-absent): no
    `parallel-assessment.md`, no `aitask_parallel_admission.sh` in the output;
  - enabled (`show`, `ask`): the line naming
    `task-workflow/parallel-assessment.md` comes **before** the "read and
    follow" hand-off line (line-order pattern:
    `tests/test_inbox_surfacing_render.sh:126-138`);
  - procedure renders: `show` → B0 reference without `--plan`, prompt
    conditional on `overlaps` or checker unusable; `ask` → unconditional;
    headless `show` → no `AskUserQuestion`; all: `not assessed`, the
    "incomplete" rule with the well-formed-UNCHECKABLE / `INFLIGHT_SOURCE` clause
    **separate** from the "checker unavailable" clause, and the `Implementing`
    skip;
  - **closure level:** walk the rendered closure from `aitask-pick/SKILL.md.j2`
    the way `aitask_skill_verify.sh:135-142` does, for a scratch profile with
    `parallel_assessment: "show"` + `parallel_admission: "off"` (and its
    headless variant): the closure contains `parallel-admission-checker.md`
    with the capture form, `--lock-freshness require-fresh` and the
    checker-unusable table, and the assessment's reference resolves to it.
    Control: both off → neither file in the closure.
- `tests/test_skill_render_task_workflow.sh`: add `parallel-assessment.md` to
  `WRAPPED_FILES_INVARIANT` (`:94-116`) with golden
  `tests/golden/procs/task-workflow/parallel-assessment-default.md`; add
  `parallel-admission-checker.md` wherever Test 0 (`:148-200`) requires;
  `parallel_admission` pins (`:632-644`), the `off` loop (`:602-612`) and
  `parallel-admission-*` goldens per **C1's outcome**; synthetic `warn` and
  synthetic `off` renders asserted regardless; `parallel_assessment: "off"`
  pinned in all three profiles and all three seed mirrors; update the comment
  at `:80-92`.
- `tests/test_parallel_admission_preflight.sh`: pins on the moved invocation /
  well-formedness text follow them into `parallel-admission-checker.md`.
- Goldens (same commit):

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py .claude/skills/aitask-pick/SKILL.md.j2 \
    aitasks/metadata/profiles/$p.yaml claude > tests/golden/skills/aitask-pick/SKILL-$p-claude.md
  for f in parallel-admission SKILL planning; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py .claude/skills/task-workflow/$f.md \
      aitasks/metadata/profiles/$p.yaml claude > tests/golden/procs/task-workflow/$f-$p.md
  done
done
"$PYTHON" .aitask-scripts/lib/skill_template.py .claude/skills/task-workflow/parallel-assessment.md \
  aitasks/metadata/profiles/default.yaml claude > tests/golden/procs/task-workflow/parallel-assessment-default.md
./.aitask-scripts/aitask_skill_rerender.sh remote   # commit the new committed-closure files it produces
```

## Verification

```bash
bash tests/test_skill_render_aitask_pick.sh
bash tests/test_skill_render_task_workflow.sh
bash tests/test_parallel_admission_preflight.sh
bash tests/test_skill_render_aitask_pickrem.sh
bash tests/test_skill_render_aitask_pickweb.sh
./.aitask-scripts/aitask_skill_verify.sh
set -o pipefail; bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
cd website && python3 check_links.py --build
```

Live: `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast`
shows no assessment; rendering against a scratch profile with
`parallel_assessment: "show"` shows it before the Step 3 hand-off.

## Risk

### Code-health risk: medium
- B0 moves the preflight's steps 2-3 into a shared file, changing the rendered
  preflight for every profile that enables it · severity: low · → mitigation:
  covered in-plan — moved verbatim; goldens and preflight pins follow
- Two new files can enter the committed `task-workflow-remote-` closure; three
  golden families move · severity: low · → mitigation: covered in-plan —
  `aitask_skill_verify.sh` walk-verify; re-render and goldens in the same commit
- A `warn` flip prompts on every pick still CONFLICT or UNCHECKABLE · severity:
  medium · → mitigation: covered in-plan — C1's prompt-rate + precision-sample
  decision, made by the user

### Goal-achievement risk: low
- The assessment is agent judgement with a reading cost · severity: low ·
  → mitigation: covered in-plan — opt-in and omitted when disabled; the read
  budget; "incomplete" instead of a false all-clear

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no merge. Archive with
`./.aitask-scripts/aitask_archive.sh 1688_2`; the parent t1688 archives with it.
