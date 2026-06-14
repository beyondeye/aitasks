---
Task: t635_2_task_workflow_checkpoint_recording.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_10_monitor_gate_status_column.md, aitasks/t635/t635_11_orchestrator_verifier_contract.md, aitasks/t635/t635_12_build_test_machine_gates.md, aitasks/t635/t635_13_risk_evaluation_gate_integration.md, aitasks/t635/t635_14_profile_gate_declaration_unification.md, aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_20_stats_multistage_completion.md, aitasks/t635/t635_21_gate_ledger_merge_safety.md, aitasks/t635/t635_3_dependency_unblock_semantics.md, aitasks/t635/t635_4_gate_guarded_archival.md, aitasks/t635/t635_5_ledger_driven_reentry.md, aitasks/t635/t635_6_aitask_resume_skill.md, aitasks/t635/t635_7_gate_aware_aitask_pick.md, aitasks/t635/t635_8_python_gate_ledger_parser.md, aitasks/t635/t635_9_board_inflight_action_view.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_gate_ledger_substrate.md
Base branch: main
plan_verified: []
---

# t635_2 — task-workflow checkpoint recording (gate-run blocks)

## Context

Phase 1 of the gate-framework roadmap (`aidocs/gates/integration-roadmap.md`,
decisions **D1 ledger-first / D2 hybrid-by-mode**). The ledger substrate landed
in t635_1 (`./.aitask-scripts/aitask_gate.sh append`, `gates.yaml` registry with
the 5 checkpoint gates already seeded, `lib/gate_ledger.py`). This task makes
**task-workflow start *recording* its existing approval checkpoints as gate-run
blocks** in the task file — purely additive. The interactive prompts
(ExitPlanMode / AskUserQuestion) are **untouched**; in attended mode the prompt
outcome IS the gate signal (D2 seed). Recording the ledger is what later makes
Phase-2 re-entry (t635_5) possible.

The 5 checkpoints (gates already in `aitasks/metadata/gates.yaml`):
`plan_approved`, `risk_evaluated`, `build_verified`, `review_approved`,
`merge_approved`.

## Key design decisions (rationale + rejected alternative)

1. **New profile key `record_gates` — opt-in, default OFF** *(decided with
   user; roadmap "open problem 2")*. User-facing name chosen over the jargony
   `gate_ledger`; pairs with the coming family `default_gates` (t635_14) and
   `auto_complete_on_all_gates_pass` (t635_17). Jinja guard mirrors
   `risk_evaluation` polarity exactly: `{% if profile.record_gates is defined
   and profile.record_gates %}`. Ship `record_gates: true` in **fast** (+ seed).
   Honors the framework doc's "no `gates:` field = behaves exactly like today".
   *Rejected:* default-ON / opt-out — bends the doc, adds noise+commits to every
   task, inverts polarity vs. `risk_evaluation` (footgun).

2. **Recording logic lives in a NEW whitelisted script
   `aitask_gate_record.sh`** *(user request)* — not inlined as multi-command
   bash in the skill markdown. The skill procedure becomes a one-line call.
   The script encapsulates: `aitask_gate.sh append` → path-scoped `task_git
   add`/commit → best-effort `task_push` (reusing `task_utils.sh` helpers, not
   `./ait git`). Fully best-effort (always exits 0) so a recording failure never
   blocks the workflow. Has its own unit test.
   *Rejected:* inlining append+commit+push in `gate-recording.md` (un-testable,
   duplicated bash in a rendered closure).

3. **`remote` profile deferred to t635_17.** t635_2 is the **attended-mode** D2
   seed; the headless/autonomous lane is t635_17's scope. `record_gates` is
   added to **fast only**, not `remote.yaml`. The committed
   `task-workflow-remote-` prerender stays byte-identical (key absent → false
   branch); `aitask_skill_verify.sh` confirms no drift.

4. **Persist each recording (path-scoped commit + best-effort push)** *(your
   durability requirement: gate state visible to all PCs)*. Done inside
   `aitask_gate_record.sh`, staging only the one task file (aligns with the
   "stage specific paths only" concurrent-writers rule).

5. **Settings-TUI registration is IN-SCOPE here** *(answering your question — no
   sibling needed)*. The Settings TUI is data-driven (`profile_editor.py`
   `PROFILE_SCHEMA` / `PROFILE_FIELD_INFO` / `PROFILE_FIELD_GROUPS`); registering
   a key is ~3 dict entries, exactly as `risk_evaluation` is registered. I add a
   new **"Gates"** field group now so the future family has a home. Future keys
   (`default_gates`, `auto_complete_on_all_gates_pass`) register themselves when
   they land — coordination notes added to t635_14 / t635_17.

