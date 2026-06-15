---
Task: t635_6_aitask_resume_skill.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_5_ledger_driven_reentry.md (landed), aitasks/t635/t635_7_gate_aware_aitask_pick.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_*.md … p635_5_ledger_driven_reentry.md
Base branch: main
---

# t635_6 — `aitask-resume` skill (programmatic re-entry surface)

## Context

Phase 2 of the gate-framework roadmap (decision **D8**): the user-facing unified
re-entry flow is gate-aware `aitask-pick` (t635_7), but a **separate
`aitask-resume <task-id> [--gate <name>]`** skill is wanted as the
**programmatic** surface — for initial testing of re-entry, for TUI invocation
(board In-Flight view ops, t635_9), and for any interaction surface that needs
direct "resume this task" control without the full pick funnel.

The resume **engine already exists** (t635_5, landed): `aitask_gate.sh
resume-point <id>` → `PLAN | IMPLEMENT | POSTIMPL`, and `task-workflow` Step 3
**Check 5** + the **Re-entry Routing** subsection (end of Step 4) perform the
in-conversation resume. This task adds a **thin front** over that engine — it
**must not fork** the derivation/routing. It is also the **seed of the future
`aitask-run-gates` orchestrator** (t635_11): when that engine lands,
`aitask-resume` becomes its conversational front (no second engine).

**Decided (user, this session):** the "headless variant for TUI / programmatic
launches" is satisfied by the **`remote` profile rendered on-demand** — NOT by
committed `prerender_for_headless` prerenders. All in-scope consumers (board
In-Flight, TUI, testing) are local where minijinja is present; committing
prerenders would impose an enforced `rerender remote`+recommit on every future
`task-workflow/` edit, and minijinja-less Web is the autonomous lane (t635_17),
out of scope here.

## Approach

A new **profile-aware entry-point skill** authored exactly like `aitask-pick`
(stub + `.md.j2`), whose body resolves a task id and **hands off to
`task-workflow` Step 3** — where the landed Check 5 / Re-entry Routing do all the
resume work. Resolver key / `skill_name`: **`resume`** (the resolver already
degrades unknown keys to `default`; `ait skillrun resume …` works with no
registration). No `ait` dispatcher entry, no helper-script whitelist change
(uses only already-whitelisted `aitask_query_files.sh`, `aitask_gate.sh`,
`aitask_pick_own.sh`, `aitask_ls.sh`).

### New files

1. **`.claude/skills/aitask-resume/SKILL.md.j2`** — authoring template (entry
   point; only profile dependence is `{{ profile.name }}` baking + the
   `task-workflow` reference, which the dep-walker rewrites to
   `task-workflow-<profile>-/SKILL.md`). Body:

   - **Step 0 — Parse args:** `/aitask-resume <task-id> [--gate <name>]`.
     `<task-id>` required (parent `16` or child `16_2`); capture `--gate <name>`.
     Missing id → usage + stop.
   - **Step 0b — Best-effort sync** (mirror `aitask-pick` Step 0c):
     `aitask_pick_own.sh --sync` (non-blocking).
   - **Step 1 — Resolve task file + context:** if id contains `_` → child:
     `aitask_query_files.sh child-file <parent> <child>`, then gather sibling
     context via `sibling-context <parent>` (read parent + `ARCHIVED_PLAN:`
     files). Else parent: `aitask_query_files.sh resolve <number>`; if
     `HAS_CHILDREN:` → list children (`aitask_ls.sh -v --children`) and **stop**
     with guidance to re-invoke with a specific child id (resume is
     single-task-scoped, not a drill-down). `NOT_FOUND` → error + stop. Read the
     task file; capture current `status` as `previous_status`.
   - **Step 2 — Surface resume state (+ `--gate`):** run `aitask_gate.sh
     resume-point <id>` and `aitask_gate.sh status <id>`; display recorded
     checkpoints + the derived target (`PLAN`→plan from scratch /
     `IMPLEMENT`→Step 7 impl / `POSTIMPL`→Step 9). If status ≠ `Implementing`
     **or** resume-point `PLAN`: advise "not in-flight — resuming behaves like a
     fresh `/aitask-pick` (plans from scratch)", then continue (task-workflow
     handles it identically). **`--gate <name>` (pre-orchestrator):** report the
     named gate's current ledger state and note "automated per-gate verifier
     execution arrives with the orchestrator (t635_11); for a human gate pass
     use `ait gate pass <id> <gate>`." Do **not** run a verifier (no second
     engine). The resume hand-off proceeds regardless of `--gate`.
   - **Step 3 — Hand off:** set context vars and read/follow
     `.claude/skills/task-workflow/SKILL.md` from **Step 3: Task Status Checks**:
     `task_file`, `task_id`, `task_name` (filename stem), `is_child`,
     `parent_id`, `parent_task_file`,
     `active_profile: { name: {{ profile.name }} }`,
     `active_profile_filename: {{ profile.name }}.yaml`,
     `previous_status` (the status read in Step 1), `skill_name: "resume"`.

