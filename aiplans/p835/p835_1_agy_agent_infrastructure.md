---
Task: t835_1_agy_agent_infrastructure.md
Parent Task: aitasks/t835_add_agy_antigravity_cli_support.md
Sibling Tasks: aitasks/t835/t835_2_agy_skill_rendering.md, aitasks/t835/t835_3_agy_setup_install_release.md, aitasks/t835/t835_4_agy_documentation.md, aitasks/t835/t835_5_agy_cleanup_refresh_verify.md, aitasks/t835/t835_6_audit_and_reorganize_adding_a_new_codeagent_doc.md, aitasks/t835/t835_7_manual_verification_add_agy_antigravity_cli_support.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-29 12:37
---

# Plan: t835_1 — Add agy to agent infrastructure (verify path)

## Context

This is the **verify-mode** pass over an already-approved plan that lives at
`aiplans/p835/p835_1_agy_agent_infrastructure.md`. The original plan was
written shortly before this pick. Verification confirms the file-by-file
inventory and ordering are still accurate; the only material change is
that the **model-id detection surface** for agy (deliberately deferred in
the original plan as a "needs practical test in a real agy session" task)
can now be pinned, because agy is installed locally and a viable surface
was identified during verification.

## Verification findings (against current main)

- All five `SUPPORTED_AGENTS=(claudecode codex opencode)` arrays still
  exist at the inventoried line numbers (drift within ±2 lines):
  `agent_string.sh:28`, `aitask_resolve_detected_agent.sh:23`,
  `aitask_verified_update.sh:12`, `aitask_usage_update.sh:12`,
  `aitask_add_model.sh:24` (the last one explicitly omits opencode).
- `aitask_codeagent.sh` dispatch sites (`get_cli_binary` /
  `get_model_flag` upstream in `agent_string.sh`, plus
  `get_agent_coauthor_name` / `get_agent_coauthor_email` /
  `build_invoke_command` in `aitask_codeagent.sh`) all match the
  inverse-blueprint pattern (`p812_1` final notes).
- `agent_model_picker.py` `MODEL_FILES` dict + `_MODES` tuple are intact;
  the docstring still says "six modes" / "through six modes" (lines 9
  and 269) — both must flip to "seven".
- `stats/stats_data.py` `AGENT_DISPLAY_NAMES` at L56-61 and the three
  agent tuples at L250, L275, L450 all match the plan.
- `monitor/prompt_patterns.py` `PROMPT_PATTERNS_BY_AGENT` (L25-40) holds
  `claude`, `codex`, `opencode`, `all` — agy needs to slot in
  alphabetically before `all`.
- `settings/settings_app.py` `CONFIG_FILE_DESCRIPTIONS` (L126-134) and
  the pickrem-rerender loop tuple (`("claude", "codex", "opencode")` at
  L2531) are unchanged. The hard-coded `× 3 agents` message string lives
  at L2554.
- `aitask_add_model.sh` SUPPORTED_AGENTS (L24) + help-text (L285) match
  the plan; the file already special-cases `opencode` via the
  `validate_agent` die-message.
- `aitasks/metadata/models_agy.json` does not exist — to be created.
- `.claude/skills/task-workflow/model-self-detection.md` has no agy
  branch (claude, codex, opencode only).

## Decision: agy model-id detection surface

Candidates tested locally (agy 1.0.2 installed at
`/home/ddt/.local/bin/agy`):

1. `agy --version` → returns `1.0.2` (CLI version only — unusable).
2. `agy --print "what model are you?"` → returns
   `Gemini 3.5 Flash` (model self-reports unreliably — the configured
   model is actually `Gemini 3.5 Flash (High)`; not usable).
3. `~/.gemini/settings.json` → no `model` field.
4. **`~/.gemini/antigravity-cli/settings.json` → has a top-level
   `"model": "Gemini 3.5 Flash (High)"` field, written and updated by
   the CLI on selection. Read via `jq -r '.model // empty' …`.** Works
   headless, present on first run after authentication.

Chosen surface: **`~/.gemini/antigravity-cli/settings.json` → `.model`,
with the parenthetical effort suffix stripped**.

Rationale: written by agy itself on model selection (verified via
`cli.log` line `Propagating selected model override to backend: label="…"`
which matches the settings file value byte-for-byte); persistent across
sessions; readable without invoking agy.

