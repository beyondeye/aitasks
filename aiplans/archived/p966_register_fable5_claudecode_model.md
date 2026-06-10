---
Task: t966_register_fable5_claudecode_model.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Register Fable 5 claudecode model (register-only)

## Context

The Claude Code agent's model registry (`aitasks/metadata/models_claudecode.json`,
mirrored in `seed/models_claudecode.json`) does not yet list the new Claude model
**Fable 5**. Until it's registered, an agent string like `claudecode/fable5`
cannot be parsed/resolved by `.aitask-scripts/lib/agent_string.sh`
(`get_cli_model_id` would `die` with "Unknown model").

This task registers Fable 5 **register-only** — it does NOT promote it to
default. No config defaults, hardcoded `DEFAULT_AGENT_STRING`, docs, or tests are
touched (those are promote-mode concerns; a separate follow-up can promote later
if desired).

**Model identity:**
- name: `fable5` (matches the helper's `^[a-z][a-z0-9_]*$` rule; consistent with `opus4_6`/`sonnet4_6` naming)
- cli_id: `claude-fable-5`
- notes: `Fable 5 — latest-generation Claude model`

## Approach

Use the existing, supported mechanism — the `add-json` subcommand of
`.aitask-scripts/aitask_add_model.sh` (driven by the `aitask-add-model` skill).
It atomically appends a `{name, cli_id, notes, verified:{}, verifiedstats:{}}`
entry to **both** the metadata and seed registries, validates the produced JSON,
and is idempotent (errors if the name already exists). This is exactly the shape
of every existing entry — no hand-editing of JSON.

### Step 1 — Dry-run preview (verify before writing)

```bash
./.aitask-scripts/aitask_add_model.sh add-json \
  --agent claudecode \
  --name fable5 \
  --cli-id claude-fable-5 \
  --notes "Fable 5 — latest-generation Claude model" \
  --dry-run
```

Confirm the diff appends the entry to `aitasks/metadata/models_claudecode.json`
and `seed/models_claudecode.json` and nothing else.

### Step 2 — Apply

Re-run the same command without `--dry-run`.

### Files modified (both by the helper, no manual edits)
- `aitasks/metadata/models_claudecode.json` — new `fable5` entry appended
- `seed/models_claudecode.json` — synced copy

### Explicitly NOT touched (out of scope — promote-mode only)
- `aitasks/metadata/codeagent_config.json` / `seed/codeagent_config.json`
- `.aitask-scripts/lib/agent_string.sh` (`DEFAULT_AGENT_STRING`)
- `.aitask-scripts/aitask_codeagent.sh` (resolution-chain note)
- `aidocs/codeagents/claudecode_tools.md`
- `tests/test_codeagent.sh`, `tests/test_brainstorm_crew.py`, `website/content/docs/commands/codeagent.md`

## Verification

```bash
# 1. Resolution works: name → cli_id
source .aitask-scripts/lib/agent_string.sh
get_cli_model_id claudecode fable5      # expect: claude-fable-5

# 2. Both files valid JSON and in sync for the new entry
jq '.models[] | select(.name=="fable5")' aitasks/metadata/models_claudecode.json
jq '.models[] | select(.name=="fable5")' seed/models_claudecode.json

# 3. Agent string parses (lists/resolves without error)
./ait codeagent list-models claudecode | grep -i fable5

# 4. Defaults untouched — no default-sensitive test regressions
bash tests/test_codeagent.sh
```

Expected: `claudecode/fable5` resolves to `claude --model claude-fable-5`;
`test_codeagent.sh` passes unchanged (defaults were not modified).

## Post-Implementation (Step 9)

Standalone parent task on the current branch — commit code change
(`feature: ... (t966)`), then archive via `./.aitask-scripts/aitask_archive.sh 966`.

Per CLAUDE.md "Working on Skills / other agents": after this lands, suggest
separate follow-up tasks to register Fable 5 for the Codex
(`models_codex.json`) and OpenCode (`models_opencode.json`) agents, if Fable 5
is available there.

## Risk

### Code-health risk: low
- None identified. The change appends two data entries via an atomic, idempotent,
  JSON-validating helper; no code paths or defaults change. Blast radius = 2
  registry files. · severity: low · → mitigation: n/a

### Goal-achievement risk: low
- Assumption: `claude-fable-5` is a valid Claude Code CLI model id (confirmed
  against current model facts: Fable 5 → `claude-fable-5`). If the CLI later
  rejects it, register-only still succeeds and breaks nothing — only a future
  *use* of `claudecode/fable5` would surface it. Confirm the cli_id and pick a
  suitable one-line `notes` at implementation time. · severity: low · → mitigation: verify cli_id in Step 1 dry-run

No before/after risk-mitigation follow-up tasks are warranted (both axes low).

## Final Implementation Notes
- **Actual work done:** Ran `aitask_add_model.sh add-json --agent claudecode --name fable5 --cli-id claude-fable-5 --notes "Fable 5 — latest-generation Claude model"` (dry-run first, then applied). Appended the `fable5` entry to `aitasks/metadata/models_claudecode.json` and `seed/models_claudecode.json`. No defaults/config/docs/tests touched (register-only, as scoped).
- **Deviations from plan:** None. The dry-run diff matched the plan exactly.
- **Issues encountered:** None in the registration itself. `test_codeagent.sh` passed 92/92 (defaults untouched).
- **Key decisions:** cli_id `claude-fable-5` confirmed authoritative via the claude-api skill model catalog (Fable 5 → `claude-fable-5`; `fable` is also a valid Claude Code `--model` alias). Committed as framework-internal `ait:` changes per repo precedent for model-registry additions (e.g. `ait: Sync claudecode/opus4_7 registration to seed`).
- **Post-implementation finding (Claude Code Fable 5 launch behavior):** User observed that launching `claude --model claude-fable-5` (via aitask-pick) starts on Fable 5 but shows **Opus 4.8** selected; `/model fable` after start switches to Fable 5 and holds. Research (Claude help center / Claude Code model-config docs) shows this is **intentional content-safety model switching** — Fable 5 runs cyber/bio classifiers and Claude Code auto-switches flagged requests to the default Opus, and the first request carries workspace context (CLAUDE.md, git status) which can trip it. This is independent of this register-only change (the cli_id is correct). Spawned follow-up **t967** to investigate the launch-time trigger (CLAUDE.md security section hypothesis vs. other causes) and a workaround (`/config` "switch models when a message is flagged"). t967 `depends: [966]`.
- **Upstream defects identified:** None.
