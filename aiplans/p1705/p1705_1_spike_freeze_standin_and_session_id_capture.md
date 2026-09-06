---
Task: t1705_1_spike_freeze_standin_and_session_id_capture.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_2_*.md … aitasks/t1705/t1705_10_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-06 10:58
---

# t1705_1 — Spike: freeze stand-in respawn + session-id capture

## Step 0 — tmux preflight (run BEFORE anything else; blocking)

This task destructively manipulates tmux (`respawn-pane -k`, real `pane-died`
cleanup hooks, `kill-window`/`kill-server` on an isolated server). Its live
tests call `tests/lib/tmux_isolation.sh::require_clean_ait_server`, which
refuses to run from inside tmux or while the dedicated `-L ait` server has any
pane. Check this **first**, before editing a file:

```bash
[ -z "${TMUX:-}" ] && echo "PREFLIGHT_OK: not inside tmux" || { echo "PREFLIGHT_BLOCKED: this session runs inside tmux ($TMUX)"; }
tmux -L ait list-panes -a -F '#{pane_id} #{window_name}' 2>/dev/null && echo "NOTE: the -L ait server has panes — stop 'ait ide' / close them before running the live suites" || echo "PREFLIGHT_OK: -L ait server idle"
```

- `PREFLIGHT_BLOCKED` → **do not implement.** Execute the workflow's **Task
  Abort Procedure** (`task-abort.md`) so the task reverts to `Ready` with its
  plan kept, and tell the user to re-pick from a terminal that is NOT inside
  tmux. Do not set `AIT_LIVE_TMUX_TEST_FORCE=1` — it is for a dedicated CI
  box only.
- `-L ait` server has panes → implementation may proceed, but the live suites
  will refuse until that server is stopped; say so in the Final
  Implementation Notes if verification had to wait.

**Planning is exempt.** `aidocs/framework/tui_conventions.md:810-811` states it
directly: "The plan can still be written from inside; only implement + verify
need the outside-tmux precaution." This plan was written and verified from
inside the `-L ait` server; implementation was deliberately deferred to a
shell outside it.

## Context

The risk-mitigation spike `spike_frozen_standin_respawn` of the parent plan
(`aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md:559`).
Every later child pins contracts on tmux and code-agent facts that this repo
has never exercised: `respawn-pane` has zero call sites, agents run with
`remain-on-exit on` plus a `pane-died[N]` hook (`aitask_companion_cleanup.sh`)
that kills the window when no real agent sibling remains, and the
SessionStart hook mechanism has no precedent here for either agent. This
child proves each fact on an isolated server and records the answers as a
`## Spike findings (t1705_1) — PINNED` block in the parent plan, which the
parent's post-approval step copies into children 2–5. **Product code is out
of scope** — the deliverable is evidence plus the reusable probe and fixtures.

**Tmux-stress**: implement and verify from a shell **outside** the user's
`-L ait` server. `$TMUX` beats `TMUX_TMPDIR`; never `kill-server` from an
agent pane.

### Verified environment baseline (2026-09-06, this host)

Established during the plan-verification pass; re-check if the host changes.

| fact | value | consequence |
|---|---|---|
| platform | Darwin 24.6.0 — **no `/proc`** | Case 3 must not read `/proc/<pid>/environ` |
| `ps eww` / `ps -E` env read | returns **nothing** (SIP) | there is *no* way to read a foreign process's env on macOS → the process must self-report |
| tmux | 3.6a | — |
| claude | 2.1.263 | parent plan verified against 2.1.259 |
| codex | 0.153.4, `~/.codex/auth.json` present | Case 6 is runnable for real |
| `codex resume` | `codex resume [OPTIONS] [SESSION_ID] [PROMPT]`, `--last` | confirmed present |
| codex hook trust | `--dangerously-bypass-hook-trust` exists ("Run enabled hooks without requiring persisted hook trust") | codex hooks are real **and gated on persisted trust** — Case 6 must resolve trust before asserting |
| SessionStart hooks in repo | **none anywhere** (`.claude/settings.json` has only the `PreToolUse` guard; `.codex/config.toml` has no `[hooks]`; `seed/` templates carry no `hooks` key) | Cases 5–6 are greenfield; child 3 must add the seeding |

## Files

