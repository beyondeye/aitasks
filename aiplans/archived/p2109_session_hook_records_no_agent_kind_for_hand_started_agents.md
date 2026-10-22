---
Task: t2109_session_hook_records_no_agent_kind_for_hand_started_agents.md
Base branch: main
Output branch: main
---

# t2109 — Record the agent kind of hand-started agents; refuse a resume whose kind is unknown or conflicts

## Context

The SessionStart hook (`.aitask-scripts/aitask_session_hook.sh`) records the
session with `--agent-string "${AITASK_AGENT_STRING:-}"`. An agent started by
hand has no `AITASK_AGENT_STRING`. A blank string is a no-op in the store
(t1802), so the record gets `agent_string=""` and therefore `agent_kind=""`.
`agent_restore.build_resume_argv` then resolves the project's `raw` default,
which is `claudecode/*` in the shipped config. A hand-started agent of another
kind therefore restores with the wrong CLI, for example `claude --resume
<codex-id>`, or `codex resume <claude-id>` in a codex-default project.
t2077 closed only the codex half, and only at freeze time.

**User decision (planning Q&A):** take the kind from the payload's **transcript
shape**, only when the path names the payload's own session id. **Preserve an
explicit agent identity.** **Refuse a resume when the kind is unknown or
conflicts with the CLI the restore would launch.** Test those cases.

**Measured shapes.** The committed interactive fixtures are
`tests/data/session_hooks/{claude,codex}_sessionstart.json` (claude 2.1.263,
codex 0.163.0). Every one of the ~30 live store records on this machine
(claude 2.1.304, codex 0.163.0, 2026-10-21) has the agent kind its transcript
shape predicts:
- claude: `<cfg>/projects/<encoded-cwd>/<session_id>.jsonl`
- codex: `<codex_home>/sessions/YYYY/MM/DD/rollout-<ts>-<session_id>.jsonl`

## Design

**Meaning of `agent_kind` after this change:** the kind of the agent whose
**current** session the record holds, and only when the call that recorded that
session carried evidence for it.
- An explicit agent string supplied in a call still decides the kind, as today.
- A transcript-inferred kind (`--agent-kind`) sets the kind and **never clears a
  stored explicit `agent_string`**: the explicit identity is preserved.
- If the inferred kind disagrees with a stored explicit string, the record keeps
  both, so `agent_kind` differs from `agent_kind_of(agent_string)`. That
  conflict stays visible, and the restore refuses it.
- **Evidence is bound to its session** (fixes the review's "unknown-session
  replacement" finding). When a call records a session id **different from the
  stored one** and carries no kind evidence (no agent string, no
  `--agent-kind`), the kind is **cleared**. The stored explicit string stays
  untouched, since it is preserved, but it no longer authorises a resume. So
  neither a claude record's old evidence nor its explicit string can authorise
  `claude --resume <unidentified id>`. The freeze engine's codex capture then
  treats the record as unlabelled, as t2077 intended, instead of skipping it as
  a claude record. A call that re-reports the **same** id without evidence
  changes nothing (t1802/t1807 keep holding).

**Restore rule:**
- The CLI to launch is `agent_kind_of(rec.agent_string)` when a string is
  stored. Otherwise it is the kind of the project's resolved `raw` default.
- A resume is refused when `rec.agent_kind` is blank (`unknown_agent`), or when
  it differs from that CLI (`agent_mismatch:<record kind>:<launch kind>`).
- The refusal comes before anything is written, and re-pick is unaffected.

**Hook rule:**
- If `AITASK_AGENT_STRING` is well-formed and names a kind other than the
  transcript kind, the hook records **nothing** (an early `exit 0`: no upsert,
  no `@aitask_record` stamp, no `@aitask_agent_session`). This is the nested
  case, for example a `codex exec` run by a claude agent's Bash tool, which
  inherits claude's `AITASK_AGENT_STRING` and `TMUX_PANE`. Today it records the
  nested codex's session under `claudecode/*`.
- Otherwise the explicit string is sent unchanged, plus `--agent-kind <kind>`
  when the shape was recognised.

## Implementation steps

### 1. Hook — `.aitask-scripts/aitask_session_hook.sh`

- **Step 3 (payload parse, the inline `python3 -c`):** also emit a 5th
  NUL-delimited field, the transcript-shape kind. Change the field-count check
  from 4 to 5 and bind `payload_kind="${_fields[4]}"`. The classifier is
  string-only, with no new imports beyond `os`:
  ```python
  vals = [str(d.get(k) or "") for k in keys]
  sid, path = vals[0], vals[1]
  base = os.path.basename(path)
  kind = ""
  if sid and base == sid + ".jsonl" and \
          os.path.basename(os.path.dirname(os.path.dirname(path))) == "projects":
      kind = "claudecode"
  elif sid and base.startswith("rollout-") and base.endswith("-" + sid + ".jsonl"):
      kind = "codex"
  sys.stdout.write("\0".join(vals + [kind]) + "\0")
  ```
  A path that does not embed the payload's own session id gives `""` (no
  evidence).
