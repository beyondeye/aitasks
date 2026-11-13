# Codex attended questions — evidence record (t2281)

What was observed against a real Codex client, what was only tested with a
scripted client, and what is still open. The contract itself is in
`codex_questions.md`.

## Saved checkpoint — 2026-11-12

User requested “save progress and abort”, then specified no commit was needed.
Prototype code, tests and this evidence report are retained locally without a
new commit; the plan is retained and the task
returns to Ready, unassigned, with plan approval reopened by the abort procedure.
No integration or archival is complete. Resume with `/aitask-pick 2281`, review
the saved plan and obtain the remaining live accepted-answer reconnect/repeated-
timeout evidence before production integration. Temporary probe databases and
the isolated venv remain under `/tmp`; their continued availability is not
guaranteed, so the verified receipt details are recorded below.

## Integration status — 2026-11-12

Done after the transport go, all with automated tests and **none of it yet
exercised by a live Codex session started from the installed configuration**:

- Server renamed from the probe to `aitask_questions`; tools ask / resume /
  status / outstanding / cancel / consume / acknowledge. The rule for an
  unanswered question sits in the first 512 characters of the instructions.
  The live runs recorded below used the earlier probe name, a 20 s deadline
  and launch-argument registration.
- Store: corrupt or locked state is an error, never an answer; a writer killed
  mid-transaction leaves the previous state; diagnostic history is bounded;
  `outstanding()` recovers session IDs after a restart.
- Setup: `[mcp_servers.aitask_questions]` in the Codex seed with a
  repo-relative launcher; the `mcp` dependency is installed when the project's
  Codex config registers the server; state lives outside the project.
- Mapping: `.agents/skills/codex_tool_mapping.md` routes `AskUserQuestion`
  through the server, spells out the timeout → prompt → resume flow, and no
  longer tells Codex to commit and archive on defaults when a finalization
  question cannot be asked. The task-workflow sources were searched for other
  default-on-no-answer fallbacks; none were found.

Status of the six items that were open here, as of the end of 2026-11-12:

1. **Live run through the installed configuration — done.** See the results
   below: repo-relative `command`, default state directory, 300 s deadline
   under a 360 s `tool_timeout_sec`, renamed tools, recovery after a restart.
2. **Multi-select — done for the three named shapes.** An accepted page
   survived a restart; the dependency, guide and finding shapes ran through
   the mapping's own guidance. See "Caller shapes" below. The other
   inventoried callers were not each run live.
3. **Monitor — form recognized.** `codex_mcp_form` is a prompt pattern and a
   question-widget kind, built from the live captures. A question that timed
   out and waits at the prompt is read from the server's state instead
   (`codex_question_at_prompt`, or `codex_question_unassociated` when the
   pane cannot be named); see `codex_questions.md`, "Monitor recognition".
4. **Gate enforcement — done for attended Codex.** The ledger refuses an
   approval `pass` without a claimable receipt and `resume-point` re-checks
   the plan approval; validated live. See "Approval gates" below.
5. **Website — updated.**
6. **Still not measured live:** an outer timeout shorter than the server
   deadline, long-question rendering, two concurrent Codex sessions. Defer
   from the form and a status question at the prompt are now measured.

## Installed-configuration live runs

### Result — 2026-11-12

One run, read back from the state file. Occurrence
`5743c873f58b483fa1bbf2d4ee69498d`, opening `run-1`, receipt
`2c7791cf4ac140ec89ee25d9d1b690a7`, one server process (pid 249616), protocol
`2025-06-18`, opened 10:44:02Z.

| Observed | Evidence |
| --- | --- |
| Codex started the server from the repo-relative `command` | the occurrence exists with project `/home/ddt/Work/aitasks` |
| The server got `HOME` and used the default state directory | the state file is at the default path |
| The shipped 300 s deadline holds under `tool_timeout_sec = 360` | q2 `deadline_expired` at 300.142 s, ended by the server |
| The turn ended and a prompt answer was forwarded | q2 `codex_prompt_model_forwarded`, 84 s after the deadline |
| Renamed tools and the mapping's claim step | `receipt_consumed` for `t2281-live:report`, then `consumption_acknowledged` |
| The bound artifact was fingerprinted and stored | one manifest entry, one snapshot |

Channels were form / prompt / form. The server deadline was 300 s on every
form, because the 30-second `-c ...env=` override in step 2 could not be
used: it crashes Codex 0.167.2 during bootstrap (reported by the user; message
not captured). Do not use it; set a short deadline with an `env` line in the
config table instead. Steps 5 and 6 leave no trace in this
occurrence: nothing shows a status question at the prompt, and question 3 was
answered in the form after 8.8 s, so deferring with Esc and a second prompt
answer are still unobserved.

### Second run — 2026-11-12, defect found

Occurrence `5540f7a38d8c4e1fbb271c40bbcdeb47`, opening `run-3`, pid 800338,
300 s deadline (no override).

- Question 2 timed out at 300.154 s. A status question at the prompt produced
  a `resume` call with no answer and recorded nothing: passed.
- `Sample Alpha` was accepted from the prompt, question 3 appeared as a form,
  and Esc after 5.0 s stored `deferred` with no answer: passed.
