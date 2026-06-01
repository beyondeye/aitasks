---
Task: t832_6_retrospective_dogfooding_evaluation.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md
Worktree: (none — profile 'fast', current branch)
Branch: current branch (main)
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 12:35
---

# Plan: t832_6 retrospective dogfooding evaluation (verified 2026-06-01)

## Context

Final child of the t832 cross-repo decomposition. Its job is **observational**:
exercise the now-shipped cross-repo plumbing (siblings t832_1–t832_5, t832_7,
t832_8) end-to-end, document what worked and what surfaced friction in an audit
doc, and file targeted follow-ups for *new* friction only. Per
`aidocs/planning_conventions.md` audit-only rule, zero new findings → the
deliverable is the documented audit with an explicit "no follow-ups needed".

t887 (`manual_verification_cross_repo_carryover`, Implementing, mine) has three
checklist items **deferred waiting on this task**: that
`aidocs/cross_repo_retrospective_t832.md` exists with all sections, that each
filed follow-up references the retrospective, and the zero-friction wording.
Those are the precise acceptance criteria.

## Verification findings (this plan was re-verified before approval)

- **All preconditions hold.** Registry (`~/.config/aitasks/projects.yaml`) has
  `aitasks_mobile` → `/home/ddt/Work/aitasks_mobile` (status OK) and `aitasks`
  (LIVE). The sibling repo is a real `ait`-enabled repo on `master` with
  applink/QR-pairing work (`PairClient`, `QrUrl`, `ConnectionDBO`) — the
  wire-protocol surface the plan named as a candidate.
- **All 7 shipped surfaces exist** with the invocation shapes below (confirmed
  by code inventory):
  1. `aitask_query_files.sh --project <name> <subcmd>` — prefix flag, all
     subcommands incl. new `task-status`; re-execs sibling via
     `lib/cross_repo_reexec.sh`.
  2. `aitask_explain_context.sh --project <name>:<path>` (also `<name>#<path>`).
  3. `aitask_create.sh --batch --xdeps <csv> --xdeprepo <name>` (both-or-neither
     for data; `--xdeprepo` alone allowed intent-only since t832_10). Writes
     `xdeps:` / `xdeprepo:` frontmatter.
  4. `aitask_ls.sh` cross-repo blocking in `calculate_blocked_status()` →
     `<repo>#<id>` markers, `UNREACHABLE` for stale/unregistered projects.
  5. `planning-cross-repo.md` (read-only design) + `cross-repo-child-assignment.md`
     (post-approval creation); metadata-only trigger on `xdeprepo`.
  6. `aitask_update.sh --project <name> --batch ...` — cross-repo allowlist
     (labels/priority/effort/deps/status Ready|Editing|Postponed); refuses
     `--name` and status Implementing/Done/Folded; lock guardrail dies if held
     by another host.
  7. `ait board` — `#` key opens read-only cross-repo popup; multi-ref picker.
- **Pre-identified friction is already handled** (do NOT re-file):
  - Board multi-ref picker keyboard-nav (p832_9 defect) → fixed in t886;
    manual verification pending in **t889**.
  - `keybinding_registry.py` YAML-crash (p832_8 upstream defect) → already
    catches `yaml.YAMLError` and degrades to "no overrides".
- **Cross-repo follow-ups already filed by sibling tasks:** t857
  (`xdeprepo_interactive_followup`), t858 (`aitask_create_skill_xrepo`,
  Postponed), t872 (`brainstorm_cross_repo_project_references`, Implementing),
  t887, t889.
- **No live xdeps data** currently exists in this repo, so read-only surfaces
  must be exercised against disposable test data.

**Net:** the retrospective realistically trends toward audit-only with most
friction already captured. The dogfood still runs to surface *new* friction and
confirm the surfaces behave as documented.

## Scope decision (confirmed with user)

**Controlled / low-footprint dogfood.** Exercise read-only surfaces against the
sibling repo's *existing* tasks (no creation needed). Exercise mutating surfaces
minimally with a single disposable local task and a label add/revert, cleaning
up after. **No permanent cross-repo artifacts**, no full wire-protocol bump.
Deliverable = audit doc + new follow-ups only.

