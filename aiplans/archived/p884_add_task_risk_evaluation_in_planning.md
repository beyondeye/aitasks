---
Task: t884_add_task_risk_evaluation_in_planning.md
Base branch: main
plan_verified: []
---

# Plan: t884 — Add task risk evaluation in planning

## Context

When directing a coding agent, it is hard to know up front (a) whether a feature
will hurt code stability, quality, or maintainability, and (b) whether the
planned implementation will actually **achieve the user's requested goals**
(wrong approach, missed/misunderstood requirements, technical infeasibility,
incomplete coverage). t884 adds a structured **risk evaluation** at the end of
planning that assesses **both** dimensions, records **two independent** risk
levels on the task — `risk_code_health` and `risk_goal_achievement` (each
high/medium/low) — writes a `## Risk` section into the plan, and
lets the user spawn **risk-mitigation follow-up tasks** to run *before* and/or
*after* implementation. When a "before" mitigation lands, the original task's
plan is **force re-verified** on the next pick (the codebase changed under it).
The whole evaluation is **opt-in** via an execution-profile key, and it is
designed with a forward-compatible **seam to the gates framework (t635)** —
built standalone now, wrappable as a gate later.

This is a high-effort, multi-subsystem task; it will be split into child tasks.

### Locked design decisions (from user)
1. **Standalone now + gates seam** — do not couple to t635; document the seam.
2. **Read-time signal at pick** for force-reverify — original task stores linked
   mitigation IDs; planning Step 6.0 compares their `completed_at` vs the plan's
   last `plan_verified` timestamp; extend `aitask_plan_verified.sh` with
   `--force-verify`.
3. **Propose both before/after mitigations, user confirms** — mirror
   `upstream-followup.md` / `manual-verification-followup.md`.
4. **Two independent risk fields, not one aggregate (redesign 2026-06-01).** Risk
   is estimated and stored **separately** per dimension: `risk_code_health` and
   `risk_goal_achievement` (each high/medium/low). The single aggregate `risk`
   field that t884_1 shipped is **replaced** (no derived aggregate kept). The
   two-field frontmatter plumbing is its own foundation task **t884_9** (filed
   because t884_1 is already archived); t884_3 `depends` on it.
   `risk_mitigation_tasks` stays a single shared list.

### Verified facts that shape the design
- `completed_at` **is** written at archive (`aitask_archive.sh:145-147`) → the
  read-time signal can compare a mitigation's completion time. ✅
- `aitask_update.sh` exposes `--deps` which **replaces** the list (no additive
  flag) → "before"-mitigation wiring must read-modify-write the `depends:` list.
- `aitask_plan_verified.sh` is **already allowlisted** (runtime + seed + codex)
  → the new `--force-verify` flag needs **no** new permission touchpoints.
- A new frontmatter field touches create/update/ls/board; **scalar** fields are
  a fold no-op, but the new **list** field `risk_mitigation_tasks` needs explicit
  `aitask_fold_mark.sh` handling.

## Architecture

Three new frontmatter fields, one new profile key, two new closure procedures,
and one additive flag on an existing helper:

- **`risk_code_health`** + **`risk_goal_achievement`** (scalars, high/medium/low)
  — **two independent** levels, one per risk dimension (code-health and
  goal-achievement). They **replace** the single aggregate `risk` field. Mirror
  `priority`'s update/display plumbing (doubled). Display-only, **not** a sort
  dimension, **no** border color. The two-field plumbing lives in **t884_9**
  (foundation), which reworks t884_1's single-field surface.
- **`risk_mitigation_tasks`** (list of task IDs) — the linked "before"
  mitigations whose landing forces re-verify. Omitted by default; ignored on fold.
- **`risk_evaluation`** (bool profile key) — the **single** toggle that gates the
  whole feature: the eval step **and** the mitigation offer. **Absent ⇒ OFF.**
  Controlled via Jinja (see "How profiles gate the procedures" below); when on,
  the mitigation offer is always propose-and-confirm.
- **`risk-evaluation.md`** closure — design-in-planning (read-only) assigns
  **both** levels + writes the `## Risk` plan section (two subsections, each
  carrying its own level); the `risk_code_health` / `risk_goal_achievement` field
  writes happen **post-approval at Step 7** (plan mode is read-only).
