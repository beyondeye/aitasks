---
Task: t1687_1_concepts_gates_page.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_1m @ 2026-09-22 09:06
---

# t1687_1 — Gates concept page

## Context

`website/content/docs/concepts/` is the section that answers "what is this
building block and why does it exist". It has no **Gates** page, which the
t1687 sweep identified as the section's single largest omission: gates are
documented in `commands/gates.md`, `skills/aitask-run-gates.md`,
`development/task-format.md` and `tuis/board/reference.md`, but nowhere as a
concept.

This child adds that page and repoints the pages that currently carry the
conceptual explanation inline. Ownership was settled at t1687 planning
(2026-09-20): t635_18 also planned a Gates page but is blocked behind t635_37,
so **t1687 writes it and t635_18 later extends it**.

## Verification of the existing plan (this pick)

The plan at `aiplans/p1687/p1687_1_concepts_gates_page.md` was re-verified
against the tree. Everything material still holds; five corrections below.

Confirmed accurate:

- All six file targets and every line anchor: `commands/gates.md` lead at 9-16
  with the lone relative link at line 13; `development/task-format.md` gate rows
  71-76; `tuis/board/reference.md` `#gate-progress` at 493;
  `crash-recovery.md` `## See also` at 182; `risk-evaluation.md` `## See Also`
  at 92.
- Per-file link-form measurements (`commands/gates.md` 3:1,
  `task-format.md` 10:1, `board/reference.md` 12:1, `crash-recovery.md` 1:8,
  `risk-evaluation.md` now 0:14 — same verdict).
- Weight **85** is free (agent-attribution 80 → locks 90), and t1687_5 expects
  exactly that weight and group.
- `concepts/` contains **zero** hand-written relative links.
- Every technical claim the page will make: the digest is three-part
  (`^[0-9a-f]{12}\.[0-9a-f]{12}\.[0-9a-f]{12}$`), a mismatch falls back to raw
  `gates:` (`_active_set_csv`), `MATERIALIZED:(empty)` is a real state, and an
  explicit `gates: []` is never backfilled (`has-gates-field`).

Corrections:

1. **The pre-phase is already satisfied.** The ownership note reached t635_18 on
   2026-09-20 09:05 (`INBOX_UNREAD:635_18|2026-09-20T09:05:29Z…|t1687`). Do not
   re-send.
2. **No `**Next:**` footer on this page.** The plan cites
   `framework-session.md` as the canonical shape "→ `---` → `**Next:**`", but
   that page has no such footer. More decisively, **t1687_5 owns the reading
   chain** ("Splice the six new pages into the chain in weight order"). End the
   page at `## See also`, exactly like `framework-session.md`.
3. **`risk-evaluation.md`'s See Also already has a `Gates` entry** pointing at
   `../../commands/gates/`. Adding a second bullet labelled "Gates" collides.
   Disambiguate (see Step 4).
4. **The slug collision is created by this change.** `commands/gates.md` is
   currently the only `gates` slug. No bare `relref "gates"` exists anywhere
   today (all 8 use full paths), so nothing breaks — but every relref this task
   writes must use the full `/docs/concepts/gates` path.
5. `crew.md`'s pattern sentence is at lines **10-13**, not 9-12.

Also verified safe: the trimmed region (`commands/gates.md` 9-16) contains no
headings, so none of the four inbound anchors
(`#ait-gates-run`, `#ait-gate-pass`, `#ait-gates-sync-registry`) is orphaned.

## Implementation

### 1. Write `website/content/docs/concepts/gates.md`

Frontmatter, keys in this order (matching `framework-session.md`):

```yaml
---
title: "Gates"
linkTitle: "Gates"
weight: 85
description: "..."
depth: [advanced]
---
```

Structure: `## What it is` → `###` subsections → `## Why it exists` →
`## How to use` → `## See also`. **No `**Next:**` footer** (see correction 2).

The page's angle — **declared intent vs the framework-derived enforced set, and
why enforcement is a claim-time snapshot**:

1. **Declared intent vs the enforced set** — `gates:` is what the task asks for;
   `active_gates` + `_filtered` / `_profile` / `_digest` is what is enforced.
   Framework-derived, never hand-edited.
2. **A claim-time snapshot** — materialized at claim time
   (`aitask_gate.sh materialize-active`), re-derived on every re-pick, so a
   profile switch cannot leave stale enforcement. `MATERIALIZED:(empty)` is a
   real state (fully profile-filtered). An explicit `gates: []` is an opt-out
   and is never backfilled.
3. **The digest and its fallback** — three 12-hex parts over the resolve inputs
   and stored outputs. On mismatch, enforcement falls back to the raw `gates:`
   field until the next pick re-materializes. Worth stating precisely: only the
   gates-half and outputs-half are checkable *without* a profile, which is why a
   profileless reader can still detect a stale tuple.
