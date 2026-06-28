---
Task: t635_14_profile_gate_declaration_unification.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_20_stats_multistage_completion.md, aitasks/t635/t635_21_gate_ledger_merge_safety.md, aitasks/t635/t635_22_polish_board_inflight_empty_gate_state.md, aitasks/t635/t635_23_port_gate_skills_codex_opencode.md, aitasks/t635/t635_24_remove_legacy_verify_build_path.md
Archived Sibling Plans: aiplans/archived/p635/p635_10_monitor_gate_status_column.md, aiplans/archived/p635/p635_11_orchestrator_verifier_contract.md, aiplans/archived/p635/p635_12_build_test_machine_gates.md, aiplans/archived/p635/p635_13_risk_evaluation_gate_integration.md, aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md, aiplans/archived/p635/p635_4_gate_guarded_archival.md, aiplans/archived/p635/p635_5_ledger_driven_reentry.md, aiplans/archived/p635/p635_6_aitask_resume_skill.md, aiplans/archived/p635/p635_7_gate_aware_aitask_pick.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md, aiplans/archived/p635/p635_9_board_inflight_action_view.md
Base branch: main
plan_verified: []
---

# t635_14 — Profile → gate-declaration unification

## Context

Phase 4 of the gate framework (`aidocs/gates/integration-roadmap.md`). Today a
converted checkpoint is configured in **two** places: the gate registry
(`gates.yaml`, defining *how* a gate runs) **and** a profile Jinja toggle
(`risk_evaluation`, deciding *whether* the risk checkpoint runs at render time).
The locked Phase-4 principle: **profiles choose which gates get DECLARED in
`gates:` at planning time; the registry defines how they run — never configure
the same checkpoint twice.**

This task realizes that principle for the already-converted **risk** checkpoint
(build/tests landed dormant in t635_12; risk verifier in t635_13). It introduces
a `default_gates` profile key that drives gate declaration into new tasks, retires
the duplicated `risk_evaluation` Jinja toggle in favour of a runtime
effective-gate-set check, and closes the `risk_evaluated` double-record seam
flagged by t635_13.

### Decisions taken (user-confirmed this session)

1. **Blast radius — shipped `fast` declares `risk_evaluated` only.** `default`
   declares nothing (zero behaviour change). `risk_evaluated` is
   `blocks_dependents: false`, so dependency-unblock (t635_3) stays effectively
   dormant; only the archival guard (t635_4) activates for tasks that declare the
   gate (it must be recorded `pass` before archival — and it is, by the Step-9
   orchestrator).
2. **Declaration site — the shared `task-creation-batch.md` template.** All
   profile-driven creation (planning children, explore, review, qa) declares the
   active profile's gates consistently (single source, DRY). Broader goldens regen.
3. **Registry-level `default_gates` deferred.** The **profile** `default_gates`
   key is the mechanism now. Effective set = task `gates:` if the field is present,
   else profile `default_gates`. The orchestrator stays unchanged (reads task
   `gates:` only). Registry-level `default_gates` (which would need profile-less
   orchestrator resolution) is documented as a future fallback. *Explicit AC note
   — the task scope's "active profile / `default_gates`" is realized as the profile
   key; registry fallback is out of scope (no silent deviation).*

### Architecture (the unifying idea)

- **`default_gates` (profile key, list)** is the single source: injected as
  `--gates` at task creation, used as the planning-time producer-trigger fallback,
  and backfilled onto the task post-approval.
- **Effective gate set** = task's literal `gates:` field if present, else the
  active profile's `default_gates` (else empty). A new helper resolves it; used
  **only** in the read-only planning window (before the backfill writes the field).
