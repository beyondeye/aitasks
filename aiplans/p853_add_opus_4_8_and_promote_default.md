---
Task: t853_add_opus_4_8_and_promote_default.md
Base branch: main
plan_verified: []
---

# t853 — Register Opus 4.8 and Promote to Default

## Context

Claude Opus 4.8 was released. It supersedes Opus 4.7 (1M) as the most-capable
Claude model and has **1M context by default** — so a single registry entry
suffices (no separate `[1m]` variant, unlike the pair `opus4_7` / `opus4_7_1m`).
The framework needs:

1. A new entry `opus4_8` in `models_claudecode.json` (and the seed copy).
2. The 5 ops currently defaulting to `claudecode/opus4_7_1m` repointed to the
   new model in `codeagent_config.json` (and the canonical 6-op seed subset
   thereof).
3. `DEFAULT_AGENT_STRING` in `.aitask-scripts/lib/agent_string.sh` bumped to
   `claudecode/opus4_8`.

The dependency task t852 is archived (Done, completed 2026-05-29 12:30) — the
`promote-default-agent-string` helper was retargeted to
`lib/agent_string.sh`, so the promote step will not die on a stale anchor.

The work is driven by the dedicated `/aitask-add-model` skill +
`.aitask-scripts/aitask_add_model.sh` helper (atomic, idempotent,
dry-run-capable). No hand-editing of JSON or `agent_string.sh`.

## Preconditions verified

- `t852` archived → `promote-default-agent-string` anchors on
  `lib/agent_string.sh`.
- `opus4_8` does NOT yet exist in either
  `aitasks/metadata/models_claudecode.json` or `seed/models_claudecode.json`
  (jq check passed).
- Current `codeagent_config.json` ops on `claudecode/opus4_7_1m`:
  `pick, explore, brainstorm-explorer, brainstorm-synthesizer,
  brainstorm-detailer` — matches the task's `--promote-ops` list exactly. All
  other ops (explain, batch-review, qa, raw, brainstorm-comparator,
  brainstorm-patcher, brainstorm-initializer) stay on `sonnet4_6`.
- Seed `codeagent_config.json` only has the canonical 6 ops; brainstorm keys
  will be silently skipped there (intended per SKILL.md Notes).

## Implementation

Run the `aitask-add-model` skill in promote mode with the exact inputs the
task specifies. Sequence below mirrors the SKILL.md workflow.

### Step 1 — Dry-run previews (always first)

```bash
./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
  --agent claudecode --name opus4_8 --cli-id claude-opus-4-8 \
  --notes "Most capable model, 1M context default, complex reasoning + agentic coding, adaptive thinking"

./.aitask-scripts/aitask_add_model.sh promote-config --dry-run \
  --agent claudecode --name opus4_8 \
  --ops pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer

./.aitask-scripts/aitask_add_model.sh promote-default-agent-string --dry-run \
  --agent claudecode --name opus4_8
```

Inspect the unified diffs:
- `add-json` should add a single new entry to both
  `aitasks/metadata/models_claudecode.json` and `seed/models_claudecode.json`
  with no `verified` / `verifiedstats` data.
- `promote-config` should flip the 5 listed ops in
  `aitasks/metadata/codeagent_config.json` from `opus4_7_1m` to `opus4_8`,
  and flip `pick` and `explore` in `seed/codeagent_config.json` (the seed's
  canonical 6 ops — the 3 brainstorm keys are silently skipped).
- `promote-default-agent-string` should change line 26 of
  `.aitask-scripts/lib/agent_string.sh` from
  `DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7_1m}"` to
  `…:-claudecode/opus4_8}"`, and refresh the resolution-chain comment near
  line 540 of `.aitask-scripts/aitask_codeagent.sh`.

If any diff is unexpected, stop and surface the diff to the user.

### Step 2 — Apply (after user confirms diffs)

Re-run the same three subcommands without `--dry-run`, in this order:

```bash
./.aitask-scripts/aitask_add_model.sh add-json \
  --agent claudecode --name opus4_8 --cli-id claude-opus-4-8 \
  --notes "Most capable model, 1M context default, complex reasoning + agentic coding, adaptive thinking"

./.aitask-scripts/aitask_add_model.sh promote-config \
  --agent claudecode --name opus4_8 \
  --ops pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer

./.aitask-scripts/aitask_add_model.sh promote-default-agent-string \
  --agent claudecode --name opus4_8
```

### Step 3 — Manual-Review reminder