- **New step 5c "agent identity",** after the process-tree guard (5b) and
  before anything is recorded:
  ```bash
  explicit_kind=""
  if [[ "${AITASK_AGENT_STRING:-}" =~ ^([a-z]+)/[a-z0-9_]+$ ]]; then
      explicit_kind="${BASH_REMATCH[1]}"
  fi
  if [ -n "$explicit_kind" ] && [ -n "$payload_kind" ] && [ "$explicit_kind" != "$payload_kind" ]; then
      echo "aitask_session_hook: AITASK_AGENT_STRING names $explicit_kind but the transcript is a $payload_kind session (an agent started inside another inherits its environment); nothing recorded" >&2
      exit 0
  fi
  ```
  The regex mirrors `agent_sessions._AGENT_STRING_RE`, with the same fullmatch
  semantics.
- **Step 7 (upsert args):** keep `--agent-string "${AITASK_AGENT_STRING:-}"`
  unchanged, and append `--agent-kind "$payload_kind"` only when it is
  non-empty. Update the step-7 comment.
- **Header:** add an `AGENT KIND` note block next to the CODEX TIMING / DAEMON
  ROUTING notes. It covers: the evidence (the transcript shape gated on the
  session id), the measured layouts and versions, that an explicit string is
  preserved, why a conflict refuses (the nested case), and that an
  unrecognised shape means "no evidence", so the restore re-picks.

### 2. Store — `.aitask-scripts/lib/agent_sessions.py` (+ usage comment in `.aitask-scripts/aitask_agent_sessions.sh`)

- Add `_AGENT_KIND_RE = re.compile(r"[a-z]+")` next to `_AGENT_STRING_RE` (the
  kind part of the same grammar).
- `upsert(..., agent_kind: str | None = None)`: validate first, before the
  restore branch and before any mutation:
  - a non-blank kind that fails the fullmatch → `ValueError("malformed
    --agent-kind …")`;
  - a non-blank kind that contradicts a well-formed `agent_string` in the same
    call → `ValueError`.

  `main` maps `ValueError` to exit 2 with nothing written, the same shape as the
  existing `clear_session_id` + `restore_of` refusal. Thread
  `agent_kind=agent_kind` into all five `_apply_upsert_fields` / `_create` call
  sites: late ack, in-grace ack, ambiguous-relocation create, selected update,
  plain create.
- `_apply_upsert_fields(..., agent_kind=None)`: decide whether this is a new
  session **before** applying the id:
  ```python
  new_session = (bool(session_id) and not clear_session_id
                 and session_id != rec.codeagent_session_id)
  ...  # session / session_id / transcript applied as today
  if agent_string:
      rec.agent_string = agent_string
      rec.agent_kind = agent_kind_of(agent_string) or agent_kind or ""
  elif agent_kind:
      rec.agent_kind = agent_kind   # inferred evidence; the stored string is preserved
  elif new_session:
      # Evidence belongs to the session it came with (t2109): an unidentified
      # replacement must not inherit the previous session's kind. The explicit
      # string is preserved, but without a kind it authorises no resume.
      rec.agent_kind = ""
  ```
  Extend the docstring with the t2109 meaning. A blank kind on the **same**
  session remains "not supplied", just as for the string.

  The other no-evidence callers were audited. The freeze fallback upsert sends
  the pane option's id. When that differs from the selected record's id, the
  kind is now cleared, and the restore re-picks; that is fail-safe, and the
  case needs the hook's own upsert to have failed. A repick-mode restore ack
  adopts a new id, but it always carries `AITASK_AGENT_STRING`, from the
  dry-run `env` prefix or the restore env. `_capture_codex_session` always
  sends a string or `--clear-session-id`.
