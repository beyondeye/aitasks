---
Task: t703_fix_aitask_agent_string_env_var_overrides_explicit_cli_id.md
Worktree: (none — working on current branch per 'fast' profile)
Branch: main
Base branch: main
---

# Plan: Stop `AITASK_AGENT_STRING` from overriding explicit `--cli-id`/`--agent`

## Context

`aitask_resolve_detected_agent.sh` has an env-var fast-path **before** argument
parsing: if `AITASK_AGENT_STRING` is set it echoes that value and exits,
silently ignoring any explicit `--agent`/`--cli-id` passed by the caller. When a
wrapping Claude Code session exports `AITASK_AGENT_STRING` (done by
`aitask_codeagent.sh:517` before `exec`-ing the agent), every downstream resolver
call that passes an explicit cli-id gets the session's cached value instead —
non-deterministic, surprising resolution. This seeded the t681
`test_verified_update_flags.sh` failure (fixed there by `unset`-ing the env var).

Reproduced (current, buggy):
```
$ AITASK_AGENT_STRING=claudecode/opus4_7_1m bash .aitask-scripts/aitask_resolve_detected_agent.sh \
    --agent claudecode --cli-id claude-opus-4-6
AGENT_STRING:claudecode/opus4_7_1m      # WRONG — explicit cli-id ignored
```

This task adopts the task's **preferred Option 1 (behavioral change)**: explicit
args always win; the env var is retained only as a *default when no explicit
args are passed*.

## Blast-radius audit (done during planning)

- **Env-var producer:** only `aitask_codeagent.sh:517` sets it, then `exec`s the
  agent CLI. It does not itself call the resolver afterward — unaffected.
- **Skill path:** `model-self-detection.md` Step 1 checks `AITASK_AGENT_STRING`
  **directly** and returns before ever calling the resolver (Step 2 only runs
  when the env var is unset). So wrapper-injection still works via the skill's own
  check — it never depended on the resolver's fast-path. No skill/doc change
  needed.
- **Real resolver callers:** `aitask_verified_update.sh:164` and
  `aitask_usage_update.sh:152` both validate `--agent`/`--cli-id` non-empty and
  always pass both. Under the new contract their explicit cli-id is honored — the
  intended fix.
- **No-arg default:** the resolver is currently called with *no* args only by the
  unit test (`test_resolve_detected_agent.sh:48`). That env-var-as-default
  behavior is preserved.
- **Pure script + test change.** No `.j2`/skill rendering, no goldens. (Verified:
  the only doc references to the resolver describe the `--agent/--cli-id`
  interface, which is unchanged.)

## New contract

The env-var fast-path becomes a **default**, not an **override**:
- Env var used **only when neither** `--agent` **nor** `--cli-id` is provided.
- If either explicit arg is present → normal resolution path; env var ignored.
  (Partial args, e.g. `--agent` without `--cli-id`, fall through to the existing
  "missing required argument" `die` — a usage error, as today for the no-env
  case. Documented as intentional: env var defaults only when *both* are absent.)

## Changes

### 1. `.aitask-scripts/aitask_resolve_detected_agent.sh`

Move the fast-path block (current lines 25–29) to **after** the argument-parsing
`while` loop (after line 49, before the `-z "$agent"`/`-z "$cli_id"` required-arg
checks), and gate it on both args being empty:

```bash
# --- Fast path: env var default (only when no explicit args) ---
# Explicit --agent/--cli-id always win for deterministic resolution; the env var
# acts only as a default when the caller passes neither.
if [[ -z "$agent" && -z "$cli_id" && -n "${AITASK_AGENT_STRING:-}" ]]; then
    echo "AGENT_STRING:${AITASK_AGENT_STRING}"
    exit 0
fi
```

Remove the original pre-parse block. Update the header comment (lines 12 / and
the `Output` block) to state the env var is a default honored only when no
explicit `--agent`/`--cli-id` is passed.

### 2. `tests/test_resolve_detected_agent.sh`

