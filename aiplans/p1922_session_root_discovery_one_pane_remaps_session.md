---
Task: t1922_session_root_discovery_one_pane_remaps_session.md
Base branch: main
Output branch: main
---

# t1922 — one wandering pane remaps a whole tmux session (simplified design)

## Context

`_collect_live_roots` (`.aitask-scripts/lib/agent_launch_utils.py:1286`) maps each
tmux session to the **first** pane cwd that walks up to an aitasks project
(`_project_root_from_pane_paths`, `:1112`). It reads the explicit registration
only when no pane resolves. One `claude` pane that `cd`'d into `thinking_app`
therefore re-rooted the whole `aitasks` session once the TUI windows listed ahead
of it were closed. Titles, DONE glyphs and marks were lost, and minimonitor `p`
looked up, and could launch, the other repo's task.
`discover_aitasks_sessions_async` (`:1376`) repeats the same loop inline.

The registration itself cannot simply be preferred today. It is a tmux **global**
variable, `AITASKS_PROJECT_<session>`, keyed by session **name**. Nothing ever
unsets it, so it outlives the session it describes. Separately,
`_tmux_bootstrap_set_project_registry` (`lib/tmux_bootstrap.sh:581`) overwrites it
even when a live session of that name belongs to another project.

## Design: the registration lives on the session itself

`ait ide` and the bootstrap stamp the **session-scoped user option**
`@aitask_project_root` on the session they own:
`set-option -t =<S> @aitask_project_root <root>`. The name follows the existing
`@aitask_frozen` / `@aitask_shadow_target` convention, and nothing uses it yet.

**Discovery rule** (one shared function, used by sync, checked and async
discovery):
1. If the session carries `@aitask_project_root` and the value is a valid
   project (marker file present), that root is **authoritative**. Pane
   directories are not consulted, and `list-panes` is skipped for that session.
2. Otherwise, use a pane vote: the root the most panes walk up to, with ties
   broken by the smallest realpath. Pane order never decides.
3. Otherwise, if no pane resolves, fall back to the legacy global
   `AITASKS_PROJECT_<session>` exactly as today. It is read only in this case.

**Discovery stays one round-trip.** The option comes back in the session listing
itself: `list-sessions -F "#{session_name}\t#{@aitask_project_root}"`. I verified
on this server that `#{@option}` expands in `list-sessions -F`. A registered
session therefore needs no extra call, and needs none of the `list-panes` call it
makes today.

### Stale registration and session recreation
- **Lifetime.** A session option dies with its session: on `kill-session`, the
  last window closing, or the server exiting. It cannot outlive the session, so
  a stale value cannot be inherited by a different session of the same name.
- **Recreation.** A new session named S starts with no option. When `ait ide`
  or the bootstrap creates S itself, it claims S at once (`--created`). A
  session recreated by some other route uses the pane vote until it is
  claimed, and a missing stamp is **not** proof that nobody owns it. The claim
  rule below asks discovery's evidence first.
- **Rename.** tmux keeps a session's options across `rename-session`, so
  ownership follows the session object, not the name.
- **Project moved or deleted while the session lives.** The value fails the
  marker check. The session is treated as unregistered (pane vote), and the
  next `ait ide` may re-claim it.
- **Sessions started before this change** have no option. They use the pane
  vote, which already fixes the reported case: 5 panes in aitasks against 1 in
  thinking_app. Running `ait ide` stamps them, but only for the project
  discovery already attributes them to. Another project's `ait ide` is refused
  (claim rule, step 4).
- **Legacy global variable.** Still written, best-effort, because projects on
  older framework versions read it, but new code reads it only in rule 3. Its
  staleness risk is unchanged from today, and smaller, because it can no longer
  override a pane.

### Takeover protection (claim rule)
`_tmux_bootstrap_set_project_registry <root> <session> [--created]` decides
ownership in this order. Each mandatory tmux command is checked explicitly,
because the helper always runs in an `|| die` / `|| return` context, where bash
suppresses errexit inside the function. A local probe confirmed this.

1. **Read the stamp.** Run
   `owner=$(ait_tmux show-options -t "=$S" -qv @aitask_project_root)`. With
   `-q`, an unset option gives rc 0 and empty output. A **non-zero rc is a
   failed read, never "unset"** → refuse with 46,
   `BOOTSTRAP_FAILED:claim_unverified:<S>`.
