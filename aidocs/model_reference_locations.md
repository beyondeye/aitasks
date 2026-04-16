# Model Reference Locations — Audit + Design Spec

Audit of every file in the `aitasks` repo that references a specific Claude
model name or default agent string, produced as deliverable of task t579_1
(parent: t579 "Support for Claude Opus 4.7").

The audit underpins the design of a new skill `aitask-add-model` that
complements the existing `aitask-refresh-code-models` skill. It also explains
why `refresh-code-models` alone is insufficient for promoting a newly released
model to the framework's default.

## Categorisation legend

| Tag | Meaning |
|---|---|
| `covered_by_refresh` | Written by the existing `aitask-refresh-code-models` skill today |
| `needed_for_add` | Must be written when a new known model is registered, even without making it the new default |
| `needed_for_promote` | Must be written only when the new model is being made the new default for one or more operations |
| `informational_only` | Example string, format illustration, or historical fixture that should stay as-is |

Notes:
- References inside `verifiedstats` blocks are historical scoring data and
  are never edited by either skill — they preserve per-model history.
- Files under `**/archived/**` are not in scope.
- Alt-agent trees (`.gemini/`, `.codex/`, `.agents/`, `.opencode/`) contain
  no live model references at the time of this audit.

---

## Inventory

### 1. Core model registry (source of truth)

| File | Line | Context | Tag |
|---|---|---|---|
| `aitasks/metadata/models_claudecode.json` | 4,5,134,135,145,146,156 | Model entries: `opus4_6`, `sonnet4_6`, `haiku4_5`, `opus4_5` | `covered_by_refresh` / `needed_for_add` |
| `aitasks/metadata/models_geminicli.json` | — | Gemini model entries (no claude refs) | `covered_by_refresh` / `needed_for_add` |
| `aitasks/metadata/models_codex.json` | — | Codex model entries | `covered_by_refresh` / `needed_for_add` |
| `aitasks/metadata/models_opencode.json` | 154,190,226 | Provider-prefixed entries: `opencode/claude-haiku-4-5`, `opencode/claude-opus-4-6`, `opencode/claude-sonnet-4-6` | `covered_by_refresh` (via `aitask_opencode_models.sh` discovery) |
| `seed/models_claudecode.json` | 4,5,14,15,24,25,34 | Synced copy of metadata | `covered_by_refresh` / `needed_for_add` |
| `seed/models_opencode.json` | 14,15 | Synced copy | `covered_by_refresh` / `needed_for_add` |
| `seed/models_geminicli.json` / `seed/models_codex.json` | — | Synced copies | `covered_by_refresh` / `needed_for_add` |

### 2. Operational defaults (per-op agent strings)

| File | Line | Context | Tag |
|---|---|---|---|
| `aitasks/metadata/codeagent_config.json` | 3–13 | Defaults for `pick`, `explain`, `batch-review`, `qa`, `raw`, `explore`, `brainstorm-explorer`, `brainstorm-comparator`, `brainstorm-synthesizer`, `brainstorm-detailer`, `brainstorm-patcher` | `needed_for_promote` |
| `seed/codeagent_config.json` | 3–8 | Synced copy | `needed_for_promote` |

### 3. Hardcoded source-code defaults

| File | Line | Context | Tag |
|---|---|---|---|
| `.aitask-scripts/aitask_codeagent.sh` | 21 | `DEFAULT_AGENT_STRING="claudecode/opus4_6"` — fallback when no config resolves | `needed_for_promote` (claudecode-only) |
| `.aitask-scripts/brainstorm/brainstorm_crew.py` | 44–50 | `BRAINSTORM_AGENT_TYPES` dict: resource defaults only (agent_string removed — now read exclusively from codeagent_config.json) | `covered_by_refresh` (via config) |

### 4. Help text and examples in scripts (format illustrations)