- `Finish` at the prompt was then refused with `not_accepted`. **Defect:** the
  store rejected every answer to a deferred occurrence while the mapping told
  the user to answer at the prompt, so Esc left no way to answer short of
  showing the form again. The agent reported the refusal accurately and
  claimed nothing.

Fixed in `store.py`: a deferred occurrence accepts an explicit prompt answer;
a late form response still returns `stale_attempt`; cancelled and invalidated
still accept nothing. Pinned by
`test_deferred_question_accepts_explicit_prompt_answer_only`. The fix has not
been re-run against Codex.

### Third run — 2026-11-12, fix confirmed, agent-driven

Driven by the implementing agent through tmux key input into a real Codex
0.167.2 TUI (`gpt-6-astra`), not by a human. The run-3 occurrence could not be
reused: editing the bound `codex_questions.md` for the fix invalidated it
(`artifact_revision_changed_or_unverifiable`), and `outstanding` then listed
nothing — the binding working as designed.

Occurrence `58afc9f903584c2c92ec94642566a148`, opening `run-4`, receipt
`4b9fb18de310449183b07a2bf0584405`, installed configuration, no overrides.

| Step | Stored result |
| --- | --- |
| Question 1 answered in the form (pid 2151667) | `mcp_form` |
| Esc on question 2 | `deferred`, no answer; agent ended its turn |
| Codex quit; new Codex, new server (pid 2220182), new conversation | `aitask_question_outstanding` found the occurrence and showed question 2 again; question 1 not re-asked |
| Esc again, then `Sample Alpha` at the prompt | accepted, `codex_prompt_model_forwarded` |
| Esc on question 3, then `Finish` at the prompt | accepted, `codex_prompt_model_forwarded` |
| Claim | `receipt_consumed` for `t2281-live:report`, then acknowledged |

The Codex form as rendered ends with `enter to submit | esc to cancel` under a
`Field 1/1 (1 required unanswered)` header; a choice shows a numbered list, a
text question `› Type your answer`.

### Multi-select across a restart — 2026-11-12, agent-driven

Same driving method. Fixture `/tmp/aitask-2281-live-multi-reconnect3`,
occurrence `ec1f1dbd3dc442cea2cbdb393cd46894`, receipt
`4de4a3682ba343588f9cc5bcf982f8b5`, Codex session
`01a1cf9c-9c15-7990-98bd-f38900599acb`, text encoding, 20 s deadline, launched
with `-c` overrides for `command`, `args` and `tool_timeout_sec` on top of the
installed registration.

| Page | Channel | Detail |
| --- | --- | --- |
| 1 | `mcp_form` | `task-1`, `task-3`, next; 6.5 s; pid 2255345 |
| 2 | `codex_prompt_model_forwarded` | form timed out at 20.006 s; Codex quit and resumed; `task-4`, `task-6`, next |
| 3 | `codex_prompt_model_forwarded` | form timed out at 20.022 s on the new server (pid 2287010); `task-7`, finish |

Final value `task-1, task-3, task-4, task-6, task-7`, one receipt, page 1 not
shown again after the restart. This closes "accepted page across a live
restart" for the sample fixture. The dependency, guide and finding caller
shapes are still not exercised.

### Approval gates — 2026-11-12, agent-driven

Real Codex 0.167.2 TUI started from this checkout, driven through tmux key
input. The question server was pointed at a scratch project
(`/tmp/t2281-live-proj`, state `/tmp/t2281-live-proj-state`) through `-c`
overrides, and the gate scripts were run against it with `TASK_DIR` /
`PLAN_DIR` set, so no real task was touched. Codex followed the mapping's
"Approval gates" section; nothing in the prompt told it how to shape the
question or which arguments to pass.

| Step | Observed |
| --- | --- |
| Plan approval asked | checkpoint `plan_approved`, plan file bound, option ids `approve_start` / `revise` / `abort` |
| Approved in the form, gate recorded with `approval=<session>:<receipt>` | exit 0, block written with `approval:388ff1f7…` note; claim `t7:plan_approved`, acknowledged |
| `resume-point 7` / `approval-check 7 plan_approved` | `IMPLEMENT` / `APPROVAL:FRESH\|388ff1f7…\|1 file(s)` |
| Plan file rewritten from outside, same two commands | `PLAN` with the explanation on stderr / `APPROVAL:STALE\|…\|aiplans/p7_demo.md differs from the approved text` |
| `aitask_gate_record.sh 7 review_approved pass type=human`, no evidence | exit 3, `GATE_RECORD_REFUSED:review_approved`, nothing written |
| Review asked, approved in the form | checkpoint `review_approved`, `src/hello.txt` bound, `approve_commit` |
| `aitask_question_consume` before the stand-in commit, then the gate record | `claimed` for `t7:review_approved`; record exit 0; `resume-point` → `POSTIMPL` |

This run predates the standing rules (revocation, `plan-bookkeeping/v2`,
bound task requirements, `deleted`, `run`, profile re-entry) and the guarded
review commit (`commit-approved`) described in `codex_questions.md`. Under
the current rules the last row is refused: a review record needs a commit made
by `commit-approved`. Those rules are covered by
`tests/test_gate_codex_approvals.sh` and have not been repeated live.