6. **Multi-PC sync — safe for t635_2; deeper gap → NEW sibling t635_21**
   *(decided with user)*. A task is *locked* through its workflow, so only the
   lock-holder appends its gate blocks; the gate section is **append-only at
   EOF**, so `task_push` (auto-pull-`--rebase`, 3 attempts) + `aitask_sync.sh` +
   `aitask_merge.py` replay it cleanly over other-file changes. The real gap —
   two PCs appending to the *same* `## Gate Runs` concurrently — only bites from
   **t635_15** (cross-PC gate passing) and is owned by no sibling
   (`aitask_merge.py merge_body()` has no gate-section special-casing; no
   `.gitattributes`). → create **t635_21**.

## Deliverables

### A. New recording script (NEW) + whitelist + test
- **`.aitask-scripts/aitask_gate_record.sh`** (new). Interface:
  `aitask_gate_record.sh <task-id> <gate> <status> [k=v …]`. Sources
  `terminal_compat.sh` + `task_utils.sh` (no new sourced lib → no test-scaffold
  change). Body (all best-effort, exit 0):
  1. `"$SCRIPT_DIR/aitask_gate.sh" append <task-id> <gate> <status> [k=v…]`
  2. resolve file via `resolve_task_file`; `task_git add "$file"`;
     `task_git commit -m "ait: Record <gate> gate for t<task-id>"`; `task_push`.
  `--help`; unknown args error clearly.
- **Whitelist** at the same 5 touchpoints as `aitask_gate.sh`:
  `.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`.
- **`tests/test_gate_record.sh`** (new, self-contained): in a temp git repo,
  `aitask_gate_record.sh <id> plan_approved pass type=human` → assert the block
  landed in the task file, `aitask_gate.sh status` shows `plan_approved: pass`,
  and the change was committed (path-scoped); best-effort push no-ops cleanly
  with no remote.

