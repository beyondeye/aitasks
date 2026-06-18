---
Task: t1016_3_anchor_spawn_site_wiring.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_1_*.md, aitasks/t1016/t1016_2_*.md, aitasks/t1016/t1016_4_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_3_anchor_spawn_site_wiring
Branch: aitask/t1016_3_anchor_spawn_site_wiring
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-18 15:43
---

# Plan — t1016_3 Spawn-site wiring (anchor provenance)

## Context

t1016_1 (landed) added the `--anchor` / `--followup-of` creation flags to
`aitask_create.sh`; t1016_2 (landed) documented them. The `--followup-of <src>`
flag makes a spawned task auto-join its source's **topic anchor** (group key =
`anchor` if set, else own id; flattened to the root, archived+zip-inclusive
validation).

This child threads `--followup-of` into the framework sites that spawn a
follow-up task but currently record **no provenance**, so spawned follow-ups
cluster with their source on the board's by-topic view (t1016_4). Depends on
t1016_1; follows t1016_2.

**Verified against current code (2026-06-18, verify path):** flag exists
(`aitask_create.sh:184`, `resolve_anchor`:208); `normalize_anchor_id`
(`lib/task_utils.sh:375`) validates via `aitask_query_files.sh task-status`,
which is **active → filesystem-archived → tar-bundle (`old*.tar.zst`/`.tar.gz`)
inclusive** (`cmd_task_status` → `cmd_archived_task` → `search_archived_task`).
`--followup-of` and `--anchor` are **mutually exclusive** and **both rejected
alongside `--parent`** (`aitask_create.sh:213-217`).

## Key design decisions (refinements over the original task proposal)

1. **qa wiring is branch-specific.** `aitask-qa/follow-up-task-creation.md`
   creates the test follow-up as a **child** (`mode: child` → `--parent`) when
   the target is a child, and as a **standalone parent** otherwise. Because
   `--followup-of` is **rejected with `--parent`**, it can only be passed in the
   `is_child == false` (standalone) branch. In the child branch the new sibling
   **auto-inherits the parent's anchor** already — passing `followup_of` there
   would make `aitask_create.sh` `die`. So: add `followup_of` to the standalone
   branch only, and add a one-line note to the child branch.