This also confirms `CODEX_THREAD_ID` is set in the shell of an interactive
Codex session (first measured with `codex exec`). Starting Codex inside the
scratch directory itself was abandoned: it raises Codex's folder-trust dialog,
whose answer is saved to the user's global Codex configuration.

### Caller shapes — 2026-11-12, agent-driven

Same session, 25 s form deadline. Each prompt gave Codex the source skill's
rows — including its "None", "Select all" and "Show more" rows — and told it
only to follow the mapping's "Multi-select" part.

| Shape | What Codex built | Pages | Stored result |
| --- | --- | --- | --- |
| Dependencies (`aitask-create`): "None" + 7 tasks, child ids such as `t130_2` | 7 options, no "None" option (mapped to the `none` action) | 1 form, 2 timeout → prompt, 3 form with an explicit empty page and `finish` | `t15, t130_3, t200` |
| Guides (`aitask-review`): "Select all", "Show more", 5 paths incl. `naming (v2).md` | 5 options, both control rows dropped | 1 timeout → prompt, 2 form | the three chosen paths, byte-exact, in candidate order |
| Findings (`aitask-review`): "Select all" + F1–F8, one long description | 8 options | 1 form (`F1`), 2 timeout → prompt `{"selected":[],"action":"all"}` | all eight, in order; page 3 never shown |

In the dependency run a prompt answer naming an id from another page was
refused and added nothing; the agent reported the refusal and asked again.
After that run Codex printed the list as `depends: [15, t130_3, 200]` — the
stored value was correct, and turning ids into frontmatter is the calling
skill's job, which this fixture did not run.

### Steps

Exercises what the earlier live runs did not: the registration in
`.codex/config.toml` with its repo-relative command, the launcher, the renamed
tools, the mapping's guidance, a receipt claim, and the default deadline.
Checked beforehand with a scripted client only: the launcher, started by its
relative command from the repository root, serves all seven tools.

1. Register the server for this checkout (uncommitted) by appending to
   `.codex/config.toml`:

   ```toml
   [mcp_servers.aitask_questions]
   command = ".aitask-scripts/aitask_questions_mcp.sh"
   tool_timeout_sec = 360
   ```

2. For a 30-second form deadline in this run only, add
   `env = { AIT_QUESTIONS_TIMEOUT = "30" }` to that table (unverified; a
   `-c ...env=` override on the command line crashes Codex at start). From the
   repository root, start Codex:

   ```bash
   codex --no-alt-screen --model gpt-6-astra
   ```

   Run `/mcp` and confirm `aitask_questions` is connected with seven tools.
   If it is listed as failed, stop and record the message.

3. Paste this prompt:

   > Compatibility test only; do not implement, commit or archive anything.
   > Read the "Attended Questions" section of
   > `.agents/skills/codex_tool_mapping.md` and follow it exactly. Ask me three
   > questions through it, workflow `t2281-live`, checkpoint `installed`,
   > opening `run-1`, binding the artifact
   > `aidocs/codeagents/codex_questions.md`: (1) a choice "Pick a color" with
   > options Blue and Green; (2) free text "Name the sample"; (3) a choice
   > "Finish?" with options Finish and Stop. When all three are answered, claim
   > the receipt for consumer `t2281-live:report`, then report every answer
   > with its channel, the session id, the receipt id and the claim outcome.

4. Answer question 1 in the form. Leave question 2 untouched for 30 seconds.
   Expected: the agent names the pending question in plain prose and ends its
   turn.
5. Type `what is still pending?` at the prompt. Expected: it answers without
   recording that text as the sample name.
6. Type `Sample Alpha`. Expected: question 3 appears as a form. Press Esc on
   it. Expected: the agent reports the question as still open (deferred), and
   does not treat it as answered.
7. Type `Finish`. Expected: the final report shows channels form / prompt /
   prompt and claim outcome `claimed`.
8. Deadline check at the shipped default: exit, remove the `env` line, start
   Codex again, repeat the prompt with
   opening `run-2`, answer question 1, and leave question 2 for a little over
   five minutes. Record whether the form stays up for the full 300 seconds and
   whether the turn ends cleanly; then answer the rest at the prompt.

State for these runs is in `~/.local/state/aitasks/questions/questions.sqlite3`.
Remove the table from `.codex/config.toml` afterwards if it should not stay.

## Go/no-go — 2026-11-12

Two separate verdicts, as the plan requires.

- **Transport recovery: GO** for sequential single-choice and free-text forms on
  Codex 0.167.2 / `gpt-6-astra` / MCP `2025-06-18`. Form → timeout → composer →
  form, a server/connection restart with an accepted answer, and a second
  timeout after that restart all passed live, each with one receipt and no
  repeated question. Hardening and setup/launch integration may proceed.
- **Multi-select: GO for the text route**, revised later on 2026-11-12. An
  accepted page survived a live restart, and the dependency, guide and finding
  shapes each completed through the mapping's guidance with a mid-question
  timeout, with control rows kept out of the options and the stored selection
  exact. Native arrays remain unavailable on the negotiated protocol. The
  remaining inventoried callers use the same route and the same guidance but
  were not each run live.

