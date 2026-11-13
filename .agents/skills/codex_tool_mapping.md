# Tool Mapping (Claude Code → Codex CLI)

When the source skill references Claude Code tools, use these Codex CLI equivalents:

| Claude Code Tool | Codex CLI Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | `aitask_question_ask` (MCP server `aitask_questions`) | One form per call; the server walks the questions in order. An unanswered form is **never** an answer — see "Attended Questions" below. Not for sandbox, command or security approvals. |
| `Bash(command)` | `functions.exec_command(command)` | Direct equivalent |
| `Read(file)` | `functions.exec_command("cat <file>")` | Use cat for file reading |
| `Write(file, content)` | `functions.apply_patch(...)` | Use Add File patch for new files |
| `Edit(file, ...)` | `functions.apply_patch(...)` | Use Update File patch for edits |
| `Glob(pattern)` | `functions.exec_command("find . -name '<pattern>'")` | Use find for file discovery |
| `Grep(pattern)` | `functions.exec_command("grep -rn '<pattern>' .")` | Use grep/rg for content search |
| `WebFetch(url)` | `web.run` with `open` | Web content fetching |
| `WebSearch(query)` | `web.run` with `search_query` | Web search |
| `EnterPlanMode` | _(not available)_ | Plan inline within the conversation |
| `ExitPlanMode` | _(not available)_ | Plan inline within the conversation |
| `Agent(...)` | _(not available)_ | Execute the sub-steps directly |
| `Skill(name)` | Read the referenced SKILL.md file directly | No sub-skill invocation mechanism |

## Codex CLI Adaptations

### Attended Questions

Every `AskUserQuestion` in a source skill is a decision the workflow needs. Ask
it through the `aitask_questions` MCP server that `ait setup` registers in
`.codex/config.toml`. Do **not** use the built-in `request_user_input` for
these: in default mode the client restricts it to optional questions and
forbids approval requests, so a required decision can silently go unasked.

Questions the active execution profile already answers are not asked at all;
that is unchanged. Sandbox, command and filesystem approvals stay with Codex's
own approval prompts and are never routed through this server.

**Asking.** Call `aitask_question_ask` with:

- `workflow` — `t<task_id>` (or the skill name when there is no task).
- `run` — only when `workflow` is a skill name: a value that identifies this
  run of the skill, so the same question open in another session is left
  alone. Use `$CODEX_THREAD_ID` (read it once with a shell command) and pass
  the same value on every ask of the run. Omit it for a task: the task is the
  run, and the server refuses a `run` there.
- `checkpoint` — a short stable name for the step, e.g. `plan_approval`.
- `opening` — a new value every time the workflow *arrives* at the step
  (e.g. `plan_approval-2`, or the step name plus a timestamp you generate
  once). Reuse the same value only to retry the very same ask after an error.
  A revised plan or a second review round is a new arrival: new `opening`.
- `questions` — one entry per source question, in order:
  `{id, text, kind, options}`. `text` carries the source header and question.
  - single choice → `kind: "choice"`, `options: [{id, label, description}]`
    with short stable ids. Any number of options is fine.
  - free text → `kind: "text"`, no options.
  - the source's implicit "Other" free-text path → add an option
    `{id: "other", ...}` and, when it is chosen, ask the detail as a `text`
    question under a new `opening`.
  - `multiSelect: true` → `kind: "multi"`; see "Multi-select" below.
- `artifacts` — project-relative paths of the files the answer approves (the
  plan file for a plan approval; omit for questions that approve nothing).
  If one of them changes before the answer is used, the answers are void.
  Every path must exist. The server stores their bytes as they are when you
  ask, so finish every edit first.
- `deleted` — project-relative paths the approved change **removes**. The
  path must be gone from the working tree and present in `HEAD`. A rename is
  its old path in `deleted` and its new path in `artifacts`.

The call shows the first unanswered question as a form and returns. While
`state` is `pending` and `next_action` is `resume_next_question`, call
`aitask_question_resume` with the `session_id` to show the next form. Use the
answers only when `state` is `complete`.

**A form that is not answered.** Any other result — `awaiting-chat-answer`,
`deferred`, `unavailable`, a timeout, a transport or tool error — means the
question is still open:

1. Do not pick a default, infer consent, skip the question, or start any work
   that depends on it (implementation, commit, gate record, archive).
2. Tell the user in plain prose which question is waiting, what the choices
   are, and that they can answer right here at the prompt. State the
   `session_id` in full, unbroken and unabbreviated — the monitor finds the
   waiting pane by it. Plain sentences only — no numbered menu of options.
3. **End your turn.** Do not poll `aitask_question_status` and do not re-ask
   in a loop.
4. On the user's next message: if it clearly answers the pending question,
   call `aitask_question_resume` with `session_id`, the `question_id` and
   their **exact** text as `prompt_answer`. If it is a status request or
   unrelated steering, handle that and leave the question open. If it is
   ambiguous, ask what they meant; an `invalid_prompt_answer` result means the
   same.
5. The resume call records the answer and shows the remaining questions as
   forms. Answered questions are never asked again. Another timeout repeats
   steps 1–5; nothing already answered is lost.