4. **Kinds of gate** — `machine`, `human`, and **procedure-backed** (`kind:`),
   whose verifier names a skill rather than a shell command, so the headless
   engine defers it to an attended agent.
5. **The ledger** — `## Gate Runs` is append-only; per-gate state is *derived*
   from it and never duplicated into `status`.
6. **The registry** — `aitasks/metadata/gates.yaml` declares how each gate runs
   (`type`, `verifier`, `max_retries`, `unlocks`, `timeout_seconds`, `signal`,
   `blocks_dependents`, `kind`); the execution profile chooses which are
   declared. Reconciled downstream with `ait gates sync-registry`.
7. **Retry budgets and the unlock DAG.**
8. **Archival and unblocking** — a task with an unmet enforced gate does not
   archive; `also_blocks_dependents` extends that to its dependents.

**Must NOT restate** (verified boundaries):

- `commands/gates.md:9-16` — the existing lead definition; trim it instead.
- `tuis/board/reference.md:462-545` — the five workflow phases, chip rendering,
  the gate-progress fraction rules, honest degradation and the task-detail row
  table. That is the *board's rendering* of declared-vs-enforced; this page
  covers the *model*.

### 2. Trim the `commands/gates.md` lead to a pointer

Replace lines 9-16 with the `crew.md:10-13` shape:

> `ait gates` and `ait gate` operate on a task's verification gates. For the
> conceptual model (declared intent vs the enforced set, the ledger, the
> registry, and gate-guarded archival), see the
> [Gates concept page]({{< relref "/docs/concepts/gates" >}}).

Keep the "Two commands operate on gates" orientation that follows.

**While in that paragraph, fix line 13**: replace
`[task file format](../../development/task-format/)` with
`{{< relref "/docs/development/task-format" >}}` — the file is 3:1
relref-dominant and this is its lone relative link.

### 3. Add back-links to the three unambiguous pages

| File | Where | Form |
|---|---|---|
| `development/task-format.md` | gate rows 71-76 | relref |
| `tuis/board/reference.md` | `#gate-progress` (493) | relref |
| `workflows/crash-recovery.md` | `## See also` (182) | **relative** `[Concepts: Gates](../../concepts/gates/)` |

`crash-recovery.md` takes the relative form (1:8) and already uses the
`Concepts: <name>` label style for its `Locks` bullet — match it.

### 4. Add the `risk-evaluation.md` back-link, disambiguated

`workflows/risk-evaluation.md` is 0:14 → **relative** form. Its `## See Also`
already contains:

```
- [Gates](../../commands/gates/) — the `risk_evaluated` gate that verifies this step's output
```

**Confirmed disambiguation:** relabel the existing bullet to `` `ait gates` ``
and add the concept bullet as plain `Gates`:

```
- [Gates](../../concepts/gates/) — what a gate is and how enforcement is derived
- [`ait gates`](../../commands/gates/) — the `risk_evaluated` gate that verifies this step's output
```

## Risk

### Code-health risk: low

- Creating `concepts/gates.md` makes `gates` an ambiguous slug site-wide, so any
  *future* bare `{{< relref "gates" >}}` fails the build. No bare relref exists
  today (verified: 0 of 8) and every relref this task writes uses the full path
  · severity: low · → mitigation: None needed — `hugo build` fails loudly rather
  than shipping a broken link.
- Six markdown files, no code, both verifiers gate the result · severity: low ·
  → mitigation: None identified.

### Goal-achievement risk: medium

- **The page misdescribes shipped behaviour.** `hugo build` and
  `check_links.py` verify structure, not truth — a wrong claim about digest
  semantics, the fallback, or materialization passes every gate and ships
  · severity: medium · → mitigation: inline post-phase `gates_page_accuracy_review`
- **The complementary-angle constraint is a judgement call.** Overlapping
  `board/reference.md`'s 80 lines of declared-vs-enforced prose would make the
  page redundant rather than additive · severity: low · → mitigation: inline
  post-phase `gates_page_accuracy_review` (same review pass)
- A back-link could land on a page that does not genuinely discuss gates —
  passes both verifiers · severity: low · → mitigation: inline post-phase
  `link_relevance_triage`

### Planned mitigations
- timing: post-phase | name: gates_page_accuracy_review | type: documentation | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — page misdescribes shipped behaviour / complementary-angle overlap | desc: Re-read the finished page against aidocs/gates/aitask-gate-framework.md and the real behaviour of aitask_gate.sh, confirming the digest, fallback and (empty) claims and the no-restate boundary
- timing: post-phase | name: link_relevance_triage | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — back-link relevance | desc: Confirm each of the five back-links lands on a page that genuinely discusses gates; t1687_5 runs the site-wide pass
- timing: dropped | name: record_page_ownership_notes | addresses: ownership overlap with t635_18 | desc: DROPPED — already satisfied; the ownership note reached t635_18 on 2026-09-20 09:05 (verified in its inbox this pick)

