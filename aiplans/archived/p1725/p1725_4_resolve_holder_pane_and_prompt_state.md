---
Task: t1725_4_resolve_holder_pane_and_prompt_state.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_1_*.md, aitasks/t1725/t1725_2_*.md, aitasks/t1725/t1725_3_*.md, aitasks/t1725/t1725_5_*.md, aitasks/t1725/t1725_6_*.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-10 14:51
---

# t1725_4 — resolve the holder's pane and prompt state

## Context

Parent t1725, finding 3: a sync deferral could have said *"t1717: aiplans/p1717 —
agent in pane aitasks:4.1 is waiting on a question"*, because lock → pid → tmux pane
→ prompt state is all derivable. t1725_3 shipped the per-file `DEFERRED_FILE:` wire
record with two columns left empty for this task (`pane`, `pane_state`, grammar
`^(waiting_[a-z0-9_]+|active|)$`) and a `--require-waiting` re-probe in
`_commit_group` that fails closed until the helpers exist. This task makes the
helpers exist, fills the columns, and makes the re-probe real. t1725_5 renders the
record in the syncer/board TUI; this task also enriches the CLI's own stderr line
(user decision, 2026-09-10).

## Verification pass (2026-09-10) — deltas from the decomposition plan

- **Confirmed, with a required bootstrap:** `monitor_core` pulls no Textual (205
  modules, ~90 ms), so the "import only `strip_ansi`" fallback is dropped. But that
  check put `monitor/` and `lib/` on `sys.path` by hand. **Launched as a script from
  `lib/`, `import monitor_core` raises `ModuleNotFoundError`** (reproduced), and the
  CLI's catch-all would turn that into a silent, permanent `""`. The probe therefore
  needs the explicit two-path bootstrap in Step 2, pinned by a CLI success-path test
  run through the shipping entry point.
- **Corrected:** capture must go through `TmuxClient.run([...])`, not
  `["tmux", *tmux_socket_args(), …]` — that literal is a raw spawn
  `tests/test_no_raw_tmux.sh` flags, and `tmux_gateway.md` forbids allowlisting.
  `lib/agent_freeze.py:196` is the precedent.
- **Corrected:** `classify_content` only scans when `category == PaneCategory.AGENT`,
  and an `agent=""` call matches the *unscoped* flat list. Mirror the monitor's
  canonical shape (`monitor_core._classify_batch`): `_classify_one(content,
  COMPARE_MODE_STRIPPED, all_patterns(), PaneCategory.AGENT,
  agent_key_from_pane(cmd, pane_pid, pane_id))` — so the gate agrees with what
  minimonitor shows, never looser.
- **Found:** `aitask_sync.sh` does not source `lib/tmux_exec.sh`, so the t1725_3
  hook's `declare -F ait_tmux_pane_for_pid` guard is false today.
- **Found:** the hook already exists (`_commit_group`, ~1206-1230) and passes the
  helper's whole tab-joined output to the probe. It must take field 1 (`%N`).
- **Found:** `parse_sync_output` drops a whole record on a bad `pane_state`, so the
  hook's `unresolvable` (a human-message word) must never reach `PROT_PANE_STATE`.
  `PROT_PANE` is the **target** string (`test_sync_action_runner.py:395` pins
  `a|b:4.1`), not the pane id.
- **Found:** `_holder_action` runs inside `$(…)` in `_protect_task_paths`; a memo it
  wrote would die with the subshell. Populate in the parent frame, read in the child.
- **Found (hazard):** `tests/lib/sync_fixture.sh::run_sync` sets no
  `AITASKS_TMUX_SOCKET` and `lock_yaml_live` plants `pid: $$`. With the probe live,
  the sweep would walk the *test runner's* ancestors on the real `ait` server and
  classify this agent's own screen — `drive_holder_not_waiting` could flip to a
  commit. User decision: fix the shared fixture. **Consequence:** the new live test
  must hand `run_sync` its own socket on every call, or it only ever measures the
  no-server default (Verification contract below).

## Pre-phase (risk mitigations)

1. [baseline_sync_and_live_endpoint_suites] Before any edit, run
   `bash tests/test_sync_protect_paths.sh`, `bash tests/test_sync_deferral_and_quarantine.sh`,
   `bash tests/test_live_endpoint_tmux_live.sh`, `bash tests/test_live_endpoint_degradation.sh`
   on the unmodified tree; record each file's PASS/FAIL/TOTAL in this plan's
   Final Implementation Notes. A red baseline is reported, not fixed here.

