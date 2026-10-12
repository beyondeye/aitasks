---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_fold, bash_scripts, gates]
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
created_at: 2026-10-12 22:40
updated_at: 2026-10-12 22:41
---

## Origin
Found downstream in the thinking_app repo (its t295, Step 8b review, 2026-10-12), which consumes this framework. The defect is in the framework, so it is tracked here.

## Upstream defect
- `.aitask-scripts/aitask_fold_content.sh:111` — folded bodies are emitted verbatim (`extract_body "$f"`), so a folded task's `## Gate Runs` and `## Inbox` blocks land in the primary's body, where another task's gate history can parse as the primary's ledger and its notes appear in a second inbox section.
- `.aitask-scripts/aitask_fold_content.sh:82` — `--primary-stdin` emits stdin verbatim (`primary_body=$(cat)`), without the frontmatter stripping the file path gets through `extract_body` (line 84). Piping the primary task file (the natural way to avoid reading and writing the same file) duplicates its frontmatter into the body.

## Diagnostic context
- A downstream fold of two tasks into one primary produced a merged body containing:
  - one folded task's `## Gate Runs` section, with a `plan_approved` pass and a `plan_approved` fail;
  - two extra `## Inbox` sections, with `✉ note` blocks addressed to the folded tasks.
- Applied unchanged via `aitask_update.sh --desc-file -`, the primary would have carried two ledgers. The gate parser is section-based (`gate_ledger.py`, `SECTION_HEADER = "## Gate Runs"`), so the folded task's history could be read as the primary's. The downstream session rewrote the folded copies as plain reference prose by hand.
- Separately, piping the whole primary task file to `--primary-stdin` produced a second frontmatter block inside the body, which was removed by hand.

## Suggested fix
- In `aitask_fold_content.sh`, demote each folded body's `## Gate Runs` and `## Inbox` sections, for example to `### t<N> gate history (reference only)` / `### Notes t<N> received`, with the `> **✅ gate:` / `> **✉ note:` markers rewritten so neither parser picks them up.
- Run stdin through `extract_body` when it starts with a frontmatter block.
- Add tests for both cases: a folded task with a ledger and an inbox, and `--primary-stdin` fed a whole task file.
