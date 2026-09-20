---
Task: t1687_1_concepts_gates_page.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
---

# t1687_1 — Gates concept page

## Goal

Add `website/content/docs/concepts/gates.md` (weight 85, *Workflow primitives*,
`depth: [advanced]`), and point the five pages that currently explain gates
inline at it.

## Pre-phase (risk mitigations)

### record_page_ownership_notes

**Runs before any page is written.** The parent task sends the ownership notes
at decomposition time; if for any reason no note reached t635_18, send it now:

```bash
./ait note 635_18 --from 1687_1 --file - <<'EOF'
t1687 planning (2026-09-20) decided that t1687 writes the Gates concept page at
website/content/docs/concepts/gates.md (weight 85). Your content map's
"New Gates concept page" item is therefore already owned; your task shrinks to
extending that page rather than creating it. Advisory only — verify before acting.
EOF
```

`NOTE_APPENDED:` is the authoritative result. A `LIVE_NONE:` after it is success
with live delivery unavailable, not a failure.

## Implementation

### 1. Read the sources before writing

- `aidocs/gates/aitask-gate-framework.md` — the model.
- `aidocs/gates/gate-guarded-archival.md`, `dependency-unblock-semantics.md`,
  `ledger-driven-reentry.md`, `risk-evaluation-gate-seam.md`.
- `.aitask-scripts/aitask_gate.sh` — the real verb surface, especially
  `materialize-active`, `archive-ready`, `resume-point`, `active`.
- `website/content/docs/development/task-format.md:71-76` — the field rows this
  page explains.

### 2. Write `concepts/gates.md`

Frontmatter, keys in this exact order:

```yaml
---
title: "Gates"
linkTitle: "Gates"
weight: 85
description: "..."
depth: [advanced]
---
```

Structure, copying `concepts/framework-session.md`:
`## What it is` → `###` subsections → `## Why it exists` → `## How to use` →
`## See also` → `---` → `**Next:**`.

Suggested `###` subsections under "What it is":

1. **Declared intent vs the enforced set** — `gates:` is what the task asks for;
   `active_gates` (+ `_filtered`, `_profile`, `_digest`) is what is enforced.
2. **A claim-time snapshot** — the tuple is materialized when the task is
   claimed and re-derived on every re-pick, so a profile switch cannot leave
   stale enforcement. An explicit `gates: []` is an opt-out and is never
   backfilled. A digest mismatch falls back to the raw `gates:` field until the
   next pick re-materializes.
3. **Kinds of gate** — machine, human, and procedure-backed (a gate whose work
   is a procedure the headless engine cannot run).
4. **The ledger** — `## Gate Runs` is append-only; per-gate state is *derived*
   from it and never duplicated into `status`.
5. **The registry** — `aitasks/metadata/gates.yaml` defines how each gate runs;
   the execution profile chooses which are declared.
6. **Retry budgets and the unlock DAG.**
7. **Archival and unblocking** — a task with an unmet enforced gate does not
   archive, and `also_blocks_dependents` extends that to its dependents.

### 3. Trim the `commands/gates.md` lead to a pointer

`website/content/docs/commands/gates.md:9-16` is currently a textbook concept
definition on a command-reference page. Reduce it to the `crew.md` shape:

> `ait gates` and `ait gate` operate on a task's verification gates. For the
> conceptual model (declared intent vs the enforced set, the ledger, the
> registry, and gate-guarded archival), see the
> [Gates concept page]({{< relref "/docs/concepts/gates" >}}).

Keep the two-command orientation that follows; only the definitional prose moves.

**While in that paragraph, fix line 13**: replace the hand-written
`[task file format](../../development/task-format/)` with
`[task file format]({{< relref "/docs/development/task-format" >}})`. The file is
relref-dominant (3:1) and this is the lone relative link, sitting in the exact
paragraph being edited.

### 4. Add the four remaining back-links

| File | Where | Form |
|---|---|---|
| `development/task-format.md` | gate rows 71-76 | relref |
| `tuis/board/reference.md` | `#gate-progress` (line 493) | relref |
| `workflows/crash-recovery.md` | `## See also` (line 182) | **relative** `[Gates](../../concepts/gates/)` |
| `workflows/risk-evaluation.md` | `## See Also` (line 92) | **relative** `[Gates](../../concepts/gates/)` |

The two relative ones are not a style lapse: those files are 1:8 and 0:13
relref:relative, and each already has a sibling row in the same list using the
relative form.

`skills/aitask-gate-docs-updated.md#why-it-runs-where-it-runs` is the author's
call — link it only if the page ends up covering the procedure-backed gate class.

## Post-phase (risk mitigations)

### gates_page_accuracy_review

Before committing, re-read `concepts/gates.md` against
`aidocs/gates/aitask-gate-framework.md` and the actual behaviour of
`aitask_gate.sh materialize-active`, and confirm every claim:

- the digest is three-part and a mismatch falls back to raw `gates:`;
- `MATERIALIZED:(empty)` is a real, meaningful state (fully profile-filtered);
- `active_gates*` are framework-derived and never hand-edited.

This page is the one most likely to misdescribe shipped behaviour; the review is
cheap and the parent recorded it as a required phase.

### link_relevance_triage (shared with t1687_5)

t1687_5 runs the site-wide pass. Here, just confirm each of the five back-links
lands on a page that genuinely discusses gates.

## Constraints

- Full path `/docs/concepts/gates` in every relref.
- **No mermaid** — the site has no support; a fence builds green and renders as
  a plain code block. Use box-drawing ASCII in a ```text fence if needed.
- Current-state-only prose (`aidocs/framework/documentation_conventions.md`).
- Do **not** touch `concepts/_index.md` — t1687_5 owns it.

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Check `${PIPESTATUS[0]}` or `set -o pipefail`. Confirm `#gate-progress` and the
two `## See also` anchors still exist, and that `concepts/` still has zero
hand-written relative links.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. The `risk_evaluated` gate is active and
must pass before archival.
