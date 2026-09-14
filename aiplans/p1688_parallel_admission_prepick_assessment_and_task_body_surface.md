---
Task: t1688_parallel_admission_prepick_assessment_and_task_body_surface.md
Base branch: main
Output branch: main
---

# t1688 — task-description surface for parallel admission + pre-claim assessment

## Context

The t1569_4 preflight is advisory and, as shipped, unusable: `decide()` refuses
CLEAR whenever any *blocking* in-flight claim has an invisible surface, and the
collector builds `Surface(ref, "plan_declared", (), "no_plan")` for every
in-flight task without a plan (`parallel_admission_collect.py:568-570`). Tasks
sit `Implementing` from Step 4 but only get a plan at the end of Step 6, so for
the whole claim→plan window they poison every candidate's verdict (measured:
88.5% UNCHECKABLE, `no_plan` on all 122). Task descriptions exist from creation
and name files. This task (A) adds a deterministic **task-description fallback
surface** (`task_declared`) to the one checker both consumers share, and (B) adds
an **opt-in, agent-judgement pre-claim assessment** (off in every shipped profile;
a missing key is off) to `aitask-pick`, where the "is it
safe to pick t<N>?" question is actually asked — before Step 4 claims the task.

## Part A — checker: `task_declared` fallback surface

**Invariant (the whole contract in one line):** the fallback can only turn an
in-flight/candidate `no_plan` into a *resolved* `task_declared` surface. It never
introduces a new cause and never merges with a plan surface. A description that
is unreadable, yields no tokens, or yields only phantom/malformed tokens —
**judged against the union of the code and task-data corpora**, at whichever
point both are known (A2 for the collector, the adapter in A5 for the gatherer
path) — leaves
the surface **exactly `no_plan`**. This keeps the remedy table in
`parallel-admission.md` step 5 truthful ("`no_tokens` → that *plan* declares no
usable surface" would be wrong for a description), keeps `no_plan_claims()` and
`replay --exclude-no-plan` meaning what they say, and makes the precedence
plan → description → `no_plan` a single testable property.

### Pre-phase (risk mitigations)
Belongs to **t1688_1**, before any code under A1-A5 changes.
1. [pin_no_plan_controls] Add characterization tests pinning today's `no_plan`
   output on **both** paths, and confirm they pass on the unmodified code:
   collector — `collect()` in-flight claim and `resolve_candidate_surface()`
   candidate, in `tests/test_parallel_admission_collect.py`; gatherer path —
   asserted on the **surface the adapter builds** from the gatherer's lines
   (`surfaces_from_inflight_records` over `INFLIGHT_PATH:` with `data_tracked`,
   `data_dirs` and the injected `plan_paths.classify`),
   in `tests/test_trail_gather.py`, because after A the gatherer defers the
   phantom judgement to the adapter (A5) and its raw lines legitimately change.
   Cases, each with no plan file: (a) no task file; (b) a body with no path
   token; (c) a body naming only paths that resolve in **neither** corpus — not
   tracked, and not under a tracked directory, on the code or the
   task-data branch; (d) a body whose only real paths sit under `## Inbox` and
   under `## Gate Runs`. All four must stay `no_plan` after A lands — that is
   the "the fallback never introduces a new cause" invariant proven against a
   baseline rather than asserted afterwards. (Case (d) passes trivially today;
   it becomes the guard on the section cut.)

### A1. `.aitask-scripts/lib/plan_paths.py` — the shared body cut
- Add `cut_task_framework_sections(body)`: truncate at the first line that is
  exactly one of the framework-appended headers — `## Inbox` and `## Gate Runs`.
  Import the literals lazily inside the function from
  `note_inbox.SECTION_HEADER` and `gate_ledger.SECTION_HEADER` (no restated
  string; lazy so the shell bridge `plan_paths_sh.sh` load path is unchanged).
  **Cut at whichever comes first**: `aitask_note.sh:94-100` inserts `## Inbox`
  *before* `## Gate Runs`, so "Gate Runs and below" alone would leave other
  agents' note prose (arbitrary paths from other tasks) in the surface. Note
  bodies cannot fake the headers — `note_render_body` prefixes every body line
  with `> | ` (`aitask_note.sh:384-400`).
- Add `task_body_text(raw)`: strip a leading `---` frontmatter block (same shape
  as `parallel_admission_collect.strip_frontmatter`), then
  `cut_task_framework_sections`. Used by the gatherer, which has the raw text in
  `TaskRow.text` already.
- No grammar change: both reuse `extract()`; the seam guard
  (`tests/test_plan_paths_seam.sh:46-69`, "no second copy of the grammar") holds.

### A2. `.aitask-scripts/lib/parallel_admission_collect.py`
- `task_surface(ref, task_path, tracked, dirs)`: run the ONE extractor —
  `plan_extraction(ref, task_path, tracked, dirs,
  body_transform=plan_paths.cut_task_framework_sections)` (frontmatter is
  stripped by `strip_frontmatter` first, exactly as for plans). Return
  `Surface(ref, "task_declared", ext.paths, "resolved", "n/a")` iff
  `ext.resolution == "resolved"`, else `None`.
- `_task_surface(...)`: memoised twin of `_plan_surface` (same `surface_cache`,
  key `(ref, task_path)`), so a task that is both candidate and claim in one
  `replay` is read once.
- `_no_plan_fallback(root, ref, tracked, dirs, cache)`: `task_file_for(root, ref)`
  → `_task_surface` → the surface, or `Surface(ref, "plan_declared", (),
  "no_plan", "n/a")` when there is no task file or no resolved description.
- Use it at both no-plan sites: `collect()` (in-flight, line ~568) and
  `resolve_candidate_surface()` (candidate, line ~816). On `--from auto` the
  existing origin fallback still runs only when the surface is unresolved after
  plan → description (the description is the task's own words; origin is a
  proxy).
- `no_plan_claims()` needs no change — a `task_declared` claim is not `no_plan`.
  Update its docstring to say so.

### A3. `.aitask-scripts/lib/parallel_admission_vocab.py`
- `PROVENANCES += ("task_declared",)`.
- `CAVEAT_REASONS["task_declared"] = NONE` — bare code; the scope carries the
  task (`CAVEAT:inflight:<ref>|task_declared`, `CAVEAT:candidate|task_declared`).

### A4. `.aitask-scripts/lib/parallel_admission.py` (`decide`, pure)
- Validate every in-flight surface's provenance with `check_member` (today only
  the candidate's is validated).
- Candidate `task_declared` + resolved → `caveat("candidate", "task_declared")`.
- Blocking in-flight claim with a `task_declared` resolved surface →
  `caveat(scope, "task_declared")` (drives the verdict). A no-collision result
  therefore grades **CLEAR_CAVEATED**, never bare CLEAR — "CLEAR = fully
  evidenced on both sides" stays true. A specific overlap is still a CONFLICT
  (the check is advisory; hiding an overlap because the evidence is coarse would
  be fail-open).
- Advisory-tier (stale) claims: no `task_declared` caveat — they already do not
  drive the verdict.
- `_display`'s CLEAR_CAVEATED wording already lists the driving caveat codes, so
  `task_declared` appears in `DISPLAY:` with no display change.
- The checker's `INFLIGHT:` row gains a 6th field,
  `INFLIGHT:<ref>|<sources>|<liveness>|<n_paths>|<path_state>|<provenance>`,
  rendered through `check_member(…, vocab.PROVENANCES, …)`, so a consumer (and
  B's assessment) can tell a description-derived surface from a plan-derived
  one. Document the row grammar in the module docstring (no doc spells it out
  today). Surveyed consumers: only `test_parallel_admission.py:126` matches the
  row exactly and is updated; the rest use `startswith` / substring / field
  indices `[2]`, `[4]`.

### A5. `.aitask-scripts/lib/trail_gather.py` + the records adapter
The gatherer classifies against the **code branch only**
(`plan_paths.tracked_sets(root)`, `trail_gather.py:909`), where every task-data
path (`aitasks/metadata/…`) classifies `phantom`; only the adapter holds
`data_tracked`. So the gatherer must **not** judge "phantom-only": it would
discard a description whose sole real path is a task-data file before the
adapter could promote it, and the gatherer path would disagree with the
collector, which already judges against the union (`resolve_corpora`). Split
the invariant by what each side can know:
- `_classify_plan_paths` (signature and 4-tuple return unchanged —
  `test_trail_gather.py:1907-1929` stubs it): when `plan is None` and `row`
  exists, extract `plan_paths.task_body_text(row.text)`. **No non-malformed
  token** (a corpus-independent fact) → the unchanged `no_plan` sentinel.
  Otherwise emit a marker record `INFLIGHT_PATH:<ref>|task_declared|-` followed
  by **every** classified record of the description, phantoms included.
  `has_plan` stays False; `INFLIGHT_SCAN`'s corpus axis stays about plans
  (documented next to `_corpus_status`).
- `parallel_admission.surfaces_from_inflight_records` — the one place both
  corpora are known on this path. **Its phantom promotion becomes the shared
  classification rule, not exact membership.** Today it promotes a `phantom`
  record only when the path is *in* `data_tracked` (`parallel_admission.py:
  550-551`), while the collector classifies against the union of tracked files
  **and directories** (`resolve_corpora` → `plan_paths.classify`): a proposed
  new file under an existing task-data directory
  (`aitasks/metadata/profiles/custom.yaml` beside a tracked `fast.yaml`) is
  `planned_new` to the collector and `no_plan` here. Fix: the adapter and
  `input_from_records` take `data_dirs` alongside `data_tracked`, plus the
  classifier **by injection** (`classify=plan_paths.classify`, passed by the
  impure caller) — `parallel_admission` must stay pure and cannot import
  `plan_paths`, which imports `subprocess` (poisoned by
  `tests/test_parallel_admission_purity.py`). A `phantom` record is promoted
  iff `classify(path, data_tracked, data_dirs)` is `tracked` / `planned_new`.
  That is the collector's rule applied to the half the gatherer could not see,
  so resolution agrees by construction (code-branch phantom ∧ data-side
  resolved ⇔ union resolved; `malformed` is checked first on both). It also
  closes the same pre-existing blind spot for **plan**-derived task-data paths.
  With no classifier injected the adapter keeps today's exact-membership
  behaviour, documented as the degraded mode. Then a ref carrying the marker
  gets `provenance="task_declared"`: a resolved `task_declared` surface if ≥1
  path resolved, otherwise
  `Surface(ref, "plan_declared", (), "no_plan")` — never `all_phantom`. The
  marker is handled explicitly: the adapter files an unknown class as phantom
  (`parallel_admission.py:552-553`).
- Grammar: `task_declared` joins the class list at `trail_gather.py:40` and
  `.claude/skills/aitask-trail/SKILL.md.j2:72` (+ its 3 goldens) as a per-task
  **provenance marker** with a `-` path — not a sentinel, not an UNCHECKABLE
  code. No new record prefix (keeps `test_trail_skill_contract.sh:88-89`'s
  pinned prefix count) and no `NORMALIZATION_VERSION` bump: every `INFLIGHT*`
  line is emitted after `DIGEST:` and is digest-excluded (`trail_gather.py:
  1122-1128`, pinned by `test_digest_is_unchanged_by_the_flag`).
- Consumer reality (surveyed): the roadmap driver does **not** read these lines —
  it goes through `collect_population` (`roadmap_run.py:344`), i.e. A2's path,
  which already sees both corpora. The adapter's only caller is
  `input_from_records`; the lines' other reader is the aitask-trail skill. The
  producer-to-adapter parity test (Tests) is what keeps the two paths agreeing.

### A6. Measurement (Final Implementation Notes)
Before any code change and again after A:
`./.aitask-scripts/aitask_parallel_admission.sh replay --candidates auto --from
plan --lock-freshness require-fresh` — record the verdict-rate shift and the
`UNCHECKABLE_CAUSE` census. Acceptance is the mechanism, not the statistic.

## Part B — `aitask-pick` pre-claim parallel-safety assessment (opt-in)

**Opt-in by user decision.** `parallel_assessment` is `"off"` in every shipped
profile and seed mirror, and a **missing key is off**. When disabled, the
templates omit the assessment entirely — no checker invocation, no extra
reading, no prompt — so a default pick pays no new time cost. `show` and `ask`
are preserved for users who enable it.

### B0. Shared checker contract `.claude/skills/task-workflow/parallel-admission-checker.md`
`parallel-admission.md` steps 2-3 (invocation + well-formedness) render away
entirely when `parallel_admission` is off (`parallel-admission.md:29-33`), and
`remote` ships it off — so the assessment cannot borrow them. Extract them into
an **ungated** shared file (no profile conditionals) that each caller references
only from its own *enabled* branch, so it is in the rendered closure whenever
either caller is on, whatever the other's toggle:
- the `if out="$(…)"` capture form (never merge stderr), the three
  non-preferences (`--lock-freshness require-fresh` mandatory; the checker's
  self-exclusion; read live state at call time), and the table classifying an
  output as **"checker unusable"** (exit 2, other non-zero, no / multiple
  `VERDICT:`, token outside the closed set, unlisted cause). `--plan
  "<plan_file>"` is **optional**: the post-plan preflight passes it; the
  pre-claim assessment omits it (no plan exists yet, and `--from plan` resolves
  plan → description after A).
- It defines the **classification only**. Dispositions stay with each caller:
  the preflight maps "checker unusable" to its UNCHECKABLE disposition
  (unchanged behaviour); the assessment's is B1 step 6.
- `parallel-admission.md` steps 2-3 become a reference to it (with `--plan`);
  nothing else in the preflight changes.

### B1. New procedure `.claude/skills/task-workflow/parallel-assessment.md`
Jinja-templated like `parallel-admission.md` (strict renderer: every key test is
`profile.parallel_assessment is defined and …`). **Enabled only when the value
is `"show"` or `"ask"`**; absent, `"off"`, `false` or anything else is disabled.
The disabled branch interpolates nothing (no `{{ profile.name }}`), so every
shipped profile renders it byte-identically.
Rendered into every agent's `task-workflow-<profile>-/` automatically by the
closure walker (`lib/skill_template.py:332-438`) — no manifest, no stub edits;
Codex/OpenCode get it for free.

Inputs: `task_id`, `task_file`, `active_profile`. Steps:
1. **Disabled** (`{% if not (profile.parallel_assessment is defined and
   profile.parallel_assessment in ["show", "ask"]) %}`) → the whole procedure
   renders as a one-line no-op. (Reached only if something links it directly —
   the pick template already omits the reference when disabled, B2.)
2. **Skip** when the selected task's `status` is `Implementing` (the resume path —
   Step 2.0 or `/aitask-pick <in-flight id>`; it is already claimed and the
   post-plan preflight covers it) or `issue_type: manual_verification` (writes no
   code). Display one line saying it was skipped and why.
3. **Run the checker** per `.claude/skills/task-workflow/parallel-admission-checker.md`
   (B0), **without `--plan`**:
   `check --candidate <task_id> --from plan --lock-freshness require-fresh`.
   If that contract classifies the output as **checker unusable**, keep the
   reason; the assessment continues on reading alone and step 6 decides.
   After Part A the candidate resolves from its description. Its `OVERLAP:` /
   `CAVEAT:` / `UNCHECKABLE_CAUSE:` / `INFLIGHT:` lines are **structured input,
   not the answer**. The population is the checker's `INFLIGHT:` rows — the same
   gate ∪ lock ∪ status union t1569 computes, with liveness — not re-derived.
4. **Read** the candidate's description, and for each in-flight row whose
   liveness is not `dead`: its task description (to the first `## Inbox` /
   `## Gate Runs`) and its plan when `aitask_query_files.sh plan-file` finds one.
   `dead` rows are listed as excluded, not assessed. **Read budget:** when
   there are more than 12 live rows, read in full only those the checker named
   in `OVERLAP:` lines or that share a label or topic anchor with the candidate,
   skim the rest by title only. A skimmed row is graded `not assessed` in
   step 5 — never `unrelated`.
5. **Assess**: one line per live in-flight task graded `overlaps` / `adjacent` /
   `unrelated` / `not assessed`. **`not assessed`** is mandatory wherever the
   evidence was not actually read — a title-only skim (step 4), an unreadable
   task file — and says which; a title never establishes `unrelated`. The other
   three grades carry the concrete reason (same file; same procedure or template;
   same seed mirror / golden set; same subsystem; one consumes the other's
   record format). Then an overall recommendation: any `overlaps` → name them;
   otherwise the result is **"incomplete"**, naming each gap, whenever either
   coverage has one — never "no overlap found":
   - *reading coverage*: any `not assessed` row;
   - *deterministic coverage*, read from the checker's **well-formed** output,
     not only from a malformed one: a `VERDICT:UNCHECKABLE` (list every
     `UNCHECKABLE_CAUSE:` verbatim — e.g. `candidate|no_plan` when the
     candidate's own description names no file, `locks|<reason>` when lock
     freshness failed, `inflight:<ref>|<reason>`); and any
     `INFLIGHT_SOURCE:<gate|lock|status>` whose status is not `ok` — then the
     **population itself may be incomplete**: a task missing from the
     `INFLIGHT:` rows cannot be graded at all, so the gap is named as "in-flight
     enumeration incomplete (<source>: <status>)";
   - separately, B0's "checker unusable" (malformed output, crash, bad exit),
     named as "checker unavailable". Never the words "safe to run
   in parallel" — same wording rule as the preflight. Then print the checker's
   `DISPLAY:` line verbatim, labelled **"Deterministic view (checker):"** — or
   `Deterministic view (checker): unavailable — <reason>` when B0 classified the
   output as checker unusable.
6. **Prompt** — `ask`: always. `show` (attended): when any task is graded
   `overlaps` **or** the checker was unusable — agent judgement without its
   deterministic cross-check is not silently accepted; `not assessed` rows alone
   do not prompt (the read budget is this procedure's own choice) but are named
   in the display and in any question; the same holds for a well-formed
   `VERDICT:UNCHECKABLE` and an incomplete enumeration (step 5's deterministic
   gaps) — carried as "incomplete", no extra prompt, advisory continuation
   preserved. Headless profile (`{% if
   profile.headless %}`), in either enabled mode: never prompt — display the
   assessment, the not-assessed list and any checker-unavailable line, then
   continue; this pre-claim look is advisory and the post-plan preflight (when
   enabled) remains the later check. Otherwise `AskUserQuestion`, findings **inside the question text** (the
   `aitask-explore` visibility rule), header "Parallel", options in this order:
   "Pick anyway" / "Pick a different task" / "Stop". Continue first; nothing is
   ever selected automatically.
7. **Branches** — nothing has been claimed yet (Step 4 has not run), so no branch
   reverts anything: "Pick anyway" → return; "Pick a different task" → back to
   task selection (Step 2a; Step 1 when the task came from a Step 0b argument);
   "Stop" → end the workflow.
Notes: advisory, agent judgement, never a guard (t1343 remains the only basis
for a hard stop); two call sites / two evidence qualities / one checker (this
pre-claim look, then the plan-derived preflight at the planning Checkpoint and
IMPLEMENT re-entry); ordering vs. `resource-admission.md` unchanged.

### B2. `.claude/skills/aitask-pick/SKILL.md.j2`
Insert as the **first action of pick's Step 3**, before "Set the following
context variables, then read and follow …/task-workflow/SKILL.md". Every route
into Step 3 (Step 0b auto-confirm and confirm macros, 2c, 2d, 2.0) passes
through it with no re-routing of three separate "Proceed to Step 3" sites. Wrap
the bullet in `{% if profile.parallel_assessment is defined and
profile.parallel_assessment in ["show", "ask"] %}` — a missing or `off` setting
renders **nothing** in Step 3: no reference, hence no checker call, no extra
reading and no prompt (and
the walker pulls nothing). Reference it by full path
(`.claude/skills/task-workflow/parallel-assessment.md`) — a bare filename
resolves against `aitask-pick/` and is silently skipped. Update pick's Notes
with one bullet.

### B3. Profile key `parallel_assessment: ask | show | off`
- `aitasks/metadata/profiles/{default,fast}.yaml` + `seed/profiles/` mirrors:
  `parallel_assessment: "off"`, and the same in `remote.yaml` + mirror —
  **opt-in**; a missing key is also off. `profiles.md` documents `"off"` as the
  default and `"show"` / `"ask"` as the opt-in values.
  Quoted, same rationale as `parallel_admission`.
- `.claude/skills/task-workflow/profiles.md`: table row mirroring the
  `parallel_admission` row (`:50`) and a prose section mirroring `:69-108`,
  including the headless rule (`ask` never valid for a headless profile).
- Settings-TUI `profile_editor.py` does not list `parallel_admission` either;
  not extended here (unknown keys survive a save, `profile_editor.py:719`).

## Part C — shipped default, docs, coordination

### C1. The shipped `parallel_admission` default — decided on the prompt rate
Candidate change: `default` and `fast` (+ `seed/profiles/` mirrors) `"off"` →
`"warn"`; `remote` stays `"off"` (headless) — t1569_4's approved target
(p1569_4 :762-769) and the task's ask. Knob semantics (`confirm | warn | off`)
unchanged. `warn` asks for **both** CONFLICT and UNCHECKABLE
(`parallel-admission.md` step 6), so verdict availability alone is not the
criterion: a replay with 0% UNCHECKABLE and 100% CONFLICT would still prompt on
every pick. Decided in t1688_2, re-measured there (the population moves between
sessions):
1. **Prompt-producing rate** = (CONFLICT + UNCHECKABLE) / candidates, from
   `replay --candidates auto --from plan --lock-freshness require-fresh`.
2. **Precision sample**: up to 5 CONFLICT verdicts whose `OVERLAP:` involves a
   `task_declared` surface (either side). For each, read both descriptions and
   classify the shared path as an **edit collision** or a **context mention**;
   record the table in t1688_2's plan.
3. **Recommendation rule** (orders the options; the user decides at t1688_2's
   planning, with the numbers in the question text): flip to `warn` only when
   the prompt-producing rate is **≤ 30%** of candidates **and** at most half of
   the sampled `task_declared` conflicts are context mentions; otherwise keep
   `"off"`, record the numbers, and the docs keep describing `off` as shipped,
   with the measured reason.
The comprehensive precision study stays the separate
`measure_task_declared_precision` follow-up; it does not gate this decision.

### C2. Procedure + profile docs (current-state only, no version history)
- `parallel-admission.md` Notes: "two call sites, two evidence qualities, one
  checker"; the "regex-extracted from plan prose" bullet also covers task
  descriptions; step-5 `no_plan` remedy reads "no plan **and** no path-bearing
  description".
- `profiles.md`: `parallel_admission` row (`:50`) + opt-out rationale
  (`:98-107`) rewritten for C1's outcome (flipped to `warn`, or kept `off` with
  the measured reason); new `parallel_assessment`
  row + section (B3).
- Website: `skills/aitask-pick/parallel-admission.md` (`:16-17` "once",
  `:24-26` "plan's prose", `:78-91` — rewritten per C1's outcome — the "Why all three ship off"
  subsection, `:100` remedy row; add a `task_declared` CLEAR_CAVEATED example and
  the pre-claim assessment as a short section), `execution-profiles.md` (`:44`
  + new `parallel_assessment` row), `skills/aitask-pick/_index.md` (`:32`,
  `:58-64`), `workflows/parallel-development.md` (`:44-46`),
  `skills/aitask-backlog-roadmap.md` (`:30-31`). Run `check_links.py --build`.
- `aidocs/framework/background_work_roadmap.md`: the parallel-safe lane was
  empty by construction before this task; `CLEAR_CAVEATED` (incl.
  `task_declared`) lands in the core lane at medium/low confidence
  (`roadmap_policy.py:91-92, 432-433`).

### C3. Coordination — `./ait note` at Step 8e (advisory context, not work)
- **t1569** (status section `:311-335` is now stale) and **t1569_7**: C1's
  outcome — if the shipped profiles flipped to `warn` (remote `off`), the
  `[t1569_4]` items verify as shipped; if C1 kept `off`, they still verify under
  a `confirm` profile, now with the measured reason; the CLEAR_CAVEATED rendering item
  (`t1569_7:27`, `:46`) gains the `task_declared` caveat.
- **t1343**: extends its t1688 pointer (`:399-401`) — `task_declared` is a
  description heuristic, not a declaration; t1343 remains the only admissible
  basis for a hard stop.
- **t1470**: cross-reference only (consumer of the same verdicts).
- The t1569_6 point ("parallel-safe lane was empty by construction") goes into
  the roadmap aidoc (C2), not a note — t1569_6 is archived.

## Tests
- `tests/test_parallel_admission.py`: `claim()` helper gains `provenance=`;
  new cases — in-flight `task_declared` no-collision → `CLEAR_CAVEATED` with
  `CAVEAT:inflight:t9|task_declared`; candidate `task_declared` →
  `CAVEAT:candidate|task_declared`; `task_declared` specific overlap → still
  `CONFLICT`; advisory-tier `task_declared` claim emits no `task_declared`
  caveat; NegativeControlTests: a `task_declared` surface can never yield bare
  `CLEAR`; undeclared in-flight provenance raises `VocabularyError`.
- `tests/test_parallel_admission_vocab.py`: add a `task_declared` fixture to
  `_fixtures()` (`:152-175`) so the parse-every-emitted-reason test covers it.
- `tests/test_parallel_admission_collect.py`: fixtures now write
  `aitasks/t<N>_*.md` bodies — (a) no plan + body naming a tracked path →
  resolved `task_declared`, collect → not UNCHECKABLE, graded CLEAR_CAVEATED;
  (b) no plan + body with no path → `no_plan` (unchanged); (c) no plan + body
  paths only under `## Inbox` / `## Gate Runs` → `no_plan` (the cut works);
  (d) no plan + only phantom paths → `no_plan`; (e) no task file → `no_plan`;
  (f) candidate with no plan resolves from its description
  (`resolve_candidate_surface`); (g) read-once: the task body is read once when
  the task is both candidate and claim in one `replay` (mirrors `:578-625`);
  (h) `no_plan_claims` omits a `task_declared` claim. Anything reaching
  `col.main` sits under `_ReplayScaffold` / `ExcludeNoPlanPredicateTests` so the
  44f92f5fa `_FrozenClock` pin covers it.
- `tests/test_plan_paths.py`: `cut_task_framework_sections` cuts at the first of
  the two headers in either order, ignores `> | ## Inbox` note-body lines,
  leaves `## Merged from t<N>` intact; `task_body_text` strips frontmatter.
- `tests/test_trail_gather.py`: a no-plan task with a path-bearing body emits
  the `task_declared` marker then all its classified records (phantoms
  included); an empty or malformed-only body → `no_plan`; the adapter turns a
  marker whose paths resolve in neither corpus into `no_plan`, never
  `all_phantom`.
- New `tests/test_task_declared_parity.py` — **producer-to-adapter parity**, the
  case adapter-only tests cannot catch (evidence discarded upstream): one
  fixture repo whose no-plan in-flight task's description names **only** a
  tracked task-data file (`aitasks/metadata/profiles/fast.yaml`). Run the
  gatherer (`--with-inflight`), feed its `INFLIGHT_PATH:` lines to
  `surfaces_from_inflight_records(data_tracked={that path})`, and assert the
  same resolved `task_declared` surface (ref, paths, resolution, provenance) as
  `collect()` with `_DATA_TREE` reporting that path. Control: the path absent
  from the data corpus → `no_plan` on both sides. Second case — **directory
  evidence**: a description naming only a *proposed new* file under an existing
  tracked task-data directory (`aitasks/metadata/profiles/custom.yaml`, only
  `fast.yaml` tracked there) → `planned_new` on both sides, the same resolved
  `task_declared` surface; with the directory absent from the data corpus →
  `no_plan` on both. Third: the same new file named by a **plan** rather than a
  description → the adapter agrees with the collector there too.
- `tests/test_parallel_admission_preflight.sh`: string pins on the invocation /
  well-formedness text follow it into `parallel-admission-checker.md` (B0); the
  new file joins `test_skill_render_task_workflow.sh` Test 0's lists if its
  Jinja scan includes it. Keep the `no_plan` control at
  `:140-151`; add the end-to-end case (no-plan in-flight body names
  `src/beta.py` → `VERDICT:CLEAR_CAVEATED`, `CAVEAT:inflight:200|task_declared`).
- `tests/test_skill_render_task_workflow.sh`: `parallel-assessment.md` into
  `WRAPPED_FILES_INVARIANT` + one golden `parallel-assessment-default.md` (every
  shipped profile is disabled and that branch interpolates nothing, so the
  renders are byte-equal — the invariant test asserts it);
  the shipped-profile `parallel_admission` pins (`:632-644`), the `off` loop
  (`:602-612`) and the `parallel-admission-*` goldens follow **C1's recorded
  outcome** — flip: `warn`/`warn`/`off` and the loop reduced to `remote` + the
  synthetic `off`; keep: unchanged. Independent of the outcome, synthetic
  `warn` and synthetic `off` profiles are rendered and asserted (`warn`: checker
  invoked, the step-6 question for CONFLICT/UNCHECKABLE; `off`: no-op), so both
  branches stay covered whichever ships; new pins for
  `parallel_assessment` `"off"` in all three profiles **and** their seed mirrors;
  comment `:80-92`.
- `tests/test_skill_render_aitask_pick.sh` new Test 7, **disabled and enabled
  renderings**, via `skill_template.py` against real and scratch profiles
  (scratch YAMLs written to a temp dir: a copy of `fast.yaml` with the key
  removed, set to `"show"`, set to `"ask"`, and `remote.yaml` set to `"show"`):
  - disabled — `default`, `fast`, `remote` and the key-absent scratch profile:
    the rendered pick contains no `parallel-assessment.md`, no
    `aitask_parallel_admission.sh`, and its Step 3 has no new `AskUserQuestion`;
  - enabled — `show` and `ask`: the rendered pick names
    `task-workflow/parallel-assessment.md` on a line **before** the "read and
    follow … task-workflow" hand-off line (line-order pattern from
    `tests/test_inbox_surfacing_render.sh:126-138`);
  - enabled procedure renders — `show`: references the B0 contract without
    `--plan`, prompt conditional on `overlaps` or checker unusable; `ask`:
    prompt unconditional; headless `show`: no `AskUserQuestion` at all; all
    three carry the `not assessed` grade, the "incomplete" recommendation rule
    — with the well-formed `VERDICT:UNCHECKABLE` / `INFLIGHT_SOURCE:`-not-`ok`
    gaps asserted as a clause **separate** from the malformed-output "checker
    unavailable" one — and the `Implementing` skip.
  - **independent toggles, at closure level** (not text-mention): walk the full
    rendered closure from `aitask-pick/SKILL.md.j2` (the in-memory walk
    `aitask_skill_verify.sh:135-142` uses) for a scratch profile with
    `parallel_assessment: "show"` **and** `parallel_admission: "off"` (plus its
    headless variant): the closure contains `parallel-admission-checker.md`
    rendered with the capture form, `--lock-freshness require-fresh` and the
    checker-unusable table, and `parallel-assessment.md`'s reference resolves to
    it. Control: both off → the closure contains neither file.
