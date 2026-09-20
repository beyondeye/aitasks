---
priority: medium
effort: medium
depends: [t1687_3]
issue_type: documentation
status: Ready
labels: [documentation, website, concepts]
gates: [risk_evaluated]
anchor: 1687
created_at: 2026-09-20 12:02
updated_at: 2026-09-20 12:02
---

## Context

Part of t1687 (Concepts docs gap sweep). Two advisory-by-construction
primitives: the trail (an advisory *artifact*) and the shadow (an advisory
*agent*). Neither has a concept page.

These are the **two highest-duplication pages in the whole sweep**. The user
explicitly chose "write both, strictly complementary" at t1687 planning after
being shown the overlap. Honour the no-restate lists below — without them this
produces exactly the duplicate-index outcome the parent task warns against.

## Key files to modify

- **NEW** `website/content/docs/concepts/implementation-trails.md` — weight
  **105**, group *Lifecycle and infrastructure*.
- **NEW** `website/content/docs/concepts/shadow-agent.md` — weight **125**,
  group *Workflow primitives*.

Back-links:

| Target | Insertion point | Form |
|---|---|---|
| `website/content/docs/workflows/implementation-trails.md` | `#what-a-trail-never-does` (line 125) | relref (1:2 mixed, but its only cross-section link is a relref to `/docs/concepts/...`) |
| `website/content/docs/skills/aitask-trail.md` | `## Related` (line 89) | relref (6:1) |
| `website/content/docs/tuis/board/reference.md` | `#by-trail` (line 249) | relref (12:1) |
| `website/content/docs/concepts/topic-anchoring.md` | `## See also` (line 130) | relref (6:0) |
| `website/content/docs/workflows/shadow-agent.md` | lead paragraph, lines 9-11 | **relative** — `(../../concepts/shadow-agent/)` (1:9) |
| `website/content/docs/tuis/minimonitor/_index.md` | `#launching-a-shadow-agent` (line 77) | relref (9:2) |
| `website/content/docs/tuis/minimonitor/how-to.md` | line 187, beside the existing workflow link | relref (23:0) |
| `website/content/docs/tuis/monitor/how-to.md` | line 184, beside the existing workflow link | relref (15:1) |

## Do NOT link

- `website/content/docs/tuis/monitor/reference.md` — shadow appears only as
  keybinding rows and SHADOW-*zone* mechanics; it explains the preview column,
  never what a shadow is.
- `website/content/docs/tuis/monitor/_index.md` — shadow named only as an
  excluded companion pane in the pane-classification rules.
- There is **no** `website/content/docs/skills/aitask-shadow.md`. Do not invent
  a link to it.
- `website/content/docs/tuis/minimonitor/` has only `_index.md` and `how-to.md`
  — there is **no** `reference.md` under minimonitor.

## Content sources

`aidocs/implementation_trail_design.md`,
`aidocs/implementation_trail.schema.json`,
`aidocs/framework/shadow_agent.md`.

## Complementary angle (MANDATORY)

**`concepts/implementation-trails.md` angle:** why a sequencing
*recommendation* is stored as a **versioned artifact** rather than re-derived
each time.

Must NOT restate `workflows/implementation-trails.md:9-47` (what a trail is,
waves, classifications, observations, exclusions), `:90-104` (freshness/drift),
`:125-134` (advisory by construction — already fully covered there).

The artifact substrate itself (`art:<id>` handles, manifests, immutable
versions, backends) belongs to **t1231_3's `concepts/artifacts.md`**, which does
not exist yet. **Link to `development/task-format.md#nested-fields-artifacts-and-attachments`
for the frontmatter shape; do NOT describe the artifact store**, and do not
create or pre-link a `concepts/artifacts.md`.

**`concepts/shadow-agent.md` angle:** the **advisory-only contract** and the
**pane-binding identity**. `@aitask_shadow_target` has **zero** website presence
today (it exists only in `CLAUDE.md:376` and tests), so the binding mechanism is
entirely new prose with nothing to reciprocate.

Must NOT restate `workflows/shadow-agent.md:9-11` (what a shadow is),
`:28-38` (what happens once running), `:186-188` (advisory only).

## Hard scope limit — no trail merging

`merged_from` / merged trails have **not shipped** to the website and
**t1647_6 owns them**. Write **no** merge line on the trails page. t1647_6 adds
it once its feature lands.

## Constraints

- **Slug collision:** `/docs/concepts/implementation-trails` and
  `/docs/concepts/shadow-agent` both collide with same-named workflow pages.
  **Always use the full `/docs/...` path** — a bare relref is ambiguous and
  FAILS the build.
- **No mermaid** on this site.
- Current-state-only prose per `aidocs/framework/documentation_conventions.md`.
- Do **not** add `concepts/_index.md` bullets here — t1687_5 owns that file.
- `concepts/topic-anchoring.md` already links the trails *workflow* page at
  lines 21 and 136; add the concept link beside it rather than replacing it
  silently.

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Use `set -o pipefail` or check `${PIPESTATUS[0]}`.
