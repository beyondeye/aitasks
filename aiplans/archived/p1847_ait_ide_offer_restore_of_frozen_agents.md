---
Task: t1847_ait_ide_offer_restore_of_frozen_agents.md
Base branch: main
Output branch: main
---

# t1847 — `ait ide` offers to bring back frozen agents whose panes are gone

## Context

After a PC shutdown the tmux server dies, so every frozen stand-in viewer dies
with it. The records survive in the session store as `frozen` with a pane that no
longer exists, and `reconcile` deliberately leaves them alone
(`agent_freeze._reconcile_frozen` → `KEEP:<id>|pane_gone`). `ait ide` has no
frozen-agent logic, so the user gets a fresh session with no sign of them
(observed 2026-09-21: 6 records survived, nothing surfaced).

Goal: when `ait ide` starts or attaches to a project session, find **this
project's** `frozen` records whose viewer is not tracked, list them, and offer
to recreate their viewers (default), restore all, re-pick all, or skip.
Everything lands in **the session `ait ide` is opening**, under the record's
**recorded window name**. Recreated viewers must be fully back in the state
machine: pane stamped `@aitask_frozen`, record pane/pid updated via the store's
existing `standin-respawned` verb, so monitor/minimonitor show `F` and
restore/drop work from the new pane.

Existing machinery reused:
- `agent_sessions.standin_respawned` accepts `frozen → frozen` after a
  `lease-take` (agent_sessions.py ~1149), so no new store verb is needed.
  `lease-release` is already a CLI verb (~2296).
- `agent_restore._session_for_root(root, name=…)`,
  `_bootstrap_project_session`, `_spawn_companion` (t1851),
  `unique_window_name`.
- `frozen_ops.probe_pane` (present / gone / unknown, t1773) and
  `frozen_ops.kill_if_stamped` (stamp check and kill in ONE `if-shell -F`
  dispatch, verified by an after-read, t1783).
- The viewer stamps `@aitask_standin_ready=<id>` on its own `$TMUX_PANE` when
  it mounts in `--record` mode (`frozenagent_app._stamp_ready`), which gives an
  unforgeable identity even for a viewer window whose `@aitask_frozen` stamp
  was never written.

## Design decisions

- **New module `lib/agent_reopen.py`**, on the coordinator side. It may import
  `agent_restore`; `agent_freeze` still must not. It is reached through
  `aitask_frozen.sh` verbs: `gone --root <p>` (read-only) and
  `reopen <id> | --root <p>`, both with an optional `--session <name>`.

- **Two recoverable kinds, one batch (review round 2, concern 1).** For a
  `frozen` record of the root, one `list-panes -a` pass collects every live
  pane that claims the record ("claimed panes"). A pane claims record `id`
  when `@aitask_frozen == id`, OR `@aitask_standin_ready == id`, OR its
  window name matches `-reopen-<id>-<8 hex>$` — the attempt-name identity
  described below. Then:
  - claimed pane == the record's own `pane_id` → **tracked**; not listed;
  - a claimed pane exists but is not the record's pane → **stranded** (an
    untracked survivor of an earlier failed reopen, or of an uncertain launch);
  - no claimed pane, and (`pane_id` empty, OR `probe_pane` = gone, OR present
    with a foreign stamp) → **gone**;
  - tmux unreachable → `GONE_ERROR:<id>|tmux_unreachable` (fail closed).
  `gone` lists both kinds with a `kind` field. `reopen --root` processes both:
  gone → a fresh window; stranded → **adopt**. The `ait ide` offer therefore
  reaches every survivor.

- **Adoption honours the selected session.** With `--session S`, a stranded
  pane that lives in another session is moved into S before it is recorded:
  a guarded `move-window -s <pane> -t '=S:'` inside one `if-shell -F` on the
  claim (`#{||:#{==:#{@aitask_frozen},<id>},#{==:#{@aitask_standin_ready},<id>}}`),
  then an after-read of `#{session_name}`. If the move fails, the command
  reports `REOPEN_FAILED:<id>|adopt:move` and the pane is left untouched.

- **Session targeting (round 1, concern 1).** `ait ide` passes the session it
  resolved to every launch path: `reopen --session S` and
  `restore <id> [--repick] --session S`. With `--session`, the target is
  `_session_for_root(realpath(root), name=S)`. When S is not attributed to the
  root, the command fails closed (`session_not_for_root:<S>`), with no
  bootstrap and no fallback to another same-root session. Without `--session`,
  behaviour is unchanged.

- **Session-name parsing (round 2, concern 2).** The token after `--session` is
  taken **verbatim as its value, even when it starts with `-`**. The rule is
  exactly `ait ide`'s (`_tmux_bootstrap_session_name_ok`): non-empty, no `.`,
  no `:`. So `ait ide --session -n` recovers its agents. A missing value is a
  usage error (exit 2).