- Goldens regenerated in the same commit (aitask-pick entry goldens +
  task-workflow procs); `./.aitask-scripts/aitask_skill_rerender.sh remote` and
  commit the new committed-closure files.

## Verification
- `bash tests/<each touched .sh>`; `bash tests/run_all_python_tests.sh
  --test-dir tests` (last line only; `set -o pipefail`).
- `./.aitask-scripts/aitask_skill_verify.sh` (incl. committed remote
  prerenders); `shellcheck` on any touched `.sh`.
- `cd website && python3 check_links.py --build`.
- Live: A6 before/after replay; `check --candidate <a Ready task> --from plan
  --lock-freshness require-fresh` no longer reports `no_plan` for in-flight tasks
  whose descriptions name files.
- Live render: `aitask_skill_render.sh aitask-pick --profile fast` renders **no**
  assessment (opt-in); rendered against a scratch profile setting
  `parallel_assessment: "show"` it shows the
  assessment before the hand-off; the procedure skips an `Implementing` task.

## Decomposition — 2 children (user decision at the Complexity Assessment)

Created post-approval via `task-creation-batch.md` (`--parent 1688`, fast
profile auto-injects `--gates "risk_evaluated"`); each child's own pick re-runs
risk evaluation on its verify path. Parent t1688 then reverts to `Ready`
(`--assigned-to "" --plan-approved-at ""`), its lock is released, and this file
is externalized as `aiplans/p1688_*.md`; child plans go to
`aiplans/p1688/p1688_{1,2}_*.md`, committed together.