## Steps

1. **Gateway helper.** Move `resolve_pane_for_pid` (`aitask_live_endpoint.sh:186-210`)
   into `lib/tmux_exec.sh` as `ait_tmux_pane_for_pid <pid>`; the bound becomes
   `AIT_TMUX_PANE_WALK_MAX=20` there. Body and its comment block (pane_pid first,
   `#{window_id}` not `@#{window_index}`, gateway socket only) move verbatim.
   `aitask_live_endpoint.sh` drops the function and `ANCESTOR_WALK_MAX` and calls the
   gateway helper; its output line is byte-identical.

2. **Probe — `lib/pane_state_probe.py`** (module + CLI):
   - **Import bootstrap (module top, before any framework import)** — the same
     two-path shape as `lib/agent_freeze.py:66-70`: derive
     `_LIB = Path(__file__).resolve().parent` and `_SCRIPTS = _LIB.parent`, and insert
     both into `sys.path` if absent. Then import the monitor modules **as a package**
     (`from monitor.monitor_core import _classify_one, PaneCategory,
     COMPARE_MODE_STRIPPED`, `from monitor.prompt_patterns import all_patterns`,
     exactly as `agent_freeze.py:89-90` does), and the lib ones flat (`from tmux_exec
     import TmuxClient`, `from agent_keys import agent_key_from_pane`). Package form
     for both monitor imports keeps one `monitor.prompt_patterns` module object, so
     `monitor_core`'s own relative import and the probe's import agree.
   - `probe(pane_id, *, client=None) -> str` — `""` unless `pane_id` matches
     `^%[0-9]+$` (enforce the one input shape; never parse a target). With
     `client = client or TmuxClient()`: `display-message -p -t <id>
     '#{pane_current_command}\t#{pane_pid}'`, then `capture-pane -p -e -t <id> -S -200`
     (timeout 2 s each). Any rc≠0 → `""`.
   - `classify_text(text, current_command, pane_pid, pane_id) -> str` —
     `_classify_one(...)` as above; awaiting → `waiting_<kind>`, else `active`. The
     result is re-validated against `^(waiting_[a-z0-9_]+|active)$` → else `""`, so a
     future pattern name outside the grammar fails closed at the write site.
   - CLI: `pane_state_probe.py <id>` prints **exactly one line** on stdout and exits
     0 always (usage error included). The framework imports are the part most likely
     to break, and a broken import must not be indistinguishable from "not waiting".
     So the catch-all also writes `pane_state_probe: <ExceptionClass>: <msg>` to
     **stderr**. This makes it visible when run by hand; it does not make it visible
     to the sweep, which discards stderr. The success-path pin in Verification is
     what makes a broken bootstrap fail a test.
   - Idle is not attempted (needs two samples over time).

3. **Sweep fill + stderr line (`aitask_sync.sh`).**
   - `source "$SCRIPT_DIR/lib/tmux_exec.sh"` (+ `# shellcheck source=` directive).
   - Memo maps `HOLDER_PANE[tid]` (target), `HOLDER_PANE_ID[tid]`,
     `HOLDER_PANE_STATE[tid]`, `HOLDER_PANE_DONE[tid]`.
   - `_resolve_holder_pane <tid>` — once per tid: only when `LOCK_HOST[tid]` equals
     `hostname` and `LOCK_PID[tid]` is numeric > 0. `line=$(ait_tmux_pane_for_pid …)
     || line=""`; probe only when a pane resolved and `resolve_python` answers; the
     probe result is re-validated against the grammar. Every call absorbed with
     `|| x=""` — never aborts, never blocks the sweep.
   - Called at the top of `_protect_task_paths` (parent frame) for `live_lock` and
     `unknown_liveness` only. `_protect` fills `PROT_PANE` / `PROT_PANE_STATE` from
     the memo (else `""`); both already reach the wire through `_pct_encode` / the
     grammar at line ~1412.
   - `_holder_action` (read-only, in its subshell) adds pane and state to the
     `self` / `other` parenthetical when known, e.g. `(pid 4242, pane
     aitasks:@4.%12, waiting on a prompt: claude_askuserquestion)` / `…, running — not
     at a prompt)`. The rest of each line is unchanged.

