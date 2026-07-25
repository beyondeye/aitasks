---
Task: t1241_register_opus5_sonnet5_claudecode.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# Plan: Register Opus 5 + Sonnet 5 for claudecode, promote Opus 5 to default

## Context

Opus 5 (`claude-opus-5`, 1M input context by default) has shipped, and a new
Sonnet 5 (`claude-sonnet-5`) exists that the framework's `claudecode` model
registry does not yet know about (its highest entries are `opus4_8` /
`opus4_8_1m` and `sonnet4_6`). We want new tasks to run on the latest Opus by
default. This change:

1. **Registers** `opus5` and `sonnet5` in the claudecode registry.
2. **Promotes** `opus5` to the operational default for every op that currently
   defaults to `opus4_8`.

Scope is the `claudecode` agent only (codex / opencode untouched).

The framework already has purpose-built machinery for exactly this — the
`aitask-add-model` skill and `.aitask-scripts/aitask_add_model.sh` helper
(`add-json`, `promote-config`, `promote-default-agent-string`). We use the
helper for all registry/config/DEFAULT_AGENT_STRING writes and hand-edit only
the files the helper explicitly does not cover (documented manual-review
surface in `aidocs/framework/model_reference_locations.md`).

## Key facts established during exploration

- `aitasks/` is a symlink to `.aitask-data/aitasks`, so `aitasks/metadata/*`
  are the **live task-data-branch** files → commit via `./ait git`. `seed/*`,
  source, tests, and docs are on **main** → plain `git`.
- **Model design (pinned):** Opus 5 is a **single** entry `opus5` →
  `claude-opus-5` (1M context is the default with the plain id — do NOT add a
  separate `opus5_1m` / `claude-opus-5[1m]` variant, unlike the opus4_7/opus4_8
  two-entry pattern). Sonnet 5 = `sonnet5` → `claude-sonnet-5` (add-only, not
  promoted).
- **`promote-config` sets each listed op unconditionally in BOTH files** (no
  "only if currently opus4_8" guard) and applies the same op list to both
  files. It skips ops absent from a given file.
- **Op sets that currently default to `opus4_8`:**
  - Live `codeagent_config.json`: `pick`, `explore`, `learn`, `trail`,
    `brainstorm-explorer`, `brainstorm-synthesizer`,
    `brainstorm-module_decomposer`, `brainstorm-module_merger`,
    `brainstorm-module_syncer`.
  - Seed `codeagent_config.json`: `pick`, `explore`, `shadow`, `learn`, `trail`.
  - `shadow` diverges: seed=`opus4_8`, live=`codex/gpt5_6_terra`. **User
    decision:** promote seed `shadow`→opus5, keep live `shadow`=codex. Because
    the helper would clobber live if `shadow` were in `--ops`, we exclude
    `shadow` from the helper call and do a **seed-only manual edit**.

## Implementation steps

All helper calls: preview with `--dry-run` first, then apply.

### 1. Register the two models (helper — writes live + seed)

```bash
./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode \
  --name opus5 --cli-id claude-opus-5 \
  --notes "Most capable model, 1M context default, complex reasoning + agentic coding, adaptive thinking"

./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode \
  --name sonnet5 --cli-id claude-sonnet-5 \
  --notes "Best speed/intelligence balance, adaptive thinking, 1M context"
```

Writes `aitasks/metadata/models_claudecode.json` (live) + `seed/models_claudecode.json`.

### 2. Promote opus5 for the live-opus4_8 op set (helper — writes live + seed)

```bash
./.aitask-scripts/aitask_add_model.sh promote-config --agent claudecode --name opus5 \
  --ops "pick,explore,learn,trail,brainstorm-explorer,brainstorm-synthesizer,brainstorm-module_decomposer,brainstorm-module_merger,brainstorm-module_syncer"
```

Effect: live gets all 9 → opus5 (shadow stays codex, not in list); seed gets
`pick,explore,learn,trail` → opus5 (brainstorm-* absent → skipped; shadow not
in list → still opus4_8, fixed next step).

### 3. Seed-only shadow promotion (manual edit, helper can't express per-file)

Edit `seed/codeagent_config.json`: `"shadow": "claudecode/opus4_8"` →
`"claudecode/opus5"`. Live `codeagent_config.json` shadow is left as
`codex/gpt5_6_terra`.

### 4. Promote DEFAULT_AGENT_STRING (helper — claudecode only)

```bash
./.aitask-scripts/aitask_add_model.sh promote-default-agent-string --agent claudecode --name opus5
```

Patches `.aitask-scripts/lib/agent_string.sh` (`DEFAULT_AGENT_STRING` fallback,
opus4_8→opus5, preserving the `${VAR:-...}` shape) and the resolution-chain
note in `.aitask-scripts/aitask_codeagent.sh`.

### 5. Manual-review surface (NOT patched by the helper)

- **`tests/test_codeagent.sh`** — Test 5 copies `seed/codeagent_config.json`,
  so promoting seed `pick`→opus5 breaks it. Update lines ~109 (comment), ~112
  (`AGENT_STRING:claudecode/opus4_8`→opus5), ~114 (`MODEL:opus4_8`→opus5).
  Lines 214/218 pass explicit `claudecode/opus4_8` and still resolve (opus4_8
  stays a registered model) — leave them.
