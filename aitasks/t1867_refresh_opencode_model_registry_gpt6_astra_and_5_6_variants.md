---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [codeagent, opencode, models]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-09-22 23:29
updated_at: 2026-09-23 16:21
---

## Goal

Refresh `aitasks/metadata/models_opencode.json` (and its `seed/` copy) from
OpenCode CLI discovery, so the GPT-6 and GPT-5.6 families are registered.

Companion to **t1866** (Codex GPT-6 registration + shadow/discuss default
promotion). Deliberately a **separate** task: the mechanism, the files, and the
blast radius are all different.

## Premise — re-measured at implementation (2026-09-23)

Measured with opencode 1.18.32 (auth: OpenCode Zen api + OpenAI oauth). The
catalog moved since this task was written (2026-09-22), so the numbers below
replace the ones originally recorded here.

### GPT-6 is ASTRA ONLY — at both providers

The request named a GPT-6 family of *astra, sol, luna*. OpenCode offers no
`gpt-6-sol` or `gpt-6-luna`. It now offers **three** GPT-6 ids, all astra:

- `opencode/gpt-6-astra`
- `openai/gpt-6-astra`
- `openai/gpt-6-astra-fast`

(Originally recorded: `opencode/gpt-6-astra` only, no `openai/gpt-6-*`.)
This does not contradict t1866 — Codex CLI and OpenCode expose different model
sets from different providers.

### GPT-5.6

| provider | offered | registered before | added |
|---|---|---|---|
| `opencode/` | 3 (sol, terra, luna) | 3 | 0 |
| `openai/` | 6 (sol, terra, luna, each + `-fast`) | 3 | **3** |

The three added `openai/` ids: `gpt-5.6-luna-fast`, `gpt-5.6-sol-fast`,
`gpt-5.6-terra-fast`. The bare `gpt-5.6`, `gpt-5.6-fast`, `gpt-5.6-pro` and the
`*-pro` variants originally listed here as missing are **no longer offered**.

## The registry is broadly stale

The refresh is not a surgical addition. This run's dry-run reported:

> Total: 104 models (85 active, 19 unavailable)

against a registry of **67**. The refresh adds **37** models. Of the 19
unavailable entries, 11 were already `unavailable`; **8 newly flip** to
`status: "unavailable"`:

- `openai/gpt-5.2`, `openai/gpt-5.3-codex`, `openai/gpt-5.5-pro` — still offered
  under `opencode/`; the `openai/` flips reflect what the OpenAI-OAuth provider
  lists on this box (see "Machine dependence")
- `opencode/claude-opus-4-1`, `opencode/deepseek-v4-flash-free`,
  `opencode/minimax-m2.5-free`, `opencode/nemotron-3-super-free`,
  `opencode/ring-2.6-1t-free`

No entry flips back from `unavailable` to active. (Originally recorded:
108 total, 92 active, 16 unavailable.)

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
  prints the 3 GPT-6 ids: `opencode/gpt-6-astra`, `openai/gpt-6-astra`,
  `openai/gpt-6-astra-fast`.
- All 6 `openai/gpt-5.6*` ids are present and `active` in both files.
- The applied active→unavailable flips are exactly the 8 reviewed ids above,
  with no reverse flips and no unreviewed additions.
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

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-23T13:21:23Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-23T13:48:30Z status=pass attempt=1 type=human
