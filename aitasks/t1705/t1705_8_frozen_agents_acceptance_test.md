---
priority: high
effort: medium
depends: [t1705_7]
issue_type: test
status: Ready
labels: [tmux, tmux_destructive, codeagent, session_persistence, test_infrastructure, testing]
gates: [risk_evaluated]
plan_approved_at: 2026-09-09 19:31
anchor: 1705
created_at: 2026-09-04 16:08
updated_at: 2026-09-09 19:31
---

## Step 0 — tmux preflight (run BEFORE anything else; blocking)

This task destructively manipulates tmux (`respawn-pane -k`, real `pane-died`
cleanup hooks, `kill-window`/`kill-server` on an isolated server). Its live
tests call `tests/lib/tmux_isolation.sh::require_clean_ait_server`, which
refuses to run from inside tmux or while the dedicated `-L ait` server has any
pane. Check this **first**, before planning or editing a file:

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

## Context

Eighth child of t1705 (frozen code agents). The feature succeeds only if
hooks, live-record binding, capture, pane stamping, cleanup abstention,
viewer launch, restore and cleanup all agree — and every earlier child
proves only its own seam. This child is the **end-to-end acceptance test
through the shipped wrappers only**, on an isolated tmux server, with a fake
agent binary standing in for `claude`/`codex` so it runs unattended. It is
the parent's risk mitigation for cross-child drift (parent plan `## Risk`,
"per-child tests can pass with incompatible joins"). Real-agent behaviour is
the manual-verification sibling's job. **Tmux-stress**: run from outside the
`-L ait` server.

## What "through the shipped wrappers" means

No test may call a Python mutator directly. The path is: `install.sh --dir
<scratch>` + `ait setup` (hooks installed by t1705_3) → an agent launched
with `aitask_codeagent.sh --agent-string claudecode/opus5 invoke raw` (the
fake `claude` on `PATH` receives the real argv) → the fake binary execs the
**real** `aitask_session_hook.sh` with a synthetic SessionStart payload and
the env it inherited (`AITASK_AGENT_STRING`, `AITASK_RESTORE_*`) → the real
store → `aitask_frozen.sh freeze` → the **real** `ait frozenagent --record`
stand-in in the pane → `aitask_frozen.sh restore` as the real detached
`run-shell -b` coordinator → the fake binary honouring `--resume <sid>`
(prints the id it got, calls the hook with that session id, sleeps) →
`drop`. `AITASKS_FROZEN_STANDIN_CMD` is **not** set here — the real viewer
must come up and self-stamp.

## Cases (`tests/test_frozen_agents_acceptance.sh`)

1. **Launch + hook binding**: after launch, `aitask_agent_sessions.sh list`
   shows one `live` record for `(root, agent-pick-1, slot 0)` with
   `pane_pid` = `#{pane_pid}`, `codeagent_session_id` = the fake's id,
   `agent_string` from the env; the pane carries `@aitask_record=<id>` and
   `@aitask_agent_session`.
2. **Freeze**: `aitask_frozen.sh freeze <pane>` → record `frozen`,
   `standin_pid` set, capture files present (0600, line count = fake
   output), the pane runs the real viewer, `@aitask_frozen` and
   `@aitask_standin_ready` set, companion pane alive, `capture-pane` of the
   stand-in pane shows the header line with the window name.
3. **Failed restore** (`FAKE_AGENT_EXIT=1`): `aitask_frozen.sh restore <id>`
   → `RESTORE_FAILED:<id>|agent_exited`, record `frozen`, capture intact,
   viewer back and ready, `restore_attempts=1`, elapsed < `restore_ack_grace`.
4. **Mismatched restore through the detached path** (`FAKE_AGENT_SESSION=other`):
   the coordinator is the real `run-shell -b` process; the hook reports the
   other id → `last_error="<nonce>:session_mismatch"` → `RESTORE_FAILED:…|session_mismatch`,
   capture intact, stand-in back, and **the liveness fallback did not fire**
   (assert elapsed < grace and `ack` is empty).
5. **Successful restore**: fake binary receives `--resume <sid>` and the
   `AITASK_RESTORE_*` env, calls the hook → `RESTORED:<id>|hook`, record
   `live`, `ack=hook`, capture files deleted, `@aitask_frozen` cleared,
   `@aitask_record` still the same id, `pane_pid` updated.
6. **Gone-pane restore**: freeze again, `kill-window`, `restore` → a new
   window with the recorded name (or `-2` suffix if it collides), the **old**
   record acknowledged (`id` unchanged, no second record, `window_slot`
   unchanged), captures deleted.
7. **Dead coordinator**: freeze; start `restore` with
   `AITASKS_FROZEN_PAUSE_AT=aborting` after a forced `FAKE_AGENT_EXIT=1`;
   `SIGKILL` the coordinator; a second `restore` is `TRANSITION_REFUSED`;
   advance past `stale_op_grace` (config it to 2 s for the test);
   `aitask_frozen.sh reconcile` → `frozen`, viewer back; the killed
   coordinator's nonce is dead.