2. **3 stubs** (canonical bodies from `aidocs/framework/stub-skill-pattern.md`
   §3b/§3d, resolver key `resume`):
   - `.claude/skills/aitask-resume/SKILL.md` (agent `claude`; reads
     `.claude/skills/aitask-resume-<profile>-/SKILL.md`)
   - `.agents/skills/aitask-resume/SKILL.md` (agent `codex`; reads
     `.agents/skills/aitask-resume-<profile>-codex-/SKILL.md`)
   - `.opencode/commands/aitask-resume.md` (agent `opencode`; the two
     `@`-includes + reads `.opencode/skills/aitask-resume-<profile>-/SKILL.md`)
   - **Plus** `.opencode/skills/aitask-resume/SKILL.md` — the OpenCode
     discovery-skill stub, present for every existing entry skill
     (pick/qa/revert/pickrem all have it). Mirror `aitask-pick`'s exactly.

3. **Goldens:** `tests/golden/skills/aitask-resume/SKILL-{default,fast,remote}-claude.md`
   (3 files, claude canonical — per the golden-dimensionality rule; no
   `{% if agent %}` gate, so codex/opencode are byte-identical and covered by
   Test 1b).

4. **Test:** `tests/test_skill_render_aitask_resume.sh` modeled on
   `tests/test_skill_render_aitask_pick.sh` — Test 1 (per-profile golden), 1b
   (agent invariance), 2 (profile-conditional sanity: `--gate`/skill_name text
   present in all; if no profile branch divergence exists, assert the invariant
   text), 3 (no Jinja leak), 3b (no runtime profile-resolution tokens), 4
   (cross-agent `task-workflow` ref rewrite via walk-write), 5 (stub markers:
   resolver `resume`, render call, Read path, per-agent literals/paths).

5. **Website (incremental-docs rule):**
   `website/content/docs/skills/aitask-resume.md` modeled on
   `aitask-pickrem.md` (single file): what it is (programmatic re-entry front),
   invocation, the 3-state resume mapping, the `--gate` current-state note, that
   it shares the t635_5 engine. Add one row to the **Task Implementation** table
   in `website/content/docs/skills/_index.md` (hand-curated list). Current-state
   only; the comprehensive Gates sweep is t635_18.

### Generation / verification commands (during implementation)

- Render goldens (3 profiles, claude) with the
  `skill_authoring_conventions.md` "Regenerate goldens" loop into
  `tests/golden/skills/aitask-resume/`.
- `./.aitask-scripts/aitask_skill_verify.sh` (auto-discovers the new `.j2`;
  checks all 3 stub surfaces render + closure walks; the new skill does NOT
  declare `prerender_for_headless`, so no committed-prerender check applies).

## Behavioral verification — autonomous MV follow-up + ephemeral gate fixtures

The render test (deliverable 4) proves the **template** is correct; it cannot
prove the skill **routes** correctly at each resume stage (that runs through a
live `task-workflow` hand-off). To cover that, create a **standalone
manual-verification task** (`issue_type: manual_verification`) at **Step 8c**
(the `manual-verification-followup.md` path, accepted instead of declined),
designed to run in **autonomous** auto-verification mode
(`auto-verification.md` §2a). Its checklist drives the real skill against
**ephemeral gate fixtures it builds and tears down itself**:

- **Setup (per checklist run):** create 3 throwaway tasks (no commit) via
  `aitask_create.sh --batch`, set each to `status: Implementing`
  (`aitask_update.sh --batch <id> --status Implementing`), and artificially
  populate the `## Gate Runs` ledger with `aitask_gate.sh append` to land each
  resume stage:
  - **PLAN** — no gate runs appended (empty ledger).
  - **IMPLEMENT** — `append <id> plan_approved pass`.
  - **POSTIMPL** — `append … plan_approved pass` + `append … review_approved pass`.
- **Checklist items (each marked pass/defer per §2a):**
  1. **Derivation:** `aitask_gate.sh resume-point <fixture>` returns the
     expected stage for each of the three.
  2. **Skill routing:** invoke `/aitask-resume <fixture>` (or
     `ait skillrun resume`) for each; assert it surfaces the correct stage
     banner and reaches the matching `task-workflow` step (Check 5 → PLAN
     plans / IMPLEMENT → Step 7 impl body / POSTIMPL → Step 9). **Observe the
     route, do not complete destructive steps** — for POSTIMPL, assert it
     reaches Step 9 and stops at the NON-SKIPPABLE merge approval (correct
     autonomous behavior), then abort the fixture.
  3. **`--gate` degradation:** `/aitask-resume <fixture> --gate review_approved`
     reports the gate's ledger state and runs **no** verifier.
  4. **Not-in-flight advisory:** a `status: Ready` fixture → resume-point
     `PLAN`, skill advises "behaves like a fresh `/aitask-pick`".
