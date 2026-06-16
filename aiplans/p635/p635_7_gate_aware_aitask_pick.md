---
Task: t635_7_gate_aware_aitask_pick.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_5_ledger_driven_reentry.md (landed), aitasks/t635/t635_6_aitask_resume_skill.md (landed)
Archived Sibling Plans: aiplans/archived/p635/p635_1_*.md … p635_6_aitask_resume_skill.md
Base branch: main
---

# t635_7 — Gate-aware aitask-pick

## Context

Phase 2 of the gate-framework roadmap (`aidocs/gates/integration-roadmap.md`,
decision **D8**): aitask-pick stays the single user-facing front door and
becomes **gate-aware** rather than growing a second "gates workflow" beside it.

Today `aitask-pick` lists only `Ready` tasks (`aitask_ls.sh` defaults to
`STATUS_FILTER="Ready"`, parents-only). A task left **in-flight** —
`status: Implementing` with a recorded `## Gate Runs` ledger because a prior
session deferred archival (t635_4), crashed, or spanned multiple days — is
therefore invisible in the pick list. The **resume engine already exists**
(t635_5, landed): `aitask_gate.sh resume-point`/`archive-ready`/`status`, plus
`task-workflow` Step 3 **Check 5** (sets `resume_point`, resumes from the first
unmet checkpoint) and **Check 4** (offers archival when all gates pass) and the
**Re-entry Routing** block at the end of Step 4. t635_6 (landed) added the
`aitask-resume` *programmatic* front over that engine.

This task adds the **user-facing pick-list surfacing**: in-flight tasks get
their own section in `aitask-pick`, showing derived gate/checkpoint state;
picking one routes through Step 3 — **consuming** the engine, never re-deriving
it. The board's existing `/aitask-pick <n>` agent launch gains re-entry for
free (`<n>` resolves → Step 3 Check 5 resumes), with no board change.

## Approach (one new capability + a profile-invariant skill section)

The only genuinely new code is **enumerating in-flight gated tasks across both
parents and children** — nothing does this today (`aitask_ls.sh -s Implementing`
lists parents only and ignores the ledger). Everything else is *routing into the
landed engine*.

### Deliverable 1 — `inflight` subcommand in `aitask_query_files.sh` (new)

`.aitask-scripts/aitask_query_files.sh` is the canonical "query task/plan file
locations" helper and is **already whitelisted**. Add a `cmd_inflight()`
subcommand — zero whitelist change, exactly the t635_5 precedent that added
`resume-point` to the already-whitelisted `aitask_gate.sh`.

Behavior (read-only, exits 0, structured output — matching the script's
contract):
- Scan active **parent** files `$TASK_DIR/t*_*.md` and active **child** files
  `$TASK_DIR/t*/t*_*.md` (skip archived — they live under `$ARCHIVED_DIR`).
- **Predicate** (matches the t635_4 coordination note exactly): frontmatter
  `status: Implementing` (via the sourced `read_task_status`) **AND** the file
  contains a `## Gate Runs` section (`grep -qE '^##[[:space:]]+Gate Runs'`).
- For each match, derive the id (`<N>` parent / `<N>_<M>` child from the
  filename) and enrich by delegating to the already-built deriver — call
  `"$SCRIPT_DIR/aitask_gate.sh" resume-point <id>` and `… archive-ready <id>`
  (do **not** re-implement the derivation — consume it).
- Emit one sorted line per task:
  `INFLIGHT:<id>|<path>|<resume_point>|<archive_status>`
  where `<resume_point>` ∈ `PLAN|IMPLEMENT|POSTIMPL` and `<archive_status>` ∈
  `NO_GATES|ALL_PASS|BLOCKED:<csv>`.
- Emit `NO_INFLIGHT` when none match.

Wire it into: the top-of-file usage block, `show_help` (Subcommands + Output
format sections), and the `main()` dispatch `case`.

### Deliverable 2 — `aitask-pick/SKILL.md.j2`: In-Flight pick section

Edit the **source of truth** `.claude/skills/aitask-pick/SKILL.md.j2`. The
addition is **profile-invariant prose** (no new `{% if %}` gate), so it renders
byte-identically into all 3 goldens — same low-churn strategy as t635_4 Check 4
/ t635_5 Check 5.