**Effort suffix stripping.** The raw value embeds an effort/reasoning
level inside a trailing parenthetical — e.g. `"Gemini 3.5 Flash (High)"`,
`"Gemini 3.5 Flash (Medium)"`. Confirmed by binary inspection
(`strings ~/.local/bin/agy`) and runtime test: agy has **no
command-line flag, subcommand, or env var** to set the model or the
effort level. The user interacts with agy's UI, which writes the chosen
combination to the settings.json `.model` field. Because the framework
convention is that `cli_id` represents the value that *could* be set via
the agent's CLI to reproduce the same launch, and effort is not
CLI-settable for agy, **the `cli_id` excludes the effort suffix**. The
base model name (e.g. `"Gemini 3.5 Flash"`) is what `cli_id` stores; the
effort suffix is treated as runtime state, not identity.

Detection command:

```bash
jq -r '.model // empty' ~/.gemini/antigravity-cli/settings.json \
  | sed -E 's/ +\([^)]+\)$//'
```

Examples: `"Gemini 3.5 Flash (High)"` → `Gemini 3.5 Flash` →
`agent_string` `agy/gemini_3_5_flash`.

## Implementation outline (mirrors approved plan)

The original plan's step ordering remains. The only refinements are
(a) Step 1 now has a concrete answer, and (b) two structural choices
that the inverse-blueprint left open are pinned below.

1. **Identity layer** — add `agy` to all 5 `SUPPORTED_AGENTS` arrays in
   alphabetical order `(agy claudecode codex opencode)`. Mirror codex in
   `get_cli_binary` (`agy) echo "agy"`), `get_model_flag` (`agy) echo
   "-m"` — but see open question below), `get_agent_coauthor_name`,
   `get_agent_coauthor_email`, `build_invoke_command`.
   - **No custom label helper** (no `format_agy_model_label`) — agy
     cli_ids like `"Gemini 3.5 Flash (High)"` already render correctly
     via `stats_data.py::titleize_words` / `slugify_key` fallback paths;
     adding a regex would over-fit a single product line.
2. **Detection wiring** — `aitask_resolve_detected_agent.sh` is data-driven
   (loads `models_<agent>.json`) so adding `agy` to SUPPORTED_AGENTS plus
   creating `models_agy.json` is sufficient; no new branch needed there.
