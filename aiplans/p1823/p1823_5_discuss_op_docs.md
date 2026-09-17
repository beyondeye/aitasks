---
Task: t1823_5_discuss_op_docs.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_4_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
---

# t1823_5 — Website docs for the brainstorm Discuss operation

## Context

Document the shipped Discuss op and its skill. Read the archived sibling plans
(`aiplans/archived/p1823/`) first and document **what shipped** (final label,
shortcodes, helper behaviour), not the plans. Follow
`aidocs/framework/documentation_conventions.md`: current-state-only prose, generic
wording for the supported coding agents, no `diffviewer`.

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Steps

1. `website/content/docs/tuis/brainstorm/reference.md`: add Discuss to the
   "Operations and agents" table with a note that it launches an interactive
   advisory agent, is not a crew agent / wizard op, and creates no node; update the
   "Operations dialog and wizard" section.
2. `website/content/docs/tuis/brainstorm/how-to.md`: "Discuss proposals with an
   agent" — cursor node vs marked set, the agent dialog (agent/model, window vs
   split, terminal), the capabilities and their `>` shortcodes, the read-only guarantee.
3. NEW `website/content/docs/skills/aitask-brainstorm-discuss.md` (usage, arguments,
   capabilities, advisory-only contract, profile key `brainstorm-discuss`); link it
   from `website/content/docs/skills/_index.md`.
4. `website/content/docs/tuis/_index.md` only if its brainstorm blurb enumerates ops.
5. Use `{{< relref "/docs/..." >}}` for internal links.

## Verification

- `cd website && python3 check_links.py --build` passes
- `hugo build --gc --minify` in `website/` succeeds
- `bash tests/test_website_doc_lists.sh` passes (skills index links the new page)
- Offer `python3 check_link_relevance.py` (report only)

## Post-implementation

Step 9 of the task workflow.