Not measured live in any run: an outer `tool_timeout_sec` shorter than the
server deadline, long-question rendering, two concurrent Codex sessions.

## Decision as of 2026-11-11

**Experimental only; no shared mapping or setup rollout.** The durable store and
actual STDIO MCP process tests pass. The user completed the baseline real Codex
form → timeout → composer → form sequence, corroborated by its persisted receipt.
The paginated **text-form multi-select adaptation** also passed live recovery,
with all five selected IDs retained. Native multi-select was stopped by the
prototype's protocol guard; it was not rendered or validated. Retaining accepted
answers across a live restart, and across a second timeout after that restart,
passed live on 2026-11-12 for single-select questions (see the evidence table).
These passes alone do not permit rollout. Implementation remains incomplete.

This report precedes broad integration. The prototype is intentionally limited:
it cannot record a gate pass, commit, archive, or execute a workflow action.
Its completion receipt says `prototype_answers_only_not_workflow_authorization`.
The approved plan lives in
`aiplans/p2281_codex_mcp_questions_with_timeout_resume.md`.

## Implementation available for testing

- `.aitask-scripts/aitask_questions/store.py`: stdlib SQLite store with durable
  occurrence IDs, opening-key idempotency, exact local artifact fingerprints,
  immutable accepted answers, form-attempt deadlines, cancellation/defer,
  conflicting/duplicate answer handling and receipt invalidation.
- `.aitask-scripts/aitask_questions/server.py`: SDK adapter exposing ask, status,
  resume and cancel through STDIO; one sequential form per call. A server timeout
  returns `awaiting-chat-answer`, preserving pending question text/options and
  accepted answers. The model must end its turn and use explicit prompt recovery.
- `.aitask-scripts/aitask_questions/selection.py`: experimental paginated native
  multi-select and JSON text adaptation, sharing exact-ID validation and durable
  page accumulation. The text adaptation has passed live Codex validation for
  the three-page fixture; native arrays remain unverified.
- `.aitask-scripts/aitask_questions_server.py`: server entry point, started by
  `.aitask-scripts/aitask_questions_mcp.sh`.
- `tests/manual/codex_questions_probe.py`: a reproducible attended three-question
  fixture and one-off Codex launcher. It writes private test state and passes
  MCP settings as launch arguments; it does not edit any Codex config file or
  change sandbox/approval policy. It never types an answer for the human.

SQLite transactions serialize prompt/form answer races; old form generations
cannot cancel a newer form. An expired transport lease is recoverable from a new
process even if the original process died before handling cancellation.
An artifact mismatch invalidates the occurrence and receipt. Reopening a
checkpoint with a new opening key retires older occurrences even with identical
question wording and artifact bytes. Reconnection reuses the old occurrence.

Free-text intent cannot be authenticated or classified reliably by the store.
The resume tool requires a specific question ID and model-forwarded user text;
its instructions forbid consuming status requests/unrelated steering. Recorded
channels are `mcp_form` and `codex_prompt_model_forwarded`, not authenticated
identities. Choice validation rejects ambiguous labels and unrelated prose.

## Environment and observations

| Item | Observation / boundary |
| --- | --- |
| Installed CLI | `codex-cli 0.167.1`, measured locally |
| Intended live model | `gpt-6-astra`, recorded in the actual test launch arguments; runtime model switch not independently measured |
| Python | Local 3.14; prototype code uses Python 3.11+ features |
| SDK | `mcp==2.3.0`, installed only into `/tmp/aitask-2281-venv` |
| SDK test transport | Actual STDIO child process, not an in-process transport stub |
| SDK test negotiated protocol | `2025-11-25` |
| Elicitation | SDK test callback advertises form support; separate no-capability test returns `unavailable` without any answer |
| Codex negotiated protocol/capabilities | Text multi-select run persisted `2025-06-18`, elicitation `form: {}` and `url: {}`; baseline did not persist negotiation |
| Codex Default-mode UI/composer | Baseline passed by user report, corroborated by answer channels and timed-out q2 in the store |
| Real client reconnect | Passed live 2026-11-12 (Codex 0.167.2, `gpt-6-astra`, protocol `2025-06-18`): occurrence `8f6c70e5e61c4250b29dc00c01d09a8d`, receipt `64e28a36c65644fcaf2aa72ed3d37b1d`. q1 accepted by form in server pid 978290; q2 timed out after 20.011 s; Codex exited and resumed (Codex session `01a1cef9-3d5e-7190-bc1f-8dbe42afea69`); a new server process (pid 1115632, different process instance) accepted q2 from the composer and showed q3 without re-asking q1; one receipt. Channels form / model-forwarded prompt / form |
| Repeated timeout after reconnect | Not exercised in the run above (q3 was answered in its form after 5.5 s). Passed live in a second run 2026-11-12 (same CLI/model/protocol): occurrence `1a80ae43104c4f8192909a165f345e20`, receipt `51d3cda4e1904e529d7a3ffe9243c1e8`, Codex session `01a1cf01-c0fe-7653-a170-744c72810938`. q1 by form (pid 1247651); q2 timed out at 20.02 s; after exit/resume a new server process (pid 1288112) accepted q2 from the composer, showed q3, q3 timed out at 20.02 s, and q3 was accepted from the composer 13 s later. Channels form / model-forwarded prompt / model-forwarded prompt; one receipt; q1 never re-asked. Single-select only: multi-select was not part of either reconnect run |
| Multi-select | Text-form adaptation passed live; native probe returned `unsupported_shape` before rendering; shared mapping unchanged |
| Long-question rendering | Not tested |