| File | Line | Context | Tag |
|---|---|---|---|
| `.aitask-scripts/aitask_codeagent.sh` | 5, 44, 49, 652, 657, 663, 671 | Comments / help text / error messages using `claudecode/opus4_6` as the agent-string format example. Line 663 specifically claims `"4. Hardcoded default: claudecode/opus4_6"` — this one IS tied to the actual hardcoded default. | Line 663: `needed_for_promote`; rest: `informational_only` |
| `.aitask-scripts/aitask_update.sh` | 127 | Help text: `Agent string that implemented this task (e.g., "claudecode/opus4_6"; use "" to clear)` | `informational_only` |
| `.aitask-scripts/aitask_crew_init.sh` | 48, 49, 57 | Help-text examples of `--add-type` arguments | `informational_only` |
| `.aitask-scripts/aitask_brainstorm_init.sh` | 126–130 | Default fallback values passed to `_get_brainstorm_agent_string` — these ARE live defaults (used when config + hardcoded both miss) | `needed_for_promote` (brainstorm ops) |
| `.aitask-scripts/aitask_opencode_models.sh` | 61 | Comment giving an example of the name-derivation rule | `informational_only` |
| `.aitask-scripts/aitask_verified_update.sh` | 41 | Help text | `informational_only` |

### 5. Documentation (website + aidocs)

| File | Line | Context | Tag |
|---|---|---|---|
| `website/content/docs/commands/codeagent.md` | 16, 28, 36, 54, 55, 56, 57, 89, 105, 107, 108, 118, 119, 167, 176, 177, 178, 179, 208, 209, 248 | Examples, operational defaults table, and hardcoded-default list | Line 167 ("Hardcoded default: `claudecode/opus4_6`"), lines 54–57 (defaults table): `needed_for_promote`; rest: `informational_only` |
| `website/content/docs/tuis/settings/_index.md` | 26 | "The current value (e.g., `claudecode/opus4_6`)" — example | `informational_only` |
| `website/content/docs/tuis/settings/reference.md` | 156, 157 | Example JSON showing `"name": "opus4_6"`, `"cli_id": "claude-opus-4-6"` | `informational_only` |
| `website/content/docs/tuis/codebrowser/how-to.md` | 197 | "By default, this is `claudecode/sonnet4_6`" (qa default) | `needed_for_promote` (only when sonnet is bumped, not applicable to opus4_7) |
| `website/content/docs/tuis/board/reference.md` | 189 | Example in `implemented_with` column | `informational_only` |
| `website/content/docs/skills/aitask-refresh-code-models.md` | 39 | "e.g., Opus 4.6 → `opus4_6`" naming-convention example | `informational_only` |
| `aidocs/claudecode_tools.md` | 5 | `**Model:** Claude Opus 4.6 (claude-opus-4-6)` — stale asof-today statement | `needed_for_promote` |
| `aidocs/agentcrew/agentcrew_architecture.md` | 68, 71, 185 | Architecture diagrams using agent strings as examples | `informational_only` |
| `aidocs/brainstorming/brainstorm_engine_architecture.md` | 476, 479, 482, 485, 488 | Rationale for assigning specific agents to brainstorm types | `informational_only` (historical rationale) |

### 6. Skills and procedure files

| File | Line | Context | Tag |
|---|---|---|---|
| `.claude/skills/task-workflow/model-self-detection.md` | 4, 18 | Format example | `informational_only` |
| `.claude/skills/task-workflow/satisfaction-feedback.md` | 8, 25 | Format example | `informational_only` |
| `.claude/skills/task-workflow/planning.md` | 90 | Format example | `informational_only` |
| `.claude/skills/task-workflow/SKILL.md` | 25 | Format example | `informational_only` |
| `.claude/skills/aitask-refresh-code-models/SKILL.md` | 169, 177, 189 | Naming-convention table + example | `informational_only` |

### 7. Tests

| File | Line(s) | Context | Tag |
|---|---|---|---|
| `tests/test_codeagent.sh` | 127–144, 193, 250–281, 351 | Asserts current defaults + list-models / resolve / coauthor output for `opus4_6`, `sonnet4_6`, `haiku4_5` | `needed_for_promote` (default-sensitive asserts) |
| `tests/test_resolve_detected_agent.sh` | 48, 49, 56, 57 | Env-var + exact-match resolution tests | `needed_for_add` (new opus4_7 mapping should be added) |
| `tests/test_aitask_stats_py.py` | 81, 122, 205, 397, 499 | Fixtures containing `opus4_6` model entries + `implemented_with` strings | `needed_for_add` (add opus4_7 fixture alongside) |
| `tests/test_brainstorm_crew.py` | 376, 380, 389, 392–394, 405, 458 | Asserts BRAINSTORM_AGENT_TYPES defaults | `needed_for_promote` |
| `tests/test_verified_update.sh` | 107, 108, 167–330 | Fixtures pinned to `opus4_6` for verified-stats tests | `informational_only` (fixtures pinned to a specific model; stays stable) |
| `tests/test_verified_update_flags.sh` | 48, 49, 52, 53, 56, 64 | Flag-parsing tests against `opus4_6` / `claude-opus-4-6` | `informational_only` (fixture, stable) |
| `tests/test_crew_init.sh`, `test_crew_groups.sh`, `test_crew_template_includes.sh`, `test_crew_runner.sh`, `test_crew_status.sh`, `test_crew_report.sh`, `test_crew_setmode.sh`, `test_launch_mode_field.sh` | many | Pass `--add-type impl:claudecode/opus4_6` as a stable test argument — model choice is incidental | `informational_only` |
| `tests/test_plan_verified.sh` | 108, 128, 148, 149, 202, 218, 222, 230, 246 | Fixtures for plan-verified append — agent string is incidental | `informational_only` |

