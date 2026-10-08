---
Task: t1916_add_haiku5_5_model.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: Register claudecode/haiku5_5 (+ haiku5_5_1m) — t1916

## Context

Claude Haiku 5.5 is available in Claude Code, but the aitasks model registry has
no entry for it. That means it can't be picked per operation, and a Haiku 5.5
session self-detects to an `unregistered_*` fallback. This change only adds
entries (no default model changes, no `DEFAULT_AGENT_STRING` edit, no test
changes that depend on defaults), following the add-only `sonnet5_5_1m` change
in t1886 (95f0394cb).

### Precondition — resolved (CLI id verified)

- Claude Code **2.1.293** (npm latest; `@anthropic-ai/claude-code-linux-x64`
  unpacked into the scratchpad) has a model catalog entry
  `{id:"claude-haiku-5-5", family:"haiku", display_name:"Haiku 5.5",
  provider_ids.first_party:"claude-haiku-5-5", context:{window:1e6,
  native_1m:true, supports_1m_beta:true}, max_output_tokens:128000,
  capabilities:[effort, adaptive_thinking, rejects_disabled_thinking, …]}`.
  It also maps the `haiku` alias to `claude-haiku-5-5` and sets
  `HAIKU_ID:"claude-haiku-5-5"`. The id has **no date suffix**.
- Its context profile matches `claude-sonnet-5-5`, which already has a
  registered `[1m]` sibling (`sonnet5_5_1m`). So a `[1m]` variant exists and
  gets its own entry, `haiku5_5_1m`.
- Live probe: the installed 2.1.288 binary was called by absolute path with
  `claude -p --model <id>`, asking the model to repeat its model ID. Both ids
  were served, and each answered with the exact id: `claude-haiku-5-5` and
  `claude-haiku-5-5[1m]`. 2.1.288 printed only an `unrecognized_model` warning.
  So verbatim self-detection will match these cli_ids.

## Implementation (repo root, current branch — profile `fast`)

Use the existing helper `.aitask-scripts/aitask_add_model.sh add-json`. Do not
hand-edit the JSON. Its working copy carries uncommitted t1910 edits, but
`cmd_add_json` is functionally unchanged (only the dry-run diff labels differ).
**No t1910 file is staged or committed by this task.**

1. Dry run, then apply, for each entry:
   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode --name haiku5_5 \
     --cli-id claude-haiku-5-5 \
     --notes "Fastest model with near-frontier intelligence, 1M context, 128K output, adaptive thinking always on" --dry-run
   ./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode --name haiku5_5_1m \
     --cli-id 'claude-haiku-5-5[1m]' \
     --notes "Fastest model with near-frontier intelligence, 1M context (explicit [1m] variant), 128K output, adaptive thinking always on" --dry-run
   ```
   Then run both again without `--dry-run`. Each run appends to
   `aitasks/metadata/models_claudecode.json` with zero-history
   `verified`/`verifiedstats`, and syncs `seed/models_claudecode.json`.
2. Keep `haiku4_5` (predecessors are never removed).
3. Commit using the skill's path-scoped strategy:
   - metadata (aitask-data branch):
     `./.aitask-scripts/aitask_task_commit.sh -m "ait: Register claudecode/haiku5_5 and haiku5_5_1m" aitasks/metadata/models_claudecode.json`
   - seed (main):
     `git commit -m "ait: Sync claudecode/haiku5_5 registration to seed (t1916)" -- seed/models_claudecode.json`,
     then `git show --stat <sha>` to confirm the commit holds only that one path.

## Coordination

- **t1910** (Implementing, uncommitted): its supersession table and
  `record-supersession` verb have not landed. Per the task, don't touch them.
  Instead, send `./ait note 1910 --from 1916` saying that
  `haiku5_5`/`haiku5_5_1m` are now registered, and that a
  `claudecode: haiku4_5 → haiku5_5` edge is a candidate for its table if its
  semantics cover non-default models (`haiku4_5` is no seed default). Hedge the
  note: the registration is a tree-relative claim as of the commit.
- **t1912** (Ready, not started): no in-flight edit to `models_*.json`, so no
  conflict.

## Follow-ups (created after implementation, not part of this change)

- **OpenCode refresh** (user decision): `ait opencode-models` now offers
  `opencode/claude-haiku-5-5`. A full run adds about 27 other new models
  (opus/sonnet 5.5, gpt-6.x, …) and marks 3 unavailable, so it gets its own
  task: run `aitask_opencode_models.sh --sync-seed`, review, and commit.
- **Coauthor label defect** (pre-existing; `haiku5_5_1m` inherits it):
  `format_claude_model_label` in `.aitask-scripts/aitask_codeagent.sh` matches
  only `claude-<family>-<maj>-<min>[-date]`. So `claude-opus-5-5[1m]`,
  `claude-sonnet-5-5[1m]` and the major-only `claude-opus-5` produce the raw id
  as the coauthor name (e.g. `Claude Code/claude-opus-5-5[1m]`). It gets its
  own bug task, because `aitask_codeagent.sh` currently has another session's
  uncommitted edits.

## Verification

- `./.aitask-scripts/aitask_codeagent.sh list-models claudecode` lists `haiku5_5` and `haiku5_5_1m`.
- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id claude-haiku-5-5` → `claudecode/haiku5_5`;
  the same with `'claude-haiku-5-5[1m]'` → `claudecode/haiku5_5_1m`.
