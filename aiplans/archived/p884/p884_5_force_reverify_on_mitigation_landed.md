---
Task: t884_5_force_reverify_on_mitigation_landed.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_6_risk_evaluation_website_docs.md, aitasks/t884/t884_7_risk_eval_retrospective_and_ports.md, aitasks/t884/t884_8_manual_verification_risk_evaluation.md
Archived Sibling Plans: aiplans/archived/p884/p884_1_risk_frontmatter_field_plumbing.md, aiplans/archived/p884/p884_2_risk_evaluation_profile_key.md, aiplans/archived/p884/p884_3_risk_evaluation_planning_step.md, aiplans/archived/p884/p884_4_risk_mitigation_followup_procedure.md, aiplans/archived/p884/p884_9_two_field_risk_plumbing.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 22:11
---

# Plan: t884_5 — Force-reverify when a "before" mitigation lands

> Verified 2026-06-01 against the current tree. Parent architecture & decisions:
> `aiplans/p884_add_task_risk_evaluation_in_planning.md`. Depends on t884_1
> (`risk_mitigation_tasks` field) and t884_4 (populates it + the stop-&-revert
> path that makes re-pick meaningful) — both **archived/landed**.

## Context

When a "before" risk-mitigation task lands (t884_4's flow: the original task is
reverted to `Ready` and blocked on the mitigation, then re-picked once it
lands), the codebase has changed *underneath* the original task's plan. Without
a signal, a profile that normally **skips** verification (it has a fresh
`plan_verified` entry) would reuse a now-stale plan. This task adds a **read-time
signal at pick**: if any listed `risk_mitigation_tasks` was archived (its
`completed_at`) **after** the plan's most-recent `plan_verified` timestamp, force
the plan into VERIFY mode on the next pick. **No-op when the field is
absent/empty.**

This is invisible plumbing — t884_6 documents it as a one-liner.

**Scoping (resolved with user):** the signal is meaningful **only when risk
evaluation is active**. `risk_mitigation_tasks` is populated *exclusively* by
t884_4's risk-mitigation flow (gated by the `risk_evaluation` profile key), so
outside that context the check is a pure no-op. The design therefore splits into
two honestly-scoped pieces:
- A **generic** `--force-verify` flag on `decide` — `decide` doesn't know *why*
  it is being forced, so the flag is a legitimate plan-verification primitive
  that stays on `aitask_plan_verified.sh`.
- A **risk-named standalone helper** `aitask_risk_mitigation_landed.sh` that owns
  the risk-specific check (reads `risk_mitigation_tasks`, resolves archived
  `completed_at`, compares to last verification). Risk-feature logic stays out of
  the generic plan-metadata script; the name signals its narrow scope.

## Verify-pass findings (anchors confirmed against current tree)

- **`aitask_plan_verified.sh`** — `cmd_decide` (lines 186-246) emits the fixed
  8-line `KEY:value` contract (`TOTAL/FRESH/STALE/LAST/REQUIRED/STALE_AFTER_HOURS/DISPLAY/DECISION`).
  `cmd_read` (56-95) emits `<agent>|<timestamp>` lines; `parse_ts` (45-52) is the
  portable epoch parser. The missing-file early return (196-200) already yields
  `DECISION:VERIFY`. ✅
- **`aitask_archive.sh:145-149`** writes `completed_at: <ts>` after `updated_at`
  in fixed `YYYY-MM-DD HH:MM` format (same format as `plan_verified` entries →
  the two are **lexicographically comparable as strings**). ✅
- **`aitask_query_files.sh archived-task <N|N_M>`** resolves an archived task
  file, emitting `ARCHIVED_TASK:<path>` (or `NOT_FOUND`). ✅
- **`planning.md` source** — the `decide` call lives in **two** Jinja branches:
  the profile branch (line 52, templated args) and the both-keys-absent fallback
  (line 86). §6.0 opens at line 16; the plan_preference Jinja block starts at
  line 29 — the suffix insertion point for Step 6.0a is between line 27 and 29
  (profile-agnostic, outside the Jinja block). ✅
- **Goldens** — `planning.md` is a profile-**varying** wrapped file
  (`tests/test_skill_render_task_workflow.sh` Test 1) with goldens
  `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`. New
  profile-agnostic prose renders identically into all three. ✅
- **`test_plan_verified.sh`** exists with `decide` coverage to extend. ✅
- `aitask_plan_verified.sh` is already allowlisted (so the `--force-verify` flag
  needs no permission change). The **new** `aitask_risk_mitigation_landed.sh`
  does need allowlisting — see Step 2 touchpoints.
- `aitask_plan_externalize.sh` is the model allowlist entry to mirror: it appears
  in `.claude/settings.local.json:64`, `seed/claude_settings.local.json:65`,
  `seed/codex_rules.default.rules:34`, `seed/opencode_config.seed.json:54`.