2. **Stamped with a valid project.** If it equals `<root>` by realpath → go to
   step 5 (refresh the best-effort writes) and return 0. If it names another
   project → refuse with 45, `BOOTSTRAP_FAILED:session_owned:<S>:<owner>`.
3. **Unstamped or invalid, and `--created`** (this invocation's own
   `new-session` just made S) → claim (step 4). The flag is passed **only** by
   `spawn_session_detached` on its "I created it" branch: in ensure mode after
   `has-session` failed and `ait_tmux_new_session_persistent` succeeded, and in
   `--create-only` mode.
4. **Unstamped or invalid, existing session → ownership evidence.** Ask
   discovery itself, not a second bash implementation, which root it would give
   this session today. A Python heredoc (`resolve_python`, as
   `aitask_project_resolve.sh` does) calls the new
   `agent_launch_utils.unregistered_session_attribution(session) -> (root | None, complete)`.
   It applies the same rules 2–3 (pane vote, then the legacy global) through
   the **checked** adapters. Then:
   - incomplete, a non-zero Python exit, or no Python at all → refuse with 46
     (`claim_unverified`);
   - a valid root other than `<root>` → refuse with 45 (`session_owned`, owner
     = that root). This is the upgrade path: A's pre-upgrade session, whose
     panes and legacy global say A, is **not** claimable by B;
   - `<root>` itself, or nothing at all (no pane resolves and no valid legacy
     global) → claim (step 5).

   Because this is the discovery rule, A's own pre-upgrade session with one
   pane wandered into B still attributes to A by majority, and A claims it.
5. **Claim.** Run `ait_tmux set-option -t "=$S" @aitask_project_root "$root"`,
   then re-read the option and compare. A non-zero `set-option` **or** a
   mismatched re-read → refuse with 47,
   `BOOTSTRAP_FAILED:claim_write_failed:<S>`. This is verification by re-read,
   not by the success line. Only after it verifies: write the legacy global and
   run `aitask_projects.sh add`. Both stay best-effort, `|| true`.

Every refusal prints its sentinel and then a human-readable line on stderr. The
human line comes last, because the switcher's generic error path shows the last
line. No refusal touches the session.

Every caller stops on **any** non-zero exit, **before** it modifies or attaches
to the session:
- `spawn_session_detached` returns the code before the syncer step, and documents
  45/46/47.
- `agent_restore._bootstrap_project_session` already treats anything other than
  `BOOTSTRAP_CREATED:` as "not ownership". No change is needed there.
- `aitask_ide.sh` dies before the monitor window, the syncer window, the frozen
  offer and the attach, in all three branches. The message depends on the code:
  - 45: "Session 'S' belongs to project <owner>. Use 'ait ide --session NAME'."
  - 46: "Could not verify who owns tmux session 'S' — not touching it."
  - 47: "Could not register session 'S' to this project."

  On the fresh path, a 46/47 after `new-session` leaves this invocation's own
  session unstamped, with its monitor window. The next `ait ide` attributes it
  to this project through step 4 and claims it.

## Trade-offs (what this gives up, and what it defers)
- **Registration beats panes, even if every pane has left.** That is the point:
  registration means ownership. Pointing a live session at another project
  takes one of: kill the session, use `ait ide --session NAME`, or
  `tmux set-option -t =S -u @aitask_project_root`. The refusal message names
  the first two.
- **Unregistered sessions still guess** (pane vote, then the legacy global). A
  1-vs-1 tie is a deterministic guess, not a refusal. For a registered session
  the root cannot change mid-dialog or between ticks, so the hardening below is
  independent and is **deferred**:
  - **F1 `bind_dialog_project_root`:** bind the root when a monitor/minimonitor
    dialog opens and revalidate it at every confirmation (`p` number → confirm,
    `n`, `R`, `E`, column create/move). Also make the no-followed-pane `p` path
    use one root for both lookup and launch. Concern 2 from your review.
  - **F2 `unregistered_session_ambiguity`:** for unregistered sessions, flag a
    tied or disagreeing pane vote or a failed read as unverified. Acting
    consumers then refuse: monitor actions, the switcher guard plus a dedupe
    preference for a verified record, marks / purge, restore authorization on
    incomplete scans, and the project-resolve candidates. Concerns 1 and 3, and
    the stray-mark hazard, restricted to unregistered sessions.
- **Concern 1 (a failed registry read lets the pane vote win silently) mostly
  disappears.** The registration arrives in the same `list-sessions` call as
  the session name, so the session list cannot succeed while the registration
  read fails. The leftover case is an unregistered session with a failed
  `list-panes` falling back to a stale legacy global; that is today's behaviour
  and moves to F2.
