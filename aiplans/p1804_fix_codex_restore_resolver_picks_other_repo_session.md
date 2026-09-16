---
Task: t1804_fix_codex_restore_resolver_picks_other_repo_session.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1804 — Tie a Codex session to its own agent instead of the newest same-repo rollout

## Context

`_codex_newest_transcript` (`.aitask-scripts/lib/agent_sessions.py:1670`) returns the
newest rollout whose `session_meta.payload.cwd` equals the project root. With several
Codex agents in one repo that is another agent's conversation (observed live in t1797's
resume smoke). Investigation showed the real shape of the gap:

- `newest_transcript_for` has **no production caller** — only tests and a stale comment
  in `aitask_session_hook.sh:29`. Interactive codex fires no SessionStart hook, so a
  codex record carries **no session id**, and `agent_restore.restore()` answers
  `RESTORE_FAILED:<id>|no_session` (user must re-pick).
- **Live evidence (codex 0.154, this box):** every running `codex` process holds exactly
  one `rollout-*.jsonl` open in `/proc/<pid>/fd`, and it is the pane's own process (its
  parent is the tmux server). So the freeze engine's `pane_pid` *is* the codex process,
  and its open rollout is an exact, deterministic identity — the correlation the task
  asks for.
- **Blocking trap:** freeze records carry a **blank `agent_string`** (all 6 live records
  checked; the dry-run launch path never exports `AITASK_AGENT_STRING`). `build_resume_argv`
  then resolves the project's `raw` default — `claudecode/sonnet5` — so capturing only a
  codex id would produce `claude --resume <codex-uuid>`: worse than today's clean refusal.
  **A session id is therefore recorded only together with a well-formed codex agent string.**

Intended outcome: freezing a codex agent captures *its own* session id + agent string, so
restore resumes the right conversation with the right agent; wherever no correlation is
possible (no `/proc`, pane not running codex directly, unmapped model, ambiguous fds) the
record stays id-less and restore falls back to re-pick exactly as today. The uncorrelated
root scan refuses to guess.

User decisions (planning): Linux `/proc` only + spawn a macOS follow-up task; Codex only,
offer a Claude-side follow-up at review; the live observation wins over a stored id.

## Implementation

### Pre-phase (risk mitigations)

1. [probe_pick_codex_fd] Before writing code, confirm the fd evidence holds for a
   pick-style codex, not only shadow companions. Resolve the argv read-only with
   `./.aitask-scripts/aitask_codeagent.sh --agent-string codex/gpt5_6_terra --dry-run invoke raw`,
   run it in a detached pane of an **isolated** tmux server (`tmux -L t1804probe`, cwd =
   a scratch git dir), wait a few seconds, and record: `ls -l /proc/<pane_pid>/fd | grep
   rollout` **before** any turn, the same **after** one short prompt, and
   `tr '\0' ' ' </proc/<pane_pid>/cmdline` (`-m <cli_id>` present?). Tear down with
   `tmux -L t1804probe kill-server` only — never the default or `ait` socket.
   Outcomes: held after the first turn → proceed as planned; not held before the first
   turn → proceed, and document in the resolver docstring that a never-prompted agent
   captures nothing (safe re-pick); never held, or no `-m` in cmdline → **stop and
   report** — the design's premise is false.

### 1. `.aitask-scripts/lib/agent_sessions.py` — pid-correlated resolver + no-guess scan

- Add miss reasons beside the existing ones (~1509): `MISS_AMBIGUOUS = "ambiguous"`,
  `MISS_NO_PROCESS = "no_process"`, `MISS_NOT_CODEX = "not_codex"`.
- Add a small helper deriving a rollout's identity: first line must be
  `type == "session_meta"` with a dict `payload`; id = `payload.session_id`, else the
  filename id via `_CODEX_ROLLOUT_RE` (159/1168 real rollouts lack `session_id`; a
  subagent-thread rollout carries its **parent's** `session_id`, so grouping by derived id
  folds it into the parent — no explicit subagent branch needed). Reuse
  `_codex_session_meta` rather than re-parsing.
