---
Task: t579_4_update_tests_and_docs_for_opus_4_7.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_1_*.md, aitasks/t579/t579_2_*.md, aitasks/t579/t579_3_*.md
Archived Sibling Plans: aiplans/archived/p579/p579_*_*.md
Worktree: aiwork/t579_4_update_tests_and_docs_for_opus_4_7
Branch: aitask/t579_4_update_tests_and_docs_for_opus_4_7
Base branch: main
---

# Plan: t579_4 — Update tests and docs for Opus 4.7

## Context

Fourth and final child for t579. Consumes the manual-review list that t579_3
captured in its Final Implementation Notes and finishes the rollout by
updating prose docs and test fixtures. After this task archives, parent t579
auto-archives.

Read first:
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Archived sibling plans: `aiplans/archived/p579/p579_1_*.md`, `p579_2_*.md`,
  `p579_3_*.md` — especially t579_3's `Manual review follow-ups for t579_4`
  and the list of failing tests

## Step 1 — Consume t579_3's manual-review list

Read t579_3's Final Implementation Notes. Each entry should resolve to a file
in Step 2 below. If the skill flagged a file not in this plan, evaluate it
case-by-case — add to scope only if it's a live-default reference, not a
format example.

## Step 2 — Tests

Run each test file BEFORE editing to record failure modes:

```bash
bash tests/test_codeagent.sh
bash tests/test_resolve_detected_agent.sh
python -m pytest tests/test_aitask_stats_py.py -v
python -m pytest tests/test_brainstorm_crew.py -v
bash tests/test_verified_update_flags.sh
```

Update to match new defaults:
- `tests/test_codeagent.sh` — replace hardcoded `opus4_6` expectations that
  represent the *current default* with `opus4_7`. Add a case asserting
  `DEFAULT_AGENT_STRING` resolves to `claudecode/opus4_7`
- `tests/test_resolve_detected_agent.sh` — add a mapping test for
  `claude-opus-4-7 → claudecode/opus4_7`
- `tests/test_aitask_stats_py.py` — add opus4_7 fixture (empty
  `verifiedstats`) alongside opus4_6
- `tests/test_brainstorm_crew.py` — update expected defaults for explorer,
  synthesizer, detailer
- `tests/test_verified_update_flags.sh` — update ONLY if fixtures reference
  `opus4_6` as the current default

Re-run all five and confirm green.

## Step 3 — Docs

- `website/content/docs/commands/codeagent.md` — update example agent strings
  and the operational-defaults table
- `website/content/docs/tuis/settings/reference.md` — single-line example
  update
- `aidocs/claudecode_tools.md` line 5 — update model reference
- `website/content/docs/skills/aitask-add-model.md` — check existing skill
  docs to see if website auto-generates from `.claude/skills/<name>/SKILL.md`.
  If manual mirror is the pattern, create the mirror. If auto, verify the
  SKILL.md has proper frontmatter (name, description) and `hugo build`
  succeeds

Preserve format-illustration references (e.g., "agent string format is
`<agent>/<model>`, e.g., `claudecode/opus4_6`") — those are generic format
demos, not live defaults.

## Step 4 — Final sweep

```bash
grep -rn 'opus4_6\|claude-opus-4-6' \
  aitasks/metadata/ seed/ .aitask-scripts/ aidocs/ website/content/docs/ \
  tests/ 2>/dev/null \
  | grep -v 'verifiedstats' \
  | grep -v 'archived'
```

Every remaining hit should either be:
- A format-illustration example that was intentionally left alone
  (document in Final Implementation Notes), OR
- A fixture that should still test the legacy 4.6 entry (also document)

## Step 5 — Website build (if applicable)

```bash
cd website && hugo build --gc --minify
```

If the build produces uncommitted files, stage and commit them separately.

## Step 6 — Commit

```bash
git add tests/ website/ aidocs/
git commit -m "documentation: Update tests and docs for Opus 4.7 default (t579_4)"
./ait git push
```

## Verification

- All 5 test files pass
- `hugo build` succeeds
- Final grep sweep returns only documented exceptions
- `/aitask-pick` displays `opus4_7` as the default model in a fresh task
- `shellcheck .aitask-scripts/aitask_*.sh` passes

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 579_4`. When this child
archives, `aitask_archive.sh` auto-archives parent t579 since all children
are complete.
