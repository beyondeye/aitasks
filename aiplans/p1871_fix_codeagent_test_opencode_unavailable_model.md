---
Task: t1871_fix_codeagent_test_opencode_unavailable_model.md
Base branch: main
Output branch: main
---

# t1871 — Stop pinning a literal opencode model in the codeagent dry-run tests

## Context

`tests/test_codeagent.sh` Test 11e's negative control loops over
`opencode/openai_gpt_5_2`. t1867 (commit 2d9db16ab) flipped that entry to
`"status": "unavailable"` in the opencode registry; `lib/agent_string.sh:114`
now dies on it, and because the `output=$(...)` assignment runs under `set -e`,
the whole file aborts at 11e — every later test (11d4, the batch-review gating,
coauthor tests 12–25c, help/list checks) silently goes unrun.

Same drift class as t1318/t1865: a test pinned to a literal registry entry that
a legitimate refresh changes. The fixture copies `aitasks/metadata/models_*.json`
(currently byte-identical to `seed/`), so the fix is to derive an active model
from the fixture's own registry.

### Exposure survey (other literal names)

- **Status-gated paths** (`--dry-run invoke` / `resolve` go through
  `get_cli_model_id`, which refuses `unavailable`):
  - `test_codeagent.sh` Test 11e — `opencode/openai_gpt_5_2` — **broken now**.
  - `test_codeagent_work_report.sh` Test 3 — `opencode/openai_gpt_5_4` —
    active today, same exposure. Its assertions check only the `opencode`
    binary and the verbatim slash-command, never the model → safe to derive.
- **Not status-gated**: `coauthor` (Tests 21–25c incl. the already-unavailable
  `opencode/openai_gpt_5_1_codex` in Test 25) reads only the registry `name` →
  display mapping; attributing past work to a now-unavailable model is valid,
  and those tests assert model-specific display names, so they stay literal.
- `claudecode/*` and `codex/*` registries carry no `status` field and are not
  touched by `ait opencode-models`; the codex literals are also asserted by
  cli-id (`gpt-5.4`). Out of scope.

## Implementation

### 1. Shared helper — `tests/lib/codeagent_defaults.sh`

Add, next to `codeagent_sentinel_excluding`:

```bash
# codeagent_active_model <models_file>
#
# Print the name of the first model in <models_file> that the launcher will
# accept, i.e. whose status is not "unavailable" (absent status = active, the
# same default lib/agent_string.sh applies). Registry refreshes legitimately flip
# entries to unavailable (t1867 did it to openai_gpt_5_2 and turned
# test_codeagent.sh red — t1871), so a dry-run test that needs "some opencode
# model" must derive one rather than pin it. Returns non-zero with nothing on
# stdout when no model qualifies, so callers can fail loudly.
codeagent_active_model() {
    local models_file="$1" name

    [[ -f "$models_file" ]] || return 1
    name="$(jq -r '[.models[] | select((.status // "active") != "unavailable") | .name][0] // empty' \
        "$models_file" 2>/dev/null)" || return 1
    [[ -n "$name" ]] || return 1
    printf '%s\n' "$name"
}
```

(Same predicate as `aitask_codeagent.sh:324` / `agent_string.sh:113-114`.
bash-3.2/BSD safe: jq + POSIX only.)

### 2. `tests/test_codeagent.sh` Test 11e negative control (~line 353)

Replace the literal loop with a derived opencode entry and fail-loud handling:

```bash
opencode_active="$(codeagent_active_model "$TMPDIR_TEST/aitasks/metadata/models_opencode.json" || true)"
assert_exit_zero "fixture opencode registry has an active model" test -n "$opencode_active"
negative_agents=(claudecode/opus5)
[[ -n "$opencode_active" ]] && negative_agents+=("opencode/$opencode_active")
for agent_string in "${negative_agents[@]}"; do
    output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string "$agent_string" --dry-run invoke pick 42 2>&1) || true
    ...existing two asserts unchanged...
done
```

- Missing active model → a recorded FAIL, not a skip, and the file keeps going.
- `|| true` on the capture: a refused model now shows up as the "still
  dry-runs" assertion failing instead of truncating the rest of the file under
  `set -e` — the actual damage mode in this bug.
- Add a one-line comment above pointing at t1871 / the derive rule.