4. **`--require-waiting` wiring (`_commit_group`).** Split the helper output:
   `hpane=${hline%%$'\t'*}` goes to the probe, `${hline#*$'\t'}` is the target. The
   re-probe stays fresh (never read from the memo), and it **overwrites** the memo
   (target + validated state; `""` for unresolvable) before
   `_protect_group_paths "holder_not_waiting"`, so that record carries the observed
   pane. The human message keeps `observed: unresolvable`. Drop the stale "until
   t1725_4 lands" comment.

5. **Fixture hermeticity (`tests/lib/sync_fixture.sh::run_sync`).** Export
   `AITASKS_TMUX_SOCKET="${SYNC_FIXTURE_TMUX_SOCKET:-ait_syncfx_nosrv_$$}"` — never
   empty (empty = legacy follow-`$TMUX`, the kill-server hazard class). The comment
   states both halves of the contract: the default reaches no server, and a test that
   wants pane resolution **must** set `SYNC_FIXTURE_TMUX_SOCKET` to its own server's
   `-L` name, sharing that server's `TMUX_TMPDIR`. Update the `drive_holder_not_waiting`
   comment in `test_sync_protect_paths.sh` to point at the live test below instead of
   "until t1725_4".

6. **Docs (internal).** `aidocs/framework/monitor_idle_and_prompt_detection.md`: one
   paragraph naming `lib/pane_state_probe.py` as a second consumer of the pattern
   registry that gates `--require-waiting` commits. `aidocs/framework/tmux_gateway.md`:
   list `ait_tmux_pane_for_pid` among the shell helpers. (User-facing website docs
   are t1725_6.)

7. `shellcheck` the touched scripts; `bash tests/test_no_raw_tmux.sh`.

## Post-phase (risk mitigations)