---

## Summary matrix

| Category | `covered_by_refresh` | `needed_for_add` | `needed_for_promote` | `informational_only` |
|---|---|---|---|---|
| Model registry (JSON, §1) | 8 files | 8 files (same) | 0 | 0 |
| Operational defaults (§2) | 0 | 0 | 2 files | 0 |
| Hardcoded source defaults (§3) | 0 | 0 | 3 files | 0 |
| Script help/examples (§4) | 0 | 0 | 2 lines (aitask_codeagent.sh:663, aitask_brainstorm_init.sh:126–130) | ~8 lines |
| Docs (§5) | 0 | 0 | 3 locations (codeagent.md defaults table + line 167, aidocs/claudecode_tools.md:5) | many |
| Skills & procedures (§6) | 0 | 0 | 0 | 8 locations |
| Tests (§7) | 0 | test_resolve_detected_agent, test_aitask_stats_py | test_codeagent, test_brainstorm_crew | many stable fixtures |

**Conclusion:** `aitask-refresh-code-models` covers the full model-registry
write in §1 but writes **nothing** in §2, §3, §4-partial, or §5-partial.
Those are the files a new skill must touch to promote a model to default.

---

## Design spec: `aitask-add-model`

### Positioning vs. `aitask-refresh-code-models`

| Concern | `refresh-code-models` | `aitask-add-model` |
|---|---|---|
| Discovery | Web research (WebSearch + WebFetch) | Known inputs from user (or CLI flags) |
| Scope | All agents, all models found upstream | One agent, one new model per invocation |
| Writes | Model registry only (§1) | Model registry (§1) + optional promotion writes (§2, §3, §4 hardcoded, §5 aidocs/claudecode_tools.md, §7 default-sensitive tests) |
| Typical use | "Refresh everything periodically" | "Vendor announced a specific model, add it and maybe make it default" |
| Determinism | Web-research results vary | Fully deterministic given inputs |
| Dry-run | No | Yes (`--dry-run`) |

### Skill API

```
/aitask-add-model [--agent <a>] [--name <n>] [--cli-id <id>] [--notes <s>]
                  [--promote] [--promote-ops <csv>]
                  [--dry-run] [--batch]
```

- **Required inputs** (prompt interactively if omitted, unless `--batch`):
  `agent`, `name`, `cli_id`
- **Optional inputs:**
  - `notes` (prompt if omitted)
  - `--promote` — opt-in to promote mode
  - `--promote-ops <csv>` — which operations to re-default onto the new model.
    When `--promote` is set without `--promote-ops`, present a multiSelect of
    the operations listed in `codeagent_config.json` defaults.
- **Flags:**
  - `--dry-run` — print per-file unified diff and exit without writing
  - `--batch` — forbid interactive prompts; fail if any required input is
    missing

### Supported agents

| Agent | Supported in add-mode | Supported in promote-mode | Notes |
|---|---|---|---|
| `claudecode` | yes | yes (full) | Owns `DEFAULT_AGENT_STRING` + brainstorm fallbacks |
| `geminicli` | yes | yes (limited) | No equivalent `DEFAULT_AGENT_STRING`; promotion only touches `codeagent_config.json` + seed |
| `codex` | yes | yes (limited) | Same as geminicli |
| `opencode` | **limited** | no | Use `aitask-refresh-code-models` for opencode — models are gated by provider availability and discovered via `aitask_opencode_models.sh`. This skill should refuse `--agent opencode` with a clear pointer to the other skill. |

### Mode contracts

#### add mode (default) — writes

1. Append entry to `aitasks/metadata/models_<agent>.json` (initialize
   `verified` + `verifiedstats` to zero-history). Preserve existing entries'
   `verified` / `verifiedstats`.
