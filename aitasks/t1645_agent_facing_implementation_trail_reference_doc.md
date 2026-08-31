---
priority: medium
effort: medium
depends: [1644, 1647]
issue_type: documentation
status: Ready
labels: [documentation, artifacts, planning, install]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-08-31 10:12
updated_at: 2026-08-31 11:11
---

## Problem

An interactive code agent working directly in a project (outside the `ait board`
By-Trail view and outside `/aitask-trail`) has **no document to read** that
explains how implementation trails are stored, discovered, recovered, or
manipulated. To do anything with a trail today it must reverse-engineer the
skill prose (`.claude/skills/aitask-trail/SKILL.md`) or the implementation
(`lib/trail_schema.py`, `lib/trail_gather.py`, `board/aitask_board.py`).

Exploration established the gap concretely:

- **No agent-facing trail doc exists.** The only trail documentation is
  `aidocs/implementation_trail_design.md` (748-line design RFC),
  `aidocs/implementation_trail.schema.json`, and three examples under
  `aidocs/implementation_trail_examples/`. These are design material — an RFC
  organized around problem statement, alternatives considered, and
  decomposition — not a working reference.
- **`aidocs/` does not ship to installed projects.** Stated at
  `.aitask-scripts/lib/trail_schema.py:8` ("aidocs/ does not ship to installed
  projects -- same reasoning that made gates_reference.yaml canonical under
  .aitask-scripts/, t1147"). Only the byte-identical runtime copy
  `.aitask-scripts/lib/implementation_trail.schema.json` reaches a user
  project, and a raw JSON Schema is not a usage guide.
- **`CLAUDE.md` has zero trail/artifact coverage.** It carries 29 `aidocs/`
  pointers; none mentions trails or artifacts.
- **The installed agent-instruction seed has no trail content.**
  `seed/aitasks_agent_instructions.seed.md` (97 lines) documents frontmatter
  fields, task hierarchy, `./ait git`, commit format, folded-task semantics and
  manual-verification tasks — nothing about trails or artifacts. This is the
  Layer-1 file that `assemble_aitasks_instructions()` composes and
  `insert_aitasks_instructions()` writes into a project's CLAUDE.md / AGENTS.md
  between the `>>>aitasks` / `<<<aitasks` markers
  (`.aitask-scripts/aitask_setup.sh:1280-1340`).

The surface an agent needs already exists — it is just undocumented outside the
skill:

- Trails are task-owned artifacts of `--kind implementation_trail` with handle
  `art:<trail_id>` where `trail_id` matches `^trail-[a-z0-9][a-z0-9_-]{2,63}$`
  (`.claude/skills/aitask-trail/SKILL.md.j2:478`).
- Recovery is `ait artifact get <handle> [--out <path>] [--version sha256:…]`,
  with `ait artifact ls [<task>]` and `ait artifact versions <handle>`.
- **Discovery is frontmatter-driven, not manifest-driven** — the manifest
  stores no kind (RFC par.5), so trails are found by scanning `artifacts:`
  entries with `kind == implementation_trail` across active *and* archived task
  frontmatter (`.aitask-scripts/board/aitask_board.py:1187-1210`). An agent that
  assumes `ait artifact ls` alone enumerates trails gets the wrong answer.
- Helper verbs: `aitask_trail_gather.sh snapshot|drift` (deterministic
  gatherer + drift checker; `drift --trail` accepts a path *or* an
  `art:` handle) and `aitask_trail_depth.sh resolve|validate` (mode/depth
  resolver and depth-aware schema validation).
- Schema is `1.1.0`, `additionalProperties: false`, required keys
  `schema_version, trail_id, title, owner, scope, generation, freshness,
  narrative, waves, evidence`.

User-facing docs cover only the board By-Trail view
(`website/content/docs/tuis/board/reference.md`, `how-to.md`) plus a release
blog post — nothing on the JSON format or the CLI recovery path.

## Goal

Give a direct-working code agent a single installable document that answers
"how do I find, read, validate and manipulate an implementation trail?" without
reading trail source code or the trail skill.

## The surface is moving — track t1644 and t1647

This doc must describe the trail subsystem **as it will be once the in-flight
expansion lands**, not as it is today. Two sibling tasks (same `anchor: 1210`
topic) are actively changing exactly the surface this reference documents, and
`depends: [1644, 1647]` is set so this task is written against their settled
result rather than a snapshot that is stale on arrival:

- **t1644 — `trail_interactive_run_summary_and_website_docs`** (status:
  `Implementing`). Enriches the `/aitask-trail` interactive run summary beyond
  today's two lines (depth + `narrative.overview`, resolved exactly as the
  board's `trail_summary_text()`), adding wave/phase breakdown and per-entry
  order/classification/confidence; and adds the missing
  `website/content/docs/skills/aitask-trail.md` page plus its
  `docs/skills/_index.md` row. **Impact here:** the direct-invocation path gets
  a real user-facing page, so this reference must link to it rather than
  restate it, and must describe the *enriched* run-summary output. Also settle
  the division of labour explicitly: t1644's page is user-facing "how do I run
  the skill", this doc is agent-facing "how do I read and manipulate the data".
- **t1647 — `merge_trails_skill_shared_helpers_board_command_docs`** (status:
  `Ready`, effort high, decomposed at planning). Adds trail-to-trail **merge
  (fold)**: a dedicated `/aitask-merge-trails` skill, a `merge-trails` codeagent
  operation, a board By-Trail command, and — most relevant here — **shared
  library helpers that own discovery, validation, merge planning and artifact
  writes**, so the skill, the board and `/aitask-trail` all reuse the same
  seams. **Impact here:** those shared helpers become the canonical seams an
  agent should call, superseding any recipe this doc would otherwise write
  against `aitask_trail_gather.sh` / `ait artifact` directly. Discovery in
  particular is slated to move into a shared helper — do not document the
  frontmatter scan as something an agent should re-implement if t1647 ships a
  helper for it. Merge also introduces a **retired/folded trail** state that
  the read-only vs mutating boundary section must cover.

**Concrete obligations for planning:**

1. Re-read both task files (and their plans / archived plans, if closed by then)
   before authoring, and document the **post-t1644/t1647 seams**, not the
   current ones.
2. Cite the shared helpers t1647 lands as the preferred entry points; keep the
   lower-level `ait artifact` recipes as the fallback/explanatory layer.
3. Cross-link t1644's `docs/skills/aitask-trail.md` from this reference (and
   consider a reciprocal pointer, per the bidirectional-link convention).
