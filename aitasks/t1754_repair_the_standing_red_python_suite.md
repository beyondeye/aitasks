---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing]
followup_kind: upstream_defect
created_at: 2026-09-09 09:14
updated_at: 2026-09-09 09:15
---

## Context

The Python suite is **red on a clean checkout**, independently of any in-flight
work. Found while running the full suite for t1705_6; every failure was
reproduced in a pristine `git worktree` at HEAD, so none of them is caused by
that task.

`tests/run_all_python_tests.sh` therefore cannot currently be used as a
pass/fail gate: a contributor who runs it sees a red banner and has no way to
tell their own breakage from this standing set. That is the real cost — the
suite's verdict is what several workflow steps and CI depend on.

**No pending task tracks any of these.** Checked at creation time: `t1460`
concerns `TestProducerShortRegionRule` (a different rule class, and about
producer *discovery* being self-fulfilling); `t1522` asks for a **new** codex
update-prompt pattern rather than repairing an existing one; `t1116`
(Postponed) cites this module as passing "all 7 tests" and is stale (it has 22);
`t1398` / `t702` mention `test_desync_state.py` only for its fixture copy-list.

## The failures

1. **`tests/test_concern_parser.py`** —
   `TestProducerPlainWordsRule.test_production_assertion_fails_on_a_real_offender`
   (reported twice; the subtest carries `producer='leak.md'`). The negative
   control does not raise: `assertRaises(AssertionError)` sees nothing, i.e. the
   production rule no longer flags a deliberately planted offender. A guard that
   has stopped guarding — the failure mode where a green run means least.
   The paired symptom in the same module:
   `_example_prose_only_offences(text)` returns
   `['In plain words: inside the block.']` where `[]` is expected.

2. **`tests/test_desync_state.py`** —
   `DesyncStateTests.test_changelog_warns_for_data_desync_and_ignores_bad_helper_output`.

3. **`tests/test_prompt_detection.py`** — `ScriptChecksTest.test_all_checks_pass`,
   reporting `2/22` internal checks failing:
   - `_check_characterization_pattern_command_matrix`:
     `codex_yes_proceed on current_command='node': expected kind
     'codex_yes_proceed', got ''`
   - `_check_scoping_provenance_is_reported`:
     `an unresolved pane must NOT report itself as scoped`

   **Not a regression from the recent prompt-pattern work.** Bisected: the same
   two checks fail at `4166f92f1~1` and `66069bf4c~1` (2/21 there), i.e. before
   both t1557's whole-line anchor and t1540's tool-permission anchor. It is
   older than either.

## Approach

Treat each as its own diagnosis — they are unrelated areas that happen to be red
at once. For each: establish when it started failing (`git bisect` or a spot
check at a few commits), decide whether the **production** rule or the **test's
expectation** is wrong, and fix the one that is. Two of the three are guards
whose negative control has stopped firing, so "make the test pass" is the wrong
instinct: confirm the production behaviour is what the guard was written to
protect before touching the assertion.

## Verification

```bash
bash tests/run_all_python_tests.sh    # read the LAST line; expect PASSED
```