## Goal

Read-time signal at pick: if any `risk_mitigation_tasks` entry's archived
`completed_at` is **after** the plan's most-recent `plan_verified` timestamp,
force `DECISION:VERIFY` on the next pick. **No-op when the field is absent/empty.**

## Steps

### 1. `aitask_plan_verified.sh` — add `--force-verify` to `decide` (pure-additive)

In `cmd_decide`, after the three positional args, parse an optional
`--force-verify` flag (4th position). Implementation:
- `local force_verify=0`; if `$# -gt 3`, `shift 3` and loop remaining args:
  `--force-verify` → `force_verify=1`; anything else → `die`.
- Keep the existing positional validation and the missing-file early return
  **unchanged** (missing file already returns VERIFY → force is moot there).
- Compute `total/fresh/stale/last_entry` exactly as today, then in the
  decision branch add a **new first arm**:
  ```bash
  if [[ $force_verify -eq 1 ]]; then
      decision="VERIFY"
      display="Forced re-verification: a risk-mitigation task landed after the last verification."
  elif [[ $total -eq 0 ]]; then
      ...   # unchanged
  ```
  This keeps `TOTAL/FRESH/STALE/LAST` accurate (richer than a bare
  short-circuit) and only overrides `DECISION`/`DISPLAY`.
- **Byte-stability:** with the flag absent, `force_verify=0`, the new arm never
  fires → output is byte-identical to today. Update the usage/header comment to
  document the optional flag.

### 2. New `aitask_risk_mitigation_landed.sh` — the risk-specific check

New script: `aitask_risk_mitigation_landed.sh <task_file> <plan_file>`. Output
contract (exit 0):
```
FORCE_VERIFY:<0|1>
LANDED:<id>|<completed_at>      # one line per mitigation that landed after last verify (only when FORCE_VERIFY:1)
```
The `LANDED:` lines are the point of the script — they tell the caller **which**
mitigations changed the codebase, so verify mode can read exactly those archived
plans. Logic:
1. Read `risk_mitigation_tasks` from the **task** frontmatter (reuse the YAML
   list reader; `yaml_utils.sh` is in the source chain). If absent/empty →
   print `FORCE_VERIFY:0` and exit (no-op).
2. Last verification timestamp: call `aitask_plan_verified.sh read <plan_file>`,
   take the lexicographically-largest `<timestamp>` (fixed `YYYY-MM-DD HH:MM`,
   string-sortable). If empty (no prior verifications) → `FORCE_VERIFY:0`
   (the `decide` helper already returns VERIFY in that case; nothing to force).
3. For each ID: resolve its archived file via
   `aitask_query_files.sh archived-task <id>`; on `ARCHIVED_TASK:<path>` read
   `completed_at`; on `NOT_FOUND` the mitigation hasn't landed → skip.
4. Collect every ID whose `completed_at` > last-verification timestamp (string
   compare) into the landed set. If the set is non-empty → print
   `FORCE_VERIFY:1` followed by one `LANDED:<id>|<completed_at>` line per landed
   mitigation (sorted). Else → `FORCE_VERIFY:0`.
- Standard framework conventions: `#!/usr/bin/env bash`, `set -euo pipefail`,
  source `terminal_compat.sh`/`yaml_utils.sh` from `SCRIPT_DIR`, `die`/`usage`.
- **Allowlist touchpoints** (mirror an existing entry such as
  `aitask_plan_externalize.sh` exactly): add the script to every runtime + seed
  allowlist — `.claude/settings.local.json`, `seed/claude_settings.local.json`,
  `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`, and any
  runtime codex/opencode config present in this repo. Use
  `/aitask-audit-wrappers` (or its helper) + `aitask_skill_verify.sh` to confirm
  no touchpoint is missed.
- **New test** `tests/test_risk_mitigation_landed.sh` (model on
  `test_plan_verified.sh`): builds a sandbox task+plan+archived-mitigation
  fixtures and asserts: absent field → `FORCE_VERIFY:0` (no `LANDED:` lines);
  no prior verification → `0`; one mitigation `completed_at` later than last
  verify → `FORCE_VERIFY:1` + exactly one matching `LANDED:<id>|<ts>` line;
  two landed → both IDs listed; earlier `completed_at` → `0`; `NOT_FOUND`
  mitigation skipped (not listed).

### 3. `aitask_plan_verified.sh decide` — generic `--force-verify` flag