2. **verification-followup is best-effort (guarded), archived+zip-inclusive.**
   The bug-task origin is a *loose* reference (resolved from `verifies` /
   `--from` / `--origin`) that may be commit-only / unresolvable. To preserve the
   current tolerant contract (today it creates the bug task even when the origin
   has no task file), guard the flag: resolve the origin via
   `aitask_query_files.sh task-status` (active+archived+zip-inclusive) and pass
   `--followup-of` **only when it resolves**; otherwise skip it (bug task becomes
   a root, `--deps` unchanged). The guard **fails safe** if `task-status` is
   unavailable → the existing `test_verification_followup.sh` (whose
   commit-only origins don't resolve) keeps passing with **no patch**.

3. **carryover is unconditional.** In `aitask_archive.sh::create_carryover_task`
   the source `$orig_id` *is the task being archived* — structurally guaranteed
   resolvable (task-status is archived-inclusive). Pass `--followup-of
   "$orig_id"` unconditionally; no extra resolver call added to the archival hot
   path. (Asymmetry with #2 is deliberate: carryover's source is guaranteed,
   verification-followup's is not.)

4. **review stays root-by-default.** `aitask-review` reviews a diff/area with no
   single source task → it must create a ROOT. Document a one-line caveat in the
   authoring template; do **not** wire an unconditional anchor.

## Steps

### Shell sites

1. **`aitask_archive.sh::create_carryover_task`** (~L583-590) — add
   `--followup-of "$orig_id"` to the `create_args` array (unconditional; orig is
   the archived task).

2. **`aitask_verification_followup.sh`** (create call ~L193-198) — add a
   best-effort guard before the create and thread the flag safely:
   ```bash
   # Best-effort topic anchor: only when origin resolves (active/archived/zip).
   local followup_args=()
   local origin_status
   origin_status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status "$origin" 2>/dev/null || true)
   if [[ "$origin_status" == STATUS:* && "$origin_status" != STATUS:NOT_FOUND ]]; then
       followup_args=(--followup-of "$origin")
   fi
   ```
   Then add `"${followup_args[@]+"${followup_args[@]}"}"` to the
   `aitask_create.sh` invocation (the `+` form is safe under `set -u` with an
   empty array). It already passes `--deps "$origin"`; keep that.
   Requires copying `aitask_query_files.sh` into the fake repo of the **new**
   anchor test (the guard shells to it); the existing test is unaffected.

### Markdown procedures (source of truth: `.claude/skills/`)

3. **`.claude/skills/aitask-qa/follow-up-task-creation.md`** — in the
   **`is_child == false`** (standalone, `mode: parent`) param list add
   `- followup_of: <task_id>` (the qa target). In the **`is_child == true`**
   (`mode: child`) branch add a one-line note: the test sibling auto-inherits the
   parent's anchor; do **not** pass `followup_of` (mutually exclusive with
   `--parent`).

4. **`.claude/skills/task-workflow/risk-mitigation-followup.md`** — Part 2
   (Step 7 "before", ~L143-148) and Part 3 (Step 8d "after", ~L218-221): both
   create with `mode: parent` (independent tasks), so add
   `followup_of: <task_id>` (the original task) to the Batch Task Creation params
   so each mitigation anchors to the task it protects.

### Caveat (document, do NOT force)

5. **`.claude/skills/aitask-review/SKILL.md.j2`** (Step 4 Task Creation, ~L179-220
   — note `SKILL.md` is a 22-line stub; the content lives in the `.j2`) — add a
   one-line caveat: review creates a ROOT by default (no single source task);
   only pass `followup_of` when a specific reviewed task is the clear source.

### Regenerate rendered variants + goldens

Edits to #3/#4/#5 feed committed rendered variants and goldens
(`.claude/skills/aitask-qa-{default,fast,remote}-/`, `aitask-review-*-/`,
task-workflow variants; `tests/golden/procs/`, `tests/golden/skills/`). Per
CLAUDE.md, read `aidocs/framework/skill_authoring_conventions.md`
("Regenerate goldens after any `.md.j2` or closure edit"), then:
```bash
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
# regenerate affected goldens per the conventions doc, then verify:
bash tests/test_skill_render_task_workflow.sh
./.aitask-scripts/aitask_skill_verify.sh
```

## Verification

**New tests (per task AC):**
- `tests/test_archive_carryover_anchor.sh` — real-`aitask_create.sh` fixture
  (copy `aitask_create.sh`, `aitask_claim_id.sh`, `aitask_query_files.sh`,
  `lib/archive_scan.sh`, plus the libs the existing `test_archive_carryover.sh`
  copies). Archive a task with deferred manual-verification items
  (`--with-deferred-carryover`) → assert the carryover task file carries
  `anchor: <orig_id>`.
- `tests/test_verification_followup_anchor.sh` — copy `aitask_query_files.sh`
  into the fake repo and create a **real** origin task file. Cases:
  (a) resolvable origin → bug task has `anchor: <origin>` **and** still
  `depends: [origin]`; (b) **unresolvable / commit-only origin → bug task
  created with NO `anchor:` line** (guard fail-safe), still `depends:`.

**Regression / no-patch confirmation:**
- `bash tests/test_verification_followup.sh` — still green unchanged (guard
  fails safe; commit-only origins don't resolve → no anchor).
- `bash tests/test_archive_carryover.sh` — still green (stubs `aitask_create.sh`;
  stub ignores the new flag).

**Lint / render:**
- `shellcheck .aitask-scripts/aitask_archive.sh .aitask-scripts/aitask_verification_followup.sh`
- `bash tests/test_skill_render_task_workflow.sh` + `./.aitask-scripts/aitask_skill_verify.sh` — clean after the markdown edits + goldens regen.

## Risk

### Code-health risk: medium
- Touches two load-bearing shell scripts (`aitask_archive.sh`,
  `aitask_verification_followup.sh`) on the archival / verification-followup
  paths; the verification-followup guard adds one `aitask_query_files.sh`
  shell-out per bug-task creation. Changes are additive (one flag / one guard per
  site). · severity: medium · → mitigation: in-task new tests + existing-test
  regression confirmation + shellcheck.
- The qa branch nuance is a correctness trap — passing `followup_of` in the
  `--parent` branch would make `aitask_create.sh` `die` at runtime. Mitigated by
  scoping the flag to the standalone branch and documenting the child branch;
  the rule is already in the canonical contract. · severity: low · → mitigation:
  branch-scoped edit + note; render/verify tests.
- Blast radius spans 3 rendered markdown surfaces + 1 `.md.j2` → many generated
  variants/goldens; a missed regen would diverge. · severity: low · →
  mitigation: `aitask_skill_rerender.sh` (all profiles) + `test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh`.

### Goal-achievement risk: low
- None identified. Approach verified against current code (flag + line numbers +
  archived/zip resolver confirmed); all spawn sites from the parent task covered;
  the guard satisfies the robustness requirement; tests cover resolvable,
  unresolvable, and the child-branch mutual-exclusion case.

(No `### Planned mitigations` — the code-health risk is fully mitigated in-task by
the testability-first design; a separate before/after task would be redundant,
consistent with siblings p1016_1 / p1016_2.)

## Post-Implementation
Step 9 applies on completion. In Final Implementation Notes record: any spawn
sites found that intentionally remain un-wired (and why), the guarded-vs-
unconditional asymmetry rationale, and the exact goldens-regen command used. The
parent t1016 archives automatically once all siblings are done (remaining after
this: t1016_4 board view, t1016_5 manual verification).

## Final Implementation Notes

- **Actual work done:** Threaded `--followup-of` anchor provenance into the
  framework's follow-up spawn sites.
  - `aitask_archive.sh::create_carryover_task` — `--followup-of "$orig_id"`
    added to `create_args` (unconditional).
  - `aitask_verification_followup.sh` — a best-effort guard (resolve origin via
    `aitask_query_files.sh task-status`, archive+zip-inclusive; thread
    `--followup-of "$origin"` only when it resolves, using the
    `${followup_args[@]+...}` empty-array-safe expansion).
  - `aitask-qa/follow-up-task-creation.md` — `followup_of` in the standalone
    (`mode: parent`) branch only; explicit note in the child branch.
  - `task-workflow/risk-mitigation-followup.md` — `followup_of` in Part 2 & 3
    (both `mode: parent`).
  - `aitask-review/SKILL.md.j2` — root-by-default caveat.
  - New tests `tests/test_archive_carryover_anchor.sh` (4 asserts) and
    `tests/test_verification_followup_anchor.sh` (10 asserts, resolvable +
    unresolvable-origin cases). Regenerated goldens: review entry-point ×3
    profiles + `risk-mitigation-followup-default` proc golden.

- **Deviations from plan:** None substantive. The plan anticipated possibly
  patching the existing `test_verification_followup.sh` setup; the guarded
  (best-effort) design made that unnecessary — its commit-only origins don't
  resolve, so the guard fails safe and the existing 28 asserts pass unchanged.

- **Key decisions / asymmetry rationale:** carryover wiring is **unconditional**
  (the source `$orig_id` IS the task being archived — structurally guaranteed
  resolvable; `verification_gate_and_carryover` runs at `main()` before the
  archive move, so the original is still active at create time);
  verification-followup is **guarded** (its origin is a loose reference resolved
  from `verifies`/`--from`/`--origin` that may be commit-only). Origin
  resolution reuses the existing archive+zip-inclusive resolver
  (`task-status` → `cmd_archived_task` → `search_archived_task`, covering
  `old*.tar.zst`/`.tar.gz`), per the user's request. The qa wiring is
  branch-scoped because `--followup-of` is mutually exclusive with `--parent`
  (a child auto-inherits the parent's anchor; passing both would `die`).

- **Spawn sites intentionally left un-wired:** `aitask-review` — reviews a
  diff/area with no single source task, so it must create topic roots; only a
  one-line caveat was added, no unconditional anchor.

- **Goldens regen command used:** per-profile `skill_template.py` render for the
  review entry-point goldens (`default`/`fast`/`remote`) and the profile-
  invariant `risk-mitigation-followup-default.md` proc golden; verified with
  `tests/test_skill_render_task_workflow.sh` (99/99),
  `tests/test_skill_render_aitask_review.sh` (96/96),
  `tests/test_skill_render_aitask_qa.sh` (189/189), and
  `aitask_skill_verify.sh` (OK). `aitask_skill_rerender.sh remote` produced no
  tracked diff (`risk-mitigation-followup.md` is not part of the committed
  `task-workflow-remote-/` closure — a pre-existing omission, left as-is).

- **Upstream defects identified:** None.

- **Notes for sibling tasks (t1016_4 board view):** anchors set by these sites
  are stored **bare** (`42` / `42_1`) and point at the topic root; group key =
  `anchor` if present else the task's own bare id. Roots emit no `anchor:` line.
  Carryover/mitigation/verification follow-ups now carry an `anchor:` line, so
  the by-topic view will cluster them with their source.
