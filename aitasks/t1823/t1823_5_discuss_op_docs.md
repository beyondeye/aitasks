---
priority: medium
effort: low
depends: [t1823_4]
issue_type: documentation
status: Implementing
labels: [ait_brainstorm, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1823
implemented_with: claudecode/opus5
created_at: 2026-09-17 09:51
updated_at: 2026-09-18 13:03
---

## Context

Parent t1823 added a **Discuss** node operation to the `ait brainstorm` TUI: from
the Operations dialog (`A`) on the cursor node or the space-marked set, it opens
the agent dialog and launches an interactive, advisory-only (read-only) code agent
running the `aitask-brainstorm-discuss` skill over those nodes' proposals
(siblings t1823_1..4). Per `aidocs/framework/planning_conventions.md`, docs for a
user-visible TUI feature are a first-class sibling created before the
manual-verification sibling. (The `codeagent.md` operations-table row already
landed with t1823_3 because a test pins it.)

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.
**Read first:** `aidocs/framework/documentation_conventions.md` — current-state-only
prose (no version history), genericize any passage naming the supported coding
agents.

## Key files to modify

- `website/content/docs/tuis/brainstorm/reference.md` — "Operations and agents"
  table (~:132-146): add Discuss, making clear it is NOT a crew agent / wizard op
  and produces no node; "Operations dialog and wizard" key table (~:59-72).
- `website/content/docs/tuis/brainstorm/how-to.md` — a short "Discuss proposals
  with an agent" how-to next to the `A → Compare` / `A → Synthesize` entries (~:45):
  one node vs marked set, the agent dialog, what the agent offers (compare simple /
  detailed, explain, Q&A, flaw & risk check, how a proposal evolved), and that it
  never edits the session.
- NEW `website/content/docs/skills/aitask-brainstorm-discuss.md`, linked from
  `website/content/docs/skills/_index.md` (`tests/test_website_doc_lists.sh` Test 2
  requires every `skills/aitask-*` page to be linked from the index).
- `website/content/docs/tuis/_index.md` only if its brainstorm blurb enumerates operations.

## Implementation notes

- Read the landed siblings' archived plans (`aiplans/archived/p1823/`) for the
  final shortcodes, labels and helper grammar — document what shipped, not the plan.
- Prefer `{{< relref "/docs/..." >}}` over hand-written relative paths.
- Do not mention `diffviewer`.

## Verification

- `cd website && python3 check_links.py --build` (mandatory after editing `website/content/`)
- `hugo build --gc --minify` in `website/`
- `bash tests/test_website_doc_lists.sh`
- Offer `python3 check_link_relevance.py` (report only, not a gate).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-18T10:03:01Z status=pass attempt=1 type=human
