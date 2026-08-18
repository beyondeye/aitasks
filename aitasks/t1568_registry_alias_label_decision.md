---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [tui, project_groups]
gates: [risk_evaluated]
anchor: 1544
followup_kind: risk_mitigation
created_at: 2026-08-18 12:30
updated_at: 2026-08-18 12:30
---

## Origin

Risk-mitigation ("after") follow-up for t1544_1, created at Step 8d after implementation landed.

## Risk addressed

`addresses:` code-health — a deduped aliased registry row can change the
surviving record's rendered label.

Verbatim from t1544_1's plan `## Risk` section:

> Where a deduped record's label was sourced from the registry `name` rather
> than the directory basename, the rendered label can change. In stats the
> outcome is *order-dependent* — `{s.key: lbl}` is last-wins over a
> session-name sort, so it may already resolve to the live record's basename —
> which makes the change hard to predict per-environment · severity: low
> · → mitigation: registry_alias_label_decision

## Goal

Decide whether the record surviving a key-dedupe should adopt the registry
`name` instead of `project_root.name`, and implement the chosen semantics.

### Background

t1544_1 made `_assemble_aitasks_sessions` collapse records resolving to the
same repo, keeping the **first** — which is structurally the live record,
because live records are appended before registered ones. A registry row
whose `name` differs from the directory basename at a live path (duplicate
source 2) is therefore dropped, and the survivor carries
`project_name = project_root.name`.

Consequence: for a repo whose registry entry declares an alias
(e.g. `name: acme-main` at a directory named `acme`), any surface that labels
by `project_name` renders the **basename**, not the registered alias.

Measured during t1544_1:

- **Switcher** — labels are session-name-primary, so the alias row simply
  disappears as a duplicate; no single row's label "changes".
- **Stats / syncer** — labels are `project_name`-primary. Before the dedupe,
  `{s.key: lbl}` collapsed last-wins over a session-name sort, so the rendered
  label was already order-dependent and could land on either the alias or the
  basename. After the dedupe it is deterministically the basename.

### Decision to make

Either:

1. **Keep current behaviour** (survivor keeps `project_root.name`) and
   document that registry aliases do not affect display for live repos; or
2. **Merge the registry `name` onto the surviving record** when a registered
   row is deduped away, so the user-declared alias wins.

Option 2 was explicitly considered and **deferred** during t1544_1's plan
review: it turns the dedupe from a first-wins **filter** into a field
**merge**, which is a larger change to a helper feeding every registry-
inclusive TUI. If option 2 is chosen, keep
`_dedupe_sessions_by_key`'s filter shape intact and do the merge in a separate,
clearly named step so the two concerns stay separable.

### Verification

- `python3 tests/test_discover_session_dedupe.py` — the duplicate-input checks
  pin `live project_name kept` = basename today; they must be updated
  deliberately (not incidentally) if option 2 is chosen.
- `python3 tests/test_switcher_ring_dedupe.py`
- Check the stats and syncer session labels for a repo whose
  `project_config.yaml` declares a `project.name` different from its directory
  basename.
