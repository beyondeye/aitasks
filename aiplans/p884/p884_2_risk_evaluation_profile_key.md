---
Task: t884_2_risk_evaluation_profile_key.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_3_risk_evaluation_planning_step.md, aitasks/t884/t884_4_risk_mitigation_followup_procedure.md, aitasks/t884/t884_5_force_reverify_on_mitigation_landed.md, aitasks/t884/t884_6_risk_evaluation_website_docs.md, aitasks/t884/t884_7_risk_eval_retrospective_and_ports.md, aitasks/t884/t884_8_manual_verification_risk_evaluation.md
Archived Sibling Plans: aiplans/archived/p884/p884_1_risk_frontmatter_field_plumbing.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 12:12
---

# Plan: t884_2 — `risk_evaluation` execution-profile key (data layer)

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Existing plan verified against current codebase (2026-06-01): all file paths,
> line anchors, and the `("bool", None)` schema pattern still valid; no `risk`
> references exist yet in `profile_editor.py` or `profiles.md`.

## Context

t884 adds a "risk evaluation" feature to the planning workflow (assess code-health
/ goal-achievement risk at end of planning, then optionally spawn mitigation
follow-up tasks). The whole feature must be gated by a **single** opt-in
execution-profile toggle `risk_evaluation` (bool) so existing users see zero
change until they enable it. This child is the **data layer only**: register the
key in the profile schema, settings-editor metadata, and the profiles.md schema
doc. The Jinja that actually branches on `{% if profile.risk_evaluation %}` lives
in siblings t884_3 (eval step) and t884_4 (mitigation offer) — **not here**.

**Blast radius: absent ⇒ feature OFF.** `{% if profile.risk_evaluation %}` is
Jinja-falsy on an undefined key, so do NOT seed `risk_evaluation: true` (or the key
at all) into any profile YAML. Existing users are unaffected.

## Changes

### 1. `.aitask-scripts/lib/profile_editor.py` (the three-structure triple)

The Settings TUI auto-discovers any new key from these three structures — no other
editor code change is needed (verified: `compose_profile_fields` / group rendering
at line ~520 iterates `PROFILE_FIELD_GROUPS`).

- **`PROFILE_SCHEMA`** (dict at line 46): add `"risk_evaluation": ("bool", None),`
  placed after `"post_plan_action_for_child"` (line 58), grouping it with the
  planning keys.
- **`PROFILE_FIELD_INFO`** (dict at line 99): add a `(short, long)` tuple. Short:
  "Enable risk evaluation during planning". Long: explains it assesses code-health
  + goal-achievement risk at the end of planning, gates both the risk-evaluation
  step and the mitigation follow-up offer, is opt-in (unset ⇒ disabled). Follow the
  multi-line string style of `qa_run_tests` / `manual_verification_mode`.
- **`PROFILE_FIELD_GROUPS`** (list at line 300): append `"risk_evaluation"` to the
  end of the existing **"Planning"** group's key list (lines 304–311).

### 2. `.claude/skills/task-workflow/profiles.md` (schema-table row)

Add one row to the "Profile Schema Reference" table (after the
`post_plan_action_for_child` row, line 34): 

```
| `risk_evaluation` | bool | no | `true` = run risk evaluation at end of planning and offer mitigation follow-ups; omit or `false` = disabled | Step 6.1 (planning) |
```

Keep the Step reference generic to planning — siblings t884_3/t884_4 own the exact
consumption sites; this row documents the toggle, not their internals.

### 3. Profile YAMLs — NO CHANGE

Leave `aitasks/metadata/profiles/{default,fast,remote}.yaml` and
`seed/profiles/{default,fast,remote}.yaml` untouched. Absent = disabled everywhere.

## Out of scope (sibling tasks)

- No Jinja `{% if profile.risk_evaluation %}` gates here (t884_3 / t884_4).
- No goldens regeneration here — this task edits no `.md.j2` or closure procedure,
  so no `tests/golden/skills` or `tests/golden/procs` files change.

