---
Task: t1162_2_work_report_codeagent_operation.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_3_work_report_skill_and_wrappers.md, aitasks/t1162/t1162_4_board_w_work_report_flow.md, aitasks/t1162/t1162_5_work_report_documentation.md, aitasks/t1162/t1162_6_manual_verification_add_manager_facing_work_report_skill_and.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_1_work_report_gatherer_helper.md
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-22 18:49
---

# Plan: t1162_2 — `work-report` code-agent operation + dry-run tests + whitelisting

## Context

Registers `work-report` as a configurable read-only code-agent operation
(Claude Code, Codex, OpenCode), seeds its lightweight default model, and
whitelists the t1162_1 gatherer helper. Parent design:
`aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`
(t1162_2 section). The board (t1162_4) resolves its launch command through
this registration via `aitask_codeagent.sh --dry-run invoke work-report …`.

Plan verified against current `main` on 2026-07-22 — all line references and
file formats below re-checked against live source (see Verification notes).

## Design decisions

**D1 — Whitespace in passthrough args is rejected fail-closed (review
concern).** All three agents compose the slash command by flattening argv
into one whitespace-joined string (`${args[*]}` claudecode/opencode;
`build_skill_prompt`'s `"$*"` for codex, `aitask_codeagent.sh:399`). An
argument containing whitespace therefore loses its boundary undetectably —
`--columns "my col"` (one shell argument) arrives at the skill as two
tokens. The values at stake are identity fields that must round-trip
(column IDs, task IDs), so silent coercion is not an option; the text
protocol simply cannot represent them. Policy:

- Board-generated column IDs are safe **by construction** — the board
  slugifies to `[a-z0-9_]`, max 20 chars (`ColumnEditScreen._generate_col_id`,
  `aitask_board.py:4128-4144`) — and task IDs are numeric. The hazard is a
  hand-edited `board_config.json` ID containing whitespace.
- The `work-report` arm **rejects** any passthrough arg matching
  `[[:space:]]` with a distinct usage error (die), at the top of
  `build_invoke_command`'s work-report handling — once, agent-independent,
  BEFORE per-agent dispatch. Checked even under `--dry-run` so the refusal
  is unit-testable (same precedent as the explore-relay env prechecks,
  comment at `aitask_codeagent.sh:473-474`).
- Scope-honest: the same flattening exists for every skill-launch operation
  (pick, explain, qa, …) but changing their behavior is out of scope; the
  guard is work-report-only, where the passthrough contract is pinned.
  The pre-existing shared hazard is recorded for the plan's Final
  Implementation Notes "Upstream defects" bullet.

## Changes

1. **`.aitask-scripts/aitask_codeagent.sh`**
   - Add `work-report` to `SUPPORTED_OPERATIONS` (line 26). `cmd_resolve` and
     `cmd_invoke` both validate against this array — no separate list to edit.
   - Add a `work-report` arm in `build_invoke_command` for each agent,
     composing `/aitask-work-report <args>` with all passthrough args
     (`--columns`/`--tasks` values arrive as plain positional passthrough).
     Model on the `explain` arms (verified locations):
     Before the per-agent dispatch, add the D1 whitespace guard:
     ```bash
     if [[ "$operation" == "work-report" ]]; then
         local wr_arg
         for wr_arg in "${args[@]}"; do
             [[ "$wr_arg" =~ [[:space:]] ]] && die "work-report argument contains whitespace — slash-command text cannot preserve argument boundaries: '$wr_arg'"
         done
     fi
     ```
     - claudecode (~435-438): `CMD+=("/aitask-work-report ${args[*]}")`
     - codex: the outer `*` arm (line 505) already routes non-batch ops to the
       skill-prompt composer in **default mode** (the comment at ~506-509
       documents why there is no plan-mode forcing). The required change is an
       arm in the **inner** `case "$operation"` (lines 511-518):
       `work-report) prompt=$(build_skill_prompt "\$aitask-work-report" "${args[@]}") ;;`
       **Without it, `prompt` expands empty and the command is broken** —
       this arm IS the change; keep default mode (no plan-mode flag), pinned
       by a test.
     - opencode (~528-529): `CMD+=("--prompt" "/aitask-work-report ${args[*]}")`
   - Update the operation enumeration in `show_help` (lines 608-609:
     `Operations: pick, explain, …`). Verified: this is the only prose
     enumeration site.
2. **`.aitask-scripts/lib/agent_command_screen.py`** — add `"work-report"` to
   `_FRESH_WINDOW_OPERATIONS` (lines 64-66).
3. **Per-operation default model (THE "lightweight model class"):**
   - `seed/codeagent_config.json` — add `"work-report": "claudecode/sonnet4_6"`
     to `.defaults` (exactly mirrors the `explain` entry).
   - Live `aitasks/metadata/codeagent_config.json` — same addition (commit via
     `./ait git`, task-data file). Verified: live `.defaults.explain` is also
     `claudecode/sonnet4_6`.
   - Rationale (verified): resolution chain is `--agent-string` flag →
     `codeagent_config.local.json` `.defaults[op]` →
     `codeagent_config.json` `.defaults[op]` → `DEFAULT_AGENT_STRING`
     (`claudecode/opus4_8`, `lib/agent_string.sh:26`). Without the seeded
     entry, work-report silently gets the heavier fallback.
4. **Verified scores:** add `"work-report": <same value as that model's
   "explain">` to the `verified` map of every model **that has an `explain`
   entry** in `seed/models_claudecode.json`, `seed/models_codex.json`,
   `seed/models_opencode.json` AND the live `aitasks/metadata/models_*.json`
   (live maps are richer — mirror each model's live `explain` value). Models
   with an empty `verified: {}` (e.g. seed opus4_7/opus4_8/fable5) stay
   empty — do not invent scores. Live copies commit via `./ait git`.
5. **Whitelist `aitask_work_report_gather.sh` in all 5 touchpoints** (exact
   entry shapes verified against `aitask_audit_wrappers.sh
   helper_present_in_touchpoint`; insert alphabetically among existing
   `aitask_*.sh` entries in each file):
   - `.claude/settings.local.json` and `seed/claude_settings.local.json`:
     `"Bash(./.aitask-scripts/aitask_work_report_gather.sh:*)"`
   - `.codex/rules/default.rules` and `seed/codex_rules.default.rules`:
     `prefix_rule(pattern = ["./.aitask-scripts/aitask_work_report_gather.sh"], decision = "allow", justification = "Aitasks helper script")`
   - `seed/opencode_config.seed.json`:
     `"./.aitask-scripts/aitask_work_report_gather.sh *": "allow"`

   Verification note: the helper is not yet referenced by any skill tree
   (t1162_3 lands `/aitask-work-report`), so the audit's `discover-helpers`
   phase will NOT surface it. Verify the whitelist directly with:
   `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_work_report_gather.sh`
   → expect **no** `MISSING:` lines. Note for t1162_3: re-run the full audit
   once the skill references the helper.

## Tests

Add `tests/test_codeagent_work_report.sh` (the existing `test_codeagent.sh`
is 393 lines — a new file keeps it manageable). Follow its scaffold exactly:
source `tests/lib/test_scaffold.sh` + `tests/lib/asserts.sh`, `setup_test_env`
copies `aitask_codeagent.sh`, `lib/task_utils.sh`, `lib/archive_utils.sh`,
`lib/agent_string.sh`, the three live `aitasks/metadata/models_*.json`,
`seed/codeagent_config.json` (as `aitasks/metadata/codeagent_config.json`)
and `project_config.yaml` into a mktemp repo, `git init`; skip if no `jq`.

- `--dry-run invoke work-report --columns now,next --tasks 12,34` for each of
  the 3 agents (claudecode default; `--agent-string codex/gpt5_4` and
  `--agent-string opencode/<model>` overrides): assert output starts with
  `DRY_RUN:` and contains `/aitask-work-report --columns now,next --tasks
  12,34` verbatim (shell-quoted in the `%q` output — match as
  `aitask-work-report` plus each passthrough token, mirroring how
  test_codeagent.sh Tests 11/11b assert).
- Codex default-mode pin: assert the codex dry-run command contains NO
  plan-mode/sandbox-forcing marker — verified there is currently no `plan`
  token anywhere in a composed codex command, so assert absence of `plan`
  (case-insensitive) and absence of `--sandbox`.
- Resolution equivalence, seeded: `resolve work-report` and `resolve explain`
  both return `AGENT_STRING:claudecode/sonnet4_6`.
- Resolution equivalence, no-config: in a second env WITHOUT
  `codeagent_config.json` (keep `models_*.json` — `resolve` needs them for
  `CLI_ID`), both return `AGENT_STRING:claudecode/opus4_8`
  (`DEFAULT_AGENT_STRING`).
- **D1 whitespace guard:** `--dry-run invoke work-report --columns "my col"`
  (embedded space in ONE shell argument) → nonzero exit, error mentions
  whitespace, and output contains no `DRY_RUN:` line. Assert for the default
  (claudecode) agent AND under `--agent-string codex/gpt5_4` (guard fires
  before per-agent dispatch). Control: `--columns now,next` (no whitespace)
  still dry-runs cleanly — pins that the guard rejects only genuinely
  unrepresentable args.
- Harness self-check: temporarily corrupt one expectation, confirm the suite
  reports FAIL and exits 1, then revert.

## Verification

- `bash tests/test_codeagent.sh` (regression) and
  `bash tests/test_codeagent_work_report.sh` — all PASS.
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist
  aitask_work_report_gather.sh` — no `MISSING:` lines.
- `shellcheck .aitask-scripts/aitask_codeagent.sh` clean.
- `jq .` parses every edited JSON file (settings, seeds, models, config).
- **Verified-score parity assertion** (the mirror rule, checked — not just
  stated): for each of the 6 models files (3 seed + 3 live), assert every
  model's `verified["work-report"]` exactly equals its `verified["explain"]`
  wherever `explain` exists, and that `work-report` is absent wherever
  `explain` is absent:
  ```bash
  for f in seed/models_*.json aitasks/metadata/models_*.json; do
    jq -e '[.models[].verified
            | if has("explain") then (.["work-report"] == .explain)
              else (has("work-report") | not) end] | all' "$f" >/dev/null \
      || echo "PARITY_FAIL:$f"
  done
  ```
  No `PARITY_FAIL:` lines expected. Include this same assertion as a test
  block in `tests/test_codeagent_work_report.sh` (run against the repo's
  real files, not the tmp env) so the parity rule stays pinned.

## Risk

### Code-health risk: low
- `aitask_codeagent.sh` is the load-bearing dispatcher every TUI agent launch
  routes through, but every edit is an additive case arm / array element;
  existing operations are untouched and the regression suite pins them ·
  severity: low · → mitigation: none needed
- The codex composer's inner `case` silently yields an empty prompt for an
  unlisted operation (pre-existing structural hazard); this task adds the
  `work-report` arm and pins it with a dry-run test · severity: low ·
  → mitigation: none needed (covered by test)

### Goal-achievement risk: low
- Slash-command composition flattens argv (`${args[*]}` / `"$*"`), so a
  whitespace-bearing column ID from a hand-edited board config would split
  undetectably; addressed by the D1 fail-closed guard + tests (board-generated
  IDs are slug-safe by construction) · severity: low · → mitigation: none
  needed (covered by D1 guard and tests)
- The gatherer helper is whitelisted before any skill references it, so the
  audit's discovery phase cannot confirm coverage end-to-end until t1162_3
  lands; bounded by verifying with the direct `audit-helper-whitelist` verb
  and an explicit re-audit note for t1162_3 · severity: low ·
  → mitigation: none needed
- All acceptance criteria map to verified source locations (enumeration
  sites, resolution chain, touchpoint formats re-checked this session) ·
  severity: low · → mitigation: none needed

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9.
