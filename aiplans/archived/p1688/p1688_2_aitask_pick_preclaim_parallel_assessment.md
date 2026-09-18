---
Task: t1688_2_aitask_pick_preclaim_parallel_assessment.md
Parent Task: aitasks/t1688_parallel_admission_prepick_assessment_and_task_body_surface.md
Sibling Tasks: aitasks/t1688/t1688_1_parallel_admission_task_declared_surface.md
Archived Sibling Plans: aiplans/archived/p1688/p1688_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-17 15:21
---

### Pre-phase (risk mitigations)

1. [snapshot_preflight_move] Before any B0 edit, render
   `.claude/skills/task-workflow/parallel-admission.md` with
   `.aitask-scripts/lib/skill_template.py` against synthetic `warn` and
   `confirm` profiles (same shape as Test 4e's `test_pa_warn` / `test_pa_confirm`)
   into the scratchpad, and save a copy of source lines `:37-88`. After B0:
   (a) `diff` the saved steps 2-3 text against the corresponding block of
   `parallel-admission-checker.md` — the only allowed differences are the
   `--plan` optionality wording, the "checker unusable" relabel and the closing
   "this file classifies" paragraph; (b) `diff` the old vs new `warn`/`confirm`
   renders — the only allowed hunk is steps 2-3 collapsing into the reference
   line. Any other hunk is a regression to fix before continuing.

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

## Verification pass (2026-09-17, re-checked against HEAD `a3e08bd1b`)

The approach holds. Deltas against the original text (applied below):

- **t1688_1 landed** (`8bb86c85c`). Present in the tree: `OVERLAP_CLASSES =
  ("specific", "hub", "declared")`, `ADVISORY_OVERLAP_CAVEATS`
  (`task_declared_overlap`, `hub_overlap_only`, `stale_claim_overlap`),
  `INFLIGHT_SOURCE:<name>|<status>|<age>|<reason>` emitted once per source with
  `SOURCE_STATUSES = ok|degraded|unavailable|not_consulted`
  (`parallel_admission.py:433-437`; `not_consulted` is treated as unavailable,
  `:271`), and `DISPLAY:` (`:471`).
- **PINNED 6 (from t1688_1): a `task_declared` overlap never grades CONFLICT**
  — it renders `OVERLAP:<ref>|declared|…` + `CAVEAT:inflight:<ref>|task_declared_overlap:<path>`
  → CLEAR_CAVEATED. Consequences here: C1's original sample of "CONFLICTs
  involving `task_declared`" is empty by construction; description-only overlaps no longer
  count toward the prompt rate (C1 therefore samples the CONFLICT
  counterparties that do prompt, via `pa.conflict_refs`, for the default
  decision, and the caveats only for the t1343 note); B1 reads `declared` rows
  as advisory evidence;
  counterparties of a CONFLICT are only `pa.conflict_refs` (class `specific`,
  no `stale_claim` caveat).
- **User decision (2026-09-17): PINNED 6 stays in this task.** t1814/t1824
  measured description precision ≥ plan precision (0.446/0.456 creation-time vs
  0.407 plan at threshold 10), which undercuts PINNED 6's premise; lifting it is
  handed off to t1343 by an advisory note at Step 8e (C3), not done here.
- **The CONFLICT row in `parallel-admission.md` (`:97`) was already corrected
  by t1688_1** — C2 keeps it verbatim.
- Anchors re-read and current: `parallel-admission.md` steps 2-3 `:37-88`, `off`
  gate `:29-33`; `aitask-pick/SKILL.md.j2` Step 3 `:337-351`, Notes `:355`;
  `profiles.md` row `:50`, section from `:71`; all six profile YAMLs carry
  `parallel_admission: "off"`; `remote.yaml` has `headless: true`.
- **Shifted test anchors** in `tests/test_skill_render_task_workflow.sh`:
  wrapped-file comment `:79-92`, `WRAPPED_FILES_INVARIANT` `:94-120`, Test 4e
  `:503-680` (synthetic warn/absent/confirm/off profiles `:527-544`, `off`
  pins `~:620-631`, shipped `"off"` pins `:655-667`, profiles.md pin `:676`).
  `tests/test_skill_render_aitask_pick.sh` ends at Test 6 (`:171`), so the new
  test is Test 7.

- **Review revision (2026-09-17, both confirmed against the plan text):**
  (1) the caveat-only sample checked rows that never prompt under `warn`, so
  C1 now samples the CONFLICT counterparties that do prompt
  (`pa.conflict_refs`) and gates the recommendation on it; (2) B1 promises no
  prompt in headless under **either** mode, but only headless `show` was
  tested, so Test 7 adds headless `ask` with non-vacuous controls.

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
  rule (in a headless profile neither `show` nor `ask` ever prompts — the
  procedure displays and continues; `ask` there is accepted but behaves like
  `show`), and the opt-in rationale (no default pick-time cost).

## C1. Shipped `parallel_admission` default — decide on the prompt rate

1. Re-run `./.aitask-scripts/aitask_parallel_admission.sh replay --candidates
   auto --from plan --lock-freshness require-fresh`; compare with t1688_1's
   AFTER census.
2. **Prompt-producing rate** = (CONFLICT + UNCHECKABLE) / candidates — `warn`
   asks for both (`parallel-admission.md` step 6), so availability alone is not
   the criterion.
3. **CONFLICT prompt-quality sample (the prompts users will actually get):**
   from the replay output, take up to 5 CONFLICT candidates and name each one's
   counterparties **only** through `pa.conflict_refs(lines)` /
   `pa.conflict_overlaps(lines)` (`.aitask-scripts/lib/parallel_admission.py:702`,
   `:732` — class `specific`, no `stale_claim` caveat; never by re-parsing
   `OVERLAP:` rows by hand). For each (candidate, counterparty, shared path) read
   both tasks' plans/descriptions and classify it **edit collision** (both
   intend to change that file) or **context mention** (one only cites, runs or
   references it). Put the table in this plan. If there are fewer than 5
   CONFLICTs, sample all of them and say so; if there are none, record that the
   quality check is vacuous and the rate is the only evidence.
