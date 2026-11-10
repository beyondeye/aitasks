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

> **✉ note:t2254** id=2026-11-09T20:53:40Z.61867fd78f8d891ebf6e60be from=t2254 from_verified=yes at=2026-11-09T20:53:40Z base=b90a154a7750a7f1890aa2a843175dd336ac2901 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2254 (code commit b90a154a7 on main), relevant to item 5 and to the `ait obsolete` docs.
> | 
> | - website/content/docs/development/task-format.md, `archived_reason` row: t2254 already edited it. It now says the reason is written on the task the flag names, and that a parent auto-archived with its last child takes it only when none of its children was completed. Item 5's "if t1981_6 did not add it" condition is also already met: `obsolete` is listed in that row.
> | - website/content/docs/concepts/parent-child.md: t2254 added one clause with the same rule.
> | - Behaviour that `ait obsolete review` docs should describe, not the pre-t2254 inheritance. Archiving a parent's LAST pending child with `aitask_archive.sh --obsolete` (or `--superseded`) auto-archives the parent:
> |   - as completed work, with no `archived_reason` and firing `obsolescence landed`, when any sibling landed, whether its archived record is loose or bundled;
> |   - with the run's reason only when every sibling record was read, none landed, and the view stayed stable across the scan;
> |   - as completed work, with a stderr warning, when the evidence was unreadable or kept changing.
> | - The authoritative wording is in aidocs/framework/task_relations.md under "The landed trigger".
> | 
> | These are tree-relative claims as of b90a154a7; check them against the current files before relying on them.

> **✉ note:t1981_11** id=2026-11-10T10:46:35Z.5b1616e19b79802c796b1761 from=t1981_11 at=2026-11-10T10:46:35Z base=e16e440e4036bf3929b3d0a60a54f81be2f11003 base_branch=main dirty=yes host=omg16
>
> | Advisory: the obsolescence concept and workflow docs now have their own task, t1981_11 (`obsolescence_website_docs`, created 2026-11-10).
> | 
> | t1981_11 owns:
> | - a concept page, planned at `website/content/docs/concepts/task-obsolescence.md`, covering bands and dispositions, signal versus context evidence, unknown evidence and dismissals;
> | - a workflow page, planned at `website/content/docs/workflows/obsolete-tasks.md`, covering `ls` / `show` / `evidence`, the `review` walk, the landed trigger, `sweep`, the pick-time band and `unblock`;
> | - the parent-archiving behaviour t2254 shipped.
> | 
> | t1981_8 keeps the `ait relations` / `ait obsolete` CLI reference, the relations concept page, the relations workflow pages and the TUI page.
> | 
> | To avoid duplicating material: link to t1981_11's pages from the `ait obsolete` reference and the relations concept page, rather than explaining obsolescence there. If t1981_8 lands first, t1981_11 may instead add a section to your relations concept page. Its task body says to coordinate either way. The page paths above are t1981_11's plan, not yet files.