- `main()` upsert: `agent_kind=_arg(rest, "agent-kind")`.
- Wrapper usage comment: add `[--agent-kind <k>]` with one explanatory
  paragraph.

### 3. Restore — `.aitask-scripts/lib/agent_restore.py`

- Import `resolve_agent_string` (from `agent_launch_utils`) and `resolver_env`
  (from `cross_repo_settings`). First check that this adds no import cycle.
- New helpers:
  ```python
  def _raw_agent_string(root: str) -> str:
      """The project's `raw` agent string, resolved with ITS config (a foreign root too)."""
      return resolve_agent_string(Path(root), "raw", env=resolver_env()) or ""

  def _resume_agent(rec: dict) -> tuple[str, str]:
      """(agent string the resume launches, blocker). t2109."""
      kind = rec.get("agent_kind", "")
      if not kind:
          return "", "unknown_agent"
      agent_string = rec.get("agent_string", "") or _raw_agent_string(rec.get("root", ""))
      if not agent_string:
          return "", ""            # unresolvable: build reports `binary`, as today
      launch = agent_sessions.agent_kind_of(agent_string)
      if launch and launch != kind:
          return "", f"agent_mismatch:{kind}:{launch}"
      return agent_string, ""
  ```
- `resume_blocker`: after the `no_session` and opencode checks, `return
  _resume_agent(rec)[1]`. Extend the docstring's reason list. `gone_line` (the
  `ait ide` offer) inherits the result automatically.
- `build_resume_argv`: `agent_string, blocker = _resume_agent(rec)`, and
  return `None` on a blocker or an empty string. Pass the string explicitly to
  `resolve_dry_run_command`, so the launch uses exactly the string that was
  checked: a string-less record no longer leaves the choice to the wrapper's
  own default resolution. Update its docstring.

### 4. Freeze backfill — `.aitask-scripts/lib/agent_freeze.py::_backfill_agent_string`

This is a consumer of the new invariant. With a stored session id, refuse the
recovered value when its kind is codex (the t2077 rule, unchanged), **or when
its kind differs from the stored `agent_kind`**, including a blank stored kind:
```python
if stored.get("codeagent_session_id", ""):
    recovered = agent_sessions.agent_kind_of(value)
    if recovered == "codex" or recovered != stored.get("agent_kind", ""):
        return
```
Otherwise a backfill would flip the kind to the pane process's kind and pair it
with a session recorded under another kind, or under none. Update the
docstring's second rule.

### 5. Frozenagent viewer — a read-only resume preflight (`.aitask-scripts/frozenagent/frozenagent_app.py::_start_restore`)

This addresses the review's "viewer refusal reporting" finding. The viewer
dispatches the coordinator detached (`run-shell -b`) and learns the outcome only
from the store. A preflight refusal writes nothing, so today it would surface
after `DISPATCH_GRACE` (10 s) as "restore did not start — run 'ait frozenagent'
or reconcile".

- Add `resume_refusal_note(blocker: str, task_id: str) -> str` to
  `agent_restore.py`, next to `resume_blocker`, so the vocabulary lives with its
  producer. It maps every `resume_blocker` reason to a sentence:
  - `no_session` → "no session was recorded for this agent";
  - `resume_unsupported:<k>` → "<k> cannot resume a session";
  - `unknown_agent` → "the agent CLI that ran this session is unknown";
  - `agent_mismatch:<rec>:<launch>` → "this is a <rec> session but the restore
    would launch <launch>";
  - an unknown reason → the raw blocker.

  Each sentence takes a suffix: "— re-pick it instead (P)" when
  `frozen_ops.usable_identifier(task_id)`, else "— it has no task id to
  re-pick". The full note is `cannot restore: <reason> — <next>`.