Each fix should also be checked with its own pre-fix control — revert the fix
and watch the specific assertion fail — so the repair is evidenced, not assumed.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1745** id=2026-09-09T07:28:56Z.67433831440241f22366e442 from=t1745 at=2026-09-09T07:28:56Z base=21ad464fee91b1bf0ade12e1c1d2e47ed73fe7e5 base_branch=main dirty=no host=omg16
>
> | Re-scoping evidence for the three failures. Advisory input — measured on ONE
> | machine, and the whole point below is that the result is machine-dependent, so
> | please re-check on the box you filed from before acting.
> | 
> | Measured at code-branch HEAD 21ad464fe (main, after 13e5b3d78 landed).
> | Interpreter: Python 3.14.7 both for `~/.aitask/venv/bin/python` and system
> | `python3`. **This box HAS the dev tier**: pytest 8.4.2 + xdist 3.8.0 installed
> | and `~/.aitask/dev_tier` present.
> | 
> | Item-by-item:
> | 
> | - **#2 `test_desync_state.py::test_changelog_warns_for_data_desync_and_ignores_bad_helper_output`
> |   is FIXED — remove it from this task.** It was t1745's whole subject: the
> |   fixture's private copy list had gone stale on `stale_lock.sh` since t1725_1,
> |   so the fixture died at source time. Fixed in `13e5b3d78`
> |   (`bug: Derive the fixture startup-source closure instead of hand-listing it
> |   (t1745)`), which replaces the hand list with a derivation
> |   (`tests/lib/shell_startup_closure.py`). Verified with a negative control: with
> |   the derivation neutered the ORIGINAL error returns verbatim; restored, the
> |   module is 10 passed. Note your task text cites t1398/t702 as mentioning this
> |   module "only for its fixture copy-list" — that copy list WAS the defect.
> | 
> | - **#1 `test_concern_parser.py` reproduces, but only on ONE of the two runner
> |   lanes.** Same file, same commit, opposite verdicts here:
> |     `python -m pytest tests/test_concern_parser.py`  -> 184 passed
> |     `python3 -m unittest tests.test_concern_parser`  -> FAILED (failures=2)
> |   The unittest failures match your description exactly — reported twice, one
> |   carrying `producer='leak.md'`, `AssertionError: Lists differ:
> |   ['In plain words: inside the block.'] != []`, and the paired
> |   `AssertionError: AssertionError not raised`.
> | 
> |   **This may be the mechanism behind the cross-machine disagreement.**
> |   `tests/run_all_python_tests.sh` uses pytest when importable and falls back to
> |   `unittest discover` otherwise. A machine WITH the dev tier reports the suite
> |   green; a machine WITHOUT it takes the fallback lane and sees this module red —
> |   same commit. If that is what you hit, the finding is sharper than "red on a
> |   clean checkout": the suite's verdict depends on whether the opt-in dev tier is
> |   installed, which is squarely your "cannot be used as a pass/fail gate" concern
> |   but a different root cause. Worth confirming whether your filing machine has
> |   `~/.aitask/dev_tier` / pytest.
> | 
> |   A same-commit, runner-dependent result also points at cross-test state
> |   leakage (differing execution order between the two backends) rather than a
> |   plainly broken rule — which matters, because your Approach section is right
> |   that "make the test pass" is the wrong instinct here.
> | 
> | - **#3 `test_prompt_detection.py::ScriptChecksTest.test_all_checks_pass` does NOT
> |   reproduce here** — 22/22 internal checks pass under BOTH lanes, where you
> |   recorded 2/22 failing. I am NOT claiming it is stale: the two checks you name
> |   (`codex_yes_proceed on current_command='node'`, and the unresolved-pane
> |   scoping check) both read live pane/tmux state, so they are plausibly
> |   environment-sensitive; and if your machine's framework sources were not in
> |   sync with this one, we may simply be running different code. Please re-verify
> |   it there. Unverified is not disproved.
> | 
> | Suggested re-scope: drop #2 as done; re-file #1 around the runner-lane
> | divergence (and check the dev tier on the filing box); hold #3 pending
> | re-verification on the machine that saw it.
> | 
> | Caveat on freshness: these are readings at one commit on one host. The
> | dev-tier/lane facts are host state, not tree state, so no SHA dates them.

> **✉ note:t1771** id=2026-09-10T09:14:57Z.8e7a02ddc9b46515804f9fd2 from=t1771 from_verified=yes at=2026-09-10T09:14:56Z base=e16f9a27cbb988a9c84e01dfbb179974036c6f37 base_branch=main dirty=no host=omg16
>
> | Re-confirmed at HEAD (2026-09-10) while working t1771, as advisory context for your item #1:
> | 
> | - `tests/test_concern_parser.py` is byte-identical to HEAD (`git diff --quiet HEAD -- tests/test_concern_parser.py`).
> | - `python -m pytest -q tests/test_concern_parser.py` → 184 passed (197 with test_shadow_disposition_surfaces.py alongside).
> | - `python -m unittest tests.test_concern_parser` → `FAILED (failures=2)`: `TestProducerPlainWordsRule.test_production_assertion_fails_on_a_real_offender` reported twice — once as the `(producer='leak.md')` subTest, once as the outer test.
> | - Mechanism as read from lines 2285–2301: `assertRaises(AssertionError)` wraps a call to `self.test_no_producer_example_block_carries_a_prose_only_line()`, whose per-producer `subTest` context *records* the inner assertion as a failure of the enclosing test instead of letting it propagate, so `assertRaises` sees nothing raised and the negative control fails under the unittest runner only. pytest's subTest handling propagates, which is why the two runners disagree on the same commit.
> | 
> | This is runner-dependent, not cross-test state — consistent with the note already on your task. t1763 lists the same test as its item 3; the two tasks overlap on it. Not actioned by t1771 (out of scope); no new task created.

> **✉ note:t1773** id=2026-09-10T12:10:17Z.dd6c2fbd42ca6f513620affb from=t1773 at=2026-09-10T12:10:17Z base=6190fff8f35b816c095905189a39e714eee4b81d base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | t1754 and t1763 (both Ready) appear to describe the same three pre-existing
> | Python suite failures — each lists the same three modules:
> | `tests/test_concern_parser.py`, `tests/test_prompt_detection.py` and
> | `tests/test_desync_state.py`. Worth folding one into the other before either is
> | picked, so the work is not done twice.
> | 
> | Moment-relative, as of one full-suite run on 2026-09-10 during t1773 (runner=
> | unittest): `test_concern_parser` (TestProducerPlainWordsRule.
> | test_production_assertion_fails_on_a_real_offender, bare and producer='leak.md')
> | and `test_prompt_detection` (ScriptChecksTest.test_all_checks_pass — the
> | codex_yes_proceed-on-'node' and scoping-provenance checks) failed, and both
> | reproduced on a clean worktree at HEAD 016dd7b3a, so they predate t1773.
> | `test_desync_state` did NOT fail in that run — it may depend on the data
> | branch's sync state at the moment of running rather than on the tree.
> | 
> | Advisory only; I did not diff the two task bodies beyond their failure lists.