- **Window identity from creation to cleanup (round 1, concerns 2–3).**
  - The window is created **detached under an attempt name**
    `<final>-reopen-<id>-<nonce8>`, through the gateway directly
    (`new-window -d -P -F '#{pane_id}\t#{pane_pid}'`), not `launch_in_tmux`.
    The name serves two purposes. The record id makes it **discoverable by any
    later run with no stored state**: tmux sets the name atomically with the
    window's creation, so there is no instant at which the window exists
    unclaimed (round 3, concern 2). The nonce makes it **unique per attempt**,
    so the name guards and lookups of one attempt never match another
    attempt's survivor. Record ids are 8-hex (`agent_sessions._ID_RE`), so the
    pattern is unambiguous.
  - From creation to commit the pane is claimed at every instant: first by the
    attempt name, then by the verified stamp (set before the rename), then by
    the record itself.
  - First write: a **name-guarded stamp** (`if-shell -F` on
    `#{==:#{window_name},<temp>}` → `set-option -p @aitask_frozen <id>`),
    then a re-read to verify it.
  - After that, every cleanup is `frozen_ops.kill_if_stamped(pane,
    option=FROZEN_OPTION, expect=id, window=True)`. The code **never unstamps
    before killing**. Before the stamp is verified, cleanup is a name-guarded
    kill with the same dispatch-then-after-read verdict shape.
  - A cleanup that is not verified `gone` is reported and the stamp is kept. The
    survivor is then **stranded**, and the next `reopen`/`ait ide` adopts it.

- **Uncertain launch (round 2, concern 3).** A non-zero `new-window` rc is
  **not** read as "nothing created": the gateway's `-1` also covers a timeout
  after which the server may have completed the command. On any non-zero rc,
  look the temp name up (`list-panes -t '=S:<temp>'`):
  - exactly one pane → continue as a launch that succeeded, with its identity
    recovered;
  - tmux answered and found nothing (rc > 0, or empty output) → nothing was
    created; release the lease and report `launch:rc=<rc>`;
  - lookup unreachable or ambiguous → report `launch:uncertain` and release
    the lease. A window that did get created carries the attempt name from its
    first instant, so any later run, including one before the viewer mounts
    and self-stamps, classifies it as **stranded** and adopts it rather than
    duplicating it. A run that overlaps a still-in-flight attempt sees the
    same claim and gets `LEASE_HELD` → skip.

- **Rename inside the transaction (round 2, concern 4).** The rename to the
  final recorded name happens **before** `standin-respawned`: a stamp-guarded
  `rename-window`, then an after-read verifying `#{window_name}`. The final
  name is `unique_window_name(names_of_other_windows, rec.window or
  "agent-frozen")`. The collision set **excludes the window being renamed**
  (round 4, concern 2), and when the current name already equals that
  result, no rename is issued. A survivor that already carries its final
  name, for example after a store failure whose cleanup also failed, is
  therefore never pushed to a `-2` suffix by its own name. The result is
  stable across reruns.
  - On a fresh launch, a failed rename triggers guarded cleanup and the
    command fails.
  - On adoption, the pre-existing window is left as it is and the command
    fails; the record is not committed, so the pane stays stranded and the
    next run retries the rename.
  - Adoption always runs the rename too, which repairs any `-reopen-` survivor.
  - Nothing can fail after the commit except the best-effort companion spawn.

- **Test seams (round 2, concern 5).** `agent_reopen` gets its own
  **combination-aware** seam. `AITASKS_REOPEN_FAIL_AT` is a comma-separated
  stage set (`launch,launch_uncertain,lookup,identify,stamp,rename,store,cleanup,move`;
  `lookup` makes the attempt-name lookup report tmux unreachable),
  honoured only under `AITASKS_TEST_MODE=1`. It is implemented locally as
  membership in the split set, so the shared `frozen_ops.make_fail_at`
  (exact-match, one stage) is untouched.

