---
priority: high
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [documentation, website, concepts]
gates: [risk_evaluated]
anchor: 1687
created_at: 2026-09-20 12:01
updated_at: 2026-09-20 12:01
---

## Context

Part of t1687 (Concepts docs gap sweep). `website/content/docs/concepts/` has no
Gates page, which the re-verification sweep confirmed is the section's single
largest omission: gates are documented in `commands/gates.md`,
`skills/aitask-run-gates.md`, `development/task-format.md` and
`tuis/board/reference.md`, but nowhere as a concept.

**Ownership decision made at t1687 planning (2026-09-20):** t635_18 also plans a
Gates concept page with a fuller outline, but it is blocked behind t635_37. The
user decided **t1687 writes this page**; t635_18 later extends it rather than
creating it. A note recording this was sent to t635_18 before this task was
created.

## Key files to modify

- **NEW** `website/content/docs/concepts/gates.md` — weight **85**,
  group *Workflow primitives*, `depth: [advanced]`.
- `website/content/docs/commands/gates.md` — trim the lead definition
  (lines 9-16) to a pointer; **also fix line 13**, a hand-written
  `[task file format](../../development/task-format/)` in an otherwise
  relref-dominant file (3 relref : 1 relative).
- `website/content/docs/development/task-format.md` — gate rows 71-76 under
  `#frontmatter-fields`.
- `website/content/docs/tuis/board/reference.md` — `#gate-progress` (line 493).
- `website/content/docs/workflows/crash-recovery.md` — `## See also` (line 182).
- `website/content/docs/workflows/risk-evaluation.md` — `## See Also` (line 92).

## Link form (measured; per-FILE, not per-directory)

| File | relref : relative | Use |
|---|---|---|
| `commands/gates.md` | 3 : 1 | relref |
| `development/task-format.md` | 10 : 1 | relref |
| `tuis/board/reference.md` | 12 : 1 | relref |
| `workflows/crash-recovery.md` | 1 : 8 | **relative** — `[Gates](../../concepts/gates/)` |
| `workflows/risk-evaluation.md` | 0 : 13 | **relative** — `[Gates](../../concepts/gates/)` |

## Reference files for patterns

- `website/content/docs/concepts/framework-session.md` — the canonical deep-page
  shape: frontmatter key order `title`, `linkTitle`, `weight`, `description`,
  `depth`; `## What it is` → `###` subsections → `## Why it exists` →
  `## How to use` → `## See also` → `---` → `**Next:**`.
- `website/content/docs/commands/crew.md:9-12` — the canonical back-link
  sentence: "`ait crew` manages **agentcrews** — ... For the conceptual model
  (...), see the [Agentcrews concept page]({{< relref ... >}})."

## Content sources

`aidocs/gates/aitask-gate-framework.md`, `gate-guarded-archival.md`,
`dependency-unblock-semantics.md`, `ledger-driven-reentry.md`,
`risk-evaluation-gate-seam.md`; `.aitask-scripts/aitask_gate.sh`.

## Complementary angle (MANDATORY — do not restate)

The page's angle: **declared intent vs the framework-derived enforced set, and
why enforcement is a claim-time snapshot.**

Must NOT restate:
- `commands/gates.md:9-16` — the existing lead definition (trim it to a pointer
  instead).
- `tuis/board/reference.md:462-545` — ~80 lines of phases / gate progress /
  honest degradation, the most detailed declared-vs-enforced prose on the site.

Cover: `gates:` as intent vs `active_gates` + `_filtered` / `_profile` /
`_digest` as the enforced tuple; materialization at claim time and re-derivation
on every re-pick; the digest-mismatch fallback to raw `gates:`; machine vs human
vs procedure-backed gates; the append-only `## Gate Runs` ledger and derived
state; the registry at `aitasks/metadata/gates.yaml`; retry budgets and the
unlock DAG; gate-guarded archival and dependency unblocking.

## Constraints

- **Slug collision:** always use the full path `/docs/concepts/gates`. Bare
  relrefs are ambiguous where a workflow page shares a slug.
- **No mermaid** anywhere on this site — a mermaid fence renders as a plain code
  block and the build stays green. Use box-drawing ASCII in a ```text fence
  (see `concepts/framework-session.md:50-64`).
- Current-state-only prose per `aidocs/framework/documentation_conventions.md`.
- Do **not** add the `_index.md` bullet here — t1687_5 owns that file.

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Use `set -o pipefail` or check `${PIPESTATUS[0]}` — piping discards the status.
Confirm every anchor named above still exists, and that
`website/content/docs/concepts/` still contains zero hand-written relative links.
