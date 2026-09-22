---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [codeagent, opencode, models]
gates: [risk_evaluated]
created_at: 2026-09-22 23:29
updated_at: 2026-09-22 23:29
---

## Goal

Refresh `aitasks/metadata/models_opencode.json` (and its `seed/` copy) from
OpenCode CLI discovery, so the GPT-6 and GPT-5.6 families are registered.

Companion to **t1866** (Codex GPT-6 registration + shadow/discuss default
promotion). Deliberately a **separate** task: the mechanism, the files, and the
blast radius are all different.

## Premise correction — GPT-6 on OpenCode is ASTRA ONLY

The request named a GPT-6 family of *astra, sol, luna*. Measured against the
installed CLI (`opencode models`), that is not what OpenCode offers:

- **`opencode/gpt-6-astra` is the only GPT-6 model available**, at either
  provider.
- There is **no** `gpt-6-sol`, **no** `gpt-6-luna`, and **no** `openai/gpt-6-*`
  entry of any kind.

This does not contradict t1866 — Codex CLI and OpenCode expose different model
sets from different providers — but it does mean this task registers exactly
**one** new GPT-6 model, not three. Re-measure before implementing; the provider
catalog moves.

## GPT-5.6 is NOT complete

An initial `grep terra` undercounted and suggested 5.6 was fully registered. It
is not:

| provider | offered | registered | missing |
|---|---|---|---|
| `opencode/` | 3 (sol, terra, luna) | 3 | 0 |
| `openai/` | 12 | 3 | **9** |

The nine missing `openai/` 5.6 entries: `gpt-5.6`, `gpt-5.6-fast`,
`gpt-5.6-pro`, `gpt-5.6-luna-fast`, `gpt-5.6-luna-pro`, `gpt-5.6-sol-fast`,
`gpt-5.6-sol-pro`, `gpt-5.6-terra-fast`, `gpt-5.6-terra-pro`.

## The registry is broadly stale

The refresh is not a surgical two-model addition. A dry-run on the exploring
machine reported:

> Total: 108 models (92 active, 16 unavailable)

against a registry that currently holds **67**. So the refresh adds roughly
**41** models and flips **16** existing ones to `status: "unavailable"` —
including `openai/gpt-5-codex`, `openai/gpt-5.1-codex{,-max,-mini}`,
`openai/gpt-5.2-codex`, `openai/codex-mini-latest`,
`opencode/claude-opus-4-1`, `opencode/claude-3-5-haiku`,
`opencode/gemini-3-pro`, `opencode/glm-4.6`, `opencode/glm-4.7`,
`opencode/minimax-m2.1`, and several `-free` tiers.

`unavailable` is a soft-delete marker — entries are retained, not dropped. The
decided scope is to **accept the full refresh**.

## Constraint — there is no per-model path

`.aitask-scripts/aitask_add_model.sh` **refuses** `--agent opencode` outright:

> Agent 'opencode' is not supported. Use aitask-refresh-code-models for
> opencode (models are provider-gated and CLI-discovered).

The only supported writer is `.aitask-scripts/aitask_opencode_models.sh`
(`ait opencode-models`), whose flags are `--dry-run`, `--list`, `--sync-seed`.
It has **no filter** — it rewrites the whole registry from what the CLI
reports. Hand-editing individual entries was considered and rejected: it drifts
the registry away from discovery and the next refresh would overwrite it.

## Implementation

1. Confirm the binary is present: `command -v opencode`. If absent, stop — the
   registry cannot be refreshed without it.
2. Dry-run and read the diff, **including the unavailable list**:
   ```bash
   ./.aitask-scripts/aitask_opencode_models.sh --dry-run
   ```
3. Re-verify the premise against this run's output before writing:
   ```bash
   ./.aitask-scripts/aitask_opencode_models.sh --dry-run 2>&1 | grep -i 'gpt-6'
   ```
   If models beyond `gpt-6-astra` now appear, update this task's body rather
   than silently registering a different set.
4. Apply, syncing the seed in the same call:
   ```bash
   ./.aitask-scripts/aitask_opencode_models.sh --sync-seed
   ```

## Verification

- `jq -r '.models[] | select(.cli_id | test("gpt-6")) | .cli_id'` on both
  `aitasks/metadata/models_opencode.json` and `seed/models_opencode.json`
  prints `opencode/gpt-6-astra`.
- All 12 `openai/gpt-5.6*` ids are present in both files.
- `jq '.models | length'` matches between metadata and seed.
- `jq -e '.models[] | select(.status == null)'` finds nothing — every opencode
  entry carries `status` (unlike codex entries, which have no such field).
- `jq . ` parses both files.

## Machine dependence — read before implementing

Discovery reflects **the provider auth of the machine that runs it**. A box
with different OpenCode provider credentials will discover a different set, and
running the refresh there could flip models to `unavailable` that are merely
unreachable from that machine rather than genuinely retired. Run this on a box
with the full provider set configured, and review the unavailable list in the
dry-run before applying.

## Out of scope

- No `codeagent_config.json` default changes. No OpenCode model is promoted to
  any operation default; `shadow` / `discuss` are t1866's business.
- No `DEFAULT_AGENT_STRING` change (claudecode-only).

## Commit layout

- **Task-data branch:** `aitasks/metadata/models_opencode.json` via
  `./.aitask-scripts/aitask_task_commit.sh -m "ait: Refresh opencode model registry" aitasks/metadata/models_opencode.json`
- **main:** `git commit -m "chore: Sync opencode model registry to seed" -- seed/models_opencode.json`
