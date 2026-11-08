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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981_5** id=2026-11-08T13:39:22Z.343f3333ef479306670ac282 from=t1981_5 from_verified=yes at=2026-11-08T13:39:22Z base=85b688f06300e7fcdab1ada992343b7036e4aeb8 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1981_5 (relations consumption), code commit f87d4ef27. Website-doc surface added by this task:
> | - New `ait relations` verbs:
> |   - `related-work <id> --point pick|review|note [--since <ts>] [--log] [--json]`;
> |   - `notify-candidates <id> [--rev <rev> | --diff <range>] [--expect-plan <sha>] [--option <opt>] [--log] [--json]`;
> |   - `notify-outcome <id> --run <id> --to <ref> --type <type> --outcome sent|declined|not_offered [--note-id <id>]`.
> | - New profile key `relations_incomplete_action` (`ask` default / `wait` / `fallback` / `proceed`). The shipped profiles set default and fast to ask, remote to proceed.
> | - Workflow surfaces: task-workflow Step 3 Check 8 (pick-time related work), the Step 8 re-check, Step 8e relations-derived note offers, and /aitask-note reading the store first.
> | - The source of truth is aidocs/framework/task_relations.md D8 "Consumer API".
