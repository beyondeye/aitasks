---
name: aitask-add-model
description: Register a known code-agent model in models_<agent>.json, optionally promote it to default across config/seed/DEFAULT_AGENT_STRING.
---

Companion to `aitask-refresh-code-models`. Where that skill discovers
models via web research, this one skips research and takes known inputs
(e.g., a just-announced Opus release) to:

- **Add mode** — append the model to `aitasks/metadata/models_<agent>.json`
  and the matching `seed/` file. When the new model succeeds an
  already-registered one (e.g. `haiku4_5` → `haiku5_5`), it also records that
  lineage in `.aitask-scripts/lib/model_supersessions.json`, so projects still
  configured with the old model are offered the new one on `ait upgrade`.
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
- `--supersedes <old>` — the already-registered model of the same agent that
  this one succeeds (records `<old>` → `<name>`; see "Lineage" below)
- `--no-supersession` — record no supersession at all: neither the edges a
  promotion implies nor a `--supersedes` lineage (see "Lineage" below)
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
- **predecessor** — see "Lineage" below

**Lineage.** Unless `--supersedes` or `--no-supersession` was given, ask with
`AskUserQuestion`:

- Question: "Does `<agent>/<name>` succeed an already-registered model? Projects
  still configured with that model will be offered `<name>` on `ait upgrade`."
- Header: `Lineage`
- Options: up to three registered models of the same agent whose name starts
  with the same leading letters as `<name>` (its family — `haiku` for
  `haiku5_5`), newest first, each described by its `notes`; plus `None — no
  lineage`. These candidates are a convenience, not an inference: the user
  picks one, names another registered model via "Other", or declines. Never
  record a lineage the user did not choose.

The answer (or `--supersedes`) is `<old>`; "None" leaves it unset.

**One opt-out: `record_lineage`.** Keep a single decision that governs **both**
recording paths — the edges `promote-config` derives from the seed defaults it
retires, and the explicit `<old>` → `<name>` lineage. It starts `true` and
becomes `false` on `--no-supersession` or on any choice below that declines
recording ("Register without lineage", "Promote without recording
supersession", "Apply without recording supersession"). While it is `false`:
`promote-config` runs with `--no-supersession`, `record-supersession` is not
run at all (neither preview nor apply), and the Step 4 summary says that no
lineage will be recorded.

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
to `promote-config` manually. If the model is registered and only its lineage
is missing, say so: run
`./.aitask-scripts/aitask_add_model.sh record-supersession --agent <agent> --old <old> --new <name>`
directly.

When `<old>` is set, it must be registered in the same registry and differ
from `<name>`. `--supersedes` together with `--no-supersession` is
contradictory — refuse before any dry-run: "`--supersedes` declares a lineage
and `--no-supersession` forbids one — pass one of them." Do not guess which
one wins.

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

If `<old>` is set and `record_lineage` is `true`, preview the lineage — with
`--assume-registered` for the same reason as above (only on a `--dry-run`):

```bash
./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run --assume-registered \
  --agent <agent> --old <old> --new <name>
```

Skip it in promote mode when the `promote-config` preview already printed
`RECORDED:<agent>/<old>-><agent>/<name>` — the promotion records that edge.
Relay its lines as for `promote-config` (`RECORDED`, `RECORDED_SIBLING`,
`WARN:family`, `SKIPPED`). A `BLOCKED` line means the apply would be refused;
resolve it with `AskUserQuestion` before Step 4:

- `BLOCKED:in_seed:<agent>/<old>|<ops>` — `<old>` is still the seed default
  of `<ops>`, and the framework never ships a default it declares obsolete.
  Options: `Promote instead` (restart in promote mode with those ops) /
  `Register without lineage` / `Abort`.
- `BLOCKED:conflict|cycle|seed_invariant:…` — the table already says
  something else. Options: `Register without lineage` / `Abort`; never edit
  the table to force the edge in.

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

When a preview recorded a supersession (in either mode), add a third
option: `Apply without recording supersession` (description: `Apply the
registration and defaults but declare no lineage — upgrading projects are not
offered the new model`). It sets `record_lineage` to `false`, which runs
`promote-config` with `--no-supersession` and skips `record-supersession`.

If `Apply`, run the same subcommands without `--dry-run` (and without
`--assume-registered`), in this order, dropping the ones that do not apply:

1. `add-json` — registers the model
2. `promote-config` (promote mode) — updates `codeagent_config.json` (and
   seed) and records the supersession the promotion implies
3. `record-supersession` (only when `record_lineage` is `true`, `<old>` is
   set, and step 2 did not already record `<old>` → `<name>`) — records the
   lineage; it validates against the real registry, which step 1 just wrote
4. `promote-default-agent-string` (promote mode, claudecode only) — updates
   `DEFAULT_AGENT_STRING` in `.aitask-scripts/lib/agent_string.sh` and the
   resolution-chain note in `.aitask-scripts/aitask_codeagent.sh`

**If a call fails,** stop — do not run the remaining calls. Report which calls
succeeded and which failed (with its output), then report what is actually
saved by looking, not by exit status — a failed call can have written some of
its own files before failing:

```bash
./ait git status --short -- aitasks/metadata/models_<agent>.json aitasks/metadata/codeagent_config.json
git status --short -- seed/ .aitask-scripts/lib/model_supersessions.json
```

Never relay a helper's "Nothing was written" as a statement about the whole
operation. If the model is registered but the lineage is missing (typically
`record-supersession` refused it), give the targeted retry, to run once the
`BLOCKED` cause is resolved:
`./.aitask-scripts/aitask_add_model.sh record-supersession --agent <agent> --old <old> --new <name>`
— re-running this skill with the same `--name` would stop at the duplicate
check.

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

**Supersession table (main branch, when `promote-config` or
`record-supersession` printed `NOTE: commit
.aitask-scripts/lib/model_supersessions.json`):** the table is already
tracked, so there is no `add`:
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
- A promotion records supersession from the **seed** defaults (what downstream
  projects carry), and only when it retires the old model from the seed
  entirely — the framework must never ship a default it declares obsolete.
  Supersession is not limited to defaults: when you register the successor of a
  model that was never a default (e.g. `haiku4_5` → `haiku5_5`), the Step 1
  lineage question (or `--supersedes`) records it, so users who chose the old
  model are offered the new one. Outside this workflow — a lineage a partial
  promotion could not record once the old model is no longer a seed default,
  or one declared after the fact — run
  `./.aitask-scripts/aitask_add_model.sh record-supersession --agent <a> --old <old> --new <new> [--dry-run]`
  (same guards; commit the table as in Step 6). Existing edges are never
  overwritten.
- OpenCode models carry no supersession lineages yet: this skill refuses
  `opencode`, and so does `record-supersession`.
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