- `jq . aitasks/metadata/models_claudecode.json seed/models_claudecode.json` succeeds, and the
  new entries are identical in both files (`diff` of the two `jq` selections).
- `./.aitask-scripts/aitask_codeagent.sh coauthor claudecode/haiku5_5` → `Claude Code/Haiku 5.5`.
- `bash tests/test_add_model.sh` and `bash tests/test_codeagent.sh` pass.

Then Step 9 (Post-Implementation): archive the task and the plan per the
shared workflow.

## Risk

### Code-health risk: low
- None identified. The change only appends two entries to the registry JSON
  (plus the seed mirror), through the existing guarded helper. No code path,
  default or test changes.

### Goal-achievement risk: low
- None identified. The cli_id was verified from the shipped catalog and by a
  live round-trip in which the model reported its own id verbatim, so
  self-detection resolves to the new entries.

## Final Implementation Notes
- **Actual work done:** Registered `claudecode/haiku5_5` (`claude-haiku-5-5`) and `claudecode/haiku5_5_1m` (`claude-haiku-5-5[1m]`) via `aitask_add_model.sh add-json` (dry-run first). Each appended to `aitasks/metadata/models_claudecode.json` and synced to `seed/models_claudecode.json` with empty `verified`/`verifiedstats`. `haiku4_5` kept. No default, `DEFAULT_AGENT_STRING`, or test change.
- **Deviations from plan:** The seed commit uses the Step-8 code-commit format `feature: … (t1916)`, not the plan's draft `ait: Sync …` subject.
- **Issues encountered:** Installed Claude Code 2.1.288 lacks the id in its catalog (prints `[claude-code:unrecognized_model]`), but the API serves both ids and each self-reports verbatim. 2.1.293 (npm latest) has the full catalog entry. `test_add_model.sh` in the shared worktree includes t1910's uncommitted tests; all 114 pass, and `test_codeagent.sh` passes 236/236.
- **Key decisions:** `[1m]` sibling registered because the 2.1.293 catalog gives Haiku 5.5 the same `native_1m`/`supports_1m_beta` profile as Sonnet 5.5, which has `sonnet5_5_1m`. OpenCode is left to a follow-up full discovery refresh (user decision): a run adds about 27 other models and marks 3 unavailable. t1910 landed mid-session (6126268ff), so its supersession branch applied. The user widened the policy past framework defaults, so the `haiku4_5 → haiku5_5` edge was recorded and t1910's test control and docs were updated (see Post-Review Changes); the systematic policy is in t1927. An advisory note was also sent to (archived) t1910, note-id 2026-10-08T14:03:20Z.232741d3a4f3792e22cf1e65.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_codeagent.sh:167 — format_claude_model_label only matches claude-<family>-<maj>-<min>[-date], so [1m] ids (claude-opus-5-5[1m], claude-sonnet-5-5[1m], now claude-haiku-5-5[1m]) and major-only ids (claude-opus-5) yield the raw cli_id as the Co-Authored-By name, e.g. "Claude Code/claude-opus-5-5[1m]"`

## Post-Review Changes

### Change Request 1 (2026-10-08 16:10)
- **Requested by user:** t1910 landed mid-session (6126268ff), so the task's "t1910 has landed" branch applied. Its shipped design restricted supersession to former framework defaults ("Not recorded: models never a framework default (… haiku …)"). The user judged that restriction wrong: obsolete-model upgrade offers should not be limited to models the framework ships as defaults. Chosen scope: keep the haiku edge, fix the test and the docs here, and make the policy systematic in a follow-up task.
- **Changes made:**
  - `record-supersession --agent claudecode --old haiku4_5 --new haiku5_5` → edge `haiku4_5 → haiku5_5` (the `_1m` sibling was skipped: `haiku4_5_1m` is unregistered).
  - `tests/test_install_superseded_models.sh`: the never-offered control moves from `haiku4_5` to `haiku5_5` (nothing supersedes it). New positive case: `explore: haiku4_5` is offered `haiku5_5`.
  - The policy statements are rewritten so supersession is not limited to defaults: `website/content/docs/commands/codeagent.md` (Superseded model defaults), `website/content/docs/commands/setup-install.md`, `website/content/docs/skills/aitask-add-model.md`, `.claude/skills/aitask-add-model/SKILL.md` Notes.
  - Verified: test_install_superseded_models.sh 23/23, test_model_supersession.py OK, test_install_superseded_prompt_pty.py OK, test_add_model.sh 114/114, `check_links.py --build` SWEEP: PASSED.
- **Files affected:** .aitask-scripts/lib/model_supersessions.json, tests/test_install_superseded_models.sh, .claude/skills/aitask-add-model/SKILL.md, website/content/docs/commands/codeagent.md, website/content/docs/commands/setup-install.md, website/content/docs/skills/aitask-add-model.md

### Change Request 2 (2026-10-08 16:25)
- **Requested by user:** Review concern (low, CONFIRMED). The new add-model SKILL Notes say to declare a non-default model's successor and to "commit the table as in Step 6". But Step 6 limits the supersession-table commit to promote mode when `promote-config` printed its NOTE, so an add-only run that follows the Notes can leave the table uncommitted. Disposition: follow-up.
- **Changes made:** None in t1916's diff. Verified as valid (`record-supersession` prints the same `NOTE: commit …` line that Step 6 never names) and carried into follow-up t1927 (item 1), together with the systematic policy work.
- **Files affected:** none (follow-up task t1927 created)