- **t1688_1 `parallel_admission_task_declared_surface`** — enhancement, high
  priority, effort high. **Part A** (A1-A6) and its tests: `test_plan_paths.py`,
  `test_parallel_admission.py`, `test_parallel_admission_vocab.py`,
  `test_parallel_admission_collect.py`, `test_trail_gather.py`, the
  `test_parallel_admission_preflight.sh` end-to-end case, the aitask-trail
  grammar line + its 3 goldens, and `aitask-backlog-roadmap/SKILL.md:215-218`.
  Records the before/after `replay` census in its Final Implementation Notes —
  the baseline t1688_2's C1 re-measures and decides on.
- **t1688_2 `aitask_pick_preclaim_parallel_assessment`** — enhancement, high
  priority, effort high; auto-depends on t1688_1. **Part B** (B0 shared checker contract, opt-in procedure, pick
  Step 3 insertion, `parallel_assessment` knob) and **Part C** (the gated
  `warn` flip, docs, Step 8e notes), plus the skill-render tests, goldens and
  `aitask_skill_rerender.sh remote`. Reads t1688_1's archived plan for the rates.
- **Manual-verification sibling**: offered per `planning.md` (N=2 → prompt).

## Risk

### Code-health risk: medium
- The fallback changes the in-flight surface for **every** consumer at once
  (preflight, roadmap, `replay`); a body cut that lets other agents' `## Inbox`
  prose through would manufacture CONFLICTs on every pick once `warn` is on ·
  severity: low (residual — the four no_plan controls are pinned before the code
  changes, including the section-cut case) · → mitigation: inline pre-phase
  pin_no_plan_controls