- **Concern 4 (a refused registration still modifies the session)** is fully
  in scope; see Takeover protection above.

## Steps

### Pre-phase (risk mitigations)
1. [characterize_discovery_unanimous] Before changing the resolver, add
   `tests/test_discover_characterization.py` and run it green against the
   current code. It pins `(session, project_root)` for three cases: panes that
   all agree, registry-only (no pane resolves, legacy global set), and no
   match (excluded). It checks each case in `discover_aitasks_sessions()`,
   `_async()` and `_checked()` (`complete=True`). The fake answers the
   `list-sessions` query whatever its `-F` string, so the file must stay
   green **unchanged** after Step 1.

### 1. Discovery (`.aitask-scripts/lib/agent_launch_utils.py`)
- Add the constant `PROJECT_ROOT_OPTION = "@aitask_project_root"` and
  `_SESSION_LIST_FORMAT = "#{session_name}\t#{@aitask_project_root}"`. Add
  `_parse_session_list(out) -> list[tuple[str, str]]`, which splits each line
  on its **first** tab. A line with no tab parses as unregistered, so fakes
  that return bare names keep working.
- Add `_registered_root(value) -> Path | None`, applying the same marker check
  as `_registry_entry_from_output`.
- Add `_pane_vote(pane_paths) -> Path | None`: count walk-up roots by realpath
  key, take the highest count, and break ties by the smallest key string. It
  replaces `_project_root_from_pane_paths`; `:1310` and `:1394` are its only
  callers.
- `_collect_live_roots(run, read_registry)`: same seam. Per session:
  registered root → append it and skip `list-panes`. Otherwise
  `_pane_vote(panes)`, then `read_registry(session)` only when the vote finds
  nothing, exactly as today.
- `discover_aitasks_sessions_async`: the same structure, using the shared
  helpers.
- `discover_aitasks_sessions_checked`: its `run` adapter is unchanged. A
  registered session issues no `list-panes`, so it cannot be marked incomplete
  by one. The checked dispositions are otherwise unchanged; update the
  docstring.
- New `unregistered_session_attribution(session) -> tuple[Path | None, bool]`.
  It applies rules 2–3 (pane vote, then the legacy global) to **one** session
  through the same checked adapters as `discover_aitasks_sessions_checked`, so
  any failed read comes back as `complete=False`, never as "no owner". It is
  used only by the bash claim (step 4 of the claim rule).
- Docstrings: `AitasksSession`, `discover_aitasks_sessions` (detection
  priority), `_collect_live_roots`.

### 2. Claim and refusal (`.aitask-scripts/lib/tmux_bootstrap.sh`)
- Rewrite `_tmux_bootstrap_set_project_registry <root> <session> [--created]`
  to follow the five-step claim rule above exactly. It returns 0, 45, 46 or 47
  and checks every mandatory command explicitly (`if ! …; then … return 4x; fi`),
  never relying on errexit. Rewrite its header comment, and add the exit codes
  and sentinels to the file's exit-code list.
- Add a helper `_tmux_bootstrap_session_evidence <session>`. It resolves Python
  through `lib/python_resolve.sh`, runs the heredoc, and prints `ROOT:<path>`,
  `NONE` or `UNVERIFIED`. Python missing, crashing, or reporting
  `complete=False` all produce `UNVERIFIED`.
- `spawn_session_detached`: keep a local `created=1` on the branch where this
  call's `new-session` succeeded. Then run
  `_tmux_bootstrap_set_project_registry "$root" "$session" ${created:+--created} || return $?`
  **before** `_tmux_bootstrap_ensure_syncer_window` and before the
  `BOOTSTRAP_CREATED` echo. Document the new exit codes in the ensure-mode
  paragraph.
- Read `aidocs/framework/tmux_gateway.md` and `aidocs/framework/shell_conventions.md`
  before editing. Every call goes through `ait_tmux`, and
  `tests/test_no_raw_tmux.sh` must stay green.

### 3. `ait ide` (`.aitask-scripts/aitask_ide.sh`)
- `set_project_registry`: capture the return code
  (`rc=0; _tmux_bootstrap_set_project_registry "$(pwd)" "$SESSION" || rc=$?`)
  and `die` with the code-specific message whenever `rc != 0`. The owner path
  for 45 comes from the sentinel line on the helper's stderr. The inside-tmux
  and existing-session branches both call it before any window creation, which
  is already the order.