4. **Secondary sample (for the t1343 hand-off only):** up to 5 candidates whose
   CLEAR_CAVEATED carries `CAVEAT:inflight:<ref>|task_declared_overlap:<path>`,
   classified the same way. Under PINNED 6 these never prompt under `warn`, so
   this sample does **not** feed the default decision — it goes into the C3
   note to t1343.
5. Ask the user (`AskUserQuestion`, rate, CONFLICT/UNCHECKABLE split and the
   CONFLICT sample's edit-collision / context-mention counts in the question
   text). Recommended rule (orders the options only): flip `default` + `fast`
   (+ seed mirrors) to `"warn"` when the rate is **≤ 30%** **and** at most half
   of the CONFLICT sample are context mentions; otherwise keep `"off"`.
   `remote` stays `"off"`. (t1688_1's AFTER census was 26/129 = 20.2%, all 12
   CONFLICTs plan-derived — moment-relative, re-measure.)
6. Record the decision and the numbers here; everything in C2 / Tests follows
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
  declaration; hard stops remain t1343's. Also carry the PINNED 6 hand-off:
  t1814 (`aiplans/archived/p1814_*`) and t1824 measured description precision
  ≥ plan precision, so whether a `declared` overlap may grade CONFLICT
  (parity) is t1343's decision, not made by t1688_2; include C1's
  `task_declared_overlap` precision sample.
- t1470: cross-reference (consumer of the same verdicts).

## Tests