- Two line protocols change — a 6th field on the checker's `INFLIGHT:` row and a
  `task_declared` marker class in `INFLIGHT_PATH:`; the adapter files an unknown
  class as phantom, so a missed adapter update fails silently · severity: medium
  · → mitigation: covered in-plan — explicit marker handling in
  `surfaces_from_inflight_records` with its own test; the one exact-match
  consumer (`test_parallel_admission.py:126`) updated
- Two producers of in-flight surfaces judge against different corpora (the
  gatherer sees the code branch only, the collector the code ∪ task-data union);
  judging "phantom-only" in the gatherer would drop task-data-only descriptions
  the collector keeps, and exact-membership promotion would still miss
  proposed new files under task-data directories · severity: medium ·
  → mitigation: covered in-plan — the judgement moves to the adapter (A5),
  which applies the injected shared classifier to task-data files **and**
  directories, and the producer-to-adapter parity test (existing file, new file
  under an existing directory, plan-derived) pins agreement with the collector
- B0 moves the preflight's steps 2-3 into a shared file, changing the rendered
  preflight for every profile that enables it · severity: low · → mitigation:
  covered in-plan — goldens regenerated, preflight string pins moved with the
  text, behaviour unchanged
- Skill surface: the two new files (B0 contract, B1 procedure) can enter the
  committed `task-workflow-remote-`
  closure; three golden families move (aitask-pick, task-workflow procs,
  aitask-trail) · severity: low · → mitigation: covered in-plan —
  `aitask_skill_verify.sh` (`walk-verify` catches a missing re-render) and
  goldens regenerated in the same commit