1. **New subsection `#### 2.0: In-Flight Tasks (resume candidates)` at the top
   of Step 2** (keeps the 2a/2b/2c/2d labels intact — minimal diff). It:
   - Runs `./.aitask-scripts/aitask_query_files.sh inflight`.
   - On `NO_INFLIGHT` → skip to 2a (normal Ready listing).
   - On `INFLIGHT:` lines → for each, read the task file and render a one-line
     derived-state summary from `<resume_point>`/`<archive_status>` (running
     `aitask_gate.sh status <id>` for the recorded-checkpoint detail, e.g.
     "3/4 — pending review"):
     - `ALL_PASS` → "all gates pass — ready to archive"
     - `POSTIMPL` → "reviewed — resume at merge / post-implementation"
     - `IMPLEMENT` → "plan approved — resume implementation"
     - `PLAN` → "in flight — resume (re-plan from recorded state)"
   - Presents an `AskUserQuestion` (header "Resume", distinct from Ready tasks),
     paginated like 2c if >3: one option per in-flight task + a final **"Pick a
     new (Ready) task instead"** option.
   - **Selection handling:** an in-flight task → set it as the working task,
     derive `is_child`/`parent_id` from the id, gather sibling context for a
     child (`sibling-context <parent>` + read parent), then **proceed to
     Step 3**. Step 3 Check 5 resumes (derives `resume_point` itself) and
     Check 4 offers archival on `ALL_PASS` — the skill sets **only task
     selection vars**, never `resume_point`/archival decisions. "Pick a new
     task instead" → proceed to 2a.
2. **Notes section:** add a bullet documenting (a) the in-flight section and the
   consumed Step-3 engine, and (b) that direct selection `/aitask-pick <n>` of
   an in-flight task already resumes via Step 3 Check 5 (board re-entry "for
   free") — **no Step 0b logic change** (the existing resolve→Step 3 path
   already surfaces the resume banner + reclaim confirmation).

This is profile-invariant; the per-agent `task-workflow` reference rewrite and
the Step 0b auto-confirm macro are unchanged.

### Deliverable 3 — Tests

- **New `tests/test_query_files_inflight.sh`** (self-contained; model on
  `test_gate_reentry.sh` fixture style — `export TASK_DIR` to a temp tree so
  both `aitask_query_files.sh` and the delegated `aitask_gate.sh` resolve into
  the fixture). Cases: parent Implementing + ledger (plan_approved pass →
  `IMPLEMENT`); child Implementing + ledger (plan_approved + review_approved
  pass → `POSTIMPL`); parent Implementing **without** ledger → **excluded**;
  `Ready` task **with** ledger → **excluded**; empty tree → `NO_INFLIGHT`;
  assert the `INFLIGHT:<id>|<path>|<rp>|<as>` shape and `archive_status`
  `NO_GATES` (no declared gates).
