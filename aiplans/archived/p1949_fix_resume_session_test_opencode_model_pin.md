---
Task: t1949_fix_resume_session_test_opencode_model_pin.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1949 — Stop pinning the opencode model in test_codeagent_resume_session.sh

## Context

`tests/test_codeagent_resume_session.sh:107,112` pins `opencode/openai_gpt_5_2`.
A registry refresh marked that entry `unavailable` in
`aitasks/metadata/models_opencode.json`, so `lib/agent_string.sh:155` `die`s
(exit 1, "Model 'openai_gpt_5_2' is unavailable…") before
`aitask_codeagent.sh:658` reaches the `RESUME_UNSUPPORTED:opencode` guard
(exit 2). Result: 36/39, the same 3 failures on a clean HEAD. The file asserts
against a registry that drifts with every `ait opencode-models` refresh.

t1871 fixed the identical pattern in `tests/test_codeagent.sh` by deriving the
model from a fixture registry with `codeagent_active_model`
(`tests/lib/codeagent_defaults.sh:147`). Apply the same idiom here.

The launcher also reads `METADATA_DIR` cwd-relatively (`aitasks/metadata`
unless the env var is set — `lib/agent_string.sh:28`), so today the file only
works when run from the repo root. Pointing it at a fixture dir makes the
derivation and the launcher read the very same registry file by construction.

## Changes — `tests/test_codeagent_resume_session.sh` only

1. **Source the helper** after `asserts.sh` (the helper must come after it):
   ```bash
   # shellcheck source=lib/codeagent_defaults.sh
   . "$PROJECT_DIR/tests/lib/codeagent_defaults.sh"
   ```

2. **Hermetic metadata fixture**, right after `CODEAGENT=…`:
   ```bash
   # A hermetic METADATA_DIR (t1949): the launcher reads registries from it, and
   # the opencode case below derives its model from the same file — never a
   # literal pin, which a registry refresh can flip to unavailable (t1871).
   FIXTURE_META="$(mktemp -d)"
   trap 'rm -rf "$FIXTURE_META"' EXIT
   codeagent_fixture_metadata "$FIXTURE_META"
   export METADATA_DIR="$FIXTURE_META"
   ```
   No config source is passed — every call uses an explicit `--agent-string`,
   so no `codeagent_config.json` is needed (and the gitignored
   `codeagent_config.local.json` is never copied). Claude/codex cases read
   byte-identical copies of the live registries, so their expectations are
   unchanged.

3. **Derive the opencode model** in the "opencode is refused with exit 2"
   block, replacing both `opencode/openai_gpt_5_2` literals:
   ```bash
   # Derived, not pinned (t1949): `|| true` keeps an empty result a recorded
   # FAIL below instead of an abort under `set -e`.
   opencode_active="$(codeagent_active_model "$FIXTURE_META/models_opencode.json" || true)"
   assert_exit_zero "fixture opencode registry has an active model" test -n "$opencode_active"

   run_ca --agent-string "opencode/$opencode_active" --resume-session x1 --dry-run invoke raw
   ...
   run_ca --agent-string "opencode/$opencode_active" --dry-run invoke raw
   ```
   An unavailable model still fails loudly: the exit-2 assertion would then see
   die's 1. The "exit 2 NOT die's 1" assertion is preserved verbatim.

4. **Header comment**: add one line to the "opencode REFUSES" bullet noting the
   model is derived from the fixture registry (not pinned) and why.

## Verification

- `bash tests/test_codeagent_resume_session.sh` → 40/40 (39 + the new
  non-empty assertion), exit 0.
- Run from another cwd (`cd /tmp && bash …/tests/test_codeagent_resume_session.sh`)
  → still passes (fixture removes the cwd dependency).
- Negative control: temporarily run with a fixture whose opencode registry has
  every entry `unavailable` (e.g. a scratch copy of the test with a `jq`
  rewrite of `$FIXTURE_META/models_opencode.json`) → the non-empty assertion
  and the opencode asserts FAIL, file exits 1. Run from the scratchpad only; no
  tracked file edited for the control.
- `shellcheck tests/test_codeagent_resume_session.sh`.

## Step 9

Current-branch mode (profile `fast`): no merge; archive via
`./.aitask-scripts/aitask_archive.sh 1949`, then `./ait git push`.

## Risk

### Code-health risk: low
- None identified. One test file; reuses the existing shared helpers
  (`codeagent_fixture_metadata`, `codeagent_active_model`) exactly as
  `tests/test_codeagent.sh` does.

### Goal-achievement risk: low
- None identified. The failure is reproduced, the root cause (unavailable pinned
  model checked before the resume guard) is confirmed in the source, and the
  derived model is selected by the same `status != "unavailable"` filter the
  launcher applies.

## Final Implementation Notes
- **Actual work done:** As planned, in `tests/test_codeagent_resume_session.sh` only: sourced `tests/lib/codeagent_defaults.sh`, built a hermetic `METADATA_DIR` with `codeagent_fixture_metadata` (removed by an EXIT trap), and replaced both `opencode/openai_gpt_5_2` pins with `opencode/$opencode_active`, which comes from `codeagent_active_model` over the fixture's `models_opencode.json`. Added a non-empty assertion on the derived model and a header note.
- **Deviations from plan:** None.
- **Issues encountered:** None. Verification: 40/40, exit 0, from the repo root and from `/tmp`. Negative control (a scratchpad copy that marks every fixture opencode entry `unavailable`): 4 FAIL (the non-empty check plus the 3 opencode asserts), exit 1. `shellcheck` shows only info-level notices (SC1091/SC2016), which already appear on the file's existing lines.
- **Key decisions:** The whole file now reads the fixture copy, not only the opencode block. That way the launcher and the derivation read the same registry file, and the file no longer depends on the cwd (before this, it only worked when run from the repo root). The claudecode/codex cases still pin `opus5` / `gpt5_4`. Their exact-argv assertions need the matching cli_id, and both entries are currently active, so they were left alone.
- **Upstream defects identified:** None