## Post-phase (risk mitigations)

### gates_page_accuracy_review

Before committing, re-read `concepts/gates.md` against
`aidocs/gates/aitask-gate-framework.md` and the actual behaviour of
`aitask_gate.sh`, confirming every claim:

- the digest is three-part, and only the gates-half and outputs-half are
  checkable without a profile;
- a digest mismatch falls back to the raw `gates:` field (`_active_set_csv`);
- `MATERIALIZED:(empty)` is a real, meaningful state (fully profile-filtered);
- an explicit `gates: []` is an opt-out and is never backfilled;
- `active_gates*` are framework-derived and never hand-edited.

Then confirm the page does not restate `commands/gates.md:9-16` or
`tuis/board/reference.md:462-545`.

### link_relevance_triage (shared with t1687_5)

Confirm each of the five back-links lands on a page that genuinely discusses
gates. t1687_5 runs the site-wide `check_link_relevance.py` pass.

## Constraints

- Full path `/docs/concepts/gates` in every relref.
- **No mermaid** — the site has no support; a fence builds green and renders as
  a plain code block. Use box-drawing ASCII in a ```text fence
  (`framework-session.md:50-64` is the model).
- Current-state-only prose (`aidocs/framework/documentation_conventions.md`).
- Do **not** touch `concepts/_index.md` and do **not** add a `**Next:**` footer
  — t1687_5 owns both.

## Verification

```bash
cd website && set -o pipefail && hugo build --gc --minify
cd website && set -o pipefail && python3 check_links.py --build
```

Check `${PIPESTATUS[0]}` if piping. Then confirm:

- `#gate-progress`, `#ait-gates-run`, `#ait-gate-pass` and
  `#ait-gates-sync-registry` still resolve;
- `concepts/` still contains **zero** hand-written relative links;
- no bare `relref "gates"` was introduced.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. The `risk_evaluated` gate is active and
must pass before archival.

## Implementation Notes

All four implementation steps done as planned. Deviations and findings:

- **Code, not the design doc, was the source for the enforced tuple.**
  `aidocs/gates/aitask-gate-framework.md` predates `active_gates*`, and
  `gate-guarded-archival.md` still says archival requires "every *declared*
  gate". The shipped code reads the **enforced** set for both archival
  (`archive_status_from_text`: "a profile-filtered gate can never block
  archival") and dependency unblocking (`dependents_status`, which also drops
  `also_blocks_dependents` entries the profile filtered). The page follows the
  code. Facts taken from `lib/gate_ledger.py` `compute_active_gates` /
  `build_active_digest` and `lib/gate_orchestrator.py` `successors`.
- **Two claims corrected against the code before writing:** the archive guard
  refuses *unless overridden* (`--ignore-gates` exists), so the page does not
  say "no caller can archive past an unmet gate"; and `max_parallel_gates` is
  read by `ait gates run` (`aitask_run_gates.sh`, default 2), not the
  orchestrator module.
- **`ait create` link:** `--gates` is documented only on the `/aitask-create`
  skill page (as a batch flag of the create script), so the "How to use" link
  names that page rather than a nonexistent `ait create` command page.
- **Back-link wording:** `crash-recovery.md` uses its existing
  `Concepts: <name>` label; `task-format.md` follows the `See [Agent
  attribution](…)` pattern already in the same table.

### Post-phase results

- **gates_page_accuracy_review** — every claim re-checked against the code.
  Three fixes applied: the ledger's first line carries an attempt number only
  once a run has finished (`pending` blocks carry none); `blocks_dependents`
  examples narrowed to "review and merge approval" (`plan_approved` is
  `blocks_dependents: false`); dependency unblocking now stated to read the
  enforced set. No-restate boundary holds — the definition *moved* off
  `commands/gates.md` rather than being duplicated, and none of
  `board/reference.md:462-545` (phases, chips, fractions, degradation, detail
  rows) is repeated.
