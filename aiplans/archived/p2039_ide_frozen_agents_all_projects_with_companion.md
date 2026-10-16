---
Task: t2039_ide_frozen_agents_all_projects_with_companion.md
Base branch: main
Output branch: main
---

# t2039 — `ait ide`: frozen agents of every project, each with its companion

## Context

Two user-visible defects, both observed live on 2026-10-16 (tmux 3.8, `-L ait`):

1. Frozen-agent viewers brought back by `ait ide` (V, or R/P) come back with **no
   minimonitor**. Root cause (re-measured in planning on a scratch socket): an
   untargeted `tmux list-panes` run with `TMUX_PANE` pointing into a background
   window lists the session's **active** window, so the single-instance guard in
   `aitask_minimonitor.sh` sees the `monitor` window's live marker and every
   companion spawned into a non-active window exits at once. `list-panes -t
   "$TMUX_PANE"` lists the pane's own window.
2. `ait ide` only offers the frozen agents of the project it runs in; the store
   (`~/.config/aitasks/agent_sessions.json`) is global and today holds records for
   `aitasks`, `thinking_backend` and `thinking_app`.

Decisions taken with the user during planning:
- **Per-project prompts**: one V/R/P/S question per actionable project group.
- **Act only on** the current project, or projects that are in the `ait projects`
  registry (which `ait ide` fills automatically) **and** whose directory still holds
  the aitasks marker. Everything else is listed with a reason and never bootstrapped.
- **Companion top-up**: every `ait ide` start silently gives each *tracked* frozen
  viewer on the server (all projects) its minimonitor; idempotent; skipped with
  `--no-frozen-check`.

Working on the current branch (profile `fast`).

### Pre-phase (risk mitigations)

1. [baseline_offer_suites] Before editing anything, run the suites the rewrite
   touches and record their pass/fail as the baseline: `bash
   tests/test_ide_frozen_offer.sh`, `bash tests/test_claude_hook_status.sh`, `bash
   tests/test_frozen_reopen_live.sh`, `bash
   tests/test_minimonitor_single_instance_guard.sh`, `python3
   tests/test_agent_reopen.py`, `python3 tests/test_agent_restore.py`, `python3
   tests/test_minimonitor_instance_guard.py`. Any pre-existing failure is noted
   (and not attributed to this task) before step 1.

## Part A — the companion guard reads its own window

