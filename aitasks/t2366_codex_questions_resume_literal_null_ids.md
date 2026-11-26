---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codexcli, codeagent, codex_questions]
anchor: 2281
followup_kind: review_finding
created_at: 2026-11-26 12:08
updated_at: 2026-11-26 12:08
---

## Goal

Keep a literal question or page id that looks like JSON (e.g. `null`) intact at the
`aitask_question_resume` tool boundary of the Codex attended-questions MCP server.

## Problem (found in t2329 review, confirmed over STDIO)

`aitask_question_resume` in `.aitask-scripts/aitask_questions/server.py` declares
`question_id: str | None = None` and `page_id: str | None = None`. The MCP SDK
(2.3.0) pre-parses JSON-looking strings for union annotations, so a question whose
id is the string `null` arrives as `None`. Its chat answer is then rejected with a
tool error ("supply question_id and prompt_answer together"). This happens whether
`allow_other` is set or not. The handler already keeps `prompt_answer` as a plain
`str` for the same reason (see the comment above the `question_id is None` check).

t2329 fixed this for the new `back_to_choices` parameter by making it a plain
`str` with `""` meaning absent, covered by
`test_back_to_choices_keeps_a_json_looking_question_id` in
`tests/test_aitask_questions_mcp.py`.

## Scope

- Make `question_id`, and `page_id` if it has the same exposure, plain `str`
  parameters with an explicit "absent" value. Keep the rule that the presence of
  `question_id` signals an answer, and keep the existing error for
  `prompt_answer` without `question_id`.
- Check the other tools (`aitask_question_status`, `aitask_question_cancel`, …)
  for nullable string parameters with the same problem.
- Process tests: resume with `question_id: "null"` (allow_other on and off)
  records the answer; a multi page id that looks like JSON reaches the store
  intact.
- Update the docstring and `aidocs/codeagents/codex_questions.md` only if
  something user-visible changes.
