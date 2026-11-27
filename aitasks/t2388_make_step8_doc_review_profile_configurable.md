---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [task_workflow, execution_profiles, skills, doc_review]
gates: [risk_evaluated]
created_at: 2026-11-27 14:37
updated_at: 2026-11-27 14:37
---

## Goal

Make the task-workflow **Step 8 documentation review** (added by t2369) switchable
through an execution-profile key. The shipped `fast` profile turns it **on**, and
it stays on by default.

Proposed key: `doc_review` (bool).
- **Missing key = on.** `default` and `remote` keep today's behaviour without any
  edit, and so does every user profile.
- `fast` ships `doc_review: true` explicitly, in both
  `aitasks/metadata/profiles/fast.yaml` and `seed/profiles/fast.yaml`.
- `doc_review: false` renders the whole review away from that profile's
  task-workflow variant.

## Background: this reverses a t2369 decision

t2369 made the review profile-invariant on purpose.
`tests/test_skill_render_task_workflow.sh:142-149` says the procedure "carries no
profile conditional and ships no knob". The stated reason: "whether the
documentation about to be committed is the revision that was reviewed must not
depend on how chatty a profile is". The user has now decided it should be
configurable. Rewrite that comment to record the new decision and its reason. Do
not just delete it.

## Sites in `.claude/skills/task-workflow/SKILL.md` (a Jinja template)

All of these must be gated together, so that no rendered variant keeps half the
mechanism:

1. **Review round** bullet ("Documentation review (every pass through Step 8)", ~line 749).
2. **Approval-prompt summary block**: the "put it at the start of the question text"
   clause on the Step 8 `AskUserQuestion` (~line 758). Keep the base question unchanged.
3. **Documentation commit check**: the first action of "Commit changes" (~line 766).
4. **Final commit guard** around the code commit (~lines 791-824). With it off,
   the code commit must return to the plain form that came before t2369
   (`git add -- <untracked>` + `git commit -F - -- <paths>` + `git show --stat <sha>`).
   **A guard with no review evidence would block every commit.** The
   "commit happened only when … GUARD:clean" paragraph and the
   "Plan file commit — only after the code commit … never after a failed guard"
   wording change with it.
5. **Plan consolidation** `- **Documentation review:**` line (~line 778).
6. **"Need more changes"** documentation-feedback rule (~line 845) and the
   `Concern resolutions:` line in the Post-Review Changes entry (~line 856).
7. The sentence about the `docs_updated` gate dispatch at ~line 742 ("That skip is
   why the documentation review below does not depend on any gate…"). When the
   review is off, it must not refer to a review that is not rendered.

`doc-review.md` itself has no Jinja. Decide whether it is still rendered/shipped
when the key is off (it would be unreferenced) or left as an inert file, and keep
Test 0's inventory consistent with that choice.

**Codex route:** `codex_tool_mapping.md` and `doc-review.md` `## Final commit guard`
item 5 put the same guard in front of `aitask_gate.sh commit-approved`. With the
review off, that route must also commit without the guard. Check
`.agents/skills/codex_tool_mapping.md` for text that assumes the guard always runs.

**Out of scope / unchanged:** the `docs_updated` gate and its skill
`aitask-gate-docs-updated` (a separate, gate-driven mechanism that shares the
review record), `aitask_doc_review.sh` / `lib/doc_review_record.py`, and
`/aitask-docs-review`.

## Wiring a new profile key (checklist)

- `.claude/skills/task-workflow/profiles.md`: Profile Schema table row (key, type,
  values, missing = on, Step 8) plus a short section on what turns off and why
  someone would do it.
- `.aitask-scripts/lib/profile_editor.py`: `PROFILE_SCHEMA` entry (`bool`), the
  description/help dict and the group list (where `post_plan_action` etc. live,
  ~lines 69/192/434). **⚠ `profile_editor.py` and `settings/settings_app.py` had
  uncommitted edits from another session when this task was created.** Check them
  before editing and do not commit someone else's hunks.
- Settings TUI tests that enumerate schema keys, if any.
- `website/content/docs/skills/aitask-pick/execution-profiles.md` (key table), and
  `documentation-review.md` (t2369's page) should say the review can be turned off
  per profile. Run `website/check_links.py --build` afterwards.
- The profile `.yaml` files above.
- Goldens: `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` (plus
  `doc-review-*` if its render inventory changes). Regenerate them in the same
  commit, following `aidocs/framework/skill_authoring_conventions.md`.
- `tests/test_doc_review_step8_contract.sh` pins the guarded block in the **fast**
  golden (lines ~24, 48, 244-261). It stays valid because fast ships `true`. Add
  a case that renders a `doc_review: false` profile and asserts **all** sites are
  gone and the plain commit form is present (no `aitask_doc_review.sh guard`, no
  `DOC_GUARD_FAILED`). Also add a missing-key case that asserts the review is
  present.
- `tests/test_skill_render_task_workflow.sh`: the rewritten comment, plus any
  assertion of profile invariance.
- Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- Rendered copies of the remote variant: `.claude/skills/task-workflow-remote-/`,
  `.agents/skills/task-workflow-remote-codex-/`, `.opencode/skills/task-workflow-remote-/`.
  These should not change because remote leaves the key out, but confirm it.
- Per CLAUDE.md: Claude Code first. Suggest follow-up tasks for the Codex/OpenCode
  ports if any surface differs.

## Acceptance

- `fast` / `default` / `remote` renders are byte-identical to today's goldens,
  apart from intentional prose changes.
- A `doc_review: false` profile renders a Step 8 with no doc-review reference
  and a plain, unguarded code commit.
- The settings TUI shows and edits the key.
- Docs and profiles.md describe the key, say a missing key means on, and say
  what turning it off gives up (no stale-review protection at commit).
