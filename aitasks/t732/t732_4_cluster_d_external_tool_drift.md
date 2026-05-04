---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [testing, external_tools, codex, gemini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-03 16:30
updated_at: 2026-05-04 23:57
---

## Context

Child 4 of t732. Cluster D: external-tool / agent-metadata drift. Two failing tests, two distinct sub-issues with related "drift between external tool and our config/expectations" theme.

## Failing tests (verified on `main` @ `74c59788` today)

### Sub-issue (a): tests/test_codex_model_detect.sh
```
Total runs: 24 / MATCH: 0 / PARTIAL: 2 / MISMATCH: 6 / ERROR: 16
```
Codex CLI model-name detection has drifted catastrophically (0/24 exact matches). Either Codex changed its model output format, or `aitasks/metadata/models_codex.json` is out of date.

### Sub-issue (b): tests/test_gemini_setup.sh (Test 8)
```
ok:   Created ~/.gemini/policies/aitasks-whitelist.toml
PASS: Created global policy file
PASS: Global policy contains aitask rules
info:   Existing ~/.gemini/policies/aitasks-whitelist.toml found — merging policies...
/home/ddt/.aitask/bin/python3: line 2: /tmp/tmp.XXXXXX/global_home/.aitask/venv/bin/python: No such file or directory
```
Test 8 ("Global Gemini policy install helper") sets up a temp HOME at `/tmp/.../global_home/`, then the merge helper invokes `/tmp/.../global_home/.aitask/venv/bin/python` — but no venv exists at that temp path. Either the test must seed a venv at the temp HOME, or `/home/ddt/.aitask/bin/python3` must not insist on the venv path when called from a non-default HOME. Suggests an absolute-path bake-in via the `.aitask/bin/python3` symlink/wrapper.

## Root cause hypothesis

- **(a)**: Codex CLI's `--list-models` (or whatever `aitask_resolve_detected_agent.sh` uses) output has drifted. `models_codex.json` references model IDs no longer reported as-is. Use the `/aitask-refresh-code-models` skill to refresh.
- **(b)**: `/home/ddt/.aitask/bin/python3` (a wrapper line 2 references `$HOME/.aitask/venv/bin/python`) honors `$HOME` at invocation time, but the test's temp HOME points to a directory with no venv. Either:
  - test bug: must `cp -r` (or symlink) a venv into `$temp_HOME/.aitask/venv/` before invoking helpers, OR
  - script bug: `aitask_path.sh` / the venv shim should locate the venv at the absolute install path, not via `$HOME`.

## Key files to investigate / modify

- `aitasks/metadata/models_codex.json` — refresh via `/aitask-refresh-code-models codex`
- `.aitask-scripts/aitask_resolve_detected_agent.sh` — codex parsing logic
- `~/.aitask/bin/python3` (wrapper) — where does it look up the venv?
- `.aitask-scripts/lib/aitask_path.sh` — PATH/venv lookup logic
- `tests/test_gemini_setup.sh` Test 8 setup — may need to seed a venv at the temp HOME
- `.aitask-scripts/aitask_gemini_policy_merge.sh` (or wherever the merge helper is)

## Reference patterns

- `.claude/skills/aitask-refresh-code-models/SKILL.md` — the skill that refreshes `models_*.json` files.
- `aitasks/metadata/models_claudecode.json` and `models_gemini.json` — for the JSON format pattern.
- t695_3 commit (`709380a5`) — added `~/.aitask/bin/` symlink and scoped PATH lib; check whether the python3 wrapper from there is the one being invoked.

## Implementation plan

### For sub-issue (a)
1. Run the refresh skill: `/aitask-refresh-code-models codex` (or equivalent) to regenerate `models_codex.json`.
2. Re-run the test: `bash tests/test_codex_model_detect.sh`.
3. If still failing, inspect what `aitask_resolve_detected_agent.sh` is parsing — its regex/string-extraction may need updating.

### For sub-issue (b)
1. `bash -x tests/test_gemini_setup.sh 2>&1 | sed -n '/Test 8/,/Test 9/p'` to see exact setup.
2. Inspect `~/.aitask/bin/python3` line 2.
3. Decide: fix the test (seed a venv at the temp HOME) or fix the wrapper (use the absolute install-time venv path, not `$HOME`-relative).
4. Patch and re-test.

## Verification

- `bash tests/test_codex_model_detect.sh` reports `MATCH: 24` (or accept a documented partial-match threshold if Codex output is genuinely fuzzy).
- `bash tests/test_gemini_setup.sh` passes all sub-tests.
- `./ait setup` smoke test still works on the dev machine.