## Verification

- Syntax: `python -c "import ast; ast.parse(open('.aitask-scripts/lib/profile_editor.py').read())"`.
- `bash tests/test_scan_profiles.sh` (existing profile suite — confirms no regression;
  it tests the scanner, not the schema, but guards the surrounding plumbing).
- Manual (deferred to the t884_8 manual-verification sibling, not blocking here):
  `ait settings` → Profiles tab → confirm `risk_evaluation` renders under "Planning",
  cycles true/false/(unset), saves to YAML, and round-trips on reload.
- Confirm no `risk_evaluation:` line was added to any profile YAML
  (`grep -rn risk_evaluation aitasks/metadata/profiles seed/profiles` → no matches).

## Step 9 (Post-Implementation)

Standard child-task archival: commit code changes (`enhancement: ... (t884_2)`),
update + commit the plan file via `./ait git`, then `aitask_archive.sh 884_2`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, plus one extra
  consistency step the plan under-specified.
  - `.aitask-scripts/lib/profile_editor.py`: added `"risk_evaluation": ("bool",
    None)` to `PROFILE_SCHEMA` (after `post_plan_action_for_child`), a
    `(short, long)` help tuple to `PROFILE_FIELD_INFO`, and `"risk_evaluation"`
    to the **"Planning"** group in `PROFILE_FIELD_GROUPS`. The settings TUI
    auto-discovers from these three structures — no other editor code touched.
  - `.claude/skills/task-workflow/profiles.md`: added the schema-table row
    (`| risk_evaluation | bool | no | … | Step 6.1 (planning) |`).
  - **Headless prerender propagation (extra step):** `profiles.md` is part of
    the committed headless-prerender closure for `aitask-pickrem`/`aitask-pickweb`
    under the `remote` profile. Regenerated all three committed copies so they
    carry the new row: `.claude/skills/task-workflow-remote-/profiles.md`,
    `.agents/skills/task-workflow-remote-codex-/profiles.md`,
    `.opencode/skills/task-workflow-remote-/profiles.md` (`aitask_skill_render.sh
    aitask-pickrem/pickweb --profile remote --agent {claude,codex,opencode}
    --force`). Each diff was exactly the single `risk_evaluation` row (+1 line),
    zero unrelated bleed.
- **Deviations from plan:** The plan said "no goldens regeneration / no closure
  edits". That held for `tests/golden/`, but it overlooked that the **committed
  headless prerenders** bundle `profiles.md` verbatim and therefore needed
  regeneration. Caught and handled in this task. Profile YAMLs left untouched as
  planned (absent ⇒ feature OFF; verified `grep risk_evaluation` over
  `aitasks/metadata/profiles` + `seed/profiles` returns nothing).
- **Issues encountered:** During verification a transient working-tree state made
  the `task-workflow-remote-` prerenders briefly *appear* stale w.r.t. the
  cross-repo feature (t832_5). On clean re-inspection this was a false alarm: the
  committed prerenders already contain the cross-repo content and
  `aitask_skill_verify.sh` passes. No stale-prerender defect exists; no follow-up
  bug task warranted.
- **Key decisions:** Placed `risk_evaluation` in the "Planning" group (it gates a
  planning-time step), kept the profiles.md Step reference generic to "Step 6.1
  (planning)" since t884_3/t884_4 own the exact consumption sites.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - t884_3 / t884_4 consume the key via `{% if profile.risk_evaluation %}` at
    their dispatch sites and MUST regenerate goldens (they edit `.md.j2` / closure
    procedures, unlike this task).
  - The key is **opt-in**: undefined ⇒ Jinja-falsy ⇒ feature OFF. Do not seed it
    `true` in any profile YAML.
  - `aitask_skill_verify.sh` does NOT deep-compare `profiles.md` content between
    source and the committed headless prerenders, so it will not flag a missing
    row there — propagate manually (as done here) whenever `profiles.md` changes.
