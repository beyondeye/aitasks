---
Task: t579_support_for_opus_4_7.md
Base branch: main
plan_verified: []
---

# Plan: t579 — Support for Claude Opus 4.7

## Context

Claude Opus 4.7 (cli_id: `claude-opus-4-7`) is the new flagship Claude model,
superseding Opus 4.6. The aitasks framework currently defaults to `opus4_6` for
`pick`, `explore`, and several `brainstorm-*` operations, and hardcodes
`claudecode/opus4_6` as the fallback `DEFAULT_AGENT_STRING` in
`.aitask-scripts/aitask_codeagent.sh`. We need to (a) register 4.7 as a known
model, (b) promote it to the new default, and (c) make this process **repeatable**
for future model bumps across **any** supported codeagent (Opus 4.8, Sonnet 4.7,
Gemini 3.0, GPT-5.4 Codex, etc.).

**Key insight from exploration:** the existing
`.claude/skills/aitask-refresh-code-models/` skill only updates the
`models_*.json` registry (add/update/flag-deprecated) via web research — it does
**not** update operational defaults in `codeagent_config.json`, the
`DEFAULT_AGENT_STRING` constant, `BRAINSTORM_AGENT_TYPES` in
`brainstorm_crew.py`, `crew_meta_template.yaml`, or documentation examples. It
also requires a full web-research round-trip even when the user already knows
the exact model details (e.g., vendor just announced a specific new model).

We will build a new skill `aitask-add-model` that complements
`refresh-code-models`. It works for **any** supported codeagent (claudecode,
geminicli, codex, opencode) and supports **two modes**:

- **add mode (default):** register a known new model in
  `models_<agent>.json` (+ seed sync) without touching defaults — fast,
  deterministic, no web research. This is the everyday use case for handling
  a vendor-announced model where the user already knows `name`, `cli_id`, and
  notes.
- **promote mode (opt-in via `--promote`):** add as above, then also promote
  the new model to default for a user-selected set of operations
  (`pick`, `explore`, `brainstorm-*`), updating every hardcoded default
  location atomically.

Both modes support `--dry-run` and emit a manual-review list of docs/tests
the skill intentionally does not edit. Opus 4.7 serves as the end-to-end
validation exercise for `promote` mode.

---

## Coverage gap analysis (preview — full audit is t579_1's deliverable)

**Covered by `aitask-refresh-code-models`:**
- `aitasks/metadata/models_<agent>.json` (add new entry, preserve verified stats)
- `seed/models_<agent>.json` (sync copy)

**NOT covered — needed for a full "promote to default" flow:**
- `aitasks/metadata/codeagent_config.json` — operational defaults per operation
- `seed/codeagent_config.json`
- `.aitask-scripts/aitask_codeagent.sh` line 21: `DEFAULT_AGENT_STRING="claudecode/opus4_6"`
- `.aitask-scripts/brainstorm/brainstorm_crew.py` lines 45–50: `BRAINSTORM_AGENT_TYPES`
- `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml` — default agent strings
- `.aitask-scripts/aitask_crew_init.sh` (help-text examples) — optional
- `.aitask-scripts/aitask_update.sh` line 127 (help-text example) — optional

**Not covered — intentional (documentation / tests):**
- `website/content/docs/commands/codeagent.md` — examples
- `website/content/docs/tuis/settings/reference.md` — example
- `aidocs/claudecode_tools.md` line 5 — current model reference
- `tests/test_codeagent.sh`, `tests/test_resolve_detected_agent.sh`,
  `tests/test_aitask_stats_py.py`, `tests/test_brainstorm_crew.py`,
  `tests/test_verified_update_flags.sh` — add/update fixtures

The new `aitask-add-model` skill will cover the **first two** bullet groups
(config + hardcoded defaults, plus seed sync — the latter only in `--promote`
mode). It will emit a **manual review list** for the last group (docs + tests)
rather than silently editing prose.

---

## Child task breakdown

Split into 4 child tasks, executed in order.

### t579_1 — Audit `refresh-code-models` and produce design spec for `aitask-add-model`

- **Type:** refactor
- **Priority:** high · **Effort:** low
- **Depends on:** none

Deliverables:
1. `aidocs/model_reference_locations.md` — complete inventory of every file
   that references a specific model name or default agent string, with
   `covered_by_refresh` / `needed_for_add` / `needed_for_promote` /
   `informational_only` tags for each entry.
