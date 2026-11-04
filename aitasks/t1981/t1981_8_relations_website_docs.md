---
priority: medium
effort: low
depends: [t1981_4, t1981_5, t1981_6, t1981_7]
issue_type: documentation
status: Ready
labels: [task_relations, documentation]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-04 15:39
---

## Context

Child of t1981. User-facing website documentation for the task-relations and
obsolescence features, written from what t1981_4–t1981_7 **actually shipped**,
not from the design doc alone. Design anchor:
`aidocs/framework/task_relations.md`.

## Scope

1. **CLI reference** for `ait relations` (every verb, including `enable` /
   `disable`, `analyze`, `analysis-state`, `notify-candidates`, `sweep`,
   `usage`, `status` / `flush` / `gc`) and for `ait obsolete`.
2. **A concept page** under `website/content/docs/concepts/` covering:
   - what a relation is, and the vocabulary;
   - that analysis is **off by default**, what enabling it costs (headless agent
     runs), and how to enable it;
   - what "disabled", "not analysed yet" and "analysed, 0 relations" mean;
   - the hybrid model: pull at pick time and at the target's Step 8, push only
     for in-flight or plan-holding targets with confirmed impact.
3. **Workflow pages**: the related-work check, the Step 8e flow (including the
   incomplete-analysis choices), `/aitask-note` store-first.
4. **The TUI page** under `website/content/docs/tuis/`, and the `tuis/_index.md`
   list.
5. **`archived_reason: obsolete`** in `development/task-format.md`, if t1981_6 did
   not already add it.

## Rules

- `aidocs/framework/documentation_conventions.md`: current state only;
  genericize agent names in blurbs.
- Prefer `{{< relref >}}` links.
- **Run `python3 check_links.py --build` in `website/`** after editing.
  Offer `check_link_relevance.py` for new links.

## Implementation plan

See `aiplans/p1981/p1981_8_relations_website_docs.md`.

## Verification

- `hugo build --gc --minify` succeeds.
- `check_links.py --build` is clean.
- Every documented verb and flag exists in the shipped scripts. Grep each one.
