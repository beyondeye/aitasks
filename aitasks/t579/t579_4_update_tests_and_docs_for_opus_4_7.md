---
priority: medium
effort: low
depends: [t579_3]
issue_type: documentation
status: Ready
labels: [codeagent, ait_settings, documentation, test]
created_at: 2026-04-16 23:27
updated_at: 2026-04-17 09:35
---

## Context

This is child 4 of 4 for parent task t579 (adding Opus 4.7 support). Depends on
t579_3, which registered TWO Opus 4.7 variants and promoted the 1M context
variant to default via the `aitask-add-model` skill:
- `opus4_7` / `claude-opus-4-7` — standard variant (registered, not promoted)
- `opus4_7_1m` / `claude-opus-4-7[1m]` — 1M context variant (**promoted as default**)

The `[1m]` suffix is a Claude Code client-side signal for 1M context; the API
model ID is always `claude-opus-4-7`. The promoted default is `opus4_7_1m`.

The `aitask-add-model` skill intentionally does NOT edit prose documentation or
test fixtures — those require human curation. This task consumes the
"manual review list" emitted by the skill in t579_3 (captured in that task's
Final Implementation Notes) and updates tests and docs to reflect opus4_7_1m as
the new default. It also adds skill documentation for `aitask-add-model` if
the website auto-generation needs a stub.

## Key Files to Modify

### Tests (update fixtures + add explicit 4.7 coverage)
- `tests/test_codeagent.sh` — **TWO fixes needed:**
  1. **Pre-existing setup bug:** `setup_test_env()` (line ~73) doesn't copy
     `archive_utils.sh` which `task_utils.sh` now sources. Add:
     `cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"`
     after line 75. This bug causes the test to fail on clean main (before any
     Opus 4.7 changes).
  2. **Default assertions:** Replace `opus4_6` fixture expectations with
     `opus4_7_1m`; update `DEFAULT_AGENT_STRING` assertion.
- `tests/test_resolve_detected_agent.sh` — add mapping tests for BOTH:
  `claude-opus-4-7 → claudecode/opus4_7` AND
  `claude-opus-4-7[1m] → claudecode/opus4_7_1m` (if the resolve script
  handles the `[1m]` suffix)
- `tests/test_aitask_stats_py.py` — add opus4_7 fixture (empty
  `verifiedstats`) alongside opus4_6
- `tests/test_brainstorm_crew.py` — update expected defaults for explorer,
  synthesizer, detailer (now `opus4_7_1m`)
- `tests/test_verified_update_flags.sh` — update ONLY if fixtures reference
  `opus4_6` as the *current default*; leave references that are purely about
  an older model version alone

### Docs
- `website/content/docs/commands/codeagent.md` — update example agent strings
  and the "operational defaults" table (pick/explore/brainstorm-opus ops now
  `claudecode/opus4_7`)
- `website/content/docs/tuis/settings/reference.md` — update example showing
  the current default model
- `aidocs/claudecode_tools.md` line 5 — update to
  "**Model:** Claude Opus 4.7 (`claude-opus-4-7`)"
- `website/content/docs/skills/aitask-add-model.md` — stub or auto-generated
  from `.claude/skills/aitask-add-model/SKILL.md`. Check whether the website
  build already auto-generates from SKILL.md (look at existing skill docs) —
  if auto-gen exists, nothing to do; if manual mirror is needed, create it

## DO NOT modify

- Comments or help-text that merely use `opus4_6` as an illustrative example
  string (e.g., format docs like "agent string format: <agent>/<model> (e.g.,
  claudecode/opus4_6)") — those are generic format demos, not live defaults
- Historical verified-stats entries for opus4_6 — preserved to maintain the
  scoring history

## Reference Files for Patterns

- Parent task: `aitasks/t579_support_for_opus_4_7.md`
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Archived sibling plans: `aiplans/archived/p579/p579_1_*.md`, `p579_2_*.md`,
  `p579_3_*.md` — especially the Final Implementation Notes of p579_3 (contains
  the manual-review list + any expected test failures)
- Skill file: `.claude/skills/aitask-add-model/SKILL.md` (for doc auto-gen check)

## Implementation Plan

### 1. Consume t579_3's Final Implementation Notes
Read the manual-review list. Every entry should resolve to a file listed
above. If the skill flagged additional files not in this plan, evaluate
each — add it to scope only if it's a live default reference, not a format
example.

### 2. Tests first (fail-fast)
Run each test file BEFORE editing. Record which ones fail and how they fail.
Some should fail because defaults changed in t579_3 — that's expected. Others
may pass if the test doesn't pin the default.

Edit each failing test to match the new defaults. Re-run and confirm green.

### 3. Docs
- Examples in `codeagent.md`: convert every live-default reference; leave
  format-illustration references alone
- `settings/reference.md`: single-line update
- `aidocs/claudecode_tools.md`: single-line update (line 5)
- `aitask-add-model.md` in `website/content/docs/skills/`: check existing
  skill docs to see if there's a manual mirror pattern or auto-gen from
  `.claude/skills/<name>/SKILL.md`. If manual pattern: create the mirror.
  If auto: verify the skill's SKILL.md has a proper `description` frontmatter
  and metadata

### 4. Final sweep
`grep -rn "opus4_6\|claude-opus-4-6" aitasks/metadata/ seed/ .aitask-scripts/
 aidocs/ website/content/docs/ tests/ 2>/dev/null | grep -v verifiedstats |
 grep -v archived` — every hit should either be (a) a format-illustration
 example that was intentionally left alone (document the decision in the
 plan's Final Implementation Notes) or (b) a fixture that should still test
 the legacy 4.6 entry (also document).

### 5. Commit
- Code + test commit: `documentation: Update tests and docs for Opus 4.7 default (t579_4)`
- If website auto-gen docs need regeneration, run whatever build step the
  website uses and commit the regenerated files separately

## Verification Steps

1. Full test run passes:
   ```
   for f in tests/test_codeagent.sh tests/test_resolve_detected_agent.sh \
            tests/test_brainstorm_crew.py tests/test_verified_update_flags.sh \
            tests/test_add_model.sh; do
     bash "$f" || break
   done
   ```
   Plus `python -m pytest tests/test_aitask_stats_py.py -v`
2. `shellcheck .aitask-scripts/aitask_*.sh` passes
3. Website build succeeds (if applicable): `cd website && hugo build --gc --minify`
4. `grep` sweep described in Step 4 above returns only documented exceptions
5. `/aitask-pick` a fresh task: the displayed default model is `opus4_7`
6. Commit follows convention: `(t579_4)` suffix

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 579_4`. After this
child archives, parent t579 auto-archives since all children are complete.
Final Implementation Notes should note:
- Which tests required updates vs which already passed
- Any residual `opus4_6` references that were intentionally kept and why
- Whether the website build needed manual attention