- In `_start_restore`, for `not repick`, after the existing pending, missing
  record and task-id checks and **before** `_pending` is set or anything is
  dispatched:
  ```python
  if not repick:
      blocker = agent_restore.resume_blocker(dataclasses.asdict(rec))
      if blocker:
          note = agent_restore.resume_refusal_note(blocker, rec.task_id)
          self._set_note(rid, note)
          self.notify(note, severity="warning")
          return
  ```
  The preflight is read-only and writes nothing to the store; the coordinator
  still runs its own `resume_blocker` at the execution boundary, so this is
  reporting, not the guard. Launch stays detached. `_pending` is never set on a
  refusal, so `R`, `P` and `k` stay available. Measured: `aitask_codeagent.sh
  resolve raw` takes 21 ms, and only string-less records run it, so the check
  is synchronous, like `_run_frozen`'s own tmux call, with no worker and no
  await. Import `agent_restore` into the app (it already imports
  `agent_launch_utils` and `monitor_core`, which `agent_restore` needs; check
  for a cycle first).
- The dispatch-time "original model unknown — restoring with the default
  model" note needs no conditional any more: a resume that reaches dispatch has
  passed the preflight, so for a string-less record the restore really does use
  the raw default's model.
- No other surface dispatches a restore. The monitors dispatch only `drop`
  detached (`monitor_shared._poll_frozen_outcome`). `ait frozenagent` prints
  the coordinator's `RESTORE_FAILED:<id>|<reason>` line directly, and `ait ide`
  shows the `gone_line` yes/no.

### 6. Docs (current-state only)

- `website/content/docs/concepts/framework-session.md`, "The session hook":
  one paragraph covering how the hook tells the agent kind of an agent started
  by hand (the transcript shape, only when it names the reported session), that
  an inherited agent string disagreeing with it records nothing, and that such
  an agent is restored only when the project's default agent for raw sessions
  is the same CLI.
  Also state that a new session reported without that evidence leaves the
  record's agent unknown, so it is re-picked.
- `website/content/docs/workflows/freeze-and-restore-agents.md`, the
  restore-needs paragraph (~l.75): add that an agent started by hand is resumed
  only when the project's raw default runs the same CLI, and is otherwise
  re-picked. The same applies when its CLI could not be told.
- `website/content/docs/tuis/frozenagent/how-to.md` (~l.59-64): the paragraph
  saying a missing session is reported as `restore did not start …` "because
  the coordinator runs detached" becomes: the viewer checks before dispatching
  and names the reason (no recorded session, an unknown agent CLI, or a session
  of another CLI than the restore would launch) with the re-pick hint. `restore
  did not start` remains only for a coordinator that never ran. Grep
  `website/content/docs/tuis/frozenagent/` for any other mention.
- Run `cd website && python3 check_links.py --build`.

### 7. Tests (each case asked for, plus every changed consumer)