- **Restore / re-pick all** from `ait ide` covers **every listed record, gone
  and stranded alike** (round 3, concern 1):
  1. Run `reopen --root R --session S` first. Every listed record then has a
     tracked viewer in S under its recorded name: gone records get a fresh
     window, stranded ones are adopted.
  2. **Re-classify before restoring** (round 4, concern 1): run `gone --root R`
     again, and decide per listed id on its **current** state, not on what
     reopen printed:
     - no longer listed → **tracked**: its viewer is the record's own pane, so
       `restore` takes its existing **same-pane** branch and respawns the
       agent inside the viewer, keeping the companion and the name;
     - still `gone` (no claimed pane anywhere, reopen failed) → restoring is
       safe: nothing would be left behind, and the gone-pane branch targets S
       via `--session S`;
     - still `stranded` → **skip**, and report it as "viewer open but not
       tracked — not restored; re-run `ait ide`". Restoring it would launch a
       second agent elsewhere and orphan the viewer;
     - `GONE_ERROR` (unreachable) → skip and report.
  3. Loop `restore <id> [--repick] --session S` over the ids that step 2
     allowed and whose mode is not blocked.
  A record whose mode is blocked, or whose restore fails, stays a viewer:
  `restore`'s rollback respawns the stand-in in the same pane. The prompt
  labels say so explicitly: "Restore all (records that cannot resume stay as
  viewers)" / "Re-pick all (records without a task stay as viewers)".

- **Companion** after a successful commit: `_spawn_companion(S, final, pane,
  root)`, best-effort. `maybe_spawn_minimonitor` already refuses a window that
  holds a live minimonitor, so an adopted window that kept its companion is
  not doubled.

- **Non-interactive:** never prompt; print a one-line hint and continue. Any
  error in the offer warns and continues; startup is never blocked.

## Implementation steps

### 1. `agent_restore.py` — pure eligibility helpers + session threading

- Extract the preflight rules in `restore()` (~494–512) into
  `resume_blocker(rec)` (`""` / `no_session` / `resume_unsupported:opencode`)
  and `repick_blocker(rec)` (`""` / `no_task_id`). `restore()` uses them with
  unchanged wire lines.
- Extract target resolution (~435–448) into
  `_resolve_target_session(root, session=None) -> (target|None, error)`.
  - With `session`: `_session_for_root(realpath(root), name=session)`, else
    `session_not_for_root:<session>`, and no bootstrap.
  - Without it: today's first-match-then-bootstrap logic, verbatim.
- `restore(record_id, *, repick=False, session=None)` →
  `_launch_into_new_window(rec, command, env, session=session)`, which uses
  `_resolve_target_session`.
- `main()`: parse `--session <value>` positionally, taking the next token
  verbatim even if it begins with `-`. Validate with
  `session_name_ok(name)` (non-empty, no `.`/`:`), a new small public helper
  that `agent_reopen` also uses. Accepted on `restore <id>` and
  `restore --all`.

### 2. New `lib/agent_reopen.py`

The module docstring covers: the seam rule; store writes only via
`frozen_ops.store`; tmux only via `frozen_ops.run`; the identity protocol; the
classification; why the code never unstamps before killing; and why the
rename precedes the commit.

- `_claimed_panes() -> dict[id, list[Claim]] | None`: one `list-panes -a -F`
  with `#{pane_id}`, `#{pane_pid}`, `#{pane_dead}`, `#{session_name}`,
  `#{window_name}`, `#{@aitask_frozen}`, `#{@aitask_standin_ready}`. Dead
  panes are ignored. A claim is keyed by the stamp, the ready mark, or the
  attempt-name regex `-reopen-([0-9a-f]{8})-[0-9a-f]{8}$` on the window name.
  Returns None when tmux is unreachable.
- `classify(root) -> (items, error_lines)`: `store list --state frozen --root
  <root>`, then `frozen_ops.store_show(id)` per record → `gone` / `stranded`
  per the design.
- `gone` CLI: `GONE:<id>|<kind>|<window>|<task_id>|<frozen_at>|<resume_blocker or ok>|<repick_blocker or ok>`,
  then `GONE_ERROR:` lines, then `GONE_COUNT:<n>`. Exit 0; exit 1 only when
  the store list fails.
- `reopen_one(record_id, *, session=None) -> str`: re-read (not `frozen` →
  `REOPEN_SKIPPED:<id>|state:<s>`), re-classify (tracked →
  `REOPEN_SKIPPED:<id>|pane_present`; unreachable → `REOPEN_FAILED:<id>|preflight:tmux unreachable`),
  `lease-take` (`LEASE_HELD` → `REOPEN_SKIPPED:<id>|lease_held`),
  `_resolve_target_session(root, session)`. Then dispatch; every failure exit
  after the lease runs `lease-release`:
  - **fresh** (`gone`): new-window under the temp name (the uncertain-launch
    rules above) → identify (`-P` output, else the name lookup) →
    name-guarded stamp + verify → guarded rename to the final name + verify →
    `standin-respawned`.
    - A failure before the stamp is verified → name-guarded kill.
    - A failure after it → `kill_if_stamped(window=True)`.
    - An unverified cleanup appends `|cleanup:<verdict>:<reason>|pane:<p>` and
      keeps the stamp.
  - **adopt** (`stranded`):
    1. Ensure the `@aitask_frozen` stamp when the claim is only the ready mark
       or only the attempt name. Use a guarded `set-option` whose `if-shell -F`
       condition is the exact claim that was observed (`@aitask_standin_ready
       == id`, or `window_name ==` the full observed attempt name), then verify.
    2. Move into S if needed (guarded + verified).
    3. Guarded rename + verify.
    4. `standin-respawned` with that pane/pid.
    No kill on failure: the pane pre-existed, and the next run retries.
  - On success: `_spawn_companion` →
    `REOPENED:<id>|<fresh|adopted>|<S>:<final>|<pane>`.