- **Extend `tests/test_skill_render_aitask_pick.sh`:** assert the in-flight
  section renders in **all 3 profiles** (the `inflight` call, the "2.0: In-Flight
  Tasks" heading, the "Pick a new (Ready) task instead" option). Existing Test 1b
  (agent invariance) and Test 2 (profile branches) must stay green — the new
  prose is invariant and does not touch the auto-confirm assertions.

### Deliverable 4 — Goldens + render verification (same commit)

- Regenerate the 3 tracked goldens
  `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md` via
  `python .aitask-scripts/lib/skill_template.py <template> <profile.yaml> claude`.
- `./.aitask-scripts/aitask_skill_verify.sh` green.
- **No `rerender remote`** — aitask-pick declares no `prerender_for_headless`
  (verified); the rendered `-<profile>-` dirs are not git-tracked (regenerated
  on demand). Other proc goldens diff empty (the `.j2` edit is local to pick).

### Deliverable 5 — Coordination notes (post-approval, Final Implementation Notes)

No new `depends:` edges (deps `[t635_5, t635_6]` already landed). Notes for
siblings (with bidirectional `./ait git` links per the coordination convention):
- **t635_8 (Python gate-ledger parser):** the bash `inflight` subcommand is the
  **skill-facing** enumerator; the Python parser is the **TUI-facing** shared
  derivation. Keep them separate — do not conflate (mirrors the
  `resume_point` vs `archive_status` separation).
- **t635_9 (board In-Flight view):** may reuse `inflight` for a quick launch or
  the t635_8 parser for the richer view; both route picks through the same
  Step 3 engine.

## Scope decisions (surfaced for review)

- **Website docs deferred to t635_18 (user-confirmed).** An aitask-pick docs
  **section** already exists at `website/content/docs/skills/aitask-pick/`
  (`_index.md` + topic sub-pages: build-verification, commit-attribution,
  execution-profiles). The roadmap's documentation track assigns the
  comprehensive sweep — updated aitask-pick docs **and** a new "resuming
  in-flight tasks" workflow page — to **t635_18**; a sub-page authored here
  would be rewritten there. Per the incremental rule this is a deliberate
  carve-out (the AC lists only "per-profile rendering + goldens").
- **No Step 0b change.** Direct `/aitask-pick <n>` of an in-flight task already
  resumes through Step 3 Check 5; adding detection there would duplicate the
  engine. Documented in Notes instead.
- **`record_gates`-invariant.** The section keys off **ledger presence**, not the
  recording profile (an empty ledger → no in-flight rows; a non-`record_gates`
  Implementing task has no ledger → excluded). So the prose is profile-invariant,
  inert without a ledger — exactly t635_5's keying.

## Risk

### Code-health risk: low
- Editing the shared `aitask-pick/SKILL.md.j2` (rendered × 3 agents × 3 profiles)
  risks golden/Jinja churn · severity: low · → mitigation: profile-invariant
  prose (no new Jinja gate; mirrors t635_4 Check 4 / t635_5 Check 5); regenerate
  all 3 goldens; `test_skill_render_aitask_pick.sh` + `aitask_skill_verify.sh`
  green; other proc goldens diff empty.
- New `inflight` is additive and delegates derivation to `aitask_gate.sh`
  (cross-script call within the same dir) · severity: low · → mitigation:
  dedicated `test_query_files_inflight.sh`; `shellcheck`; no new awk (macOS-safe).

### Goal-achievement risk: medium
- The contract is **consume, do not re-derive**; a divergent in-flight section
  that re-implements resume/archival logic or sets `resume_point` itself would
  drift from the engine · severity: medium · → mitigation: the section sets only
  task-selection vars and hands to Step 3 (Check 5 derives `resume_point`;
  Check 4 derives archival); both downstream gates are NON-SKIPPABLE, so a stale
  enumeration cannot cause silent harm (worst case: an extra resume prompt).
- Enumeration predicate (Implementing + ledger) could miss/over-include in-flight
  tasks · severity: low · → mitigation: `test_query_files_inflight.sh` covers
  include (parent + child) and exclude (no-ledger Implementing, Ready+ledger).
- Live **routing** correctness (does picking an in-flight task actually resume at
  the right step?) runs through a live task-workflow hand-off — unprovable by
  render/unit tests · severity: medium · → mitigation: verify_inflight_pick_routing
  (committed 'after' manual-verification task — see Planned mitigations).

### Planned mitigations
- timing: after | name: verify_inflight_pick_routing | type: manual_verification | priority: high | effort: low | addresses: goal-achievement (live pick→resume routing) | desc: autonomous MV driving /aitask-pick against ephemeral in-flight fixtures (parent + child × ALL_PASS/POSTIMPL/IMPLEMENT/PLAN), asserting the in-flight section lists them with correct derived state and routes each to the matching task-workflow step (Check 5 resume / Check 4 archival), then tears the fixtures down (clean git status). Created post-implementation via `aitask_create_manual_verification.sh` (seeded checklist), recorded in the original's `risk_mitigation_tasks`.

## Verification

1. `shellcheck .aitask-scripts/aitask_query_files.sh` (no new awk; macOS-safe).
2. `bash tests/test_query_files_inflight.sh` — include/exclude predicate, parent +
   child, resume_point IMPLEMENT/POSTIMPL, archive_status NO_GATES, NO_INFLIGHT.
3. `bash tests/test_skill_render_aitask_pick.sh` — in-flight section in all 3
   profiles; agent invariance + profile branches still green.
4. Regenerate the 3 goldens; `./.aitask-scripts/aitask_skill_verify.sh` → 0
   failures; other proc goldens diff empty.
5. Manual smoke: with an `Implementing`-plus-ledger fixture present,
   `./.aitask-scripts/aitask_query_files.sh inflight` prints the `INFLIGHT:` line;
   with none, `NO_INFLIGHT`.
6. **Behavioral (deferred):** the Step 8c autonomous manual-verification task
   confirms live pick→resume routing; not executed within this task.

## Step 9 reference

Post-implementation cleanup/archival follow the shared **Step 9** flow (current
branch — `fast` profile; no worktree/merge). This child declares no `gates:`, so
its own archival is unaffected.

## Final Implementation Notes

- **Actual work done:** Made `aitask-pick` gate-aware exactly to plan. (1) New
  `inflight` subcommand in the already-whitelisted `.aitask-scripts/aitask_query_files.sh`
  (`cmd_inflight`): scans active parents (`$TASK_DIR/t*_*.md`) and active children
  (`$TASK_DIR/t*/t*_*.md`) for `status: Implementing` AND a recorded `## Gate Runs`
  ledger, then delegates the derived state to `aitask_gate.sh resume-point` /
  `archive-ready` (never re-implementing it) and emits
  `INFLIGHT:<id>|<path>|<resume_point>|<archive_status>` per task or `NO_INFLIGHT`.
  Wired into the usage block, `show_help`, the example list, and the `main()`
  dispatch. (2) `.claude/skills/aitask-pick/SKILL.md.j2`: a profile-invariant
  **§2.0 In-Flight Tasks (resume candidates)** subsection at the top of Step 2
  (lists in-flight tasks in their own `AskUserQuestion` "Resume" section with a
  derived-state label, routes a picked task through Step 3 — Check 5 resume /
  Check 4 archival — setting only task-selection vars), plus a Notes bullet
  documenting the consumed engine and the "free" board re-entry (no Step 0b
  change). (3) New `tests/test_query_files_inflight.sh` (6/6: include parent +
  child, exclude no-ledger Implementing + Ready-with-ledger, IMPLEMENT/POSTIMPL,
  NO_GATES, NO_INFLIGHT). (4) Extended `tests/test_skill_render_aitask_pick.sh`
  with Test 6 (section renders in all 3 profiles). (5) Regenerated all 3
  `SKILL-{default,fast,remote}-claude.md` goldens (identical 49-line invariant
  adds). `shellcheck` clean (only pre-existing SC1091 source infos);
  `aitask_skill_verify.sh` OK; render test 97/97; gate/query regressions green.

- **Deviations from plan:** None. Lexical `sort` (not GNU `sort -V`) was used in
  `cmd_inflight` for macOS portability — deterministic ordering is all the skill
  needs (it presents the list).

- **Issues encountered:** None. The enumerator surfaced t635_7 itself once it
  reached `Implementing` + `plan_approved` (`INFLIGHT:635_7|…|IMPLEMENT|NO_GATES`)
  — a live confirmation that the predicate and the consumed `resume-point`
  derivation work end-to-end.

- **Key decisions:** (1) **Extend `aitask_query_files.sh`, don't add a new
  script** — zero whitelist change (subcommand of an already-whitelisted helper),
  the exact t635_5 precedent that added `resume-point` to `aitask_gate.sh`. (2)
  **Consume, never re-derive** — §2.0 sets only task-selection vars and hands to
  Step 3; Check 5 derives `resume_point`, Check 4 derives archival (both
  NON-SKIPPABLE downstream, so a stale enumeration cannot cause silent harm).
  (3) **Profile-invariant prose** (no new Jinja gate) — renders identically into
  all 3 goldens, keying off ledger *presence* not the `record_gates` profile key
  (mirrors t635_4 Check 4 / t635_5 Check 5). (4) **No Step 0b change** — direct
  `/aitask-pick <n>` (incl. the board launch) of an in-flight task already
  resumes via Step 3 Check 5; documented in Notes. (5) **Website docs deferred to
  t635_18** (user-confirmed) — the comprehensive sweep owns the aitask-pick docs
  section + the "resuming in-flight tasks" workflow page.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t635_8 (Python gate-ledger parser):** the bash `inflight` subcommand is the
    **skill-facing** enumerator; the Python parser is the **TUI-facing** shared
    derivation. Keep them separate — do not conflate (mirrors the
    `resume_point` vs `archive_status` vs `dependents_status` separation in
    `gate_ledger.py`). Both should ultimately route picks through the same
    `task-workflow` Step 3 engine.
  - **t635_9 (board In-Flight view):** may reuse `aitask_query_files.sh inflight`
    for a quick launch, or the t635_8 parser for the richer action-grouped view;
    either way, launch via `ait skillrun pick … <id>` / `/aitask-pick <id>` so the
    pick resumes through Step 3 — no board change is needed for re-entry.
  - **Behavioral coverage:** an autonomous manual-verification task
    (`verify_inflight_pick_routing`, the confirmed `after` mitigation) is created
    post-implementation to drive `/aitask-pick` against ephemeral in-flight
    fixtures and assert live pick→resume routing — the live counterpart to the
    static render/unit tests here.