- **Teardown:** unlock (`aitask_lock.sh --unlock`) and delete every fixture;
  confirm `git status` is clean (fixtures were never committed). Mark items
  `defer` (not `fail`) only if genuinely blocked, per §2a.

The MV task definition (authored at Step 8c) carries this full checklist and an
explicit "run in autonomous mode" note so a later `/aitask-pick <mv-id>` offers
and runs the autonomous strategy. It is the live counterpart to the static
`test_gate_reentry.sh` (engine) and `test_skill_render_aitask_resume.sh`
(template) tests.

## What this task explicitly does NOT touch

- **No edits to `task-workflow/` `SKILL.md` / `crash-recovery.md` / goldens** —
  the resume engine (Check 5 + Re-entry Routing) is consumed as-is from t635_5.
  Therefore no task-workflow golden regeneration and no `rerender remote`.
- No gate-running engine (`aitask-run-gates`, verifier contract) — that is
  t635_11; `--gate` is accepted for invocation-contract compatibility only.
- No `gates:` frontmatter population (t635_14), no TUI wiring (t635_9/_10), no
  committed headless prerenders.

## Risk

### Code-health risk: low
- Purely **additive** (new skill files + one `_index.md` table row + one website
  page); no edits to shared logic. Established `aitask-pick` pattern; render/verify
  infra auto-discovers the new `.j2`. Goldens + a dedicated render test guard
  template drift · severity: low · → mitigation: in-task (`aitask_skill_verify.sh`,
  new `test_skill_render_aitask_resume.sh`, all green before commit).

### Goal-achievement risk: medium
- The **`--gate` pre-orchestrator semantics** (report-state-not-run) and the
  **"not in-flight → advise + proceed"** behavior are design judgments; if they
  diverge from intent the skill under/over-does its job · severity: medium ·
  → mitigation: behavior is conservative (hands to the proven task-workflow
  engine; `--gate` never forks an engine); **directly validated** by the
  autonomous manual-verification follow-up task created at **Step 8c** (see
  "Behavioral verification" above), which drives `/aitask-resume` against
  ephemeral PLAN/IMPLEMENT/POSTIMPL gate fixtures and asserts each routes to the
  correct `task-workflow` step.
- Resume-handoff context-var correctness (esp. `is_child`/`parent_*`) · severity:
  low · → mitigation: copied verbatim from the audited `aitask-pick` Step 3 table.

### Planned mitigations
None — risks are bounded and covered in-task by the render test/goldens/verify
and the Step 8c manual-verification offer. No before/after mitigation tasks.

## Cross-agent follow-ups (CLAUDE.md rule)

Claude Code is the source of truth. The Codex/OpenCode **stubs are authored in
this task** (thin per-agent dispatch, required for the skill to exist on those
agents). The rendered variants are produced by `aitask_skill_render.sh` on
demand. No further agent-specific port task is needed unless a reviewer wants
the OpenCode/Codex stubs split out — flag at review if so.

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` → 0 failures (renders all 3 stub
   surfaces against every profile; closure walk resolves the `task-workflow`
   reference).
2. `bash tests/test_skill_render_aitask_resume.sh` → all green (goldens, agent
   invariance, no Jinja leak, no runtime profile-resolution tokens, ref rewrite,
   stub markers).
3. Manual smoke (read-only): `ait skillrun resume --profile fast --dry-run -- 635_6`
   prints the expected launch command; `./.aitask-scripts/aitask_gate.sh
   resume-point 635_6` → `PLAN` (empty ledger) confirming the surfaced advice path.
4. Regression: `bash tests/test_skill_render_aitask_pick.sh`,
   `bash tests/test_gate_reentry.sh` (engine untouched, must stay green).
5. Hugo: `cd website && hugo build --gc --minify` (or serve) — new skill page +
   `_index.md` row render without error.
6. **Behavioral (deferred to the MV follow-up):** at Step 8c, create the
   standalone autonomous manual-verification task described in "Behavioral
   verification". It is run later via `/aitask-pick <mv-id>` (autonomous
   strategy) — that run is what confirms live routing at each resume stage; it
   is not executed within this task.

## Step 9 reference

Post-implementation cleanup/archival follow the shared **Step 9** flow (current
branch — `fast` profile; no worktree/merge). This child declares no `gates:`, so
its own archival is unaffected.
