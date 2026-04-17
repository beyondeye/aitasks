---
name: aitask-add-model
description: Register a known code-agent model in models_<agent>.json, optionally promote it to default across config/seed/DEFAULT_AGENT_STRING.
---

Companion to `aitask-refresh-code-models`. Where that skill discovers
models via web research, this one skips research and takes known inputs
(e.g., a just-announced Opus release) to:

- **Add mode** — append the model to `aitasks/metadata/models_<agent>.json`
  and the matching `seed/` file.
- **Promote mode** — in addition, patch `codeagent_config.json` defaults
  for listed ops and, for `claudecode`, update `DEFAULT_AGENT_STRING` in
  `.aitask-scripts/aitask_codeagent.sh`.

All writes go through `.aitask-scripts/aitask_add_model.sh`. The helper
is idempotent (errors clearly on duplicates), atomic (tempfile + `mv`),
and supports `--dry-run` that prints unified diffs and leaves the
filesystem untouched.

## Workflow

### Step 1: Parse Inputs

If invoked with CLI flags, parse them directly. Supported flags:

- `--agent <name>` — one of `claudecode`, `geminicli`, `codex`
- `--name <id>` — lowercase, `^[a-z][a-z0-9_]*$` (e.g., `opus4_7`)
- `--cli-id <id>` — exact CLI model ID (e.g., `claude-opus-4-7`)
- `--notes "<text>"` — one-line description
- `--promote` — also update config defaults + `DEFAULT_AGENT_STRING`
- `--promote-ops <csv>` — required with `--promote`; comma-separated ops
  (e.g., `pick,explore,brainstorm-explorer`)
- `--dry-run` — preview only, no writes

If any required input is missing, collect it via `AskUserQuestion`:

- **agent** — options: `claudecode`, `geminicli`, `codex`, `opencode (not supported — use aitask-refresh-code-models)`
- **name** — free text, validate client-side against the regex
- **cli-id** — free text
- **notes** — free text
- **mode** — `Add only` vs. `Add and promote to default`
- **promote-ops** (if promote) — multiSelect from the keys present in
  `aitasks/metadata/codeagent_config.json` under `.defaults` (read the
  file to enumerate)

### Step 2: Validate Inputs

Refuse `--agent opencode` with a pointer to `aitask-refresh-code-models`
(opencode models are provider-gated and CLI-discovered). Validate the
name regex and non-empty `cli-id`. The helper also validates, so this
step mainly provides clearer errors before invocation.

Check the target registry for duplicates:

```bash
jq -e --arg n "<name>" 'any(.models[]?; .name == $n)' \
  aitasks/metadata/models_<agent>.json
```

If the model name already exists, abort with a message — the add step
will fail anyway, and the user needs to either pick a new name or skip
to `promote-config` manually.

### Step 3: Compute Proposed Changes (Dry Run)

Always run a dry-run first to show the user what will change:

```bash
./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
  --agent <agent> --name <name> --cli-id <cli-id> --notes "<notes>"
```

If promoting, also:

```bash
./.aitask-scripts/aitask_add_model.sh promote-config --dry-run \
  --agent <agent> --name <name> --ops <csv>
```

And for `claudecode` only:

```bash
./.aitask-scripts/aitask_add_model.sh promote-default-agent-string --dry-run \
  --agent claudecode --name <name>
```

Show the diffs to the user. If the user passed `--dry-run`, stop here.

### Step 4: Confirm and Apply

If not already a dry-run, use `AskUserQuestion`:

- Question: `Apply these changes?`
- Header: `Confirm`
- Options:
  - `Apply` (description: `Write the changes shown in the dry-run above`)
  - `Abort` (description: `Make no changes`)

If `Apply`, run the same subcommands without `--dry-run`. Subcommand
order when promoting:

1. `add-json` — registers the model
2. `promote-config` — updates `codeagent_config.json` (and seed)
3. `promote-default-agent-string` — updates
   `.aitask-scripts/aitask_codeagent.sh` (claudecode only)

### Step 5: Manual-Review Reminder (promote mode only)

After a successful promote-mode apply, print the following block
verbatim so the user knows which files are out of scope for this skill
and require manual review:

```
Manual review needed — the following files reference the default model
string but are NOT patched by this skill:

  - aidocs/claudecode_tools.md:5         (display name + cli_id)
  - tests/test_codeagent.sh              (model-resolution assertions)
  - tests/test_brainstorm_crew.py        (default agent_string fixtures)
  - website/content/docs/commands/codeagent.md  (user-facing docs)

Full audit: aidocs/model_reference_locations.md
```

Skip this block for add-only mode (nothing beyond the registry changed).

### Step 6: Commit

Commit in two groups. The metadata and seed registry files live on the
task-data branch (via `./ait git`); the script, SKILL, and test live on
`main` (via plain `git`).

**Registry + config (task-data branch):**
```bash
./ait git add aitasks/metadata/models_<agent>.json
# If promote mode:
./ait git add aitasks/metadata/codeagent_config.json
./ait git commit -m "ait: Register <agent>/<name> and promote to default"
```

**Seed sync (main branch):**
```bash
git add seed/models_<agent>.json
# If promote mode:
git add seed/codeagent_config.json
git commit -m "ait: Sync <agent>/<name> registration to seed"
```

**DEFAULT_AGENT_STRING (main branch, promote mode + claudecode only):**
```bash
git add .aitask-scripts/aitask_codeagent.sh
git commit -m "refactor: Promote <agent>/<name> as hardcoded DEFAULT_AGENT_STRING"
```

Only include groups that actually changed. Skip unchanged files.

### Step 7: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see
`.claude/skills/task-workflow/satisfaction-feedback.md`) with
`skill_name` = `"add-model"`.

## Notes

- `aitask-refresh-code-models` discovers models via web research and
  only updates registries. This skill takes known inputs and can also
  promote to default — the two complement each other.
- `opencode` is rejected on purpose: OpenCode models are gated by the
  provider config and are discovered exclusively via its CLI, so manual
  registration here would be misleading.
- `promote-config` only patches keys that already exist under
  `.defaults`. Seed's `codeagent_config.json` has only the canonical 6
  ops, so brainstorm keys are silently skipped in seed — this is
  intended so that the seed stays minimal.
- `promote-default-agent-string` is `claudecode`-only because only
  `.aitask-scripts/aitask_codeagent.sh` hardcodes a default fallback.
- All writes are atomic: subcommands write to a tempfile, validate JSON
  with `jq .`, then `mv` into place. `--dry-run` uses the same pipeline
  but prints a unified diff instead of moving.
- Tests: `bash tests/test_add_model.sh` (6 groups, TMPDIR-isolated via
  `AITASK_REPO_ROOT` env var).
