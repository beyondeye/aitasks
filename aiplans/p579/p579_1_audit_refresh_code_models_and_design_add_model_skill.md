---
Task: t579_1_audit_refresh_code_models_and_design_add_model_skill.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_2_*.md, aitasks/t579/t579_3_*.md, aitasks/t579/t579_4_*.md
Archived Sibling Plans: aiplans/archived/p579/p579_*_*.md
Worktree: aiwork/t579_1_audit_refresh_code_models_and_design_add_model_skill
Branch: aitask/t579_1_audit_refresh_code_models_and_design_add_model_skill
Base branch: main
plan_verified:
  - claudecode/claude-opus-4-7 @ 2026-04-16 23:33
---

# Plan: t579_1 — Audit refresh-code-models and design aitask-add-model

## Context

First of 4 children for t579. Produces the audit + design spec that drives
t579_2's skill implementation. No source code changes — only a new doc at
`aidocs/model_reference_locations.md`.

See parent plan `aiplans/p579_support_for_opus_4_7.md` for full background on
why `aitask-refresh-code-models` alone is insufficient.

## Step 1 — Complete the inventory

The parent plan already identified ~15 files. Verify and expand:

```bash
# Catch anything we missed — exclude verifiedstats (historical data) and
# archived content
grep -rn 'opus4_6\|opus_4_6\|claude-opus-4-6\|opus4\|sonnet4_6\|haiku4_5' \
  aitasks/metadata/ seed/ .aitask-scripts/ aidocs/ website/content/docs/ \
  tests/ .claude/skills/ .gemini/ .codex/ .opencode/ .agents/ 2>/dev/null \
  | grep -v 'verifiedstats' \
  | grep -v 'archived/'
```

Categorize each hit into one of:
- `covered_by_refresh` — written by `aitask-refresh-code-models` today
- `needed_for_add` — must be written when a new model is registered (even
  without promotion)
- `needed_for_promote` — must be written only when the new model is being
  made the new default for one or more operations
- `informational_only` — example string / format illustration / historical
  fixture that should stay as-is

## Step 2 — Write `aidocs/model_reference_locations.md`

Structure:
1. **Inventory table** — one row per reference, columns: file, line, context,
   tag, notes
2. **Summary matrix** — per-tag count, grouped by agent (claudecode / geminicli
   / codex / opencode / cross-cutting)
3. **Design spec for `aitask-add-model`** — see Step 3 below

## Step 3 — Design spec

Sections:

### 3.1 Skill API
- Directory: `.claude/skills/aitask-add-model/SKILL.md`
- CLI surface (preferred invocation from inside Claude Code):
  ```
  /aitask-add-model [--agent <a>] [--name <n>] [--cli-id <id>]
                    [--notes <s>] [--promote] [--promote-ops <csv>]
                    [--dry-run] [--batch]
  ```
- Required inputs: `name`, `cli_id`, `agent`. Prompt interactively if any
  omitted unless `--batch` forbids prompting.
- `--promote` opts into promote-mode. `--promote-ops` controls which ops are
  re-defaulted; prompted via multiSelect if `--promote` is set without it.

### 3.2 Mode contracts

| Mode | Writes | Does NOT touch |
|---|---|---|
| add (default) | `aitasks/metadata/models_<agent>.json`, `seed/models_<agent>.json` | everything else |
| promote | add-mode files PLUS `codeagent_config.json` (+ seed), `DEFAULT_AGENT_STRING` (claudecode only), `BRAINSTORM_AGENT_TYPES` + `crew_meta_template.yaml` (brainstorm-* ops only) | docs, tests, help-text examples |

### 3.3 Agent-specific quirks
- **opencode** uses `aitask_opencode_models.sh` for discovery. Decide: does
  add-mode write to `models_opencode.json` directly, or delegate to the
  discovery script? Recommended: direct write (keeps the skill deterministic),
  but document in SKILL.md that `aitask-refresh-code-models` is the better
  path for opencode because providers gate availability.
- **claudecode** owns `DEFAULT_AGENT_STRING` in `aitask_codeagent.sh`; other
  agents do not have an equivalent hardcoded default.
- **Brainstorm** overrides live in `codeagent_config.json` keys like
  `brainstorm-explorer`; the python/yaml hardcoded defaults are fallbacks and
  only need updating when the default is changed (promote-mode only).

### 3.4 Dry-run + manual-review output
- Dry-run: print `diff -u` per affected file; exit without writing
- Manual-review list: emitted after a real write (not on dry-run), names
  every file that matched the grep sweep but falls in the
  `informational_only` or `needed_for_promote` but skipped bucket. Format:
  one path per line with a short reason.

### 3.5 Commit strategy
Per `CLAUDE.md`:
- `./ait git` for `aitasks/metadata/` (lands on task-data branch)
- Plain `git` for `seed/` and `.aitask-scripts/`
- Separate commits for metadata vs. source (per `CLAUDE.md` "Never mix")
- Messages: `ait: Add model <name> for <agent>` (metadata), `feature: Promote
  <agent>/<name> to default (...)` (source)