`cancelled` means the user declined: treat it as the source skill's abort or
"no" path only if the skill defines one for dismissal, otherwise stop and ask
what they want. `invalidated` means a bound file changed or the step was
reopened: ask again with a new `opening`.

**After a restart or lost context**, call `aitask_question_outstanding` with
the `workflow` to recover open `session_id`s instead of asking again. With more
than one row, match the `checkpoint` and, for a skill without a task, the
`run` (rows carry it; pass `run` to list only yours); never guess. A row under `retired` is a
question that was open and has been voided since (a bound file changed): it
cannot be resumed — ask it again with a new `opening`.

**Before acting on an approval.** A `complete` result carries a `receipt`.
Immediately before the action the answers permit — deleting a branch, for
example — call `aitask_question_consume` with the `session_id`, the `receipt.id` and a
stable `consumer` name for that one action. The three approval gates below
are different: their receipts are claimed by the gate scripts, not by you. Proceed only on `claimed`. On
`duplicate`, check whether the action already happened before repeating it. On
`stale_approval` or `conflict`, do not proceed: ask again with a new `opening`.
Call `aitask_question_acknowledge` once the action is done. Questions that
approve nothing (a label filter, an explanation mode) need no consume.

#### Approval gates

The plan approval, the review before the commit and the merge approval are
recorded in the task's gate ledger. In a Codex session the gate scripts check
the receipt themselves: a `pass` for `plan_approved`, `review_approved` or
`merge_approved` without one is **refused** (`GATE_RECORD_REFUSED`, exit 3) and
nothing is recorded. A refusal means the approval does not exist — stop, and
ask again under a new `opening`. Shape these three questions so the receipt is
accepted:

- `workflow` is `t<task_id>` and `checkpoint` is the gate name itself:
  `plan_approved`, `review_approved` or `merge_approved`.
- The decision is the **first** question, `kind: "choice"`. Give every option
  that approves an id starting with `approve` (`approve_start`,
  `approve_stop`, `approve_commit`, `approve_merge`) and every other option an
  id that does not (`revise`, `more_changes`, `abort`, `not_yet`).
- `artifacts`: for `plan_approved`, the plan file — the server binds the
  task's description itself, so do not list the task file. For
  `review_approved`, the files of the change set being reviewed, with removed
  paths under `deleted` — not the plan file, which is edited again after the
  review. `merge_approved` takes no `artifacts`: pass `merge_source` (the
  task branch, `aitask/<task_name>`) and `merge_into` (the resolved output
  branch) instead. The server refuses a merge approval without them.
- Record the gate with the receipt as evidence:

  ```bash
  ./.aitask-scripts/aitask_gate_record.sh <task_id> <gate> pass type=human \
      approval=<session_id>:<receipt_id>
  ```

  The script claims the receipt for `t<task_id>:<gate>`, records the gate and
  acknowledges the claim. Do not call `aitask_question_consume` for any of
  the three gates yourself.
- **The review commit.** Do not run `git commit` for the reviewed change.
  Write the commit message to a file and run:

  ```bash
  ./.aitask-scripts/aitask_gate.sh commit-approved <task_id> \
      <session_id>:<receipt_id> <message-file>
  ```

  It commits exactly the `artifacts` and `deleted` paths of the review
  question, with the content they had when you asked, onto the branch that
  was checked out then. `COMMIT:committed|<commit>` or
  `COMMIT:duplicate|<commit>` means the commit exists; then record the gate
  as above with the same `approval=`. `COMMIT_REFUSED:<reason>` (exit 3)
  means nothing was committed: a reviewed file changed
  (`stale_approval`), the branch changed under one (`target_changed`), or a
  `pre-commit` hook tried to change what is committed
  (`hook_changed_index` — apply its changes to the files first).
  Show the user the current change and ask for the review again under a new
  `opening`. A review gate is refused (`review_commit_missing`) for a change
  committed any other way. Task and plan files under `aitasks/` and
  `aiplans/` are not part of the reviewed change set; commit them as the
  workflow says.
- **The merge.** Record the `merge_approved` gate as above, then run the
  merge broker as the workflow says. In a Codex session
  `aitask_merge_task.sh begin` merges only the commit the approval bound,
  into the branch it bound. When the profile does not record gates, pass the
  receipt to the broker instead: `begin ... --approval
  <session_id>:<receipt_id>`. Exit 2 with `APPROVAL_REFUSED:<reason>` on
  stderr and no verdict means nothing was merged and no reservation is held:
  the task branch gained a commit after the approval
  (`merge_source_differs`), the target is another branch, or no approval
  exists. Ask for the merge approval again under a new `opening`.
- **Archiving.** `aitask_archive.sh` refuses (`APPROVAL_BLOCKED`, exit 2)
  while a plan, review or merge question of the task is unanswered,
  declined, voided, answered without approving, approved but never recorded,
  or stale. Archiving the last child checks the parent's questions too.
  `--ignore-gates` does not change that. Settle the question it
  names — ask it again and act on the answer — then archive.