- `tests/test_session_hook.sh`, new section `t2109: agent kind from the
  transcript shape`, using `run_hook` with `AITASK_AGENT_STRING=` (blank) and
  explicit cases:
  1. claude-shaped path, matching sid → `--agent-kind claudecode`;
     `--agent-string` empty.
  2. codex rollout path, matching sid → `--agent-kind codex`.
  3. Each shape with a **different** sid embedded → no `--agent-kind` (the gate).
  4. Each shape with no sid, and a plain `/t/a.jsonl` → no `--agent-kind`.
  5. Claude shape with the wrong grandparent (`/x/notprojects/d/<sid>.jsonl`)
     → no kind.
  6. Explicit `claudecode/opus5` + claude shape → the string is preserved and
     the kind is sent.
  7. Explicit `claudecode/opus5` + unrecognised shape → the string is
     preserved and no kind is sent (today's behaviour).
  8. Explicit `claudecode/opus5` + codex shape → `expect_refused`: no upsert, no
     stamps, and stderr names both kinds. Also the reverse (explicit `codex/x`
     + claude shape).
  9. A malformed explicit string + claude shape → no refusal; the string is
     forwarded verbatim and `--agent-kind claudecode` is sent.
  - The existing fixture loop runs each fixture with its own
    `_env_visible_to_hook.AITASK_AGENT_STRING` (it previously forced
    `claudecode/opus5` onto the codex fixture, which is now a conflict). Add a
    blank-env pass asserting that each captured fixture yields its own kind
    (claude → claudecode, codex → codex).
- `tests/test_agent_sessions_identity.py`, a new `AgentKindEvidenceTests`
  (after `BlankAgentStringTests`):
  - a kind-only create → kind set, string blank;
  - a kind-only update on a same-kind explicit record → both preserved;
  - a kind-only update on a conflicting explicit record → the string is
    preserved and the kind is the inferred one;
  - a later explicit string re-derives the kind;
  - a blank kind is a no-op;
  - malformed kind values (`"Codex"`, `"codex/x"`, `"a b"`) → `ValueError`
    with nothing mutated;
  - a contradicting string + kind in one call → `ValueError`;
  - an agreeing string + kind → accepted;
  - the in-grace restore ack applies the kind;
  - a CLI round trip (`main(["upsert", …, "--agent-kind", "codex"])`) persists
    it, and a malformed one exits 2 with the file unchanged.
  - **Unidentified replacement (review finding 1), required regressions:**
    - an explicit record (`claudecode/opus5`, id A) followed by
      `upsert(session_id="B")` with no string and no kind → string preserved,
      **kind cleared**, id B;
    - a kind-only record (`claudecode`, id A) followed by the same no-evidence
      `B` → kind cleared;
    - **controls:** re-reporting the **same** id A without evidence keeps the
      kind, for both record shapes, and a new id B **with** `--agent-kind codex`
      sets codex (the conflict stays visible on the explicit record);
    - the same sequence through `main([...])` on a real store file, so the CLI
      path is covered too.
- `tests/test_agent_restore.py`, a new `TestAgentKindGate`. `_raw_agent_string`
  is patched, so no test depends on the repo's config:
  - blank kind → `resume_blocker == "unknown_agent"`, and `restore()` returns
    `RESTORE_FAILED:<id>|unknown_agent` with **no store or tmux calls**;
  - a kind-only record whose raw default has the same kind → no blocker, and
    `build_resume_argv` passes the resolved raw string as `--agent-string`
    (`resolve_dry_run_command` patched and inspected);
  - kind-only + a raw default of another kind →
    `agent_mismatch:codex:claudecode`, nothing written;
  - an explicit string conflicting with `agent_kind` (the preserved-identity
    conflict) → `agent_mismatch:codex:claudecode`;
  - an unresolvable raw → no blocker, and `build_resume_argv` is `None` →
    outcome `binary`;
  - **an explicit string with a cleared kind** (the state an unidentified
    replacement leaves) → `unknown_agent`, nothing written, and
    `build_resume_argv` is `None`. This is the restore half of review finding 1;
  - `resume_refusal_note` covers each reason, with and without a usable task
    id.
  - `repick_blocker` / re-pick of a blank-kind record still run;
  - `agent_reopen.gone_line` reports the new resume reason.
  - Update `test_a_record_without_an_agent_string_delivers_only_the_four` to a
    **kind-only** record (`agent_kind="claudecode"`, string blank, raw
    patched), so it still tests "no string to deliver" rather than now hitting
    the refusal.
- `tests/test_agent_freeze.py`, two backfill cases: a stored id under kind
  `codex` + a recovered `claudecode/…` → no backfill; a stored id under kind
  `claudecode` + a recovered `claudecode/…` → filled. Add a blank-kind + id +
  recovered claude → no backfill. Re-check the existing backfill tests for one
  that encodes the old fill-a-blank-kind-id behaviour, and update it with a
  comment if so. **Freeze half of review finding 1:** a record holding an
  explicit `claudecode/opus5` string, a cleared kind and a codex id, with a live
  codex naming a mapped model, is captured as `codex/<model>` (no longer
  skipped as a claude record). With a codex naming no model, the id is cleared.
- `tests/test_frozenagent_app.py`, new `RestorePreflightTests`, with
  `agent_restore._raw_agent_string` patched:
  - an `unknown_agent` record with a task id → `R` dispatches **nothing**, the
    header note and notification name the unknown CLI and the re-pick hint,
    `_pending` is empty, `check_action("repick")` is True, and `P` then
    dispatches `restore <rid> --repick`. This is the "re-pick stays available"
    requirement;
  - an `agent_mismatch` record (explicit `claudecode/opus5`, kind `codex`) →
    the note names both kinds, nothing is dispatched, and `P` still works;
  - a kind-only mismatch (string blank, kind `codex`, raw patched to
    `claudecode/sonnet5_5`) → refused the same way;
  - a refusal on a record **without** a task id → the note says there is no
    task id to re-pick;
  - `no_session` → refused immediately with its sentence, instead of the 10 s
    "did not start";
  - a kind-only record whose raw default has the same kind → dispatched, with
    the default-model note.

  Update `_dispatch_notes("")`: its blank-kind record is now refused by the
  preflight. It keeps testing the t1850 note, but on a kind-only record
  (`agent_kind="claudecode"`, raw patched). The existing dispatch tests use
  `claudecode/opus5` records, which need no subprocess, and stay unchanged.

### Post-phase (risk mitigations)

1. [transcript_layout_agreement] Add a section `t2109: one transcript layout,
   two encodings` to `tests/test_session_hook.sh`. For each `captured` fixture
   in `tests/data/session_hooks/`:
   - run the hook with a blank `AITASK_AGENT_STRING` and assert that
     `--agent-kind` is that fixture's agent (`claude_sessionstart.json` →
     `claudecode`, `codex_sessionstart.json` → `codex`);
   - for the codex fixture, also assert through `python3 -c` (importing
     `.aitask-scripts/lib/agent_sessions.py`) that
     `_CODEX_ROLLOUT_RE.match(basename(transcript_path))` succeeds and that its
     `session_id` group equals the fixture's `session_id`;
   - for the claude fixture, assert that the transcript's grandparent directory
     is `projects` and its basename is `<session_id>.jsonl`. That is the layout
     `_claude_store_roots` / `newest_transcript_for` search.

   A refreshed fixture with a changed layout then fails the hook's assertion and
   the store's assertion together, and cannot pass by updating only one of them.