- **Flip the existing "env var overrides args" test (lines 51–53)** to the new
  contract: rename to "explicit args override env var" and expect resolution of
  the explicit cli-id:
  ```bash
  echo "=== Test: explicit args override env var ==="
  result=$(AITASK_AGENT_STRING="custom/model" bash "$RESOLVE_SCRIPT" --agent codex --cli-id gpt-5.4 2>&1)
  assert_eq "explicit --agent/--cli-id beats env var" "AGENT_STRING:codex/gpt5_4" "$result"
  ```
- **Add a regression test** matching the task's exact verification command:
  ```bash
  echo "=== Test: explicit cli-id wins over env var (t703 regression) ==="
  result=$(AITASK_AGENT_STRING="claudecode/opus4_7_1m" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-6 2>&1)
  assert_eq "t703: explicit claude-opus-4-6 resolves despite env var" "AGENT_STRING:claudecode/opus4_6" "$result"
  ```
- The no-arg default test (line 48, `AITASK_AGENT_STRING=... $RESOLVE_SCRIPT` with
  no args → returns env var) stays as-is and still passes — it confirms the
  preserved default behavior.

## Verification

```bash
# 1. Bug is fixed (Option 1 expected output):
AITASK_AGENT_STRING=claudecode/opus4_7_1m bash .aitask-scripts/aitask_resolve_detected_agent.sh \
  --agent claudecode --cli-id claude-opus-4-6
#   → AGENT_STRING:claudecode/opus4_6

# 2. Env var still a default when no explicit args:
AITASK_AGENT_STRING=claudecode/opus4_6 bash .aitask-scripts/aitask_resolve_detected_agent.sh
#   → AGENT_STRING:claudecode/opus4_6

# 3. Full resolver test suite passes:
bash tests/test_resolve_detected_agent.sh

# 4. The flag test that originally surfaced this passes with the env var set
#    (making t681's `unset` redundant):
AITASK_AGENT_STRING=claudecode/opus4_7_1m bash tests/test_verified_update_flags.sh

# 5. Lint:
shellcheck .aitask-scripts/aitask_resolve_detected_agent.sh
```

After implementation, Step 9 handles archival/merge per the task-workflow.

## Risk

### Code-health risk: low
- None identified. The change relocates a 5-line block within one script and
  updates its unit test; blast radius is fully audited (see above) and confined
  to the resolver plus callers that already pass explicit args. No new patterns,
  no abstraction debt.

### Goal-achievement risk: low
- None identified. The fix is exactly the task's preferred Option 1 and matches
  its stated verification output; all callers were audited to confirm none rely
  on the env var winning over explicit args.

## Final Implementation Notes
- **Actual work done:** Implemented Option 1 exactly as planned. In
  `aitask_resolve_detected_agent.sh`, relocated the `AITASK_AGENT_STRING`
  fast-path from before the argument-parsing loop to after it, and gated it on
  `[[ -z "$agent" && -z "$cli_id" && -n "${AITASK_AGENT_STRING:-}" ]]` so the
  env var is honored only when the caller passes neither explicit arg. Updated
  the header comment. In `tests/test_resolve_detected_agent.sh`, flipped the
  former "env var overrides args" case to "explicit args override env var"
  (expects `codex/gpt5_4`) and added a t703 regression test matching the task's
  exact verification command.
- **Deviations from plan:** None.
- **Issues encountered:** None. The working tree contained unrelated concurrent
  changes (brainstorm/*, settings.local.json, website docs); only the two
  task-owned files were staged and committed, leaving the rest untouched.
- **Key decisions:** Gate the env-var default on *both* args being absent (not
  just cli-id). Partial args (e.g. `--agent` without `--cli-id`) fall through to
  the existing "missing required argument" `die` — treated as a usage error,
  consistent with the no-env behavior. The no-arg env-var-as-default path
  (test line 48) is preserved, so the wrapper-injection use case is unaffected
  (and `model-self-detection.md` Step 1 reads the env var directly anyway,
  never depending on the resolver fast-path).
- **Upstream defects identified:** None.
