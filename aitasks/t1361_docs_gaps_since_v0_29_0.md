---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [docs, web_site]
created_at: 2026-07-31 12:07
updated_at: 2026-07-31 12:07
---

Documentation gaps found by /aitask-docs-gap for the release window v0.29.0..HEAD.
Each section below is self-contained and can become its own child task at
decomposition time.

Window scope: 43 task-tagged tasks analyzed — 18 already documented, 21 not
doc-relevant (tests, internal refactors, design-doc-only changes), 4 gaps below.

## Gap: `ait gates sync-registry` (t635_34)

- **Target doc page(s):** `website/content/docs/commands/` — no page currently
  covers the `ait gate` / `ait gates` family; `commands/_index.md` has no gates
  entry in any group, and the only site mention of the CLI is a single
  `ait gate pass <task-id> <name>` line in `skills/aitask-resume.md`.
- **What shipped:** A new `sync-registry` verb in `aitask_gate.sh`, dispatched
  from `ait`, that reconciles a project's installed `aitasks/metadata/gates.yaml`
  against the framework's `gates_reference.yaml`: it fills missing fields,
  reports CONFLICT for locally customised values rather than overwriting them,
  preserves comments, supports `--dry-run`, takes a repo-level `registry_lock`,
  never auto-commits, and exits 0 for every completed run (NOOP / applied /
  conflicts) with distinct nonzero codes for fail-closed conditions. An
  `AIT_GATES_REFERENCE` environment override selects an alternate reference. A
  claim-time warning now fires when an active gate has no configured verifier —
  the condition `sync-registry` exists to repair.
- **What to write:** A user-facing entry for the gates CLI surface in
  `commands/` — at minimum `ait gates sync-registry` (what it reconciles, the
  `--dry-run` flag, FILLED vs CONFLICT reporting, that it commits nothing so the
  registry change stays review-worthy, and the exit-status contract), plus the
  already-shipped-but-undocumented `ait gate pass`. Add the corresponding row(s)
  to the `commands/_index.md` table and cross-link from
  `workflows/risk-evaluation.md`, which describes gates conceptually but names
  no CLI at all. Note the "no verifier configured" warning as the symptom that
  should send a user to this command.
- **Sources:** `aiplans/archived/p635/p635_34_reconcile_installed_gate_registry.md`;
  commits: c09d6cd68

## Gap: board By-Trail view refresh ladder and key contract (t1268)

- **Target doc page(s):** `website/content/docs/tuis/board/reference.md`
  (View Filters section, ~line 129) and `website/content/docs/tuis/board/how-to.md`
- **What shipped:** The By-Trail view got a three-key refresh ladder — `r`
  (local re-render, zero subprocess), `d` (recorded-freshness re-read), `R`
  (spawn a refresh agent, with an armed artifact-version watch) — plus `S` to
  run `ait sync` from the view, `C` hidden in this view, per-view footer labels,
  and per-card drift markers.
- **What to write:** The board reference currently has **no By-Trail entry at
  all**: the View Selector render block shows
  `[a All | l Locked | f Free | i In-Flight | y By-Topic]` and the base-filter
  table stops at By-Topic, even though the view has a base key (`z`) and shipped
  before this window. Writing this gap therefore means adding the By-Trail base
  filter to the selector render and the base-filter table, then documenting the
  refresh ladder (what each of `r` / `d` / `R` costs and refreshes), `S`, the
  absence of `C`, the drift markers, and the fact that the footer relabels per
  view. Cross-link to whatever page covers implementation trails.
- **Sources:** `aiplans/archived/p1268_bytrail_refresh_semantics_and_key_footer_contract.md`;
  commits: ceb07381d

## Gap: COMPLETED agent state in monitor and minimonitor (t1322)

- **Target doc page(s):** `website/content/docs/tuis/monitor/how-to.md`,
  `website/content/docs/tuis/monitor/reference.md`,
  `website/content/docs/tuis/minimonitor/how-to.md`
- **What shipped:** A fourth agent state, COMPLETED, in the shared state ladder
  (`PROMPT > COMPLETED > IDLE > active`), rendered as a `dodger_blue1` card
  badge / status dot. Both apps compute one per-refresh completed-pane set that
  drives the badge, the session-bar counters (now three-way) and the auto-switch
  filter — auto-switch no longer focuses an agent whose task is done. Shadow
  panes can never render as COMPLETED. Detection retries on a decaying schedule
  that never gives up, so a late archive still resolves.
- **What to write:** Both TUI pages describe only green/active and yellow/idle.
  Add COMPLETED to the status-indicator lists (card anatomy in the monitor
  how-to, the status-dot list in the minimonitor how-to), update the session-bar
  / title-bar counter descriptions to the three-way form, and note in the
  auto-switch (`a`) description that completed agents are excluded. Describe
  what "completed" means (the pane's task reads as done) rather than the
  internal detection mechanism.
- **Sources:** `aiplans/archived/p1322_monitor_completed_agent_status.md`;
  commits: 411c7a546

## Gap: recovering a plain-bullet verification checklist (t1264)

- **Target doc page(s):** `website/content/docs/workflows/manual-verification.md`
- **What shipped:** A `convert` subcommand on the verification parser that turns
  plain bullets inside an existing verification-checklist section into pending
  checkbox items — preserving item text and indentation, skipping items that are
  already checkboxes, updating task metadata atomically, and erroring without
  mutating when there is nothing to convert. The checklist runner gained a
  matching recovery option, so a checklist written with plain bullets is no
  longer a dead end.
- **What to write:** The page's subcommand list (`parse`, `set`, `summary`,
  `terminal_only`, `seed`) is missing `convert`. Add it, plus a short "recovering
  a plain-bullet checklist" passage in the checklist-format section explaining
  the symptom (a checklist whose items are plain bullets is unrecoverable to the
  runner), the recovery offer, and the no-op / error case. While on the page,
  verify the referenced helper path is current — the shipped work is in
  `.aitask-scripts/aitask_verification_parse.py`.
- **Sources:** `aiplans/archived/p1264_manualverification_checklist_with_plain_bullets_is_unrecover.md`;
  commits: 2679e5261