8. **Coordinator killed after clearing ready, before respawn**
   (`AITASKS_FROZEN_PAUSE_AT=respawn` + `SIGKILL`): reconcile recognises the
   viewer by `standin_pid`, aborts, respawns, never confirms.
9. **Ambiguous relocation after a "server restart"**: two fake agents in
   one window (slot 0 and 1), kill the server, recreate the window with one
   fake agent → `UPSERTED:…|created_slot2|ambiguous_relocation`; after
   `reconcile`, the two stale records are `dead_pane`-purged.
10. **Drop**: `aitask_agent_sessions.sh drop <id>` (via minimonitor's path is
    t1705_7's test; here the CLI) → record gone, capture dir gone, pane
    options cleared.
11. **Repeated `ait setup`** in the scratch project leaves exactly one
    SessionStart entry (a cheap re-check of t1705_3's guarantee in the
    composed environment).

Each case is a `( … )` subshell with `assert_counters_init`/`_load`; the
script tears down the isolated server in a trap. Budget: the whole run must
finish in < 3 min with `restore_ack_grace=5` and `stale_op_grace=2` set via
the scratch project's `project_config.yaml` `frozen:` block.

## Amendment from t1705_2 (2026-09-06) — assert the pane->record join

Add a case asserting `@aitask_record` is present on the agent's pane after a
real hook fire, equals the stored record id, and **survives the freeze/restore
cycle** (pane user options survive `respawn-pane`, so it must still be there on
the stand-in pane and on the restored agent).

Why it lands here rather than in t1705_2: the store is tmux-free by construction
(`tests/test_no_raw_tmux.sh` permits raw `tmux` only from the two gateways), so
`upsert` cannot stamp the pane — the caller does, via `ait_stamp_record` in
`lib/agent_sessions.sh`. t1705_2 ships that helper's argv contract and id guard
against a stubbed tmux; t1705_3 asserts the hook stamps at all. Only this task
has a live agent going through the whole cycle, which is where a *missing* stamp
actually bites: the record stores fine, and the damage shows up later as the
freeze engine creating a second record for an already-recorded agent.

## Key files

- **New** `tests/test_frozen_agents_acceptance.sh`; **edit**
  `tests/lib/fake_agent.sh` (from t1705_1/5) if a knob is missing.
- **Edit** `aidocs/framework/testing_conventions.md` — a short "composed
  acceptance through shipped wrappers" paragraph pointing at this file as
  the pattern.

## Reference patterns

- `tests/test_restore_flows_live.sh` (t1705_5) and `tests/test_freeze_engine_live.sh`
  (t1705_4) — reuse their helpers by sourcing a shared
  `tests/lib/frozen_fixtures.sh` (extract it here if the two duplicated it).
- `tests/test_session_hook_install.sh` (t1705_3) — the scratch-install recipe.
- `tests/lib/tmux_isolation.sh`, `tests/lib/asserts.sh`.
- Memory/convention: "verification needs independent ground truth" — the
  ground truth here is the pane and file state observed through tmux and
  the filesystem, never the store's own claims alone.

## Verification

```bash
bash tests/test_frozen_agents_acceptance.sh        # outside the -L ait server; prints per-case PASS/FAIL and a timing line
bash tests/test_no_raw_tmux.sh
```

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_7** id=2026-09-09T10:08:51Z.b5cedc44c2d9da006f95e3fe from=t1705_7 from_verified=yes at=2026-09-09T10:08:51Z base=a13fcfa1b338ae9c99558b52c33c7dddc8aabdfa base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | t1705_7 landed. What you will be driving, and what it does NOT yet prove.
> | 
> | KEYS (identical in both TUIs, not the task's proposed z/Z/F):
> |   f = freeze this agent, Z = freeze all -- both behind a confirm dialog
> |   R = restore, p = re-pick, k = drop -- each acts only on the window's
> |       CURRENT agent (minimonitor: the followed agent; monitor: the focused
> |       card) and only when it is frozen. The guard is in the action, so on a
> |       live row `R` is still Restart and `p` is still pick-by-number.
> |   P = the EXISTING filter, widened to hide parked AND frozen. There is no
> |       `F` key.
> | 
> | DISPATCH, which matters for what your test can observe:
> |   * freeze goes through a SUBPROCESS (it respawns the agent's pane, not the
> |     TUI's), on a 90s budget for one pane and 90s x eligible-count for --all.
> |     Its result lines ARE read back and counted.
> |   * restore / re-pick / drop go through `run-shell -b` -- detached, stdout
> |     unreadable -- so the TUI observes the outcome by POLLING the store record
> |     and interpreting it with `agent_sessions.restore_verdict` /
> |     `drop_verdict` (new in this task; the frozenagent viewer now uses the same
> |     two functions). If you assert on a TUI's notification text, that is where
> |     it comes from.
> |   * `k` on a frozen row shells out to `aitask_frozen.sh drop <id>`, NOT
> |     `kill_agent_pane_smart`. The latter's store write is unleased and would
> |     delete the record out from under an in-flight restore.
> | 
> | NEW ENGINE SURFACE you may want:
> |   `aitask_frozen.sh freeze --all --dry-run` -> `WOULD_FREEZE:<pane>|<session>|
> |   <window>` per pane, then `FREEZE_ELIGIBLE:<n>`. Non-destructive by design.
> |   Also: `agent_freeze.main()` now validates the FULL freeze grammar before
> |   enumerating or mutating. It previously dispatched on its first argument and
> |   ignored the rest, so `freeze --all --dry-rnu` was a real freeze of every
> |   agent on the machine. If any fixture of yours passes extra arguments to
> |   `freeze`, it now gets exit 2 instead of silently freezing.
> | 
> | WHAT IS UNPROVEN, i.e. your job:
> |   Nothing here has been exercised against a real tmux server. This session ran
> |   INSIDE the `ait` server, so every live suite was off-limits. The keys are
> |   proven only at the argv level against fake seams -- the call SHAPE, never the
> |   outcome. `tests/test_cleanup_rule_parity.sh` is also still unrun (it refuses
> |   while the `-L ait` server has panes); t1705_11 tracks that separately.
> | 
> | Advisory only -- verify against the tree before relying on any of it.

> **✉ note:t1705_7** id=2026-09-09T13:31:24Z.44ef090a02d2e92df077e229 from=t1705_7 from_verified=yes at=2026-09-09T13:31:24Z base=d822b650a2362b82356f64ff1e5292ef2556f0f4 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | Second review round on t1705_7 changed four things that affect live acceptance.
> | Advisory only — verify against the tree, not against this note.
> | 
> | 1. **The frozen drop confirmation is no longer a "Freeze" button.** `k` on a
> |    frozen row opens `FreezeConfirmDialog` with `confirm_label="Drop"` and
> |    `destructive=True` (error-variant button, error border and header). The
> |    affirmative button id changed from `btn-freeze` to `btn-confirm`. Any
> |    acceptance step that clicks or names the old label/id will miss.
> | 
> | 2. **The dialog was resized for the minimonitor's 40-column host.** It was
> |    `width: 70%; min-width: 28` with Textual's default `Button` `min-width: 16`,
> |    which put Cancel's region at x=27..43 on a 40-column screen — past the
> |    dialog's own clip at x=34. A real centre click returned False and dismissed
> |    nothing; Escape was the only exit. Now `width: 90%; max-width: 60;
> |    min-width: 24` with per-button `min-width: 10`.
> | 
> |    Gotcha if you write click tests: `pilot.click(selector)`'s default offset is
> |    `(0, 0)` — the widget's TOP-LEFT, not its centre — and a clipped button keeps
> |    its top-left, so a default click passes against a broken layout. Pass an
> |    explicit centre offset computed from `widget.region`.
> | 
> | 3. **`freeze --all --dry-run` exists** and is what the `Z` confirmation's count
> |    comes from. It prints `WOULD_FREEZE:<pane>|<session>|<window>` per pane then
> |    `FREEZE_ELIGIBLE:<n>`, and mutates nothing. The wrapper's `freeze` arity gate
> |    was relaxed to `-ge 2` and `agent_freeze.main()` now validates the full
> |    grammar before any enumeration — every other form exits 2 having called
> |    neither mutator.
> | 
> | 4. **The restore watch deadline is now configuration-derived.**
> |    `monitor_shared._poll_frozen_outcome` was hardcoded to 40s and ignored
> |    `frozen.restore_ack_grace`; it now calls the new
> |    `agent_frozen_ops.restore_settle_timeout(root, *, dispatch_grace)`, read from
> |    the RECORD's root rather than the app's. At the default grace it still
> |    returns exactly 40.0, so default-config acceptance is unchanged — but if you
> |    test with a raised grace, the monitor now waits it out instead of reporting a
> |    stall.
> | 
> |    The `frozenagent` viewer still has the old hardcoded deadline
> |    (`frozenagent_app.py:877`); filed as t1766, not fixed here.
> | 
> | Everything above is proven at unit/render level only. Nothing in t1705_7 was
> | verified against a real tmux server — that session ran inside the `ait` server,
> | so the keys are proven at the argv level against fake seams: the call shape,
> | never the outcome. That gap is yours by design.

> **👁 note:read** id=2026-09-09T13:58:45Z.e8edcf54bd879962b3823291 by=t1705_8 at=2026-09-09T13:58:45Z mode=explicit ids=2026-09-09T10:08:51Z.b5cedc44c2d9da006f95e3fe,2026-09-09T13:31:24Z.44ef090a02d2e92df077e229

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-09T16:31:09Z status=pass attempt=1 type=human
>
> Note: deferred
