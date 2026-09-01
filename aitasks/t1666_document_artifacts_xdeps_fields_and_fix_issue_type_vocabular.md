---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, web_site, frontmatter, seed]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-01 15:27
updated_at: 2026-09-01 15:28
---

## Problem

The task frontmatter ("metadata header") schema has grown to 39 live fields, but
the canonical website reference has not kept pace, and the `issue_type`
vocabulary is spelled out — stale — in eight separate places.

Established by exploration against the live corpus (all active `aitasks/*.md` +
`aitasks/t*/t*.md`), the CLI flag surface (`ait create --help`, `ait update
--help`), and the metadata vocabularies.

## Findings

### 1. Three live fields have no row in the canonical table

`website/content/docs/development/task-format.md` documents 36 fields. Missing:

| field | on disk | introduced | site coverage |
|---|---|---|---|
| `artifacts` | 4 tasks | 2026-07-05 (t1076_1, `e65eb4249`) | **nowhere** as a frontmatter key |
| `xdeprepo` | 4 tasks | 2026-05-27 (t832_3, `56f3dfd68`) | only `workflows/cross_project_dependencies.md` |
| `xdeps` | 2 tasks | 2026-05-27 (t832_3, `56f3dfd68`) | only `workflows/cross_project_dependencies.md` |

All three are settable: `--xdeprepo` / `--xdeps` on both `ait create` and
`ait update`; `artifacts` is written by `ait artifact` / `ait attach`.

`artifacts` is the header's **only nested field** — a list of mappings keyed
`handle` / `kind` / `name` / `mime` / `size` / `added_at` / `backend` / `url`
(ordering per `.aitask-scripts/lib/frontmatter_patch.py:47` `FIELD_ORDER`).
The existing table is entirely flat-scalar/flat-list shaped and has no idiom
for a nested block, so this row needs an example, not just a cell.

### 2. The `issue_type` vocabulary is stale in eight places

`aitasks/metadata/task_types.txt` **and** `seed/task_types.txt` both ship **10**
types. Every enumerated copy below lists only **9** — `manual_verification` is
missing:

- `website/content/docs/development/task-format.md:37`
- `CLAUDE.md:139` (frontmatter block) and `CLAUDE.md:208` (commit-type list)
- `seed/aitasks_agent_instructions.seed.md:15` and `:74` — **ships to downstream
  projects**, whose seeded `task_types.txt` does include `manual_verification`
- `.claude/skills/task-workflow/SKILL.md:698` and
  `.claude/skills/task-workflow-remote-/SKILL.md:621` (commit-format rule)
- `.claude/skills/aitask-wrap/SKILL.md.j2:77`
- `.claude/skills/aitask-docs-gap/SKILL.md:75`

`task-format.md` is additionally **self-contradictory**: line 52 states that
`followup_kind: manual_verification` "additionally requires `issue_type:
manual_verification`" — a value line 37 says does not exist.

Note the two commit-type sites (`CLAUDE.md:208`,
`seed/aitasks_agent_instructions.seed.md:74`) are a separate question from the
frontmatter sites: decide explicitly whether `manual_verification:` is a valid
commit-message type before adding it there.

### 3. `--also-blocks-dependents` is undocumented site-wide

The flag exists on both `ait create` and `ait update`; the field
`also_blocks_dependents` **is** in the task-format table, but the flag that sets
it appears nowhere in `website/content/docs`.

### 4. `concepts/tasks.md` carries an 8-field snapshot

Last touched 2026-04-21. It describes the header as "fields like `priority`,
`effort`, `depends`, `status`, `labels`, `assigned_to`, `issue_type`,
`boardcol`" — 8 of 39 — and offers no pointer to the full table in
`development/task-format.md`.

### 5. The two agent-instruction copies have already drifted from each other

`seed/aitasks_agent_instructions.seed.md` spells all four `active_gates*` fields
and the full 8-value `followup_kind` vocabulary inline; `CLAUDE.md` compresses
both to pointers. Neither lists `artifacts`, `xdeprepo`, `xdeps`, `verifies`, or
`file_references`.

## Deliberately out of scope of the finding (confirm during planning)

Workflow-written flags absent site-wide, plausibly by design because they are
framework-derived and never hand-set: `--plan-approved-at`, `--risk-code-health`,
`--risk-goal-achievement`, `--risk-mitigation-tasks`, `--active-gates`,
`--active-gates-profile`, `--clear-active-gates`. Decide once, explicitly —
either document them as read-only or record why they stay out.

## What is already clean (do not re-audit)

- `status` (6 values) matches `aitask_update.sh:1927` exactly.
- `followup_kind` (8 values) matches `.aitask-scripts/lib/followup_kinds.py`.
- All 8 gates in `aitasks/metadata/gates.yaml` are documented on the site.
- Every `ait ls` filter flag appears on the site.
- `ait` subcommand coverage is complete except `diffviewer` (intentional, per
  CLAUDE.md).
- `manual_verification` as a concept is covered on 9 other website pages — the
  gap is precisely the canonical field table, not the feature's documentation.

## Why this recurs

Nothing under `tests/` references `task-format.md`. The field table is
hand-maintained, and the three missing fields post-date fields that *did* get
rows (`followup_kind`, `plan_approved_at`), so this is per-field oversight
rather than a lapsed document.

Planning should decide whether to add a guard that scans the real field set and
asserts a table row exists for each, and where its source of truth lives
(the corpus is not it — a brand-new field has zero on-disk instances). A
plausible source is the `ait create` / `ait update` flag surface plus the
framework writers, but the guard must not fail open on a field it cannot see.

## Acceptance criteria

- `task-format.md` has rows for `artifacts` (with a nested example),
  `xdeprepo`, and `xdeps`.
- The `issue_type` row in `task-format.md` lists all 10 types from
  `task_types.txt`, and the self-contradiction with the `followup_kind` row is
  gone.
- Every enumerated `issue_type` copy in section 2 is corrected, or explicitly
  recorded as intentionally 9-valued with the reason stated in place.
- `--also-blocks-dependents` is documented on the website.
- `concepts/tasks.md` no longer implies an 8-field header and links to the full
  table.
- The workflow-written-flag question in "Deliberately out of scope" is answered
  in the plan, not left open.
- `hugo build --gc --minify` succeeds in `website/`, and any `relref` added
  resolves (a dead `#fragment` does **not** fail the build — check anchors by
  hand).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T12:58:07Z status=pass attempt=1 type=human