## Implementation steps

### Step 1 — Read-only surfaces against existing sibling data (no creation)
Pick a real `aitasks_mobile` task ID (read `aitasks_mobile/aitasks/`). Run and
capture output + any friction:
- `aitask_query_files.sh --project aitasks_mobile task-file <id>` and
  `task-status <id>` and `sibling-context <parent>`.
- `aitask_explain_context.sh --max-plans 1 --project aitasks_mobile:<real_file>`
  (and the `aitasks_mobile#<file>` shorthand) — confirm cross-repo aggregation.
- Negative path: `--project does_not_exist` and a stale/bogus task id → confirm
  the error / `UNREACHABLE` messaging is clear.

### Step 2 — Mutating surfaces, minimal + reverted
- **xdeps creation + blocking display:** create ONE disposable local task with
  `aitask_create.sh --batch --name dogfood_t832_6_probe --xdeps <mobile_id>
  --xdeprepo aitasks_mobile` (no `--commit`). Inspect emitted `xdeps:`/`xdeprepo:`
  frontmatter; run `aitask_ls.sh -v` and confirm the `aitasks_mobile#<id>`
  blocking marker renders. Capture create-time cross-repo validation behavior
  (false positives/negatives). **Then delete the probe task file** (it was never
  committed → zero footprint).
- **`aitask_update.sh --project`:** exercise the lock guardrail / allowlist
  *without* a lasting change — attempt a refused transition
  (`--status Implementing` cross-repo) and confirm it dies with the documented
  message; then do an allowed add-label + immediate remove-label round-trip on a
  sibling task to confirm the re-exec + lock-check path works, and verify the
  label is gone afterward.
- **parallel-cross-repo-planning trigger:** confirm metadata-only trigger
  detection by inspection (the procedure fires on `xdeprepo` frontmatter). Do
  NOT drive a real paired creation. Document the read-only design path.

### Step 3 — TUI surfaces (document, defer live check to t887/t889)
`ait board` `#`-navigation and the multi-ref picker are interactive TUI flows
already covered by t889's manual-verification checklist. Note in the audit that
live verification is delegated there rather than re-driven here.

### Step 4 — Author the audit document
Write `aidocs/cross_repo_retrospective_t832.md`. One section per shipped surface
(t832_1, _2, _3, _4, _5, _7, _8), each with:
- **What worked** (concrete example / command run).
- **Friction surfaced** (with reproducer), or "none".
- **Already-tracked** cross-references (t857/t858/t872/t887/t889, p832_8/p832_9
  fixes) so the audit doesn't double-count.
- A final **Recommended follow-ups** section listing only genuinely new gaps
  (name, scope, friction addressed) — or an explicit "No new follow-ups needed"
  per the audit-only convention.

### Step 5 — File new follow-ups (only if new friction surfaces)
For any *new* confirmed friction, create a top-level task (NOT a child of t832)
via the Batch Task Creation Procedure, each body referencing this retrospective
and the specific friction. Likely most/all candidates are already filed → expect
few or zero. Candidates the plan flagged (file only if they actually bite and
aren't already covered): `ait monitor` cross-repo surfacing; board
project-switch (note: picker nav already fixed); xdeps maintenance/repair.

## Verification

- `aidocs/cross_repo_retrospective_t832.md` exists with a section per shipped
  surface and a Recommended-follow-ups section (matches t887's deferred items).
- Each new follow-up (if any) references this retrospective + its friction.
- Zero new friction → audit explicitly states "no follow-ups needed".
- No permanent cross-repo artifacts left behind: probe task deleted, sibling
  label round-trip reverted, sibling repo `git status` unchanged by the dogfood.

## Out of scope

- Re-implementing siblings; full wire-protocol bump; major refactors (→ follow-ups).
- Re-filing already-tracked friction (board picker nav, keybinding YAML crash).

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)

## Step 9 reference

After implementation + review, proceed to Step 9 (Post-Implementation): archive
via `./.aitask-scripts/aitask_archive.sh 832_6`, which removes the child from the
parent's `children_to_implement` and archives the parent if all children are done.