- `reopen_all(root, *, session=None)`: sequential over `classify(root)`, one
  failure never stops the batch, trailing `REOPEN_ALL:<ok>/<n>`.
- `_kill_if_named(pane_or_target, name)`: `if-shell -F` on
  `#{==:#{window_name},<name>}` → `kill-window`, then an after-read →
  `gone|present|unknown`, the same verdict contract as `kill_if_stamped`.
- `_fail_at(stage)`: the combination-aware seam above. `cleanup` makes the
  guarded kill a no-op returning `("present", "seam")`. `launch_uncertain`
  dispatches the real `new-window`, then reports rc `-1` with no output.
- `main()`: `gone --root <p>`, `reopen <id> [--session S]`,
  `reopen --root <p> [--session S]`, with the verbatim `--session` rule.
  Exit 0 all-ok, 1 some failed, 2 usage.

### 3. `aitask_frozen.sh`

Add `gone` / `reopen` to the header comment, usage and verb `case`, with
`ENGINE="$SCRIPT_DIR/lib/agent_reopen.py"`. Gates: `gone` `$# -ge 3`,
`reopen` `$# -ge 2`; the module owns the grammar. Usage for `restore` gains
`[--session NAME]`.

### 4. `lib/ide_frozen_offer.sh` (new, sourced by `aitask_ide.sh`)

`ide_offer_frozen_agents <root> <session> <frozen_sh>`:
1. `out=$("$frozen_sh" gone --root "$root")`; on failure, warn and return 0.
2. Parse the `GONE:` lines; if there are none, return silently.
   `GONE_ERROR:` lines → warn.
3. Non-interactive (tty check; test override `AIT_IDE_FROZEN_ASSUME_TTY=1`,
   honoured only under `AITASKS_TEST_MODE=1`) → a one-line hint naming
   `ait frozenagent`; return 0.
4. Table: window, task (`t<id>` / `—`), frozen_at, `restore: yes/no`,
   `re-pick: yes/no`. Markers: `(view only)` when neither is possible,
   `(viewer open, untracked)` for stranded records.
5. Prompt, with counts filled in:
   `[V]iewers for all N (default)  [R]estore K of N (rest stay as viewers)
   re-[P]ick J of N (rest stay as viewers)  [S]kip`. Empty ⇒ V.
6. V → `"$frozen_sh" reopen --root "$root" --session "$session"`. R/P → the same
   `reopen` first, then a second `gone --root`. Ids absent from it (tracked)
   or still `gone` are restored; ids still `stranded` or in `GONE_ERROR` are
   skipped and reported. Then loop
   `restore <id> [--repick] --session "$session"` over the allowed listed ids
   whose mode is not blocked.
   S → hint. Result lines are printed, followed by a summary
   (`restored X, viewers Y, failed Z`); the function always returns 0.

### 5. `aitask_ide.sh`

Source the lib. Call `ide_offer_frozen_agents "$(pwd)" "$SESSION"
"$SCRIPT_DIR/aitask_frozen.sh"` once the session exists and its registry
entry is set, before each `exec tmux …`:
- the inside-tmux path, after `ensure_syncer_window`;
- the attach path, after `ensure_syncer_window`;
- the fresh path, after `spawn_session_detached`.

Add a `--no-frozen-check` flag and a `--help` paragraph.

### 6. Documentation

- `website/content/docs/workflows/freeze-and-restore-agents.md` ("Before
  shutting down"): cover the `ait ide` offer (viewers / restore / re-pick /
  skip, in the opened session, under recorded names) and the non-interactive
  hint. Also say that other projects' records stay in `ait frozenagent` list
  mode, and document `--no-frozen-check`.
- `website/content/docs/installation/terminal-setup.md`: one paragraph in the
  `ait ide` section.
- `python3 check_links.py --build` in `website/`.

### 7. Tests