The tools truthfully advertise writes to local durable state (`readOnlyHint:
false`); even status can expire a lease or invalidate stale approval state.
Host-owned tool approvals, if shown, are separate from the elicited questions.

### Deadlines

- The launcher explicitly sets Codex `tool_timeout_sec=60`, independent of the
  prototype server's default 20-second per-form `anyio.fail_after` deadline.
  A call shows only one form, so three questions do not multiply a single call's
  wait past the outer deadline. Server timeout is configurable up to 45 seconds.
- SDK 2.3.0 `ServerSession.elicit_form()` delegates to `send_request()` without
  an explicit SDK request timeout. Its JSON-RPC dispatcher uses
  `request_clock(opts.get("timeout"))`; the prototype supplies the independent
  outer AnyIO deadline. This is source inspection, not proof of all client timers.
- The Codex UI's independent elicitation timer and outer-cancellation behavior
  remain unmeasured. The baseline server-timeout returned control successfully.
  Raising `tool_timeout_sec` is not
  claimed to make a form live indefinitely.
- Process tests use a 0.3-second server timeout and deliberately withhold a
  response. Another test cancels the outer tool call after 0.2 seconds with a
  2-second server lease and verifies recovery from a fresh server process.

## Live baseline evidence

User reported all three answers with a completion receipt. Read-only inspection
of `/tmp/aitask-2281-live/questions.sqlite3` corroborated:

- Occurrence `54b80effffa04be4a8ba232bedad87fb` completed with receipt
  `c380d62bebda4e85881e9e3180685a41` and exactly three accepted-answer events.
- Color: `blue`, `mcp_form`; Name: `Sample Alpha`,
  `codex_prompt_model_forwarded`; Finish: `finish`, `mcp_form`.
- Question 2 reached its persisted deadline about **20.020 seconds** after its
  form started. Its prompt answer was accepted about **47.300 seconds** later;
  question 3 started immediately and was answered by form about **7.077 seconds**
  later. These are server event intervals, not independent UI frame measurements.
- No answer exists for timeout itself, and the first answer was not repeated.
- User report establishes composer usability; storage alone does not prove the
  exact visual rendering or independent client timer. Reconnection and a second
  timeout were not part of this reported run.

## Live multi-select evidence

User report and read-only inspection of
`/tmp/aitask-2281-live-multi-text/questions.sqlite3` agree:

- Occurrence `958213a338634f44b3ae9093683ddad6`, receipt
  `8f5b0ee4110547b28ea779d540d6e676`, complete with exactly three accepted-page
  events and one final accepted-answer event.
- Page 1 selected `task-1, task-3` with Next through `mcp_form`; page 2 selected
  `task-4, task-6` with Next through `codex_prompt_model_forwarded`; page 3 selected
  `task-7` with Finish through `mcp_form`. The final ordered set is exactly
  `task-1, task-3, task-4, task-6, task-7`.
- Launch configuration and every recorded transport event identify **text**
  mode. Form provenance here means the JSON text field, not native checkboxes.
  Protocol `2025-06-18` and form/url capabilities were persisted. Requested model
  was `gpt-6-astra`; server deadline 20 seconds, outer deadline 60 seconds.
- The successful page-2 attempt expired after **20.021 seconds**. Its prompt
  answer arrived approximately **730.705 seconds** later; page 3 was then answered
  through the form in **2.800 seconds**. Timing comes from server events.
- An earlier page-1 attempt also timed out (20.022 seconds), followed by a new
  process instance before the successful page-1 answer. This establishes pending
  state survival and two deadline events, but does **not** establish survival of
  an already accepted selection across restart: all three accepted pages belong
  to the later process instance.

The separate native fixture `/tmp/aitask-2281-live-multi` has no accepted answers
or receipt and records `unsupported_shape`. Its original rejection did not
persist negotiation details, so the text run's observed protocol is not claimed
as independently recorded native negotiation. The adapter now persists these
details on native protocol rejection too, with a matching older-protocol test.
No conclusion about native checkbox rendering follows from this guarded stop.

Decision: use the demonstrated text adaptation as the candidate Codex multi-select
route. Do not retry native arrays on an older protocol or claim native parity.
Complete accepted-answer reconnect/repeated-timeout validation and caller-level
adapters before enabling that route in the shared mapping.

## Automated evidence

Run from the repository root:

```bash
python3 -W error::ResourceWarning tests/test_aitask_questions.py
python3 -W error::ResourceWarning tests/test_aitask_questions_selection.py
/tmp/aitask-2281-venv/bin/python tests/test_aitask_questions_mcp.py
```