- **Producer + checker ALWAYS toggle together (lockstep — t635_13 req #2).** The
  planning-time risk *producer* (`risk-evaluation.md`, authors `## Risk` + threads
  levels before plan approval) runs iff `risk_evaluated` ∈ effective set. Then, at
  the post-approval write point (Step 7, where plan mode's read-only constraint is
  lifted), a **gate-declaration backfill** writes `gates:` = the effective
  `default_gates` onto any task that lacks the field — so the producer's decision
  becomes a *real declaration*. The verify-time *checker* (`aitask-gate-risk`,
  t635_13) then runs at Step 9 because the task now literally declares the gate.
  Result: the producer never runs without the checker; there is **no
  producer-only legacy split**. (Explicit opt-out — `gates: []` present-but-empty,
  or a profile with no `default_gates` — means the producer never ran, so there is
  nothing to check; lockstep still holds vacuously.)
- **Double-record is structurally impossible:** the Step-7 `risk_evaluated`
  self-record fires only when the task does **not** literally declare the gate
  (decided by a unit-tested helper). After backfill a risk-gated task always
  declares it → self-record skipped → only the Step-9 orchestrator records. A
  non-declaring task never authored a `## Risk` section → self-record's
  `## Risk`-present precondition is false. Either way ≤1 terminal record.
- **Agent-invariance preserved:** all skill edits are *profile-dimension* (and
  several become profile-INvariant runtime prose). No `{% if agent %}` gate is
  introduced, so the 9 callers' Test 1b agent-invariance assertions still pass
  (checked `aidocs/framework/agent_runtime_guards_audit.md`).

---

## Implementation

### A. `default_gates` profile key + `list` type — `.aitask-scripts/lib/profile_editor.py`

`profile_editor.py` types are currently `bool/enum/string/int` only (no list).

- **`PROFILE_SCHEMA`**: add `"default_gates": ("list", None)`; **remove**
  `"risk_evaluation": ("bool", None)`. Update the `# type:` comment to include `list`.
- **`PROFILE_FIELD_INFO`**: add a `default_gates` entry (short: "Gates declared into
  new tasks"; long: explains it is injected as `--gates` at creation and drives the
  risk producer via the effective set; effective = task `gates:` else this list);
  **remove** the `risk_evaluation` entry.
- **`PROFILE_FIELD_GROUPS`**: "Gates" group → `["record_gates", "default_gates",
  "max_parallel_gates"]`; remove `risk_evaluation` from the "Planning" group.
- **Add `list` type handling at the 3 type-switch sites** (mirror `string`):
  - compose/TUI (~L557-588): `elif ktype == "list":` → `Input` pre-filled with the
    comma-joined values, id prefix `profile_list_`.
  - collect/serialize (~L631-658): `elif ktype == "list":` → split the input on
    commas, strip, drop empties → emit a YAML flow list (`[a, b]`); empty → omit key.
  - id-prefix map (~L862-863): add `profile_list_`.
  - Confirm the YAML **load** path round-trips a list value (display = join). Patch
    if it assumes scalars.

### B. Helpers — `gate_ledger.py` + `aitask_gate.sh`

Reuse the existing declared-gates reader (`read_declared_gates`, L387); add
resolution + two CLI surfaces.

- **`lib/gate_ledger.py`**:
  - `effective_gates(task_file, profile_file=None) -> list[str]`: if the
    frontmatter has a `gates:` *key* (present, even if `[]`) → return
    `read_declared_gates`; elif `profile_file` is given **and readable** → parse its
    `default_gates` list; else `[]`. Add `_frontmatter_has_key(text, key)` (reuse
    `_read_frontmatter_list_from_text` machinery + key-presence check). Profile
    `default_gates` parsing reuses the registry YAML-list reader.
    **Graceful degradation (concern 3):** a `profile_file` that is empty/`None`,
    nonexistent, or unparsable is treated as "no profile" — resolve from
    `task.gates` only (warn to stderr on an unreadable-but-named file). Never raise.
  - `should_self_record(task_file, gate) -> bool`: `gate not in
    read_declared_gates(task_file)` — the **literal** declaration check (NOT the
    effective set), because the orchestrator records based on the literal `gates:`
    field. This is the single testable decision point for the Step-7 self-record.
- **`aitask_gate.sh`** (new dispatch alongside `list`/`archive-ready`/`resume-point`,
   ~L475-481):
  - `effective-gates <task_id> [--profile <file>]` → `cmd_effective_gates`, prints
    one gate per line. If `--profile` is omitted **or** the file is unreadable, it
    resolves from `task.gates` only (mirrors the Python degradation).
  - `has-gates-field <task_id>` → `cmd_has_gates_field`, **exit 0 = the `gates:` key
    is present in frontmatter (even if `[]`), exit 1 = absent**. Thin wrapper over
    `_frontmatter_has_key`. This is the **field-presence oracle** the Step-7 backfill
    branches on — it distinguishes an absent field (eligible for backfill) from an
    explicit `gates: []` opt-out (must be preserved). `list` stays a declared-gate
    *listing*, never a presence oracle.
  - `should-self-record <task_id> <gate>` → `cmd_should_self_record`, **exit 0 =
    record (not declared), exit 1 = skip (declared)**. Thin wrapper over
    `should_self_record`. This is what the Step-7 self-record markdown branches on, so
    the decision is in tested code rather than prose.

### C. Retire `risk_evaluation` Jinja → runtime — shared closures

All edits are in the **source** `.claude/skills/task-workflow/{SKILL.md,planning.md}`
(rendered transitively; no `.j2`).

**`planning.md`:**
- §6.1 *End-of-planning terminal step* "Risk evaluation" bullet (`{% if
  profile.risk_evaluation %}`): replace the Jinja guard with always-rendered prose
  — compute the effective set: **if `active_profile_filename` is set**, run
  `aitask_gate.sh effective-gates <task_id> --profile
  aitasks/metadata/profiles/<active_profile_filename>`; **otherwise** (null/missing
  — manual/resume invocation) run `aitask_gate.sh effective-gates <task_id>` with no
  `--profile` (concern 3). **If** the output contains `risk_evaluated`, run the Risk
  Evaluation Procedure (`risk-evaluation.md`) and thread the levels; else skip.
- L163 verify-path inline narrative (`{% if profile.risk_evaluation %}…{% else %}
  and exit plan mode.{% endif %}`): make unconditional — always "run the
  End-of-planning terminal step before `ExitPlanMode`" (the terminal step itself
  decides risk at runtime).