- `tests/test_agent_reopen.py` (pattern: `tests/test_agent_restore.py`,
  swapping `agent_frozen_ops.store` / `_TMUX` in place):
  - Classification: tracked / stranded (via `@aitask_frozen`, via
    `@aitask_standin_ready` only, and via the attempt name only) / gone
    (empty pane, probe gone, foreign stamp) / unreachable. Another record's
    attempt name (a different id) is not a claim.
  - The fresh-path call order.
  - The rc≠0 lookup rules: found → continue; not found → `launch:rc`;
    unreachable → `launch:uncertain`.
  - A stamp miss → name-guarded kill.
  - A rename miss → cleanup, no `standin-respawned`.
  - The final-name rule: the own window is excluded from the collision set;
    a current name that already equals the result → no `rename-window` call;
    a name held by another window → `-2`, stable on rerun.
  - A store failure → `kill_if_stamped` is called and `unset_option` is never
    called.
  - Adopt: stamp-if-needed, move when the session differs, rename,
    `standin-respawned`; no kill on an adopt failure.
  - `LEASE_HELD`.
  - `--session -n` is accepted; `--session a.b` and a missing value → exit 2.
  - A session not attributed to the root → `session_not_for_root`, with no
    new-window call.
  - The seam parses comma sets.
- `tests/test_agent_restore.py`:
  - the blockers;
  - `restore()` wire lines unchanged;
  - `session=` unattributed → `session_not_for_root` and no bootstrap;
  - `session=` given → launch targets that session even when another same-root
    session sorts first;
  - `--session -n` parsing.
- `tests/test_ide_frozen_offer.sh` (a stub `frozen_sh` logging its args):
  - no records → silent; non-tty → hint only;
  - V/empty → `reopen --root R --session S`, including an `S` of `-n`;
  - R → `reopen`, then a second `gone`, then `restore … --session S` for
    resume-eligible ids that are now tracked or still `gone`. Ids that the
    stub's second `gone` still reports `stranded` (or `GONE_ERROR`) get no
    `restore` call and are reported. P → the same, with `--repick` for
    task-bearing ids. S → nothing;
  - the prompt shows the K/J/N counts; stranded rows carry their marker;
  - a `gone` failure → a warning and status 0.
- `tests/test_ide_session_override.sh` stays green (pass `--no-frozen-check`
  in any case that reaches the offer).

### Post-phase (risk mitigations)

