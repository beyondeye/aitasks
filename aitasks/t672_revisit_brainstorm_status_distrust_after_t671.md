---
priority: low
effort: medium
depends: [671]
issue_type: refactor
status: Postponed
labels: [ait_brainstorm, agentcrew]
created_at: 2026-04-27 14:06
updated_at: 2026-04-27 14:06
boardidx: 10
---

Follow-up to t671 (archived as `aiplans/archived/p671_*`).

t671 made `<agent>_status.yaml: status` purely the agent's self-reported
lifecycle: the runner no longer flips Running -> MissedHeartbeat -> Error
on stale heartbeats. With `status` now trustworthy, two long-standing
workarounds in the brainstorm flow can potentially simplify:

## Candidates for simplification

1. **`brainstorm_app.py:_poll_initializer` 30s slow-watcher fallback**
   (`brainstorm_app.py:3520-3534`). The Error/Aborted branch currently
   distrusts `status` and installs a 30 s slow-watcher that keeps trying
   to apply late-arriving output via `_try_apply_initializer_if_needed()`.
   Now that an Error/Aborted status genuinely reflects agent failure,
   evaluate whether the slow-watcher and retry can be dropped (or kept as
   a defensive belt-and-suspenders with the rationale comment updated).

2. **`brainstorm_session.py:n000_needs_apply` four-delimiter gate**
   (`brainstorm_session.py:267-301`). The function gates apply on the
   four output-file delimiters (NODE_YAML_START, NODE_YAML_END,
   PROPOSAL_START, PROPOSAL_END) rather than `status == "Completed"`.
   The archived plan `aiplans/archived/p670_*` rejected the status-based
   gate explicitly because of the heartbeat-stale-flips-Error problem.
   That rejection rationale is gone after t671 — the file-content gate
   could now simplify to a status-based gate, OR stay as-is for
   robustness against agent implementation drift.

## Soak before deciding

This task should be **postponed** until t671 has soaked for at least 1-2
weeks of real brainstorm usage. Picking too early risks: (a) hidden
status-trust bugs that t671 didn't surface, (b) deciding without enough
production data on whether late-arriving output actually happens.

## Suggested approach

When ready:
1. Audit recent brainstorm sessions for any late-output cases that the
   slow-watcher actually rescued. If zero, simplify; if non-zero, keep.
2. For `n000_needs_apply`, decide between status-based + delimiter-based
   simplifications based on how often the bootstrap output appears
   structurally complete vs. status-Completed in real sessions.
3. Update inline comments in both files to drop the t653_1/t670
   distrust framing.

## References

- `aiplans/archived/p671_separate_heartbeat_freshness_from_agent_terminal_status.md`
- `aiplans/archived/p670_n000_needs_apply_premature_true_on_tui_load.md`
- `aiplans/archived/p653/p653_1_brainstorm_tui_self_heal_apply.md`