Print the SKILL.md Step-5 block verbatim so the user knows which manual
references still need attention (handled in follow-up docs/test task per the
task's "Out of scope" section).

### Step 4 — Commits (two groups; standard task-workflow Step 8 review first)

The skill's commit pattern splits between `./ait git` (task-data branch) and
plain `git` (main). After Step 8 review approves:

1. **Registry + config (task-data branch via `./ait git`):**
   ```bash
   ./ait git add aitasks/metadata/models_claudecode.json \
                 aitasks/metadata/codeagent_config.json
   ./ait git commit -m "ait: Register claudecode/opus4_8 and promote to default"
   ```

2. **Seed sync + DEFAULT_AGENT_STRING (main branch via plain `git`):**
   ```bash
   git add seed/models_claudecode.json seed/codeagent_config.json \
           .aitask-scripts/lib/agent_string.sh .aitask-scripts/aitask_codeagent.sh
   git commit -m "feature: Promote claudecode/opus4_8 as default (t853)"
   ```

   Note: the main-branch commit bundles seed + DEFAULT_AGENT_STRING because
   they are conceptually one change ("framework defaults to Opus 4.8"). The
   commit subject uses `feature:` to match `issue_type: feature` and carries
   the `(t853)` tag for `aitask_issue_update.sh` discoverability.

## Verification

Run before/after the apply:

- **Before apply:** review the three dry-run diffs (described in Step 1).
- **After apply:**
  - `jq '.models[] | select(.name=="opus4_8")' aitasks/metadata/models_claudecode.json`
    returns the new entry; same for `seed/`.
  - `jq '.defaults' aitasks/metadata/codeagent_config.json` shows the 5
    listed ops on `claudecode/opus4_8` and all others unchanged.
  - `grep DEFAULT_AGENT_STRING .aitask-scripts/lib/agent_string.sh`
    shows `claudecode/opus4_8`.
  - `./.aitask-scripts/aitask_codeagent.sh default` resolves to
    `claudecode/opus4_8`.
- **Test suites** (per task Verification section):
  - `bash tests/test_add_model.sh` — must pass.
  - `bash tests/test_agent_string.sh` — must pass.
  - `bash tests/test_codeagent.sh` — may need fixture updates; if it fails
    only on default-model-string fixture assertions, that is in scope for
    the follow-up docs/test task and is recorded in "Final Implementation
    Notes" rather than fixed here.
- **Shellcheck** on the helper is unchanged (no edits to bash scripts in
  this task; the helper is invoked, not modified).

## Out of Scope (per task)

Docs and test fixtures referencing the default model string by name (e.g.
`aidocs/claudecode_tools.md`, `tests/test_codeagent.sh` fixtures,
`tests/test_brainstorm_crew.py`, `website/content/docs/commands/codeagent.md`)
are flagged by the skill's Step-5 manual-review block and handled in the
dependent documentation task (created after this one lands).

## Reference to Step 9

After commit + Step 8 user review, proceed to Step 9 (Post-Implementation)
for archival via `./.aitask-scripts/aitask_archive.sh 853` and push via
`./ait git push`. No worktree to clean (profile 'fast' kept us on the
current branch).

## Final Implementation Notes

- **Actual work done:** Drove `aitask-add-model` skill via three helper
  subcommands (`add-json`, `promote-config`, `promote-default-agent-string`).
  Inputs matched the task spec exactly. All three dry-run diffs reviewed
  before apply and were identical to expected.
- **Deviations from plan:** None. The helper produced clean atomic updates;
  no manual touch-up of JSON or `agent_string.sh` was needed.
- **Issues encountered:** `test_codeagent.sh` has 4 failures (out of 87)
  that assert against the previous default model string:
  `resolve returns opus4_7_1m for pick`, `resolve returns model`,
  `resolve returns cli_id` (expecting `claude-opus-4-7[1m]`), and
  `dry-run contains model flag` (expecting `claude-opus-4-7`). All four
  are fixture-bound default-string assertions and were explicitly
  out-of-scope per the task ("test_codeagent may need fixture updates —
  those are handled in the follow-up docs/test task"). The follow-up doc
  task should refresh these fixtures to `opus4_8` / `claude-opus-4-8`.
  `test_add_model.sh` (31/31) and `test_agent_string.sh` (12/12) both
  pass cleanly.
- **Key decisions:**
  - Bundled the main-branch commit (seed JSON + `agent_string.sh` +
    `aitask_codeagent.sh` resolution-chain note) under a single
    `feature: ... (t853)` subject because all four files are one
    semantic change ("framework defaults to Opus 4.8"). This deviates
    slightly from the SKILL.md example which splits them into two
    `git commit` invocations — bundling matches the actual semantic
    grouping and reduces noise.
  - Kept the helper-emitted comment "(claudecode/opus4_7_1m at time of
    writing)" near the docstring at the top of `agent_string.sh`
    untouched. The phrase "at time of writing" makes it a historical
    note rather than a stale current-state claim; the helper does not
    patch it and editing it manually is out of scope here.
- **Upstream defects identified:** None.