1. [pane_unresolvable_degrades_to_pid] In the live test (Case S3 below): a deferred
   sweep whose live lock's pid is in no gateway pane (the test shell, `$$`) emits the
   `DEFERRED_FILE:` record with pid, email and host filled and `pane` / `pane_state`
   both empty, and the run's first stdout line is still a recognised batch token.
   The sweep runs **with** `SYNC_FIXTURE_TMUX_SOCKET="$SOCK"` (a live server is
   reachable), so the empty pane is attributable to the pid and not to a missing
   server. (TUI half — `pane=""` renders with no commit button — is t1725_5's.)

## Verification

- **`tests/test_tmux_pane_for_pid.sh`** (new; `require_isolated_tmux`, private
  `-L ait_panepid_$$`, trap kills only that socket): (1) the pane's own pid → the
  exact `%N\t<session>:@W.%N`, compared with tmux's own `list-panes -F` rendering;
  (2) a descendant (`sleep` spawned in the pane, pid via file) → same pane;
  (3) unrelated pid `$$` → rc 1, empty; (4) `""` / `abc` / `0` → rc 1; (5) session
  `a|b` → target starts `a|b:`; (6) negative control: case 1's pid with the socket
  repointed at a no-server name → rc 1.
- **`tests/test_pane_state_probe.py`** (new, stub client scripted per verb):
  AskUserQuestion body on a `claude` pane → `waiting_claude_askuserquestion`; plain
  body → `active`; capture rc≠0 → `""`; bad ids (`aitasks:1.1`, `%x`, `""`) → `""`
  with **zero** client calls. Scoping pin: an `opencode_palette` body on a `claude`
  pane → `active` (the mutant `agent=""` would answer `waiting_opencode_palette`).
  CLI subprocess with a no-server socket and with no args → exactly one empty line,
  rc 0. **Bootstrap pin:** a subprocess launched with `cwd` outside the repo and no
  `PYTHONPATH` runs `python -c` that imports `pane_state_probe` by file path the
  way the CLI loads it, and asserts `probe` / `classify_text` resolved (i.e. the
  `monitor.*` imports succeeded), with empty stderr.
- **`tests/test_sync_holder_pane_live.sh`** (new) — **socket contract, stated
  first:**
  - `require_isolated_tmux` runs before anything else, so `TMUX_TMPDIR` is exported
    and inherited by both the fixture's server and every `run_sync` subshell. Then
    `SOCK="ait_syncpane_$$"` and `NOSRV="ait_syncpane_nosrv_$$"`.
  - Every sweep goes through one wrapper, `run_sync_live() {
    SYNC_FIXTURE_TMUX_SOCKET="$SOCK" run_sync "$@"; }`. That includes the E1
    re-probe run and S3. Only the negative controls call
    `SYNC_FIXTURE_TMUX_SOCKET="$NOSRV" run_sync` explicitly. No case calls bare
    `run_sync`; a grep in the test's own footer asserts that.
  - **Precondition asserted before each positive sweep:** `tmux -L "$SOCK"
    list-panes -a -F '#{pane_pid}'` lists `$PANE_PID`, so the server is reachable
    under exactly the name handed to the sweep. **Precondition asserted in each
    negative control:** `tmux -L "$NOSRV" list-sessions` fails, so the control
    reaches no server.
  - Fixture: session `ait|t10`; its pane redraws `$SCREEN` from a file; the lock is
    anchored to its `pane_pid`; `set_userconfig_email other@x.com` → class `self`;
    remote ahead plus a tracked dirty file, so the run defers. A fresh fixture per
    case. Poll `capture-pane` until the screen renders (bounded).

  Cases:
  - **P1 (CLI success path, the bootstrap pin through the shipping artifact):**
    screen = snippet → `AITASKS_TMUX_SOCKET="$SOCK" "$(resolve_python)"
    .aitask-scripts/lib/pane_state_probe.py "$PANE_ID"`, run from a `cwd` outside the
    repo, prints exactly `waiting_claude_askuserquestion` with empty stderr. **P2:**
    plain screen → `active`.
  - **S1:** screen = snippet → the record (via `parse_sync_output`) has pane =
    tmux's own target (`|` survives the `%7C` round-trip) and
    `waiting_claude_askuserquestion`. The stderr line names the pane and "waiting on
    a prompt". **S1-control:** the identical sweep via `$NOSRV` → the same record
    with pane `""` and pane_state `""`. S1's pane therefore comes from the selected
    socket, not from anything ambient.
  - **S2 (control):** plain screen → same pane, `active`.
  - **S3:** post-phase step 1.
  - **E1:** a deferred run with a waiting screen, then the screen is rewritten to
    plain, then `run_sync_live --commit-for-task 10 --require-waiting` →
    `holder_not_waiting`, `observed: active`, no `Auto-commit t10` in the data log.
  - **E2:** screen stays waiting → `run_sync_live --commit-for-task 10
    --require-waiting` → committed.
  - **E2-control:** E2 via `$NOSRV` → refused with `observed: unresolvable`, so E2's
    commit is attributable to the probe reaching `$SOCK`.
  - Verify at implementation that `setup_repo`'s clone carries
    `lib/pane_state_probe.py` and `monitor/`, the same way it carries the rest of
    `.aitask-scripts/`. P1 must run the clone's copy, since that is the copy the
    sweep executes.
- Existing: `bash tests/test_sync_protect_paths.sh` (`drive_holder_not_waiting` now
  goes through the real probe path, which fails closed because no server is
  reachable), `bash tests/test_sync_deferral_and_quarantine.sh`,
  `bash tests/test_live_endpoint*.sh`, `bash tests/test_no_raw_tmux.sh`,
  `bash tests/run_all_python_tests.sh --test-dir tests` (last line only).

## Risk

### Code-health risk: medium
- New calls on the sweep's `_protect` path under `set -euo pipefail`: an unabsorbed status or an unset index produces empty stdout, the class `test_sync_protect_paths.sh` exists for · severity: medium (residual — detection is the existing characterization harness, and the inline pre-phase baseline makes a regression attributable to this change) · → mitigation: inline pre-phase baseline_sync_and_live_endpoint_suites
- Moving `resolve_pane_for_pid` into the shared gateway could drift t1657_4's live endpoint (`ait note --with-live`) · severity: low (residual — the live-endpoint suites are baselined before the move and re-run after) · → mitigation: inline pre-phase baseline_sync_and_live_endpoint_suites
- The shared-fixture change reaches every test that sources `sync_fixture.sh` · severity: low · → mitigation: none (it only removes ambient reachability; the full sync suites are re-run)
- Sweep latency: per same-host protected task, one `list-panes`, ≤21 `ps`, one Python start (~0.1-0.3 s), memoized per task · severity: low · → mitigation: none

### Goal-achievement risk: low
- An unresolvable pane (the agent on a non-gateway tmux server, or a pid in no pane) must degrade to a pid-only record, never drop the record or abort the run · severity: low (residual — pinned by inline post-phase pane_unresolvable_degrades_to_pid) · → mitigation: inline post-phase pane_unresolvable_degrades_to_pid
- Detection sees the bottom 6 lines, and unresolved-agent panes match unscoped, the same as the monitor. A false `active` under-offers commit-on-behalf (safe); a false `waiting` is bounded to what minimonitor would itself show, and the 5a.3 re-check and publication guard still stand · severity: low · → mitigation: none
- A probe that cannot import its framework modules would answer `""` forever, so `--require-waiting` could never commit — silently, because the sweep discards the probe's stderr · severity: low (residual — the explicit two-path bootstrap in Step 2, pinned by P1 through the shipping artifact and by the unit test's bootstrap pin) · → mitigation: none (addressed in the plan body)

