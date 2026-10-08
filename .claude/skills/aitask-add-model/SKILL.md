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
  `.aitask-scripts/lib/agent_string.sh` (and the resolution-chain help note
  in `.aitask-scripts/aitask_codeagent.sh`). It also records that the model
  the promotion retires from the seed defaults is **superseded** by the new
  one, in `.aitask-scripts/lib/model_supersessions.json`. That record is a
  global declaration shipped with the framework: on `ait upgrade`, every
  project op still configured with the old model is offered the new one.

All writes go through `.aitask-scripts/aitask_add_model.sh`. The helper
is idempotent (errors clearly on duplicates), atomic (tempfile + `mv`),
and supports `--dry-run` that prints unified diffs and leaves the
filesystem untouched.

## Workflow

### Step 1: Parse Inputs

If invoked with CLI flags, parse them directly. Supported flags:

- `--agent <name>` — one of `claudecode`, `codex`
- `--name <id>` — lowercase, `^[a-z][a-z0-9_]*$` (e.g., `opus4_7`)
- `--cli-id <id>` — exact CLI model ID (e.g., `claude-opus-4-7`)
- `--notes "<text>"` — one-line description
- `--promote` — also update config defaults + `DEFAULT_AGENT_STRING`
- `--promote-ops <csv>` — required with `--promote`; comma-separated ops
  (e.g., `pick,explore,brainstorm-explorer`)
- `--no-supersession` — promote without recording a supersession (see
  Step 3)
- `--dry-run` — preview only, no writes

If any required input is missing, collect it via `AskUserQuestion`:

- **agent** — options: `claudecode`, `codex`, `opencode (not supported — use aitask-refresh-code-models)`
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

If promoting, also — with `--assume-registered`, because the `add-json`
preview above wrote nothing and the new model is not in the registry yet
(only ever on a `--dry-run`; the Step 4 apply call never carries it):

```bash
./.aitask-scripts/aitask_add_model.sh promote-config --dry-run --assume-registered \
  --agent <agent> --name <name> --ops <csv>
```

Promoting an already-registered model (no `add-json` in this run) omits
`--assume-registered`.

The promote-config preview prints one line per supersession decision before
the diffs. Relay them to the user:

- `RECORDED:<agent>/<old>-><agent>/<new>` (and `RECORDED_SIBLING:` for the
  matching `_1m` variants) — upgrading projects still on `<old>` will be
  offered `<new>`.
- `WARN:family:…` — the old and new model names belong to different families
  (e.g. `sonnet5 → opus5_5`). Point it out explicitly: if the promotion is not
  a real succession, the user should apply without recording supersession.
- `SKIPPED:…` — informational (`cross_agent`, `exists`, `no_seed`,
  `sibling_*`).
- `BLOCKED:<reason>:…` — the apply would be **refused**. Resolve it before
  Step 4 with `AskUserQuestion`:
  - `BLOCKED:partial:<agent>/<old>|<ops>` — `<old>` would stay the default of
    the listed seed ops, and a supersession is global. Question: "`<old>` is
    still the seed default for `<ops>`. How should the promotion proceed?",
    Header: `Supersede`, Options: `Also promote <ops>` (re-run this dry-run
    with those ops added to `--ops`) / `Promote without recording supersession`
    (use `--no-supersession` from here on; the lineage can be declared later
    with `record-supersession` once no seed default uses `<old>`) / `Abort`.
  - `BLOCKED:conflict|cycle|seed_invariant:…` — the table already says
    something else. Offer only `Promote without recording supersession` /
    `Abort`; never edit the table to force the new edge in.
  - `BLOCKED:unregistered:…` — the target model is not registered: on an
    add-and-promote run the preview is missing `--assume-registered`; otherwise
    register the model first.

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

In promote mode, when the preview recorded a supersession, add a third
option: `Apply without recording supersession` (description: `Promote the
defaults but declare no lineage — upgrading projects are not offered the new
model`) — it runs `promote-config` with `--no-supersession`.

If `Apply`, run the same subcommands without `--dry-run` (and without
`--assume-registered`). Subcommand order when promoting:

1. `add-json` — registers the model
2. `promote-config` — updates `codeagent_config.json` (and seed) and
   records the supersession
3. `promote-default-agent-string` — updates `DEFAULT_AGENT_STRING` in
   `.aitask-scripts/lib/agent_string.sh` and the resolution-chain note in
   `.aitask-scripts/aitask_codeagent.sh` (claudecode only)

### Step 5: Manual-Review Reminder (promote mode only)

After a successful promote-mode apply, print the block below so the user
knows which files are out of scope for this skill and require manual
review, dropping the lines that do not apply to this promotion:

- drop the whole `claudecode promotions only` group unless `--agent` is
  `claudecode` — those files track the claudecode default and built-in
  fallback, which a `codex` promotion does not change;