1. **`.aitask-scripts/aitask_minimonitor.sh`** — the guard's read becomes
   `ait_tmux list-panes -t "$TMUX_PANE" -F "#{pane_id}|#{@aitask_monitor_kind}"`
   (a pane target lists that pane's window). Build the target as an array:
   `target=(); [[ -n "${TMUX_PANE:-}" ]] && target=(-t "$TMUX_PANE")`. **`$TMUX_PANE`
   unset** (TMUX set but no pane identity — not a state tmux produces for a pane
   process): keep the untargeted read, i.e. today's behaviour, because the guard's
   default arm is blocking and there is no own window to name. Rewrite the guard
   comment: why untargeted is wrong (session's current window, measured t2039), the
   unset fallback, and that the foreign-server pane-id collision is pre-existing and
   unchanged.
2. **`.aitask-scripts/codebrowser/codebrowser_app.py::_detect_tmux_window`** — the
   same defect class (sweep result: the only other own-window read without `-t`).
   Add `-t $TMUX_PANE` when set: `["tmux", "display-message", "-p", *(["-t", pane]
   if pane else []), "#{window_index}"]`. The session-scoped `#S` reads found by the
   sweep are not window-dependent and stay.
3. **`tests/test_minimonitor_single_instance_guard.sh`** — add a two-window fixture
   (`setup_two_windows`: window `bg` holds SELF + a sibling, window `fg` holds one
   pane and is selected; `TMUX_PANE=SELF`). New cases; (vi) and (vii) must fail on
   the pre-fix guard (red proof in Verification):
   - (vi) live marker only in the **active** `fg` window → proceeds, `launched=yes`.
   - (vii) live marker on the `bg` sibling while `fg` is clean → blocks (own window
     still guarded when it is not active).
   - (viii) `TMUX_PANE` unset, live marker in `fg` → blocks (pins the fallback).
   Existing (i)–(v) stay (single window = active window). Update the header list.
4. **Codebrowser test** — new `tests/test_codebrowser_detect_tmux_window.py`:
   patch `subprocess.run`, assert the argv carries `-t <TMUX_PANE>` when set and no
   `-t` when unset.

## Part B — restored agents and tracked viewers always get a companion

5. **`.aitask-scripts/lib/agent_launch_utils.py::maybe_spawn_minimonitor`** — close
   the booting-companion race (reopen spawns a companion, then R/P's same-pane
   restore asks again before that minimonitor has mounted and stamped its marker).
   - Define `_COMPANION_ARGV = ("ait", "minimonitor")` once; the split uses it and
     the check compares `#{pane_start_command}` to `" ".join(_COMPANION_ARGV)`
     (tmux renders argv `ait minimonitor` verbatim — measured).
   - Append `#{pane_dead}|#{pane_start_command}` to the `list-panes` format, start
     command **last** so a `|` inside it stays in the remainder of the partition.
   - Order per pane: frozen stand-in → counted (unchanged); marker → live blocks /
     stale self-heals (unchanged); **no marker, not dead, start command is the
     companion command → return None** ("a companion is already booting"), not
     counted; otherwise counted unless a shadow (unchanged).
   - **Serialize the eligibility check and the split** (review finding: two callers
     — two `ait ide` top-ups, or a top-up racing R/P's same-pane restore — can both
     observe "no companion" before either splits, and both shell guards can finish
     before either app mounts, leaving two live companions). New context manager
     `_companion_spawn_lock(session, win_index, timeout=2.0)`:
     - reads `#{socket_path}` of the window target (one `display-message`); the
       lock file is `<socket_path>.aitask-companion.lock` — beside the server's own
       socket, in tmux's per-user 0700 directory, one file per server, never
       deleted (no unlink race), and a test server's lock lives in its fixture dir;
     - `fcntl.flock(LOCK_EX | LOCK_NB)` retried every 50 ms until the deadline
       (`fcntl` imported inside the function); the kernel drops the lock if the
       holder dies, so there is no stale-lock recovery to get wrong;
     - **fails closed**: an unreadable / non-absolute socket path, a lock file that
       cannot be opened, or the deadline passing → no spawn (`None`); the next
       top-up retries. 2 s bounds a TUI caller's wait; the critical section is a
       handful of tmux round-trips.
     - One lock per **server** rather than per window: strictly coarser than
       per-window serialization, needs no window id before the lock, and keeps the
       file count bounded. `maybe_spawn_minimonitor` is the only companion split
       site in the tree (sweep), so this one lock covers every caller (board,
       codebrowser, trails, syncer, TUI switcher, restore, reopen, top-up).
   - The pane-list eligibility read (marker, booting companion, frozen stand-in,
     overcrowding, `agent_pane` membership) moves **inside** the lock and happens
     there exactly once, followed by the active-pane probe and the split; the lock
     is released before the cleanup hook and refocus. A caller that acquires second
     therefore re-reads after the first caller's split and sees its pane through the
     booting-companion rule (the marker does not exist yet) — which is why the two
     changes ship together.
   - The shell guard stays marker-only: if it also treated a booting sibling as
     blocking, two concurrent companions would both exit.
6. **`.aitask-scripts/lib/agent_restore.py`**
   - `_spawn_companion` returns the companion pane (`str | None`, `None` on any
     failure); callers that ignore it are unaffected.
   - `restore()` becomes a thin wrapper over the current body (renamed
     `_restore_attempt`), which records on a small `_Attempt` object the pane the
     same-pane branch reused (set only when `respawn_if_stamped` fired) and the
     record root. After an **ok** result with a reused pane, call
     `_companion_for_pane(pane, root)`: `frozen_ops.window_facts(pane)` → skip on
     `None`/`{}`; else `_spawn_companion(facts["session"], facts["window"], pane,
     root)`. The new-window branch is untouched (it already spawned one). A failed
     restore spawns nothing (the rollback put the stand-in back; its viewer keeps
     whatever companion it had).
   - Rewrite the `_launch_into_new_window` docstring sentence ("the companion its
     surviving window already has is never doubled") to the new rule: the
     same-pane branch tops up after success, and `maybe_spawn_minimonitor` refuses a
     live or booting companion, so nothing doubles.
7. **`.aitask-scripts/lib/agent_reopen.py`** — new verb `companions --root <p> |
   --all-roots`:
   - Factor `_classified(root | None)` out of `classify()` (returns every `(rec,
     kind, claim)` including `tracked`); `classify()` keeps filtering `tracked` out,
     so `gone --root` output is byte-identical. `_frozen_records(root | None)`
     omits `--root` from the store `list` for `None`.
   - `companions(root | None)`: for each `tracked` record whose claim is not dead,
     `window_facts(claim.pane_id)` → `agent_restore._spawn_companion(session,
     window, pane, rec root)`; emit `COMPANION_SPAWNED:<id>|<session>:<window>|<pane>`
     per spawn, `COMPANION_ERROR:*|store unreadable` / `COMPANION_ERROR:*|tmux
     unreachable` (exit 1), and a trailing `COMPANION_COUNT:<n>`. Never creates or
     moves a window.
   - Grammar: exactly one of `--root` / `--all-roots`; `--session` refused (2).
8. **`.aitask-scripts/aitask_frozen.sh`** — route `companions` to `REOPEN_PY`
   (`gone|reopen|companions`), add it to `usage` and the verb list in the header.

## Part C — one `ait ide` run offers every project's frozen agents

9. **`agent_reopen.py`: `gone --all-roots`** (read-only, `gone --root` unchanged):
   - Classify all frozen records (`_classified(None)`), keep non-tracked.
   - Per distinct root compute `(state, name)` once:
     - `missing` — `<root>/aitasks/metadata/project_config.yaml` is not a file
       (the registry's own OK/STALE rule, `agent_launch_utils._read_registry_index`);
     - else read the registry with `agent_launch_utils._parse_registry_records_strict()`
       (`OSError`/`ValueError` → `unverified`); `ok` when a record's
       `realpath(path) == root`, else `unregistered`.
     - `name` = registry name, else `basename(root)`.
   - Output, roots sorted by `(name, root)`:
     `GONE_ROOT:<state>|<name>|<root>`, then that root's
     `GONE:<id>|<kind>|<window>|<task>|<at>|<resume>|<repick>|<root>` (root is the
     **last** field, verbatim, so `read` keeps any `|` in it), then
     `GONE_ERROR:<id>|tmux_unreachable|<root>`; trailing `GONE_COUNT:<n>`. A root
     containing a newline cannot be one wire line: its records become
     `GONE_ERROR:<id>|root_unprintable` and no `GONE_ROOT` is printed.
   - Grammar: `--root` and `--all-roots` are mutually exclusive; `--session` with
     `gone` stays a usage error.
10. **`.aitask-scripts/lib/ide_frozen_offer.sh`** — rewrite
    `ide_offer_frozen_agents <root> <session> <frozen_sh>` (same signature, same
    never-fails / never-blocks contract, same `AIT_IDE_FROZEN_ASSUME_TTY` seam):
    - `cur="$(cd "$root" 2>/dev/null && pwd -P)" || cur="$root"`.
    - List with `gone --all-roots`; parse `GONE_ROOT` into `rstate[root]` /
      `rname[root]`, `GONE` into parallel arrays plus `roots[i]`, `GONE_ERROR` into
      a warning (as today). Group order: `cur` first, then the Python order.
      Actionable group ⇔ `root == cur` or `rstate == ok`.
    - Nothing listed → top-up (below) → return 0.
    - **Non-interactive**: one stderr line — `Note: N frozen agent(s) of this project
      have no open viewer (M more in K other project(s)) — run 'ait frozenagent' to
      see them.` (the parenthesis only when M>0; with N=0 the line names only the
      other projects), the hook note as today, then the top-up, return.
    - **Interactive**: print every group — header `<name> (this project) — N` /
      `<name> — N · lands in its own tmux session`; rows exactly as today's table;
      list-only groups add their reason and are never prompted:
      `missing` → "project directory gone — not touched; drop them with 'ait
      frozenagent'"; `unregistered` → "not a registered project — not touched; run
      'ait ide' there, or 'ait projects add <path>'"; `unverified` → "project
      registry unreadable — not touched". Hook note once (current root). Then one
      prompt per actionable group, all asked before anything runs:
      `<name>: [V] viewers for all N (default) / [R] restore k / [P] re-pick j / [S]
      skip — Choice [V/r/p/s]: ` (EOF/empty = V, as today).
    - **Execute**, in order:
      a. every V/R/P group: `_ide_frozen_reopen <root> <session-or-empty>
         <frozen_sh>` — `--session <session>` only for `cur`; other roots pass no
         `--session` so `_resolve_target_session(root, None)` picks that project's
         session or bootstraps it (t1784 ownership rule). Each root is a separate
         invocation, so one project's refused bootstrap (`session_name_taken`,
         `session_not_for_root`, `default_session_unreadable`) is printed under that
         project and never stops the next. Output is headed by `<name>:` and ends
         with today's `Viewers: X reopened, Y failed.`
      b. if any R/P group: re-classify **once** with `gone --all-roots` →
         `still[id]` across every root (failure → "could not re-check the frozen
         agents; nothing restored" for every R/P group).
      c. every R/P group: today's per-record loop (eligibility, `stranded` /
         `survivor` / `error` skips with today's messages), `restore <id>
         [--repick]` plus `--session <session>` only for `cur`; per-group summary
         `Restored a, viewers b, failed c, skipped d.` (unchanged string).
      d. if another project acted, one line naming where its agents are, from the
         `REOPENED:` lines' `<session>:<window>` field: `Other projects' agents are
         in their own tmux sessions: thinking_backend (thinking_back), … — switch
         with j from any TUI, or run 'ait ide' in that project.`; skipped groups
         get one `… stay listed in 'ait frozenagent'.` line.
    - **Top-up** (`_ide_frozen_companions <frozen_sh>`), every path that reached the
      listing: `companions --all-roots`; print `Companions: N viewer window(s) got
      their minimonitor back.` only when N>0; a non-zero exit warns with the last
      line it printed (same shape as `_ide_frozen_reopen`'s crash warning).
    - Rewrite the file header (verbs, grouping, per-project prompts, eligibility,
      top-up) — keep the R/P "reopen first, then re-classify" rationale.
11. **`.aitask-scripts/aitask_ide.sh`** — rewrite the `--help` "Frozen agents:"
    paragraph (every project's records, grouped; one question per project; other
    projects land in their own session; list-only projects; companion top-up;
    `--no-frozen-check` skips all of it) and the `offer_frozen_agents` comment. The
    three call sites are unchanged.

## Docs

12. `website/content/docs/workflows/freeze-and-restore-agents.md` (lines ~89–124):
    describe the grouped, per-project offer, where each project's agents land, the
    list-only rule (registered + present), the companion top-up, and the
    `gone --all-roots` / `companions --all-roots` commands next to the existing
    `gone --root` example. Remove "Only this project's records are offered…".
    `website/content/docs/installation/terminal-setup.md:51` — the "Frozen agents
    after a restart" paragraph says the same thing briefly. Current-state prose only
    (`aidocs/framework/documentation_conventions.md`). Then `cd website && python3
    check_links.py --build`.

## Tests

13. `tests/test_ide_frozen_offer.sh` — stub `gone` answers in the all-roots shape
    (`GONE_ROOT` + 8-field `GONE`), stub logs every argv, `reopen` can be made to
    fail for one root, `companions` answers from a canned file. Re-express every
    existing case in the new shape (empty, non-tty, V, option-like session, R,
    still-gone, unreachable re-check, P, S, failing listing, crashing reopen,
    explained failure, `--help`, three call sites). New cases:
    - two actionable projects + answers `V`/`R` → `reopen --root /proj --session S`,
      `reopen --root /other` (no `--session`), `restore <other-id>` with no
      `--session`, `restore <cur-id> --session S` never issued for V;
    - group order (current first) and headers;
    - `missing` / `unregistered` / `unverified` groups are listed with their reason,
      never prompted (answer count = actionable groups), never reopened/restored;
    - one root's reopen fails (`REOPEN_FAILED:…|no_session_for_root:…`) → reported
      under that project, the other root still reopened and restored;
    - current project has none, another has some → still offered (interactive) /
      hinted (non-tty, hint names the other projects);
    - non-tty hint carries the "M more in K other project(s)" count;
    - R re-classification is one `gone --all-roots` after all reopens;
    - top-up: message when `COMPANION_SPAWNED` lines come back, silent at 0, warning
      on a non-zero exit; runs on the "nothing listed" path too.
14. `tests/test_claude_hook_status.sh` (case F) — its stub answers `gone` in the
    all-roots shape with `<root>` = the test project's `pwd -P`, and `companions`
    with `COMPANION_COUNT:0`, so "no gone records → nothing printed" still holds.
15. `tests/test_agent_reopen.py` — `Store.list` honours a missing `--root`
    (all roots). New: `gone --all-roots` line shapes and ordering; root states via
    temp dirs (`project_config.yaml` present/absent) and an `AITASKS_PROJECTS_INDEX`
    fixture (registered, unregistered, unreadable → `unverified`); `gone --root`
    output unchanged; grammar (`--root`+`--all-roots`, `--all-roots`+`--session`,
    `companions` without scope → 2); `companions`: a tracked live viewer → one spawn
    with its session/window/pane and root, a dead or gone or stranded one → none,
    unreachable tmux → `COMPANION_ERROR`, exit 1.
16. `tests/test_agent_restore.py` — `test_a_same_pane_restore_spawns_no_companion`
    becomes `…_tops_up_the_companion`: one spawn, after success, `agent_pane` = the
    reused pane, session/window from `window_facts`. Add: a failed same-pane restore
    spawns nothing; a companion exception does not fail the restore; the
    new-window branch still spawns exactly once (existing test).
17. `tests/test_minimonitor_instance_guard.py` — the fake answers `#{socket_path}`
    with a path inside a per-test temp dir (otherwise the lock file would land in
    the cwd); pane tuples gain `dead`/`start` fields (old 3-field tuples keep
    parsing). Cases:
    - a live booting companion (`ait minimonitor`, no marker) blocks; a dead one
      does not; a pane with another start command is counted as before; the split
      argv still ends `ait minimonitor`;
    - the lock fails closed: socket path unreadable / relative, lock file not
      openable, lock held past the deadline (held by the test from another fd) →
      no `split-window` issued;
    - **deterministic two-caller race**: one shared stateful fake (a split adds a
      live pane whose start command is `ait minimonitor`), two threads calling
      `maybe_spawn_minimonitor` for the same window, and a `threading.Barrier(2)`
      injected by wrapping `_companion_spawn_lock` so **both callers finish every
      read they make before the lock and wait at its door together** — both have
      already decided to spawn on a window with no companion. Exactly one
      `split-window` is issued, and the second caller returns `None`.
    - **negative control** (proves the race test can fail): the same harness with
      `_companion_spawn_lock` replaced by a no-op and the barrier moved into the
      fake's `list-panes` (both eligibility reads complete before either split)
      yields two splits. Without this control the race test could pass vacuously.
    - the lock is released on every path (a raised split error included): a third
      call afterwards acquires at once.
18. **New** `tests/test_ide_frozen_all_projects_live.sh` (a new file, rather than
    `test_frozen_reopen_live.sh`, because it needs the bootstrap isolation recipe of
    `test_restore_session_bootstrap_live.sh`: `AITASKS_PROJECTS_INDEX` fixture,
    `AIT_NO_SYSTEMD_RUN=1`, a stub `ait` on PATH before the server starts — which
    would change the environment of every existing reopen case). Real store
    (fixture `AITASKS_AGENT_SESSIONS_FILE` / `AITASKS_FROZEN_DIR`), records seeded
    via `tests/lib/frozen_fixtures.sh`, `auto_spawn: false`. Projects: P (current,
    session A exists), Q (registered, no session), R (registered, its
    `default_session` is a name already held by a session of another project), M
    (registered, directory deleted), U (present, unregistered). Answers V/V/V for
    P/Q/R. Assert: P's viewer in A; Q's viewer in a **newly created** session named
    by Q's `default_session`; R reports `session_name_taken` and its record stays
    frozen with no pane, while P and Q still succeed; M and U are listed, not
    prompted, no session created for M's configured name, records untouched; the
    output names Q's session in the "Other projects' agents" line. Uses
    `assert_counters_init` if any case runs in a subshell.

## Verification

- Every touched suite, individually: the seven baseline suites, plus
  `bash tests/test_ide_frozen_all_projects_live.sh`,
  `python3 tests/test_codebrowser_detect_tmux_window.py`,
  `bash tests/test_no_raw_tmux.sh`, then
  `bash tests/run_all_python_tests.sh` (read only the last line; `set -o pipefail`
  if piped).
- **Red proof for Part A** (nothing in the repo is modified for it): in the
  scratchpad, a copy of `aitask_minimonitor.sh` with the pre-fix untargeted line,
  beside `lib/` and `monitor/` symlinks into the repo (so its `SCRIPT_DIR` sourcing
  and `MARKER_TOOL` resolve), plus a `sed`-rewritten copy of the guard test with
  `PROJECT_DIR` pinned to the repo and `GUARD` pointed at that copy. (vi) and (vii)
  must fail there and pass against the real file. For step 5 the red proof is in
  the suite itself: the race test's negative control (lock replaced by a no-op)
  must show two splits; additionally, a scratch copy of the module with the
  booting-companion rule removed must fail the two-caller test.
- `shellcheck .aitask-scripts/aitask_minimonitor.sh .aitask-scripts/aitask_frozen.sh
  .aitask-scripts/aitask_ide.sh .aitask-scripts/lib/ide_frozen_offer.sh`.
- `cd website && python3 check_links.py --build`.
- Not done here: running `ait ide` against the user's live `-L ait` server (it would
  change the user's sessions) — offered as a manual follow-up.

## Step 9 (Post-Implementation)

Commit code (`bug: … (t2039)`) and the plan/task via `./ait git` per task-workflow
Step 8/9; archive. Follow-up to propose at Step 8: a separate bug task for
`aitask_shadow_capture.sh:321` — its cross-server guard compares two values that both
come from the gateway server, so it never fires (found by the sweep; a different
defect, not this task's).

## Risk

### Code-health risk: medium
- The guard change sits on every minimonitor start; a wrong target could let a
  duplicate start or block every companion · severity: medium · → mitigation: covered
  by steps 3 and the red proof (both directions, each failing pre-fix)
- `maybe_spawn_minimonitor` is on every launch path; the new in-flight rule could
  suppress a companion that should spawn (e.g. a mis-rendered start command) ·
  severity: low · → mitigation: covered by step 17 + the start-command measurement
- The new per-server flock is a new cross-process primitive on every launch path:
  a TUI caller can wait up to 2 s behind another spawner, and a fail-closed
  acquisition skips a companion · severity: medium · → mitigation: covered by step 17
  (fail-closed and release-on-every-path cases, two-caller race + negative control)
- `ide_frozen_offer.sh` is largely rewritten; the stranded / survivor / unchecked
  skip rules of R/P could regress · severity: low (residual — addressed by inline
  pre-phase baseline_offer_suites, with every existing case re-expressed in step 13)
  · → mitigation: inline pre-phase baseline_offer_suites
- `restore()` is wrapped; a success path could miss the top-up or a failure path
  spawn one · severity: low · → mitigation: covered by step 16

### Goal-achievement risk: medium
- Cross-project reopen for a project with no session relies on the t1784 bootstrap
  being reached through `reopen` (so far proven mainly through `restore`) ·
  severity: medium · → mitigation: covered by step 18 (real bootstrap, refusal
  isolation)
- "Every viewer window has a live minimonitor" is proven by the guard live test and
  unit tests, not by booting a real minimonitor in a reopened window on the user's
  server · severity: medium · → mitigation: t2044

### Planned mitigations
- timing: pre-phase | name: baseline_offer_suites | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: ide_frozen_offer.sh rewrite regressions | desc: run the seven touched suites before editing and record the baseline
- timing: after | name: manual_verify_live_ide | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: companion acceptance only proven indirectly | desc: on the real -L ait server, run ait ide in aitasks; confirm the cross-project groups, Q-style session targeting, and a live minimonitor in every viewer window after V and after R | created: t2044

## Post-Review Changes

### Change Request 1 (2026-10-16 12:40)
- **Requested by user:** three review findings. (1, blocking) `_project_marker` let a
  `PermissionError` from `Path.is_file()` escape on Python 3.11–3.13, aborting the
  whole all-roots listing and so `ait ide`'s offer for every healthy project.
  (2, blocking) the shell parsers read the root with `IFS='|' read`, which drops
  a trailing `|` from the last variable, so `/p|` became `/p` and lost its
  session pin. (3, follow-up) `_frozen_records` spawns one `store show`
  subprocess per record, now twice per `ait ide` start over the global store.
- **Changes made:** (1) `_project_marker` returns None on `OSError`; `root_states`
  maps it to a new non-actionable state `inaccessible` ("project directory
  unreadable — not touched" in the offer); other roots continue. Test injects
  `PermissionError` for one root next to a healthy one; red proof in-process
  (the unguarded lookup errors). (2) new `_ide_frozen_tail <n> <line>` takes the
  root verbatim after the n-th `|` (fails on a short line, which is skipped);
  used for GONE_ROOT and GONE. Tests: a root ending in `|` for another project
  and for the current project (keeps `--session S`), a short GONE line, the
  inaccessible reason; the old `read`-based parser fails exactly the 4
  trailing-pipe assertions. (3) not changed here — recorded as follow-up task
  t2041 (`frozen_listing_single_store_read`, review_finding).
- **Files affected:** `.aitask-scripts/lib/agent_reopen.py`,
  `.aitask-scripts/lib/ide_frozen_offer.sh`, `tests/test_agent_reopen.py`,
  `tests/test_ide_frozen_offer.sh`.

## Final Implementation Notes
- **Actual work done:** All three parts as planned. A — the minimonitor guard
  lists `-t "$TMUX_PANE"` (untargeted fallback kept when unset); codebrowser's
  `_detect_tmux_window` targets `$TMUX_PANE`. B — `maybe_spawn_minimonitor`
  recognises a booting companion by `#{pane_start_command}` and runs its single
  eligibility read + split under a per-server `flock`
  (`_companion_spawn_lock`, `<socket_path>.aitask-companion.lock`, fails
  closed); `restore()` tops up the companion after a successful same-pane
  restore (`_companion_for_pane`); new `companions --root|--all-roots` verb.
  C — `gone --all-roots` (`GONE_ROOT:<state>|<name>|<root>` groups, root as the
  last field; states ok / missing / unregistered / unverified / inaccessible),
  `ide_frozen_offer.sh` rewritten for grouped, per-project V/R/P/S prompts, own
  sessions for other projects, one re-classification for R/P, companion top-up
  on every path. Docs: `ait ide --help`, freeze-and-restore page, terminal-setup
  page, `aidocs/framework/tui_conventions.md` companion section.
- **Deviations from plan:** the lock was added after the plan-review finding (two
  concurrent spawners could both read "no companion"); the helper
  `_companion_check_and_split` returns `(split_ran, pane, agent_pane)` so a split
  with empty `-P` output still refocuses as before. Post-review: the
  `inaccessible` root state and `_ide_frozen_tail` (see Post-Review Changes).
  The new live test is a separate file (`test_ide_frozen_all_projects_live.sh`)
  because it needs the bootstrap isolation recipe.
- **Issues encountered:** a scratch-copy red proof for `agent_reopen` was
  vacuous — an import re-inserts the real `lib/` ahead of the scratch path — and
  was redone in-process by swapping the function. Same-pane success tests in
  `test_agent_restore.py` reached the new `window_facts` read unscripted; fixed by
  scripting arity 7 in `_TMUX_OURS_AND_FIRES`, and `swap_tmux` now also swaps
  `agent_launch_utils._TMUX` for a failing gateway so no unit test can reach a
  real tmux server through the companion spawner.
- **Key decisions:** per-project prompts, registered+present projects only, and an
  all-projects companion top-up (user decisions in planning); one lock per tmux
  server rather than per window (coarser, no window id needed before the lock,
  bounded file count); the shell guard stays marker-only so two booting
  companions cannot both exit.
- **Verification:** offer 97, reopen 67, restore 84, companion-spawn 26, guard
  live 35, hook-status 51, cross-project live 30, reopen live 148, no-raw-tmux 5,
  standin-stamp 28, tui-switcher multi-session 52, restore bootstrap live 55, full
  Python suite PASSED, `check_links.py --build` PASSED. NOT run (they refuse to
  start inside tmux): `tests/test_frozen_agents_acceptance.sh`,
  `tests/test_restore_flows_live.sh`. Red proofs: guard (vi)/(vii) fail on the
  pre-fix guard; the race test fails without the booting rule and its no-lock
  control shows two splits; the PermissionError test errors with the unguarded
  lookup; the old `read` parser fails the four trailing-pipe checks.
- **Follow-ups:** t2041 (single store read for the all-roots listing and
  top-up, review finding); manual_verify_live_ide (planned "after" mitigation,
  created at Step 8d).
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_shadow_capture.sh:321 — the cross-server guard compares #{socket_path} and the -t "$own_pane" read, both taken from the gateway server, so the comparison is always true and the guard never fires (its sibling shadow_self_target compares against ${TMUX%%,*} correctly)`