- Risk-section guard (~L390-404, `{% if profile.risk_evaluation %}`): runtime-gate
  on the same effective-set check (only assert `## Risk` exists when `risk_evaluated`
  is in the effective set).

**`SKILL.md`:**
- **NEW — Gate-declaration backfill (post-approval write, top of Step 7):** before
  the risk block, add an always-rendered step gated on the **field-presence oracle**
  (not `list`, which can't tell absent from `gates: []`): if `aitask_gate.sh
  has-gates-field <task_id>` **exits 1** (field absent) **and**
  `active_profile_filename` is set, compute `eff=$(aitask_gate.sh effective-gates
  <task_id> --profile aitasks/metadata/profiles/<active_profile_filename>)`; if
  `eff` is non-empty, declare it on the task and commit:
  ```bash
  ./.aitask-scripts/aitask_update.sh --batch <task_id> --gates "<eff-csv>"
  ./ait git add aitasks/ && ./ait git commit -m "ait: Declare gates for t<task_id> from profile" 2>/dev/null || true
  ```
  This makes the producer's planning-time decision a real declaration so the Step-9
  checker runs (lockstep). No-op when `has-gates-field` exits 0 — i.e. the task
  already declares gates **or** carries an explicit `gates: []` opt-out (which is
  preserved, never overwritten) — or the profile has no `default_gates`.
  `aitask_update.sh --gates` already exists (replaces-all).
- Step 7 risk block (L327-342): **remove** the outer `{% if
  profile.risk_evaluation %}…{% endif %}`. The "Risk fields (post-approval write)"
  step stays, runtime-gated on its existing condition ("if the plan has a `## Risk`
  section").
- The `risk_evaluated` self-record (L338-341) — **double-record structural fix
  (t635_13 req #3):** keep the `{% if profile.record_gates %}` guard, **add** the
  runtime guard: record here **only if `aitask_gate.sh should-self-record
  <task_id> risk_evaluated` exits 0** (task does not literally declare the gate).
  When it declares (the post-backfill norm), exit 1 → skip; the Step-9 orchestrator
  records it. Decision lives in the tested helper, not prose.
- Step 8c→8d nav (L506, `{% if profile.risk_evaluation %}Step 8d{% else %}Step 9
  {% endif %}`): → always "Step 8d".
- Step 8d section (L507-527, `{% if profile.risk_evaluation %}`): remove the guard
  (always render); its body already runtime-checks "if the plan has a `###
  Planned mitigations` subsection with `after` lines" → no-op when no mitigations.

### D. `default_gates` injection at creation — `task-creation-batch.md`

In the canonical parent + child `aitask_create.sh --batch` templates, inject after
`--labels`:
```
{% if profile.default_gates is defined and profile.default_gates %}--gates "{{ profile.default_gates | join(',') }}" \
{% endif %}
```
(render-time, single source = `default_gates`; `fast` → `--gates "risk_evaluated"`,
`default` → omitted). Document `--gates` in the Input table + optional-flags prose.
`aitask_create.sh` already supports `--gates` (t635_1) — no script change.

### E. Documentation

- **`profiles.md`**: replace the `risk_evaluation` schema row with `default_gates`
  (type `list`); keep `record_gates`/`max_parallel_gates`. Add a **"Gate Declaration
  Model"** section: profiles declare via `default_gates`; registry defines how;
  effective set = task `gates:` else profile `default_gates`; the Step-7 backfill
  makes the declaration durable; producer+checker toggle together; registry-level
  `default_gates` deferred. **Caveat to document:** declaring a **human** gate
  (`plan_approved`/`review_approved`/`merge_approved`) requires `record_gates: true`
  (only the workflow records those) or the archival guard deadlocks — the shipped
  risk-only default avoids this, but custom profiles must heed it.
- **`gate-recording.md`**: note the `risk_evaluated` self-record now fires only for
  tasks that do **not** declare the gate (declared → orchestrator records).
- **`aidocs/gates/aitask-gate-framework.md:466`** (the planning.md integration-table
  row): update to "writes `gates:` into new tasks from the active profile's
  `default_gates` via `task-creation-batch.md`; effective set = task `gates:` else
  profile default; registry-level `default_gates` deferred".
- **`aidocs/gates/dependency-unblock-semantics.md`** & **`gate-guarded-archival.md`**:
  update the "dormant until t635_14" statements to current state — *honestly*:
  archival guard activates for tasks declaring `risk_evaluated`; dependency-unblock
  stays dormant under the shipped risk-only default (no `blocks_dependents` gate
  declared).
- **`aidocs/gates/integration-roadmap.md`**: mark the Phase-4 configuration-
  unification principle as realized (profile `default_gates`; registry deferred).

### F. Profile YAML migration

- `aitasks/metadata/profiles/fast.yaml` (active, `.aitask-data` → `./ait git`):
  remove `risk_evaluation: true`; add `default_gates: [risk_evaluated]`.
- `seed/profiles/fast.yaml` (main → plain `git`): add `default_gates:
  [risk_evaluated]`.
- `default.yaml` / `remote.yaml` (seed + active): no `default_gates`; confirm neither
  carries `risk_evaluation`.

### G. Tests + goldens

- **New `tests/test_gate_effective_gates.sh`** — helper resolution + decisions:
  - `effective_gates`: `gates:` present & populated → those; present & empty `[]` →
    empty (opt-out honoured); absent + `--profile` w/ `default_gates` → profile list;
    absent + no `--profile` → empty; absent + **nonexistent/unparsable** profile →
    empty + stderr warning, no crash (concern 3).
  - `has-gates-field`: absent → **exit 1**; present-populated → **exit 0**; present
    but `gates: []` → **exit 0** (the case `list` cannot distinguish). Pins that the
    backfill never clobbers an explicit opt-out.
  - `should-self-record`: declaring task → **exit 1** (skip); non-declaring → **exit
    0** (record). This is the unit-tested Step-7 decision.
- **New `tests/test_gate_declaration_backfill.sh`** — the Step-7 backfill primitive,
  driven by the real `has-gates-field` gate:
  - no `gates:` field + profile `default_gates:[risk_evaluated]` → backfills
    `gates: [risk_evaluated]`;
  - **explicit `gates: []` opt-out** → `has-gates-field` exits 0 → **no overwrite**
    (field stays `[]`);
  - already-declaring task → no change;
  - profile with no `default_gates` → field stays absent.
- **Double-record regression** (t635_13 req #3) — covers **both halves** (Step-7
  self-record logic AND Step-9 orchestrator), with a negative control:
  - *Declaring task* (`gates:[risk_evaluated]`, `## Risk` plan + both levels):
    drive the actual Step-7 decision — `should-self-record` exits 1 → **do not**
    self-record; then `ait gates run` (Step-9) → assert **exactly one** terminal
    `risk_evaluated`.
  - *Negative control* (proves the guard is load-bearing): if Step-7 self-records
    **unconditionally** (skipping the guard) then `ait gates run` → **two** terminal
    records. Asserts the bug exists without the guard and the guard removes it.
  - *Non-declaring task* (no `gates:`, `## Risk` present): `should-self-record`
    exits 0 → self-record once; `ait gates run` → `No gates declared` → orchestrator
    records nothing → **exactly one**. (Models `tests/test_gate_risk_verifier.sh`
    test 8 for the terminal-count assertion.)
- **Render-content assertions** (so instructions can't drift from the helpers) —
  extend the task-workflow render test: the rendered Step-7 (record_gates profile)
  MUST contain `should-self-record … risk_evaluated` in the self-record block AND
  the `effective-gates … --gates` backfill step.
- **`profile_editor` tests**: update for `default_gates` + the new `list` type;
  drop `risk_evaluation` assertions.
- **Goldens**: rerender all profiles for task-workflow + the 9 caller skills
  (`aitask_skill_rerender.sh`), regenerate affected `tests/golden/` skill+proc
  goldens, run `aitask_skill_verify.sh`.
- **Regression**: `shellcheck` new/edited scripts; run `tests/test_gate_orchestrator.sh`,
  `test_gate_verifiers.sh`, `test_gate_risk_verifier.sh`, dependency-unblock &
  archival tests.

### Coordination / cross-agent

- **No cross-agent port task**: skill edits auto-render Claude→Codex/OpenCode;
  helper scripts are agent-agnostic. (Gate *skills* port is t635_23, separate.)
- **t635_24** (`depends: [t635_14]`, removes the legacy inline `verify_build`
  fallback) — scope intact; unblocks once this archives. No reverse edit needed
  beyond noting completion.

---

## Files

- **New:** `tests/test_gate_effective_gates.sh`,
  `tests/test_gate_declaration_backfill.sh`; double-record regression test
  (new file or added to an existing gate test).
- **Edited (scripts):** `.aitask-scripts/lib/profile_editor.py`,
  `.aitask-scripts/lib/gate_ledger.py`, `.aitask-scripts/aitask_gate.sh`.
- **Edited (skill closures):** `.claude/skills/task-workflow/SKILL.md`,
  `planning.md`, `task-creation-batch.md`, `profiles.md`, `gate-recording.md`
  (+ rendered variants + goldens).
- **Edited (profiles):** `aitasks/metadata/profiles/fast.yaml`,
  `seed/profiles/fast.yaml`.
- **Edited (docs):** `aidocs/gates/aitask-gate-framework.md`,
  `dependency-unblock-semantics.md`, `gate-guarded-archival.md`,
  `integration-roadmap.md`.
- **Edited (tests):** `profile_editor` test(s).

## Verification

1. `shellcheck` the edited scripts; `bash tests/test_gate_effective_gates.sh` and
   the double-record regression pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens regenerated &
   committed in the same change.
3. Regression: `test_gate_orchestrator.sh`, `test_gate_verifiers.sh`,
   `test_gate_risk_verifier.sh`, dependency-unblock & archival tests still pass;
   `profile_editor` tests pass.
4. **Live smoke:** create a child under `fast` → confirm it gets `gates:
   [risk_evaluated]`; pick it → producer runs at planning, `## Risk` authored, Step-7
   writes levels & **skips** the self-record (task declares), Step-9 `ait gates run`
   records exactly one `risk_evaluated pass`, archival guard sees `ALL_PASS`.
   Create a child under `default` → no `gates:` field, behaviour unchanged.
5. **Lockstep on a pre-existing fast task with no `gates:` field:** producer runs
   (effective fallback to profile `default_gates`); Step-7 **backfills**
   `gates: [risk_evaluated]`; `should-self-record` → skip; Step-9 orchestrator runs
   the checker and records exactly one `risk_evaluated`. Confirm the committed task
   file now declares the gate (producer never ran without the checker).
6. **No-profile invocation:** run the producer-trigger helper path with
   `active_profile_filename` unset (e.g. resume/manual) → no invalid command, no
   crash; effective set falls back to the literal `gates:` (empty if absent).
7. **Step 9 (Post-Implementation)** handles cleanup / archival / merge.

## Risk

### Code-health risk: medium
- Edits central shared closures (`SKILL.md`, `planning.md`, `task-creation-batch.md`)
  consumed by reference by 9 caller skills → broad profile-goldens regen · severity:
  medium · → mitigation: changes are **profile-dimension and agent-invariant** (no
  `{% if agent %}` gate, Test 1b safe); `default` declares nothing (zero behaviour
  change); full rerender + `aitask_skill_verify.sh` + golden regen guard drift.
- New `list` type in `profile_editor.py` touches the settings-TUI type switch ·
  severity: low · → mitigation: mirror the `string` path at all 3 switch sites +
  `profile_editor` test.
- New `effective_gates` helper in `gate_ledger.py`/`aitask_gate.sh` is additive ·
  severity: low · → mitigation: dedicated unit test + `shellcheck` + gate-test
  regression.

### Goal-achievement risk: medium
- The producer/checker lockstep + double-record fix live partly in **markdown
  instructions** (not directly executable) · severity: medium · → mitigation:
  the two structural decisions are encoded in **unit-tested helpers**
  (`should-self-record` for the Step-7 record; the Step-7 **backfill** that makes
  the declaration real so the checker always runs); the double-record regression
  exercises **both halves** (Step-7 decision + Step-9 orchestrator) with a
  **negative control** proving the guard is load-bearing; **render-content
  assertions** keep the instructions wired to the helpers; the pre-existing
  **t1015** (`gate_orchestrator_live_verify` MV) covers the live declared-gate flow
  for Phase-4 verifiers (add a coordination note).
- Registry-level `default_gates` deferred → the roadmap's "and the registry's
  default_gates" is only partially realized · severity: low · → mitigation: explicit
  scope-honesty note in plan + `aitask-gate-framework.md`; profile key fully covers
  the shipped profiles' needs.

### Planned mitigations
- No new before/after task: live validation is covered by the **pre-existing t1015**
  MV (Phase-4 live verify) — add a coordination note that risk gate-declaration
  landed. `risk_mitigations_planned: false`.

## Final Implementation Notes

- **Actual work done:** Realized the Phase-4 configuration-unification principle for
  the risk checkpoint. (1) Added a `default_gates` **profile** key + a new `list`
  type to `profile_editor.py` (PROFILE_SCHEMA / PROFILE_FIELD_INFO / "Gates"
  PROFILE_FIELD_GROUPS; list edited as a comma-separated string row reusing the
  string-widget infra, serialized as a YAML list), and **removed** the
  `risk_evaluation` key. (2) Added three gate-resolution helpers in
  `lib/gate_ledger.py` — `effective_gates` (task `gates:` if the field is present,
  else profile `default_gates`, with graceful degradation on a missing/unreadable
  profile), `should_self_record` (literal-declaration check), and
  `_frontmatter_has_key` — exposed via `aitask_gate.sh` `effective-gates` /
  `has-gates-field` / `should-self-record`. (3) Retired every `{% if
  profile.risk_evaluation %}` Jinja gate in `planning.md` + `SKILL.md`, replacing
  them with always-rendered, runtime-gated prose driven by `effective-gates`; added
  a **Step-7 gate-declaration backfill** (keyed off the `has-gates-field` presence
  oracle so an explicit `gates: []` opt-out is never overwritten) so producer +
  checker toggle together; gated the Step-7 `risk_evaluated` self-record on
  `should-self-record`. (4) Injected `--gates` from `default_gates` into the shared
  `task-creation-batch.md`. (5) Set `default_gates: [risk_evaluated]` on seed +
  active `fast.yaml`. (6) Updated `profiles.md` (Gate Declaration Model),
  `gate-recording.md`, and four `aidocs/gates/*` docs to current state. (7) Added
  `tests/test_gate_effective_gates.sh`, `tests/test_gate_declaration_backfill.sh`,
  `tests/test_gate_no_double_record.sh`; rewrote Test 5 + extended Test 6 of
  `test_skill_render_task_workflow.sh`; regenerated 7 procedure goldens and the
  committed `remote` prerenders across all 3 agent trees.

- **Deviations from plan:** (a) The `list` type reuses the existing `profile_str_`
  widget id (comma-separated string row) instead of a new `profile_list_` prefix —
  this avoids touching `on_key`/`_apply_string_edit`, which already map non-int
  types to `profile_str_`. (b) The negative-control assertion in the double-record
  test was reframed: empirically the orchestrator **skips an already-`pass` gate**
  ("All gates satisfied"), so bypassing the Step-7 guard does not duplicate the
  record — it lets the self-record **mask the real `aitask-gate-risk` verifier**
  (which never runs). The test asserts that the guard ensures the verifier's
  authoritative record exists (`Result: risk evaluated`), and the negative control
  proves the verifier is masked without it. The structural fix is unchanged; the
  test now pins the actual failure mode.

- **Issues encountered:** `set -u` tripped on a same-`local`-statement self-reference
  in a test helper (split into two `local`s). The active `aitasks/metadata/profiles/
  fast.yaml` edit was swept into a concurrent syncer commit on the aitask-data
  branch (expected per the concurrent-writers model) — it is persisted correctly.
  shellcheck emits only the documented SC1091 baseline.

- **Key decisions:** `default_gates` is a **profile** key (per t635_2 coordination);
  the registry-level `default_gates` fallback is **deferred** (it would require
  profile-less orchestrator resolution) — documented in `aitask-gate-framework.md`,
  `integration-roadmap.md`, and `profiles.md`. The shipped `fast` declares only
  `risk_evaluated` (machine gate, `blocks_dependents: false`): so dependency-unblock
  (t635_3) stays dormant, while the archival guard (t635_4) goes live for `fast`
  tasks (the Step-9 orchestrator records `risk_evaluated pass`, so a normal run
  archives through). All edits are profile-dimension and agent-invariant (no
  `{% if agent %}` gate) — Test 1b byte-identity across agents still holds
  (`agent_runtime_guards_audit.md` checked). No new helper scripts → no whitelist
  changes (new subcommands ride the already-whitelisted `aitask_gate.sh`).

- **Upstream defects identified:** None.

- **Notes for sibling tasks:** The effective-gate-set model is now concrete:
  `aitask_gate.sh effective-gates <id> [--profile <file>]` = task `gates:` if present
  else profile `default_gates`; `has-gates-field` is the presence oracle (distinguishes
  absent from `gates: []`); `should-self-record <id> <gate>` decides Step-7
  self-record (exit 0 record / 1 skip). A profile declares gates via the
  `default_gates` list key; new tasks get it via `--gates` at creation and a picked
  task gets it via the Step-7 backfill. **For t635_24:** the legacy inline
  `verify_build` path is still present (its removal is t635_24's job); this task did
  not touch it. **Caveat for any profile that declares human gates** (plan/review/
  merge): pair it with `record_gates: true` or the archival guard deadlocks. The
  pre-existing **t1015** (`gate_orchestrator_live_verify` MV) covers live end-to-end
  validation of the declared-gate flow.