### Planned mitigations
- timing: pre-phase | name: baseline_sync_and_live_endpoint_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — empty-stdout abort on the _protect path; live-endpoint drift from the helper move | desc: run the sync and live-endpoint suites on the unmodified tree and record pass counts before any edit
- timing: post-phase | name: pane_unresolvable_degrades_to_pid | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — unresolvable pane must degrade to a pid-only record | desc: a deferred sweep with a live lock whose pid is in no gateway pane still emits the DEFERRED_FILE record with pid/email/host filled and pane/pane_state empty

## Step 9

Standard post-implementation; parent t1725 archives after the last child.

## Post-Review Changes

### Change Request 1 (2026-09-10 15:37)
- **Requested by user:** review finding — `--require-waiting` treats prompt-shaped
  text in an unrecognised pane (agent key unresolved, so matching runs over the
  unscoped pattern list) as proof an agent is waiting; a shell or wrapper showing
  copied prompt text could satisfy it. The gate should eventually require durable
  agent provenance (e.g. a launch-time pane marker), with a regression test for an
  unrecognised pane showing prompt-like output. Disposition: **follow-up**.
- **Changes made:** none to code — the disposition was honored. Created **t1787**
  (`require_waiting_durable_agent_provenance`, `followup_kind: review_finding`,
  `depends: [t1725_4]`). The regression test belongs there: it must assert
  refusal, so it stays red until the provenance fix lands; pinning today's
  `waiting_*` answer in this task would make the hole the contract.
- **Files affected:** none in the code tree (task file `aitasks/t1787_*.md` only).

## Deferred, with owners