3. **Self-detection procedure** — add an agy bullet to
   `model-self-detection.md` Step 2 (the per-agent "Obtain your current
   model ID" list) using the chosen surface.
4. **Model picker** — add `"agy": METADATA_DIR / "models_agy.json"` to
   `MODEL_FILES` and `("agy", "All Agy models")` to `_MODES`. Flip
   "six modes" → "seven modes" in both the module docstring (L9) and
   the class docstring (L269).
5. **Stats** — add `"agy": "Antigravity"` to `AGENT_DISPLAY_NAMES` and
   `"agy"` to each of the three agent tuples (L250, L275, L450). No
   regex addition in `model_key_from_cli_id` / `model_display_from_cli_id`
   — the `slugify_key` / `titleize_words` fallback handles
   `"Gemini 3.5 Flash (High)"` → key `gemini_3_5_flash_high`, display
   `Gemini 3.5 Flash (High)` (parens preserved by titleize since it
   only splits on `[-_]+`).
6. **Monitor** — `PROMPT_PATTERNS_BY_AGENT["agy"] = []` (placeholder;
   populated when wording is observed).
7. **Settings TUI** —
   - `CONFIG_FILE_DESCRIPTIONS["models_agy.json"] = "Antigravity CLI (agy) model list and verification scores"`.
   - Pickrem auto-rerender loop: **add `"agy"` to the loop tuple** at
     L2531 (post-t834 each agent renders into a distinct
     `aitask-pickrem-remote-<agent>-` dir under the shared root, so agy
     needs its own render invocation).
   - `root_map["agy"] = ".agents/skills"` at L2560 (same physical root
     as codex).
   - Bump `× 3 agents` → `× 4 agents` at L2554.
   - **NOTE (out-of-scope upstream defect):** `_pickrem_rendered_paths`
     globs `<root>/aitask-pickrem-remote-` (no agent suffix), which has
     not existed for codex since t834 landed. The function has been
     silently a no-op for codex (and will be for agy too) — needs a
     follow-up. Recorded under "Upstream defects identified" in Final
     Implementation Notes per workflow conventions.
8. **add-model whitelist** — append `agy` to `SUPPORTED_AGENTS` in
   `aitask_add_model.sh` and to the help-text "Supported agents:" line.
9. **Stub model file** — create `aitasks/metadata/models_agy.json` with a
   single placeholder entry mirroring the codex schema:
   ```json
   {
     "models": [
       {
         "name": "gemini_3_5_flash",
         "cli_id": "Gemini 3.5 Flash",
         "notes": "Placeholder stub; populated by t835_5 via /aitask-refresh-code-models. cli_id stores the base model name without the effort suffix — effort is runtime state, not identity (agy has no CLI flag to set either).",
         "verified": {},
         "verifiedstats": {},
         "usagestats": {}
       }
     ]
   }
   ```
   - Used `gemini_3_5_flash` as the placeholder name (matches the
     `slugify_key` output for the effort-stripped cli_id). t835_5 will
     replace this with the real model catalogue.

## Open questions answered during verification

- **`get_model_flag` value for agy?** agy has **no model flag at all** —
  not via CLI argument, subcommand, or environment variable. Model and
  effort are chosen exclusively in the interactive UI; the choice
  persists to `~/.gemini/antigravity-cli/settings.json` and is read on
  every CLI invocation. Confirmed by:
    1. `agy --help` and `agy help` — no `--model` / `-m` flag.
    2. Empty `env | grep -iE "gemini|agy|antigrav"` and binary string
       inspection — no env-var override.
    3. Runtime test: `agy --model=flash --print "…"` errors with
       `flags provided but not defined: -model`.

  This is **a striking anomaly** versus every other supported agent
  (Claude Code, Codex, OpenCode) all expose first-class CLI model
  selection. The framework's `build_invoke_command` assumes every agent
  accepts `<binary> <flag> <cli_id> [<args>]`; agy breaks that
  assumption. The references to `--model=<flash_lite|flash|pro>` found
  inside the agy binary (`strings ~/.local/bin/agy`) appear to belong
  to an internal `agentapi` helper that is not exposed via the user-
  facing `agy` entry point — possibly a planned-but-not-shipped flag,
  or a Google-internal-only surface. Worth tracking as a potential
  agy upstream feature request / framework integration gap.

  **Resolution within scope of t835_1:** introduce a sentinel `none`
  return from `get_model_flag agy`, and teach `build_invoke_command`
  (and `cmd_check`) to skip the model-flag positional when the flag is
  `none`. agy launches will use whatever model the user has selected
  in the agy UI; the framework records that selection (read from
  settings.json) into `implemented_with` for stats / coauthor
  attribution. A runtime model-override mechanism for agy — likely
  pre-writing `~/.gemini/antigravity-cli/settings.json` before
  exec — is **deliberately out of scope** for this child (and arguably
  for the entire t835 parent: it deserves its own task once the
  framework needs to launch agy with a specific model from non-
  interactive contexts like the verified-update loop). For now, agy
  invocation respects the user's chosen UI state.

  **Recorded as upstream-defect-style follow-up under "Upstream
  defects identified" in Final Implementation Notes** so the missing-
  CLI-model-flag question surfaces for someone (likely an agy team
  contact or the next maintainer revisiting agy support).

- **`get_agent_coauthor_name` display label?** Use
  `"Antigravity"` (matches the product name; consistent with
  `"Claude Code"`, `"Codex"`, `"OpenCode"`). cli_id passes through
  unchanged — `"Antigravity/Gemini 3.5 Flash"`.

## Verification

- `bash tests/test_agent_string.sh tests/test_codeagent.sh tests/test_resolve_detected_agent.sh` all pass.
- `./.aitask-scripts/aitask_codeagent.sh list-agents` output includes
  `AGENT:agy BINARY:agy STATUS:available` (locally) or `not-found`
  (CI).
- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent agy
  --cli-id "Gemini 3.5 Flash"` returns
  `AGENT_STRING:agy/gemini_3_5_flash`.
- `./.aitask-scripts/aitask_codeagent.sh coauthor agy/gemini_3_5_flash`
  returns `AGENT_COAUTHOR_NAME:Antigravity/Gemini 3.5 Flash` and
  `AGENT_COAUTHOR_EMAIL:agy@aitasks.io`.
- `ait settings` launches; Models tab cycles to "All Agy models" and
  lists the stub entry without error.
- `grep -rn 'geminicli' .aitask-scripts/ aitasks/metadata/` returns
  nothing new (no accidental reversal of t812).
- `shellcheck .aitask-scripts/aitask_*.sh .aitask-scripts/lib/*.sh` —
  no new warnings.

## Out of scope (deferred to siblings)

- Skill rendering (`skill_template.py`, `agent_skills_paths.sh`,
  rendering driver) — t835_2.
- Setup / install / release flow, seed files, `setup_agy_cli()` — t835_3.
- Documentation updates (README, CLAUDE.md, website docs, changelog,
  goldens regen) — t835_4.
- Refresh + verify + cleanup of `geminicli_to_agy.md` — t835_5.
- `adding_a_new_codeagent.md` audit/reorganize — t835_6.
- End-to-end manual verification (live agy session, frontmatter check) —
  t835_7.

## Post-implementation (Step 9 reference)

After the standard Step 8 user-review approval, follow task-workflow
Step 9 (archival, push). Parent t835 is archived automatically when the
last child (t835_7) lands.