- **New** `tests/test_frozen_standin_spike.sh` — the probe, permanent (child 4's live control).
- **New** `tests/lib/fake_agent.sh` — long-running fake agent; `--resume <id>` / `resume <id>` print the id then sleep; `--report-env <file>` writes `$$` and selected env vars then sleeps; `FAKE_AGENT_EXIT=1` exits 1 immediately. Reused by children 5 and 8.
- **New** `tests/lib/observe_pane_died.sh` — fixture-owned `pane-died` observer; appends `pane_id`, `pane_dead`, `@aitask_frozen` and a timestamp to a log. Must **not** contain the string `aitask_companion_cleanup.sh` (see Case 1's ordering trap).
- **New (committed baselines)** `tests/data/session_hooks/claude_sessionstart.json`, `codex_sessionstart.json` — real captured payloads, redacted. **Committed by this task unconditionally**, not conditionally generated.
- **New** `tests/data/session_hooks/schema.json` — the three `_fixture_status` values (`captured` / `unsupported` / `provisional`) with their per-status required and forbidden fields, plus the redaction contract. Asserted on every run by Case 5a.
- **New** `tests/data/session_hooks/README.md` — per fixture: status, how it was captured (command, agent version, date), and how to refresh it.
- **Edit** `aiplans/p1705/p1705_3_session_id_capture_hooks.md` — step 7 must branch on `_fixture_status` instead of treating both fixtures as successful payloads (same commit as the findings block).
- **Edit** `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` — append the findings block.
- **Edit** `tests/test_guard_live_tmux.sh` (case 7 — add the missing socketed-`respawn-pane` assertion).

`tests/data/` currently holds one file (`font_coverage.json`); the repo splits
fixtures across `tests/data/`, `tests/fixtures/` and `tests/golden/` with no
dominant convention. The task file names `tests/data/session_hooks/` — keep it.

## Implementation steps

### Pre-phase (risk mitigations)

**P1 — `isolation_selfcheck`** (addresses the code-health risk that a wrong
isolation reaches the user's real agents). Before any destructive case runs,
assert the isolation actually took, and re-assert at end of run:

```bash
assert_isolation_took() {
    [ -z "${TMUX:-}" ] || fail "TMUX still set after require_isolated_tmux"
    [ "${AITASKS_TMUX_SOCKET+set}" = set ] && [ -z "$AITASKS_TMUX_SOCKET" ] \
        || fail "AITASKS_TMUX_SOCKET must be set-and-empty, got '${AITASKS_TMUX_SOCKET-unset}'"
    case "$TMUX_TMPDIR" in */ait_isolated_tmux_*) : ;; *) fail "TMUX_TMPDIR not isolated: $TMUX_TMPDIR" ;; esac
}
```

and, in the trap that runs at exit, assert the user's server was never
touched: `tmux -L ait list-panes -a` must return the same pane set (or the
same "no server" error) as it did before the first case. This is the guard
that converts "isolation silently regressed" into a named FAIL instead of a
destroyed session.

**P2 — `codex_hook_trust_preflight`** (addresses the goal-achievement risk
that Case 6 is written against a guessed schema and silently no-ops into a
false "unsupported" finding). Before Case 6 asserts anything, run `codex
doctor` and a minimal hook probe to establish (a) which config surface
0.153.4 honours — `[hooks]` in `.codex/config.toml` vs `.codex/hooks.json` —
and (b) whether the project hook layer needs persisted trust, and whether
`--dangerously-bypass-hook-trust` is required under the
`AITASKS_SPIKE_REAL_AGENTS=1` guard.

**Define what evidence licenses each verdict — "silent" is not "unsupported".**
A missing payload can be produced by an unavailable binary, missing auth, a
codex startup failure, an untrusted project layer, or simply the wrong config
surface. Pinning the parent's `codex = re-pick only` fallback on any of those
would convert an inconclusive probe into architecture. So the preflight must
first establish a **positive control**, then emit exactly one of four
distinguishable verdicts:

*Positive control (both legs required before any verdict but `unavailable`):*
- **the capture script works** — invoke `capture_hook.sh` directly with a
  synthetic stdin payload and assert it writes the expected file. This
  separates "hook never fired" from "our capture script is broken".
- **codex actually ran and produced a session** — assert the `codex exec`
  invocation exited successfully *and* a new session is discoverable
  (`codex resume --last`, or a fresh file under `~/.codex/sessions/`). This
  separates "hook never fired" from "codex never started".

*Verdicts:*

| verdict | evidence | may it change the parent contract? |
|---|---|---|
| `unavailable` | `command -v codex` fails, or auth/`codex doctor` reports the CLI unusable | **no** — nothing was tested |
| `trust_blocked` | hook config accepted, but the run reports untrusted hooks, or the payload appears only with `--dangerously-bypass-hook-trust` | **no** — a deployment question, not a capability one |
| `config_unresolved` | positive control passes, but no tried surface (`[hooks]` in `.codex/config.toml`, `.codex/hooks.json`) is demonstrably accepted by codex | **no** — we failed to find the surface, which is not the same as it not existing |
| `unsupported` | positive control passes, a config surface is demonstrably accepted **and** trusted, and no SessionStart payload is delivered | **yes** — this is the only verdict that pins `codex = re-pick only` |

Record the verdict in `FINDINGS` **before** running Case 6's assertions.

**P3 — `fixture_baseline_validation`** (addresses the goal-achievement risk
that child 3's unconditional fixture consumers are built on evidence a normal
run never checks). Commit the two SessionStart fixtures as **baselines** plus
a `schema.json` contract, and validate them on **every** run with no binaries
required. Implemented as **Case 5a** (step 7); the real-agent lanes (steps 8
and 9) refresh-and-diff against those baselines rather than being their only
producer.

**P4 — `interactive_launch_fixture_control`** (addresses the goal-achievement
risk that children 3/5 pin a fixture shape the production path never
produces). **This is a precondition for pinning, not a trailing control** —
it was moved out of the post-phase precisely because a comparison performed
*after* a baseline is chosen cannot un-pin it. The rule is stated in Case 5a's
**Pinning rule** and enforced by Case 5a's `_capture_mode == interactive`
assertion; the interactive capture itself is performed in **Case 5b** (step 8)
and must succeed **before** any fixture is committed as authoritative. A
headless-only state is not a passing state — it is either a documented
non-authoritative variant or a `provisional` contract that children 3/5 are
told not to rely on.

---

1. **Scaffold** `tests/test_frozen_standin_spike.sh`. Source
   `tests/lib/asserts.sh` and call `assert_counters_init` — **required**,
   because the cases run in `( … )` subshells and CLAUDE.md's rule is that
   in-process `PASS`/`FAIL` increments die at subshell exit; add
   `assert_counters_load` in the footer before the `[[ "$FAIL" -eq 0 ]]`
   guard. (Do **not** copy `tests/test_shadow_capture.sh`'s counter shape —
   it hand-rolls `PASS/FAIL/TOTAL` and never sources the isolation helper;
   it is a good model for *live-block structure and skip guards* only.)

   Then source `tests/lib/tmux_isolation.sh` and call, **in this order**:

   ```bash
   require_clean_ait_server     # FIRST — reads $TMUX and the -L ait server
   require_isolated_tmux        # SECOND — unsets TMUX, redirects TMUX_TMPDIR
   ```

   The order is load-bearing and documented at `tests/lib/tmux_isolation.sh:115-119`:
   `require_isolated_tmux` unsets `$TMUX` (`:55-56`), which is exactly the
   evidence `require_clean_ait_server` refuses on (`:130-146`). Reversing them
   makes the clean-server check silently pass from inside tmux.

   Every tmux call goes through `ait_tmux` from
   `.aitask-scripts/lib/tmux_exec.sh:103`. Note what isolation does to it:
   `require_isolated_tmux` exports `AITASKS_TMUX_SOCKET=""` (`:85`), and
   `ait_tmux_socket_args` (`tmux_exec.sh:53`) emits **no `-L` flag at all**
   for a set-but-empty value. Isolation therefore comes from the redirected
   `TMUX_TMPDIR`, not from a named socket — do not assume a `-L <name>` is in
   play.

2. **Fixture builder** `make_agent_window()` — build the window through the
   *shipped* Python helpers so the hook wiring is the real one:
   `python3 - <<'EOF'` with `.aitask-scripts/lib` on `sys.path`, importing
   `agent_launch_utils`, calling
   `launch_in_tmux(fake_agent_cmd, TmuxLaunchConfig(session=…, window="agent-pick-1", new_window=True, …))`
   (`TmuxLaunchConfig` is the real class name, `:74`; `launch_in_tmux` is
   `:1326-1407` and returns the **`pane_pid`** — map it to a pane id with
   `resolve_pane_id_by_pid`, `:1410`). Then `split-window` a companion
   running `sleep 1000`, and call `attach_companion_cleanup_hook(agent_pane,
   companion_pane)` (`:1536-1599`; it sets `remain-on-exit on` and installs
   `pane-died[<slot>]`).

   **Stamp the companion explicitly** with
   `@aitask_monitor_kind=minimonitor:<pid>` — the constant is
   `MONITOR_KIND_OPTION` at `.aitask-scripts/lib/monitor_marker.py:32`, and
   the value must match `_MARKER_RE = ^(minimonitor|monitor):([0-9]+)$`
   (`:38`); `agent_launch_utils.mark_monitor_pane` (`:1475-1502`) is the
   shipped writer. This is what makes the real cleanup script recognise the
   pane: `aitask_companion_cleanup.sh:68-86` lists panes as
   `#{pane_id}|#{@aitask_shadow_target}|#{@aitask_monitor_kind}` and treats a
   non-empty `kind` as a companion.

   **Do not copy `tests/test_kill_agent_pane_smart.sh`'s approach.** Its
   `make_window()` is a Python function inside a heredoc (`:106`, docstring
   `:107-113`) that stamps **no pane options at all** — it detects the
   companion by monkey-patching `mc._is_companion_process` against an argv
   sentinel (`:97`). That works for exercising `count_other_real_agents` in
   Python, but it would leave the *shell* cleanup script blind. (t1699 is
   `status: Implementing` and, per its own postmortem, has **not** edited
   `make_window` yet — there is no landed reordering to accommodate, but read
   `.aitask-data/aitasks/t1699_kill_smart_live_fixture_orders_companion_last.md`
   before touching that file.)

3. **Case 1 — stand-in respawn keeps the window.**

   **Hook evidence: use a separate indexed observer hook, NOT `PATH`.**
   A `PATH`-prepended wrapper cannot intercept the shipped hook, for two
   independent reasons, so the case's central claim would be unobserved and
   then falsely inferred from the window merely surviving:
   - `attach_companion_cleanup_hook` builds an **absolute** path —
     `script_path = str(Path(__file__).resolve().parent.parent / CLEANUP_SCRIPT_NAME)`
     and `hook_cmd = f"run-shell '{script_path} …'"`
     (`agent_launch_utils.py:1589-1592`). `PATH` is never consulted.
   - `run-shell` executes in the **tmux server's** environment, not the test
     shell's, so exporting `PATH` in the test would not reach it even if the
     path were relative.

   Instead install a **second, independent `pane-died` observer** — and it
   **MUST occupy a lower hook index than the shipped cleanup**, i.e. be
   installed **before** `attach_companion_cleanup_hook`, not after.

   **Why the order is load-bearing (not a style preference).** tmux runs
   indexed hooks in index order, and `aitask_companion_cleanup.sh` ends with

   ```sh
   tmux kill-pane -t "$primary" 2>/dev/null || true     # :86
   ```

   which sits **outside** the `if [ "$others" -eq 0 ]` guard (`:82-85`) and so
   runs **unconditionally** whenever the hook fires — the primary pane is
   killed on every invocation, not only when siblings are absent. An observer
   at a higher index would therefore run after the primary pane, and with it
   the window, is already gone: `#{pane_id}` / `#{@aitask_frozen}` would
   expand against a dead or absent pane and yield nothing, putting us straight
   back to inferring the result from the window's fate instead of measuring
   it.

   Install it at slot 0, **before** the shipped wiring:

   ```bash
   # 1. observer FIRST, at index 0
   ait_tmux set-hook -p -t "$agent_pane" 'pane-died[0]' \
     "run-shell '$FIXTURE_DIR/observe_pane_died.sh \"#{pane_id}\" \"#{pane_dead}\" \"#{@aitask_frozen}\"'"

   # 2. THEN attach_companion_cleanup_hook(...) — it appends at
   #    max(indices)+1 == 1 and MUST return "installed"
   ```

   `observe_pane_died.sh` emits **one** `printf` line (pane id, `pane_dead`,
   the expanded `@aitask_frozen`, timestamp) appended to
   `$FIXTURE_DIR/pane_died.log` — a single sub-`PIPE_BUF` `O_APPEND` write, so
   the record lands atomically and cannot be torn or lost when the cleanup
   hook runs immediately after. The stamp is captured **at hook-expansion
   time**, which is exactly the moment the question is about. Passing the pane
   id and the option as tmux **format arguments** — the same shape the shipped
   hook uses for `<agent_pane> <companion_pane>` — is what makes "was the stamp
   visible to a hook running at pane-died time?" a recorded observation.

   **The two ordering constraints are compatible — but only in this
   direction.** `_pane_died_hook_indices` sets `has_cleanup = True` for any
   `pane-died` line containing `CLEANUP_SCRIPT_NAME` (`:1531`), and
   `attach_companion_cleanup_hook` returns `"existing"` and installs
   **nothing** when that is true (`:1587-1589`). So the observer command must
   never contain the literal string `aitask_companion_cleanup.sh`; with that
   respected, installing the observer first leaves `indices=[0]`,
   `has_cleanup=False`, and the real hook lands at slot 1 exactly as intended.
   The script is named `observe_pane_died.sh` for precisely this reason.

   **Assert the wiring is the shipped one:** `attach_companion_cleanup_hook`
   must return `"installed"`, and a `show-hooks -p` assertion must confirm the
   observer sits at a **strictly lower** index than the cleanup entry.
   `"existing"`, `"unverified"`, or an inverted index order means the fixture
   is not exercising the real hook in an observable order — fail the case
   loudly rather than continuing.

   Then: stamp `@aitask_frozen=abc123` on the agent pane;
   `ait_tmux respawn-pane -k -t "$agent_pane" 'sleep 1000'`; sleep 1; assert
   the window exists, the companion pane exists, the agent pane id is
   unchanged and `#{pane_current_command}` is `sleep`. Record in `FINDINGS`
   whether `pane_died.log` gained a line (did `pane-died` fire at all?) and
   what `@aitask_frozen` read at that moment (was the stamp visible?).

   **Negative control**: repeat with the cleanup script unmodified and no
   stamp-aware abstention — if the window survives even without abstention,
   that too is a finding (`pane-died` may simply not fire on a `-k` respawn);
   if it dies, the control proves the abstention is load-bearing. Note that
   `@aitask_frozen` has **zero** occurrences in the repo today, so the
   abstention branch does not exist yet — the control is measuring the
   current shipped behaviour, which is the point.

4. **Case 2 — options survive respawn; pane_pid changes.** Assert
   `#{@aitask_frozen}` still reads `abc123` after the respawn; assert the new
   `#{pane_pid}` ≠ the old one.

5. **Case 3 — `env` prefix keeps `pane_pid` = the launched process, and the
   process sees the variables.** This validates the exemption implied by
   `launch_in_tmux`'s docstring (`:1335-1345`): that docstring forbids a
   wrapper that **outlives** the agent (it would break `pid_anchor`'s
   lock liveness, t1465) and says nothing about `env`. `env` *execs* into the
   target, so it should be exempt — this case proves it.

   **Do not use `/proc/<pid>/environ`.** This host is macOS: there is no
   `/proc`, and `ps eww` / `ps -E` return no environment at all (SIP), so
   there is no portable way to read a *foreign* process's env. The repo's
   precedent for platform-split process introspection is
   `.aitask-scripts/lib/pid_anchor.sh:39-72` (Linux `/proc` branch +
   BSD `ps` branch), and `tests/lib/proc_fixtures.sh` records the
   macOS-is-supported rule for exactly this class of footgun.

   **Do not identify the process with `pgrep -f 'sleep 1000'` either.** A
   pattern that generic can match a concurrent case in this same suite, a
   parallel test run, or an unrelated user process — so the assertion can
   pass while inspecting the *wrong* process, which is worse than failing.
   Nothing in this case may identify a process by command-line pattern.

   Instead, **have the process self-report into a fixture-owned file**:

   ```bash
   report="$(mktemp "$FIXTURE_DIR/envprobe.XXXXXX")"     # unique, owned by this run
   ait_tmux respawn-pane -k -t "$pane" \
     "env AITASK_RESTORE_RECORD=x '$PROJECT_DIR/tests/lib/fake_agent.sh' --report-env '$report'"
   ```

   `fake_agent.sh --report-env <file>` writes `pid=$$` and
   `AITASK_RESTORE_RECORD=$AITASK_RESTORE_RECORD` to `<file>`, then sleeps.
   Assert: the reported `pid` equals `#{pane_pid}` **read from this pane**
   (proves `env` exec'd rather than wrapped), and the reported variable
   equals `x` (proves the variable reached the process).

   This is strictly stronger than either the `/proc` read or `pgrep`: the
   pid and the environment come from **one self-report by the process
   itself**, tied to a path only this run knows, so there is no way to
   observe a different process by accident.

6. **Case 4 — `run-shell -b` outlives the caller pane.** From the agent
   pane's shell: `ait_tmux run-shell -b 'sleep 2; touch <marker>'`, then
   immediately `respawn-pane -k` that pane; assert the marker appears within 4 s.

7. **Case 5a — fixture contract (ALWAYS runs; no real agents, no opt-in).**
   Child 3 consumes these fixtures unconditionally — `p1705_3` step 7 feeds
   `tests/data/session_hooks/{claude,codex}_sessionstart.json` into
   `tests/test_session_hook.sh` as plain test input. If the only producer
   were the opt-in real-agent lane, a normal CI or developer run would skip
   it and leave fixture **presence, redaction, schema and freshness
   unproved**, with child 3 then built on missing or stale evidence.

   So the fixtures are **committed baselines**, and this case validates them
   on every single run, with no binaries required.

   **Every fixture carries an explicit `_fixture_status`.** A single
   "required keys" rule cannot be right for all three outcomes this spike can
   legitimately reach — a proven-unsupported agent has no payload to carry,
   and an unpinned contract must not masquerade as a settled one. So
   `schema.json` defines **three statuses with different required fields**,
   and validation is per status:

   | `_fixture_status` | meaning | required fields | forbidden |
   |---|---|---|---|
   | `captured` | a real, authoritative payload | `session_id`, `transcript_path`, `cwd`, `source` (all non-empty strings) + `_capture_mode: interactive`, `_agent_version`, `_captured_at` | `_capture_mode: headless` |
   | `unsupported` | the agent provably has no SessionStart hook | `_reason` (must be exactly `unsupported`), `_evidence` (both positive-control results from P2), `_agent_version`, `_captured_at` | **any** payload key — no `session_id`/`transcript_path`/`source`, so nothing can read a half-payload as real |
   | `provisional` | inconclusive — not authoritative, not disproved | `_reason` (one of `no_interactive_capture`, `unavailable`, `trust_blocked`, `config_unresolved`), `_agent_version`, `_captured_at`; payload keys **optional** and, when present, non-authoritative | `_capture_mode: interactive` |

   Common assertions for all three statuses:
   - the file exists, parses as JSON, and `_fixture_status` is one of the three;
   - the status-specific required fields above are present and non-empty, and
     the forbidden fields are absent;
   - it is **redacted**: when `cwd` is present it is exactly `/REDACTED`, and
     no value contains `$HOME`, the current user name, or an absolute path
     under `/Users/` or `/home/`;
   - `README.md` records, per fixture, the status, the capturing command,
     agent version and date.

   **The P2 verdict taxonomy maps onto these statuses, and only one mapping
   pins anything:** P2's `unsupported` → `_fixture_status: unsupported`;
   P2's `unavailable` / `trust_blocked` / `config_unresolved` → `provisional`
   with the verdict as `_reason`. This is what stops an untested or
   misconfigured environment from being recorded as a capability limit.

   **Child 3 must branch on `_fixture_status`, not assume a payload.** This is
   a cross-child contract, so it goes in the findings block that is copied
   into children 2–5, and `aiplans/p1705/p1705_3_session_id_capture_hooks.md`
   step 7 must be updated in the same commit (its current text feeds both
   fixtures into `tests/test_session_hook.sh` as if each were a successful
   payload):
   - `captured` → run the full `upsert` argv assertions as written today;
   - `unsupported` → assert the opposite contract for that agent (no hook
     installed, no `upsert` call) and record an explicit skip, never a pass
     by absence;
   - `provisional` → run the assertions as **advisory** and do not treat
     `schema.json` as settled for that agent.

   **Pinning rule — which shape is authoritative (decided here, not later).**
   The framework's production path launches agents **interactively** via
   `launch_in_tmux`; `claude -p` is a spike convenience only. Therefore:

   1. The **authoritative** baseline — the file children 3 and 5 consume, and
      the file `schema.json` is derived from — is the payload captured on the
      **interactive** path. Nothing else may be pinned.
   2. A headless capture is **never** committed as the baseline. If its shape
      differs from the interactive one, the difference is recorded in
      `README.md` as a documented variant, and — only if a downstream child
      genuinely needs it — added as an explicitly named, explicitly
      non-authoritative second file `claude_sessionstart.headless.json`,
      which `schema.json` does not govern and no child consumes by default.
   3. If interactive equivalence has **not** been established (no real-agent
      run has ever produced an interactive capture, or the bounded wait in
      Case 5b expired), the fixture is committed with
      `_fixture_status: provisional` and `_reason: no_interactive_capture`.
      `README.md` must say so and the findings block must report
      `claude fixture: provisional (no interactive capture)` — an explicit
      instruction to children 3/5 not to treat the schema as settled.

   This is the case that makes the fixtures a maintained contract rather
   than a by-product of one developer's machine.

8. **Case 5b — Claude SessionStart capture: refresh-and-diff** (guarded by
   `command -v claude` and `AITASKS_SPIKE_REAL_AGENTS=1`). Scratch project dir with
   `.claude/settings.json`:
   `{"hooks":{"SessionStart":[{"matcher":"startup|resume","hooks":[{"type":"command","command":"<abs>/capture_hook.sh","timeout":10}]}]}}`
   where `capture_hook.sh` writes stdin + `env | grep -E '^(TMUX_PANE|AITASK_AGENT_STRING)='`
   to a file. Launch `env AITASK_AGENT_STRING=claudecode/opus5 claude -p 'say hi'`
   in a pane; assert the payload has `session_id`, `transcript_path`, `cwd`,
   `source`; assert `TMUX_PANE` and `AITASK_AGENT_STRING` were visible
   (`aitask_codeagent.sh:611` exports the latter immediately before `exec`).
   Relaunch `claude --resume <id> -p 'hi again'` in a respawned pane; assert a
   second payload with `source: resume` and the same id.

   **Then capture the same payload on the production path — this is the
   authoritative one.** In the same scratch project with the same hook,
   launch `claude` **interactively** through `agent_launch_utils.launch_in_tmux`
   (not `-p`) and capture a third payload. Diff the key sets:

   - **Equivalent** → commit the interactive payload as the baseline with
     `_capture_mode: interactive`, and record
     `claude SessionStart: headless keys == interactive keys: yes`.
   - **Different** → the **interactive** payload is still the baseline; the
     headless shape goes to `README.md` as a documented variant (and, only if
     a child needs it, the explicitly non-authoritative
     `claude_sessionstart.headless.json`). Record
     `claude SessionStart: headless keys == interactive keys: no (<diff>)`.
   - **Interactive capture unavailable/failed/timed out** → commit nothing as
     authoritative; mark the fixture `_fixture_status: provisional` with
     `_reason: no_interactive_capture` per Case 5a's rule 3.

   **Every wait for a hook payload is bounded — the opt-in suite must not
   hang.** An interactive `claude` in a pane will sit at its prompt forever
   if the hook never fires, so a naive "poll until the file appears" loop
   wedges the whole suite instead of failing it. Use the existing helper
   rather than a bare `timeout`:

   ```bash
   # tests/lib/proc_fixtures.sh :: run_bounded <secs> <outfile> <cmd...>
   #   -> the command's status, or 124 if it had to be killed
   . "$PROJECT_DIR/tests/lib/proc_fixtures.sh"
   run_bounded "$HOOK_WAIT_SECS" "$out" wait_for_payload "$payload_file"
   ```

   `run_bounded` is the repo's sanctioned bound: it already handles macOS
   shipping GNU `timeout` only as `gtimeout` (and a third rung for a box with
   no Homebrew coreutils), which a bare `timeout` would fail at with exit 127
   — never reaching the behaviour under test. Apply it to **both** the
   headless and the interactive capture waits, with a generous but finite
   `HOOK_WAIT_SECS` (default ~30 s, overridable).

   Exit status `124` is **not** a suite failure: it is the
   `no_interactive_capture` branch above — record it and continue. Teardown
   needs nothing extra; the isolated-server cleanup trap already kills the
   `-L <sock>` server and with it any agent still sitting in a pane.

   **This lane refreshes and diffs; it never *is* the fixture's only
   source.** Redact every captured payload, then diff against the committed
   baseline. A difference is reported as a `FINDINGS` line
   (`claude fixture: baseline matches live capture: yes | no (<key diff>)`)
   and **fails the case**, because a silent drift means child 3 is testing
   an agent version that no longer exists. Rewriting the baseline requires an
   explicit `--refresh-fixtures` flag, which updates the JSON, the
   `_capture_mode` field *and* the `README.md` provenance line in the same
   commit.

   `claude -p` is used deliberately and is **already gated** behind
   `AITASKS_SPIKE_REAL_AGENTS=1`, which satisfies
   `aidocs/framework/shell_conventions.md:120-127` ("gate any genuinely
   non-interactive need behind an explicit opt-in flag"). Its cost is the
   reason the lane is opt-in. See Case 5a's **Pinning rule** for why a
   headless-only fixture can never be the authoritative one.

9. **Case 6 — Codex SessionStart + `codex resume`.** Codex 0.153.4 is
   installed and authenticated. Using the schema and trust answer from
   pre-phase **P2**, install the capture hook, run `codex exec 'say hi'`,
   capture, then `codex resume <id>` in a respawned pane. Assert the same
   payload fields as Case 5a's schema where they exist.

   **Failures remain findings, but only one of them is a capability
   verdict.** Write P2's verdict verbatim into the block —
   `codex hooks: unavailable | trust_blocked | config_unresolved | unsupported`
   — and **change the parent's contract only on `unsupported`**. The other
   three are explicitly inconclusive: the findings block must then say
   `codex = re-pick only: NOT pinned (inconclusive: <verdict>)`, so a later
   child cannot read an untested environment as a proven limitation. Record
   `codex resume: works | fails` independently of the hook verdict — resume is
   a separate capability and `codex resume [SESSION_ID] [PROMPT]` is already
   confirmed present in 0.153.4. The same **refresh-and-diff**
   rule as Case 5b applies: the committed `codex_sessionstart.json` baseline
   is validated by Case 5a on every run, and this lane diffs a live capture
   against it rather than being its only producer. Bound every wait for a
   codex hook payload with `run_bounded` exactly as Case 5b does; a `124`
   maps to the `config_unresolved` verdict, not to a hang.

   **The committed codex fixture always exists — its `_fixture_status`
   records which answer we got**, so child 3 has a defined input in every
   case: `captured` on success, `unsupported` only on P2's proven verdict
   (payload keys absent, `_evidence` carrying both positive-control results),
   and `provisional` with the verdict as `_reason` for `unavailable` /
   `trust_blocked` / `config_unresolved`.

10. **Case 7 — live-tmux guard.** The guard **already allows** a socketed
   respawn: `.claude/hooks/guard_live_tmux.py` lists `respawn-pane` in
   `DESTRUCTIVE_VERBS` (`:63-72`) but `check()` does `if has_socket: continue`
   *before* any verb test. So there is nothing to fix — the deliverable is
   the **missing regression assertion**: `tests/test_guard_live_tmux.sh`
   covers a bare `respawn-pane` deny (`:69`) and a socketed *kill-pane*
   allow, but never a socketed *respawn-pane*. Add it via the existing
   `decision_for()` helper (`:36-49`), asserting no `deny` for
   `tmux -L throwaway respawn-pane -k -t %1 sleep 1`.

   Note for the implementer: the guard is a `PreToolUse` hook that inspects
   only `payload["tool_input"]["command"]` — the Bash command string the
   agent runs. It never sees tmux calls made *inside* a script, so running
   `bash tests/test_frozen_standin_spike.sh` is unaffected regardless of what
   the script does. Only a respawn typed directly into a Bash call is denied.

11. **Findings block.** The script prints a `FINDINGS:` summary; copy it
    into the parent plan under `## Spike findings (t1705_1) — PINNED` in the
    format the task file shows, and commit with `./ait git`.

    Extend the task file's format with the three lines this plan added, so
    the contract propagates to children 2–5 with the rest of the block:

    ```
    - claude fixture: captured | provisional(<reason>) ; interactive == headless keys: yes | no (<diff>)
    - codex fixture: captured | unsupported | provisional(<reason>)
    - codex = re-pick only: pinned | NOT pinned (inconclusive: <verdict>)
    ```

    Child 3's plan edit (branching on `_fixture_status`) lands in this same
    commit — the fixture statuses are a cross-child contract, and the plan's
    own rule is that a deviation updates the parent plan and every sibling
    plan together.

## Verification

```bash
bash tests/test_frozen_standin_spike.sh                       # from a shell OUTSIDE the -L ait server
AITASKS_SPIKE_REAL_AGENTS=1 bash tests/test_frozen_standin_spike.sh   # with real claude/codex
bash tests/test_guard_live_tmux.sh
bash tests/test_no_raw_tmux.sh
grep -A8 'Spike findings' aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md

# the fixtures child 3 consumes must be present, well-formed and redacted
# WITHOUT any agent binary — Case 5a covers this and must pass in the
# no-opt-in run above. Spot-check the contract directly:
ls tests/data/session_hooks/{claude,codex}_sessionstart.json tests/data/session_hooks/schema.json
# every fixture declares a status; redaction is asserted only where cwd exists
jq -e '._fixture_status | IN("captured","unsupported","provisional")' \
   tests/data/session_hooks/{claude,codex}_sessionstart.json
jq -e 'has("cwd") | not or .cwd == "/REDACTED"' \
   tests/data/session_hooks/{claude,codex}_sessionstart.json
# an `unsupported` fixture must carry no payload key at all
jq -e 'select(._fixture_status=="unsupported") | has("session_id") | not' \
   tests/data/session_hooks/codex_sessionstart.json
grep -rn "$HOME" tests/data/session_hooks/ && echo "LEAK: unredacted home path" || echo "redaction OK"
```

The first invocation (no `AITASKS_SPIKE_REAL_AGENTS`) must still exercise
Case 5a and cases 1–4 and 7 — a run that skips *everything* agent-related is
the normal CI shape and must still prove the fixture contract.

`tests/test_no_raw_tmux.sh` scans **only** `.aitask-scripts/` (`:104`, header
`:23` — "NOT scanned: `tests/`"), so it will not police the new test file; it
is run here to prove nothing under `.aitask-scripts/` regressed.

Step 9 (Post-Implementation) of the task workflow handles commit, sibling
context and archival.

## Risk

### Code-health risk: medium
- The suite destructively manipulates tmux (`respawn-pane -k`, real `pane-died` hooks) and a mis-ordered or regressed isolation reaches the user's live `-L ait` server and every agent on it. The reversed `require_*` ordering found in the pre-verification plan is direct evidence that this is easy to get wrong. · severity: high · → mitigation: inline pre-phase isolation_selfcheck
- Case 1's negative control deliberately reproduces a window kill; if it runs against a non-isolated server it destroys real work. · severity: medium · → mitigation: inline pre-phase isolation_selfcheck
- Code footprint is otherwise small and additive (two new test files, fixtures, one added assertion in an existing test), touching no product code. · severity: low · → mitigation: TBD

### Goal-achievement risk: high
- The spike exists to answer unknowns, and this verification pass already falsified several of its own assumptions (`/proc` on macOS, the fixture's pane-option stamping, the isolation call order). Further assumptions may fail during implementation, and the plan's value is the *findings*, not a green suite. · severity: high · → mitigation: TBD
- Cases 5–6 depend on real agents, real auth, and a codex hook schema that is undocumented in `codex --help`; a mis-guessed schema yields a false "unsupported" verdict that the parent would then pin as architecture. · severity: high · → mitigation: inline pre-phase codex_hook_trust_preflight
- The framework launches agents interactively, but Case 5b captures via `claude -p`; a headless-only payload shape could mislead children 3 and 5, whose unit tests consume the fixture. · severity: medium · → mitigation: inline pre-phase interactive_launch_fixture_control
- Child 3 consumes the session-hook fixtures unconditionally, but the real-agent lane that captures them is opt-in; without committed baselines a normal run leaves their presence, redaction, schema and freshness entirely unproved. · severity: high · → mitigation: inline pre-phase fixture_baseline_validation
- Case 1's evidence path had to observe whether `pane-died` fires and whether the frozen stamp is visible to it; a `PATH`-based instrumentation cannot intercept the shipped hook (absolute path at `agent_launch_utils.py:1589-1592`, executed in the tmux server's environment), which would have left the spike's central claim inferred rather than measured. Addressed in Case 1's design by a separate indexed `pane-died` observer. · severity: high · → mitigation: Case 1 observer hook (design fix, no separate phase)

### Planned mitigations
- timing: pre-phase | name: isolation_selfcheck | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — destructive blast radius reaching the user's live -L ait server | desc: assert isolation actually took (TMUX unset, AITASKS_TMUX_SOCKET set-and-empty, TMUX_TMPDIR inside the isolated dir) before any destructive case, and assert the user's -L ait pane set is unchanged at end of run
- timing: pre-phase | name: codex_hook_trust_preflight | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — Case 6 written against a guessed codex hook schema silently no-ops into a false "unsupported" finding | desc: run codex doctor plus a minimal hook probe to establish which config surface 0.153.4 honours and whether persisted hook trust (or --dangerously-bypass-hook-trust) is required, before Case 6 asserts anything
- timing: pre-phase | name: fixture_baseline_validation | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — child 3 consumes session-hook fixtures unconditionally while the capturing lane is opt-in, leaving presence/redaction/schema/freshness unproved on a normal run | desc: commit baseline claude/codex SessionStart fixtures plus a schema.json contract defining three explicit statuses (captured/unsupported/provisional) with per-status required and forbidden fields, and validate status, those fields and redaction on every run with no binaries required (Case 5a); the real-agent lanes refresh-and-diff against those baselines instead of being their only source, and child 3 branches on _fixture_status instead of assuming a payload
- timing: pre-phase | name: interactive_launch_fixture_control | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — headless `claude -p` payload may not match the framework's real interactive launch path, and a comparison made after a baseline is chosen cannot un-pin it | desc: make interactive equivalence a PRECONDITION for pinning — the authoritative baseline and schema.json derive from a launch_in_tmux interactive capture (asserted by Case 5a's `_capture_mode == interactive`), a differing headless shape becomes a documented non-authoritative variant, and an absent interactive capture marks the contract provisional so children 3/5 do not consume it as settled

## PINNED contracts (from p1705 — do not re-decide)

Copied verbatim from `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A–§D. On any discrepancy the parent plan wins; if a child must deviate, update the parent plan and every sibling plan in the same commit.


#### A. Session store — `lib/agent_sessions.py` + `aitask_agent_sessions.sh`

- Path `~/.config/aitasks/agent_sessions.json`, env override
  `AITASKS_AGENT_SESSIONS_FILE`, lock dir derived from the resolved path
  (`<file>.lockd`), 0600 with `_target_mode` preservation, write via
  `lib/atomic_write.py`. Captures under `~/.config/aitasks/frozen/<id>/`
  (0700 dir; `capture.ansi`, `capture.txt`), env `AITASKS_FROZEN_DIR`.
- Schema v1:
  ```json
  {"version": 1, "sessions": [{
    "id": "7f3a2c1d",                 // record id (8 hex, os.urandom) — PRIMARY KEY
    "root": "/real/path/project",     // realpath, both sides         ┐ DURABLE IDENTITY
    "window": "agent-pick-1705",      //                               │ (root, window, window_slot)
    "window_slot": 0,                 // assigned once; >0 only for a 2nd agent in the same window ┘
    "pane_id": "%104", "pane_pid": 41233,   // LOCATION / GENERATION data — replaceable, never identity
    "session": "aitasks",             // tmux session name — display only
    "operation": "pick", "task_id": "1705",          // task_id "" when unbound
    "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
    "codeagent_session_id": "", "transcript_path": "",  // "" = unknown → re-pick only
    "started_at": "2026-09-04T09:12:03Z",
    "state": "live",                  // live | freezing | frozen | restoring | aborting
    "state_at": "2026-09-04T09:12:03Z",
    "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",   // LEASE of the in-flight freeze/restore (see below)
    "frozen_at": "", "capture_ansi": "", "capture_txt": "",
    "capture_lines": 0, "last_phase": "",
    "standin_pid": 0,                 // #{pane_pid} of the stand-in viewer, written at freeze-commit and every stand-in respawn
    "launch_pid": 0,                  // #{pane_pid} of the replacement agent, written by restore-launched (nonce-bound)
    "restore_attempts": 0, "restore_mode": "",   // "" | resume | repick (current attempt)
    "ack": "",                        // "" | hook | liveness — how the last restore was confirmed
    "last_error": ""                  // "" | "<nonce>:session_mismatch" | "<nonce>:<reason>" — coordinator-readable outcome channel
  }]}
  ```
  `pane_id` / `pane_pid` are **location and generation data**: a tmux server
  restart, a reattach or a respawn replaces them on the same record. They
  are never part of the identity key and a recycled `%N` can attach to
  nothing on its own — attachment needs either `@aitask_record` on the pane
  (options die with the pane, so a recycled pane never carries a stale one)
  or a `(root, window)` match under the conflict policy below.
  Unknown `state` = corruption (not a default). `load()` raises
  `MalformedSessionsError`; `load_safe()` returns empty. Generation normalised
  to `SCHEMA_VERSION` on read.
- **Record ownership (one allocator) and the `(root, window)` conflict
  policy.** The `upsert` verb is the *only* creator of records. Resolution
  order for a caller without `--restore-of`:
  1. `--id <rid>` (from `@aitask_record` on the caller's pane) → that record,
     whatever its `(root, window)` (a renamed window keeps its record).
  2. Else, **among `live` records only** with the caller's `(root, window)`,
     the relocation candidates are: the one whose `pane_id` equals the
     caller's pane, else those whose `pane_pid` is dead or whose pane no
     longer exists. **Exactly one candidate** → it is the same agent slot:
     replace `pane_id`/`pane_pid`, update session id / transcript / agent
     string, print `UPSERTED:<id>|updated` (the tmux-restart and reattach
     case — no second record). **More than one candidate** (two agents shared
     the window before a server restart; nothing on the caller's side can
     tell them apart) → **fail closed on relocation**: fall through to rule 3
     and print `UPSERTED:<id>|created_slot<N>|ambiguous_relocation`; the stale
     records are left for purge (rule: a `live` record whose `pane_pid` is
     dead and whose `pane_id` is absent from an enumerated window →
     `DROPPED:…|dead_pane`), never guessed.
     Transitional records (`freezing`/`restoring`/`aborting`) are **never**
     relocated or updated by an unstamped caller: they are touched only by
     `--restore-of` + the current nonce, or by `reconcile`. If the caller's
     pane *is* a transitional record's pane → refuse
     (`UPSERT_REFUSED:<id>|<state>_unacknowledged`, a stray session in a
     transacting pane); otherwise they are simply not candidates.
  3. Else every `(root, window)` record is `live` in **another** pane (a
     second agent split into the same window), transitional, or `frozen`
     (retained state whose window name is being reused, e.g. the same task
     re-picked after a tmux restart) → **create beside it**: new record,
     `window_slot` = lowest unused slot for that `(root, window)`, print
     `UPSERTED:<id>|created_slot<N>`. A retained frozen record never blocks a
     live launch and is never attached to; it stays restorable into a fresh
     window (`unique_window_name` disambiguates) and is listed distinctly by
     its `frozen_at`.
  4. Else → create (`state=live`, `window_slot=0`), print `UPSERTED:<id>|created`.
  In every create/update branch the caller's pane is stamped
  `@aitask_record=<id>`.
  Other branches:
  - record exists in `restoring` **and** the caller passes
    `--restore-of <id> --nonce <n>` (the hook forwards them from the
    replacement agent's environment, §D) → the **restore acknowledgement**:
    nonce must equal `op_nonce`; in `resume` mode `--session-id` must equal
    `codeagent_session_id` — else the store **persists**
    `last_error="<nonce>:session_mismatch"` (state unchanged) and prints
    `RESTORE_SESSION_MISMATCH:<id>` exit 7. The hook has no return channel to
    the detached coordinator, so the record *is* the channel: the coordinator
    and `reconcile` both read `last_error` for the current nonce and take the
    abort branch, never the liveness fallback. In `repick` mode the new
    session id is adopted. On success: `pane_id`/`pane_pid` updated from the
    caller's pane, `@aitask_record` stamped on it, state `live`, `ack=hook`,
    capture files deleted, print `UPSERTED:<id>|restored`;
  - record exists in `restoring` without `--restore-of`/`--nonce` → refuse,
    print `UPSERT_REFUSED:<id>|restoring_unacknowledged` (a stray session in
    a restoring pane is never an ack);
  - record exists in `freezing` / `frozen` → refuse, print
    `UPSERT_REFUSED:<id>|<state>` (a hook firing in a stand-in pane is a bug).
  Two callers: the SessionStart hook (child 3, normal path) and the freeze
  engine (child 4, fallback when the hook never fired). Both read
  `@aitask_record` off the pane first and pass `--id` when present, so a pane
  that was already recorded is never duplicated even after a `pane_id`
  recycle. A restore into a **new** pane (window gone) carries the record id
  in the environment, never on the pane, so it selects the old record instead
  of creating a second one.
- **Operation lease.** `freeze-begin`, `restore-begin` and `lease-take` mint
  `op_nonce` (8 hex), record `op_owner_pid` (the coordinator) and
  `op_started_at`, and print the nonce. **Every verb that mutates a record
  holding a lease** (`freeze-commit`, `freeze-abort`, `restore-launched`,
  `restore-confirm`, `restore-abort`, `standin-respawned`, the ack form of
  `upsert`) requires `--nonce <n>`; a mismatch prints `NONCE_MISMATCH:<id>`
  exit 6 and writes nothing — a coordinator that lost the race to
  `reconcile` fails closed instead of double-acting. `lease-take <id>` →
  `LEASED:<id>|<nonce>` is how `reconcile` (or a stand-in relaunch on a
  `frozen` record) acquires ownership: it is refused (`LEASE_HELD:<id>`)
  while a lease exists whose `op_started_at` is younger than
  `stale_op_grace` (default 60 s) **or** whose `op_owner_pid` is alive; a
  stale lease with a dead/unverifiable owner is taken over. Within the grace,
  or with a live owner, reconcile leaves the record alone. Lease-clearing
  transitions (`freeze-commit`, `freeze-abort`, `restore-confirm`, hook ack,
  `standin-respawned` out of `aborting`) clear the lease.
- **State machine** (every transition is one locked verb; illegal transitions
  print `TRANSITION_REFUSED:<id>|<from>|<verb>` exit 5 and write nothing):
  ```
  live ──freeze-begin──▶ freezing ──freeze-commit──▶ frozen ◀────────────────┐
   ▲                        │                          │                      │
   └────freeze-abort────────┘                          │ restore-begin        │ standin-respawned
   ▲                                                   ▼                      │ (same nonce)
   └──upsert (hook ack) / restore-confirm── restoring ──restore-abort──▶ aborting
  drop: any state → record removed + capture files removed
  ```
  `aborting` is **nonce-owned**: the record stays leased by the aborting
  attempt until its stand-in is back (`standin-respawned --nonce` → `frozen`,
  lease cleared). `restore-begin` on `aborting` → `TRANSITION_REFUSED`, so a
  user or a second controller cannot start another restore in the gap and
  an old coordinator cannot respawn over a newer attempt: its `standin-respawned`
  carries a stale nonce and is refused.
  **Captures are deleted only on a verified ack** (`ack=hook`). A
  liveness-only `restore-confirm` transitions to `live` but **keeps** the
  capture files (`ack=liveness`); they are removed on `drop` or liveness
  purge. This is what stops a malformed resume that starts a fresh session
  from destroying the only copy.
- Wrapper verbs (sole writer; `list`/`show` take no lock; exit 0/2/3
  `LOCK_BUSY`/4 `ERROR`/5 `TRANSITION_REFUSED`/6 `NONCE_MISMATCH`/7
  `RESTORE_SESSION_MISMATCH`/8 `LEASE_HELD`):
  `upsert --root <r> --window <w> --pane <id> --pane-pid <pid> [--id <rid>] [--session-id <sid>] [--transcript <p>] [--agent-string <s>] [--operation <op>] [--task-id <t>] [--restore-of <rid> --nonce <n>]`;
  `freeze-begin <id> --capture-ansi <p> --capture-txt <p> --lines <n> [--phase <t>]` → `FREEZING:<id>|<nonce>`;
  `freeze-commit <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0>` → `FROZEN:<id>` (writes the stand-in's location: `pane_id`/`standin_pid` from the arguments; `--pane "" --pane-pid 0` is the gone-pane commit used by reconcile; `--pane` without `--pane-pid` or vice versa → usage error exit 2);
  `freeze-abort <id> --nonce <n>` → `LIVE:<id>` (captures deleted);
  `restore-begin <id> --mode resume|repick` → `RESTORING:<id>|<nonce>` (captures **retained**, `restore_attempts`+1, `launch_pid=0`, `last_error=""`);
  `restore-launched <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LAUNCHED:<id>` (records the replacement's `launch_pid` + location; written by the coordinator right after `respawn-pane`/`launch_in_tmux` returns — the nonce-bound evidence that the respawn happened);
  `restore-confirm <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LIVE:<id>|liveness` (captures **kept**; refused with `TRANSITION_REFUSED` unless `launch_pid != 0` and equals `--pane-pid`);
  `standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>` → `STANDIN:<id>` (records the stand-in's `standin_pid` + location; from `aborting` it also transitions to `frozen` and clears the lease; from `frozen` (a `lease-take`n relaunch of a dead stand-in) it just updates and clears the lease; `freeze-commit` folds the same write in);
  `restore-abort <id> --nonce <n>` → `ABORTING:<id>` (captures retained; lease kept by the same nonce);
  `lease-take <id>` → `LEASED:<id>|<nonce>` / `LEASE_HELD:<id>` exit 8;
  `drop <id>` → `DROPPED:<id>`;
  `list [--state <s>] [--root <r>]` → `SESSION:<id>|<state>|<root>|<window>|<pane_id>|<task_id>|<agent_string>|<state_at>`;
  `show <id>` → `KEY:value` lines;
  `purge --observed <file>` → `DROPPED:<id>|<reason>` + `PURGED:<n>`.
  **Observation protocol (superset of the marks one, backward-compatible):**
  ```
  ROOT<TAB><root>                                   -- successfully enumerated root
  WINDOW<TAB><root><TAB><window>                    -- observed agent window
  PANE<TAB><root><TAB><window><TAB><pane_id><TAB><pane_pid><TAB><pane_dead>   -- every pane of that window
  INCOMPLETE                                        -- suppress every sweep
  ```
  `monitor_shared._write_observation_file()` gains a `panes=` argument and
  writes the `PANE` rows from `TmuxMonitor.last_discovered_panes()` (the
  `_LIST_PANES_FORMAT` already carries `pane_id` and `pane_pid`; `pane_dead`
  is appended to the format — see §B arity rule). The marks reader
  (`agent_marks._read_observed`) is extended to **skip** `PANE` rows so one
  file serves both purges; `agent_sessions` requires them. A file with
  `ROOT`/`WINDOW` but no `PANE` rows for an enumerated root is treated as
  pane-incomplete for that root: `dead_window` still applies, `dead_pane`
  does not (fail closed).
- **Purge policy** (fail-closed on `INCOMPLETE`, mirrors `sweep_liveness`):
  a `live` record whose `(root, window)` is absent from a successfully
  enumerated root → `DROPPED:…|dead_window`; a `live` record whose window has
  a `WINDOW` row **and** `PANE` rows, but whose `pane_id` appears in none of
  them (or appears with `pane_dead=1`) and whose `pane_pid` is dead
  (`os.kill(pid, 0)` → `ESRCH`; an `EPERM`/unverifiable pid is treated as
  alive) → `DROPPED:…|dead_pane` — this is what retires the stale candidates
  left behind by an ambiguous relocation. Two producers feed `purge`: the
  monitor maintenance tick (observation file above) and `aitask_frozen.sh
  reconcile`, which builds the same file from its own `list-panes` pass so
  retirement does not depend on a TUI being open. `freezing` / `frozen` / `restoring` /
  `aborting` records are never purged by liveness — they are reconciled by
  `aitask_frozen.sh reconcile` (§C/§D). A frozen record whose capture file is
  missing → `DROPPED:…|capture_missing`.
- `SessionsView` (mtime+size+inode gated) for the TUIs; `invalidate()` after
  every write. `standin_command(record_id) -> str` returns
  `ait frozenagent --record <id>` unless `AITASKS_FROZEN_STANDIN_CMD` is set
  (documented **test seam**; production never sets it).

#### B. Pane options (tmux user options, pane-scoped)

| Option | Set by | Cleared by | Read by | Meaning |
|---|---|---|---|---|
| `@aitask_record=<id>` | `upsert` (hook or freeze engine) | `drop`; pane death | freeze engine, restore coordinator, hook (`--id`) | the pane-visible join to its store record |
| `@aitask_frozen=<id>` | freeze engine, immediately before `respawn-pane` | `restore-confirm` path (coordinator), `drop` | `_LIST_PANES_FORMAT` (appended), `kill_agent_pane_smart` format, `aitask_companion_cleanup.sh`, `maybe_spawn_minimonitor` occupancy | this pane is a frozen stand-in — **authoritative** classifier |
| `@aitask_standin_ready=<id>` | **the viewer itself**, after mount (only the app stamps its own pane — `mark_monitor_pane` rule) | freeze engine + restore coordinator (`set-option -pu`) immediately **before** every `respawn-pane`; `drop` | `reconcile` | positive proof that the stand-in is up — the only signal that distinguishes "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session=<sid>` | SessionStart hook on `$TMUX_PANE` | pane death | freeze engine fallback when the store has no session id | codeagent session id |

**Pane user options survive `respawn-pane`** (they are pane-scoped, not
process-scoped), which is why `@aitask_standin_ready` must be explicitly unset
before each respawn and why `@aitask_record` stays valid across freeze/restore
on the same pane. `#{pane_current_command}` is a process basename and is
**never** used as identity; `#{pane_pid}` (stored as `pane_pid`) and the
options above are the only server-observable identities reconcile reads.

Constants live in `monitor/monitor_core.py` beside `SHADOW_TARGET_OPTION`
(`RECORD_OPTION`, `FROZEN_OPTION`, `STANDIN_READY_OPTION`,
`AGENT_SESSION_OPTION`) and are mirrored in `lib/agent_sessions.sh` for shell
callers.

#### C. Freeze — `lib/agent_freeze.py` + `aitask_frozen.sh freeze <pane>|--all`

Runs **out of the agent pane** (from a TUI, a shell, or `run-shell -b`).
Every step is persisted before the next irreversible one:

1. Resolve the record: `@aitask_record` → `show`; else `upsert` (fallback).
   Read `codeagent_session_id`; if empty, try `@aitask_agent_session`.
2. `capture-pane -p -e -J -t <pane> -S -<cap>` via `TmuxClient.run` →
   `capture.ansi`; strip via `monitor/ansi_utils` → `capture.txt`.
3. `freeze-begin` → state `freezing`, capture paths persisted, **lease
   minted** (`op_nonce`, `op_owner_pid`=this coordinator).
4. `set-option -p -t <pane> @aitask_frozen <id>`; `set-option -pu -t <pane>
   @aitask_standin_ready` (clear any stale ready mark from a previous cycle).
5. `respawn-pane -k -t <pane> '<standin_command(id)>'` via the gateway.
   Window name unchanged, so `classify_pane` / `task_id_from_window_name`
   keep working. The viewer stamps `@aitask_standin_ready=<id>` on mount.
6. `freeze-commit --nonce <n> --pane <pane> --pane-pid <stand-in pid>` →
   state `frozen`, `standin_pid` + location recorded (read via
   `display-message -p -t <pane> '#{pane_id}\t#{pane_pid}'` after the
   respawn), lease cleared.

Failure at 1–3 → nothing to undo beyond temp files (`FREEZE_FAILED:<stage>`).
Failure at 4 → `freeze-abort --nonce`. Failure at 5 (tmux refused) → unstamp +
`freeze-abort --nonce`; the agent is still running. Failure at 6 (store busy)
→ the record stays `freezing`; **reconcile** completes it once the lease is
stale. A `NONCE_MISMATCH` at 6 means reconcile already resolved the record;
the coordinator reports it and exits without touching the pane.

**`aitask_frozen.sh reconcile`** (idempotent; run by the coordinator after
every freeze/restore, by the monitor maintenance tick beside
`_maybe_purge_marks`, and manually) resolves every non-`live` record **whose
lease is stale** (`op_started_at` + `stale_op_grace` elapsed **and**
`op_owner_pid` dead/unverifiable — otherwise the record is skipped as
in-flight) from server-observable facts only
(`list-panes -F '#{pane_id}\t#{pane_pid}\t#{pane_dead}\t#{@aitask_frozen}\t#{@aitask_standin_ready}\t#{@aitask_record}'`;
"agent alive" = `pane_pid == record.pane_pid`; "viewer here" =
`pane_pid == record.standin_pid`; "replacement here" =
`pane_pid == record.launch_pid`; "stand-in up" = `@aitask_standin_ready == id`;
"mismatch" = `last_error` begins with the current `op_nonce`):

| record state | pane observation | action |
|---|---|---|
| `freezing` | `@aitask_frozen==id` **and** stand-in up | `freeze-commit --pane <pane> --pane-pid <observed pid>` |
| `freezing` | agent alive, stand-in not up | unstamp both options, `freeze-abort` (captures deleted) |
| `freezing` | `@aitask_frozen==id`, stand-in not up, neither agent nor viewer pid, pane not dead | **indeterminate — no transition** (viewer may still be booting); re-checked next pass |
| `freezing` | `@aitask_frozen==id`, pane dead | respawn the stand-in (clear ready first), `standin-respawned`, then re-check |
| `freezing` | pane gone | `freeze-commit --pane "" --pane-pid 0` |
| `frozen` | pane gone | keep (restorable into a new window) |
| `frozen` | `@aitask_frozen==id`, pane dead | `lease-take`, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | mismatch recorded for this nonce | `restore-abort` (→ `aborting`), kill the wrong agent via `respawn-pane -k` back to the stand-in, `standin-respawned --nonce` (→ `frozen`) — **never** liveness-confirm |
| `restoring` | viewer here (`pane_pid==standin_pid`) — the coordinator died before or during the respawn, whether or not the ready mark survived | `restore-abort`; respawn the stand-in so it re-stamps ready; `standin-respawned --nonce` |
| `restoring` | `launch_pid==0` and pane pid is neither the viewer's nor the agent's | **indeterminate — no transition** (respawn may be mid-flight); after `stale_op_grace` ×2 → `restore-abort` + respawn stand-in + `standin-respawned --nonce` |
| `restoring` | replacement here (`pane_pid==launch_pid`), pane not dead, no mismatch, `state_at` + `restore_ack_grace` (default 20 s) elapsed | `restore-confirm --pane --pane-pid` (`ack=liveness`, captures kept) |
| `restoring` | pane dead | `restore-abort`, clear ready, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | pane gone | `restore-abort` with `pane_id=""`, then `standin-respawned --nonce --pane "" --pane-pid 0` (→ `frozen`, restorable into a new window) |
| `aborting` (stale lease taken over) | stand-in up (`@aitask_standin_ready==id`) | `standin-respawned --nonce` (→ `frozen`) |
| `aborting` (stale lease taken over) | anything else | clear ready, respawn the stand-in, `standin-respawned --nonce` (→ `frozen`) |

Every reconcile action on a leased record is preceded by `lease-take`; a
`LEASE_HELD` answer means a live coordinator owns it and reconcile skips.

A liveness confirm therefore requires **positive evidence** that the
process in the pane is the one the coordinator launched (`launch_pid`), and
a viewer whose ready mark was cleared is still recognised by `standin_pid`.

Failure injection: `AITASKS_FREEZE_FAIL_AT=capture|begin|stamp|respawn|commit`,
`AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`, and `AITASKS_FROZEN_PAUSE_AT=<stage>`
(the coordinator `SIGSTOP`s itself so a test can run a concurrent
`reconcile` and then `SIGCONT`) — documented test seams, honoured only under
`AITASKS_TEST_MODE=1`.

**Cleanup contract** (`aitask_companion_cleanup.sh` + `count_other_real_agents`
must agree — pinned by the parity test):
- a `@aitask_frozen`-stamped pane **counts as a real agent sibling** (the
  window exists to hold it; killing agent B must not destroy frozen A's viewer);
- when the *dying* pane is the stamped one, the cleanup script **abstains
  entirely** (it is being respawned, not departing);
- `kill_agent_pane_smart` on a frozen pane = `drop` + kill by the same rule.

#### D. Restore — `lib/agent_restore.py` + `aitask_frozen.sh restore <id> [--repick] | --all`

**Never runs inside the pane it replaces.** The viewer's `R`/`p` keys and the
minimonitor keys invoke `run-shell -b "<repo>/.aitask-scripts/aitask_frozen.sh restore <id>"`
through the gateway; the coordinator is a detached process that outlives the
respawn. Two-phase, acknowledged:

1. Build the argv: `aitask_codeagent.sh --agent-string <s> --resume-session <sid> --dry-run invoke raw`
   (resume) or the existing pick launch argv (`--repick`, task id required).
   Empty session id and no `--repick` → `RESTORE_FAILED:no_session` (nothing changes).
2. `restore-begin --mode <m>` → state `restoring`, lease minted (nonce `n`);
   captures and `@aitask_frozen` retained.
3. Prefix the argv with the **restore identity environment** (the
   `explore-relay` `env` precedent — `env` execs into the agent, so the pane
   pid is still the agent's):
   `env AITASK_RESTORE_RECORD=<id> AITASK_RESTORE_NONCE=<n> AITASK_RESTORE_MODE=<m> AITASK_RESTORE_EXPECT_SESSION=<sid> <argv>`.
   Then `set-option -pu @aitask_standin_ready` and
   `respawn-pane -k -t <stand-in> '<env argv>'` — or, when `pane_id=""`,
   `launch_in_tmux` into a new window with the recorded name. Immediately
   after tmux returns, read the new `#{pane_pid}` and write
   `restore-launched --nonce --pane --pane-pid` — the nonce-bound evidence
   that a replacement was actually started. The replacement agent's
   SessionStart hook forwards the four variables as `upsert --restore-of
   --nonce --session-id` (§A ack rules), which is what selects the **old**
   record from a brand-new pane, verifies the resumed session id, and stamps
   `@aitask_record` there.
4. Wait for the ack: poll `show <id>` until `state=live`, `last_error`
   carries this nonce, **or** `restore_ack_grace` elapses.
   - `live` with `ack=hook` → clear `@aitask_frozen`, print `RESTORED:<id>|hook`
     (captures already deleted by the ack).
   - `last_error="<nonce>:session_mismatch"` (the hook reported a different
     session in `resume` mode; persisted by the store because the hook has
     no channel to this process) → `restore-abort --nonce` (→ `aborting`,
     still owned by this nonce), `set-option -pu @aitask_standin_ready`,
     `respawn-pane -k` back to the stand-in, then `standin-respawned --nonce
     --pane --pane-pid` (→ `frozen`), print `RESTORE_FAILED:<id>|session_mismatch`;
     **capture intact**. The same abort → respawn → `standin-respawned --nonce`
     sequence is used by every failure branch below; a `NONCE_MISMATCH` at
     any step means reconcile already finished the abort.
   - grace elapsed, pane alive, `pane_pid == launch_pid`, no hook ack and no
     error → `restore-confirm --nonce --pane --pane-pid` → `live` with
     `ack=liveness`, **captures kept**, clear the stamp, print
     `RESTORED:<id>|liveness` (the viewer/minimonitor show "restored,
     unverified — capture kept").
   - pane dead at any poll (invalid session, binary missing, immediate exit)
     → `restore-abort --nonce`, clear ready, respawn the stand-in,
     `standin-respawned --nonce`, print `RESTORE_FAILED:<id>|agent_exited` —
     **the capture is intact and the viewer is back**.
   - `NONCE_MISMATCH` on any verb → reconcile already settled it; exit
     without touching the pane.
5. Coordinator crash between 2 and 4 → `reconcile` (§C table) settles it
   once the lease is stale.

`aitask_codeagent.sh` gains a global `--resume-session <sid>` (template
`OPT_HEADLESS`): `claude --model <id> --resume <sid>`, `codex resume <sid>`
(model flag per codex CLI), opencode → `RESUME_UNSUPPORTED:opencode` exit 2.
Resolution stays single-sourced in `lib/agent_string.sh`. Restore-All iterates
`frozen` records; per-record failures are reported, never abort the batch.