- New `codex_process_model(pid, *, proc_root="/proc") -> (is_codex, cli_id)`: read
  `/proc/<pid>/cmdline` once; `is_codex` iff argv0's basename is `codex` (an `env A=B
  codex …` prefix **execs into** codex, so the cmdline is codex's own); `cli_id` = the
  value after `-m` / `--model` / `--model=` anywhere in argv (a resumed codex is
  `codex resume <sid> … -m <id>`). Never raises.
- New `codex_session_for_pid(pid, *, proc_root="/proc") -> (session_id, path, miss)`:
  - `pid <= 0`, or `<proc_root>/<pid>/fd` missing/unreadable → `MISS_NO_PROCESS`.
  - **The process must itself be codex** (`codex_process_model`) → else `MISS_NOT_CODEX`.
    This precondition lives *here*, not at the call site, so no caller can bypass it:
    a recycled pane, or any program holding a rollout-shaped file, must never be able to
    write its session into a codex record.
  - **Depth 0 only** (the pane process is the agent — launches `exec` through, which
    `agent_restore._env_prefixed` already relies on). No descendant walk: a claude pane
    whose Bash tool runs codex would otherwise capture a child tool's rollout.
  - `os.readlink` each fd; skip `" (deleted)"` targets; keep basenames matching
    `_CODEX_ROLLOUT_RE` whose first line is a `session_meta`. No store-root filter (the
    codex process's `CODEX_HOME` may differ from the freezer's; the fd is proof enough).
  - Group by derived id: 0 → `MISS_NO_MATCH`; >1 → `MISS_AMBIGUOUS`; exactly 1 → that id
    and the path whose filename id equals it (else first sorted path).
  - Docstring: Linux-only; elsewhere it answers `no_process` and callers keep today's
    re-pick behaviour (macOS follow-up tracks an `lsof` path).
- `_codex_newest_transcript`: collect every cwd-matching rollout, group by derived id;
  one id → return it with its newest path; more than one → `MISS_AMBIGUOUS` (never the
  newest guess); none → `MISS_NO_MATCH`. Update the module note (~1488-1494) and the
  `newest_transcript_for` docstring: the codex branch now resolves only single-session
  roots; the real mechanism is the freeze-time pid capture. Claude branch unchanged.

### 2. `.aitask-scripts/lib/agent_freeze.py` — capture at freeze, stage 1

The agent is still alive in stage 1 (`_resolve_record`); stage 5's respawn kills it.
Freeze-All goes through `freeze_pane`, so it is covered; reconcile never sees a live agent.

- New `_codex_agent_string(cli_id, root) -> str` (never raises): resolve the cli id via
  the canonical `aitask_resolve_detected_agent.sh --agent codex --cli-id <id>` (cwd=root,
  `TASK_DIR` dropped from env, short timeout). Accept only an `AGENT_STRING:` line whose
  value satisfies `agent_sessions.agent_kind_of(...) == "codex"`; `AGENT_STRING_FALLBACK:`
  → `""`. (`stats_data.load_model_cli_ids` was rejected: it drags in archive/gate imports.)
  Identity is **not** this function's job — `codex_session_for_pid` already proved the
  process is codex; this only names its model.
- Observation, called through the module (`agent_sessions.codex_session_for_pid(...)`,
  `agent_sessions.codex_process_model(...)`, `_codex_agent_string(...)`) so tests can swap
  it, wrapped so it can never raise out of stage 1. A hit is **usable** only when the
  resolver returned a session id (which already implies a verified live codex process)
  **and** an agent string is available — derived from the live cli id, or, only when the
  cmdline carries no `-m`, taken from the stored record's existing codex `agent_string`.
  **A stored label never substitutes for live process verification**, only for the model
  name.
- **Path 1 (stamped, known record):** keep the `store_show(stamped)` dict instead of
  discarding it. If its `agent_kind` is not `codex` **and** it already holds a session id
  (a hook-owned claude record), do nothing — not even observe. Otherwise observe and act
  on the outcome:
  - **usable hit** whose id differs from the stored one, or whose record lacks the agent
    string → best-effort `upsert --id <stamped> --root <rec.root> --window <rec.window>
    --pane <pane_id> --pane-pid <pane_pid> --session-id <sid> --transcript <path>
    [--agent-string <s>]` (the record's own root/window, so no relocation).
  - **`MISS_NO_MATCH` / `MISS_AMBIGUOUS` / `MISS_NOT_CODEX` on a record that already holds
    a codex session id → CLEAR it**: the same best-effort upsert with an explicit
    `--session-id "" --transcript ""`. The observation *ran* and could not prove the
    stored id is this process's, so keeping it would resume a conversation this agent is
    no longer in (e.g. after `/new`, or a recycled pane); an id-less record degrades to
    re-pick, which is the fail-safe direction. Verified: an explicit empty clears while an
    absent flag leaves the field, and `agent_string` survives either way (blank =
    not supplied), so re-pick still launches the right agent.
  - **`MISS_NO_PROCESS` → change nothing.** That is *absence of evidence* (no `/proc` at
    all — every macOS freeze, an unreadable `fd` dir), not evidence of staleness. Clearing
    here would wipe a valid hook-captured `codex exec` id on macOS at every freeze.
  - Success = rc 0 **and** an `UPSERTED:` line (`UPSERT_REFUSED` exits 0). Anything else
    prints `WARNING:<rid>|session capture: …` to stderr and the freeze continues.
- **Path 2 (fallback upsert):** no stored record exists, so there is nothing to clear. On
  a usable hit pass `--session-id`, `--transcript` and `--agent-string` from the
  observation. Otherwise pass `--session-id` **only when** `facts["agent_session"]` is
  non-empty — fixes the pre-existing blanking: the CLI turns `--session-id ""` into `""`,
  and an upsert that selects an existing record by pane would overwrite a hook-captured id.
- Warn only on `MISS_AMBIGUOUS` or a failed update — never on the ordinary miss every
  claude pane produces. Update the `_resolve_record` docstring.

### 3. Stale comments

- `.aitask-scripts/aitask_session_hook.sh:26-29` — interactive codex ids are captured at
  freeze from the process's open rollout, not by `newest_transcript_for`.
- `tests/data/session_hooks/README.md:123-127` — same correction; the codex fallback
  refuses ambiguity.
- `tests/test_codeagent_resume_session.sh:28-32` — "`codex = re-pick only` stands" no
  longer holds on Linux.
- `.aitask-scripts/lib/agent_restore.py:~455` — the `no_session` comment names the
  remaining causes (non-Linux, pane not running codex directly, unmapped model, ambiguous).

### 4. Tests

- `tests/test_agent_sessions_transcripts.py` — new class over a fake `proc_root`
  (`<tmp>/proc/<pid>/fd/<n>` symlinks into a synthetic codex store):
  1. **t1797 regression:** two same-root agents, the OTHER one's rollout newer — each pid
     resolves its own id, while `newest_transcript_for` answers `MISS_AMBIGUOUS`.
  2. main + subagent rollout held by one pid → the main id and path.
  3. two main rollouts held → `MISS_AMBIGUOUS`.
  4. only non-rollout fds → `MISS_NO_MATCH`; missing pid → `MISS_NO_PROCESS`.
  5. **a non-codex process (argv0 `python3`/`bash`) holding a synthetic rollout →
     `MISS_NOT_CODEX`**, and nothing is captured. The wrong-agent-identity guard.
  6. `session_id` absent → filename id.
  7. rewrite `test_date_partitioned_selection_picks_the_newest` (it pins the defect) to
     expect `MISS_AMBIGUOUS`; add a single-session-root hit; extend
     `test_every_miss_reason_is_distinguishable` to seven reasons.
- `tests/test_agent_freeze.py` — `_FakeStore.upsert` forwards `--id`, `--transcript`,
  `--agent-string` with **absent → None** (today `""` hides the blanking bug); `setUp`
  stubs `agent_sessions.codex_session_for_pid` (default miss) and
  `agent_freeze._codex_agent_string` (`AGENT_PID=4242` may be a real process). Cases:
  unstamped codex pane records id + transcript + agent string; stamped id-less record
  gains them; observed id replaces a differing stored codex id; a claude-shaped record
  (id stored, kind blank) is untouched and not even observed; a hit with no agent string
  records nothing; a refused best-effort update warns and the freeze succeeds; path 2 with
  empty `agent_session` sends no `--session-id`. **Stale-id cases:** a codex record with a
  stored id gets it **cleared** on `MISS_NO_MATCH`, on `MISS_AMBIGUOUS` and on
  `MISS_NOT_CODEX` (assert the upsert carries an explicit empty `--session-id` and that
  `agent_string` survives); the same record is **left untouched** on `MISS_NO_PROCESS`;
  an id-less record on any miss stays untouched and the freeze succeeds.
- `tests/test_agent_sessions_contract_call_sites.py` — add the new call site
  (`live`, `upsert`, `[root, window, pane, pane_pid, session_id, transcript, agent_string]`)
  and extend the `C.freeze.1` row with the arguments it may now supply.

### Post-phase (risk mitigations)

1. [live_capture_resume_argv_smoke] Read-only, no store writes: for every running
   `codex` pid, compare `agent_sessions.codex_session_for_pid(pid)` with
   `ls -l /proc/<pid>/fd`. For the agent string, **derive each pid's expected value from
   its own `-m` argument** (`codex_process_model(pid)` → cli id → the `models_codex.json`
   entry with that `cli_id`) and assert `_codex_agent_string` equals it — never a
   hard-coded `codex/gpt5_6_terra`, which would fail falsely on any agent running another
   configured model. Also assert a non-codex pid (this shell) yields `MISS_NOT_CODEX`.
   Then take **one** capture and carry its own three derived values — `sid`, its
   `agent_string`, and the `cli_id` read from that same pid — into
   `agent_restore.build_resume_argv({"root": ..., "codeagent_session_id": sid,
   "agent_string": <that agent_string>})`, asserting the argv is the codex binary with
   `resume <sid>` and `-m <that cli_id>`. Assert against the selected capture's **own**
   model, never a hard-coded `gpt-5.6-terra`: a fixed expectation fails falsely on any
   other configured model, and hand-picking a Terra session to dodge that would stop the
   check proving the captured session and its model stay paired. Control: a blank
   `agent_string` yields the claude argv — the reason the capture is gated on it.

## Verification

- `python3 tests/test_agent_sessions_transcripts.py`, `tests/test_agent_freeze.py`,
  `tests/test_agent_sessions_contract_call_sites.py`, `tests/test_agent_restore.py`,
  `tests/test_agent_frozen_ops.py`; then `bash tests/run_all_python_tests.sh` (last line
  is the verdict); `bash tests/test_codeagent_resume_session.sh`,
  `bash tests/test_session_hook.sh`; `shellcheck .aitask-scripts/aitask_session_hook.sh`.
- Negative control: the t1797 regression test must fail against the old
  newest-wins logic (the ambiguity assertion) — confirmed by reading the pre-change
  behaviour it pins, not by stashing.

## Follow-ups (after implementation)

- Create a task: macOS `lsof` path for `codex_session_for_pid` (user-requested).
- Offer (Step 8b) a task for `_claude_newest_transcript`'s identical newest-by-cwd guess.

## Post-implementation

Step 9 of the task workflow: current-branch profile — no merge; archive via
`aitask_archive.sh 1804`, then push.

## Risk

### Code-health risk: medium
- Stage 1 of the freeze transaction (a load-bearing path) gains `/proc` reads, a
  subprocess and a best-effort store write whose refusal exits 0; a mistake here could
  fail or slow a freeze · severity: medium · → mitigation: none (contained by the
  never-raise wrapper, the `UPSERTED:`-prefix check and the freeze-suite failure cases)
- Pre-existing `--session-id ""` blanking is fixed in the same code, widening the diff
  beyond the codex path · severity: low · → mitigation: none (pinned by its own test)

### Goal-achievement risk: low
- The fd-holding evidence comes from shadow companions only; a pick-launched codex
  agent (or one before its first turn) may not hold its rollout yet, so capture could
  miss on exactly the agents users freeze · severity: low (residual — addressed by
  inline pre-phase probe_pick_codex_fd; any remaining miss degrades to today's re-pick)
  · → mitigation: inline pre-phase probe_pick_codex_fd
- A captured id reaching restore with a wrong/blank agent string would resume the
  wrong agent; correctness depends on the cmdline `-m` → agent-string derivation holding
  for real launches · severity: low (residual — addressed by inline post-phase
  live_capture_resume_argv_smoke) · → mitigation: inline post-phase live_capture_resume_argv_smoke
- Clearing an unprovable stored id can discard a still-valid one — e.g. a codex agent
  that has not yet opened its rollout, or a transient `MISS_AMBIGUOUS` — downgrading a
  working resume to re-pick · severity: low · → mitigation: none (deliberate fail-safe
  direction: re-pick is recoverable, resuming a stranger's conversation is not; the
  no-evidence case `MISS_NO_PROCESS` is excluded from clearing, and the pre-phase probe
  measures whether a fresh agent holds its rollout)

### Planned mitigations
- timing: pre-phase | name: probe_pick_codex_fd | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — fd evidence comes from shadow companions only | desc: Launch a pick-style codex in an isolated tmux server and confirm it holds its rollout fd (before/after the first turn) and carries -m in its cmdline.
- timing: post-phase | name: live_capture_resume_argv_smoke | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a captured id resuming under the wrong agent | desc: Run the pid resolver and agent-string derivation against live codex pids, and confirm build_resume_argv yields a codex resume argv (claude argv for a blank agent string as the control).
