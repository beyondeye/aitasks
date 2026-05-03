---
Task: t732_4_cluster_d_external_tool_drift.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---

# p732_4 — Cluster D: external-tool / agent-metadata drift

## Goal

Make 2 tests green: `test_codex_model_detect.sh` (codex model registry refresh) + `test_gemini_setup.sh` Test 8 (temp-HOME venv path).

## Confirmed failures (today)

### Sub-issue (a) — Codex model detect
`Total runs: 24 / MATCH: 0 / PARTIAL: 2 / MISMATCH: 6 / ERROR: 16`. `models_codex.json` stale or codex CLI output drift.

### Sub-issue (b) — Gemini Test 8
`/home/ddt/.aitask/bin/python3: line 2: /tmp/.../global_home/.aitask/venv/bin/python: No such file or directory`. Test scaffolds a temp HOME without seeding a venv; the `python3` wrapper is `$HOME`-relative and fails.

## Steps

1. Read `aitasks/t732/t732_4_cluster_d_external_tool_drift.md` for full context.

### Sub-issue (a)
2. Run `/aitask-refresh-code-models codex` (or invoke the underlying skill scripts) to regenerate `aitasks/metadata/models_codex.json`.
3. `bash tests/test_codex_model_detect.sh` — confirm MATCH count rises.
4. If still failing, inspect `.aitask-scripts/aitask_resolve_detected_agent.sh` parsing of codex output.

### Sub-issue (b)
5. `bash -x tests/test_gemini_setup.sh 2>&1 | sed -n '/Test 8/,/Test 9/p'` to see exact setup.
6. Inspect `~/.aitask/bin/python3` line 2 and `.aitask-scripts/lib/aitask_path.sh`.
7. Decide: seed a venv in the temp HOME (test fix) OR teach the wrapper to use the absolute install-time venv path (script fix). Document the decision in Final Implementation Notes.
8. Patch and re-test.

## Verification

- `bash tests/test_codex_model_detect.sh` reports `MATCH: 24` (or accept a documented partial-match threshold).
- `bash tests/test_gemini_setup.sh` passes all sub-tests.
- `./ait setup` smoke test still works on the dev machine.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_4`.