### 3. `tests/test_codeagent_work_report.sh` Test 3 (~line 114)

Derive the same way (`$TMPDIR_TEST/aitasks/metadata/models_opencode.json`),
record a failing assertion if empty, and use `opencode/$opencode_active` in the
dry-run. Keep assertions unchanged; add `|| true` to the capture for the same
reason.

## Verification

- `bash tests/test_codeagent.sh` → runs to its footer, all PASS (previously
  exit 1 at 11e).
- `bash tests/test_codeagent_work_report.sh` → all PASS.
- Negative control (red proof, scratch copy only — never touching the tracked
  registry): run the helper against a temp registry where every entry is
  `unavailable` and confirm it returns non-zero with empty stdout; and against
  one with only `openai_gpt_5_2` unavailable ahead of an active entry and
  confirm it skips it.
- **End-to-end fail-loud check (whole scripts, no usable opencode model).** The
  fixture helpers copy from `$PROJECT_DIR/aitasks/metadata`, and `PROJECT_DIR`
  comes from the script's own location. So build a scratch mirror under the
  session scratchpad (`cp -a` of `tests/`, `.aitask-scripts/`, `seed/`,
  `aitasks/metadata/` into `$SCRATCH/proj`). The tracked registry is never
  touched.
  1. **Positive control.** Run the unmutated mirror's
     `tests/test_codeagent.sh` and `tests/test_codeagent_work_report.sh`. Both
     must exit 0, which proves the mirror is complete enough to be a valid
     harness.
  2. **Mutant.** Use `jq '.models[].status = "unavailable"'` on
     `$SCRATCH/proj/aitasks/metadata/models_opencode.json`, then re-run both
     mirror scripts, capturing rc with `PIPESTATUS`/no pipe. Each must:
     - exit **non-zero**;
     - print the `FAIL: fixture opencode registry has an active model` line,
       or the work-report equivalent;
     - **reach its results footer** (`PASS: N / M` plus `FAIL: K`). The footer
       shows it ran to the end instead of aborting under `set -e`. For
       test_codeagent.sh, also confirm that a late marker (`--- Test 25c`)
       appears in the output.
  The helpers in `tests/lib/asserts.sh` record the failure and return 0
  (`assert_eq` / `assert_exit_zero` end on `echo`), so a recorded FAIL does not
  itself trip `set -e`. The `|| true` on the dry-run capture covers the
  launcher refusal.
- `shellcheck tests/lib/codeagent_defaults.sh tests/test_codeagent.sh tests/test_codeagent_work_report.sh`
  (no new warnings).

## Step 9

Post-implementation: commit code (`bug: ... (t1871)`), then archive via Step 9.

## Risk

### Code-health risk: low
- None identified. (The shared-lib helper is purely additive; the `|| true`
  captures cannot mask a refusal because the next assertion requires
  `DRY_RUN:` in the output.)

### Goal-achievement risk: low
- None identified. The derive predicate is identical to the launcher's, so a derived model is by construction one the launcher accepts.

## Final Implementation Notes
- **Actual work done:** Added `codeagent_active_model <models_file>` to
  `tests/lib/codeagent_defaults.sh` (first model whose `status // "active"` is
  not `unavailable` — the launcher's own predicate; non-zero + empty stdout when
  none). Test 11e in `tests/test_codeagent.sh` and Test 3 in
  `tests/test_codeagent_work_report.sh` now derive their opencode model from the
  fixture registry, record a FAIL when none is usable, and capture the dry-run
  with `|| true` so a launcher refusal is a recorded FAIL, not a `set -e` abort.
- **Deviations from plan:** None.
- **Issues encountered:** None. Verified: both files green (199/199, 29/29);
  helper probed against all-unavailable / skip-first / no-status / missing
  registries; scratch-mirror positive control green, and the all-unavailable
  mutant makes both scripts exit 1 with the "active model" FAIL while still
  reaching the results footer (test_codeagent.sh reaches Test 25c).
- **Key decisions:** Coauthor tests (incl. the already-unavailable
  `opencode/openai_gpt_5_1_codex` in Test 25) stay literal — `coauthor` never
  consults status and asserts model-specific display names. claudecode/codex
  literals left alone: those registries carry no `status` field.
- **Upstream defects identified:** None