4. If either task's settled design changes a fact asserted in the Problem
   section above (e.g. discovery mechanics, the two-line run summary), correct
   the fact rather than documenting both variants.

## Scope

1. **Author the reference.** Place it where it *ships* — under
   `.aitask-scripts/` (mirroring the `gates_reference.yaml` / t1147 precedent
   cited by `trail_schema.py`), not under `aidocs/`. Decide the exact path and
   whether an `aidocs/` pointer stub should remain for framework developers.
   Content to cover:
   - The artifact storage model: task-owned handles, `kind:
     implementation_trail`, `art:trail-<slug>` naming, versioning, backends.
   - **Discovery**: the frontmatter-driven rule and why `ait artifact ls` is not
     the enumeration seam; include the active + archived scan.
   - **Recovery recipes**: concrete `ait artifact ls|get|versions` invocations,
     including fetching a specific version.
   - **The JSON document shape**: the required keys, what `waves`,
     `narrative`, `evidence`, `freshness` and `generation` mean, and a
     short worked example (the existing
     `aidocs/implementation_trail_examples/*.json` are candidate sources —
     decide whether an example ships alongside the doc).
   - **Helper CLIs**: `aitask_trail_gather.sh` (snapshot/drift, including the
     `ERROR:artifact_unresolved:<handle>` line-protocol outcome) and
     `aitask_trail_depth.sh` (resolve/validate) — plus whatever shared
     discovery / validation / merge helpers **t1647** lands, which take
     precedence as the documented entry points.
   - **Trail merge**, once t1647 lands: what `/aitask-merge-trails` does to the
     two handles, and what state a folded/retired trail is left in.
   - **Read-only vs mutating boundary**: what an agent may do directly versus
     what must go through `/aitask-trail` (trails are refreshed, not hand-edited
     — state this explicitly so the doc does not invite hand-editing a validated
     artifact).
2. **Link it from `CLAUDE.md`** in the existing `> **Read `aidocs/...`**` pointer
   style, with a trigger condition ("when reading, refreshing, or programmatically
   consuming an implementation trail").
3. **Link it from `seed/aitasks_agent_instructions.seed.md`** so installed
   projects get the pointer inside their `>>>aitasks` / `<<<aitasks` block. Keep
   the seed addition short — a pointer plus the two or three facts an agent
   cannot guess (kind, handle shape, frontmatter-driven discovery), not a copy
   of the reference.
4. **Verify the installed result**: confirm the doc is present and the pointer
   resolves in a project installed via `ait setup` (the seed is composed from
   `aitasks/metadata/…seed.md` with a `seed/` fallback — both paths must work).

## Notes / open questions for planning

- Confirm the shipping boundary: does the whole of `.aitask-scripts/` reach an
  installed project, and is there an existing convention for prose docs living
  there (vs. only code + data files)? If not, decide the convention here.
- Check overlap with `aidocs/implementation_trail_design.md` — the reference
  should link to the RFC for rationale rather than restate it, but must be
  self-sufficient in a project where the RFC is absent.
- Any facts duplicated from the schema (required keys, `trail_id` pattern) risk
  drift; prefer deriving/pointing at
  `.aitask-scripts/lib/implementation_trail.schema.json`, or add a drift guard,
  rather than restating values by hand.
- Website docs are out of scope for this task: **t1644** already owns the
  user-facing `website/content/docs/skills/aitask-trail.md` page. Link to it
  from here instead of duplicating it, and raise a separate docs task only if a
  genuinely different user-facing gap appears.
- Both dependencies must be `Done` before authoring — the reference is written
  against their settled seams (see "The surface is moving" above).