Current results (2026-11-12): **28 store, 9 selection and 13 transport/launcher
tests pass**, plus 37 setup/launcher assertions in
`tests/test_setup_questions_server.sh` and 62 gate-guard assertions in
`tests/test_gate_codex_approvals.sh`.

Store coverage includes repeated timeouts, restart, stable reconnect receipts,
revision before answer, edited/missing artifacts after receipt, identical-content
new occurrences, immutable answer provenance, late/conflicting forms, stale
cancellation, concurrent submissions, ambiguous choice input, defer/cancel,
project/run isolation and explicit rejection of unknown question shapes.

The MCP tests verify these distinct flows:

1. First answer by form; timeout on question 2; fresh server process; question 2
   reconciled as prompt input; timeout on question 3; another process; final
   prompt input completes once with the previous answers intact.
2. First answer by form; timeout on question 2; fresh process; prompt answer for
   question 2; question 3 returned and answered as an MCP form. No repeated q1.
3. A client with no elicitation capability returns `unavailable`, still pending.
4. Outer tools/call cancellation preserves the question through process restart.
5. Ambiguous/unrelated prompt input returns the pending question without an answer.
6. An artifact edit during actual elicitation invalidates the returned answer.
7. The prepared launch preserves the venv executable and ordinary security policy.
8. Client decline, cancel and an accepted-but-empty form create no answer/receipt.
9. Native arrays and JSON-text selection both preserve the complete set across
   three pages, fresh processes and two timeouts. Page 1 selects multiple IDs;
   subsequent prompt submissions retain punctuation and canonical candidate order.
10. JSON-shaped free text reaches validation unchanged, including `null`, `true`,
    arrays and duplicate object fields. SDK 2.3.0 pre-parses strings for union
    annotations; the resume argument uses plain `str` to avoid this conversion.
11. A real `2025-06-18` handshake stops native arrays before any form is emitted,
    persists negotiation evidence, and retains the unanswered occurrence.
    Explicitly reconnecting with the text adapter completes that same occurrence.

Selection-store tests cover explicit all/none, early finish, min/max cardinality,
duplicate/conflicting page replay, late form attempts, malformed/unknown/off-page
IDs, missing page identity and candidate-universe revision. These exercise the
protocol; downstream skill adapters and their result consumers remain untested.

These callbacks supply synthetic responses. They are explicitly **not** human
consent, real Codex UI evidence, model willingness evidence, or live acceptance.

## Reproduce the human live checkpoint

The prepared fixture is `/tmp/aitask-2281-live` (keep it for recovery). Its question
session ID is in `launch.json` and the SQLite store. If the temporary environment
has been removed, recreate it:

```bash
python3 -m venv /tmp/aitask-2281-venv
/tmp/aitask-2281-venv/bin/pip install 'mcp>=2.3,<2.4'
```

In a **separate terminal** from the implementing agent, run:

```bash
python3 tests/manual/codex_questions_probe.py \
  --python /tmp/aitask-2281-venv/bin/python \
  --state-dir /tmp/aitask-2281-live --model gpt-6-astra
```

`--prepare` prints the exact command without launching. There is no `/plan`
injection or built-in question-tool dependency. The configured Codex host retains
its ordinary policies; the launcher uses `--no-daemon` for an isolated MCP process
and `--no-alt-screen` for readable terminal history.

1. Confirm the client is in Default mode, record version/model, and inspect
   `/mcp` if needed to verify the four probe tools are connected.
2. Answer **question 1 (color)** through the form.
3. Leave **question 2 (sample name)** unanswered for at least 20 seconds. Record
   whether the form closes and whether the model ends its turn with the pending
   question and question-session ID. The ordinary composer must become usable.
4. At the composer, type a sample name explicitly, e.g. `Sample Alpha`. Confirm
   that resume associates it with question `name` and opens **question 3** as a
   form. Answer question 3. Verify color is retained and the three answer
   channels are form / model-forwarded prompt / form. No real workflow continues.
5. Repeat using a **different state directory**, e.g.
   `/tmp/aitask-2281-live-reconnect`. After q2 times out, exit Codex normally,
   retain its Codex session ID, then restart with the same state directory and
   `--resume <codex-session-id>`. This is a new MCP process/connection. Supply q2
   through the composer; let q3 time out too, then answer q3 in the composer.
   Verify both earlier answers persist and exactly one receipt is returned.
6. For an outer-client-timeout run, use another new state directory and
   `--timeout 30 --outer-timeout 5`. Observe the actual client behavior; do not
   equate this with the inner server-timeout result. After an orphaned attempt's
   lease expires, status can reconcile it without keeping the original call alive.
7. Exercise cancel/defer, an unrelated status request while an answer is pending,
   and ordinary free-text form submission in separate runs. Record failures
   verbatim and distinguish blocked capability, transport error, user cancellation
   and timeout. Never silently fill unanswered test steps.

Expected measurements: CLI/model, relevant launch settings, returned `transport`
protocol/capabilities/timings, actual rendered controls, elapsed time until the
composer returns, tool call/answer order, and the final persisted answer channels.
Only include non-sensitive probe messages when recording captures.

### Multi-select live checkpoint

To repeat the demonstrated text-adapter path, use a new state directory:

```bash
python3 tests/manual/codex_questions_probe.py \
  --python /tmp/aitask-2281-venv/bin/python \
  --state-dir /tmp/aitask-2281-live-multi-new --model gpt-6-astra \
  --scenario multi --multiselect-mode text
```

On page 1 submit `{"selected":["task-1","task-3"],"action":"next"}`.
Leave page 2 unanswered until
timeout; enter `{"selected":["task-4","task-6"],"action":"next"}` at the composer.
On page 3 submit `{"selected":["task-7"],"action":"finish"}` through the form.
The final ordered selection must be exactly
`task-1, task-3, task-4, task-6, task-7`, with page channels form/prompt/form.
A timeout or empty form is never an explicit empty selection. Native mode remains
an exploratory alternative (`--multiselect-mode native`, separate new directory)
and requires newer negotiated protocol plus observed checkbox rendering.

For the remaining process-restart check, retain the same directory and restart
with `--resume <codex-session-id>` after page 2 times out. Supply page 2 at the
composer; let page 3 time out as well, then answer it there. Verify the original
page-1 form selection survives the process change, with the same final set and
one receipt. Never change the candidate fixture mid-occurrence.

## Caller compatibility inventory

Canonical sources below are under `.claude/skills/`. No source, rendered variant
or shared mapping has been switched. Every replacement is still **blocked** on
live compatibility and caller-level result assertions.

| Caller | Existing semantics and required result | Migration boundary |
| --- | --- | --- |
| `aitask-create/SKILL.md` §3c–3d | Active task IDs; siblings first, then parent-level tasks; explicit None; a separate sibling-dependency choice may add one ID. Validate every selected task exists. | Preserve the entire dependency list and sibling IDs. None must be a control, never a dependency or combined with IDs. Source has no explicit pagination/fallback here. |
| `aitask-review/SKILL.md.j2` §1b | Guide relative paths are identities; displayed names/descriptions and relevance order; 3 guides plus Show more, last page up to 4; accumulated selections feed guide loading. Profile defaults bypass the prompt. | Preserve every selected path across pages and duplicate guide names; no loading/review before completed selection. |
| Same, §3 | Finding IDs, labels and file/line/severity descriptions; accumulated pages and Select all; empty selection ends review; selected findings feed task creation. | All means the original entire finding set. Keep navigation separate. Existing wording can exceed four options when all/next are included; adapter must not truncate. |
| `aitask-work-report/SKILL.md` | Columns select inclusion, tasks select exclusion. Selecting items plus Show more retains items and advances. Unvisited columns remain excluded; unvisited tasks remain included. Results use canonical gatherer order. | Preserve inclusion/exclusion distinction and validate IDs before subtraction. Existing one-text-answer fallback stays available; opaque column IDs keep prefixes, task IDs alone permit `t` normalization. |

Additional canonical call sites inspected:

| Source | Shape, controls and downstream boundary |
| --- | --- |
| `aitask-revert/SKILL.md.j2` §3b | Child IDs plus optional parent-level commits; All children and comma-separated Other for larger lists. Area paths allow free-text file refinements. Unselected items are kept; a separate confirmation permits adjustment. A fixed-ID selection alone cannot replace the refinement path. |
| `aitask-contribute/SKILL.md` §2–3 | Paginated area names and file paths; hierarchical sub-areas; Use all applies to one subtree; Other triggers custom path/description input. Persist each scope separately, preserve all selected files, and retain custom-path follow-up. |
| `task-workflow/related-task-discovery.md` §4–5; `aitask-pr-import/SKILL.md.j2` §4 | Eligible task IDs behind filename labels; related discovery accumulates pages; None/empty returns no folds. PR import has no explicit pagination. Never fold before complete selection; preserve eligibility filtering. |
| `task-workflow/SKILL.md` note discovery; `planning.md` verification sibling | Note recipients paginate at four, each with evidence and qualified project identity; dispatch uses bare NOTE_TARGET plus project separately. Verification-child selection becomes the full `--verifies` list. No note or verification task before completion. |
| `aitask-pick/SKILL.md.j2` §1 | Label set plus Show all/no filter; selected labels feed `-l`. No explicit pagination. Control must not become a label. |
| `aitask-wrap/SKILL.md.j2` files/plans | Changed paths grouped by status, accumulated pages. Separate plan selection intentionally limits candidates to three recent plans plus None; use plan paths as IDs despite duplicate/truncated titles. Do not expand that caller's candidate universe silently. |
| `aitask-reviewguide-import/SKILL.md` §7 | Repository file IDs, Import all and Show more, accumulated pages; fetch/process only the final selected set. Budget page controls separately from items. |
| `aitask-refresh-code-models/SKILL.md`, `supersession-lineages.md` | Agent IDs plus All; later per-agent change IDs. Lineage edges/chains require explicit selection, four per page; unselected edges are dropped, confirmed chains applied oldest first. Candidate/action binding must include every edge, not just its label. |
| `aitask-explain/SKILL.md`; brainstorm `discuss-explain.md`; shadow `plan-explain.md` / `plan-diagnose-errors.md` | Three explanation modes; dynamic subjects plus All/None; concern IDs plus None. Brainstorm has an Other path for additional subjects. Selected concerns only lead to a separate offer, never automatic task creation. |
| `aitask-gate-docs-updated/SKILL.md`; `aitask-docs-gap/SKILL.md` | Unknown changed paths with attribution evidence; docs gap IDs with target pages. Include all/subset; empty gap selection ends without creating a task. Preserve the distinct subsequent review/confirmation steps. |
| `aitask-audit-wrappers/SKILL.md` | Selected gaps or MISSING touchpoint/helper pairs, batched at four; apply only the complete selected pairs. |
| `aitask-learn-skill/generate.md` | Procedure IDs plus “whole thing as one skill”. Whole is a grouping choice, not merely select-all; preserve grouping in a separate action parameter. |
| `aitask-add-model/SKILL.md` | Promotion-operation keys read from config `.defaults`; only selected operations receive a new default. Candidate revisions must follow that config snapshot. |

