---
priority: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, website]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-09-24 22:19
updated_at: 2026-11-15 17:48
---

## Context

Spawned from t1687_5 (Concepts docs gap sweep). While re-verifying the sweep's
deferred gaps against the current site, one remained genuine: four `ait
brainstorm` subcommands are not documented anywhere on the website.

`tuis/brainstorm/` already documents `init`, `status`, `list`, `archive` and
`ait brainstorm <num>` (see `tuis/brainstorm/how-to.md` around line 133 and
`tuis/brainstorm/_index.md`). A grep of `website/content/docs` for
`brainstorm (delete|apply-)` returns nothing.

## Undocumented subcommands

From the dispatcher in `ait` (the `brainstorm)` case) and its help text:

- `delete` — completely delete a brainstorm session (`aitask_brainstorm_delete.sh`)
- `apply-initializer` — re-run apply on a session; recovers stuck imports
  (`aitask_brainstorm_apply_initializer.sh`)
- `apply-explorer` — re-run apply on an explorer agent; recovers stuck
  explorations (`aitask_brainstorm_apply_explorer.sh`)
- `apply-synthesizer` — re-run apply on a synthesizer agent; recovers stuck
  hybrids (`aitask_brainstorm_apply_synthesizer.sh`)

## Suggested approach

- Read each script's `--help` / usage and its effect before writing prose.
- Most likely home: a recovery / cleanup section in
  `website/content/docs/tuis/brainstorm/how-to.md`, next to the existing
  `status` / `list` / `archive` sentence. A `commands/brainstorm.md` page is the
  alternative if the full CLI surface warrants one — TUIs are otherwise
  documented under `tuis/`, not `commands/`.
- Document behaviour, not just the command names: what state each `apply-*`
  recovers from, and what `delete` removes (and whether it is reversible).

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build
```

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-15T15:48:30Z status=pass attempt=1 type=human
