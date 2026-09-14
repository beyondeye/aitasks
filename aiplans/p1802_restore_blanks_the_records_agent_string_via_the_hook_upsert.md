---
Task: t1802_restore_blanks_the_records_agent_string_via_the_hook_upsert.md
Base branch: main
Output branch: main
---

# t1802 — Restore blanks the record's agent_string via the hook upsert

## Context

After one successful freeze + restore, a record launched through the wrapper
(`agent_string: claudecode/opus5`) comes back with `agent_string` and
`agent_kind` EMPTY (observed live in t1801). Mechanism, verified against the
tree:

- `lib/agent_restore.py::build_resume_argv` / `build_repick_argv` resolve the
  agent command with `resolve_dry_run_command` (`lib/agent_launch_utils.py:234`),
  i.e. `aitask_codeagent.sh ... --dry-run invoke ...`. `cmd_invoke` returns at
  the dry-run branch (`aitask_codeagent.sh:636-641`) BEFORE
  `export AITASK_AGENT_STRING` (`:646`), so the respawned bare `claude …` has no
  `AITASK_AGENT_STRING` — on resume AND on re-pick.
- The coordinator hands the replacement only the four `AITASK_RESTORE_*`
  variables (`agent_restore.py:185-191`).
- The hook upserts `--agent-string "${AITASK_AGENT_STRING:-}"` = `""`
  (`aitask_session_hook.sh:138`), and `_apply_upsert_fields`
  (`lib/agent_sessions.py:729-731`) overwrites on any non-None value, so `""`
  clobbers the string and `agent_kind_of("")` re-derives `agent_kind` as `""`.

Consequence: a SECOND restore resumes with the project's default agent
(`claude --resume <codex-sid>` for a codex agent — wrong binary); `--repick`
loses the agent the same way; monitor/minimonitor/frozenagent show a blank kind.

**A second caller sends the same blank.** The freeze engine's fallback upsert
(`lib/agent_freeze.py:267-276`, `_resolve_record` path 2) passes
`"--agent-string", ""`. It runs when a pane's `@aitask_record` stamp is missing
or dangling, and `upsert` can still SELECT an existing record by pane identity
(`agent_sessions.py:817-819`), so it clobbers exactly the same way. The only
other `--agent-string` writers are the hook and this fallback — nothing in the
tree clears the field on purpose.

## Approach — two layers, one per defect site

The task lists three options. This plan takes **option 2 (root cause)** plus
**option 3 (defensive chokepoint)**, because either alone leaves a known hole:
option 2 alone leaves the freeze-engine fallback clobbering; option 3 alone
keeps the record right but leaves the restored agent's environment differing
from a wrapper launch (no `AITASK_AGENT_STRING` for its own
`model-self-detection.md` step 1 / `implemented_with`). Option 1 (respawn
through the wrapper for real) is rejected: it changes the respawned process
tree for every restore and re-opens the `#{pane_pid}` invariant (t1465) for no
gain over delivering one variable.

**Consequence for testing (drives §3):** layer 2 alone makes every
*record-level* assertion pass, so a record check can never prove layer 1. Every
coordinator-driven restore case therefore asserts on the **replacement
process's own environment** as well as on the record.

### 1. Coordinator delivers `AITASK_AGENT_STRING` — `.aitask-scripts/lib/agent_restore.py`

- Add `ENV_AGENT_STRING = "AITASK_AGENT_STRING"` beside the four `ENV_*`
  constants; rewrite the comment block above them (`:123-129`) — it now says
  "four identity variables"; describe the fifth as the one the wrapper would
  have exported on a real launch, consumed by the hook (`--agent-string`) and by
  the restored agent itself.
- `_restore_env(record_id, nonce, mode, expect_session, agent_string="")`: add
  `ENV_AGENT_STRING: agent_string` **only when
  `agent_sessions.agent_kind_of(agent_string)` is non-empty** (reuse the store's
  existing well-formedness check, `_AGENT_STRING_RE` =
  `[a-z]+/[a-z0-9_]+`). Two reasons: an empty record has nothing to deliver
  (and the store guard below makes a blank harmless anyway), and the value is
  spliced UNQUOTED into the `if-shell` branch as `-e NAME=value`
  (`agent_frozen_ops.py:522-523`) — only a regex-clean value may ride there.
  Follow however `agent_restore.py` already imports from the lib dir.
- `restore()` (`:508`): pass `rec.get("agent_string", "")` into `_restore_env`,
  **unconditionally of mode** — no `if mode == "resume"` around it. Both
  branches consume the same `env` dict — `respawn_if_stamped(..., env=env)`
  (-e flags) and `_launch_into_new_window(rec, command, env)` (`env A=… cmd`
  prefix) — so resume AND repick, reused pane AND new window, are all covered
  by this one change; the tests in §3 pin all four combinations so a later
  conditional cannot silently drop one.
