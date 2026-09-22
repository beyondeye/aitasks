---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [tests, codeagent]
gates: [risk_evaluated]
anchor: 1307
followup_kind: risk_mitigation
created_at: 2026-07-29 21:37
updated_at: 2026-08-13 23:06
boardidx: 98304
---

## Origin

Risk-mitigation ("after") follow-up for t1318, created at Step 8d after
implementation landed.

## Risk addressed

*Code-health risk (medium) — derived assertions drifting into vacuity:*

> Replacing a failing literal assertion with a derived one can **weaken the
> test into vacuity** — the derived expectation and the resolver read the same
> config, so a broken resolver could still satisfy it.

t1318 solved this for three specific test files. Nothing yet stops the next
default-sensitive test from being written with a pinned literal (which rots) or
with a naive derived assertion (which goes vacuous).

## Goal

Record the pattern t1318 established in `aidocs/framework/testing_conventions.md`
so future default-sensitive tests are promotion-proof *by construction*.

Document, with the concrete rationale:

1. **Derive, don't pin.** Read the expected value from the config the code under
   test actually reads (`aitasks/metadata/codeagent_config.json` live,
   `seed/codeagent_config.json` for fixture envs — they diverge). Helpers already
   exist in `tests/lib/codeagent_defaults.sh`.
2. **Inject a sentinel to prove the derivation is not vacuous.** Asserting the
   real fallback constant is worthless when it happens to equal the configured
   value (in t1318 both were `claudecode/opus5`, so a refreshed literal would
   have passed whether or not the config was ever read). Override
   `DEFAULT_AGENT_STRING` with a registered-but-different sentinel and assert the
   config value AND not-the-sentinel.
3. **Keep the fallback path as a permanent test case**, not a manual ritual: a
   config-less fixture that must return the sentinel is what proves the injection
   seam is live.
4. **Build fixtures hermetically.** Never resolve against live metadata when a
   gitignored per-developer override (`codeagent_config.local.json`) outranks the
   project config — that makes assertions machine-dependent.
5. **Assert exact extracted fields, not substrings.** `assert_contains
   "KEY:$expected"` degrades into the always-true `"KEY:"` when `$expected` is
   empty, and lets a prefix (`opus5`) match a longer name (`opus5_1m`). Anchoring
   with a trailing newline does NOT fix it: the assert helpers use `grep -F`,
   which reads an embedded newline as a second, empty pattern matching every
   line, making `assert_not_contains` unpassable. Use
   `codeagent_resolve_field` + `assert_eq`.

Cross-reference the note added to `aidocs/framework/model_reference_locations.md`
§7 by t1318, so the promotion checklist and the testing conventions point at each
other.

## Verification

- The new section exists in `aidocs/framework/testing_conventions.md` and names
  `tests/lib/codeagent_defaults.sh` as the shared helper home.
- `aidocs/framework/model_reference_locations.md` §7 and the new section
  cross-reference each other (bidirectional doc link).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1865** id=2026-09-22T21:29:59Z.715c5f2fc6778c31809c8681 from=t1865 from_verified=yes at=2026-09-22T21:29:59Z base=915cb836c4d8e2a054838bd5c312563c62a5fe27 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1865 (promoted `claudecode/opus5_5` to the operational
> | default), which applied the t1318 idiom you are documenting to a fourth file.
> | 
> | **A fourth adopter, with the seam you name already in place.**
> | `tests/test_codeagent.sh` was the file that actually went red on this promotion
> | (its fixture installs `seed/codeagent_config.json` as the project config, so its
> | five literal assertions broke). It is now converted: derives `pick` via
> | `codeagent_config_default` from the seed config, injects a sentinel
> | `DEFAULT_AGENT_STRING` from `codeagent_sentinel_excluding`, and asserts with
> | `assert_eq` + `codeagent_resolve_field` rather than `assert_contains_ci`. It also
> | adopted `codeagent_fixture_metadata` in its `setup_test_env` — that helper
> | copies exactly the file set the suite used to copy by hand, and brings the
> | `AIT_CODEAGENT_FIXTURE_OMIT_OPS` seam, so the file now carries a one-command
> | negative control recorded in its header.
> | 
> | **A refinement your current Goal section does not cover, and probably should.**
> | Your point 2 (inject a sentinel) closes vacuity against *the resolver*. It does
> | not close vacuity against *the registry*. When a task both writes a registry
> | entry and tests resolution against it, a derived expectation agrees with a
> | typo'd `cli_id` by construction — both sides read the same file, so
> | `aitask_add_model.sh add-json` accepting a bad `--cli-id` (its `validate_cli_id`
> | only checks non-empty) would flow through the resolver into the expectation and
> | pass. The split t1865 used:
> | 
> | - the **test** derives, so it cannot rot on the next promotion;
> | - the **exact literal** (`claude-opus-5-5`) is pinned once, in a one-time
> |   promotion readback script that is not part of the suite.
> | 
> | Worth stating explicitly, because the obvious "strengthen the test by pinning
> | the ID there" instinct reintroduces exactly what t1318 removed.
> | 
> | **A second, related rule from the same work.** The readback originally used a
> | per-line `|| echo "FAIL …"`. `echo` exits 0, so the block printed FAIL and still
> | returned success — a verification that cannot fail. Any derived/negative-control
> | guidance you write is worth pairing with "the check's exit status must be the
> | gate, and the check must be observed failing before a pass is believed".
> | 
> | **Hedge:** describes t1865's tree as of commit 915cb836c on main; the helper
> | names and the `AIT_CODEAGENT_FIXTURE_OMIT_OPS` seam are pre-existing in
> | `tests/lib/codeagent_defaults.sh` and not introduced by t1865.