2. Sync to `seed/models_<agent>.json` if `seed/` exists.
3. Commit:
   - `./ait git add aitasks/metadata/models_<agent>.json` and
     `./ait git commit -m "ait: Add <agent>/<name> to model registry"`
   - `git add seed/models_<agent>.json` and
     `git commit -m "ait: Sync <agent>/<name> to seed template"`

Add mode does NOT touch §2, §3, §4, §5, or §7.

#### promote mode (`--promote`) — writes all of add-mode PLUS:

4. `aitasks/metadata/codeagent_config.json` — update each op in
   `--promote-ops` to `<agent>/<name>`.
5. `seed/codeagent_config.json` — synced.
6. If `agent == claudecode` and any promote-op exists:
   - `.aitask-scripts/aitask_codeagent.sh` line 21: replace
     `DEFAULT_AGENT_STRING="..."` with the new value.
   - `.aitask-scripts/aitask_codeagent.sh` line 663: replace the human-readable
     "Hardcoded default: ..." line.
7. If any promote-op starts with `brainstorm-`:
   - No source-code changes needed — `brainstorm_crew.py` reads
     `agent_string` exclusively from `codeagent_config.json` (updated
     in step 4 above). `crew_meta_template.yaml` was deleted (t579_5).
     `aitask_brainstorm_init.sh` no longer passes hardcoded fallbacks.
8. Commit code changes as one commit:
   - `git add .aitask-scripts/aitask_codeagent.sh .aitask-scripts/brainstorm/brainstorm_crew.py .aitask-scripts/aitask_brainstorm_init.sh seed/codeagent_config.json`
   - `git commit -m "feature: Promote <agent>/<name> to default for <ops>"`
   - Config (metadata) commit separately via `./ait git`

Promote mode does NOT touch §5 docs (except
`aidocs/claudecode_tools.md` — see below) or §7 tests; those go to the
manual-review list.

#### Optional aidocs/claudecode_tools.md update

When `agent == claudecode` and the promote-ops include `pick`, the skill
also updates line 5 of `aidocs/claudecode_tools.md` (the `**Model:** Claude
<Display> (<cli_id>)` line). This file is meant to always reflect the
current default pick model, so it's part of the automated set rather than
the manual-review list. Derivation: the human-readable display name is
supplied via an optional `--display-name` flag (default: title-case of
`<name>` with version dots reinserted — e.g., `opus4_7` → `Opus 4.7`).

### Manual-review output

After every real write (not on dry-run), the skill emits a block like:

```
=== Manual review follow-ups ===
These files reference the previous default and may need updating:
  tests/test_codeagent.sh           (default-sensitive assertions)
  tests/test_brainstorm_crew.py     (BRAINSTORM defaults)
  website/content/docs/commands/codeagent.md
                                    (defaults table + line 167 hardcoded default)
  website/content/docs/skills/aitask-refresh-code-models.md
                                    (naming-convention example — OK to skip)
See aidocs/model_reference_locations.md for the full audit.
```

Emitted only in promote-mode (add-mode doesn't change defaults, so nothing
is left stale).

### Dry-run semantics

- For each file the skill would write, print `diff -u <old> <new>` to stdout
  (using a tempfile for the proposed content).
- Exit 0 without writing anything.
- Manual-review block is NOT emitted on dry-run (implied by the diff list).

### Commit strategy (full)

1. Metadata commit: `./ait git` for `aitasks/metadata/models_<agent>.json`
   (and `codeagent_config.json` in promote mode). Message:
   `ait: Add <agent>/<name> to model registry` or
   `ait: Promote <agent>/<name> to default for <ops>`.
2. Seed commit: plain `git` for `seed/*.json`. Message:
   `ait: Sync <agent>/<name> to seed template`.
3. Source commit (promote-mode only): plain `git` for
   `.aitask-scripts/` and `aidocs/claudecode_tools.md`. Message:
   `feature: Promote <agent>/<name> to default (<ops>)`.

Rationale: keeps the task-data branch (`aitasks/`, `aiplans/`) strictly
separate from source code per `CLAUDE.md`. Each commit is reviewable
independently and reversible independently.

### Helper bash script: `.aitask-scripts/aitask_add_model.sh`

Subcommands for testability:

| Subcommand | Purpose |
|---|---|
| `add-json --agent <a> --name <n> --cli-id <id> --notes <s> [--dry-run]` | Append entry to `models_<agent>.json` and sync seed |
| `promote-config --agent <a> --name <n> --ops <csv> [--dry-run]` | Update `codeagent_config.json` + seed |
| `promote-default-agent-string --agent <a> --name <n> [--dry-run]` | Update `DEFAULT_AGENT_STRING` (claudecode only); error if not claudecode |
| `promote-brainstorm --agent <a> --name <n> --ops <csv> [--dry-run]` | No-op after t579_5: brainstorm agent_strings now come exclusively from codeagent_config.json (updated by `promote-config`) |
| `promote-aidocs --agent <a> --name <n> --display-name <s> --cli-id <id> [--dry-run]` | Update `aidocs/claudecode_tools.md` line 5 |
| `emit-manual-review --agent <a> --old-name <n> --new-name <n>` | Print the manual-review list |

All subcommands:
- Use `jq` for JSON (never sed on JSON)
- Use `sed_inplace` (from `lib/terminal_compat.sh`) for text edits
- Anchor regex on structural markers (e.g., `BRAINSTORM_AGENT_TYPES = {` line)
  to avoid false positives
- Are idempotent (re-running after a successful apply yields zero diffs)
- Validate every JSON file after write (`jq . <f> >/dev/null` must succeed)
- On `--dry-run`, print `diff -u` and exit 0

SKILL.md orchestrates these subcommands.

### Rollback safety

- `--dry-run` shows exactly what would change
- If any step fails mid-apply, the skill aborts BEFORE committing, leaving
  uncommitted edits on disk for the user to inspect and `git checkout --
  <file>` if needed
- Commits are not amended (per CLAUDE.md), so each reversible via `git
  revert` without rewriting history

### Unit tests (`tests/test_add_model.sh`)

Cover:
1. `add-json` inserts a new entry at end of `models` array, preserving
   existing entries' `verified` and `verifiedstats`.
2. `add-json` is idempotent: second run with same inputs fails with clear
   "already exists" error (non-zero exit).
3. `promote-config` updates only the ops listed, leaves others intact.
4. `promote-default-agent-string` errors when `--agent` is not `claudecode`.
5. `promote-default-agent-string` replaces line 21 and line 663 of
   `aitask_codeagent.sh` correctly.
6. `promote-brainstorm` updates python dict, yaml, AND bash fallback lines
   atomically — failure in one reverts the others OR fails loudly.
7. `--dry-run` across all subcommands emits diffs AND leaves filesystem
   unchanged (verify via `git diff --quiet` after run).
8. Invalid inputs fail with clear errors:
   - unknown agent
   - malformed `name` (uppercase, spaces)
   - malformed `cli_id` (empty)
   - `--agent opencode` → "Use aitask-refresh-code-models for opencode"
9. JSON validation: `jq .` succeeds on every produced JSON file.

### Open questions to resolve at t579_2 time

1. **opencode handling.** Should the skill refuse `opencode` outright, or
   allow add-mode (bypassing `aitask_opencode_models.sh` discovery) with a
   warning? This audit recommends refusing — but if you have a concrete
   use case where opencode needs a manual add, reconsider.
2. **Idempotent re-run semantics.** When the model already exists in the
   registry, should `add-json` error (safer) or succeed silently? This
   audit recommends error — caller should use `--promote` alone (no
   add-json) if they want to re-promote.
3. **Display name derivation.** Auto-derive from `<name>` or always require
   `--display-name`? This audit recommends auto-derive with a manual
   override flag — covers 90% of cases without friction.
4. **Manual-review list format.** Path-only (one per line) is machine-grep-able,
   bulleted with reasons is human-readable. This audit recommends the
   bulleted form (see "Manual-review output" above).

### Implementation order for t579_2

1. `.aitask-scripts/aitask_add_model.sh` with `add-json` subcommand
2. `tests/test_add_model.sh` — add-mode cases (1, 2, 7, 9 from above)
3. `promote-config` subcommand + tests (3, 7, 9)
4. `promote-default-agent-string` subcommand + tests (4, 5, 7)
5. `promote-brainstorm` subcommand + tests (6, 7)
6. `promote-aidocs` subcommand
7. `emit-manual-review` subcommand
8. `.claude/skills/aitask-add-model/SKILL.md` orchestration
9. Final end-to-end test with `--dry-run` against a fake `opus4_8`
10. Validation invocations in t579_3 (real opus4_7 promotion)