- `.aitask-scripts/lib/agent_frozen_ops.py:629-637` (`respawn` docstring):
  "the four `AITASK_RESTORE_*` identity variables" → the restore identity
  variables plus `AITASK_AGENT_STRING`.

### 2. Store: a blank agent string is "not supplied" — `.aitask-scripts/lib/agent_sessions.py`

- `_apply_upsert_fields` (`:729`): `if agent_string is not None:` →
  `if agent_string:`. Update its docstring: for `agent_string`, `""` also means
  "not supplied" — the same rule the hook already applies to a blank session id
  (hook contract 4), and for the same reason: a blank would overwrite a good
  stored value. Creation is unaffected (`_create` defaults the field to `""`).
- Both entry points go through this function — the restore ack
  (`:788-796`) and the selected-record update (`:839-847`) — so one line covers
  the hook's ack, the hook's plain re-fire, and the freeze-engine fallback.
- `aitask_session_hook.sh:138`: one comment line noting a blank
  `AITASK_AGENT_STRING` is a no-op in the store (a hand-launched agent outside
  the wrapper keeps whatever the record already had). No behaviour change there.
- `lib/agent_freeze.py:275`: leave the `--agent-string ""` as is (now a no-op);
  record it in Final Implementation Notes as the second site this fixes.

### 3. Tests

Run every new/changed unit assertion against the UNFIXED code first and watch
it fail (pre-fix control), then apply the fix and watch it pass.

#### 3a. Store — `tests/test_agent_sessions_identity.py`

Reuse `_UpsertTestCase.up` and `RestoreAckTests._restoring` (give `_restoring`
an `agent_string=` kwarg passed to its seeding `up`):
- `RestoreAckTests.test_a_blank_agent_string_on_the_ack_keeps_the_stored_one`
  — seed `claudecode/opus5`, restore-ack with `agent_string=""` → string and
  `agent_kind == "claudecode"` survive. Run it for `mode="resume"` AND
  `mode="repick"` (subTest) — the ack path is shared, but the repick ack is the
  one the task names as losing the agent. (Fails pre-fix.)
- Update-path test (the freeze-engine fallback shape):
  `up(pane="%1", agent_string="claudecode/opus5")` then
  `up(pane="%1", agent_string="")` → kept. (Fails pre-fix.)
- Non-blank still overwrites: second `up(..., agent_string="codex/gpt5")` →
  replaced, `agent_kind == "codex"`. (Passes both sides — proves the guard does
  not freeze the field.)

#### 3b. Coordinator — `tests/test_agent_restore.py`

Every delivery test runs as a **subTest over `repick in (False, True)`**,
patching BOTH `build_resume_argv` and `build_repick_argv` to fixed strings, and
calling `restore("7f3a2c1d", repick=repick)`:
- Reused pane (`-e` path): rename
  `TestRestoreEnvDelivery.test_four_e_flags_are_passed_to_respawn` →
  `test_identity_and_agent_string_e_flags_are_passed_to_respawn`; add
  `("AITASK_AGENT_STRING", "claudecode/opus5")` to its tuple list (`_rec()`
  already carries that string), expect `5` flags, and assert
  `AITASK_RESTORE_MODE` matches the mode. Update the class docstring.
  (Fails pre-fix, both modes.)
- New window (`env` prefix path): model on
  `TestRecordedPaneIsOnlyAHint._run` / `test_a_gone_pane_routes_to_a_new_window`
  (`:575-595`) — gone-pane probe, `_launch_into_new_window` patched — and
  assert `launched.call_args.args[2]["AITASK_AGENT_STRING"] == "claudecode/opus5"`.
  (Fails pre-fix, both modes.)
- `test_a_record_without_an_agent_string_delivers_only_the_four` —
  `_rec(agent_string="", agent_kind="")` → 4 flags, no `AITASK_AGENT_STRING`.
- `test_a_malformed_agent_string_is_never_spliced_into_the_branch` —
  `_rec(agent_string="bad value;x")` → no `AITASK_AGENT_STRING` in the branch.

#### 3c. Live test seam — `tests/lib/fake_agent.sh`

A coordinator-launched replacement cannot be handed `--report-env`: its argv
comes out of the wrapper's `--dry-run`. Add an env knob
`FAKE_AGENT_REPORT_ENV=<file>` as the default for `report_env` (set before the
argv loop, so an explicit `--report-env` still wins). It reaches a coordinator
launch through `agent_env`, because both suites' fake-`claude` shims source
`$AGENT_ENV_FILE` from a path baked into the shim at write time
(`test_frozen_agents_acceptance.sh:173-186`, `test_restore_flows_live.sh:99-111`)
— so it survives Case 6c's server restart too. The report is written BEFORE the
hook runs (`fake_agent.sh:~107-129`), so it exists even if the ack fails. Add
the knob to the header's knob list and note the report already includes
`AITASK_AGENT_STRING` (`:123`).