- Flipping shipped profiles to `warn` re-introduces a prompt on every pick that
  is still UNCHECKABLE **or** CONFLICT · severity: medium · → mitigation:
  covered in-plan — C1 decides it in t1688_2 on the combined prompt-producing
  rate and a precision sample, with the user choosing on those numbers

### Goal-achievement risk: medium
- Task descriptions name files as **context** as well as edit targets, so
  `task_declared` overlaps are coarser than plan-derived ones; the prompt rate
  may not justify `warn` · severity: medium (residual — C1 decides the flip on
  the combined prompt-producing rate plus a 5-conflict precision sample) ·
  → mitigation: measure_task_declared_precision
- A fixes only `no_plan`-driven UNCHECKABLEs; other causes (`all_phantom` plans,
  cross-host/unknown liveness, lock fetch failures) remain · severity: medium ·
  → mitigation: covered in-plan — the A6 census names every remaining cause;
  acceptance is the mechanism, not a corpus statistic
- The pre-claim assessment is agent judgement: its quality varies by agent and
  it adds reading cost to every pick where it is enabled · severity: low ·
  → mitigation: covered in-plan — **opt-in** (every shipped profile and a
  missing key are off, and the disabled render carries no checker call, reading
  or prompt); when enabled, `show` prompts only on `overlaps`, headless never
  prompts, and B1 step 4's read budget bounds the cost