## Verification

```bash
bash tests/test_session_hook.sh
shellcheck .aitask-scripts/aitask_session_hook.sh
~/.aitask/venv/bin/python -m pytest -q tests/test_agent_sessions_identity.py tests/test_agent_sessions.py \
  tests/test_agent_sessions_contract_call_sites.py tests/test_agent_restore.py tests/test_agent_freeze.py \
  tests/test_frozenagent_app.py tests/test_agent_sessions_transitions.py
bash tests/test_session_hook_install.sh
bash tests/test_session_hook_live.sh           # real tmux pane; skips cleanly if unavailable
set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3   # verdict = last line
(cd website && python3 check_links.py --build)
```
If `pytest` is not in the venv, fall back to `python3 -m unittest` per file.

Manual spot-check (read-only): run the hook classifier against every
`transcript_path` in `aitask_agent_sessions.sh list --full`. Each must yield
the record's own `agent_kind`.

## Step 9

Post-implementation follows task-workflow Step 8 (review, commit
`bug: … (t2109)`) and Step 9 (archival). Current-branch mode: no worktree or
merge.

## Risk

### Code-health risk: medium
- `agent_kind` widens from "the kind of `agent_string`" to "the kind of the
  agent whose session the record holds", and can now differ from the preserved
  string's kind. Consumers are audited (`agent_sessions`, `agent_restore`,
  `agent_freeze`, frozenagent's note), but a future reader that assumes the two
  agree could misread a conflict record · severity: medium · → mitigation: none
  (the user dropped the consumer-inventory test; the planned behaviour tests for
  identity conflicts and the resume refusal, in Step 7, are retained)
