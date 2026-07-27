---
Task: t1264_manualverification_checklist_with_plain_bullets_is_unrecover.md
Worktree: current directory
Branch: main
Base branch: main
---

## Implementation Plan

1. Update `.aitask-scripts/aitask_verification_parse.py` with a narrowly scoped parser for plain Markdown bullets and a `convert` subcommand.  The command will locate the existing verification-checklist section, rewrite only its unmarked `- ` bullets to pending `- [ ]` items while preserving their indentation and text, retain already-marked checkbox items unchanged, update `updated_at`, and fail clearly when no convertible bullets exist.
2. Extend `.claude/skills/task-workflow/manual-verification.md`'s `TOTAL:0` recovery branch with a “Convert existing bullets” option.  It will invoke the parser helper, re-run `summary`, and continue through the normal checklist loop.  Regenerate the rendered profile variants and their golden fixtures with the repository’s skill-render verification tooling so all profiles offer the same recovery.
3. Add focused unit coverage in `tests/test_verification_parse.py` for conversion of a checklist section containing plain bullets: assert text/indentation are preserved, `summary` reports the expected total, and an existing checkbox is not altered.  Retain the refusal behavior for `seed` when a section already exists.
4. Run the focused Python test module and the skill-render verification tests.  Record actual results and any deviation in this plan’s Final Implementation Notes before the standard Step 9 review, gate execution, and archival steps.

## Verification

- `python3 tests/test_verification_parse.py`
- `bash tests/test_skill_render_task_workflow.sh`

## Risk

### Code-health risk: low
- None identified.

### Goal-achievement risk: low
- None identified.

## Final Implementation Notes

- Added the `convert` parser subcommand for plain bullets inside an existing verification-checklist section. It preserves item text and indentation, skips pre-existing checkbox items, updates task metadata atomically, and errors without mutating when there is nothing to convert.
- Added the checklist-runner recovery option and refreshed the committed remote profile snapshots plus golden render fixtures.
- Verification passed: `python3 tests/test_verification_parse.py` (46 tests) and `bash tests/test_skill_render_task_workflow.sh` (122 checks).