- Fresh path: capture `spawn_session_detached`'s rc the same way. 45/46/47 →
  code-specific `die`; any other non-zero keeps today's failure. The frozen
  offer and the attach run only on 0.

### 4. Docs
- `website/content/docs/tuis/monitor/reference.md` (Multi-session view): replace
  the discovery list with the three rules, plus the refusal behaviour for
  another project's `ait ide`. Run `python3 check_links.py --build` in `website/`.
- `aidocs/framework/cross_repo_references.md:104`: discovery now uses the
  session option first, with the global as a fallback.
- `ait ide --help` (in `aitask_ide.sh`): add one sentence on the refusal.

### 5. Tests
- **New `tests/test_session_root_resolution.py`.** Covers `_collect_live_roots`
  through fake `run` / `read_registry` callables, plus the async path. Cases:
  - registered A, one pane in B, the rest in A → A (the task's core regression);
  - registered A, **every** pane in B → A (registration is authoritative);
  - the same pane set, unregistered, with the B pane first and then last → the
    same root (order independence);
  - unregistered 1 B vs 3 A → A; a 1-vs-1 tie → the smallest realpath in both
    orders;
  - registered value with no marker file → pane vote;
  - unregistered with no resolving pane → legacy global consulted, and an
    invalid global excludes the session;
  - a registered session issues no `list-panes` and no `show-environment`;
  - checked `complete=True` holds for registered sessions;
  - async results equal sync results for all of the above.
- **Update the fakes keyed on the exact old argv**
  `("list-sessions","-F","#{session_name}")` to accept the new format string:
  `test_discover_async_parity.py`, `test_discover_default_unchanged.py`,
  `test_discover_include_registered.py`, `test_discover_checked.py`,
  `test_agent_freeze.py`, `test_agent_restore.py`, `test_syncer_rows.py`,
  `test_launch_in_tmux_pane_pid.py`. Fix whichever of these fail. The no-tab
  parse keeps fakes that return bare names valid.
- **New `tests/test_session_claim.sh`** (real isolated tmux server; skipped
  when tmux is missing). Projects A and B, session S.
  - **Upgrade path (the key regression):** S is created by plain `tmux
    new-session -c A` and `AITASKS_PROJECT_S=A` is set, but there is **no
    stamp**.
    - B's claim → 45, the sentinel names A, the option is still unset, and the
      global still reads A.
    - `bash tmux_bootstrap.sh B` (ensure mode, B's config has
      `syncer.autostart: true` and `default_session: S`) → 45, and no `syncer`
      window is added.
    - **Full** `aitask_ide.sh` from B (`TMUX` unset, isolated socket) →
      non-zero exit, the refusal text is printed, the window list is unchanged
      (no monitor, no syncer), and no attach happens.
  - The same unstamped S, claimed by A → 0, and the stamp reads A. A's own
    pre-upgrade session is still claimable when one of its panes has `cd`'d
    into B (A holds the majority).
  - Stamped A → B's claim → 45; A's re-claim → 0 (idempotent).
  - **Genuine recreation:** kill S, then `bash tmux_bootstrap.sh B` → this
    invocation creates S (`--created`) → 0, and the stamp reads B. This holds
    even though the legacy global still reads A.
  - An unstamped S whose panes are all outside any project and with no legacy
    global → B claims.
  - A stamp pointing at a non-project path → treated as unstamped → evidence
    decides.
- **Injected command failures** (stub `tmux` first on `PATH` that delegates to
  the real binary except for the targeted subcommand, as
  `test_ide_session_override.sh` does). Each case runs **full `aitask_ide.sh`**
  and the ensure bootstrap, and asserts a non-zero exit, the
  `claim_unverified` / `claim_write_failed` sentinel, and no `new-window`,
  `syncer`, frozen offer or attach in the stub log:
  - `show-options` fails → 46, and no `set-option` is attempted;
  - `set-option` fails → 47;
  - `set-option` "succeeds" but the re-read returns another value → 47;
  - the evidence heredoc fails (a forced `UNVERIFIED`) → 46.
- **Pick-by-number** (`tests/test_minimonitor_pick_by_number.py`, using the
  `_mk_app` pattern). Build the session map from `discover_aitasks_sessions()`
  over a fake tmux where S is registered to A and one pane is in B. The typed
  id exists in both repos. The dialog resolves A's task, and `_launch_pick`
  receives root A.
- **Marks** (`tests/test_monitor_agent_marks_action.py`). Steps:
  - a mark is stored under A, and the mapping is S→A → the mark is found;
  - the mapping flips to S→B → `_collect_marks_observation` does not list A as
    sweepable, so the mark under A survives a purge;
  - the mapping flips back → the mark is found again.

### Post-phase (risk mitigations)
1. [live_wandering_pane_regression] Extend
   `tests/test_list_panes_session_scope_live.sh` (real isolated server):
   - Session S with two panes in A, claimed through
     `_tmux_bootstrap_set_project_registry A S`.
   - `send-keys "cd B" Enter` to the **first** pane only, and wait for its
     `pane_current_path`.
   - Sync, async and checked discovery all map S → A.
   - Then `_tmux_bootstrap_set_project_registry B S` → 45, and the option still
     reads A.

## Verification
- `bash tests/run_all_python_tests.sh`; the last line must read
  `PYTHON SUITE: PASSED`.
- Run individually: `tests/test_session_claim.sh`,
  `tests/test_list_panes_session_scope_live.sh`,
  `tests/test_multi_session_primitives.sh`, `tests/test_ide_session_override.sh`,
  `tests/test_ide_frozen_offer.sh`, `tests/test_restore_session_bootstrap_live.sh`,
  `tests/test_multi_session_monitor.sh`, `tests/test_multi_session_minimonitor.sh`,
  `tests/test_tui_switcher_multi_session.sh`, `tests/test_no_raw_tmux.sh`.
- `shellcheck .aitask-scripts/lib/tmux_bootstrap.sh .aitask-scripts/aitask_ide.sh`.
- Live, on this server: after `tmux -L ait set-option -t =aitasks @aitask_project_root /home/ddt/Work/aitasks`
  (or re-running `ait ide`), discovery maps `aitasks` → `/home/ddt/Work/aitasks`
  even with a pane in thinking_app.

## Step 9 (Post-Implementation)
Commit the code as `bug: … (t1922)`, commit the plan through
`aitask_task_commit.sh`, create the F1/F2 'after' tasks (Step 8d), and archive.

## Risk

### Code-health risk: medium
- The `list-sessions` format string changes, and every Python fake keyed on the
  old exact argv must be updated. A missed one fails loudly, never silently.
  The no-tab parse keeps bare-name fakes valid · severity: low (residual — addressed by inline pre-phase characterize_discovery_unanimous) · → mitigation: inline pre-phase characterize_discovery_unanimous
- The claim adds new non-zero exits (45/46/47) on the `ait ide` /
  ensure-bootstrap path. A wrong ownership comparison (realpath, symlinks) or
  an over-strict evidence check could refuse a project's own session · severity: low (residual — addressed by inline post-phase live_wandering_pane_regression) · → mitigation: inline post-phase live_wandering_pane_regression
- The evidence check runs Python from the bash startup path, so a broken venv
  makes `ait ide` refuse unstamped existing sessions (46). This is fail-closed
  by design, bounded to one claim per pre-upgrade session, and fresh sessions
  never need it · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Unregistered sessions (pre-upgrade, or created by hand) still rely on a pane
  guess. A tie, or a failed read, can still mis-root one, together with its
  marks and `p`, until `ait ide` stamps it · severity: medium · → mitigation: unregistered_session_ambiguity
- Mid-dialog root changes are still possible for unregistered sessions whose
  vote flips · severity: low · → mitigation: bind_dialog_project_root

### Planned mitigations
- timing: pre-phase | name: characterize_discovery_unanimous | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: discovery-consumer regression in the unanimous case | desc: Pin current sync/async/checked discovery results for unanimous, registry-only and no-match sessions before changing the resolver
- timing: post-phase | name: live_wandering_pane_regression | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: claim/refusal correctness on real tmux; fake-runner fidelity | desc: Real-tmux regression: registered session with one pane cd'd into project B maps to A in all three discovery paths, and B's claim is refused
- timing: after | name: bind_dialog_project_root | type: bug | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: mid-dialog root change (review concern 2) | desc: Bind the session root when monitor/minimonitor dialogs open (p, n, R, E, column create/move) and revalidate before every launch/kill/write; one root for no-followed-pane p
- timing: after | name: unregistered_session_ambiguity | type: bug | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: unregistered-session guesses (review concerns 1, 3, stray marks) | desc: Flag unregistered sessions whose pane vote ties or whose reads failed as unverified; acting consumers (monitor actions, switcher launches + dedupe preference, marks/purge, restore, project-resolve candidates) refuse