#### 3d. Live assertions — every coordinator-driven restore gets both kinds

Pattern, per case: `agent_env FAKE_AGENT_REPORT_ENV=<fixture>/envprobe_<case>.txt`
**immediately before** the restore call and `agent_env_clear` right after it
(so the ORIGINAL launch never writes the report), then:
- **env assertion (proves layer 1 — the store guard cannot satisfy it):**
  wait for the report the way restore-flows Case 3 does (`for _ in $(seq 1 60)`
  on `-s`), then assert `AITASK_AGENT_STRING=claudecode/opus5`. A missing report
  is an `assert_record_fail` with a message, never a skip.
- **record assertion (proves the composed outcome):** `agent_string ==
  claudecode/opus5` and `agent_kind == claudecode`.

| suite / case | mode | branch exercised |
|---|---|---|
| `test_frozen_agents_acceptance.sh` Case 5 | resume | reused pane, `-e` |
| `test_frozen_agents_acceptance.sh` Case 6c | resume | new window in the bootstrapped session, `env` prefix |
| `test_restore_flows_live.sh` Case 1 | resume | reused pane, `-e`, real hook |
| `test_restore_flows_live.sh` Case 2 | **repick** | reused pane, `-e`, real hook |

Also update the acceptance header comment (`:29-33`): the restore path now gets
the variable from the coordinator, not from the wrapper's export. Restore-flows
Case 3 (the hand-built respawn) is left alone — it measures tmux's repeated
`-e`, which the coordinator-driven cases above now cover for the fifth flag.

## Verification

1. Pre-fix control: run 3a and 3b on unfixed code → every test marked
   "(Fails pre-fix)" fails, for both modes where subTested.
2. Seam smoke test (no tmux needed), from a scratch dir:
   `FAKE_AGENT_REPORT_ENV=<scratch>/r FAKE_AGENT_NO_HOOK=1 FAKE_AGENT_SLEEP=0 AITASK_AGENT_STRING=claudecode/opus5 bash tests/lib/fake_agent.sh`
   → `<scratch>/r` holds `AITASK_AGENT_STRING=claudecode/opus5`; with an
   explicit `--report-env <scratch>/r2` the report goes to `r2` instead.
3. After the fix:
   - `bash tests/run_all_python_tests.sh --test-dir` scoped to the three touched
     Python test modules, then the whole suite — read only the final
     `PYTHON SUITE:` line; no pipe without `pipefail`.
   - `bash tests/test_session_hook.sh` (hook argv unchanged — must stay green).
   - `shellcheck .aitask-scripts/aitask_session_hook.sh tests/lib/fake_agent.sh`;
     `bash -n` on the two edited live suites.
4. **Not runnable here:** `test_frozen_agents_acceptance.sh` and
   `test_restore_flows_live.sh` refuse to run inside tmux
   (`require_clean_ait_server`), and this session lives on the `ait` server they
   also require stopped. They are run from a plain terminal by the planned
   mitigation below, including a pre-fix run. The composed claim is not
   verified until they pass.

## Step 9 (Post-Implementation)

Current-branch mode: no merge; archive with `aitask_archive.sh 1802` after the
Step 8 review and commit.

## Risk

### Code-health risk: low
- The store's upsert changes meaning for `agent_string=""` (no longer clears the field). Verified that no caller clears it on purpose: the only `""` senders are the hook and the freeze-engine fallback, both accidental. Side effect: a pane re-used by a hand-launched different agent keeps the previous agent string instead of going blank. Today that case already fails, because a blank resumes with the default agent. · severity: low · → mitigation: None needed
- A fifth `-e` flag rides the `if-shell` branch unquoted. Repeated `-e` is measured for four flags (spike Case 3c), and the value is limited to the store's agent-string regex before it is spliced in. · severity: low · → mitigation: None needed (covered by the malformed-value unit test)

### Goal-achievement risk: medium
- Unit tests prove each half separately, for both modes. Only the live suites prove the composed hook → store → coordinator path, and they cannot run inside this tmux session. · severity: medium · → mitigation: run_live_restore_suites_outside_tmux

### Planned mitigations
- timing: after | name: run_live_restore_suites_outside_tmux | type: manual_verification | priority: medium | effort: low | inline_risk: high | added_complexity: low | addresses: goal-achievement — the composed restore path is only provable by the live suites, which refuse to run inside tmux | desc: From a terminal NOT inside tmux with the `-L ait` server stopped, run tests/test_frozen_agents_acceptance.sh and tests/test_restore_flows_live.sh; confirm the t1802 env + record assertions (acceptance Cases 5 and 6c, restore-flows Cases 1 and 2 incl. the repick case) pass, and once with the agent_restore.py change reverted confirm the env assertions FAIL (pre-fix control)