- When the execution profile pre-answers the step and no question was asked,
  pass `approval=profile:<profile_name>` instead. The script checks the
  profile; no profile covers the merge approval.

**Resuming a task.** `aitask_gate.sh resume-point` answers `PLAN` instead of
`IMPLEMENT` in a Codex session when the recorded plan approval no longer
stands: the plan or the task's description, dependencies or declared gates
changed after approval, the approval was asked again, or it was recorded
outside the question server (another agent, an older session). This is final for that approval —
restoring the old text does not bring it back. Follow the `PLAN` path: present
the existing plan and ask for its approval again.
`./.aitask-scripts/aitask_gate.sh approval-check <task_id> plan_approved`
shows the evidence.

**Writing to an approved plan.** One kind of change keeps the approval:
ticking or unticking task-list checkboxes (`- [ ]` / `- [x]`, the step text
untouched). Track progress that way. Any text added or changed — including
the `## Post-Review Changes` and `## Final Implementation Notes` sections the
workflow has you write — ends the approval; write those sections when the
workflow says to, and if the task is resumed before its review is recorded
the plan, with them, is approved again. Append them AFTER the approved text
and add no other `#`/`##` heading: archiving accepts an approved plan
followed by exactly those sections, and refuses (`plan_approved:stale`) any
other change to it. The same holds for the task file: its
description, `depends`, `gates` and `issue_type` are part of what was
approved; status, assignment and gate records are not.

**If the server is not available** (its tools are not listed, or the client
reports it failed to start): ask the same question in plain prose, end your
turn, and take the user's next relevant message as the answer. Do not fall
back to defaults. `ait setup` installs the server; Codex must be restarted to
load it.

#### Multi-select

A `kind: "multi"` question is shown one page per form; the server paginates
(`page_size`, default 3) and accumulates the selection. Pass **every**
candidate as an option with a stable id — task ids, file paths, guide paths —
never only the labels, and never a truncated list.

- Drop the source skill's own paging rows ("Show more", "Next page"): the
  server's `next` action replaces them. Never pass a control as an option.
- "Select all" / "None" rows in the source are the form's `all` / `none`
  actions, not options. `all` means the original full candidate set.
- Set `min_selected` / `max_selected` when the source requires them.
- Each form takes JSON such as `{"selected":["t12","t15"],"action":"next"}`;
  the form message lists the page's ids and the allowed actions. The same JSON
  is what the user types at the prompt after a timeout; forward it unchanged
  as `prompt_answer` together with `pending_page.page_id`.
- The final answer is the complete selection in candidate order. An explicit
  `{"selected":[],"action":"finish"}` is an empty selection; a timeout, an
  empty form or silence is not.
- Keep the source skill's meaning for what unselected and unvisited items
  mean (inclusion lists versus exclusion lists) — that is decided by the
  skill, after the selection is complete.
- Never emulate multi-select with one yes/no question per item, or with a
  single-choice question. A skill that defines its own text fallback
  (`aitask-work-report`) may keep using it.

If a result reports `unsupported_shape`, the question stays open: ask it in
plain prose as above.

### Plan Mode

Codex CLI has no separate `EnterPlanMode`/`ExitPlanMode`. When the source
skill references plan mode, plan inline: describe your approach as part of
the conversation output before executing.

### Sub-Skill References

When the source skill says "read and follow `.claude/skills/<name>/SKILL.md`",
read that file directly and follow its instructions. There is no sub-agent
or sub-skill invocation mechanism.

### Agent String

When recording `implemented_with` in task metadata, construct `codex/<name>`.
Do NOT guess your model ID — Codex models cannot reliably self-identify.

1. Check `AITASK_AGENT_STRING` env var — if set, use it directly.
2. Otherwise, read configured model: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`
3. Run: `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent codex --cli-id <model_id>`
4. Parse the output — the value after the colon is your agent string.

### Task-Workflow Adaptations

These adaptations apply to skills that hand off to the shared task-workflow
(`aitask-pick`, `aitask-create`, `aitask-explore`, `aitask-fold`,
`aitask-review`, `aitask-pr-import`).

**Plan file creation:** When `aitask_query_files.sh plan-file <taskid>`
returns `NOT_FOUND`, this means **no plan file exists yet** — it does NOT
mean "no plan needed" or "skip plan creation." Always create the plan file
in `aiplans/` before beginning implementation. Follow the planning workflow
in the source skill for the correct format and content.

**Post-implementation finalization:** After implementation is complete, you
MUST explicitly run all finalization steps from the task-workflow (Steps 8
and 9). They are not triggered automatically:

1. **Consolidate the plan file** — update `aiplans/` with final
   implementation notes, deviations, and outcomes
2. **Commit changes** — follow the commit message format:
   `<issue_type>: <description> (t<task_id>)`
3. **Archive the task** — run the archival workflow from the source skill

The review question before the commit is a required decision. If it cannot be
asked or is not answered — the question server is unavailable, the form times
out, the tool errors — the task stays where it is: do **not** commit, record a
review gate, or archive on a default. Follow "Attended Questions" above and
end your turn with the question pending. Only an execution profile that
explicitly pre-answers the step may skip the question.
