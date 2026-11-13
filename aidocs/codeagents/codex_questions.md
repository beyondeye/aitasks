# Codex attended questions — the `aitask_questions` MCP server

Attended `aitask-*` workflows ask the user to decide things: approve a plan,
review a change before it is committed, pick tasks to fold. In Codex's default
mode the built-in `request_user_input` tool is restricted by the client's own
instructions to optional questions and may not be used for approvals, so a
required workflow question can go unasked. The framework therefore ships its
own question tool for Codex: a local STDIO MCP server that shows each question
as an MCP elicitation form and keeps every question durable.

Evidence for what is and is not verified against a real Codex client lives in
`codex_questions_prototype.md`. This page is the contract.

## The rule

**A question is answered only by an explicit answer.** A timer that elapsed, a
form that disappeared, an empty tool result, a transport error or an
unavailable server never selects a default, never implies consent and never
lets dependent work start.

## Pieces

| Piece | Path |
| --- | --- |
| Launcher (what Codex starts) | `.aitask-scripts/aitask_questions_mcp.sh` |
| Server (MCP adapter, forms, deadlines) | `.aitask-scripts/aitask_questions/server.py` |
| Durable state, validation, receipts | `.aitask-scripts/aitask_questions/store.py` |
| Receipt guard for the gate ledger | `.aitask-scripts/aitask_questions/approval.py`, called from `aitask_gate.sh` |
| Versioned projections (task requirements, plan bookkeeping) | `.aitask-scripts/aitask_questions/projection.py` |
| Paginated multi-select | `.aitask-scripts/aitask_questions/selection.py` |
| Registration | `[mcp_servers.aitask_questions]` in `seed/codex_config.seed.toml`, merged into `.codex/config.toml` by `ait setup` |
| Dependency | `mcp` (range in `AIT_PIP_SPECS_QUESTIONS`, `aitask_setup.sh`), installed into the framework venv when the project's Codex config registers the server |
| Agent guidance | "Attended Questions" in `.agents/skills/codex_tool_mapping.md` |
| Manual live fixture | `tests/manual/codex_questions_probe.py` |

The registration is a project-level Codex setting, so every way of starting
Codex in the project gets it — `ait codeagent`, `ait skillrun`, a plain `codex`
and `codex resume` — with no extra launch arguments. Codex reads MCP
configuration at start: a session that was already running when `ait setup`
ran must be restarted. Project-level configuration applies only to a project
Codex trusts, which is outside `ait setup`'s remit.

## Tools

| Tool | Purpose |
| --- | --- |
| `aitask_question_ask` | Open an occurrence and show its first unanswered question |
| `aitask_question_resume` | Show the next question; optionally record an answer the user typed at the prompt |
| `aitask_question_status` | Read one occurrence (pending question, accepted answers) |
| `aitask_question_outstanding` | List occurrences still needing an answer or a consumer — recovery after a restart. `retired` lists questions voided in the last 24 hours, so a voided question is not mistaken for one never asked |
| `aitask_question_cancel` | Cancel, or defer for an explicit later resume |
| `aitask_question_consume` | Claim a completion receipt for one dependent action |
| `aitask_question_acknowledge` | Record that the claimed action is done |

One call shows one form. A sequence of questions is a sequence of calls, so a
single tool call never waits longer than one form's deadline.

## Occurrences

