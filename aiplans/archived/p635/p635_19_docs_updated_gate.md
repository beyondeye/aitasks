---
Task: t635_19_docs_updated_gate.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_*.md
Archived Sibling Plans: aiplans/archived/p635/p635_*_*.md
Base branch: main
---

# t635_19 — `docs_updated` gate (first concrete procedure-backed gate)

## Context

The original gates design (`aidocs/gates/aitask-gate-framework.md` §"Verifier
skill contract") makes gates **user-customizable `aitask-gate-<name>` skills**
authored from a **template skill** — the extensibility promise being "a user can
add a project-specific gate (`security_scan`, `changelog_updated`, …) in ten
minutes." t635_11 then shipped a **headless** engine + **command-script**
verifiers (exit codes), because `ait gates run` / the autonomous lane can't invoke
a Claude skill. That works for machine checks (build/tests/risk) but **cannot** do
the agent work `docs_updated` needs (inspect the change, infer which docs, ask the
user, write prose — the original worked example literally shows the docs verifier
*updating* stale docs).

So `docs_updated` is the **first concrete *procedure-backed* gate** — an
`aitask-gate-<name>` **skill** (the original design's model), run by the *attended*
agent, that the *headless* engine defers. This task lands that one gate **and** the
minimal seam that makes procedure-backed gates a first-class (if not-yet-general)
registry citizen. The gate is **not** a hardcoded one-off inside task-workflow.

**Layered spec (user direction):**
- `gates.yaml` — wires the gate and marks it **procedure-backed**.
- `seed/doc_update_guide.md` — the **generic default** guide (new projects).
- `aitasks/metadata/doc_update_guide.md` — this repo's **configured** guide (from
  `aidocs/framework/`), pointed to by `project_config.yaml`.
- `.claude/skills/aitask-gate-docs-updated/SKILL.md` — how the agent **performs and
  records** the gate.

**Explicitly deferred to a follow-up (not built here):** the full custom/external
procedure-gate system — external skill resolution, async/headless behavior, richer
registry schema, plugin gates, remote/comment-signal integration, complete
dispatch semantics.

## Design

### 1. New skill — `.claude/skills/aitask-gate-docs-updated/SKILL.md`

Authored from `aitask-gate-template` (§2), a **plain** skill (no profile-render
variants — matches `aitask-run-gates`/`aitask-gate-template` precedent; profile
interactivity is handled in-body). Contract input `<task-id> <attempt> <run-id>`;
it is **project-agnostic** (never references `aidocs/framework/`). Steps:

1. **Load the spec, layered:** read the **generic seeded guide** for the method,
   then layer this repo's **configured guide** named by `project_config.yaml`
   `doc_update.guide` (+ any `extra_guides`/overrides). The configured guide is the
   source of truth for doc roots, the change-kind→doc-area map, and writing
   conventions.
2. **Gather the change surface** (to *inform*, not to pass/fail): the task's
   `(t<task-id>)` commits (`git show --name-only` over `git log -F --grep`) plus the
   uncommitted working tree during implementation.
3. **Infer + propose** which doc pages/sections to create/update, from the change
   kind + the spec's map + the **shape of existing docs**; draft per the guide's
   conventions.
4. **Confirm with the user** (always, attended) via `AskUserQuestion`
   (apply / adjust / skip-with-reason). Autonomous/remote profiles follow their
   non-interactive policy per the loaded profile.
5. **Apply** the confirmed doc edits (code-tree files → committed with the task).
6. **Record the terminal block**, reconciling the `running` block that the
   dispatch seam allocated (§4b) — `aitask_gate.sh append --only-if-running
   <run-id> <id> docs_updated <status> attempt=<n> type=machine kind=procedure
   verifier=aitask-gate-docs-updated result=… log=…` (the same atomic
   running→terminal transition the headless engine uses). The skill receives
   `<attempt>`/`<run-id>` as its positional args — it does **not** invent them.
   **Status semantics (consistent everywhere — concern; no pass/skip overlap):**
   - **`pass`** — the procedure **performed the required doc work**, OR inspected
     the doc-relevant surfaces and **confirmed the existing docs are already
     correct**.
   - **`skip`** — the procedure **evaluated the task and concluded `docs_updated`
     is not applicable** to this change (no doc surface needed review/update).
     Terminal-satisfied, distinct from `pass`.
   - **`fail`** — docs **are** needed but the user **blocks/rejects** the update.

   Note the pass-vs-skip line: if doc-relevant surfaces existed and were checked
   (whether edited or already-correct) → `pass`; if the change had no doc-relevant
   surface at all → `skip`. Write a sidecar log like other verifiers.

### 2. Extend `aitask-gate-template` — document the procedure/agent variant

The template currently documents only the **command-script** verifier. Add a
second documented variant: a **procedure/agent verifier** = a skill that reads
context + a project spec/guide, does the work, **confirms with the user**, appends
the terminal block, and is marked `kind: procedure` in the registry so the
**headless engine defers** it (`needs-agent`) while the **attended** workflow/resume
run it. Document the run contract (the dispatch seam allocates `attempt`/`run-id`
via `aitask_gate.sh begin-procedure` §4b; the skill closes with
`append --only-if-running`) and the **status semantics** (`pass` = work done /
already-correct; `skip` = evaluated, not applicable; `fail` = user rejects). This
delivers the original design's "author your own gate" promise for work-gates
(e.g. `changelog_updated`). (Plain skill edit → auto-renders to Codex/OpenCode;
no goldens.)

### 3. Registry — `aitasks/metadata/gates.yaml`

```yaml
  docs_updated:
    type: machine            # agent-run work (not human sign-off)
    kind: procedure          # PROCEDURE-BACKED: headless engine defers (needs-agent)
    description: "Update the docs for this change per the project doc-update spec"
    blocks_dependents: false # post-integration sign-off — must not block dependents
    verifier: aitask-gate-docs-updated   # resolves to the SKILL for attended dispatch;
                                          # the headless engine never shell-executes it
    max_retries: 0
    # unlocks: ABSENT (linear-default convention)
```

**Header-comment addition — command verifiers vs procedure-backed gates.** A
*command verifier* (`kind` absent/`command`) is run headlessly (exit codes); a
*procedure-backed gate* (`kind: procedure`) is an `aitask-gate-<name>` **skill**
run by the attended agent — `ait gates run` reports it `needs-agent` and never
executes it. Point at the §7 follow-up for the future general schema.

**Dormant now + tracked activation.** Not added to any `default_gates` here (an
unproven work-gate shouldn't fire on every pick); the §7 activation follow-up adds
it to `fast.yaml` once the live-verify MV proves it.

### 4. Headless engine — minimal `kind: procedure` deferral

- **`.aitask-scripts/lib/gate_ledger.py` `read_registry`** (shared parser): parse
  the new `kind` key (default `None`/`command`). Defaulted ⇒ backward-compatible;
  covered by the registry python test.
- **`.aitask-scripts/lib/gate_orchestrator.py`**: a gate with `kind == "procedure"`
  is **excluded from headless machine dispatch** (never `resolve_verifier`d /
  spawned) and reported via `blocked_reason` as **`needs agent (procedure-backed
  gate — run via task-workflow / aitask-resume)`**. It is *unlocked-but-not-headless-
  runnable*, mirroring how empty-verifier gates are already excluded and reported —
  a small, contained branch. It **reuses the existing `SATISFIED = {pass, skip}`
  predicate** (t635_11): a procedure gate that already recorded `pass` **or** `skip`
  is satisfied → not unlocked → **not** reported as needs-agent; the report fires
  only while it is not terminal-satisfied. No new ledger *status* enum (unrun ⇒ no
  ledger entry; the skill appends pass/skip/fail itself), so archive-ready stays
  fail-safe (unsatisfied until the skill records `pass` **or** `skip`).

### 4b. Procedure-gate start helper — `aitask_gate.sh begin-procedure <task-id> <gate>` (concern)

Because the headless engine defers procedure gates, it never allocates their
`attempt`/`run-id` or writes the `running` block — so the attended path needs a
concrete contract (the skill must not invent these). Add a `begin-procedure`
subcommand to `aitask_gate.sh` (it already owns the per-task lock, ledger read via
`gate_ledger.py`, run-id generation, and the append path — the same primitives the
orchestrator's `run_gate` uses). Under the per-task lock it: computes
`attempt = current_attempts(gate) + 1`, generates `run_id = <ISO-8601-Z now>`,
appends the `running` marker block (`type=machine kind=procedure`), and prints
`RUN_ID:<run_id>` / `ATTEMPT:<attempt>` for the caller. The dispatch seam (§5)
parses these and passes them to the skill; the skill closes the run with
`append --only-if-running <run_id>` (§1.6). This mirrors the engine's
running→terminal discipline exactly, so procedure-gate runs are well-formed in the
ledger and TUIs. (`aitask_gate.sh` is already whitelisted — no new whitelist
entry.) Covered by a `test_gate_orchestrator.sh` case (begin-procedure allocates a
monotonic attempt + a running block; the skill's `--only-if-running` terminal
append yields exactly one terminal entry).

### 5. Attended dispatch seam — task-workflow / aitask-resume (generic on `kind: procedure`)

- **Primary — start of Step 8, before the change summary/review.** For each
  procedure-backed gate in the task's effective gates that is **not
  terminal-satisfied** — i.e. its current ledger status is **neither `pass` nor
  `skip`** (a gate that already recorded `skip` is done and is **not**
  re-dispatched) — dispatch it: **(a)** allocate the run via
  `aitask_gate.sh begin-procedure <id> <gate>` (§4b) → parse `RUN_ID`/`ATTEMPT`;
  **(b)** resolve `verifier` `aitask-gate-<name>` → `.claude/skills/aitask-gate-<name>/SKILL.md`
  and **Read-and-follow it with `<id> <attempt> <run-id>`**. Keyed on
  `kind: procedure` (not hardcoded to docs), but for `docs_updated` this placement
  means doc edits are in the **reviewed diff** and the **Step-8 `(t<id>)` commit**
  (docs live on `main`). The skill records the terminal result (§1.6).
- **Backstop — existing Step-9 archival gate-guard.** A task resumed at `POSTIMPL`
  with `docs_updated` not terminal-satisfied (neither `pass` nor `skip` — the
  archive-ready predicate already treats both as satisfied) hits the existing
  `GATE_PENDING` guard → "Resolve now";
  enhance that hint to "dispatch the procedure gate's skill to satisfy it". No new
  Step-9 branch logic.
- **Jinja + goldens.** The Step-8 dispatch block + a Procedures/notes entry edit the
  Jinja source `.claude/skills/task-workflow/SKILL.md` (gate under the existing
  `record_gates`/effective-gates pattern). Re-render `task-workflow-{default,fast,
  remote}-` + regenerate goldens; `aitask_skill_verify.sh` must pass. See
  `aidocs/framework/skill_authoring_conventions.md` "Regenerate goldens after any
  closure edit".

### 6. Layered spec files

- **6a. `seed/doc_update_guide.md` (generic default).** Project-agnostic — invented
  placeholder names, **no aitasks-internal paths, no `aidocs/framework/` reference**.
  Documents only the *method*: identify affected doc areas from the change kind;
  infer from existing-doc shape; current-state-only; confirm before applying; how to
  read `project_config.yaml doc_update:` and fill the project's own roots +
  conventions. **Install-flow touch** → read `aitasks_extension_points.md` before
  editing `aitask_setup.sh` / the seed manifest.
- **6b. `aitasks/metadata/doc_update_guide.md` (configured aitasks guide).**
  Hand-authored **from `aidocs/framework/`** (this is where aitasks's own doc
  knowledge lives — referenced *here, in the project's configured guide*, never from
  the generic skill/seed). Encodes: the doc landscape (`website/content/docs/`
  sections `concepts`/`workflows`/`skills`/`tuis`/`commands`/`installation`/
  `getting-started` + `aidocs/`; Hugo/Docsy); the change-kind→doc-area map (TUI →
  `docs/tuis/<name>.md`; skill/command → `docs/skills/`·`docs/commands/`; new
  `workflows/*.md` → its hand-curated `workflows/_index.md` bullet); and the writing
  conventions distilled from `documentation_conventions.md` +
  `adding_a_new_codeagent.md` §23b (current-state-only; "**autonomous**" not
  "auto-execution"; genericize the supported-agent set; generic example project
  names; no "sister"-repo terminology). On the data branch → `./ait git`.
- **6c. `aitasks/metadata/project_config.yaml`.** Small pointer (guide is the source
  of truth — derive-don't-duplicate):
  ```yaml
  doc_update:
    guide: aitasks/metadata/doc_update_guide.md   # this repo's configured spec (6b)
    # extra_guides: [...]   # optional, additive
  ```

### 7. Follow-up — full procedure-gate generalization (created post-approval)

New t635 child (`feature`), `depends:` on this task: external skill resolution,
async/headless behavior for procedure gates, richer registry schema
(`kind`/plugin/external), custom plugin gates, remote/comment-signal integration,
and complete dispatch semantics across autonomous (`pickrem`/`pickweb`) + resume.
**Also (raised at review):**
- **Per-gate code-agent + model selection** — configure which agent/model runs a
  procedure gate's skill (today it runs in the task-working agent's context),
  with the corresponding **settings-TUI** surface. General to all proper gates.
- **Per-agent gate-skill wrappers + agent-aware dispatch** — the gate skills
  currently ship only in the Claude tree (like `aitask-run-gates`/
  `aitask-gate-template`); the Step-8/Step-9 dispatch resolves the skill in the
  running agent's tree, so procedure gates are Claude-only until the Codex/OpenCode
  wrappers land. Coordinate with **t635_23** (port gate skills) and make the
  dispatch resolution formally agent-aware.
Bidirectional pointer from this task; coordinate the wrapper half with t635_23.

### 8. Tests

- **Registry parse + headless defer** (`tests/test_gate_ledger_python_parser.py` +
  `tests/test_gate_orchestrator.sh`): `read_registry` parses `kind: procedure`
  (default when absent); a task declaring `gates: [docs_updated]` → `ait gates run`
  reports it **needs-agent**, does **not** shell-execute a verifier, appends no run,
  exits 0. Proves "procedure ⇒ headless defers".
- **Archive fail-safe + status semantics** (`test_gate_orchestrator.sh`): a task
  declaring `docs_updated` with no terminal run → `archive-ready` =
  `BLOCKED:docs_updated`; after `append docs_updated pass` → `ALL_PASS`; and
  after `append docs_updated skip` (evaluated/no-docs-needed) → **also `ALL_PASS`**
  (`skip` is terminal-satisfied). Asserts the concern-2 semantics.
- **Procedure-run well-formedness** (`test_gate_orchestrator.sh`): `begin-procedure`
  allocates a monotonic `attempt` + a `running` block; a following
  `append --only-if-running <run-id> … pass` leaves exactly one terminal entry
  (running→terminal, no duplicate).
- **Render/goldens**: `aitask_skill_verify.sh` passes (new `aitask-gate-docs-updated`
  skill ships all stub surfaces; task-workflow closure resolves); goldens
  regenerated; rendered Step-8 of a `record_gates` profile contains the
  procedure-gate dispatch.
- The skill's **behavior** (inference, confirmation, doc edits) is agent-driven →
  validated by the **live-verify MV** (§Risk), not unit tests.

## Scope-honesty note

Task text says a verifier **"skill"** that **"updates"** docs with a change-scoped
**"skip"** predicate. Realigned: it **is** a skill (per the original design) that
updates docs (agent work); the heuristic **detection/skip** framing is dropped —
the user's gate-placement is the signal, so `applies_when` (open-Q3) is
intentionally not implemented. Explicit AC reconciliation, not a silent deviation.

## Files

**New:** `.claude/skills/aitask-gate-docs-updated/` (SKILL.md + Codex/OpenCode stub
surfaces), `seed/doc_update_guide.md`, `aitasks/metadata/doc_update_guide.md`
(configured, from `aidocs/framework/`).
**Edited:** `.claude/skills/aitask-gate-template/` (procedure/agent variant),
`.claude/skills/task-workflow/SKILL.md` (Step-8 dispatch seam → re-render + goldens),
`.aitask-scripts/aitask_gate.sh` (`begin-procedure` subcommand, §4b),
`.aitask-scripts/lib/gate_ledger.py` (`kind` parse),
`.aitask-scripts/lib/gate_orchestrator.py` (defer `kind: procedure`),
`aitasks/metadata/gates.yaml` (gate + header distinction),
`aitasks/metadata/project_config.yaml` (`doc_update:` pointer), the setup/seed
install flow (register the generic guide — read `aitasks_extension_points.md`),
tests.

**Commit routing (data-branch arch):** `aitasks/metadata/*` (gates.yaml,
project_config.yaml, doc_update_guide.md) are symlinked into `.aitask-data/` →
`./ait git`, separate from skill/lib/seed/test code on `main` → plain `git`.
**Cross-agent port:** the skill + template + task-workflow are closures → auto-render
Claude→Codex/OpenCode; each new skill must ship all 3 stub surfaces
(`aitask_skill_verify.sh` enforces).

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` passes (new skill's 3 stub surfaces;
   task-workflow goldens regenerated).
2. Tests: registry parses `kind: procedure`; a task declaring `docs_updated` is
   reported **needs-agent** by `ait gates run` (no shell exec) and archive-`BLOCKED`
   until a `pass` is appended; existing `test_gate_orchestrator.sh` still passes.
3. `shellcheck` on any touched `.sh`.
4. **Live smoke (manual):** scratch task `gates: [docs_updated]`; `ait gates run`
   → reports needs-agent; run task-workflow Step 8 → `begin-procedure` allocates the
   run, the skill fires, proposes doc edits, confirms, applies, appends
   `docs_updated pass`; `ait gates run` → satisfied; `archive-ready` → `ALL_PASS`.
   Then a change needing no docs → the skill records **`skip`** (not `pass`) and
   `archive-ready` is still `ALL_PASS`; a user-rejected doc update → `fail`.
5. Step 9 (Post-Implementation) handles cleanup / archival / merge.

## Risk

### Code-health risk: medium
- Touches the **shared** `gate_ledger.read_registry` (`kind` parse) and
  `gate_orchestrator.py` (defer branch) — every gate consumer + TUIs depend on
  them; a regression could corrupt gate status framework-wide · severity: medium ·
  → mitigation: `kind` is a **defaulted, additive** key (absent ⇒ command, existing
  behavior unchanged) + registry python test asserting existing callers unaffected
  + the orchestrator defer test (in-plan).
- Edits the **shared** `task-workflow/SKILL.md` (consumed by every task-based
  skill); a mis-scoped Jinja hook / golden drift could affect the review region ·
  severity: medium · → mitigation: the dispatch is **gated on the task declaring a
  procedure gate** (none do yet ⇒ dormant, unchanged behavior) + goldens +
  `aitask_skill_verify.sh` (in-plan).

### Goal-achievement risk: medium
- The gate's value rests on the **skill's** inference + genuine user confirmation
  (agent-driven, not unit-testable) · severity: medium · → mitigation: generic
  method + configured guide + always-confirm bound it; the **live-verify MV**
  exercises inference, confirmation, the escape hatch, the `_index.md` manual-list
  rule, and the archive fail-safe end-to-end.
- **Dormant** ⇒ the checkpoint never fires until declared · severity: medium · →
  mitigation: the **activation follow-up** adds it to `fast.yaml` default_gates,
  gated on the MV (tracked, proof-gated).

### Planned mitigations
- timing: after | name: t635 child (docs_updated_live_verify) | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement "skill quality unexercised" | desc: autonomous MV declaring `gates: [docs_updated]` and driving the aitask-gate-docs-updated skill end-to-end — inference from a TUI/skill change to the right page, user-confirmation, the `_index.md` manual-list rule, the no-docs-needed → **skip** outcome (still archive-satisfied), and the archive fail-safe (BLOCKED until pass/skip). Run after this lands.
- timing: after | name: t635 child (docs_updated_activation) | type: chore | priority: medium | effort: low | addresses: goal-achievement "dormant gate never fires" | desc: add `docs_updated` to `fast.yaml` `default_gates`; `depends:` on the live-verify MV; bidirectional pointer from the MV.
- timing: after | name: t635 child (procedure_gate_generalization) | type: feature | priority: medium | effort: high | addresses: framework extension (user-requested) | desc: full custom/external procedure-gate system — external skill resolution, async/headless behavior, richer registry schema, plugin gates, remote/comment-signal integration, complete dispatch across autonomous + resume; PLUS per-gate code-agent/model selection (+ settings-TUI surface) and per-agent gate-skill wrappers + agent-aware dispatch resolution (coordinate with t635_23; procedure gates are Claude-only until wrappers land). `depends:` on this task (first concrete procedure gate).

## Step 9
Reference **Step 9 (Post-Implementation)** of the shared task-workflow for
cleanup, archival (child → `aitasks/archived/t635/`), and merge.

## Final Implementation Notes

- **Actual work done:** Landed `docs_updated` as the first **procedure-backed**
  gate. Engine: `gate_ledger.py` parses a new `kind` registry key + adds
  `unmet_procedure_gates()` and a `procedure-gates` CLI verb; `gate_orchestrator.py`
  excludes `kind: procedure` from headless dispatch and reports **needs agent**
  (reusing `SATISFIED = {pass, skip}`). `aitask_gate.sh` gains `begin-procedure`
  (opens the running block, prints `RUN_ID`/`ATTEMPT`) and `procedure-gates`.
  Registry: `docs_updated` gate (`kind: procedure`, verifier → skill) + a
  command-vs-procedure header section. New skill `aitask-gate-docs-updated`
  (reads the configured guide, updates docs with user confirmation, records
  pass/skip/fail via `append --only-if-running`). `aitask-gate-template` extended
  with the procedure/agent variant. Layered spec: `seed/doc_update_guide.md`
  (generic), `aitasks/metadata/doc_update_guide.md` (configured from `aidocs/framework/`),
  `project_config.yaml`/`seed/project_config.yaml` `doc_update:` pointer, install-flow
  registration. task-workflow Step-8 dispatch seam (generic over `kind: procedure`)
  + Step-9 backstop + regenerated goldens + committed remote prerenders. New test
  `tests/test_gate_procedure_docs.sh` (15/15).

- **Deviations from plan:** (1) The skill is authored **Claude-only** (matching the
  `aitask-run-gates`/`aitask-gate-template` precedent; a plain gate skill), not the
  "3 stub surfaces" the plan first claimed — Codex/OpenCode ports are tracked in
  **t635_23** (updated to include it + depend on t635_19). (2) Added a
  `procedure-gates` query subcommand (`aitask_gate.sh` + `gate_ledger.py` CLI) for a
  clean engine-owned Step-8 seam instead of parsing `gates.yaml` in markdown. (3)
  Tests in a dedicated `test_gate_procedure_docs.sh` (15 assertions) rather than
  extending existing files. (4) Terminal blocks carry `type=machine` only — **not**
  `kind=` (`aitask_gate.sh append` warns on unknown fields; `kind` lives in the
  registry). (5) The skill reads the **installed** guide via `project_config`
  `doc_update.guide`, never `seed/` (which install.sh deletes). (6) At review the
  Step-8 seam's hardcoded `.claude/skills/` path was made agent-tree-agnostic (it
  renders for Codex/OpenCode too).

- **Issues encountered:** Inline `# comments` after a scalar registry value are NOT
  stripped by `read_registry` — the initial `type: machine  # ...` polluted the
  value and broke the `kind == procedure` check; moved comments to their own lines
  (repo convention). The data-branch metadata edits (`gates.yaml`,
  `project_config.yaml`) were swept into concurrent syncer commits (t1095/t1096/
  t1099 "Start work") — left to the syncer per the concurrent-writers convention;
  the changes are on-branch. A concurrent session's `tests/test_shadow_spawn_config.sh`
  edit was present in the tree and deliberately **excluded** from this task's commit.

- **Key decisions:** Procedure gates are the framework's original "gates as
  user-customizable skills" model (t635_11 diverged to headless command verifiers);
  `docs_updated` is the first concrete instance. Headless engine **defers** them
  (`needs-agent`); the **attended** task-workflow/aitask-resume dispatch the skill and
  record. Status semantics: `pass` = docs updated or already-correct; `skip` =
  evaluated/not-applicable; `fail` = user rejects. Gate ships **dormant** (not in any
  `default_gates`) — activation is a proof-gated follow-up.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:** The procedure-backed-gate mechanism is now concrete:
  register a gate with `kind: procedure` + `verifier: aitask-gate-<name>`, author an
  `aitask-gate-<name>` skill from `aitask-gate-template`'s procedure variant, and the
  attended workflow dispatches it (`begin-procedure` → run skill → `append
  --only-if-running`). The headless engine defers it. **Follow-ups created:**
  live-verify MV, `docs_updated` activation (adds to `default_gates`, depends on the
  MV), and procedure_gate_generalization (external/remote/async + **per-gate
  agent/model config + settings TUI** + **agent-aware dispatch resolution**;
  per-agent skill wrappers coordinate with t635_23). Procedure gates are **Claude-only
  until t635_23** ports the wrappers.
