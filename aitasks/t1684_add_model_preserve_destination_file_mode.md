---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent, claudecode, model_selection]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1680
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-02 11:22
updated_at: 2026-09-02 16:26
---

## Origin

Spawned from t1680 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_add_model.sh:145-146` — `cmd_add_json` `mv`s a `mktemp`
  (mode `0600`) file over both registries, narrowing their permissions. Git does
  not track read bits, so the change is invisible in any diff or `git status`.
  `seed/models_claudecode.json` has been `0600` since the t966 `fable5`
  registration for exactly this reason. The helper should preserve the
  destination's pre-existing mode (or `chmod` to the umask default) after the
  `mv`. The same tempfile-`mv` pattern appears in `cmd_promote_config` and
  `cmd_promote_default_agent_string`; `seed/codeagent_config.json` is likewise
  `0600`.

## Diagnostic context

From t1680's plan (`aiplans/archived/p1680_*.md`), Final Implementation Notes:

t1680 registered `claudecode/fable5_1` in both registry copies. Its plan carried
an inline post-phase mitigation `restore_and_assert_file_modes` precisely because
`aitask_add_model.sh` was expected to narrow modes via its tempfile `mv`. The
mitigation snapshotted `stat -c '%a %n'` for both files before the first write and
restored each file's own recorded pre-change mode after the last write, asserting
the result with `diff`.

Observed during that run: after the writes, both files read `644` — the drift ran
the *opposite* way from the prediction, because a later `jq > tmp && mv` step
created its temp at the umask default and **widened** `seed/models_claudecode.json`
from `600` to `644`. Restoring against the recorded per-file baseline handled both
directions correctly (`MODES_RESTORED_OK`; metadata `644`, seed `600`). A hardcoded
`chmod 644` would have silently changed the seed copy's mode instead of restoring
it.

The net effect today: every `aitask-add-model` run silently rewrites the mode of
files it touches, in a direction that depends on which code path wrote last, and
nothing in git surfaces it. The current `0600` on `seed/models_claudecode.json` and
`seed/codeagent_config.json` is the accumulated residue.

## Suggested fix

In `aitask_add_model.sh`, capture the destination's mode before the `mv` (or read
the umask) and restore it immediately after, in every subcommand that uses the
tempfile-`mv` pattern. Add a test group to `tests/test_add_model.sh` asserting the
destination mode is unchanged across `add-json`, `promote-config`, and
`promote-default-agent-string` — `tests/test_add_model.sh` Test 4 already asserts
"executable bit preserved on both patched files", so the read-bit assertion is a
natural extension of an existing pattern.

Separately decide whether to normalize the two seed files already left at `0600`
back to `0644` (a one-off repair; git will not record it, so it only affects each
local checkout).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-02T13:26:32Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-02T14:22:16Z status=pass attempt=1 type=human