2. Design spec section at the bottom of that doc covering the new skill:
   - Skill name (proposed: `aitask-add-model`) and positioning next to
     `refresh-code-models`
   - Two modes: **add** (default) and **promote** (`--promote`)
   - Multi-agent support (claudecode, geminicli, codex, opencode) — confirm
     any agent-specific quirks (e.g., OpenCode's CLI-based discovery; does
     add-mode still make sense for it, or is it claudecode/geminicli/codex
     only?)
   - Inputs (batch flags + interactive prompts)
   - Auto-applied updates vs. manual-review output per mode
   - Rollback / dry-run safety
   - Commit strategy (`./ait git` for metadata, `git` for source/seed)
3. No source-code changes beyond the new `aidocs/` file.

### t579_2 — Implement `aitask-add-model` skill

- **Type:** feature
- **Priority:** high · **Effort:** medium
- **Depends on:** t579_1

Deliverables:
1. New skill directory: `.claude/skills/aitask-add-model/SKILL.md` following
   the design from t579_1. Key API:
   - **Required inputs:** `name`, `cli_id`, `agent` (one of claudecode,
     geminicli, codex, opencode; prompted interactively if omitted)
   - **Optional inputs:** `notes` (prompted if omitted), `--promote` (opt-in
     to enter promote mode), `--promote-ops <csv>` (operations to re-default
     onto the new model; prompted via multiSelect if omitted when `--promote`
     is set)
   - **Flags:** `--dry-run`, `--batch` (non-interactive — requires all
     required inputs as flags)
2. **Add mode (default)** — auto-applies:
   - Append entry to `aitasks/metadata/models_<agent>.json` with the naming
     convention from `refresh-code-models` (initialize `verified`/
     `verifiedstats` for zero-history)
   - Sync to `seed/models_<agent>.json` if `seed/` exists
   - Commit via `./ait git` for metadata, plain `git` for seed
3. **Promote mode (`--promote`)** — applies add-mode changes, then also:
   - Update `aitasks/metadata/codeagent_config.json` defaults for each
     requested operation to `<agent>/<name>`
   - Sync to `seed/codeagent_config.json`
   - If `agent == claudecode` and any op is re-defaulted: update
     `DEFAULT_AGENT_STRING` in `.aitask-scripts/aitask_codeagent.sh`
   - If brainstorm ops are re-defaulted: update `BRAINSTORM_AGENT_TYPES` in
     `.aitask-scripts/brainstorm/brainstorm_crew.py` AND
     `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`
   - Commit as a separate code commit (plain `git`) with clear message
4. If helper bash is needed (JSON patching, atomic default promotion), add it
   to `.aitask-scripts/` (e.g., `aitask_add_model.sh`) using existing
   portability conventions (see `CLAUDE.md` sed/grep/wc notes).
5. `--dry-run` support: print proposed diffs (per file) without applying.
6. Manual-review output: a printed list of doc/test files (website docs,
   `aidocs/claudecode_tools.md`, tests) that still reference the replaced
   default, for follow-up curation. Emitted in both modes but only populated
   when defaults were changed.
7. Unit tests in `tests/` (e.g., `test_add_model.sh`) covering:
   - Add-mode JSON insertion preserves existing entries + `verifiedstats`
   - Promote-mode updates all hardcoded default locations
   - Dry-run leaves filesystem unchanged
8. Note: this task does NOT add opus4_7 — it only ships the skill.
   Verification against a real model is done in t579_3.

Reference patterns to reuse:
- Model list read/write pattern from `refresh-code-models` Step 6
- JSON manipulation: `jq` (already required by `aitask_codeagent.sh`)
- Git-split commit convention: `./ait git` for `aitasks/metadata/`, plain
  `git` for `seed/` and `.aitask-scripts/`
- Existing naming convention (`opus4_6`, `claude-opus-4-6`) from the
  `refresh-code-models` SKILL.md "Model Naming Convention" section
- Interactive-vs-batch mode pattern from any of the existing
  `aitask_*.sh` scripts (e.g., `aitask_create.sh`)

### t579_3 — Use `aitask-add-model --promote` to add Opus 4.7 as the new default

- **Type:** feature
- **Priority:** high · **Effort:** low
- **Depends on:** t579_2

Deliverables:
1. Invoke `/aitask-add-model` with:
   - `name=opus4_7`, `cli_id=claude-opus-4-7`, `agent=claudecode`
   - `notes="Most intelligent Claude model, successor to opus4_6"`
     (exact notes to be confirmed at invocation time from official docs)
   - `--promote --promote-ops=pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer`
