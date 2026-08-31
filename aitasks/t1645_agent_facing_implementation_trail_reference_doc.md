---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [documentation, artifacts, planning, install]
gates: [risk_evaluated]
created_at: 2026-08-31 10:12
updated_at: 2026-08-31 10:12
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
     `aitask_trail_depth.sh` (resolve/validate).
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
- Website docs are out of scope for this task unless planning decides the
  user-facing side needs a companion page; if so, spawn it as a separate docs
  task per the decomposition convention.