- **link_relevance_triage** — all five back-links land on pages that discuss
  gates (`crash-recovery.md` has a full "Resuming From the First Unmet
  Checkpoint" section). One outbound bullet reworded: `concepts/execution-profiles`
  never mentions gates, so its See-also line no longer implies it covers the
  ceiling. `check_link_relevance.py` flagged one link from this page
  (`/aitask-gate-docs-updated` → `#why-it-runs-where-it-runs`), triaged as a
  **false positive**: the text names the skill whose page it targets, and the
  section is exactly about the procedure-backed class. The other reported links
  are on lines this task did not touch — left to t1687_5's site-wide pass.

### Verification

- `hugo build --gc --minify` → exit 0.
- `check_links.py --build` → `broken: 0`, `SWEEP: PASSED`.
- `#ait-gates-run`, `#ait-gate-pass`, `#ait-gates-sync-registry`,
  `#gate-progress`, `#frontmatter-fields`, `#why-it-runs-where-it-runs` all
  present in the built HTML.
- `concepts/` hand-written relative links: 0. Bare `relref "gates"`: 0.
  Mermaid fences in changed files: 0.

## Post-Review Changes

### Change Request 1 (2026-09-22 09:40)
- **Requested by user:** The human-gates bullet stated that an `ait gate pass`
  signature is code-bound immediately after listing `plan_approved`,
  `review_approved` and `merge_approved`, implying all three are code-bound.
  Only `review_approved` and `merge_approved` are.
- **Verified:** valid. Only those two carry `signal: file-touch`, and
  `stale_signed_gates` only considers gates with a stamped witness. Checking it
  surfaced a second error in the same sentence: "otherwise they pend until
  someone signs with `ait gate pass`" is false for `plan_approved` —
  `aitask_gate_pass.sh:72-74` refuses it ("attended-only checkpoint — nothing
  to sign").
- **Changes made:** Split the human-gates bullet into two sub-bullets:
  `plan_approved` (attended-only, `ait gate pass` refuses it) and
  `review_approved` / `merge_approved` (attended recording, or asynchronous
  signing with a code-bound witness that re-pends on a code change). Dropped
  "from anywhere" — the witness file is local (gitignored `.aitask-gates/`).
  Nested list confirmed rendering in the built HTML.
- **Files affected:** `website/content/docs/concepts/gates.md`

## Final Implementation Notes

- **Actual work done:** New `website/content/docs/concepts/gates.md` (weight 85,
  `depth: [advanced]`, no `**Next:**` footer). Its angle is declared intent
  versus the enforced `active_gates*` tuple and why that tuple is a claim-time
  snapshot. It covers the profile ceiling, the empty-set and `gates: []` cases,
  the three-part digest and its one-directional fallback, machine / human /
  procedure-backed gates, the ledger, the registry, retry budgets, the unlock
  order, archival and dependency unblocking. Five back-links: the
  `commands/gates.md` lead was trimmed to a pointer (its lone relative link is
  now a relref), a `See [Gates]` link was added to the `task-format.md` `gates`
  row, a pointer under board `#gate-progress`, a `Concepts: Gates` bullet in
  `crash-recovery.md`, and in `risk-evaluation.md` the existing bullet was
  relabelled `` `ait gates` `` next to a new `Gates` concept bullet.
- **Deviations from plan:** None in scope. The pre-phase ownership note was not
  re-sent (already in t635_18's inbox), as the verified plan recorded.
- **Issues encountered:** The design docs under `aidocs/gates/` predate the
  enforced tuple and describe archival/unblocking against *declared* gates; the
  shipped code reads the *enforced* set. The page follows the code (see
  Implementation Notes). The review caught one misstatement: code-binding
  applies only to `review_approved` / `merge_approved`, and `ait gate pass`
  refuses `plan_approved` (Change Request 1).
- **Key decisions:** Explain the profile ceiling (`default_gates` /
  `rendered_gates`) in model terms on this page, since no other website page
  documents `rendered_gates`. Scope the code-binding claim to the
  `ait gate pass` signing path — an attended approval writes no witness.
- **Upstream defects identified:**
  - `aidocs/gates/gate-guarded-archival.md:28-33` — the stated criterion says a task may archive iff "every *declared* gate" passes, but `archive_status_from_text` reads the enforced active set (t635_33): a profile-filtered gate never blocks archival. Internal design doc is stale.
  - `aidocs/gates/dependency-unblock-semantics.md:57-60` — the unblock pseudocode computes `required` from `U.gates` (declared); `dependents_status` reads the enforced set and drops profile-filtered `also_blocks_dependents` entries. Internal design doc is stale.
- **Notes for sibling tasks:**
  - Verify against the code, not `aidocs/`: several gate design docs are
    proposals written before the feature shipped, and they describe superseded
    behaviour.
  - `check_link_relevance.py` flags `[`/skill`](…#section)` links — link text
    naming the page, anchor narrowing to a section. Expect it; it was a false
    positive here.
  - A concepts page can be cross-checked for nested-list rendering by
    building into a scratch dir (`hugo build -d <dir>`) and grepping the page's
    `index.html`.
  - `commands/gates.md` and `concepts/gates.md` now share the `gates` slug:
    every relref to either must use the full `/docs/...` path.
  - The `**Next:**` chain insertion point for this page (agent-attribution 80 →
    gates 85 → locks 90) is left to t1687_5, as its task file specifies.
