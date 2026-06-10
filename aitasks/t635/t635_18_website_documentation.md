---
priority: medium
effort: high
depends: [t635_7, t635_9, t635_10, t635_12, t635_14]
issue_type: documentation
status: Ready
labels: [gates, web_site]
created_at: 2026-06-10 19:03
updated_at: 2026-06-10 19:03
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
- `gates.yaml` registry reference; profile schema changes (gates declared
  by profiles at planning time, `default_gates`); per the unification
  model from t635_14.

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