- The transcript-layout knowledge is now encoded twice: in the hook's inline
  classifier and in `agent_sessions` (`_CODEX_ROLLOUT_RE`, the claude
  projects-dir layout). A layout change could update one and not the other ·
  severity: low (residual — addressed by inline post-phase
  transcript_layout_agreement) · → mitigation: inline post-phase
  transcript_layout_agreement
- Existing tests that encoded "a blank kind resumes on the raw default" are
  rewritten, which risks weakening what they protected (string delivery, the
  t1850 note) · severity: low · → mitigation: none (each rewrite keeps its
  original assertion on a kind-only record)
- The store now **clears** `agent_kind` on an evidence-less session change, a
  second rule beside t1802/t1807's "blank means not supplied". A caller that
  legitimately reports a new id without evidence (the freeze fallback after a
  failed hook upsert) now degrades that record to re-pick · severity: low ·
  → mitigation: none (fail-safe direction; callers audited in Step 2;
  regression and control tests in Step 7)
- The viewer gains a synchronous preflight in an action handler. It runs one
  wrapper subprocess, measured at 21 ms, and only for string-less records; the
  wrapper's timeout bounds the worst case at 10 s · severity: low →
  mitigation: none

### Goal-achievement risk: low
- If a CLI changes its transcript layout, the hook infers no kind, and
  hand-started agents of that CLI re-pick instead of resuming. This is
  fail-safe, never the wrong CLI, and the fixture refresh lane surfaces it ·
  severity: low · → mitigation: none
- Records created before this change, and freeze-fallback records whose id came
  from the pane option, carry no kind and now re-pick where a same-kind raw
  default used to resume them. This is the requested direction · severity: low
  · → mitigation: none
- Residual, out of scope: a **same-kind** nested agent (e.g. `claude -p` run by
  a claude agent) still passes the hook and rebinds the pane's session id.
  Transcript shape cannot tell the two apart, so it is a separate upstream
  defect, to be offered as a follow-up at Step 8b · severity: medium ·
  → mitigation: none (upstream follow-up)

### Planned mitigations
- timing: post-phase | name: transcript_layout_agreement | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — transcript layout encoded twice (hook classifier vs agent_sessions) | desc: Pin the hook's kind inference and agent_sessions' rollout regex / claude layout to the same committed fixtures

## Post-Review Changes

### Change Request 1 (2026-10-22 10:22)
- **Requested by user:** (1) the viewer's refusal note hard-coded "re-pick it
  instead (P)" although the frozenagent shortcuts are rebindable — name the
  active binding and add a rebound-key case; (2) the new doc paragraphs said a
  hand-started agent resumes only when its CLI matches the raw default, which is
  false once freeze has recovered its agent string (`_resume_agent` then uses the
  stored `claudecode/<model>` without consulting `raw`), and implied an automatic
  re-pick where the restore is in fact refused with re-pick left available.
- **Changes made:** `agent_restore.resume_refusal_note` takes the caller's
  active `repick_key` and names no key without one; `FrozenAgentApp._active_key`
  resolves it through `keybinding_registry.resolve_key` (single characters shown
  verbatim, combos via `shortcut_labels.display_form`). New
  `test_a_rebound_repick_key_is_the_one_the_note_names` (repick rebound to `z`:
  the note names `z` and `z` re-picks), killed by a mutant that re-hard-codes
  `(P)`. Both doc paragraphs now say the recovered agent and model are used when
  present, the raw default only without them, and that an unknown or different
  CLI refuses the restore while re-pick stays available.
- **Files affected:** `.aitask-scripts/lib/agent_restore.py`,
  `.aitask-scripts/frozenagent/frozenagent_app.py`,
  `tests/test_agent_restore.py`, `tests/test_frozenagent_app.py`,
  `website/content/docs/concepts/framework-session.md`,
  `website/content/docs/workflows/freeze-and-restore-agents.md`