1. [live_reopen_roundtrip] Add `tests/test_frozen_reopen_live.sh`, modelled on
   `tests/test_restore_flows_live.sh`: an isolated tmux socket, a temp session
   store, the `AITASKS_FROZEN_STANDIN_CMD` stand-in stub (a real `ait
   frozenagent --record` for case (h), since that case needs the self-stamp),
   and `AITASKS_TEST_MODE=1`. It skips cleanly when tmux is absent, and uses
   `assert_counters_init`/`load` if any case runs in a subshell. Cases:
   - **(a) happy path.** Seed a `frozen` record whose `pane_id` names no pane.
     `reopen --root <proj> --session <S>` → `REOPENED:<id>|fresh|…`. The window
     is named exactly the recorded name, its pane has `@aitask_frozen=<id>`,
     and `show <id>` has that pane with a matching pid, state `frozen`, no
     lease. A second `reopen --root` is a no-op.
   - **(b) drop.** `aitask_frozen.sh drop <id>` succeeds against the new pane,
     and the window's stand-in is gone.
   - **(c) two same-root sessions.** A and B are both registered to the
     project, and A sorts first. `reopen --session B` → the window lands in B
     only. `--session C`, where C belongs to another root →
     `session_not_for_root`, and no window appears anywhere.
   - **(d) stamp failure.** `FAIL_AT=stamp` → `REOPEN_FAILED:<id>|stamp`; no
     window survives; the record stays unchanged; a following `lease-take`
     succeeds.
   - **(e) lost identity.** `FAIL_AT=identify` still gives `REOPENED:` (found
     by name). `FAIL_AT=identify,stamp` → no window survives.
   - **(f) store failure and adoption.** `FAIL_AT=store` → no window survives
     and the record is unchanged. `FAIL_AT=store,cleanup` → the line carries
     `cleanup:`. The survivor keeps `@aitask_frozen=<id>` and already carries
     the **final recorded name** (the rename precedes the store write), with
     no `-reopen-` part. `gone --root` lists it as `stranded`, and a plain
     `reopen --root` adopts it (`REOPENED:<id>|adopted|…`): no second window,
     the window name is **still exactly the recorded name, no `-2` suffix**,
     no `rename-window` is issued, and the record tracks it.
   - **(f2) stable suffix.** An unrelated window already holds the recorded
     name, so the fresh launch lands as `<name>-2`. After a
     `FAIL_AT=store,cleanup` survivor is adopted, the window is still
     `<name>-2`, not `<name>-3`.
   - **(g) adoption across sessions.** A stranded viewer sits in session A;
     `reopen --root --session B` moves it into B and adopts it.
   - **(h) uncertain launch, retry before self-stamp.** Use a stand-in stub
     that **never** self-stamps (`AITASKS_FROZEN_STANDIN_CMD='sleep 600'`).
     - `FAIL_AT=launch_uncertain` → found by name → `REOPENED:`.
     - `FAIL_AT=launch_uncertain,lookup` (the name lookup is forced to
       "unreachable") → `launch:uncertain`, and the lease is released.
     - An immediate retry with no seam: `gone --root` lists the record as
       `stranded` (claimed by the attempt name alone, no
       `@aitask_standin_ready`). `reopen --root` adopts it: exactly one window
       for the record in the session, stamped, renamed to the recorded name,
       and tracked.
   - **(h2) restore-all over stranded records** (drives
     `ide_offer_frozen_agents` with `AIT_IDE_FROZEN_ASSUME_TTY=1`, answer
     `R`, and a stub agent command). One gone record and one stranded record
     → both end with the agent respawned in their viewer pane in S
     (`restore`'s same-pane branch). A third record with no session id stays
     as a tracked viewer. A fourth record's adoption is forced to fail
     (`FAIL_AT=move`, stranded in another session) → it is reported as "not
     tracked — not restored", no `restore` runs for it, no agent window
     appears for it, and its viewer is untouched.
   - **(i) rename failure.** On a fresh launch, `FAIL_AT=rename` → no window
     survives. On adoption, `FAIL_AT=rename` → the stranded window is left and
     the record is not committed; a rerun without the seam renames it and
     adopts it.
   - **(j) option-like session.** A session literally named `-n`:
     `reopen --session -n` targets it.
   - **(k) restore into the right session.** `restore <id> --session B` for a
     gone-pane record (stub agent command as in the existing restore live
     test) → the replacement window lands in B.

## Risk

### Code-health risk: medium
- The new coordinator owns a lease and creates, moves and renames tmux windows. A partial failure could strand a lease, an orphan window, or a record that points at a pane that is not its viewer. Unit tests mock tmux, so the real sequence is unproven · severity: low (residual — addressed by inline post-phase live_reopen_roundtrip) · → mitigation: inline post-phase live_reopen_roundtrip
- `ait ide` now runs a Python store/tmux query before attaching, so a failure or slowness there sits on the startup path · severity: low · → mitigation: none (fail-open design in step 4: any error warns and continues)
- The change touches two load-bearing areas at once: ide startup and the frozen-agent coordinator surface, including a refactor of `restore()` preflight and target resolution · severity: medium · → mitigation: none (restore wire lines are pinned by existing tests plus the new ones in step 7)
- The identity protocol (temp name → guarded stamp → stamp-guarded cleanup, the stranded classification, adoption, and rename before commit) adds states a future editor must keep consistent · severity: medium · → mitigation: none (documented in the module docstring; each branch is live-tested in the post-phase)

### Goal-achievement risk: low
- A reopened viewer might not be fully back in the state machine (monitor `F`, restore/drop acting on the new pane) in ways only a real tmux server shows · severity: low (residual — addressed by inline post-phase live_reopen_roundtrip) · → mitigation: inline post-phase live_reopen_roundtrip
- The offer could land agents in a same-root session other than the one being opened · severity: low (residual — `--session` threaded through both launch paths; live cases (c)/(g)/(k)) · → mitigation: inline post-phase live_reopen_roundtrip

### Planned mitigations
- timing: post-phase | name: live_reopen_roundtrip | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: stranded lease/window on partial failure; reopened viewer not fully back in the state machine | desc: live tmux test of reopen → stamp/record update → drop from new pane, plus stamp-failure rollback

## Out of scope (follow-up to propose at Step 8)

`agent_restore._launch_into_new_window` has the same partial-launch and
uncertain-rc flaw. When `launch_in_tmux` returns no pid, a `-1` rc, or
`resolve_pane_id_by_pid` misses, the new agent window is left untracked. This
task only threads `session` through it. A separate bug task should apply the
temp-name identity protocol there.

## Verification

- The two Python test files (directly, or through
  `bash tests/run_all_python_tests.sh --test-dir <dir>`).
- `bash tests/test_ide_frozen_offer.sh`, `bash tests/test_ide_session_override.sh`
  and `bash tests/test_frozen_reopen_live.sh`.
- The existing frozen live tests must still pass:
  `tests/test_restore_flows_live.sh`,
  `tests/test_restore_session_bootstrap_live.sh`,
  `tests/test_frozen_agents_acceptance.sh`.
- `shellcheck .aitask-scripts/aitask_ide.sh .aitask-scripts/aitask_frozen.sh .aitask-scripts/lib/ide_frozen_offer.sh`.
- `bash tests/test_no_raw_tmux.sh`.
- Manual: freeze an agent, kill the ait tmux server, run `ait ide` → the list
  appears. `V` recreates the window with its viewer and minimonitor under the
  recorded name, monitor shows `F`, and restore from the viewer works.

## Step 9

Post-implementation: commit the code (`feature: … (t1847)`) and the plan
separately, then archive via task-workflow Step 9.

## Post-Review Changes

### Change Request 1 (2026-09-24 09:30)
- **Requested by user:** four review findings — (1) `reopen_one` classified before `lease-take`, so a second run could act on a stale `gone` reading after the first committed and released; (2) bare `=S` session targets for `list-panes -s` / `list-windows` can resolve as a window of the current session; (3) `_ide_frozen_reopen` swallowed the command's exit status; (4) live cases h2 and k from the plan were missing.
- **Changes made:**
  1. `reopen_one` re-reads the record and re-lists the claims after `lease-take` and decides only from that (tracked → skip + release; state changed → skip + release; stranded → adopt). The module docstring states the rule. Three unit tests (viewer committed before our lease / survivor appeared / record left frozen); a mutant that removes the re-read fails all three.
  2. Measured on tmux 3.7c: from a client whose current session has a window named `B`, `list-panes -s -t =B` lists the CURRENT session's panes; `=B:` is unambiguous. `agent_reopen._session_scope()` now returns `=S:` for every session-scoped read. The unit fake asserts the form on every call.
  3. `_ide_frozen_reopen` keeps the exit status; a non-zero exit that no `REOPEN_FAILED` line explains is reported with the command's last output line. Two offer-test scenarios (crash → warning; explained failure → no extra warning).
  4. Live cases k (a gone-pane `restore --session B` lands in B; a foreign session fails closed) and h2 (the offer's R over gone / stranded / view-only / failed-adoption records: two agents come back inside their viewers, the view-only one stays a tracked viewer, the untracked one is skipped and untouched) were added to `tests/test_frozen_reopen_live.sh`. They stay in the isolated class: the synthetic project symlinks `.aitask-scripts`, copies the model metadata, and a fake `claude` drives the shipped SessionStart hook; companion auto-spawn is off.
- **Files affected:** `.aitask-scripts/lib/agent_reopen.py`, `.aitask-scripts/lib/ide_frozen_offer.sh`, `tests/test_agent_reopen.py`, `tests/test_ide_frozen_offer.sh`, `tests/test_frozen_reopen_live.sh`

### Change Request 2 (2026-09-24 10:15)
- **Requested by user:** three review findings — (1) an explicit `--session` was authorized through `discover_aitasks_sessions()`, whose pane query uses the bare `=<s>` target, so from a client in session A holding a window named like another project's session C, C was attributed to A's root and `reopen`/`restore --session C` could put an agent into the foreign session; (2) the post-lease re-read treated `store_show`'s `{}` (unreadable store) as a harmless skip; (3) the legacy refuse-class live suites and the manual restart check are unrun.
- **Changes made:**
  1. `agent_restore._named_session_for_root` authorizes an explicit session through `discover_aitasks_sessions_checked()` (t1869; `=<s>:` target, reports completeness). A foreign root → `session_not_for_root:<s>`; an incomplete scan without a positive attribution → `session_unverified:<s>`. The shared default discovery is NOT changed — t1874 owns the bare-target sweep across all call sites. New live case c2 reproduces the collision (precondition asserts that a bare `=C` from A lists A's panes) and proves both `reopen` and `restore` fail closed with no window created; a mutant that reverts to the unchecked discovery fails c2 exactly as the reviewer described (`REOPENED …|C:agent-c3`, record `live`).
  2. An empty re-read under the lease is `REOPEN_FAILED:<id>|reread:record unreadable`, lease released. Unit test added.
  3. Not runnable from this session (it runs inside the live `-L ait` server, and those suites refuse by design). Recorded as a pending manual-verification follow-up rather than claimed: `tests/test_restore_flows_live.sh`, `tests/test_frozen_agents_acceptance.sh`, `tests/test_freeze_engine_live.sh` from a plain terminal with the ait server stopped, and the manual restart check (viewer + minimonitor companion, monitor `F`, restore from the viewer).
- **Files affected:** `.aitask-scripts/lib/agent_restore.py`, `.aitask-scripts/lib/agent_reopen.py`, `tests/test_agent_restore.py`, `tests/test_agent_reopen.py`, `tests/test_frozen_reopen_live.sh`

### Change Request 3 (2026-09-24 10:50)
- **Requested by user:** (1) `_launch_into_new_window` launches into the exact session, but `resolve_pane_id_by_pid` then lists panes with a bare `=<session>` — from a client in A holding a window named B, a VALID `restore --session B` launches in B, cannot find its pid, rolls back with `launched_pane_unresolvable` and leaves the window untracked; (2) create the manual-verification follow-up before claiming full verification.
- **Changes made:**
  1. `agent_launch_utils.resolve_pane_id_by_pid` targets `=<session>:` (one token, at the source — its other callers, shadow spawn / monitor / syncer, get the same correction). The remaining bare call sites stay with t1874; t1874 gets a note naming this fix and the deterministic trigger. New live case c3 (A holds a window named B, B is this project's own second session): `restore --session B` and `reopen --session B` from a client in A both succeed in B, with the record naming the launched pane. A mutant restoring the bare target fails c3 with exactly `respawn:launched_pane_unresolvable`, record left `frozen`, window left in B.
  2. The manual-verification follow-up is created at Step 8c (right after the commit, where the workflow creates it); full verification is not claimed until those checks run.
- **Files affected:** `.aitask-scripts/lib/agent_launch_utils.py`, `tests/test_frozen_reopen_live.sh`

## Final Implementation Notes
- **Actual work done:** `ait ide` now checks, before it attaches (all three start paths), for this project's `frozen` records whose viewer is not tracked, lists them, and offers V (recreate viewers, default) / R (restore) / P (re-pick) / S (skip); non-interactive runs print a one-line note; `--no-frozen-check` skips it. New coordinator `lib/agent_reopen.py` (`aitask_frozen.sh gone --root` / `reopen <id>|--root [--session]`) classifies records as tracked / stranded / gone from one `list-panes -a` claim pass, creates fresh viewer windows through the attempt-name identity protocol (attempt name → name-guarded stamp → stamp-guarded rename before commit → `standin-respawned`), adopts stranded survivors (stamp, move into the selected session, rename, commit) instead of duplicating them, and re-classifies under the lease before acting. `agent_restore` gained `resume_blocker` / `repick_blocker` / `session_name_ok` / `take_session_arg`, `_resolve_target_session`, and `--session` on `restore` (explicit sessions authorized through the CHECKED discovery). `lib/ide_frozen_offer.sh` holds the prompt; R/P reopen first, re-classify, and restore only tracked or still-gone records. Docs: `freeze-and-restore-agents.md` ("Before shutting down") and `terminal-setup.md`.
- **Deviations from plan:** attempt windows are named `aitask-reopen-<id>-<nonce>` (no recorded-name prefix) so the name is safe inside `#{==:…}` guard formats. Session-scoped reads use `=<s>:` everywhere (`_session_scope`), and `agent_launch_utils.resolve_pane_id_by_pid` was switched to `=<s>:` at the source (Change Request 3). The live suite stays in the isolated class (synthetic project with companion auto-spawn off, fake `claude` driving the shipped SessionStart hook), so it runs alongside a live `-L ait` server; the companion spawn itself is therefore not live-tested here.
- **Issues encountered:** four review rounds (see Post-Review Changes): pre-lease stale classification (fixed by re-classifying under the lease), bare `=<s>` targets resolving as a window of the current session (measured on tmux 3.7c; fixed in the reopen reads, the explicit-session authorization, and `resolve_pane_id_by_pid`), a swallowed `reopen` exit status in the offer, and an unreadable post-lease re-read read as a skip. A concurrent t1869 commit briefly swept seven of these files into a local commit; the other session undid it before push and the working tree was verified intact.
- **Key decisions:** the pre-existing frozen record is the unit of identity, never a new record; nothing is ever unstamped before a kill, so every failed cleanup leaves a survivor the next run adopts; R/P decide per record from a fresh `gone` listing, never from what `reopen` printed; the shared default `discover_aitasks_sessions()` was left to t1874.
- **Verification status:** unit (`tests/test_agent_reopen.py`, `tests/test_agent_restore.py`), offer (`tests/test_ide_frozen_offer.sh`), and live (`tests/test_frozen_reopen_live.sh`, 93/93 including real restores and both name-collision cases) all pass, with negative controls for the race, the collision authorization and the pid lookup. NOT run from this session (they refuse inside a live `-L ait` server): `tests/test_restore_flows_live.sh`, `tests/test_frozen_agents_acceptance.sh`, `tests/test_freeze_engine_live.sh`, and the manual restart check — queued as a manual-verification follow-up at Step 8c.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_restore.py:~585 — _launch_into_new_window leaves the new agent window untracked when launch_in_tmux returns no pid or a -1 rc after the server created the window (the partial-launch/uncertain-rc class agent_reopen handles with its attempt-name protocol)`
