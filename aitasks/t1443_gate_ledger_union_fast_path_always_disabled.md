---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [gates]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-06 10:50
updated_at: 2026-08-06 10:50
---

## Problem

`aitask_merge._union_gate_runs` (`.aitask-scripts/board/aitask_merge.py:314-350`)
is the fast path that unions two sides' `## Gate Runs` sections during a
task-data merge instead of raising a conflict. It returns `None` (falling back
to human conflict resolution) for **essentially every gated task**, because both
of its guards reject ledger shapes the framework itself produces.

Verified empirically by calling `_union_gate_runs(body, body)` with the SAME
body on both sides — the trivially-mergeable, zero-divergence case, which should
always take the fast path. Both shapes returned `None`:

**Guard 1 rejects the orchestrator's own run-id format** (line 335). The regex is
anchored:

```python
_ISO_RUN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")   # line 269
```

but `gate_orchestrator._run_machine_gate` (line 348) generates
`f"{gl.iso_now()}-{gate}-a{attempt}"` — e.g.
`2026-08-06T07:13:06Z-build_verified-a1`. That never matches, so any task whose
machine gates were run by the orchestrator fails guard 1 outright.

**Guard 2b collides on the running/closer pair** (lines 343-350). For run ids
that DO pass guard 1, it rejects when one `(name, run, attempt)` key maps to more
than one distinct block text. But a `running` block and the terminal block that
closes it share all three keys **by design** — the orchestrator passes the same
`run` and `attempt` to both (`gate_orchestrator.py:350` and `:358`), and the
procedure-gate skill echoes both back
(`.claude/skills/aitask-gate-docs-updated/SKILL.md:123-125`). Their texts
obviously differ (different icon and status). So the pair is read as an
"append-only contract violation" when it is the documented ledger shape.

## Impact

Correctness is not affected — returning `None` is fail-safe (it defers to human
conflict resolution). The cost is that the optimization never fires, so
concurrent gate-ledger writes surface as merge conflicts the framework was built
to resolve automatically.

## Relationship to t1262

Pre-existing; neither caused nor fixed by t1262. t1262 changed
`begin-procedure`'s run ids from a bare ISO stamp to the orchestrator's
`<iso>-<gate>-a<N>` shape, which moves procedure gates from failing guard 2b to
failing guard 1 — the outcome (`None`) is unchanged in both directions, so this
is not a regression, but it does mean guard 1 is now the single dominant cause.

## Fix direction

1. Guard 1: match the run-id grammar the framework actually emits — an ISO-8601-Z
   stamp with an optional `-<gate>-a<N>` suffix — rather than a bare stamp.
   Sorting only needs the leading timestamp to be valid and comparable.
2. Guard 2b: the identity key must distinguish a `running` block from its
   terminal closer. Include `status` in the key, or exclude non-terminal
   (`running`/`pending`) blocks from the ambiguity check, so the check catches
   genuine append-only violations instead of the normal lifecycle.

## Verification

- `_union_gate_runs(body, body)` must take the fast path (return a merged
  section, not `None`) for a ledger containing (a) orchestrator-shaped run ids
  and (b) a `running` block plus its terminal closer sharing `(name, run,
  attempt)`.
- A genuine ambiguity — two different texts for one `(name, run, attempt,
  status)` — must still return `None`.
- Confirm the ordering remains total and side-order-independent with the
  suffixed run ids (`_attempt_int` and the sort key at lines 354-362).
