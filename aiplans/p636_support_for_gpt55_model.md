---
Task: t636_support_for_gpt55_model.md
Base branch: main
plan_verified: []
---

# Plan: Support for GPT-5.5 model (t636)

## Context

OpenAI released GPT-5.5 today (2026-04-23). The Codex CLI docs already list
`gpt-5.5` as an available model ID, but our registries have not been updated:

- `aitasks/metadata/models_codex.json` — no `gpt5_5` entry.
- `aitasks/metadata/models_opencode.json` — no gpt-5.5 entries. `opencode
  models --verbose` does not yet expose gpt-5.5 (provider hasn't rolled out),
  so CLI-discovery (`ait opencode-models`) cannot add it automatically.

User decisions (confirmed in planning):
- **Codex**: add via the canonical helper — no promotion, just registration.
- **OpenCode**: add manually, overriding the CLI-discovery convention, with
  the caveat that the next `ait opencode-models` run will mark these entries
  `status: unavailable` until the provider catches up.
- **Defaults**: do not promote — `codeagent_config.json` stays as-is.

## Scope (files to modify)

1. `aitasks/metadata/models_codex.json` — append `gpt5_5` entry
2. `seed/models_codex.json` — same append (handled automatically by `add-json`)
3. `aitasks/metadata/models_opencode.json` — append two entries:
   `openai_gpt_5_5` and `opencode_gpt_5_5`
4. `seed/models_opencode.json` — same two appends (manual mirror)

No code changes. No test changes. No config/default changes.

## Implementation

### Step 1 — Register codex/gpt5_5

Dry-run first, then apply, via the existing helper
(`.aitask-scripts/aitask_add_model.sh`). It handles both metadata and seed
atomically and errors on duplicates.

```bash
./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
  --agent codex --name gpt5_5 --cli-id gpt-5.5 \
  --notes "Newest frontier model for complex coding, tool use, and agentic workflows; successor to GPT-5.4"

./.aitask-scripts/aitask_add_model.sh add-json \
  --agent codex --name gpt5_5 --cli-id gpt-5.5 \
  --notes "Newest frontier model for complex coding, tool use, and agentic workflows; successor to GPT-5.4"
```

Notes:
- Name `gpt5_5` follows the existing convention in `models_codex.json`
  (`gpt5_4`, `gpt5_3codex`, ...).
- `--notes` string paraphrases the Codex model docs entry for `gpt-5.5`.
  Context-window size is deliberately omitted — OpenAI hasn't published
  gpt-5.5 specs yet (no platform.openai.com/docs/models/gpt-5.5 page,
  OpenRouter doesn't list it). Update the notes later once authoritative
  specs are available.

### Step 2 — Manually append opencode entries

The `aitask_add_model.sh` helper explicitly rejects `--agent opencode`, so
both `aitasks/metadata/models_opencode.json` and `seed/models_opencode.json`
are edited directly. Follow the existing entry shape (see the
`openai_gpt_5_4` / `opencode_gpt_5_4` entries as templates).

Two entries to append (the opencode registries are sorted by `name` — keep
that order so the next CLI-discovery run produces a minimal diff):

```json
{
  "name": "openai_gpt_5_5",
  "cli_id": "openai/gpt-5.5",
  "notes": "GPT-5.5 (openai provider)",
  "status": "active",
  "verified": { "batch-review": 0, "pick": 0, "explain": 0 },
  "verifiedstats": {}
},
{
  "name": "opencode_gpt_5_5",
  "cli_id": "opencode/gpt-5.5",
  "notes": "GPT-5.5 (opencode provider)",
  "status": "active",
  "verified": { "batch-review": 0, "pick": 0, "explain": 0 },
  "verifiedstats": {}
}
```

Context-window size is omitted from `notes` pending published specs —
consistent with the codex entry rationale above. The existing
opencode entries all include `(Nk context, ...)` because their values
come from `opencode models --verbose`; until the provider exposes
gpt-5.5 we can't derive an authoritative number, so we leave it out.

Sort-insertion positions (current file is alphabetical by `name`):
- `openai_gpt_5_5` goes after `openai_gpt_5_4` (currently last `openai_*`
  entry — the next alphabetical neighbor is `opencode_big_pickle`).
- `opencode_gpt_5_5` goes after `opencode_gpt_5_4_pro` and before
  `opencode_gpt_5_codex`.

Write both files with 2-space indent to match existing formatting. After the
edit, validate JSON:

```bash
jq . aitasks/metadata/models_opencode.json >/dev/null
jq . seed/models_opencode.json >/dev/null
```

### Step 3 — Commit

Per project conventions, registry files in `aitasks/metadata/` go through
`./ait git` (task-data branch), while `seed/` files go through plain `git`
(main). Two commits total:

```bash
# Registry (task-data branch)
./ait git add aitasks/metadata/models_codex.json aitasks/metadata/models_opencode.json
./ait git commit -m "ait: Register gpt-5.5 for codex and opencode (t636)"

# Seed mirror (main branch)
git add seed/models_codex.json seed/models_opencode.json
git commit -m "ait: Sync gpt-5.5 registration to seed (t636)"
```

## Verification

1. Registry sanity:
   ```bash
   jq '.models[] | select(.name == "gpt5_5")' aitasks/metadata/models_codex.json
   jq '.models[] | select(.name | test("gpt_5_5"))' aitasks/metadata/models_opencode.json
   ```
   Both should return the new entries.

2. Seed/metadata parity:
   ```bash
   diff <(jq -S . aitasks/metadata/models_codex.json) <(jq -S . seed/models_codex.json)
   diff <(jq -S . aitasks/metadata/models_opencode.json) <(jq -S . seed/models_opencode.json)
   ```
   Should be empty (verifiedstats may differ on existing entries if the
   working registry has accumulated scores — diff only the new entries
   manually in that case).

3. Board visibility: the new models should appear in any UI that lists
   registered models (e.g. settings TUI) — no code change needed; the files
   are the source of truth.

## Post-Implementation

Proceed to Step 9 of the task workflow for archival (`aitask_archive.sh
636` via `./ait git`).

## Caveats / follow-ups (not part of this task)

- Once opencode's providers expose gpt-5.5, running `ait opencode-models`
  will reconcile the manually-added entries. If the provider naming differs
  from what we guessed, the manual entries will get `status: unavailable`
  and the "real" ones will land alongside — the user can then delete the
  stale manual entries. Document as a known follow-up.
- Codex registry is missing `gpt-5.4-mini` (listed in the Codex docs but
  absent here). Out of scope for this task; flag for a separate task if the
  user wants it.