Rendered default/fast review variants still carry multiSelect and the shared
mapping still aliases to `request_user_input` without a multi-select adaptation.
Work-report has an explicit text fallback. Complete rendered-variant audits and
caller-result tests are still required; this inventory does not establish a
working replacement for every caller. Chatlink's separate transport is unaffected.

The prototype pages store immutable accepted submissions, an accumulator and page
IDs tied to the occurrence. Next accepts the current page and advances; Finish
accepts it and completes; All/None require an empty individual selection. Missing
content never becomes None. Final values retain original candidate order. An
unsupported native protocol returns `unsupported_shape` and keeps the question
pending. Text adaptation is explicitly selected, never silently substituted.

## Blocking work remaining after the transport checkpoint

**Approval freshness.** The prototype hashes exact local plan bytes and handles
occurrence invalidation. The store-side action guard now exists (2026-11-12):
`Store.consume(session, receipt, consumer)` re-proves freshness inside the
claiming transaction and claims a receipt for exactly one consumer key;
`Store.snapshot()` returns the approved bytes captured in the same read that
was fingerprinted, so a consumer acts on the immutable snapshot and never on a
later read of the live file; `Store.acknowledge()` records that the effect
exists. A repeated claim by the same consumer returns `duplicate` with the
original record — the caller reconciles a crash between claim and effect by
checking `acknowledged` and then the effect itself; the store does not make an
external git effect exactly-once. Covered: unanswered/foreign/stale receipts,
revision before consumption (including revert), a writer after the claim,
eight concurrent consumers, a missing artifact. **Still missing:** no workflow
caller uses the guard, semantic task-requirement manifests, and gate re-entry
integration. No receipt authorizes real work until those exist.
The code gate digest excludes plans; it is not an approval-revision witness.

**Multi-select.** Native and text adaptations pass synthetic process tests, and
the text adaptation has passed the live three-page recovery fixture. Native
rendering, accepted-selection survival across live restart, and downstream caller
migration remain pending. Do not route existing callers through the prototype.
Finish the inventory above, inspect rendered attended variants, and test their
exact consumers before switching.

For each caller, require native multi-select evidence or a tested adapter that
preserves all IDs, descriptions, pagination, accumulated selections, all/none,
canonical order, and timeout/prompt/MCP recovery. Work-report's existing fallback
explicitly rejects per-item yes/no emulation; its text presentation must also
meet the host's constraints. Preserve working routes during migration. An
unsupported shape blocks migration rather than losing choices or inferring an
empty selection. The initial three-question pass alone does not permit rollout.

**Other hardening.** Diagnostic negotiation/process/timing history now persists;
bound runtime
history/retention, finalize session identity across framework launches/worktrees,
test malformed client responses and crashes at write boundaries, and handle
candidate-universe changes. Complete the consumer race tests, setup/launch
integration, canonical mapping/template updates, monitor recognition and docs
only after the approved checkpoints. Current core tests are not full acceptance.

## Upstream references checked

- [OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp): local
  STDIO, trusted project configuration and tool timeout settings. Documentation
  does not establish the live recovery behavior.
- [Codex Security question server](https://github.com/openai/codex-security/blob/4aa9acc5ce459ae0f525c88f727713694597a7ad/plugins/codex-security/mcp-app/server.ts):
  form capability check, labelled single-choice schema, bounded elicitation and
  explicit non-accept handling. Its 14-minute SDK wait and unavailable fallback
  are reference behavior, not this prototype's lifetime/recovery contract.
- [Python SDK v2.3.0](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0):
  source inspected alongside the installed version for MCPServer, form elicitation,
  session callbacks and request clocks.
- [MCP 2025-11-25 elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation):
  native array/enum form schema. Specification support does not prove Codex UI support.
- [Instruction conflict #53829](https://github.com/openai/codex/issues/53829) and
  [async UI lifetime #54136](https://github.com/openai/codex/issues/54136): distinct
  reported concerns; neither is taken as proof of native elicitation compatibility.
- [Default-mode timeout #37472](https://github.com/openai/codex/issues/37472) and
  [explicit blocking PR #36410](https://github.com/openai/codex/pull/36410): built-in
  user-input lifetime context. No unverified `default_mode_is_blocking` setting is
  used, and no custom Codex fork is introduced.