### Change Request 2 (2026-10-22 10:35)
- **Requested by user:** `_active_key` read `keybinding_registry.resolve_key`,
  i.e. the SAVED configuration. The shortcut editor writes a rebind to the
  registry at once but applies it only at the next launch
  (`shortcut_editor_modal.py` "restart the TUI to apply the new keys"), so a
  rebind saved while the viewer runs made the note advertise a key that did
  nothing. Take the key from the running viewer's installed binding, or omit
  it, and add a change-after-startup case.
- **Changes made:** `FrozenAgentApp._active_key` now reads the live keymap
  (`self.screen.active_bindings`, the public map the footer test already uses)
  and returns "" when no installed binding answers to the action, so the note
  names no key. New `test_a_rebind_saved_after_startup_is_not_advertised`
  (registry says `z` after startup: the note still names `P`, `z` dispatches
  nothing, `P` re-picks), killed by a mutant restoring the registry lookup; and
  `test_the_key_comes_from_the_live_keymap_or_not_at_all`.
- **Files affected:** `.aitask-scripts/frozenagent/frozenagent_app.py`,
  `tests/test_frozenagent_app.py`

## Final Implementation Notes
- **Actual work done:** As planned (Steps 1–7 + the inline post-phase), plus the
  two review rounds above:
  - hook transcript-shape kind gated on the payload's own session id, and the
    conflict refusal (step 5c);
  - store `--agent-kind`, with evidence bound to its session (a new id without
    evidence clears the kind; the explicit string is preserved);
  - restore `unknown_agent` / `agent_mismatch:<rec>:<launch>` gate in
    `_resume_agent`, shared by `resume_blocker` and `build_resume_argv` (which
    now passes the checked string explicitly);
  - freeze backfill refuses a recovered kind that differs from the stored one,
    blank included;
  - the frozenagent viewer preflight with `resume_refusal_note`;
  - five website pages.
- **Deviations from plan:**
  - `_restore_ack_kind` (agent_sessions.py) was added. The t1802 test caught
    that a repick-mode restore ack that lost its environment reports a NEW
    session with no evidence, so the planned rule cleared the kind. But the
    restore launched the record's own stored agent string, so that launch is
    evidence: both verified ack paths (in-grace and late-ok) supply that
    string's kind when the ack carries none.
  - Three t1850 freeze tests asserted the old "fill a blank-kind record holding
    an id from argv0" behaviour, which this task removes on purpose. They now
    seed a matching kind, and negative cases were added.
  - The frozenagent fixture record gained a session id, because the preflight
    refuses `no_session` before dispatch.
  - The docs also cover `tuis/frozenagent/{_index,reference}.md` (the outcome
    tables) and the `restore did not start` paragraph of the workflow page.
- **Issues encountered:**
  - A chained `str.replace` while threading `agent_kind` cascaded across indent
    levels; it was fixed by hand.
  - The hook test's `arg_value` drops empty arguments, so a `raw_value` helper
    was added for asserting an empty `--agent-string`.
- **Key decisions:**
  - Kind evidence comes from the payload transcript shape, not from the
    per-agent hook config (the user's decision). No install-flow change; it
    works on upgrade.
  - The viewer preflight is synchronous: the `raw` resolution measured 21 ms
    and runs only for string-less records.
  - The note's re-pick key comes from the live keymap
    (`screen.active_bindings`), never from the shortcut registry: a saved
    rebind applies only at the next launch.
  - Verification: 10 mutants in total, all killed (8 core guards, the
    hard-coded key, and the registry lookup). Every live store record with a
    session (25/25) classifies to its own kind.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_session_hook.sh:194 — a SAME-kind agent started inside another (e.g. `claude -p` run from a claude agent's Bash tool) inherits TMUX_PANE, @aitask_record and AITASK_AGENT_STRING, passes the process-tree guard (the pane process is its ancestor), and its SessionStart rebinds the pane's record to the nested session, so a restore resumes the nested session instead of the pane's own. The t2109 conflict refusal catches only a DIFFERENT kind; found by code reading.`
