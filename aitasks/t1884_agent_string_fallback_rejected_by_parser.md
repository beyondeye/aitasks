---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent, models, task_workflow]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
created_at: 2026-09-25 12:33
updated_at: 2026-09-25 12:47
---

## Origin

Spawned from thinking_app t479 (recover_from_corrupt_preferences_datastore_crash_loop) during
its Step 8b review, 2026-09-25. The defect is in this framework; thinking_app consumes it as a
downstream copy.

## Upstream defect

- `.aitask-scripts/aitask_resolve_detected_agent.sh:76,97` — `AGENT_STRING_FALLBACK:${agent}/${cli_id}`
  emits the raw CLI model id (e.g. `claudecode/claude-opus-5-5[1m]`), but
  `.aitask-scripts/lib/agent_string.sh:50` `parse_agent_string()` only accepts
  `^([a-z]+)/([a-z0-9_]+)$`. A raw cli_id always contains `-` (and the 1M variant `[1m]`), so
  **every** fallback string is rejected: `ait codeagent coauthor` dies with
  "Invalid agent string format", and the Step 8 code commit loses its code-agent
  `Co-Authored-By` trailer (the Code-Agent Commit Attribution Procedure skips it on resolver
  failure). `aitask_usage_update.sh:82` / `aitask_verified_update.sh:87` carry their own
  format checks and likely reject the same strings — check them too.
- `aitasks/metadata/models_claudecode.json` (and `seed/`) registers `claude-opus-5-5` but not
  the 1M-context variant `claude-opus-5-5[1m]`, which is the id a session reports after
  `/model` → "Opus 5.5 (1M context)" — so that session always takes the fallback path.

## Diagnostic context

Reproduced in this repo at HEAD (2026-09-25):

```
$ ./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id 'claude-opus-5-5[1m]'
AGENT_STRING_FALLBACK:claudecode/claude-opus-5-5[1m]
$ ./ait codeagent coauthor "claudecode/claude-opus-5-5[1m]"   # (observed in thinking_app)
Error: Invalid agent string format: 'claudecode/claude-opus-5-5[1m]'. Expected: <agent>/<model> (e.g., claudecode/opus4_6)
```

`implemented_with` was recorded with the fallback string (Agent Attribution writes it
verbatim), so the same value poisons every later consumer of that field.

## Suggested fix

Make the two sides agree: either normalise the fallback to the parser's grammar (e.g. map
`claude-opus-5-5[1m]` → `opus5_5_1m` the same way registered entries are named) or widen
`parse_agent_string` to accept a documented fallback form; add the `claude-opus-5-5[1m]` model
entry (models + seed); add a test that every `AGENT_STRING_FALLBACK` output round-trips
through `parse_agent_string`.

## Confirmed consumers (2026-09-25)

Observed in the same thinking_app session after this task was filed: all three consumers reject
the fallback string, not only `ait codeagent coauthor`.

- `aitask_usage_update.sh --agent-string "claudecode/claude-opus-5-5[1m]"` → "Invalid agent
  string format … Expected <agent>/<model>." (rc=1)
- `aitask_verified_update.sh --agent-string …` → same error (rc=1)
- `aitask_verified_update.sh --agent claudecode --cli-id 'claude-opus-5-5[1m]'` → same error
  (rc=1): the self-detection form resolves to the same fallback and hits the same check.

Net effect for an unregistered model: the run's usage count and the user's 5/5 satisfaction score
were both lost, and the code commit had no code-agent trailer.
