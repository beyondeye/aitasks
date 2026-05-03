---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing]
created_at: 2026-04-28 15:54
updated_at: 2026-04-28 15:54
boardidx: 80
---

## Origin

Spawned from t681 during Step 8b review.

## Upstream defect

- `aitask_resolve_detected_agent.sh:25-29` — `AITASK_AGENT_STRING` env-var fast-path silently overrides explicit `--cli-id` / `--agent` arguments. Likely intentional as a session-level cache, but it produces surprising behavior when callers pass an explicit cli-id and expect deterministic resolution. Worth a separate task to either (a) gate the fast-path on the absence of explicit `--cli-id` / `--agent-string`, or (b) document the override precedence in the script header so future test authors know to clear the env var.

## Diagnostic context

t681 task description originally framed the failure of `tests/test_verified_update_flags.sh` as a "hardcoded model string" issue. Reproducing on Linux showed the test passed; the failure only manifested when `AITASK_AGENT_STRING` was exported by a wrapping Claude Code session (which mirrors how the macOS t658 audit run hit it):

```
$ AITASK_AGENT_STRING=claudecode/opus4_7_1m bash .aitask-scripts/aitask_verified_update.sh \
    --agent claudecode --cli-id claude-opus-4-6 --skill test_414_flags --score 5 --silent
UPDATED:claudecode/opus4_7_1m:test_414_flags:100
```

The resolver's fast-path at `aitask_resolve_detected_agent.sh:25-29`:

```bash
if [[ -n "${AITASK_AGENT_STRING:-}" ]]; then
    echo "AGENT_STRING:${AITASK_AGENT_STRING}"
    exit 0
fi
```

returns the env value before the script reaches argument parsing, so the explicit `--cli-id` flag is silently ignored. t681 fixed the symptom in the test (`unset AITASK_AGENT_STRING`) — the fix here is whether the resolver should change behavior or grow a documented precedence.

## Suggested fix

Two options to consider:

1. **Behavioral change (preferred):** Move the env-var fast-path *after* argument parsing so explicit `--cli-id` / `--agent-string` always win. The env var still acts as a default when no explicit args are passed (preserves existing wrapper-injection behavior).
2. **Documentation only:** Add a comment block at the top of `aitask_resolve_detected_agent.sh` documenting that `AITASK_AGENT_STRING` overrides explicit args, and add the same warning to `aitask_verified_update.sh`'s `--cli-id` flag help. Future test authors then know to `unset` it.

Option 1 makes the contract less surprising and avoids future test breakages of the same shape. Verify no callers rely on the env var winning over explicit args (audit `grep -rn "AITASK_AGENT_STRING" .aitask-scripts/ tests/`).

## Verification

After the fix:
- `AITASK_AGENT_STRING=claudecode/opus4_7_1m bash .aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id claude-opus-4-6` should print `AGENT_STRING:claudecode/opus4_6` (option 1) or be documented to print `AGENT_STRING:claudecode/opus4_7_1m` (option 2).
- `bash tests/test_verified_update_flags.sh` continues to pass with or without the env var set (already true after t681's `unset`, but the resolver-level fix would make t681's `unset` redundant).