2. Resulting changes (automatic via the skill):
   - `aitasks/metadata/models_claudecode.json` — new `opus4_7` entry
   - `seed/models_claudecode.json` — synced
   - `aitasks/metadata/codeagent_config.json` — `pick`/`explore`/brainstorm-opus ops updated to `claudecode/opus4_7`
   - `seed/codeagent_config.json` — synced
   - `.aitask-scripts/aitask_codeagent.sh` — `DEFAULT_AGENT_STRING` → `claudecode/opus4_7`
   - `.aitask-scripts/brainstorm/brainstorm_crew.py` — `BRAINSTORM_AGENT_TYPES` opus entries
   - `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`
3. Verification (in the same task):
   - Run existing tests: `bash tests/test_codeagent.sh`,
     `bash tests/test_resolve_detected_agent.sh` (pre-update check — some may
     still reference 4.6; that's a t579_4 concern, not a t579_3 blocker).
   - Sanity check: `./ait codeagent <op> --dry-run` for one pick operation to
     confirm the new default resolves.
   - Validate JSON files with `jq . <file>` for every changed JSON.
4. Capture the manual-review list emitted by the skill; attach it to the child
   plan file's Final Implementation Notes for t579_4 to consume.

### t579_4 — Update tests and docs for Opus 4.7

- **Type:** documentation
- **Priority:** medium · **Effort:** low
- **Depends on:** t579_3

Deliverables:
1. **Tests** (update fixtures + add explicit 4.7 coverage):
   - `tests/test_codeagent.sh` — opus4_7 CLI ID mapping, default agent string
   - `tests/test_resolve_detected_agent.sh` — opus4_7 case
   - `tests/test_aitask_stats_py.py` — opus4_7 fixture
   - `tests/test_brainstorm_crew.py` — updated defaults
   - `tests/test_verified_update_flags.sh` — if fixtures reference `opus4_6`
     as the default
2. **Docs:**
   - `website/content/docs/commands/codeagent.md` — examples + defaults table
   - `website/content/docs/tuis/settings/reference.md` — example
   - `aidocs/claudecode_tools.md` — line 5 model reference
   - New skill doc (if the website auto-generates from `SKILL.md`, verify
     `website/content/docs/skills/aitask-add-model.md` exists or is stubbed)
3. Do NOT update comments or help-text that merely use `opus4_6` as an
   illustrative example string — those are generic format demos, not live
   defaults. Only update places where the specific name is claimed to be the
   current default.

---

## Implementation notes (for all children)

- Work on branch `main`, no worktree (profile `fast`: `create_worktree: false`).
- Each child gets its own plan file in `aiplans/p579/p579_<N>_<name>.md` written
  up-front (via the parent's planning phase here) so children can be picked in
  fresh contexts.
- Commit convention per task-workflow Step 8:
  - **Code commit:** `<issue_type>: <description> (t579_<N>)` using plain `git`
  - **Plan commit:** `./ait git commit -m "ait: Update plan for t579_<N>"`
- After each child is archived, `aitask_archive.sh` auto-removes it from the
  parent's `children_to_implement`. When all four are archived, parent t579
  auto-archives.

## Verification (end-to-end for the whole initiative)

After t579_4 is merged:
1. Run full test suite: `for f in tests/test_*.sh; do bash "$f" || break; done`
2. `./ait codeagent --list-models claudecode` — confirm `opus4_7` appears
3. `./ait codeagent pick --dry-run 1 2>&1 | grep -i 'opus'` — confirm the
   resolved agent is `claudecode/opus4_7`
4. `/aitask-pick` a fresh task and confirm the default model displayed is
   `opus4_7`
5. `shellcheck .aitask-scripts/aitask_*.sh` passes
6. Skill round-trip (add-mode): `/aitask-add-model --dry-run --agent geminicli
   --name gemini3pro --cli-id gemini-3.0-pro` — confirm add-mode works for a
   different agent family with no defaults changed
7. Skill round-trip (promote-mode): `/aitask-add-model --dry-run --promote
   --agent claudecode --name opus4_8 --cli-id claude-opus-4-8` — confirm
   promote-mode is reusable for future bumps (no real changes applied)

## Post-plan action

Profile `fast` has `post_plan_action: ask`. After this plan is approved, the
**child checkpoint** (always interactive regardless of profile) will ask
whether to start the first child (t579_1) or stop here. Recommendation: stop
here after children are created — each child is small and well-scoped enough
to be picked in a fresh context.

## Reference to Step 9

Each child follows `task-workflow/SKILL.md` Step 9 (archive via
`aitask_archive.sh <task_id>`, push via `./ait git push`). The parent t579
will auto-archive when the last child finishes.
