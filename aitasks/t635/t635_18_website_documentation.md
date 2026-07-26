---
priority: medium
effort: high
depends: [t635_7, t635_9, t635_10, t635_12, t635_14]
issue_type: documentation
status: Ready
labels: [gates, web_site]
created_at: 2026-06-10 19:03
updated_at: 2026-07-26 00:00
---

## Context

The gates framework is a comprehensive redesign of how aitasks tasks are
worked, and it must be properly documented on the website across ALL
affected surfaces — concepts, workflows, skills, TUIs, commands, and
configuration. This sibling is the comprehensive documentation sweep;
in addition, every t635 child that lands a user-facing surface should
update its own pages incrementally (current-state-only rule:
`aidocs/framework/documentation_conventions.md` — never document
unlanded behavior).

## Initial content map (refine at planning time)

**Concepts** (`website/content/docs/concepts/`):
- New "Gates" concept page: the ideas behind the framework — gate sets
  declared in frontmatter, the append-only Gate Runs ledger, derived
  state (no status duplication), machine vs human gates, the registry
  (`aitasks/metadata/gates.yaml`), retry budgets and the unlock DAG,
  hybrid-by-mode approvals (interactive prompt vs async signal — one gate,
  two signal transports), re-entry semantics, gate-guarded archival and
  dependency unblocking.
- Update the task file format page: `gates:` frontmatter field +
  `## Gate Runs` section + marker block format.

**Workflows** (`website/content/docs/workflows/`):
- New "Working with gates" page: declaring gates, running them, reading
  status, the worked lifecycle example (adapt the framework doc's t42
  example with generic placeholder project names).
- New "Resuming in-flight tasks" page: picking up a task with pending
  gates via aitask-pick, the In-Flight board view, aitask-resume.
- New "Human review sign-off" page: pending-human gates, `ait gate pass`,
  the never-self-signal rule (autonomous agents stop and wait).
- Update existing pages that the gates work touches: crash-recovery.md
  (ledger-driven resume), risk-evaluation.md (gate conversion),
  qa-testing.md / follow-up-tasks.md where checkpoint language changes.
- NOTE: `workflows/_index.md` is a hand-curated grouped list — every new
  page needs a bullet added there (sidebar auto-builds, the index body
  does not).

**Skills** (`website/content/docs/skills/`):
- New page for `aitask-resume`; update aitask-pick page (in-flight
  section, resume routing); gate verifier template page for
  project-specific gates (the ten-minute custom gate story:
  security_scan, license_check, changelog_updated examples).

**TUIs** (`website/content/docs/tuis/`):
- Board page: In-Flight action-grouped view, per-task gate operations.
- Monitor page: gate status column.
- Keep the documented TUI list to: board, monitor, minimonitor,
  codebrowser, settings, brainstorm (diffviewer stays undocumented).

**Commands** (`website/content/docs/commands/`):
- `ait gates` / `ait gate` CLI reference (list, status, unlocked, run,
  append, pass, fail, log).

**Configuration:**
- `gates.yaml` registry reference; profile schema changes — per the
  **ceiling model from t635_33** (see Premise refresh below), NOT the
  superseded t635_14 single-key model.

## Premise refresh (2026-07-26 — t635_33 active-gates model)

This task was last updated 2026-06-10; **t635_33 landed 2026-07-19** and
superseded the profile gate model the Configuration bullet named. The content
map must document the current model:

- **Two profile keys with presence semantics.** `rendered_gates` is the
  render-time ceiling and wins whenever the KEY is present — including an
  explicit `[]`, the render-nothing override; only when absent does
  `default_gates` apply. Three states to explain, not one list. Live examples
  to describe generically: one profile setting `default_gates` only, one
  setting `rendered_gates: []`, one setting neither.
- **Declared intent vs enforced set.** A task's `gates:` is *declared intent*;
  the enforced set is the derived `active_gates` tuple materialized at claim
  time, alongside `active_gates_filtered` (what the ceiling removed),
  `active_gates_profile` (provenance stamp) and `active_gates_digest`. The task
  file format page must cover these fields — and say they are framework-written
  and must not be hand-edited.
- **The ceiling invariant.** A gate filtered out by the profile is
  **invisible**, or at most reported as "skipped: execution profile" — **never
  an error**. This is the single most surprising behavior for a user whose task
  declares a gate that never runs, so it belongs in the Gates concept page.
- **Also document `record_gates`** — a third profile knob, separate from the two
  lists, which currently controls whether the gate machinery (including the
  Step-8 procedure-gate dispatch) is rendered into a profile's task-workflow
  variant at all.
- Re-derive the whole content map at planning time against live source rather
  than trusting the bullets above — this refresh corrects the model, but the
  map itself was already marked "refine at planning time".

## Conventions checklist

- Current-state-only prose; no version history in doc bodies.
- Generic placeholder project names; genericize agent references.
- "Autonomous", not "auto-execution", for headless behavior.
- No "sister repo" terminology — "cross-repo" / "linked repo".

## Dependency note

Depends on the major user-facing surfaces (pick, board, monitor,
workflow gates, profile model). Later children (t635_15..t635_17) must
carry their own doc updates when they land — enforced by the
`docs_updated` gate itself once t635_19 ships (the framework dogfooding
its own documentation gate).

## References

- `aidocs/gates/integration-roadmap.md`
- `aidocs/gates/aitask-gate-framework.md`
- `aidocs/framework/documentation_conventions.md`