(As Step 1 above — the flag stays caller-agnostic; `decide` does not read any
risk field. It is driven solely by the result of Step 2's helper.)

### 4. `planning.md` — add Step 6.0a (calls the helper, threads the flag)

**Add `### Step 6.0a: Force-reverify when a risk mitigation landed`** as a
profile-agnostic block inserted right after "**If a plan file exists**, read it."
(line 27) and **before** the `{# plan_preference #}` Jinja block (line 29). Do
**not** renumber 6.0/6.1. Prose (now thin — no in-prose timestamp math):

1. Run `./.aitask-scripts/aitask_risk_mitigation_landed.sh <task_file> <plan_file>`.
2. Parse `FORCE_VERIFY:<0|1>` and any `LANDED:<id>|<completed_at>` lines.
   - If `0` → proceed to §6.0 unchanged.
   - If `1` → (a) **display the landed mitigations to the user** verbatim, e.g.
     "Risk-mitigation task(s) landed since the last plan verification: t884_4
     (2026-06-01 18:14). Forcing plan re-verification."; (b) the Verify Decision
     sub-procedure below must append `--force-verify` to its `decide` call;
     (c) carry the landed `<id>` list into Step 6.1 verify mode (see below).
3. **Feed landed IDs into verify mode (6.1):** when entering verification, read
   each landed mitigation's archived plan
   (`aiplans/archived/p<parent>/p<parent>_<child>_*.md`, resolved with
   `aitask_query_files.sh archived-task <id>` → its `aiplans/archived` sibling)
   to understand what changed in the codebase, and re-check the plan's
   assumptions/file paths against those specific changes. This makes the
   force-reverify actionable rather than a blind re-read.

**Thread into both Verify Decision sub-procedures** (profile branch step 3 /
line ~52, both-absent fallback step 3 / line ~86): add one line — "If Step 6.0a
returned `FORCE_VERIFY:1`, append `--force-verify` to this command." The 8-line
parser and `DECISION:` branching are unchanged.

**Scope note (use_current is coherent, not a gap):** `--force-verify` only
matters on the verify path, because `plan_verified` timestamps only exist there.
A `use_current` profile never verifies and has no timestamps to stale-ize — the
user opted into "always trust the plan." So scoping force-verify to the decide
call is semantically complete, not a missed case. Recorded so the boundary is
explicit.

### 5. Tests + goldens (same commit)

- **`tests/test_plan_verified.sh`**: add a `--force-verify` block —
  (a) byte-stability: capture `decide <plan> 1 24` once, assert it is unchanged
  by this task's edits; (b) `decide <fresh-plan> 1 24 --force-verify` ⇒
  `DECISION:VERIFY` while plain `decide <fresh-plan> 1 24` ⇒ `DECISION:SKIP`;
  (c) `--force-verify` still emits all 8 `KEY:` lines with accurate
  `TOTAL/FRESH/STALE`; (d) unknown flag ⇒ non-zero exit.
- **Regenerate** `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`:
  ```bash
  PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
  for p in default fast remote; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/task-workflow/planning.md \
      aitasks/metadata/profiles/$p.yaml claude \
      > tests/golden/procs/task-workflow/planning-$p.md
  done
  ```
  Review the diff: it must contain **only** the new Step 6.0a block + the two
  one-line threading notes, identically across all three.
- Run `bash tests/test_plan_verified.sh`, `bash tests/test_risk_mitigation_landed.sh`,
  `bash tests/test_skill_render_task_workflow.sh`,
  `./.aitask-scripts/aitask_skill_verify.sh`, and
  `shellcheck .aitask-scripts/aitask_plan_verified.sh .aitask-scripts/aitask_risk_mitigation_landed.sh`
  — all in the same commit.

## Reference patterns

- `aitask_plan_verified.sh` `cmd_decide` (186-246), `cmd_read` (56-95),
  `parse_ts` (45-52) — the 8-line contract + staleness logic; `cmd_read` is
  reused by the new helper for the last-verification timestamp.
- `aitask_plan_externalize.sh` — model for a new allowlisted helper script
  (shebang/`set`/sourcing/`die`) + its 4 allowlist entries.
- `aitask_archive.sh:145-149` — `completed_at` write format.
- `aitask_query_files.sh archived-task` — archived-file resolution.
- `lib/yaml_utils.sh` — frontmatter list reader for `risk_mitigation_tasks`.
- `tests/test_plan_verified.sh` — model for both the `--force-verify` additions
  and the new `tests/test_risk_mitigation_landed.sh`.

## Verification

- Unit (`aitask_plan_verified.sh`): `decide <plan> 1 24` byte-identical pre/post;
  `... --force-verify` ⇒ `DECISION:VERIFY`; fresh plan SKIP→VERIFY under the
  flag; unknown flag dies.
- Unit (`aitask_risk_mitigation_landed.sh`): absent field → `FORCE_VERIFY:0`;
  no prior verification → `0`; one mitigation later than last verify →
  `FORCE_VERIFY:1` + its `LANDED:<id>|<ts>` line; two landed → both listed;
  earlier → `0`; `NOT_FOUND` skipped.
- Integration sim: a task with `risk_mitigation_tasks: [<id>]` whose archived
  file's `completed_at` is later than the plan's last `plan_verified` → Step 6.0a
  surfaces `LANDED:<id>` to the user, forces verify, and reads that mitigation's
  archived plan; earlier → normal flow; absent field → no-op.
- `bash tests/test_plan_verified.sh`, `bash tests/test_risk_mitigation_landed.sh`,
  `bash tests/test_skill_render_task_workflow.sh`, `aitask_skill_verify.sh`,
  `shellcheck` (both scripts), `/aitask-audit-wrappers` allowlist check — all pass.

## Notes for sibling tasks

- t884_6 docs this as a one-liner (the `### Planned mitigations` / before=blocking
  / after=follow-up semantics + this force-reverify signal).
- t884_7 already tracks the Codex/OpenCode ports of the `planning.md` change (the
  rendered variants regenerate from the single Claude source).
- Step 6.0a is a SUFFIX — keep §6.0/§6.1 numbering and the 8-line `decide` parser
  stable. The use_current scope boundary above is intentional.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9 (no separate branch —
profile 'fast' works on the current branch).

## Final Implementation Notes

- **Actual work done:** Implemented the split design exactly as approved.
  - `aitask_plan_verified.sh decide`: optional 4th-position `--force-verify`
    flag (parsed after the 3 positionals; unknown flag → `die`). New first
    decision arm forces `DECISION:VERIFY` with a distinct `DISPLAY` while
    preserving accurate `TOTAL/FRESH/STALE/LAST`. Output byte-identical when the
    flag is absent. Header/usage comment updated.
  - New `aitask_risk_mitigation_landed.sh <task_file> <plan_file>` → emits
    `FORCE_VERIFY:<0|1>` plus one `LANDED:<id>|<completed_at>` line per
    mitigation that landed after the last verification. Reuses
    `aitask_plan_verified.sh read` for the last-verify timestamp,
    `aitask_query_files.sh archived-task` for resolution, `read_yaml_list` /
    `read_yaml_field` from `yaml_utils.sh`. Lexicographic timestamp compare
    (both `YYYY-MM-DD HH:MM`). No-op (`FORCE_VERIFY:0`) when the field is
    absent/empty or when there is no prior verification.
  - `planning.md` Step 6.0a (profile-agnostic, inserted before the
    plan_preference Jinja block; 6.0/6.1 not renumbered): calls the helper,
    surfaces landed mitigations, sets a `force_verify` signal, and feeds landed
    IDs into verify mode. `--force-verify` threaded into BOTH Verify Decision
    sub-procedures (profile branch + both-absent fallback).
  - Allowlist: helper added to `seed/codex_rules.default.rules`,
    `.codex/rules/default.rules`, `seed/opencode_config.seed.json`,
    `seed/claude_settings.local.json`.
  - Tests: `test_plan_verified.sh` +`--force-verify` block (49/49); new
    `test_risk_mitigation_landed.sh` (13/13, ARCHIVED_DIR-sandboxed, fixed
    timestamps). Goldens `planning-{default,fast,remote}.md` regenerated (+32
    identical lines each — only the new block + threading note).
- **Deviations from plan:** None structural. Two design refinements were made
  *during planning* (pre-approval) at the user's direction: (1) the check moved
  from in-prose timestamp math to a dedicated script; (2) that script is a
  risk-named standalone (`aitask_risk_mitigation_landed.sh`), not a generic
  subcommand, because it is meaningful only under risk evaluation; (3) it returns
  the landed task IDs (`LANDED:` lines), not a bare boolean, so verify mode can
  read exactly those archived plans.
- **Issues encountered:** Initial helper omitted the `LANDED:` prefix on output
  lines — caught immediately by `test_risk_mitigation_landed.sh` and fixed.
- **Key decisions:** `--force-verify` stays caller-agnostic on `decide` (it does
  not read any risk field); all risk knowledge lives in the new helper. The
  `use_current` scope boundary is intentional (no `plan_verified` timestamps
  exist on that path, so there is nothing to stale-ize).
- **Upstream defects identified:** None.
- **Outstanding (surfaced to user at review):** The runtime
  `.claude/settings.local.json` allowlist entry was blocked by the Claude Code
  auto-mode self-modification guard. The user opted to add
  `Bash(./.aitask-scripts/aitask_risk_mitigation_landed.sh:*)` manually. The
  seed (`seed/claude_settings.local.json`) is committed, so fresh installs are
  covered. `/aitask-audit-wrappers` (interactive) was not run;
  `aitask_skill_verify.sh` passed and the 5 touchpoints were cross-checked
  manually.
- **Notes for sibling tasks:** unchanged from "Notes for sibling tasks" above —
  t884_6 docs this as a one-liner; t884_7 covers the auto-rendered ports.