An occurrence is one arrival of a workflow at a question step. It is identified
by the project (the checkout's real path), a `workflow`, a `checkpoint`, an
optional `run` and an `opening` key chosen by the caller.

- The same `opening` with the same questions returns the existing occurrence
  — a retry or a reconnect never duplicates it.
- A new `opening` at the same checkpoint retires every older occurrence there,
  even when the wording and the files are byte-identical. A revised plan
  re-approved under the old approval is exactly what this prevents. An
  occurrence whose receipt was already claimed is retired too: its claim is
  revoked (see "Standing").
- Retirement stays inside one run. A task workflow (`t<id>`, `t<id>_<n>`) is
  one run and takes no `run`. A skill without a task passes a `run` value, so
  two sessions at the same skill checkpoint do not void each other's
  question; a reconnect passes the same value and gets the same occurrence.
- An occurrence may bind `artifacts`: project-relative files whose exact bytes
  are fingerprinted, and stored, when it opens. If any of them later differs
  or cannot be read, the occurrence is invalidated; reverting the file does
  not revive it.
- `deleted` binds paths the approved change removes: each must be absent from
  the working tree and present in `HEAD`, and the committed content being
  removed is fingerprinted and stored. A rename is the old path in `deleted`
  and the new path in `artifacts`. A path that exists, or that `HEAD` does
  not hold, is refused; a missing file is never read as a deletion.
- For `checkpoint: plan_approved` on a task workflow the server itself binds
  the task's requirements (`task-requirements/v2`): the frontmatter fields
  `issue_type`, `depends`, `xdeps`, `xdeprepo`, `gates`, `verifies` and
  `folded_tasks`, and the task file's body without framework ledger blocks
  (gate runs, inbox notes). Lists are compared by value, so `[1, 3]` and the
  block form are the same; an empty list and an absent key are the same.
  Every other field (status, assignment, priority, board position,
  `active_gates*`, timestamps) is workflow state and is not bound. If the
  task file cannot be found the question cannot be opened.
- For `checkpoint: review_approved` the files are a change set that will be
  committed, so each entry also records its git file mode, its `base` — the
  whole tree entry (mode, type and object) the checked-out branch holds at
  that path, or none for a new file — and its `blob`: the object git stores
  for those bytes at that path, after clean filters and attribute conversion.
  The occurrence records the branch as its `target`. A symlink is bound as
  the link, never as its target's content. If the branch gains a different
  entry at a bound path (content, executable bit or type), a filter or
  attribute changes what would be stored, or another branch is checked out,
  before the answer is used, the occurrence is invalidated.
- For `checkpoint: merge_approved` there are no files. The ask names
  `merge_source` (the branch being merged) and `merge_into` (the branch it
  lands on); the occurrence records, as its `target`, the commit the source
  names at that moment and the destination branch. A merge approval that
  names neither cannot be opened. If the source moves before the answer is
  used, the occurrence is invalidated.

States: `pending`, `awaiting-chat-answer`, `deferred`, `complete`,
`cancelled`, `invalidated`. Only `complete` carries answers a workflow may use.

## Timeout and recovery

The server ends an unanswered form itself after `AIT_QUESTIONS_TIMEOUT`
seconds (default 300) and returns `awaiting-chat-answer` with the pending
question and everything accepted so far. The client's `tool_timeout_sec` for
this server is set above that deadline so the server, not the client, ends the
wait; if the client does cut the call first, the attempt's stored deadline
expires on the next read and the state is the same.

The agent then tells the user what is pending in plain prose and ends its
turn. The user answers at the ordinary prompt. On that message the agent calls
`aitask_question_resume` with the question id and the user's exact text; the
server validates and records it, then shows the remaining questions as forms.
Accepted answers are immutable: a late or duplicate form response, or a second
prompt answer, cannot overwrite one, and concurrent submissions have exactly
one winner. All of this holds across a server restart and a new connection,
because nothing lives in the process.

Answer channels are recorded as `mcp_form` or `codex_prompt_model_forwarded`.
The second is text the model passed on; it is not authenticated, and the
server cannot tell whether a message was meant as an answer. That association
is the agent's job, and the mapping tells it to leave status requests and
unrelated steering alone and to ask when a message is ambiguous. A choice
answer must match one option id or label exactly; prose is not parsed.

`cancel` in the client's form (Esc in Codex) defers the occurrence; `decline`
cancels it. Neither produces an answer. A deferred question stays open: it can
be shown again with `aitask_question_resume`, or answered at the prompt like a
timed-out one. A cancelled occurrence accepts nothing further.

## Acting on an approval

A complete occurrence carries a receipt. The receipt alone permits nothing.
Immediately before the action the answers allow, the consumer claims it with
`aitask_question_consume(session, receipt, consumer)`:

| Outcome | Meaning |
| --- | --- |
| `claimed` | Freshness was re-proven inside the claiming transaction; proceed |
| `duplicate` | This same consumer already claimed it — check whether the action already happened before repeating it |
| `conflict` | Another action already claimed this receipt |
| `stale_approval` | Not complete, not the current receipt, or a bound file changed |

`Store.snapshot()` returns the approved bytes captured when the occurrence
opened, so code acting on an approval reads what was approved rather than the
live file. For actions other than the review commit the store does not make
the external effect exactly-once; `duplicate` plus `acknowledged` is how a
caller reconciles a crash between claim and effect.

### Committing a reviewed change

A claim followed by `git commit` is not a guard: `git commit` reads the
working tree, so whatever another writer put there after the claim is
committed under the approval. The review commit is therefore made by
`aitask_gate.sh commit-approved <task> <session_id>:<receipt_id> <message-file|->`
(`aitask_questions/commit.py`), which never reads the working tree:

1. It re-reads the branch tip and checks every bound path against its `base`.
   A branch that changed under an approved path — its content, its
   executable bit or its type — refuses the commit (`target_changed:<path>`);
   commits elsewhere on the branch do not.
2. It builds the tree in a private index: the tip's tree, with each approved
   path replaced by its stored bytes and mode, and each `deleted` path
   removed. A path that was not bound cannot enter the commit. The stored
   bytes are working-tree bytes, so they are converted the way `git add`
   would convert them for that path, and the result must be the `blob` bound
   at the ask (`conversion_changed:<path>` otherwise): what is committed is
   the representation that was approved, not raw file bytes and not whatever
   a filter configured since would produce.
3. It creates the commit object, then claims the receipt and records that
   commit in one store transaction — the transaction that proves the
   approval fresh. There is no moment at which the claim exists and depends
   on the working tree staying as approved.
4. It advances the branch with a compare-and-swap on the tip it verified. If
   the branch moved in between, it starts again from step 1 (three attempts).
5. It brings the index to the commit for the bound paths only. Bytes another
   writer left in the working tree stay there as an uncommitted modification.

It prints `COMMIT:<committed|duplicate|committed_index_not_refreshed>|<commit>`;
a refusal prints `COMMIT_REFUSED:<reason>`, exits 3 and commits nothing.
Repeating it for the same receipt returns `duplicate` with the same commit,
and finishes a run that crashed between steps 3 and 4. `pre-commit` and
`commit-msg` hooks run, against the private index; `prepare-commit-msg` and
`post-commit` do not, because the commit is made with plumbing. A
`pre-commit` hook may inspect and reject. One that changes the index —
reformats and re-stages, drops a path — refuses the commit
(`hook_changed_index:pre-commit`): what it would add or leave out was not
what the user reviewed. Apply the hook's changes to the files and ask for the
review again.

A `review_approved` pass is recordable only for a commit made this way
(`review_commit_missing` otherwise). Nothing can stop an agent with a shell
from running `git commit` itself; what the guard ensures is that such a
commit never acquires a recorded review approval.

### Merging an approved revision

`aitask_merge_task.sh begin` is the merge boundary. In a Codex tool shell it
first asks `aitask_gate.sh merge-guard <task> <destination> <source>`, which
answers `MERGE:approved|<commit>|<branch>` only when a merge approval claimed
for the task — by its gate record, or by `--approval
<session_id>:<receipt_id>` passed to `begin`, claimed there — bound exactly
that destination and the commit the source names now, and still stands. The
broker then merges **that commit**, not the branch name, so a source that
moves between the check and the merge does not change what lands.

A refusal is `MERGE_REFUSED:<reason>` from the guard (`merge_approval_missing`,
`merge_destination_differs`, `merge_source_differs`, `stale_approval`). The
broker reports it as exit 2 with `APPROVAL_REFUSED:<reason>` on stderr, before
it takes the merge reservation, and prints no verdict: its verdict vocabulary,
which every agent's rendered Step 9 branches on, is unchanged. Outside a
Codex tool shell the guard is not consulted at all.

### Archiving

`aitask_archive.sh` asks `aitask_gate.sh approvals-settled <task>` in a Codex
tool shell and refuses (`APPROVAL_PENDING:<gate>:<why>`, `APPROVAL_BLOCKED`,
exit 2) while an approval question of the task is not settled. Every task
the run archives is checked before anything is written: the named task, and
the parent that is archived together with its last child. For each of the
three gates the newest occurrence asked for the task decides:

| `<why>` | The newest question for that gate |
| --- | --- |
| `unanswered` | is still open — on a form, at the prompt, or postponed |
| `declined` | was cancelled by the user |
| `voided` | was invalidated before its answer was used |
| `not_approved` | was answered with a non-approving option |
| `not_recorded` | was approved, and the approval was never claimed |
| `not_committed` | is a review whose commit is not on its branch |
| `stale` | was claimed and no longer stands, or was revoked |

A claimed approval is settled while its verdict (below) is `FRESH`,
`BOOKKEEPING` or `NOTES`. `NOTES` is the one change to an approved plan that
archiving accepts: the approved plan intact, followed only by the sections
the workflow writes once the work is done. Any other change to the plan, a
change to the task's requirements, and a revocation recorded earlier all
block the archive as `stale`. A gate whose ledger record is a profile approval that still holds
is settled by the profile. A gate that was never asked is not judged — whether
a task needs that approval is the workflow's and the gate ledger's question.
`--ignore-gates` does not override this guard.

### Standing

A claim records a completed permission; whether it still authorizes new work
is its *standing*. A claim is revoked — permanently, and recorded in the
state — when the checkpoint is asked again in the same run, or when any read
of the occurrence (a status or recovery call, a gate check) finds a bound
entry no longer covered:

| Bound entry | Covered while |
| --- | --- |
| file | byte-identical |
| plan file of a recorded `plan_approved` | as above, or changed only within `plan-bookkeeping/v2` |
| task requirements | the `task-requirements/v2` text is identical |
| removed path | still absent |
| any entry of a change set committed by `commit-approved` | that commit is on the bound branch, or — once that branch is gone, as a task branch is after its merge — on some local branch. The files themselves are no longer consulted, because editing them again is new work |
| merge source and destination | the destination contains the approved commit, or the source still names it |

`plan-bookkeeping/v2` tolerates one thing: the checked state of task-list
checkboxes (`- [ ]` / `- [x]`). No text may be added anywhere, under any
heading, so the tolerance cannot carry a requirement nobody approved. The
sections the workflow appends to a plan later (`## Post-Review Changes`,
`## Final Implementation Notes`) therefore end the plan approval's standing
for further work: a task re-entered before its review is recorded has the
plan — with those sections — approved again.

That shape is recognised as `plan-closing-notes/v1`, verdict `NOTES`: the
approved text (checkboxes aside) is an exact prefix of the file, what follows
opens with one of those two headings, and it contains no other first- or
second-level heading outside fenced code. `NOTES` is not a tolerance. It
never resumes implementation and never re-records the gate; it is not a
revocation either, because nothing that was approved changed, and it is what
lets a finished task be archived. Text anywhere else, or a new section among
the notes, is `STALE` and is revoked.

A claim must also bind what its checkpoint requires today. A plan approval
saved before task requirements were bound, or bound under an older rule
version, and a merge approval that names no revision, are revoked the first
time they are read: they cannot be shown to cover what they should, so they
are not re-read under the new rule.

## Gate enforcement

Recording an approval gate, committing a reviewed change, merging and
archiving are guarded by the scripts that do them, not by the agent following
its instructions: the ledger checks the receipt itself, the commit is made
from the approved bytes, the broker merges the approved revision, and the
archive script refuses while an approval is open.

**Scope.** The guard is active only when both hold: the command runs inside a
Codex tool shell (`CODEX_THREAD_ID` is set) and the project that owns the task
data registers `[mcp_servers.aitask_questions]` in `.codex/config.toml`. Every
other agent, a person signing with `ait gate pass` at a terminal, the headless
orchestrator and a project without the server behave exactly as before.

**Recording.** `aitask_gate.sh append` — and so `aitask_gate_record.sh` —
refuses a `pass` for `plan_approved`, `review_approved` or `merge_approved`
with exit 3 and writes nothing, unless it is given `approval=<evidence>`:

| Evidence | Accepted when |
| --- | --- |
| `<session_id>:<receipt_id>` | the occurrence belongs to this checkout, its `workflow` is `t<task_id>`, its `checkpoint` is the gate name, its first question is a choice answered with an option whose id starts with `approve`, it bound the task's plan file and requirements (`plan_approved`) or at least one file or removed path (`review_approved`), and the receipt can be claimed for `t<task_id>:<gate>` — or was already claimed for exactly that and the claim still stands. For `review_approved` the claim must be the one `commit-approved` made, with its commit on the bound branch |
| `profile:<name>` | the profile file sets `post_plan_action: start_implementation` (or the `_for_child` key) for `plan_approved`, or `review_action: commit` for `review_approved`; never for `merge_approved` |

The claim re-proves freshness in its own transaction, so a plan edited between
the answer and the record is refused. `aitask_gate_record.sh` prints
`GATE_RECORD_REFUSED:<gate>` and exits 3; every other failure of that helper
stays best-effort. The recorded block carries
`approval:<occurrence>:<manifest digest>` as its note.

**Re-entry.** `aitask_gate.sh resume-point` demotes `IMPLEMENT` to `PLAN` when
the recorded plan approval no longer stands. The approval judged is the one
the ledger's current `plan_approved` record names in its note.
`aitask_gate.sh approval-check <task> <gate>` prints the evidence:

| Verdict | Meaning | Resumes implementation |
| --- | --- | --- |
| `FRESH` | every bound entry is covered exactly | yes |
| `BOOKKEEPING` | the plan changed only within `plan-bookkeeping/v2` | yes |
| `NOTES` | the approved plan is intact and only the workflow's closing sections follow it (`plan-closing-notes/v1`); settles an archive | no |
| `PREPARED` | a review's commit object exists but is not on its branch (an interrupted `commit-approved`; run it again) | — |
| `PROFILE` | recorded with `approval=profile:<name>`, and that profile still pre-answers the step | yes |
| `STALE` | the claim was revoked, a bound entry is not covered, or the named profile no longer pre-answers | no |
| `UNBOUND` | the pass has no claimed receipt in this checkout's state | no |

A `STALE` finding is written to the question state, so restoring the old
bytes afterwards does not restore the approval. A profile-recorded approval
has no bound files: the profile skips the question, so a plan edit does not
ask either.

`UNBOUND` covers a pass recorded by another agent or before the guard existed:
a Codex session asks for the approval again rather than inherit one it cannot
check. `POSTIMPL` is never demoted — a completed, recorded review stays
evidence of what was done.

**What this does not do.** Option ids are chosen by the asking agent, so the
`approve` prefix catches an honest mix-up, not a model that mislabels its own
options. A plan or task change made and undone between two reads of the
state is not seen. A merge approval is of a revision into a branch; the
destination may advance before the merge, as any merge target may. The
archive guard judges questions that were asked — a task whose review was
never asked at all is not held back by it. A change set is limited to 200
paths of 2 MB each.
Receipts live in
per-user state on one machine, so a task approved in Codex on one machine and
resumed in Codex on another is `UNBOUND` there. An agent with a shell can
unset `CODEX_THREAD_ID`; the guard stops mistakes and skipped steps, not a
session that sets out to defeat it.

## Monitor recognition

Two states mean "this pane is waiting on the user", and they are detected
differently.

**An open form** is on screen. `codex_mcp_form` in
`monitor/prompt_patterns.py` matches it by structure: the footer holds its
whole line, is the last row on screen, and has the form's input widget
directly above it (the last numbered option row, or the `›` answer row and one
blank row). The footer text quoted in output above a normal composer is not a
form. It is also a question-widget kind in `lib/workflow_phase.py`.

**A question waiting at the prompt** — the form timed out, failed or was
postponed — has nothing on screen: the agent said what is pending and ended
its turn. The server stamps such an occurrence with its own process: pid,
start time and ancestor pids (`aitask_questions/owner.py`). `ait monitor` and
`ait minimonitor` read the state read-only (`aitask_questions/waiting.py`) and
report a pane as awaiting input when all of these hold:

- the occurrence is `awaiting-chat-answer` or `deferred`;
- the stamped process is still running, with the recorded start time, so a
  reused pid is not a waiting session;
- the pane is the conversation's pane, or could be (below);
- the pane is idle and no on-screen prompt matched.

Which pane a question belongs to depends on how Codex was started (measured
on 0.167.2 and 0.168.0 in live sessions):

| Launch | Where the server runs | What the monitor reports | Kind |
| --- | --- | --- | --- |
| Every framework launch (in-process TUI) | a child of the `codex` process in the pane | the one pane whose process is an ancestor of the stamped process | `codex_question_at_prompt` |
| `codex` started by hand | under the shared `codex app-server` daemon, outside every pane | every pane running a client that could hold the question | `codex_question_unassociated` |

The daemon case cannot use ancestry: the daemon's server has no pane above
it, and while the pane that first started the daemon is alive the daemon is
that pane's child, so ancestry would name the wrong pane. The recorded
ancestor chain therefore stops below an app-server process and the stamp is
marked `detached`.

Codex exposes no identity that links a terminal client to the conversation it
shows: the client's arguments, open files, environment and log rows do not
name its thread, and the daemon's log names a connection number only. What a
pane displays is not an identity either: the question's `session_id` on a
screen may be a quotation, and is gone after a scroll or a monitor restart.
So a detached question is **not assigned to a pane**. `codex_question_unassociated`
means "a question of this project is waiting in one of the panes carrying
this kind", never "in this pane". A pane is such a candidate when the process
in the foreground of its terminal:

- is a `codex` terminal client;
- runs no sessions in its own process tree. A framework-launched client does
  (measured on 0.166.0–0.168.0: it has a `codex-code-mode-host` child from
  startup, and the question server when one is configured), and its own
  questions are reported by ancestry; a client of the shared daemon has no
  children. The check reads the children of all of the client's threads and
  stops at an app-server: a server the shared daemon runs is not the
  client's, also when that client is the one that started the daemon;
- has its working directory inside the question's project.

Both monitors render the kind apart from a prompt: badge `ASKED?` with a
hollow dot instead of `PROMPT`, and a separate `N asked?` term in the session
bar that is never added to `awaiting` (`monitor_shared.is_maybe_awaiting`).
The shadow's auto-recheck loop does not act on a candidate either: it is
handed "not observed" instead of "waiting" (`monitor_shared.awaiting_evidence`).

Candidates are derived from running processes on every refresh. Nothing is
stored and no earlier sighting is needed, so the result is the same after a
monitor restart and in every monitor, and a pane back at its shell, or one
running a program that is not a candidate, drops out at once. With one
hand-started Codex in a project the kind marks exactly that pane; with
several, all of them, until the question is answered.

The indicator clears by itself: an accepted answer, a cancellation, an
invalidation or a re-opened form leaves the waiting states and removes the
stamp. A closed in-process session fails the liveness check. Whether a
daemon-hosted server outlives its client depends on the Codex version (0.167.2
kept it, 0.168.0 ends it with the client). A question resumed in another
session is re-stamped by the server that touches it. Listing calls never move
a stamp. The reader writes nothing and never creates the state directory.

## Multi-select

A `multi` question is presented one page per form. Each page submission is
stored once; the selection accumulates across pages and survives timeouts and
restarts; `all` and `none` act on the original full candidate set and are
actions, never options. The final value is the complete selection in candidate
order. An explicit empty selection is distinct from no response.

Two encodings exist. `text` (the default) takes one JSON object per page in a
text field, e.g. `{"selected":["t12"],"action":"next"}`, and works with the
`2025-06-18` protocol Codex negotiates. `native` uses array schemas that need
protocol `2025-11-25`; on an older protocol it returns `unsupported_shape`
and leaves the question pending.

## Configuration

| Setting | Where | Default |
| --- | --- | --- |
| Form deadline | `AIT_QUESTIONS_TIMEOUT` (seconds, 0.05–900) | 300 |
| Client tool timeout | `tool_timeout_sec` in `[mcp_servers.aitask_questions]` | 360 — keep it above the form deadline |
| State directory | `AIT_QUESTIONS_STATE_DIR` | `${XDG_STATE_HOME:-~/.local/state}/aitasks/questions` |
| Multi-select encoding | `AIT_QUESTIONS_MULTISELECT` | `text` |

State is one SQLite file outside the project, so it cannot be committed and a
git worktree — a different real path — is a separate scope. Diagnostic event
history per occurrence is bounded; answers and receipts are not part of it.

## When the server is not there

If the `mcp` package is missing the launcher exits non-zero with the reason on
stderr and Codex reports the server as failed. The mapping then has the agent
ask in plain prose and end its turn. Re-run `ait setup` to repair, and restart
Codex.

## Limits

- The server serves questions; it does not decide what a workflow does with
  them. Everything on the agent's side of the tool call — ending the turn,
  matching a prompt message to a question, claiming before acting — is
  instruction-following by the model.
- The shadow's workflow-phase signal reads the screen only: it recognizes an
  open form, not a question waiting at the prompt.
- For a hand-started Codex (daemon-hosted server) the waiting-at-the-prompt
  indicator cannot name the pane. Every hand-started Codex whose working
  directory is inside the project is marked `codex_question_unassociated`
  while the question waits, including one that shows another conversation
  (after `/new`, or a second session). On 0.167.2 a question server can
  outlive its client, so the kind can also mark a pane when the conversation
  that asked has been closed. Codex offers nothing that would narrow this.
- `ait monitor` watches agent windows only; a Codex started by hand in a
  window with another name is not watched at all.
- Corrupt or locked state is reported as an error. It never reads as answered.
- Chatlink's Q&A relay is a separate transport with its own terminal timeout
  and is unchanged.

## Tests

```bash
python3 tests/test_aitask_questions.py            # store
python3 tests/test_aitask_questions_selection.py  # multi-select protocol
bash tests/test_setup_questions_server.sh         # seed, merge, tier, launcher
bash tests/test_gate_codex_approvals.sh           # receipt guard on approval gates
<venv-python> tests/test_aitask_questions_mcp.py  # real STDIO server; needs the mcp package
```
