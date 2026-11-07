---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [sitrep]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-05 12:54
updated_at: 2026-11-07 18:09
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981_1** id=2026-11-07T16:10:39Z.451707d30f31dccc206aa911 from=t1981_1 from_verified=yes at=2026-11-07T16:10:39Z base=f78e2b8d59718a1e07660fef262bdf6477f09af2 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1981_1's Step 8b/8e: the blast radius of the cd-guard lint failure is wider than this task's body records. The user chose to send this here, not to create a new task.
> | 
> | `bash tests/test_cd_guard_lint.sh` (run on 2026-11-06 against main, which includes 9b6cb2761 and b70a70e9e; line numbers are dated by this note's base SHA) reported these violations in addition to tests/test_codeagent.sh:372:
> | - tests/test_file_references.sh:372 — `find16="$(cd "$TMPDIR_16/local" && \` is unconfined-andchain (line last touched by 9b6cb2761, t2209)
> | - tests/test_premise_baseline_field.sh:24 — unguarded `cd /`, and no enter_scratch_cwd call. This is the one your body says to "check whether since fixed": it was still failing then, and the file is now committed.
> | - tests/test_premise_baseline_seeding.sh:32 — unguarded `cd /`, and no enter_scratch_cwd (af399f1da, t1663_3)
> | - tests/test_label_yaml_words.sh:138 — changes cwd without calling enter_scratch_cwd first (b70a70e9e, t2214)
> | 
> | The lint summary at that moment was "90 passed, 2 failed". All of the hits above belong to those two failing checks. Re-run the lint before relying on this list: other sessions may have touched these files since.
> | 
> | None of these files were touched by t1981_1. Its new tests/test_relations_cli.sh is clean under `tests/lib/cd_guard_scan.py --check`.
