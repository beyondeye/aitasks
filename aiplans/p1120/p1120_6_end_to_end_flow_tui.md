---
Task: t1120_6_end_to_end_flow_tui.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_7_chatlink_docs.md, aitasks/t1120/t1120_8_manual_verification_discord_bug_report_channel_integration.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_1_*.md … p1120_5_*.md
Worktree: aiwork/t1120_6_end_to_end_flow_tui
Branch: aitask/t1120_6_end_to_end_flow_tui
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-09 11:09
---

Contracts: parent plan §PINNED — **FROZEN as of t1120_1** (verified 2026-07-09).
Plan re-verified against the landed t1120_1..5 code on 2026-07-09; the original
draft predated t1120_3/5 and is superseded by this version.

# Plan: t1120_6 — End-to-end flow + minimal TUI

Deliverables, the fail-closed payload-validation contract text, and the pinned
reactions vocabulary (⏳ working · ❓ awaiting answer · ✅ task created ·
❌ failed/denied) are in the task file. All five prior children landed; this
plan consumes their seams as they actually exist (verified):

**What already works (do NOT re-implement):**
- Intake (`chatlink/intake.py:190` `_open_session`) already does the full
  pinned launch order: thread creation → spool mint → record persist (state
  `spawning`) → `bug_report.md` write → `make_workspace_copy` →
  `SandboxSpec` build → `launcher.launch(spec)`. `serve()` (daemon.py:671)
  already resolves the production agent argv via engine dry-run.
- Select interactions are handled end-to-end (`_handle_interaction`,
  intake.py:287): `policy.may_answer` gating → `assemble_answer` → atomic
  `write_answer(overwrite=False)` → outcome persist → component disabling.
- The death path is **live**: `DockerLauncher` watchdog fires
  `spec.on_death` → `death_q` → `_handle_agent_death` (daemon.py:583) →
  `reconcile.plan_agent_death_actions` (fail-closed: cancelled answers,
  MARK_FAILED, ❌, relay-dir removal) → phase-disciplined `ActionExecutor`.
  Terminal records no-op by construction (supersession guard,
  reconcile.py:188). The flow must NOT duplicate any of this.
- `run_startup_reconciliation` + `reap_orphans` + `run_reconnect_reconciliation`
  exist; crash-ownership is already owned by daemon.py/reconcile.py.

**What t1120_6 adds (the actual gaps, each verified as absent):**
pump (spool→post), free-text modal + pagination (currently `MSG_DEFERRED`
stubs at intake.py:321-326), launch-handle retention (return value dropped at
intake.py:267), payload validation + task creation + `./ait git` (absent
everywhere), `awaiting_payload`/`done` state transitions (declared in
sessions_store.py:35, never set), ⏳/❓/✅ reactions (only ❌ wired),
`env_allowlist` sourcing (hardcoded `{}` at intake.py:258), the Textual TUI +
registry entry (none exist).

## Step 1 — LLM-key env passthrough (contract 10; t1139 coordination)

Pinned surface (t1139 extends this — do not invent per-provider keys here):

- **Config key:** `sandbox_env_passthrough` in
  `aitasks/metadata/chatlink_config.yaml` — a YAML list of env-var **names**
  (e.g. `[ANTHROPIC_API_KEY]`). Default `[]`.