### 3.6 Helper bash
Recommend `.aitask-scripts/aitask_add_model.sh` with subcommands
(`add-json`, `promote-config`, `promote-default-agent-string`,
`promote-brainstorm`) so individual pieces are testable. SKILL.md orchestrates
the subcommands.

### 3.7 Open questions (escalate at t579_2 time)
- Does opencode add-mode diverge from the others?
- Should `--batch` mode require `--yes` to skip confirmation, or should
  `--batch` alone imply non-interactive?
- Exact phrasing of the manual-review list — bullet list vs. path-only?

## Verification

- `aidocs/model_reference_locations.md` exists and is committed
- Every file grep'd in Step 1 appears in the inventory
- Design spec covers the API surface thoroughly enough that t579_2 can
  implement without re-exploring
- No source-code changes beyond the new doc

## Commit

```bash
git add aidocs/model_reference_locations.md
git commit -m "documentation: Audit refresh-code-models and design add-model skill (t579_1)"
./ait git push
```

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 579_1`.

## Final Implementation Notes

- **Actual work done:** Created `aidocs/model_reference_locations.md`
  containing (1) a categorised inventory of every file in the repo that
  references a specific Claude model name or default agent string, tagged
  with `covered_by_refresh` / `needed_for_add` / `needed_for_promote` /
  `informational_only`, and (2) a full design spec for the new
  `aitask-add-model` skill covering API, mode contracts, multi-agent
  handling, dry-run semantics, commit strategy, helper subcommands, and
  unit-test cases.

- **Deviations from plan:** Expanded the design-spec section beyond the
  minimum listed in the plan to include an "Open questions" section (4
  concrete questions for t579_2 to resolve), an "Implementation order" list
  for t579_2, and a specific sub-file list per promote-mode step (e.g.,
  `aitask_codeagent.sh` line 21 AND line 663; `aitask_brainstorm_init.sh`
  lines 126-130 as additional fallback — not originally in the parent
  plan's gap analysis but found during the inventory sweep).

- **Issues encountered:**
  - The grep sweep produced ~191 hits; SVG asset files under
    `website/static/imgs/` contain embedded model strings inside
    XML-encoded paths — these were excluded as generated assets.
  - `aitask_codeagent.sh` line 663 ("Hardcoded default: claudecode/opus4_6")
    was initially flagged `informational_only` because it looks like help
    text, but it's actually a human-readable reflection of the real
    DEFAULT_AGENT_STRING — promoted to `needed_for_promote` in the
    inventory.
  - `aitask_brainstorm_init.sh` lines 126-130 were flagged as additional
    fallback defaults (not just examples) — the shell script uses them as
    real fallbacks when the config and the python hardcoded defaults both
    miss. Added to `needed_for_promote`.
  - The `ait codeagent coauthor` resolver rejects fallback agent strings
    like `claudecode/claude-opus-4-7` (it expects the short-name form
    `claudecode/opus4_7`). This is expected because opus4_7 isn't in the
    registry yet — t579_3 fixes it. No coauthor trailer was added to this
    task's commit.

- **Key decisions:**
  - Recommended refusing `--agent opencode` in the new skill (point users
    to `aitask-refresh-code-models` instead) because opencode's model list
    is provider-gated and CLI-discovered.
  - Recommended `aidocs/claudecode_tools.md` line 5 is updated
    automatically by the skill (promote-mode + claudecode + pick op)
    rather than deferred to the manual-review list — it's a simple
    one-line default reflection, always the same format.
  - Recommended `aitask_brainstorm_init.sh` fallback lines 126-130 are
    updated by `promote-brainstorm` subcommand — they're real fallback
    defaults not examples.

- **Notes for sibling tasks:**
  - **For t579_2:** Follow the 10-step implementation order at the end of
    the design spec. Build subcommands bottom-up and test each before
    moving on. Use `jq` for ALL JSON, `sed_inplace` (from
    `lib/terminal_compat.sh`) for text, anchored regex only.
  - **For t579_3:** The full file set the skill should change is in §2, §3
    of the inventory, plus `aidocs/claudecode_tools.md:5`. After running
    the skill, capture the emitted manual-review block verbatim for
    t579_4.
  - **For t579_4:** The default-sensitive tests are
    `tests/test_codeagent.sh` and `tests/test_brainstorm_crew.py`. The
    docs work is concentrated in
    `website/content/docs/commands/codeagent.md` (defaults table lines
    54-57, hardcoded-default line 167). The
    `aitask-refresh-code-models.md` naming-convention example is
    `informational_only` — do NOT update. Many test files pass
    `claudecode/opus4_6` as an incidental stable argument — these are
    `informational_only` fixtures and should stay untouched.
