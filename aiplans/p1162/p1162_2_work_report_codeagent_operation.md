---
Task: t1162_2_work_report_codeagent_operation.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_1_work_report_gatherer_helper.md, aitasks/t1162/t1162_3_work_report_skill_and_wrappers.md, aitasks/t1162/t1162_4_board_w_work_report_flow.md, aitasks/t1162/t1162_5_work_report_documentation.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_*_*.md
Worktree: aiwork/t1162_2_work_report_codeagent_operation
Branch: aitask/t1162_2_work_report_codeagent_operation
Base branch: main
---

# Plan: t1162_2 — `work-report` code-agent operation + dry-run tests + whitelisting

## Context

Registers `work-report` as a configurable read-only code-agent operation
(Claude Code, Codex, OpenCode), seeds its lightweight default model, and
whitelists the t1162_1 gatherer helper. Parent design:
`aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`
(t1162_2 section). The board (t1162_4) resolves its launch command through
this registration via `aitask_codeagent.sh --dry-run invoke work-report …`.

## Changes

1. **`.aitask-scripts/aitask_codeagent.sh`**
   - Add `work-report` to `SUPPORTED_OPERATIONS` (line ~26).
   - Add a `work-report` arm in `build_invoke_command` (~405-548) for each
     agent, composing the slash command `/aitask-work-report <args>` with all
     passthrough args (`--columns`/`--tasks` values arrive as plain
     positional passthrough). Model the THREE agent blocks on `explain`:
     claudecode ~435-438 (`claude --model <id> "/aitask-explain <args>"`),
     codex ~500-521 (`build_skill_prompt` composer, default mode — the
     comment at ~505-509 documents why NO plan-mode forcing; keep identical
     behavior for work-report: read-only analysis launches in default mode),
     opencode ~528-529 (`--prompt "/aitask-explain <args>"`).
   - Check whether any operation list/help text elsewhere in the script
     (usage string, `resolve` verb validation) enumerates operations — update
     every enumeration site.
2. **`.aitask-scripts/lib/agent_command_screen.py`** — add `"work-report"` to
   `_FRESH_WINDOW_OPERATIONS` (lines ~64-66).
3. **Per-operation default model (THE "lightweight model class"):**
   - `seed/codeagent_config.json` — add `"work-report": "claudecode/sonnet4_6"`
     to `.defaults` (exactly mirrors the `explain` entry).
   - Live `aitasks/metadata/codeagent_config.json` — same addition (commit via
     `./ait git`, task-data file).
   - Rationale (verified during planning): resolution chain is `--agent-string`
     flag → `codeagent_config.local.json` `.defaults[op]` →
     `codeagent_config.json` `.defaults[op]` → `DEFAULT_AGENT_STRING`
     (`claudecode/opus4_8`, `lib/agent_string.sh:26`). Without the seeded
     entry, work-report silently gets the heavier fallback.
4. **Verified scores:** add `work-report` entries to the `verified` maps in
   `seed/models_claudecode.json`, `seed/models_codex.json`,
   `seed/models_opencode.json`, mirroring each model's `explain` value; do the
   same for any live `aitasks/metadata/models_*.json` (commit live copies via
   `./ait git`).
5. **Whitelist `aitask_work_report_gather.sh` in all 5 touchpoints** (formats
   differ per file — copy the entry shape of an existing `aitask_*.sh` helper
   in each):
   - `.claude/settings.local.json` — `Bash(./.aitask-scripts/aitask_work_report_gather.sh:*)`
   - `.codex/rules/default.rules`
   - `seed/claude_settings.local.json`
   - `seed/codex_rules.default.rules`
   - `seed/opencode_config.seed.json`
   Verify with `./.aitask-scripts/aitask_audit_wrappers.sh` (Phase 2 helper
   discovery greps skill trees; the helper becomes referenced when t1162_3
   lands — run the audit here anyway to confirm the whitelist entries parse,
   and note for t1162_3 to re-run it).

## Tests

Extend `tests/test_codeagent.sh` OR add `tests/test_codeagent_work_report.sh`
(prefer a new file if the existing one is long; follow its scaffold —
`tests/lib/asserts.sh`, isolated config dirs):

- `--dry-run invoke work-report --columns now,next --tasks 12,34` for each of
  the 3 agents: assert the `DRY_RUN:` command contains
  `/aitask-work-report --columns now,next --tasks 12,34` verbatim.
- Codex: assert the dry-run command contains NO plan-mode/sandbox-forcing flag
  (mirror however test assertions distinguish default mode today; at minimum
  assert absence of any `plan` mode marker present in other forced-mode ops).
- Resolution equivalence: with the seeded config present, assert
  `aitask_codeagent.sh resolve work-report` == `resolve explain`
  (both `claudecode/sonnet4_6`); with configs absent (point the script at an
  empty temp metadata dir), assert both fall back to the same
  `DEFAULT_AGENT_STRING` (`AGENT_STRING:claudecode/opus4_8`).

## Verification

- `bash tests/test_codeagent.sh` (and the new test file) — all PASS.
- `./.aitask-scripts/aitask_audit_wrappers.sh` — no missing-touchpoint
  complaints for `aitask_work_report_gather.sh`.
- `shellcheck .aitask-scripts/aitask_codeagent.sh` clean.

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9.
