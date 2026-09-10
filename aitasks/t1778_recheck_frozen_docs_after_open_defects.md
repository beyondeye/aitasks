---
priority: medium
effort: low
depends: [1773, 1766]
issue_type: documentation
status: Ready
labels: [documentation, website, frozen, tui]
gates: [risk_evaluated]
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-10 12:10
updated_at: 2026-09-10 12:10
---

## Origin

Risk-mitigation ("after") follow-up for t1705_9, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — pages describing two open defects' current behaviour go stale
when those defects land.

From t1705_9's `## Risk`:

> Two behaviours the pages describe belong to open defects — **t1773**
> (restoring a record whose window was closed) and **t1766** (the viewer's
> hardcoded 40 s restore deadline, which the `## Configuration` section states
> as a real viewer-vs-monitor difference). Neither lands before this task, so
> the prose is correct when published and goes stale later · severity: medium
> (residual — corrected after the fact by the spawned follow-up)

## Goal

Once **t1773** and **t1766** have landed, re-check and correct the frozen-agent
documentation that describes their current behaviour.

**t1773 — restoring a record whose window was closed.** Today this does not
work: `_reconcile_frozen` returns `KEEP:<id>|pane_gone` and
`agent_restore._restore` branches on the *recorded* `pane_id` rather than a live
check, so it respawns a dead pane.
`tests/test_frozen_agents_acceptance.sh` case 6b asserts only the fail-safe half
and names t1773; case 6a (a record whose `pane_id` is empty) does restore into a
new window. t1705_9 deliberately documents no recovery route for a closed
window. When t1773 lands, that route becomes real and should be documented —
check `tuis/frozenagent/how-to.md` ("Bring an agent back") and coordinate with
t1705_10, which owns "When something goes wrong" and "records for windows that
no longer exist".

**t1766 — the viewer's restore deadline.** At t1705_9's writing the viewer used
a hardcoded 40 s while the monitors derived theirs from
`frozen.restore_ack_grace`. **Note:** t1766's implementation was already present
as an *uncommitted* change in the working tree when t1705_9 landed, so verify
its actual state first — it may already be done. t1705_9's
`tuis/frozenagent/reference.md` `## Configuration` section was deliberately
written to hold either way (it describes the knob without asserting a
viewer-vs-monitor difference), so if t1766 has landed the section is *not*
wrong — but it can now be sharpened to state that both surfaces derive their
wait from the same grace.

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build
```

Confirm both defect tasks are actually complete before editing — this follow-up
is a no-op while either is still open, and closing it early would leave the
staleness it exists to catch.