- **`tests/test_brainstorm_crew.py`** — the fixture at lines ~304–310 mirrors
  the shipped brainstorm defaults (`claudecode/opus4_8`) and the assertion at
  ~419 checks explorer==opus4_8. These are self-consistent fixtures (they don't
  break), but update them to `claudecode/opus5` to stay representative; keep
  each test self-consistent and re-run. Leave override/merge-mechanics fixtures
  (~337, ~373) that use arbitrary values as-is.
- **`aidocs/codeagents/claudecode_tools.md:5`** — per the framework's own
  manual-review convention, update the `**Model:**` line to
  `Claude Opus 5 (\`claude-opus-5\`)`. (Note: this file is a generated tools
  snapshot; we update only the model-reference line, not regenerate it.)
- **`website/content/docs/commands/codeagent.md`** — defaults table: `pick`
  (~53), `explore` (~55), `learn` (~61) → `claudecode/opus5`; the "Hardcoded
  default" line (~174) `claudecode/opus4_8`→`claudecode/opus5`. The `shadow`
  (~60) and `explore-relay` (~56) rows are **already stale** vs live config
  (shadow shown opus4_8 but live=codex) — this is pre-existing; note it in the
  Final Implementation Notes rather than silently expanding scope. Example
  output blocks that show `opus4_7_1m` (~109/111/183) are illustrative — leave.
- **`aidocs/framework/model_reference_locations.md`** — the audit doc is stale
  (still cites `opus4_7_1m` as the DEFAULT_AGENT_STRING). Refresh the two
  §3 "Hardcoded source-code defaults" rows to `claudecode/opus5` and update the
  §1 registry-entry examples to mention opus5/sonnet5.

### 6. Verify

```bash
bash tests/test_add_model.sh          # helper unit tests (TMPDIR-isolated)
bash tests/test_codeagent.sh          # resolution assertions (updated)
bash tests/test_agent_string.sh       # unaffected (opus4_7_1m stays registered)
python tests/test_brainstorm_crew.py  # fixtures updated
shellcheck .aitask-scripts/aitask_add_model.sh   # (no script logic changed; sanity)
```

Also spot-check resolution end-to-end:
```bash
./ait codeagent resolve pick     # expect claudecode/opus5
./ait codeagent list-models claudecode | grep -E 'opus5|sonnet5'
```

### 7. Commit (grouped per aitask-add-model skill Step 6)

- **Registry + config (task-data branch, `./ait git`):**
  `aitasks/metadata/models_claudecode.json`, `aitasks/metadata/codeagent_config.json`
  → `ait: Register claudecode/opus5 + sonnet5 and promote opus5 to default (t1241)`
- **Seed + source + tests + docs (main, plain `git`):**
  `seed/models_claudecode.json`, `seed/codeagent_config.json`,
  `.aitask-scripts/lib/agent_string.sh`, `.aitask-scripts/aitask_codeagent.sh`,
  `tests/test_codeagent.sh`, `tests/test_brainstorm_crew.py`,
  `aidocs/codeagents/claudecode_tools.md`,
  `website/content/docs/commands/codeagent.md`,
  `aidocs/framework/model_reference_locations.md`
  → `feature: Register opus5/sonnet5 and promote opus5 default for claudecode (t1241)`

(Exact commit split follows Step 8's code-vs-plan separation; never mix
`aitasks/` and code paths in one commit.)

## Out of scope

- `codex` / `opencode` agents.
- Regenerating the full `claudecode_tools.md` snapshot.
- Fixing the pre-existing `shadow`/`explore-relay` staleness in the website
  defaults table beyond noting it (candidate follow-up).
- Cross-agent skill ports (no agent-specific surface changes here).

## Step 9 (Post-Implementation)

Standard: review/approval (Step 8), then merge approval + `ait gates run 1241`
(risk_evaluated gate) + archival via `aitask_archive.sh 1241` (Step 9).

## Risk

### Code-health risk: low
- Registry/config are data files and docs/tests are text; no runtime logic
  changes. Writes go through the idempotent, atomic, `--dry-run`-previewable
  helper. · severity: low · → mitigation: TBD
- `promote-config`'s unconditional per-op set could clobber live `shadow`
  (codex) if `shadow` were passed in `--ops`. Mitigated structurally by
  excluding `shadow` from the helper call and doing a seed-only manual edit;
  verified by inspecting both config files' `shadow` value after apply. ·
  severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Completeness of the manual-review surface (a missed model reference). Bounded
  by following the audit at `aidocs/framework/model_reference_locations.md` and
  a post-change grep for lingering `opus4_8` defaults. · severity: low ·
  → mitigation: TBD
- Correctness of cli_ids (`claude-opus-5`, `claude-sonnet-5`) — taken from the
  known model roster; `ait codeagent resolve`/`list-models` spot-check confirms
  they resolve. · severity: low · → mitigation: TBD