- **Load-time validation** (`chatlink/config.py`, same fault-tolerant loader
  treatment as existing keys): must be a list of strings each matching
  `^[A-Z][A-Z0-9_]{0,63}$`; any invalid entry → drop the entry, audit
  warning, keep the rest (mirrors the loader's per-key degradation).
  Values NEVER live in the config file.
- **Launch mapping** (`chatlink/intake.py:258`): at launch time resolve each
  configured name from the **gateway process environment**
  (`os.environ.get`) and build
  `SandboxSpec.env_allowlist = {name: value for present names}`. Replace the
  hardcoded `{}`.
- **Degradation:** a configured name absent from the gateway environment →
  audit **warning** (`env passthrough: NAME not set — skipped`) + skip; the
  launch proceeds. Never a launch blocker (the agent fails visibly in-thread
  if it truly needed the key; the ceiling/failure paths already handle that).
  Empty config list → `env_allowlist={}` exactly as today.
- **Required test** (in `tests/test_chatlink_flow.sh`): with
  `sandbox_env_passthrough: [FOO_KEY, MISSING_KEY]` and `FOO_KEY=secret` set
  in the test environment, drive an authorized intake with `FakeLauncher`
  and assert `launcher.launched[0].env_allowlist == {"FOO_KEY": "secret"}`
  plus an audit warning naming `MISSING_KEY`. Negative control: unlisted
  gateway env vars (e.g. a planted `BOT_TOKEN_X`) never appear in the spec.

## Step 2 — flow orchestration (`chatlink/flow.py` + daemon wiring)

New module `chatlink/flow.py`, mirroring the reconcile.py style (pure
planners where possible; mutations only from the daemon loop).

**Handle retention:** intake stores `handle = launcher.launch(spec)` into a
daemon-owned in-memory registry `handles: dict[str, SandboxHandle]` (threaded
into `GatewayPipeline`). Popped on any terminal transition; used for
kill-on-payload-completion.

**Concurrency safety contract (binding — every invariant below gets a test):**

1. **Pure scanner, loop-only mutation.** The pump's background task is a
   pure **reader**: it scans spool dirs + records via `asyncio.to_thread`
   and its only write is `flow_q.put`. It NEVER writes a record, spool
   file, or platform state. Every record/spool/reaction/platform mutation
   for flow events executes inside the daemon's single sequential consumer
   (`run_daemon`'s `async for` over `_merged_events`), which already owns
   intake, interaction, and death mutations — one event at a time, awaited
   to completion. The pump is thus a producer for the same single-writer
   loop, not a second writer.
2. **Third merged source.** `flow_q` joins `_merged_events(stream, death_q)`
   (daemon.py:537) as a third source, exactly the death_q pattern. No new
   dispatch path.
3. **Re-validate at dispatch (supersession).** Scan results are stale by
   construction. Every flow-event handler re-loads the record and re-checks
   the spool inside the loop before acting: `question_ready` re-checks
   "answer absent ∧ seq not in question_messages"; `payload_ready` and the
   death signal both re-check "record non-terminal". A stale/duplicate
   event is a **no-op by construction** — same idempotent supersession
   guard as `plan_agent_death_actions` (reconcile.py:198-201). Exactly-once
   therefore comes from the loop-side guard, not from scan dedup.
4. **Terminal transitions are single-assignment.** Only the loop consumer
   assigns `done`/`failed`, and only after the non-terminal re-check; the
   completion sink and the death planner are the only two writers of
   terminal state, and both run in the loop. No answer/question mutation is
   possible after a terminal state (the re-checks precede every write).
5. **Bounded + fail-safe.** `flow_q` is bounded (drop + audit on overflow —
   the next scan tick regenerates anything dropped; scan is level-triggered,
   not edge-triggered, so lost events are always re-derivable from disk).
   A scan-tick exception is audited and skipped, never daemon-fatal.
6. **Test seam + negative controls.** The scan interval and clock are
   injectable. Required negative controls in Step 6: (a) `payload_ready`
   and a death signal for the same session dispatched back-to-back in both
   orders → exactly one terminal transition, correct one wins per re-check;
   (b) duplicate `question_ready` for the same seq → one post; (c) a flow
   event arriving after `failed` → no-op.

**Pump (spool→post):** a background asyncio task that every ~2s (injectable)
scans non-terminal sessions (`scan_one_session`, daemon.py:119, via
`asyncio.to_thread`) and enqueues flow events into `flow_q` per the contract
above. Events:
- `question_ready(sid, seq)` — question file present, answer absent, and
  `str(seq) not in record.question_messages` (the posted-marker; persisted by
  `post_question`). Handler: `GatewayPipeline.post_question` (reuse; already
  persists the marker + `asking` state) + status reaction → ❓.
- `payload_ready(sid)` — `payload.json` present and record non-terminal.
  Handler: the **completion path** below.

**Completion path (single shared sink `flow.complete_session`):**
1. Persist state `awaiting_payload` (audit).
2. Read payload dict (`SessionDir.read_payload`) → validate (Step 3).
3. Valid → create+commit task (Step 4) → persist `done` → kill retained
   handle (best-effort) → thread summary post (task id, title, file path) →
   status reaction ✅ → relay-dir + workspace-copy removal (mirror
   ActionExecutor phase order: persist → platform → remove-dir).
4. Invalid → persist `failed` (reason) → kill handle → ❌ + machine-readable
   reason in thread → audit → relay-dir + workspace-copy removal. **Nothing
   created, no fix-up** (contract 7 fail-closed).

**Death-path amendment (completion-vs-death race):** the watchdog fires on
*every* container exit — including successful completion. Amend
`_handle_agent_death` (daemon.py:583): before planning death actions, check
`payload.json` presence; if present and record non-terminal → route to
`flow.complete_session` instead of the fail-closed planner. Otherwise
unchanged. Both entry points (pump scan, death signal) converge on the same
sink; the terminal-state supersession guard makes the duplicate arrival a
no-op — assert this with a negative-control test.

**Un-stub deferred interactions** (intake.py:321-326; gating order —
`may_answer` before these — is already correct and must stay):
- free-text trigger → `adapter.open_modal(interaction, build_modal(question))`
  **immediately** (contract 5 — must beat the ~2s scheduled defer). Modal
  submit already routes through `assemble_answer` (COMPONENT_MODAL).
- page nav (`is_page_nav` → page N) → re-render
  `render_question(q, caps, page=N)` → `edit_message` on the stored question
  message with the new rows.

**Reactions-as-status:** small helper `set_status_reaction(adapter, record,
emoji)` — applied to the original bug-report message; removes the previous
vocab reaction (tracked in a new `SessionRecord.status_reaction: str = ""`
field — backward-compatible default), adds the new one, best-effort/audited.
Transitions: intake accept → ⏳; question posted → ❓; answer recorded → ⏳
(back to working); task created → ✅; any failure → ❌ (existing
`_thread_failure_note` / REACT_FAILED paths adopt the helper where they
touch the bug message).

## Step 3 — payload validation (`chatlink/payload_guard.py`)

`validate_payload(raw: dict | None, metadata_dir: Path) -> TaskPayload`,
raising `PayloadRejected(reason)` (machine-readable reason string for thread
+ audit). Ownership split pinned in relay.py:362-374 — start from
**`TaskPayload.from_dict`** (shared schema: required fields, **no extra
keys**, types, name slug ≤64, title ≤120, desc ≤64 KiB, priority/effort ∈
{high,medium,low} — all already enforced there; verified relay.py:426-442)
and layer the repo-authoritative checks on top:
- `issue_type` ∈ `aitasks/metadata/task_types.txt`
- `labels` ⊆ `aitasks/metadata/labels.txt` (must be enforced HERE —
  `aitask_create.sh` auto-adds unknown labels rather than rejecting)
- **Control characters: detect-and-reject, never sanitize.** Pinned
  semantics: `title` must contain no code point in Unicode category `Cc`
  (nor the zero-width/bidi-control formatting chars U+200B–U+200F,
  U+202A–U+202E, U+2066–U+2069); `description` allows exactly `\n` and
  `\t` and rejects every other such code point. Any hit ⇒
  `PayloadRejected("control characters in <field>")`. The gateway never
  creates a task from anything other than the byte-identical submitted
  values — silently sanitizing would accept a payload the agent never
  submitted. (Explicit strengthening of the contract-7 wording "control
  characters stripped": reject is strictly fail-closed where strip is a
  fix-up, which contract 7's "never partial creation or fix-up" clause
  itself forbids — decision confirmed in plan review 2026-07-09.)
Do NOT add validation inside `SessionDir.write_payload` (stays opaque
transport). No mutation/fix-up of rejected payloads.

## Step 4 — task creation plumbing (`chatlink/task_create.py`)

`create_task_from_payload(vp: TaskPayload, *, repo_root, session, audit) ->
CreatedTask` — argv-list `subprocess.run` (never shell), via
`asyncio.to_thread`:

```
.aitask-scripts/aitask_create.sh --batch --commit
  --name <vp.name> --priority <..> --effort <..> --type <vp.issue_type>
  --labels <csv> --desc-file -
```

stdin = description document: `## <title>` heading + `vp.description` +
provenance footer (chatlink session id, initiator tag). cwd = the gateway's
repo root (agent has no git access — gateway identity, contract 7).
`--commit` internally uses `task_git` (aitask-data-branch safe — verified
task_utils.sh:168). **Parse the `Finalized: <path> (ID: <id>)` success line**
(NOT `Created:` — that only appears on the non-commit draft path;
aitask_create.sh:788). Then best-effort `./ait git push` (audited, non-fatal).
Script path + git argv injectable for tests (spy seam).

## Step 5 — minimal chatlink TUI

Read `aidocs/framework/tui_conventions.md` + `aidocs/framework/tmux_gateway.md`
first (done at planning; re-skim at implementation).

- `chatlink/chatlink_app.py` — the ONLY module importing Textual. Single
  screen: daemon-activity line (derived read-only from audit-log mtime),
  session DataTable (id, state, initiator tag, age), audit tail. Read-only
  over `SessionsStore` + audit file via `set_interval` refresh; no daemon
  commanding, no tmux calls. Include an argparse `--smoke` flag (applink
  pattern, applink_app.py:571).
- Launcher dispatch in **bash** (`aitask_chatlink.sh`, mirroring
  `aitask_monitor.sh --headless-for-applink`): `--headless` → existing
  `python -m chatlink.daemon --headless` (yaml+discord preflight only);
  no flag → preflight `textual` too and `exec python -m chatlink.chatlink_app`.
  Keep `daemon.main()`'s refusal (defense in depth) but update its message
  ("run `ait chatlink` for the TUI"). The no-Textual-in-daemon guard
  (tests/test_chatlink_daemon.sh:36) must stay green.
- Registration is a **four-part atomic change** (tui_conventions.md) plus one:
  1. `lib/tui_registry.py` `TUI_REGISTRY` row
     `("chatlink", "Chat Link", "ait chatlink", True)` (functional grouping
     position, near applink).
  2. `lib/tui_switcher.py` `_TUI_SHORTCUTS`: letter `l` (free; taken set is
     b,m,c,s,t,y,g,a).
  3. Matching `Binding` in `_QUICK_JUMP_BINDINGS`.
  4. `action_shortcut_chatlink()` calling `self._shortcut_switch("chatlink")`.
  5. Add `chatlink/chatlink_app.py` to `KNOWN_BINDING_SOURCES` in
     `lib/shortcut_scopes.py` (else tests/test_shortcut_scopes.py fails).

## Step 6 — e2e tests

`tests/test_chatlink_flow.sh` — copy the `test_chatlink_daemon.sh` harness
(MockChatAdapter + FakeLauncher + `_mk_fixture_repo` + Clock seam + fake
audit). Cover every task-file Verification bullet:
- Authorized message → thread → Q&A round-trip: select answer AND free-text
  (button → `open_modal` asserted → modal submit) → valid payload → create
  invoked → summary + ✅. Create-script invocation verified via a **spy
  script** (fixture bin) asserting exact argv, stdin document, and that the
  gateway parses the `Finalized:` line.
- **Real-create integration path (narrow, one test):** run
  `create_task_from_payload` against the REAL
  `.aitask-scripts/aitask_create.sh --batch --commit` with cwd = a fixture
  git repo seeded with `aitasks/metadata/{task_types.txt,labels.txt}` and an
  initial commit (verified feasible: `TASK_DIR` is cwd-relative,
  aitask_create.sh:15; `aitask_claim_id.sh` supports no-remote local-only
  counter branches, claim_id.sh:7-9; legacy mode → `task_git` = plain git).
  Assert: task file exists under the fixture's `aitasks/` with the
  validated frontmatter + description, a real commit landed
  (`git log --oneline` contains `ait: Add task`), the `Finalized:` line
  parsed to the right id, and the best-effort `./ait git push` failure
  (no origin) is audited and non-fatal. This exercises the true cwd,
  stdout-parsing, and commit behavior the spy cannot. Live-Discord + real
  sandbox remains t1120_8's MV scope.
- Unauthorized user → ignored/ephemeral, no spawn (negative control).
- Non-initiating user's interaction → ephemeral rejection, question stays
  pending (answer file absent).
- Malformed payloads (bad issue_type, label ∉ labels.txt, oversize
  description, extra keys, control characters in title/description —
  including a bidi-control char) → fail-closed: `failed` state, ❌ +
  reason, audit entry, spy script NEVER invoked.
- Multi-session concurrency: two in-flight sessions, answers route by
  custom_id session_id, no cross-talk.
- Crash-restart-reconcile: drop the daemon tasks mid-question, rebuild over
  the same store with `FakeLauncher(live_session_ids=∅)`, assert reaped +
  session failed + cancelled answers (per crash-ownership).
- Completion-vs-death negative control: death signal arriving after
  completion persisted → no-op (supersession guard); death with payload
  present → completion path, not failure.
- Reactions vocabulary asserted at each state transition.
- Pagination: >25-option question → page nav re-renders via edit_message.

`tests/test_chatlink_tui.sh` — `--smoke` exit-0 + one Textual `run_test()`
Pilot render assertion on the session table (test_applink_devices.sh
pattern). Existing suites (`test_chatlink_daemon.sh`, `test_no_raw_tmux.sh`,
`test_shortcut_scopes.sh`) must stay green.

## Step 7 — Step 9 reference

Post-implementation follows task-workflow Step 9 (gates run, archival).
Last feature child before docs (t1120_7); coordination reverse-pointers:
t1139 extends the Step-1 config surface, t1140 builds on the e2e glue.

## Risk

### Code-health risk: medium
- Daemon-loop integration (third merged-event source + death-path amendment) touches the load-bearing sequential-dispatch core; a pump mutating outside the loop or double-handling death would corrupt session state · severity: medium · → mitigation: chatlink_flow_concurrency_soak
- `SessionRecord` schema growth (`status_reaction`) and intake signature changes (handles registry, env passthrough) ripple through existing tests · severity: low · → mitigation: TBD
- TUI switcher registration is a 5-file coordinated change · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- Completion-vs-death race: watchdog fires on every container exit, so a missed payload check misclassifies successful sessions as failed · severity: medium · → mitigation: chatlink_flow_concurrency_soak
- Mock-based tests cannot validate real-Discord timing (modal 2s defer window, reaction semantics) — residual risk explicitly deferred to the existing MV sibling t1120_8 · severity: medium · → mitigation: TBD
- `sandbox_env_passthrough` shape must satisfy t1139 extensibility; wrong shape means rework in the dependent task · severity: low · → mitigation: TBD

### Planned mitigations
- timing: after | name: chatlink_flow_concurrency_soak | type: test | priority: medium | effort: medium | addresses: daemon-loop sequential-dispatch races + completion-vs-death misclassification | desc: Soak/stress test — N concurrent mock chatlink sessions with randomized event interleavings and repeated daemon kill-restart cycles over the same store, asserting no cross-talk, no double terminal transitions, and correct completion-vs-death routing