| Item | Owner | Carried forward |
|---|---|---|
| `--require-waiting` must rest on durable agent provenance, not screen text | t1787 | unresolved agent key → unscoped patterns; consumers (`_commit_group` gate, record `pane_state`, t1725_5's offer); launch-time pane-marker candidate (`@aitask_shadow_target` precedent); live test E2 currently commits through the unscoped fallback (`sh render.sh` pane) and must be reworked; required refusal regression test |

## Final Implementation Notes

- **Actual work done:** as planned. `ait_tmux_pane_for_pid` moved into
  `lib/tmux_exec.sh` (the live endpoint now calls it, byte-identical output);
  new `lib/pane_state_probe.py` (module + one-line CLI, capture via `TmuxClient`,
  classified by `monitor_core._classify_one` scoped with `agent_key_from_pane`);
  `aitask_sync.sh` sources the gateway, memoizes the holder's pane + state per task
  (`_resolve_holder_pane`, called from `_protect_task_paths` for `live_lock` /
  `unknown_liveness` on this host), fills `PROT_PANE` / `PROT_PANE_STATE`, enriches
  the `self` / `other` stderr line ("pane X, waiting on a prompt: <kind>" /
  "running — not at a prompt"), and the `--require-waiting` re-probe passes the
  pane id (not the tab-joined line) and overwrites the memo so a
  `holder_not_waiting` record carries the observed state. Internal docs updated
  (`monitor_idle_and_prompt_detection.md`, `tmux_gateway.md`).
- **Deviations from plan:**
  - The no-server socket pin moved to **file scope** in `tests/lib/sync_fixture.sh`
    (plus the per-call `SYNC_FIXTURE_TMUX_SOCKET` override in `run_sync`): the
    identity sweep found `test_sync_deferral_and_quarantine.sh` invoking the sweep
    directly (`run_sync_seam`, Test 13, line ~729) with live locks, which a
    `run_sync`-only fix would have left pointed at the real `ait` server.
  - `HOLDER_PANE_ID` memo map dropped (written, never read; SC2034).
  - Probe regexes use `fullmatch` — `^…$` with `match()` accepted `"%5\n"` (caught
    by the unit test).
  - Probe framework imports run at module top inside `try`, not lazily: a lazy
    import would never run on the no-server path, and the stderr bootstrap pin
    could not fail.
  - `tests/test_live_endpoint_no_sendkeys.sh` updated (not in the plan): its 1b/1c/
    1c'/1d scans read only the endpoint file, so the move emptied its verb set. It
    now scans the endpoint + the `ait_tmux_pane_for_pid` body, with two shape
    assertions (endpoint delegates; body carries `ait_tmux list-panes`).
- **Issues encountered:** the no-sendkeys regression (HEAD control 26/26 vs 25/26
  with the change) — fixed, mutant-proven (send-keys injected into the helper body
  fails 1b/1c/1c'). The AskUserQuestion regex needs `·` and `↑/↓`, so the live test
  forces `C.UTF-8` when the locale is not UTF-8; prompt detection reads only the
  last 6 capture lines, so the live test bottom-aligns its screen.
- **Key decisions:** pane_state values are validated against
  `^(waiting_[a-z0-9_]+|active)$` at BOTH write sites (probe and sweep) —
  `sync_action_runner` drops the whole record otherwise, and `unresolvable` lives
  only in the human message. The memo is written only in the sweep's own frame
  (`_holder_action` runs in `$( )`). The re-probe never trusts the memo.
- **Verification:** pre-phase baseline (unmodified tree): protect_paths 31/31,
  deferral_and_quarantine 109/109, live_endpoint_tmux_live 16/16,
  live_endpoint_degradation 53/53. After: those unchanged, plus sync_rebase_gate
  30/30, sync_auto_commit_scoping 38/38, test_sync 42/42, branch_mode_automerge
  green, live_endpoint_no_sendkeys 28/28, tmux_pane_for_pid 25/25, no_raw_tmux 5/5,
  test_pane_state_probe 11/11, test_sync_holder_pane_live 51/51, python suite
  PASSED (runner=pytest, exit=0). Per-half mutants on isolated copies: whole line
  to the probe (E2 fails), record not filled (S1e/S1f/S2/E1 fail, stderr still
  passes), bootstrap removed (P1d fails with ModuleNotFoundError).
- **Upstream defects identified:**
  - `tests/test_task_push.sh:2116 — Test 54 ("two replayed commits both auto-merge") fails (TASK_SYNC_STATUS failed, rebase aborted) in the post-change run; tests/test_task_push.sh:2200 — Test 56 ("AIT_AUTOMERGE_MAX_ROUNDS junk/0") fails on a pristine `git archive HEAD` (b874e7058) export. Failing case varies between runs: pre-existing, likely flaky, in the t1727 automerge-loop area (lib/task_utils.sh::_task_pull_rebase, lib/task_automerge.sh); untouched by t1725_4.`
- **Notes for sibling tasks:**
  - t1725_5: `pane` is the target `<session>:<window_id>.<pane_id>` (percent-encoded
    on the wire); `pane_state` is `waiting_<kind>` / `active` / `""`, filled only for
    `live_lock` / `unknown_liveness` on this host. It is **text-derived** — for an
    unresolved agent it matches unscoped (see t1787), and your commit button rides
    on it.
  - Tests wanting pane resolution: `require_isolated_tmux` first, then source
    `sync_fixture.sh`, and pass `SYNC_FIXTURE_TMUX_SOCKET=<your -L name>` per sweep.
    `tests/test_sync_holder_pane_live.sh` is the template (redraw-from-file pane,
    bottom-aligned screen, UTF-8, parser-based record reads with an END sentinel).
  - t1787 (review finding, follow-up): durable agent provenance for
    `--require-waiting`; live-test E2 currently commits through the unscoped
    fallback and must be reworked.