### B. The thin recording procedure (NEW)
- **`.claude/skills/task-workflow/gate-recording.md`** (new, profile-invariant):
  "Execute `./.aitask-scripts/aitask_gate_record.sh <task_id> <gate> <status>
  [k=v…]`" with the per-site field conventions. One short procedure; the bash
  lives in the script.

### C. Recording call-sites (each wrapped in the `record_gates` Jinja guard with
the `{# ---------- record_gates ---------- #}` comment-convention markers)

| Gate | File / site | status, fields |
|------|-------------|----------------|
| `plan_approved` | `SKILL.md` Step 7 start (after ownership guard) — every "proceed to implementation" path | pass, type=human |
| `plan_approved` | `planning.md` Checkpoint → "Approve and stop here" branch (deferred-approval resume case) | pass, type=human, note=deferred |
| `risk_evaluated` | `SKILL.md` Step 7 — **nested inside** the existing `{% if profile.risk_evaluation %}` "Risk fields" block | pass, type=machine |
| `review_approved` | `SKILL.md` Step 8 "Commit changes" branch, after code+plan commits | pass, type=human |
| `build_verified` | `SKILL.md` Step 9 "Verify build" sub-step (inside runtime "If a separate branch was created") | pass/fail, type=machine, verifier=`<cmd>` |
| `merge_approved` | `SKILL.md` Step 9 after the NON-SKIPPABLE merge-approval → "Yes, proceed" | pass, type=human |

Add a **Gate Recording Procedure** bullet to SKILL.md's "### Procedures" list.
(For fast — current branch — `merge_approved`/`build_verified` render but are
runtime-gated by "If a separate branch was created"; they fire only for worktree
profiles. Correct: no merge without a branch.)

### D. Profile key wiring
- **`aitasks/metadata/profiles/fast.yaml`** + **`seed/profiles/fast.yaml`**: add
  `record_gates: true`.
- **`.aitask-scripts/lib/profile_editor.py`**: register `record_gates`:
  - `PROFILE_SCHEMA`: `"record_gates": ("bool", None)`
  - `PROFILE_FIELD_INFO`: short + detailed description
  - `PROFILE_FIELD_GROUPS`: new `("Gates", ["record_gates"])` group.
- `aitasks/metadata/gates.yaml` — **no change** (5 gates already seeded by
  t635_1). Verify only.

### E. Docs (current-state rule)
- **`.claude/skills/task-workflow/profiles.md`** — add a `record_gates` row to
  the Profile Schema Reference table (mirror `risk_evaluation`: "opt-in, off by
  default").
- **`website/content/docs/skills/aitask-pick/execution-profiles.md`** — add one
  `record_gates` row to its key table (already enumerates
  `risk_evaluation`/`create_worktree`). Comprehensive Gates docs stay t635_18.

### F. Tests + goldens (same commit as the template edits)
- **`tests/test_skill_render_task_workflow.sh`** — add `gate-recording.md` to
  `WRAPPED_FILES_INVARIANT`; add a Test-5-style synthetic `record_gates: true`
  profile block (recording references render when set; absent on `default`).
- **Regenerate** `tests/golden/procs/task-workflow/`:
  - changed: `SKILL-fast.md`, `planning-fast.md`.
  - unchanged (verify empty diff): `*-default.md`, `*-remote.md`.
  - new: `gate-recording-default.md` (+ invariance assertion).

### G. Roadmap + new sibling (post-approval, Step 7 — plan mode is read-only)
- **`aidocs/gates/integration-roadmap.md`**: mark "open problem 2" decided
  (opt-in chosen; key named `record_gates`); add new open-problem "Gate-ledger
  multi-PC merge safety (t635_21)"; add the `t635_21` row to the child table.
- **Create `aitasks/t635/t635_21_gate_ledger_merge_safety.md`** via the Batch
  Task Creation Procedure (`--parent 635`, `depends: [t635_1]`); scope =
  `merge=union` `.gitattributes` driver for the `## Gate Runs` region OR teach
  `aitask_merge.py` to union-merge append-only gate blocks + body-merge tests.
- **Wire blocking edge:** add `t635_21` to **t635_15**'s `depends:`.
- **Coordination notes** (bidirectional links, via `./ait git`): in **t635_14**
  ("register `default_gates` in `profile_editor.py` + Gates settings group; pick
  a user-facing name") and **t635_17** ("register
  `auto_complete_on_all_gates_pass` likewise"); reverse pointer in **t635_2**
  noting t635_21 spun off.

## Files NOT touched (scope guard)
No edits to `aitask_gate.sh`, `gate_ledger.py`, or `gates.yaml`; no
resume/archival logic (t635_5/t635_4); no website Gates concept/workflow pages
(t635_18).

## Risk

### Code-health risk: medium
- Editing shared `task-workflow/SKILL.md` + `planning.md` (rendered into every
  calling skill's closure × 4 agents × 3 profiles) risks Jinja regressions /
  golden churn affecting all task skills · severity: medium · → mitigation
  in-task: mirror the `risk_evaluation` guard precedent exactly; regenerate
  goldens; `test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh` green.
- New `aitask_gate_record.sh` is a thin best-effort wrapper over already-tested
  primitives (`aitask_gate.sh`, `task_git`/`task_push`) · severity: low ·
  → mitigation: `shellcheck`; `tests/test_gate_record.sh`; whitelist parity with
  `aitask_gate.sh` across all 5 touchpoints (verified by grep).
- `record_gates` is opt-in/default-off → zero change for profiles without it;
  default/remote goldens unchanged · severity: low.

### Goal-achievement risk: low
- Recordings must fire at the right points without altering the prompts
  (zero-behavior-change) · severity: low · → mitigation: additive one-line
  references wrapped in guards adjacent to existing approval points; Test 3
  asserts default AskUserQuestion blocks render verbatim.
- `record_gates` guard polarity must be opt-in · severity: low · → mitigation:
  `is defined and X`; default golden shows none (test asserts).

### Planned mitigations
None — risks bounded, mitigated in-task by render/golden/script tests.
(t635_21 is a forward feature-gap follow-up, not a risk-mitigation task.)

## Verification
1. `shellcheck .aitask-scripts/aitask_gate_record.sh`.
2. `bash tests/test_gate_record.sh` (append+commit happy path; no-remote push no-op).
3. `bash tests/test_skill_render_task_workflow.sh` — goldens + invariance +
   synthetic `record_gates` assertions green.
4. `./.aitask-scripts/aitask_skill_verify.sh` — renders/closure/stub-markers
   pass; `task-workflow-remote-` prerender un-drifted.
5. Render-diff: `*-default.md`/`*-remote.md` diffs empty; `SKILL-fast.md` /
   `planning-fast.md` diffs match intended recording adds.
6. Settings smoke: `record_gates` appears under a "Gates" group in
   `ait settings` Profiles tab and toggles true/false/(unset).
7. New sibling: `t635_21` created, in t635's `children_to_implement`,
   `t635_15.depends` includes `t635_21`, roadmap table updated; t635_14/t635_17
   coordination notes committed.

## Step 9 reference
Post-implementation cleanup, archival, and (if a branch was used) merge follow
the shared **Step 9 (Post-Implementation)** flow.

## Final Implementation Notes

- **Actual work done:** Added the opt-in `record_gates` execution-profile key
  (same polarity as `risk_evaluation`) and made task-workflow record its five
  approval checkpoints (`plan_approved`, `risk_evaluated`, `review_approved`,
  `build_verified`, `merge_approved`) as gate-run blocks. Recording is
  encapsulated in a new whitelisted helper `.aitask-scripts/aitask_gate_record.sh`
  (append via `aitask_gate.sh` → path-scoped `task_git` commit → best-effort
  `task_push`; always exits 0), invoked by a thin `gate-recording.md` procedure
  from six Jinja-gated call-sites in `SKILL.md` (Step 7 plan_approved +
  risk_evaluated[nested], Step 8 review_approved, Step 9 build_verified +
  merge_approved, Procedures list) and `planning.md` ("Approve and stop here"
  deferred plan_approved). Shipped `record_gates: true` on the `fast` profile
  (runtime + seed); registered the key in `profile_editor.py` (schema +
  field-info + new "Gates" settings group). Docs: `profiles.md` + website
  `aitask-pick/execution-profiles.md` rows. Tests: new `test_gate_record.sh`
  (13/13), render Test 6 (synthetic `record_gates`), regenerated goldens
  (`SKILL-fast`, `planning-fast`, new `gate-recording-default`), re-rendered the
  committed `task-workflow-remote-` prerenders. Roadmap "open problem 2" marked
  resolved; created sibling **t635_21** (multi-PC gate-merge safety) wired as a
  `depends:` blocker on t635_15, with bidirectional coordination notes in
  t635_2/t635_14/t635_17.

- **Deviations from plan:**
  - **Jinja style:** used the proven zero-footprint `{%- if ... %} / {%- endif %}`
    stripping style of the adjacent `risk_evaluation` block rather than the
    `{# ---------- #}` comment-convention markers named in the plan. Reason:
    that is the *exact* precedent in the same Step 7/8/9 region, and it
    guaranteed byte-identical `default`/`remote` renders (verified by empty
    golden diffs). Behaviour is identical; this is a cosmetic authoring choice.
  - **`remote` profile:** confirmed deferred to t635_17 (attended-mode scope);
    the `task-workflow-remote-` prerender changed only in `profiles.md` (the
    unconditional schema row), proving SKILL.md/planning.md emit nothing for
    `remote`.

- **Issues encountered:**
  - The runtime `.claude/settings.local.json` whitelist entry for
    `aitask_gate_record.sh` was blocked by the Claude Code self-modification
    guardrail (agent cannot widen its own live permissions). The other 4
    touchpoints (incl. the seed mirror that ships to new installs) succeeded.
    Left for the user to add manually:
    `"Bash(./.aitask-scripts/aitask_gate_record.sh:*)"`. No test enforces this
    (the skill whitelist-coverage tests audit only
    `aitask_skill_verify.sh`/`aitask_skill_render.sh`), so it is a one-time
    permission-prompt convenience, not a correctness gap.
  - `aitask_create.sh` has `--no-sibling-dep` but no `--depends`; set t635_21's
    `depends: [t635_1]` by editing the frontmatter after creation.

- **Key decisions:** (1) opt-in/default-off `record_gates` (preserves the
  framework doc's "no `gates:` = like today" contract; consistent polarity with
  `risk_evaluation`). (2) Recording encapsulated in a dedicated whitelisted
  script (testable; no multi-command bash inlined in a rendered closure). (3)
  Persist each recording with a path-scoped commit + best-effort push (cross-PC
  visibility; "stage specific paths only"). (4) Multi-PC concurrent-append merge
  safety is out of scope here (single-lane recording is safe under lock +
  append-only EOF + rebase) and routed to new sibling t635_21.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t635_5 (resume):** the ledger now carries `plan_approved` /
    `risk_evaluated` / `review_approved` / `merge_approved` / `build_verified`
    for `record_gates`-enabled tasks; "Approve and stop here" records
    `plan_approved` with `note=deferred` (the resume signal).
  - **t635_14 / t635_17:** register their new gate profile keys (`default_gates`,
    `auto_complete_on_all_gates_pass`) in `profile_editor.py` under the existing
    **"Gates"** `PROFILE_FIELD_GROUPS` entry, exactly as `record_gates` is
    registered (see their coordination notes).
  - **t635_21:** owns the multi-PC concurrent-append merge driver; blocks t635_15.
  - **Authoring pattern:** to gate a new task-workflow site by a profile key with
    zero render footprint, copy the `{%- if profile.<key> is defined and
    profile.<key> %}` / `{%- endif %}` wrap and regenerate goldens
    (`SKILL-fast`/`planning-fast`) + re-render committed `*-remote-` prerenders.
