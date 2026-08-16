---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [artifacts, task_metadata]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-16 18:41
updated_at: 2026-08-16 18:44
---

## Origin

Found during t1508 (`refresh_and_verify_live_trails`) while re-authoring
`art:trail-shadow-review-loop`. Not a defect in that task's work.

## Upstream defect

`.aitask-scripts/lib/trail_gather.py` — `plan_glob_regex()` builds a parent
member's plan pattern as:

```
(?:.*/)?p<ID>_[^/]*\.md$
```

applied with `re.search`. For a parent id that also has children with plans,
this matches the **child's** plan relpath as well as its own:

```
plan_glob_regex("1159") = (?:.*/)?p1159_[^/]*\.md$
  aiplans/p1159_shadow_review_loop_automation.md      -> True   (correct)
  aiplans/p1159/p1159_4_docs_and_integration.md       -> True   (WRONG)
```

`(?:.*/)?` happily consumes `aiplans/p1159/`, leaving `p1159_4_...md` to match
`p1159_[^/]*\.md`. The child's own regex is correctly scoped
(`(?:.*/)?p1159/p1159_4_[^/]*\.md$`) and matches only the child, so the fault is
one-directional: parent absorbs child, never the reverse.

## Why it breaks a trail permanently

The per-member plan attribution in the `drift` verb picks the **first** matching
record via `next()` over the trail's stored `generation.inputs`:

```python
stored_for_member = next(
    (p for p in plan_inputs
     if p.project == inp.project and belongs.search(p.relpath)), None)
current = plan_path_for(row, tree)
...
elif current_ref != stored_for_member.ref:
    add("plan_changed", inp.canonical, f"plan moved: ...")
```

The gatherer itself emits the child plan **first** (path sort: `/` (0x2F) sorts
before `_` (0x5F)), and `.claude/skills/aitask-trail/SKILL.md.j2` instructs the
writer to copy the INPUT lines' (kind, ref) pairs into `generation.inputs`. So a
faithfully-authored trail is reported STALE by the same tool that produced it:

```
DRIFT:plan_changed|aitasks#1159|plan moved: \
  aitasks:aiplans/p1159/p1159_4_docs_and_integration.md -> \
  aitasks:aiplans/p1159_shadow_review_loop_automation.md
```

and **no refresh can clear it**, because every refresh reproduces the same
ordering. The trail is not stale in any real sense — it is un-clearably
mis-attributed.

## Evidence

Paired `drift` runs over the **identical** document, differing only in the order
of the two `plan_file` records in `generation.inputs`:

| plan_file order | verdict | DIGEST |
|---|---|---|
| child first (what the gatherer emits) | `STALE` + `plan_changed` | `16212553ff7e716f` |
| parent first | `CURRENT` | `16212553ff7e716f` |

Same digest in both runs, which localises the fault precisely: `input_digest` is
order-independent, so this is purely the attribution pass, not membership or
content drift.

## Scope

Reproduces on any trail whose member set contains **both a parent and one of its
children, where both have plan files**. That shape was rare when trails were
first built (the shadow trail carried zero plan records two versions ago) and is
now common, since decomposing a member is the normal way work proceeds.

## Suggested fix

Either (or both):

1. **Anchor the regex.** Make `plan_glob_regex` reject a nested child path for a
   parent id — e.g. anchor with `^` against the plan-dir-relative path, or
   exclude an intervening `p<ID>/` segment. This is the real fix: the parent's
   pattern should simply not match the child's path.
2. **Make the attribution order-independent.** `next()` over stored input order
   silently encodes a preference the schema does not express; prefer the most
   specific match rather than the first one.

Fix (1) alone is sufficient and is the smaller change.

## Guard

A regression test asserting `plan_glob_regex("<parent>")` does NOT match
`aiplans/p<parent>/p<parent>_<child>_*.md`, plus an end-to-end `drift` test over
a two-plan parent+child trail that must return `CURRENT` in **both** input
orders. The second is what actually pins the user-visible behaviour — the first
alone would pass a fix that only reordered the inputs.

## Current workaround (remove when fixed)

`art:trail-shadow-review-loop` v5 deliberately emits its parent plan record
before the child's, and records the reason as observation
`obs-plan-attribution-order` so a later refresh does not "tidy" the order back
and re-break the document. Any other trail hitting this shape will need the same
workaround until this lands.