- `tests/test_skill_render_aitask_pick.sh`, new Test 7 (scratch YAMLs in
  `mktemp -d`: `fast.yaml` with the key removed; set `"show"`; set `"ask"`;
  `remote.yaml` (headless) set `"show"`; `remote.yaml` (headless) set
  `"ask"`), rendered with
  `"$PYTHON" .aitask-scripts/lib/skill_template.py .claude/skills/aitask-pick/SKILL.md.j2 <profile.yaml> claude`:
  - disabled (`default`, `fast`, `remote`, key-absent): no
    `parallel-assessment.md`, no `aitask_parallel_admission.sh` in the output;
  - enabled (`show`, `ask`): the line naming
    `task-workflow/parallel-assessment.md` comes **before** the "read and
    follow" hand-off line (line-order pattern:
    `tests/test_inbox_surfacing_render.sh:126-138`);
  - procedure renders: `show` → B0 reference without `--plan`, prompt
    conditional on `overlaps` or checker unusable; `ask` → unconditional;
    headless `show` **and headless `ask`** → no `AskUserQuestion` in the
    rendered procedure (both modes; a regression in the `ask` branch must not
    leave a headless pick waiting for input), each paired with a non-headless
    control of the same mode that **does** contain it, so the assertion cannot
    pass vacuously; all: `not assessed`, the
    "incomplete" rule with the well-formed-UNCHECKABLE / `INFLIGHT_SOURCE` clause
    **separate** from the "checker unavailable" clause, and the `Implementing`
    skip;
  - **closure level:** walk the rendered closure from `aitask-pick/SKILL.md.j2`
    the way `aitask_skill_verify.sh:135-142` does, for a scratch profile with
    `parallel_assessment: "show"` + `parallel_admission: "off"` (and its
    headless `show` and headless `ask` variants — neither closure contains
    `AskUserQuestion` inside `parallel-assessment.md`): the closure contains `parallel-admission-checker.md`
    with the capture form, `--lock-freshness require-fresh` and the
    checker-unusable table, and the assessment's reference resolves to it.
    Control: both off → neither file in the closure.
- `tests/test_skill_render_task_workflow.sh`: add `parallel-assessment.md` to
  `WRAPPED_FILES_INVARIANT` (`:94-120`) with golden
  `tests/golden/procs/task-workflow/parallel-assessment-default.md`; add
  `parallel-admission-checker.md` wherever Test 0 requires (it lists only Jinja-bearing files, so the Jinja-free checker file needs no array entry — only a pin that it stays Jinja-free);
  `parallel_admission` pins (`:655-667`), the `off` loop (`~:624-636`) and
  `parallel-admission-*` goldens per **C1's outcome**; synthetic `warn` and
  synthetic `off` renders asserted regardless; `parallel_assessment: "off"`
  pinned in all three profiles and all three seed mirrors; update the comment
  at `:79-92`.
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
  preflight for every profile that enables it · severity: low (residual —
  addressed by inline pre-phase snapshot_preflight_move) · → mitigation:
  inline pre-phase snapshot_preflight_move
- Two new files can enter the committed `task-workflow-remote-` closure; three
  golden families move · severity: low · → mitigation: covered in-plan —
  `aitask_skill_verify.sh` walk-verify; re-render and goldens in the same commit
- A `warn` flip prompts on every pick still CONFLICT or UNCHECKABLE · severity:
  medium · → mitigation: covered in-plan — C1's prompt rate plus a
  `pa.conflict_refs` sample of the CONFLICT prompts themselves (edit collision
  vs context mention), decision made by the user
- C1's census is moment-relative (the in-flight corpus moves daily); a
  decision on stale numbers ships the wrong default · severity: low ·
  → mitigation: covered in-plan — re-run `replay` at implementation time and
  record the raw rates beside the decision

### Planned mitigations
- timing: pre-phase | name: snapshot_preflight_move | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: B0 move rewrites enabled preflight renders | desc: render-diff proof that the B0 move is verbatim and changes only steps 2-3 of the warn/confirm preflight renders

### Goal-achievement risk: low
- The assessment is agent judgement with a reading cost · severity: low ·
  → mitigation: covered in-plan — opt-in and omitted when disabled; the read
  budget; "incomplete" instead of a false all-clear

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no merge. Archive with
`./.aitask-scripts/aitask_archive.sh 1688_2`; the parent t1688 archives with it.

## C1 — recorded outcome (decided 2026-09-17)

**Decision: all three shipped profiles keep `parallel_admission: "off"`.** The
recommended rule failed on both of its counts.

Census, `replay --candidates auto --from plan --lock-freshness require-fresh`,
131 candidates:

| verdict | count |
|---|---|
| `CLEAR` | 0 |
| `CLEAR_CAVEATED` | 86 |
| `CONFLICT` | 31 |
| `UNCHECKABLE` | 14 |

Prompt-producing rate (CONFLICT + UNCHECKABLE) = **45/131 = 34.4%**, above the
≤30% bar (t1688_1's AFTER census was 26/129 = 20.2%; CONFLICTs rose 12 → 31).
`CAUSE_RATE:` lines: `all_phantom` 5, `no_extractable_paths` 9 (the two
remaining UNCHECKABLE causes), `hub_overlap_only` 50, `stale_claim_overlap` 11,
`task_declared_overlap` 8, plus the per-claim `cross_host_lock` 131,
`no_liveness_token` 130, `stale_claim` 131, `task_declared` 131.

**CONFLICT prompt-quality sample** — 6 CONFLICT candidates, counterparties named
only through `pa.conflict_overlaps` (class `specific`, no `stale_claim` caveat):

| candidate | counterparty | shared path | classification |
|---|---|---|---|
| 1647_4 | 1823_3 | `aitasks/metadata/codeagent_config.json` | **edit collision** — both add a `defaults.<op>` key |
| 1149 | 1794_5 | `tests/test_shortcut_scopes.py` | context mention — both only *run* it |
| 1231 | 1823_3 | `tests/test_website_doc_lists.sh` | context mention — 1231 extends it, 1823_3 only cites it as the parser of a line it edits |
| 1794_6 | 1794_5 | `tests/test_shortcuts_registry_coverage.sh` | context mention — 1794_5 only runs it |
| 1823_4 | 1794_5 | `tests/test_no_raw_tmux.sh` | context mention — both only run it |
| 835 | 1688_2 | `.aitask-scripts/aitask_skill_rerender.sh` | context mention — this task only *runs* the rerenderer; 835 edits it |

**1 of 6 is a real edit collision.** More than half the sample are context
mentions, so the second half of the rule fails too — independently of the rate.

**Secondary sample (for the t1343 hand-off) could not be taken.** The replay
recorded 8 `task_declared_overlap` caveats, but re-running `check` over ~80
CLEAR_CAVEATED candidates ~30 minutes later produced **zero** — the tasks that
had been claimed-but-unplanned at census time had since been planned or landed.
That is itself the finding worth handing to t1343: a description-derived overlap
is not just weak evidence, it is *short-lived* evidence, and any precision claim
about it is a statement about a corpus snapshot rather than about the mechanism.
t1814 / t1824's frozen-corpus method is the right one for that question.

## Final Implementation Notes

- **Actual work done:** B0 (new ungated `parallel-admission-checker.md`;
  `parallel-admission.md` steps 2-3 now reference it), B1 (new
  `parallel-assessment.md`, opt-in), B2 (`aitask-pick/SKILL.md.j2` Step 3 hook +
  Notes bullet), B3 (`parallel_assessment: "off"` in all 3 profiles and all 3
  seed mirrors; `profiles.md` row + new section), C1 (measured, decided: keep
  `off`), C2 (docs), and the tests/goldens. All planned deliverables landed;
  nothing was deferred.
- **Deviations from plan:**
  - *The `off` rationale was rewritten rather than merely re-pointed.* The user
    asked mid-implementation for the current-state reason to be documented, so
    `profiles.md`, the website page, the six profile YAML comments and
    `aidocs/framework/background_work_roadmap.md` now carry the 2026-09-17
    numbers and the prompt-quality sample instead of the stale 2026-09-02
    "56% carry no plan" story, which t1688_1 had already fixed.
  - *The B0 move is verbatim in substance, not byte-for-byte.* Beyond the three
    allowed differences (the `--plan` optionality paragraph, the
    "checker unusable" relabel, the closing "this file classifies" paragraph),
    six phrases were generalized away from the preflight as sole caller:
    "parsed below" → "a caller parses"; "mandatory here" → "mandatory"; "long
    before the plan existed" → "By the preflight's call site"; "this is the one
    call site" → "these are the call sites"; "the table in step 5" → "the
    caller's remedy table". Each is a pointer, not a rule. Every rule the
    t1569_4 pins name is intact and now asserted on the new file
    (`tests/test_parallel_admission_preflight.sh`).
  - *The pick Notes bullet does not link the procedure file.* It names
    `profiles.md` instead. A path reference in that always-rendered list would
    be the only thing a disabled profile could follow at the point of use.
  - *The planned closure control "both off → neither file in the closure" was
    NOT implemented, because it is false.* `profiles.md` documents every knob
    and names `parallel-assessment.md` in prose, and the closure walker follows
    a bare filename within the same directory — so both files are in every
    profile's closure already, via the docs, not via the hook. Test 7 asserts
    what is actually true and load-bearing: the **rendered pick body** for a
    disabled profile references neither the procedure nor the checker, the
    disabled procedure body is a no-op that interpolates nothing, and (after
    review, see Change Request 1) every enabled/headless variant's in-process
    closure plan contains both files with rewritten references.
  - *One line in `parallel-admission-checker.md` was re-wrapped* so the moved
    sentence "token is one of `CLEAR`, `CLEAR_CAVEATED`," stays on one line —
    the preflight test pins that substring, and reflowing the prose was
    preferable to weakening the pin.
- **Issues encountered:**
  - The disabled branch of `parallel-assessment.md` originally interpolated
    `{{ profile.name }}`, which would have made the three renders differ and
    broken its `WRAPPED_FILES_INVARIANT` membership. The branch now interpolates
    nothing. (`WRAPPED_FILES_VARYING` with three goldens was the alternative;
    invariance is stronger, and the file only varies on keys no shipped profile
    sets.)
  - Two Test 7 assertions matched across a line wrap and were rewritten against
    single-line substrings.
  - `./.aitask-scripts/aitask_skill_rerender.sh remote` was run twice: once
    after B0/B1, and again after the Notes-bullet correction changed the pick
    body.
- **Key decisions:**
  - **PINNED 6 stays.** t1814 and t1824 measured description precision at or
    above plan precision, which undercuts its premise, but by explicit user
    decision this task does not lift it: the contract change is t1343's, and it
    gets the numbers as an advisory note at Step 8e.
  - **The checker contract is a separate file rather than a Jinja-neutral block
    inside the preflight**, because the assessment must read it under a profile
    whose own `parallel_admission` is `off` — which is every shipped profile.
    `tests/test_skill_render_task_workflow.sh` pins that it stays Jinja-free.
  - **Headless is a hard "never prompt" in both modes**, not just `show`. `ask`
    is accepted in a headless profile and behaves like `show`; the test matrix
    asserts it for both, each paired with an attended control that *does* prompt
    so the assertion cannot pass vacuously.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - The C1 numbers are a **snapshot**, and a fast-moving one: the
    `task_declared_overlap` population went from 8 to 0 in about half an hour as
    claimed tasks got planned. Any future decision about the shipped default
    should re-measure, and any precision claim about description-derived
    evidence needs a frozen corpus (t1814's method), not a live one.
  - `pa.conflict_refs` / `pa.conflict_overlaps` are the only sanctioned way to
    name a CONFLICT's counterparties; the sample above used them, and
    `tests/test_skill_render_task_workflow.sh` pins that the procedure prose and
    the library agree on the two conditions (class `specific`, no `stale_claim`).
  - When adding a procedure file that references another by bare filename, note
    that the closure walker resolves it within the same directory — so a mention
    in `profiles.md` is enough to pull a file into every profile's closure, and
    a "not in the closure" assertion about an opt-in procedure will not hold.

## Post-Review Changes

### Change Request 1 (2026-09-18)
- **Requested by user:** five review findings, all verified before changing
  anything:
  1. *Cause validation* — the checker contract classified an `UNCHECKABLE_CAUSE`
     as "checker unusable" when its code was missing from **the caller's remedy
     table**. The assessment has no such table, and the preflight's is rendered
     away under `off`, so an ordinary `no_plan` / `all_phantom` would read as a
     checker failure (and force a `show` prompt). Confirmed: that row was a
     semantic change introduced by the B0 relabel — the original said "still
     UNCHECKABLE".
  2. *Independent-toggle coverage* — Test 7's enabled scratch profiles omitted
     `parallel_admission`, so they ran the default `warn` branch; and the closure
     check relied on `walk-check`'s exit status, which cannot fail on a
     mistyped reference because `discover_refs` skips nonexistent targets.
     Confirmed.
  3. *Evidence-source semantics* — the contract and the assessment claimed that
     omitting `--plan` selects `task_declared`. `resolve_candidate_surface` uses
     `plan_path or plan_path_for(...)` first, so a `Ready` task that already
     carries a plan resolves `plan_declared`. Confirmed in code
     (`parallel_admission_collect.py:886-891`). C2's `parallel-admission.md`
     Notes / `no_plan` remedy updates had also been missed.
  4. *Overlap explanation* — the website read a `task_declared_overlap` caveat as
     "nothing collides". Confirmed: the caveat reports a shared path.
  5. *Current-state docs* — the website page narrated the original availability
     rationale and its fix. Confirmed against
     `aidocs/framework/documentation_conventions.md`.
- **Changes made:**
  1. `parallel-admission-checker.md`: the unknown-cause row now keys on the
     checker's vocabulary (`UNCHECKABLE_REASONS`), with a paragraph stating the
     parse rule (split on the first `|`, code up to the first `:`) and that a
     declared code without a caller remedy row stays a well-formed
     `UNCHECKABLE`. `parallel-assessment.md` step 2 says the same.
     `tests/test_parallel_admission_preflight.sh` section 4 applies that rule to
     a real checker `no_plan` cause, `all_phantom`, and an undeclared
     `bogus_future_code`, and pins the contract text (63/63).
  2. Test 7: all four enabled scratch profiles set `parallel_admission: "off"`
     explicitly; the closure check now runs `walk_closure(write=False)`
     in-process and asserts closure membership of both files, the **rewritten**
     `task-workflow-<profile>-/…` references in the rendered pick and
     assessment, that the off preflight's Procedure section does not reference
     the checker, the checker's rendered content, and prompt presence/absence
     for attended/headless. A typo mutant of the assessment's checker path fails
     4 assertions (verified, then restored).
  3. Contract + assessment now describe plan discovery → description fallback
     and tell the reader to take the provenance from the `CANDIDATE:` line; the
     assessment reads the candidate's plan when one exists.
     `parallel-admission.md` Notes gain "two call sites, two evidence
     qualities, one checker" and the plan/description evidence wording, and the
     `no_plan` remedy row names the path-bearing-description remedy.
  4. Website example rewritten: an overlap **was** found in description-derived
     evidence; it is advisory, not an all-clear, and should be checked.
  5. Website "why off" keeps only the current dated measurements and reasons;
     the same current-state trim applied to `profiles.md` and the six profile
     YAML comments. The historical comparison stays in this plan (C1 section).
- **Files affected:** `.claude/skills/task-workflow/{parallel-admission-checker,parallel-assessment,parallel-admission,profiles}.md`,
  `website/content/docs/skills/aitask-pick/parallel-admission.md`,
  `aitasks/metadata/profiles/*.yaml`, `seed/profiles/*.yaml`,
  `tests/test_skill_render_aitask_pick.sh`, `tests/test_skill_render_task_workflow.sh`,
  `tests/test_parallel_admission_preflight.sh`, goldens
  (`parallel-admission-{default,fast,remote}.md` now change because the Notes
  render under `off`; `aitask-pick` ×3), and the re-rendered remote prerenders.
- **Verification:** pick 209/209, task-workflow 337/337, preflight 63/63,
  pickrem 67/67, pickweb 86/86, `aitask_skill_verify.sh` OK,
  `check_links.py` 0 broken. The Python suite reported `FAILED` once and
  `PASSED` on the immediate rerun; the failing test was not captured (the first
  run's output was piped through `tail`). No Python file is touched by this
  task and two other sessions were running suites concurrently, but the failure
  is **unattributed**, not explained.