- **`risk-mitigation-followup.md`** closure — propose-and-confirm, gated by the
  `risk_evaluation` profile key (Jinja); "before" creation + `depends`-wiring at
  **Step 7**; "after" creation at a new **Step 8d**.
- **`--force-verify`** on `aitask_plan_verified.sh decide` — pure-additive; a new
  **Step 6.0a** computes the read-time signal and passes the flag.

### Design/creation split (planning runs read-only)
Following `aidocs/planning_conventions.md` and the cross-repo reference pattern
(`planning-cross-repo.md` design + `cross-repo-child-assignment.md` creation):
the eval **decides** during planning and records to the `## Risk` section; all
**mutations** (writing `risk_code_health` / `risk_goal_achievement`, creating
mitigations, wiring `depends`, populating `risk_mitigation_tasks`) run after
approval at Step 7, except the
post-implementation "after" follow-ups which run at Step 8d.

### How profiles gate the procedures (mechanism)
Profile keys are **not** read at runtime — `aitask_skill_render.sh` evaluates the
active profile's YAML against `{% if profile.<key> %}` Jinja conditionals in the
`.md.j2` authoring sources **and** the closure `.md` files, baking the chosen
branch into the per-profile rendered variant. So `risk_evaluation` gates the risk
procedures via `{% if profile.risk_evaluation %}` wrapped around the **dispatch
sites**: the eval step in `planning.md` §6.1 and the Step 7 / Step 8d mitigation
creation in `SKILL.md`. Absent/false ⇒ the rendered variant omits the steps
entirely (no footprint when off). This is the same pattern as `create_worktree`,
`plan_preference`, `manual_verification_followup_mode`, etc. Editing these `.j2`/
closure sources **requires regenerating goldens + running `aitask_skill_verify.sh`
in the same commit** (gotcha #2).

## Child task decomposition

| Child | Scope | Depends |
|-------|-------|---------|
| **t884_1** | *(landed; single-`risk` plumbing superseded by t884_9.)* Frontmatter plumbing for **`risk`** (scalar) + **`risk_mitigation_tasks`** (list). Shipped the single aggregate `risk` field across `aitask_update.sh`/`aitask_ls.sh`/`aitask_board.py`/`aitask_fold_mark.sh` (create left untouched). The single `risk` field is **replaced by the two-field design in t884_9**; `risk_mitigation_tasks` carries forward unchanged. | none |
| **t884_9** | **Two-field risk frontmatter plumbing (foundation; replaces aggregate `risk`).** Rework t884_1's single-`risk` surface into **two** independent scalar fields `risk_code_health` + `risk_goal_achievement` (each high/medium/low) **everywhere**: `aitask_update.sh` (two flags `--risk-code-health`/`--risk-goal-achievement`, two BATCH/CURRENT vars, validation, two interactive entries, two conditional `write_task_file` emits), `aitask_ls.sh` (two display values, no score), `aitask_board.py` (two snapshot keys/ReadOnlyFields/CycleFields), `aitask_fold_mark.sh` (scalars = no fold change). `aitask_create.sh` untouched. Both **omitted by default**. Rework `tests/test_update_risk.sh` + `tests/test_fold_risk_mitigation_drop.sh`. | none |
| **t884_2** | **`risk_evaluation` profile key — data layer only.** Schema row in `profiles.md`; `profile_editor.py` `PROFILE_SCHEMA`/`PROFILE_FIELD_INFO`/`PROFILE_FIELD_GROUPS` (auto-discovered by the settings TUI); seed + runtime profile YAMLs. **Do NOT default it true anywhere** (no Jinja here). | none |
| **t884_3** | **Risk-evaluation step + `## Risk` plan section + Step 7 two-field write.** New `risk-evaluation.md` closure: design part at end of `planning.md` §6.1, gated by `{% if profile.risk_evaluation is defined and profile.risk_evaluation %}` (see gotcha #3 — strict-mode requires the `is defined` guard). The eval assesses **two dimensions** — (A) **code-health** (stability/quality/maintainability) and (B) **goal-achievement** (will the plan deliver the user's requested goals: approach soundness, requirement coverage, feasibility) — and assigns **two independent** levels (one per dimension). Define the `## Risk` section format as two subsections, each headed by its own level (per-risk: description, severity, → mitigation link). Thread `risk_level_code_health`/`risk_level_goal_achievement`/`risk_mitigations_planned`; post-approval Step 7 hook writes **both** fields via `--risk-code-health`/`--risk-goal-achievement`. Include the **gates forward-compat seam** comment (maps eval → a future gate, references t635). | 884_2, 884_9 |
| **t884_4** | **Risk-mitigation procedure (before + after).** New `risk-mitigation-followup.md`: design-in-planning proposes before/after (offer **gated by `risk_evaluation`** via Jinja; structurally mirrors the propose-confirm shape of `manual-verification-followup.md`); Step 7 creates "before" mitigations, adds blocking edge by **read-modify-write of `depends:`** (since `--deps` replaces), populates `risk_mitigation_tasks`; new **Step 8d** creates "after" follow-ups (like `upstream-followup.md`). "Before" mitigations are **independent tasks the original depends on — NOT children** (do not touch `update_parent_children_to_implement`). Mitigations may target **either** risk dimension (e.g. a "before" spike/prototype to de-risk a goal-achievement concern; an "after" refactor/test to de-risk a code-health concern). | 884_3 |
| **t884_5** | **Force-reverify mechanism.** Add `--force-verify` to `aitask_plan_verified.sh decide` (pure-additive; keep the 8-line output **byte-stable** when omitted). New **Step 6.0a**: read `risk_mitigation_tasks`, compare each mitigation's `completed_at` (from its archived file) vs the plan's last `plan_verified`; if any landed later, pass `--force-verify`. **No-op when the field is absent.** No new script ⇒ no allowlist task. | 884_4, 884_9 |
| **t884_6** | **Website docs** (first-class, before manual-verify): `website/content/docs/` for the **two** risk fields on `ait board`, `ait update` risk, the planning risk workflow, the `risk_evaluation` profile key. **Not** gated on t884_5 (force-reverify is invisible plumbing → one-liner only). | 884_3, 884_4, 884_9 |
| **t884_7** | **Retrospective + follow-ups.** Document outcomes; file standalone aitasks to **port skill changes to Codex** (`.agents/skills`, `.codex`) and **OpenCode** (`.opencode`); file the **"extract priority+risk enums to single source"** refactor follow-up; file the **gates-integration** follow-up against t635. | all |
| **t884_8** | **Manual-verification sibling** (auto-offered after child creation): board risk widgets (both fields), settings `risk_evaluation` key, live planning risk-eval prompt + `## Risk` rendering, mitigation propose/confirm + before-blocking + force-reverify behavior. | UI-bearing children |

### Dependency graph
```
884_9 ─┬─> 884_3 ─> 884_4 ─> 884_5    (884_9 = two-field plumbing, replaces 884_1's risk field)
884_2 ─┘     │         │
884_9 ───────┼─────────┘   (884_5 also needs the 884_9 fields)
             └─> 884_6 <── 884_4
all(2,9,3..6) ─> 884_7    all UI ─> 884_8
```
(t884_1 already landed; its single-`risk` field is superseded by t884_9.)

## Cross-cutting decisions & blast-radius (feature OFF ⇒ zero behavior change)

| Item | Safest default |
|------|----------------|
| `risk_code_health` / `risk_goal_achievement` fields | **Omit by default**; read via `.get(<field>, None)`, render nothing when absent. Never backfill existing tasks. |
| `risk_mitigation_tasks` | **Omit by default**; absent = empty list everywhere; `aitask_fold_mark.sh` ignores it (not foldable). |
| `risk_evaluation` profile key | **Absent ⇒ disabled.** ⚠️ Under strict-mode minijinja a bare `{% if profile.risk_evaluation %}` **errors** on the absent key — the gate MUST be `{% if profile.risk_evaluation is defined and profile.risk_evaluation %}` (empirically verified; see gotcha #3). Not seeded true in any profile. |
| `--force-verify` flag | **Pure additive**; `decide` without it returns the identical 8 `KEY:value` lines → existing `planning.md` parser untouched. |
| Step 6.0a / Step 8d | **No-ops when preconditions absent**; inserted as **suffixes** — never renumber existing 6.0/8b/8c. |

### Single-source-of-truth for the risk enum — decision
**Mirror `priority`'s existing duplication** (hardcode `high\|medium\|low` at the
relevant sites). Rationale: adding the risk fields does not edit the `priority`
list, so the "refactor duplicates" convention's literal trigger isn't met; a
shared constant for the risk fields *alone* would be a new cross-language drift
surface that `priority` lacks (more surprising, not less). Instead, t884_7 **files
a named follow-up** to extract all the high/medium/low enums (priority + the two
risk fields) to a single source — respecting the convention by naming the refactor
rather than burying it, without forcing a risky multi-site refactor into a feature task.
*(Trade-off / rejected alternatives recorded here per the user's planning ethos.)*

> **Naming note:** the task wrote "med"; this plan uses **`medium`** for
> consistency with `priority`. Flag in Revise if you prefer `med`.

## Gotchas every child must honor
1. **`risk_mitigation_tasks` is a list** → explicit `aitask_fold_mark.sh` handling (not the scalar no-op).
2. **Goldens + `aitask_skill_verify.sh` in the SAME commit** for every child editing `planning.md`/`SKILL.md`/closures — explicit acceptance line per child (most-forgotten step).
3. **One profile toggle, Jinja-gated:** the single `risk_evaluation` key gates both the eval step and the mitigation offer at the dispatch sites (NOT runtime reads). ⚠️ The renderer uses `undefined_behavior="strict"`, so the gate MUST be `{% if profile.risk_evaluation is defined and profile.risk_evaluation %}` (a bare `{% if profile.risk_evaluation %}` **errors** on the absent key — empirically verified; mirror the `remote_drift_check` guard). Wrap with `{%- … %}`/`{%- endif %}` (lstrip) for zero-footprint when off. Truly non-skippable gates remain only Step 8 review and Step 9 merge — risk procedures are opt-in, not load-bearing.
4. **"Before" mitigations = dependencies, not children**; `--deps` replaces → read-modify-write.
5. **No step renumbering** — 6.0a / 8d are suffixes; keep existing parsers + goldens stable.

## Critical files
- `.claude/skills/task-workflow/planning.md` — §6.0 (add 6.0a), §6.1 end (eval step), Checkpoint
- `.claude/skills/task-workflow/SKILL.md` — Step 7 (post-approval creation hook), new Step 8d
- `.claude/skills/task-workflow/profiles.md` — schema row
- `.aitask-scripts/aitask_plan_verified.sh` — `--force-verify`
- `.aitask-scripts/lib/profile_editor.py` — SCHEMA/INFO/GROUPS
- `.aitask-scripts/aitask_create.sh`, `aitask_update.sh`, `aitask_ls.sh`, `aitask_fold_mark.sh`
- `.aitask-scripts/board/aitask_board.py`
- New closures: `.claude/skills/task-workflow/risk-evaluation.md`, `risk-mitigation-followup.md`

## Verification (per child + aggregate)
- **t884_9:** `ait update --batch <id> --risk-code-health high --risk-goal-achievement medium`, confirm board shows both fields, fold a task and confirm primary's two risk fields preserved + `risk_mitigation_tasks` dropped; created task carries neither field. `bash tests/test_update_risk.sh && bash tests/test_fold_risk_mitigation_drop.sh`.
- **t884_2:** open `ait settings` → profiles tab, confirm `risk_evaluation` key renders/saves; YAML round-trips.
- **t884_3/4/5:** regenerate goldens, `./.aitask-scripts/aitask_skill_verify.sh`; dry-run `ait skillrun pick --profile <p> --dry-run`; unit-test `aitask_plan_verified.sh decide` with/without `--force-verify` (assert 8-line output unchanged when omitted).
- **shellcheck** `.aitask-scripts/aitask_*.sh`; **Hugo build** for t884_6.
- **t884_8:** the manual-verification checklist covers the live TUI + planning flows.

## Post-implementation
Standard Step 9 (archival/merge per profile). t884_7 is the trailing retrospective
that files the cross-agent port tasks, the enum-refactor follow-up, and the
gates-integration (t635) follow-up.