- Local `main` lacks 44f92f5fa (t1763's `_FrozenClock` pin); new `col.main`
  tests would date-rot · severity: low · → mitigation: covered in-plan — new
  tests sit under the two pinned scaffolds; the Checkpoint's Remote Drift Check
  offers the pull

### Planned mitigations
- timing: pre-phase | name: pin_no_plan_controls | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — fallback changes every consumer's surface / body-cut leak | desc: pin today's no_plan output on the collector and gatherer paths (no task file, pathless body, phantom-only body, paths only under Inbox/Gate Runs) before A changes code
- timing: after | name: measure_task_declared_precision | type: enhancement | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — description surfaces may be too coarse to justify warn | desc: extend `aitask_parallel_admission.sh sweep` with a task-description source and score task_declared surfaces against landed files over the archived corpus (precision/recall, CONFLICT vs CLEAR_CAVEATED split), as t1643 did for plan surfaces

Both lines are carried into **t1688_1**'s child plan: the pre-phase runs first in
its implementation, and its Step 8d creates the `after` task (it measures what
t1688_1 ships). No `before` line, so Step 7's Part 2 is a no-op. Post-inline
reassessment (single pass): both levels stay **medium** — the inline phase lowers
one code-health bullet to a residual, and the remaining medium bullets are
unchanged.

## Step 9 (Post-Implementation)
Per child: current-branch mode (profile `fast`), no merge; archive via
`./.aitask-scripts/aitask_archive.sh 1688_<n>`; the parent archives with the
last child.