- drop the `codebrowser/how-to.md` line unless `qa` is among the
  promote-ops.

Print everything else verbatim.

```
Manual review needed — the following files reference the default model
string but are NOT patched by this skill:

  Any promoted agent:
  - website/content/docs/commands/codeagent.md  (operational-defaults table)
  - website/content/docs/tuis/codebrowser/how-to.md  (states the qa default)

  claudecode promotions only:
  - aidocs/codeagents/claudecode_tools.md:5     (display name + cli_id)
  - .aitask-scripts/lib/roadmap_run.py          (run() agent_string default
                                                 + --agent-string argparse default)
  - website/content/docs/tuis/syncer/_index.md  (matrix-cell examples of the
                                                 built-in fallback)

Re-run both and inspect any failure. Their default-resolution assertions
derive from seed/codeagent_config.json, so the promotion itself should need
no test edits — but other assertions in these files can fail for unrelated
reasons, so do not assume a green run:
  - tests/test_codeagent.sh
  - tests/test_codeagent_work_report.sh

Broader audit: aidocs/framework/model_reference_locations.md — currently
stale; where it disagrees with this list, this list is authoritative.
```

Skip this block for add-only mode (nothing beyond the registry changed).

### Step 6: Commit

Commit in two groups. The metadata and seed registry files live on the
task-data branch (via `./ait git`); the script, SKILL, and test live on
`main` (via plain `git`).

**Registry + config (task-data branch):**
```bash
# Register-only:
./.aitask-scripts/aitask_task_commit.sh -m "ait: Register <agent>/<name>" \
    aitasks/metadata/models_<agent>.json
# Promote mode — name both files in one call:
./.aitask-scripts/aitask_task_commit.sh -m "ait: Register <agent>/<name> and promote to default" \
    aitasks/metadata/models_<agent>.json aitasks/metadata/codeagent_config.json
```

Every path you name is **required**; parse the output per the **outcome
contract** in `.claude/skills/ait-git/SKILL.md`.

The two **main-branch** commits below name their paths as well — `main` is shared
by every session in this checkout, so a `git commit` with no `--` pathspec takes
whatever a concurrent session has staged (see "Never instruct a bare
`git commit` on `main`" in `aidocs/framework/skill_authoring_conventions.md`).

**Seed sync (main branch):**
```bash
git add -- seed/models_<agent>.json    # only when registering a NEW agent (it is untracked)
git commit -m "ait: Sync <agent>/<name> registration to seed" -- <seed_paths>
git show --stat <sha>    # <sha> from the commit's "[<branch> <sha>]" line — not HEAD
```
`<seed_paths>` is `seed/models_<agent>.json`, plus `seed/codeagent_config.json`
in promote mode. The config is already tracked, so it is never `add`ed —
`commit -- <paths>` takes a tracked file's worktree content without one.

**Supersession table (main branch, promote mode, when `promote-config`
printed `NOTE: commit .aitask-scripts/lib/model_supersessions.json`):** the
table is already tracked, so there is no `add`:
```bash
git commit -m "ait: Record <agent>/<name> supersession" \
    -- .aitask-scripts/lib/model_supersessions.json
git show --stat <sha>    # <sha> from the commit's "[<branch> <sha>]" line — not HEAD
```

**DEFAULT_AGENT_STRING (main branch, promote mode + claudecode only):** both
files are already tracked, so there is no `add`:
```bash
git commit -m "refactor: Promote <agent>/<name> as hardcoded DEFAULT_AGENT_STRING" \
    -- .aitask-scripts/lib/agent_string.sh .aitask-scripts/aitask_codeagent.sh
git show --stat <sha>    # <sha> from the commit's "[<branch> <sha>]" line — not HEAD
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
- Supersession is recorded only from the **seed** defaults (what downstream
  projects carry), and only when the promotion retires the old model from the
  seed entirely — the framework must never ship a default it declares
  obsolete. A lineage a partial promotion could not record is declared later,
  once the old model is no longer a seed default:
  `./.aitask-scripts/aitask_add_model.sh record-supersession --agent <a> --old <old> --new <new> [--dry-run]`
  (same guards; commit the table as in Step 6). Existing edges are never
  overwritten.
- `promote-default-agent-string` is `claudecode`-only because only
  `.aitask-scripts/lib/agent_string.sh` hardcodes a default fallback
  (`DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-...}"`). The subcommand
  preserves that parameter-expansion shape (so callers can still override)
  and also refreshes the matching resolution-chain note in
  `.aitask-scripts/aitask_codeagent.sh`.
- All writes are atomic: subcommands write to a tempfile, validate JSON
  with `jq .`, then `mv` into place. `--dry-run` uses the same pipeline
  but prints a unified diff instead of moving.
- Tests: `bash tests/test_add_model.sh` (TMPDIR-isolated via the
  `AITASK_REPO_ROOT` env var) and `python3 tests/test_model_supersession.py`.
