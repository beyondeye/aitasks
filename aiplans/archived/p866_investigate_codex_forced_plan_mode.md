---
Task: t866_investigate_codex_forced_plan_mode.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t866 — Relax Codex forced plan mode for the analysis skills (qa, explain)

## Context

t861 added the Codex `default_mode_request_user_input` feature flag to the
`ait setup` seed; t862 updated the website caveats positively but left an
"under review" hedge pending an end-to-end investigation. This task is that
investigation: decide whether the framework's forced plan-mode handling for
Codex is still needed, then act on the decision and remove the hedge.

### Investigation findings (research complete)

**Web research (codex-cli 0.135.0 installed locally):**
- `default_mode_request_user_input` is **merged** (PR #12735, Feb 2026) and
  **enabled by default** — `codex features list` shows it `under development /
  true`. So `request_user_input` *is available* in Codex default mode now.
- BUT the merging PR instructs default mode to *"prefer assumptions first and
  use `request_user_input` only when a question is unavoidable."* The tool is
  available, but the model is biased **against** asking — a reliability risk
  for load-bearing checkpoints. The flag is also "under development" (the
  sibling `collaboration_modes` flag is already "removed"), so behavior may
  change.

**Code/skill analysis:**
- The *actual* forced-plan-mode enforcement is **only** the `/plan` typing in
  `aitask_codex_plan_invoke.py`, reached from the codex arms of
  `aitask_codeagent.sh` and `aitask_skillrun.sh`.
- `.agents/skills/codex_interactive_prereqs.md` is **orphaned** — no skill
  body, instruction layer, or template references it by name (only the
  setup/install copy loops do). Its "STOP if not in plan mode" text enforces
  nothing at runtime.
- `.agents/skills/codex_tool_mapping.md` (referenced live by skill bodies,
  e.g. `aitask-explain`) still says `request_user_input` *"Only works in
  Suggest mode"* — a stale claim that, left as-is, would make a Codex agent
  running `explain` in default mode believe its prompts won't surface.
- Per-skill interactive stakes: **pick/explore = HIGH** (gate the
  non-skippable commit Step 8 + merge Step 9); **qa = MEDIUM**, **explain =
  LOW** (read-only analysis, no commit/merge gating).

### Decision (confirmed with user)

**Relax forced plan mode for `qa` and `explain`; keep it for `pick` and
`explore`** (and, in `skillrun`, for every other skill — status quo
preserved). The live interactive smoke test is **deferred to a
manual-verification follow-up** queued at Step 8c.

Rationale: pick/explore gate irreversible commit/merge prompts that must
reliably surface — plan mode guarantees that and benefits the planning itself.
qa/explain are read-only analysis whose few prompts are low-stakes, and they
benefit from default mode (no plan-mode tool restrictions). Removing plan mode
*entirely* was rejected: the flag is under development and default mode
prefers assumptions, so the high-stakes gates stay protected.

## Implementation

### 1. New shared policy lib — `.aitask-scripts/lib/codex_plan_policy.sh`

Single source of truth for the relaxed-skill set (mirrors the predicate style
of `lib/agent_skills_paths.sh`). Double-source guard per shell conventions.

```bash
#!/usr/bin/env bash
# Policy: which Codex CLI skills launch through plan mode.
# Planning skills (pick, explore) use the /plan PTY helper so the load-bearing
# commit/merge approval prompts reliably surface. Read-only analysis skills
# (qa, explain) run in Codex default mode, where request_user_input is
# available via the default_mode_request_user_input feature flag.
[[ -n "${_AIT_CODEX_PLAN_POLICY_LOADED:-}" ]] && return 0
_AIT_CODEX_PLAN_POLICY_LOADED=1

# codex_skill_forces_plan_mode <skill>  — accepts "qa" or "aitask-qa".
# Returns 0 (force plan mode) for everything except qa/explain (return 1).
codex_skill_forces_plan_mode() {
    case "${1#aitask-}" in
        qa|explain) return 1 ;;
        *)          return 0 ;;
    esac
}
```

### 2. `aitask_codeagent.sh`

- Source the new lib alongside the existing `lib/*.sh` sources (top of file).
- Restructure the `codex)` arm of the `case "$PARSED_AGENT"` (currently
  ~432-458): keep `batch-review|raw` as passthrough; for the skill ops build
  the `$aitask-*` prompt as today, then branch once on the predicate:
  ```bash
  codex)
      case "$operation" in
          batch-review|raw)
              CMD+=("${args[@]}")
              ;;
          *)
              local prompt
              case "$operation" in
                  pick)    prompt=$(build_skill_prompt "\$aitask-pick" "${args[@]}") ;;
                  explain) prompt=$(build_skill_prompt "\$aitask-explain" "${args[@]}") ;;
                  qa)      prompt=$(build_skill_prompt "\$aitask-qa" "${args[@]}") ;;
                  explore) prompt=$(build_skill_prompt "\$aitask-explore") ;;
              esac
              if codex_skill_forces_plan_mode "$operation"; then
                  CMD=("python3" "$SCRIPT_DIR/aitask_codex_plan_invoke.py" "--prompt" "$prompt" "--" "$binary" "$model_flag" "$cli_id")
              else
                  CMD=("$binary" "$model_flag" "$cli_id" "$prompt")
              fi
              ;;
      esac
      ;;
  ```
  Net effect: pick/explore still go through the `/plan` helper; qa/explain
  launch directly as `codex -m <id> "$aitask-qa <args>"` (interactive default
  mode). No defensive `-c features...` override — rely on the seed + on-by-
  default flag, respecting user config.

### 3. `aitask_skillrun.sh`

- Source the new lib alongside the existing `lib/*.sh` sources.
- In the `codex)` launch arm (~233-239), branch on the predicate (`$skill` is
  already the bare name, line 121). Only resolve Python on the helper path:
  ```bash
  codex)
      codex_prompt="\$${full_skill} ${forwarded}"
      if codex_skill_forces_plan_mode "$skill"; then
          PYTHON="$(require_ait_python)"
          CMD=("$PYTHON" "$SCRIPT_DIR/aitask_codex_plan_invoke.py" "--prompt" "$codex_prompt" "--" "$binary" "$model_flag" "$cli_id")
      else
          CMD=("$binary" "$model_flag" "$cli_id" "$codex_prompt")
      fi
      ;;
  ```

### 4. `aitask_codex_plan_invoke.py` — **no change** (still used by pick/explore + all other skillrun skills).

### 5. Codex helper docs

- `.agents/skills/codex_tool_mapping.md`: update the `request_user_input` row
  note from *"Only works in Suggest mode"* to: available in default mode via
  the `default_mode_request_user_input` feature `ait setup` enables (and in
  plan/Suggest mode); in default mode the model prefers assumptions, so
  reserve prompts for unavoidable decisions.
- `.agents/skills/codex_interactive_prereqs.md`: rewrite the blanket "Plan
  Mode Required / STOP" text to an accurate, current-state note —
  `request_user_input` works in default mode; the wrapper additionally
  launches the planning skills (pick/explore) through plan mode. (This file is
  orphaned; full removal + its setup/install copy loops is flagged as a
  follow-up, not done here, to avoid scope-creep into the install flow.)

### 6. Website docs — remove the t862 "under review" hedges

- `website/content/docs/installation/known-issues.md` (~line 25 blockquote):
  replace the hedge with a positive current-state statement — planning skills
  (`pick`, `explore`) launch through plan mode (reliable commit/merge prompts +
  planning benefit); analysis skills (`qa`, `explain`) run in default mode via
  `default_mode_request_user_input`.
- `website/content/docs/commands/codeagent.md` (~line 155): drop "under
  review"; rewrite the PTY-helper paragraph so the enumeration is `pick` and
  `explore` (helper / `/plan`), and `qa`/`explain` are launched directly in
  default mode; `raw`/`batch-review` stay passthrough.
- The 7 softened per-skill blockquotes and getting-started/_index edits from
  t862 stay as-is (still accurate).

### 7. Tests

- `tests/test_codeagent.sh`:
  - Add `codex_plan_policy.sh` to the lib files copied into the test fixture
    (alongside the existing copied libs / `aitask_codex_plan_invoke.py`).
  - **Test 11c** → narrow to "explore still uses the plan-mode helper" (keep
    the pick assertions in 11b).
  - **New Test 11d** — qa/explain launch directly: `assert_contains` the
    `$aitask-qa` / `$aitask-explain` prompt + the codex binary, and
    `assert_not_contains "aitask_codex_plan_invoke"` (helper already in the lib).
- `tests/test_skillrun_codex_planmode.sh` (new, minimal): using `--dry-run`,
  assert `skillrun qa` → no `aitask_codex_plan_invoke` and `skillrun pick` →
  uses it. If skillrun's profile/model resolution makes a hermetic fixture
  impractical, document that the shared predicate (covered by test_codeagent)
  is the guarantee and drop this file — recorded as a deviation in the plan.

## Manual-verification follow-up (Step 8c)

Queue a `manual_verification` task (the deferred live smoke test) with a
checklist: launch `ait codeagent invoke qa <id>` and `... explain <path>` with
a `codex/*` agent string, confirm Codex runs in **default mode** and a
`request_user_input` prompt actually surfaces; confirm `pick`/`explore` still
enter plan mode (composer shows `/plan`).

## Verification

- `bash tests/test_codeagent.sh` (+ new skillrun test) pass.
- `shellcheck .aitask-scripts/aitask_codeagent.sh .aitask-scripts/aitask_skillrun.sh .aitask-scripts/lib/codex_plan_policy.sh` clean.
- Manual dry-runs:
  - `./.aitask-scripts/aitask_codeagent.sh --agent-string codex/gpt5_4 --dry-run invoke qa 42` → no `aitask_codex_plan_invoke`, contains `$aitask-qa 42` + codex binary.
  - same for `explain src/x.py`; `invoke pick 42` / `invoke explore` still show the helper.
- `cd website && hugo build --gc --minify` builds clean.
- `grep -rn -i "under review" website/content/docs/commands/codeagent.md website/content/docs/installation/known-issues.md` → none.
- `grep -rn -i "only works in suggest mode\|only available in plan mode" .agents/skills/ website/content/docs/` → no stale Codex claims (OpenCode plan-mode mentions expected to remain).
- `./.aitask-scripts/aitask_skill_verify.sh` clean (no `.j2`/stub/golden surfaces touched — confirms no regression).

## Step 9 (Post-Implementation)

Profile 'fast', current branch — no worktree/branch cleanup. Commit code +
docs with `chore: <desc> (t866)`; commit the plan with `./ait git`; run Step 8b
(upstream-defect follow-up — flag the orphaned `codex_interactive_prereqs.md`
removal) and Step 8c (manual-verification follow-up above); then
`./.aitask-scripts/aitask_archive.sh 866` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Relaxed forced Codex plan mode for the analysis skills
  (`qa`, `explain`) while keeping it for the planning skills (`pick`,
  `explore`) and every other skill:
  - New `.aitask-scripts/lib/codex_plan_policy.sh` — single-source predicate
    `codex_skill_forces_plan_mode` (returns 1 for qa/explain, 0 otherwise),
    accepting both bare (`qa`) and full (`aitask-qa`) names.
  - `aitask_codeagent.sh` — sourced the lib; restructured the `codex)` case so
    skill ops build the `$aitask-*` prompt then branch on the predicate
    (helper vs. direct `codex -m <id> "$aitask-* …"`); `batch-review`/`raw`
    stay passthrough.
  - `aitask_skillrun.sh` — sourced the lib; the `codex)` arm branches on the
    predicate (Python resolved only on the helper path).
  - `.agents/skills/codex_tool_mapping.md` (live-referenced) and
    `.agents/skills/codex_interactive_prereqs.md` (orphaned) — rewrote the
    stale "only works in Suggest/plan mode" claims to current state.
  - `website/.../known-issues.md` + `.../commands/codeagent.md` — replaced the
    t862 "under review" hedges with the resolved behavior.
  - Tests: `tests/test_codeagent.sh` (Test 11c narrowed to explore; new 11c2
    asserts qa/explain are direct; added `codex_plan_policy.sh` to the fixture
    lib copy) and new `tests/test_skillrun_codex_planmode.sh` (dry-run parity).
- **Deviations from plan:** None of substance. Chose a shared lib over inline
  duplication after confirming the scaffold tests never exec
  codeagent/skillrun (so a new sourced lib is scaffold-safe). The skillrun
  test runs against the real repo via side-effect-free `--dry-run` (a hermetic
  fixture was unnecessary).
- **Issues encountered:** `codex_interactive_prereqs.md` turned out to be
  **orphaned** — no skill body, instruction layer, or template references it;
  the actual plan-mode enforcement is solely the `/plan` typing in
  `aitask_codex_plan_invoke.py`. Rewrote it for accuracy rather than expanding
  scope into the install-flow copy loops.
- **Key decisions:** No defensive `-c features.default_mode_request_user_input=true`
  on the direct launches — rely on the seed + codex's on-by-default flag,
  respecting user config. Kept plan mode for all non-qa/explain skillrun skills
  (status quo; out of scope to re-evaluate fold/review/etc.).
- **Verification:** `test_codeagent.sh` 89/89; `test_skillrun_codex_planmode.sh`
  9/9; `shellcheck -S warning` clean on all touched scripts; `aitask_skill_verify.sh`
  OK; `hugo build --gc --minify` clean; grep confirms no remaining hedges/stale
  claims. The live interactive smoke test is deferred to a manual-verification
  follow-up (Step 8c).
- **Upstream defects identified:** `.agents/skills/codex_interactive_prereqs.md:1` —
  orphaned doc (referenced only by the setup/install copy loops in
  `aitask_setup.sh:1766` and `install.sh:482`); cleanly removing it + its copy
  loops + the aidocs reference is a follow-up cleanup candidate, deferred here
  to avoid scope-creep into the install flow.
