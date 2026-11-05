---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [sitrep]
gates: [risk_evaluated]
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-05 12:54
updated_at: 2026-11-05 12:54
---

## Origin
Spawned from t2175_6 during Step 8b review.

## Upstream defect
- `tests/test_codeagent.sh:372` — `output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string "$agent" --dry-run invoke sitrep 2>&1 || true)` fails `tests/test_cd_guard_lint.sh` ("unconfined-andchain"). It was introduced with t2175_4 (`bdef300b0`). The lint's second failure, at the time of t2175_6, was another session's untracked `tests/test_premise_baseline_field.sh` (no `enter_scratch_cwd`); check whether that one has since been fixed or committed.
- `tests/lib/asserts.sh:179-196` — `assert_contains` / `assert_not_contains` use `printf '%s' "$haystack" | grep -qF -- "$needle"`. When the caller runs with `set -o pipefail` and the haystack takes more than one write, `grep -q` exits on the first match, printf gets SIGPIPE, and the pipeline fails: a needle that IS present is reported missing (and `assert_not_contains` misreports the opposite way).

## Diagnostic context
- t2175_6 hit the asserts.sh flake twice in `tests/test_sitrep_corpus.sh`: once with a whole-file haystack (a premise check), and once with `case show` output during a mutant run, where the FAIL message itself printed the needle inside the haystack. The suite now carries local here-string overrides (`grep -qF -- "$needle" <<<"$haystack"`), which can be removed once the shared helper is fixed.
- The cd-guard lint failure was reproduced on the committed tree. The line is in a committed file and was not touched by t2175_6.

## Suggested fix
- asserts.sh: feed the haystack with a here-string (no pipe), and remove the local overrides from `tests/test_sitrep_corpus.sh`. Grep `tests/` for other `printf … | grep -q` assertion helpers under pipefail.
- test_codeagent.sh:372: confine the cd in a subshell per `aidocs/framework/testing_conventions.md` (e.g. `output=$( (cd "$TMPDIR_TEST" && bash …) 2>&1 ) || true`), then re-run `tests/test_cd_guard_lint.sh`.
