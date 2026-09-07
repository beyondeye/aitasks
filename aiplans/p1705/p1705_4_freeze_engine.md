---
Task: t1705_4_freeze_engine.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_1_*.md … aitasks/t1705/t1705_3_*.md, aitasks/t1705/t1705_5_*.md … aitasks/t1705/t1705_10_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-07 16:42
---

# t1705_4 — Freeze engine

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

**What the gate does and does not cover.** It blocks **implementation and every
live suite**. A read-only plan-time verification pass (reading files, checking
line anchors, re-deriving risk) is not what the gate protects against and may run
from anywhere — but it produces **no live evidence**, and a plan verified that way
must say so rather than let a later reader mistake design approval for a green
suite. See "Execution context of the 2026-09-07 pass" below.

### Execution context of the 2026-09-07 pass — READ BEFORE IMPLEMENTING

This plan's verification pass ran **from inside tmux** (`-L ait`, pane `%9`,
window `agent-pick-1705_4`; the server also held `monitor`, `board` and this
window's companion). Step 0 therefore returned **`PREFLIGHT_BLOCKED`** on both
checks. Consequences, stated plainly so the next session does not have to
reconstruct them:

- **No suite in `## Verification` was executed.** Not the live ones, not
  `run_all_python_tests.sh`. Every verification claim in this plan is a
  *specification*, not a result.
- The pass was **read-only**: no product file, test file or task file was
  modified by it. The corrections below come from reading the tree, not from
  running it.
- The approval this plan carries is a **design approval only**. The
  `plan_verified` entry appended by this pass and any `plan_approved_at` marker
  on the task record the same limited claim.
- **The implementing session MUST re-run Step 0 first, from a shell outside
  tmux with the `-L ait` server idle**, and must not begin work until it
  returns `PREFLIGHT_OK` on both lines. Under `plan_preference_child: verify`
  a re-pick within 24 h will see this pass's fresh entry and resolve
  `DECISION:SKIP` — that skips *plan re-verification*, it does **not** skip
  Step 0, which is part of the task body and runs regardless.

## Context

The freeze transaction and the reconcile pass (PINNED §C at the end of this
file), the list-panes format extension (§B), the cleanup contract, and
Freeze-All. Driven through `aitask_agent_sessions.sh` (t1705_2, landed). The
stand-in viewer command lands in t1705_6; here `standin_command()` is honoured
as an opaque string and tests point it at a stub via
`AITASKS_FROZEN_STANDIN_CMD`.

**The stand-in hazard is resolved, and it is NOT what the task body assumed.**
t1705_1 measured it (parent plan §"Spike findings", line 621): `respawn-pane -k`
**does not fire `pane-died` at all** — window, companion pane and the agent's own
pane id all survive, and this is a controlled result (the same fixture *does*
fire `pane-died` and collapse the window when the agent process really dies,
Case 1c). So:

- The freeze swap may use a plain `respawn-pane -k`; the cleanup abstention is
  **not** load-bearing for the freeze itself — it is belt-and-braces.
- The `@aitask_frozen` stamp is still required, for two other reasons:
  **classification** (monitor/minimonitor must recognise a frozen stand-in) and
  the **sibling-count rule** (a frozen stand-in dying, or a live sibling dying
  beside one, still routes through `pane-died`).
- Implement the abstention anyway and pin it with the parity test — but do not
  repeat the task body's claim that freezing without it destroys the window.

**Tmux-stress** — implement and verify from a shell outside the `-L ait`
server. **Rebase on t1699** (`kill_smart_live_fixture_orders_companion_last`,
verified still `status: Implementing` on 2026-09-07) before touching
`tests/test_kill_agent_pane_smart.sh`.

## Verification pass (2026-09-07) — what changed in this plan

Re-verified against the tree after t1705_2 and t1705_3 landed. Four substantive
corrections; the rest of the plan stood.

1. **`_LIST_PANES_ARITIES` is a CLOSED set and the original plan never
   mentioned it.** `monitor_core.py:2138` reads `_LIST_PANES_ARITIES = (9, 10,
   11)` and `:2164` drops any record whose field count is outside it. Appending
   four fields makes arity 15 → **every pane record would be silently dropped**,
   blanking every agent list in monitor, minimonitor and board. This is the
   single highest-impact defect found. The set must be extended in the same
   change, and `tests/test_monitor_companion_filter.py::ArityToleranceTests`
   (:477-511) updated with it.
2. **The pre-phase characterization test's premise was factually wrong.** It
   specified asserting that "a row with one extra trailing tab-field leaves the
   11 known fields unchanged (appending is safe)". The opposite is true and is
   already pinned: `test_over_and_under_length_rows_are_rejected` (:505) asserts
   *"a 12-field record must be rejected, not truncated"*. Appending is safe
   **only together with** the arity-set extension. The test is rewritten below to
   pin the real contract.
3. **No seam for `stale_op_grace`.** `STALE_OP_GRACE_DEFAULT = 60.0`
   (`agent_sessions.py:73`) is read directly at `:617` with no override, so the
   live lease-takeover races the plan specifies could not run in reasonable
   time. **Decision: add `AITASKS_STALE_OP_GRACE`** to `lib/agent_sessions.py`,
   honoured only under `AITASKS_TEST_MODE=1` (new step 4a).
4. **`count_other_real_agents` is deliberately pure and import-free** (:896-912
   — it takes `(pane_id, is_helper)` pairs and the *caller* classifies). The
   original wording ("records gain an `is_frozen` flag") would change that
   contract needlessly. Correction: leave the function's signature alone; the
   change is in the caller. Note also that "a frozen pane counts as real"
   already holds **incidentally** today (a stand-in carries neither the shadow
   marker nor `@aitask_monitor_kind`), so the load-bearing halves are the
   **abstention** and `kill_agent_pane_smart`'s drop-then-kill — the parity test
   is what converts the incidental half into a pinned one.

5. **The live crash-test sequence described an impossible scenario.** It read
   "coordinator `SIGKILL`ed → reconcile takes over → the resumed coordinator's
   `freeze-commit` gets `NONCE_MISMATCH`". Neither half survives contact with
   the code: a killed coordinator cannot resume to issue any verb, and a
   `SIGSTOP`ped one is **alive** to `_pid_alive` (:317-330, fail-closed —
   only `ESRCH` proves death), so `_lease_stale` (:604-618) refuses takeover for
   a paused owner regardless of elapsed grace. Rewritten as three independent
   cases (a)/(b)/(c) in `## Live tests`, with the stale-nonce assertion driven
   directly against the store instead of via a resurrected process. **This also
   strengthens coverage**: case (a) now asserts refusal *past* the grace, which
   is the only assertion that actually pins the `and` in `_lease_stale`.
6. **The replacement stale-nonce case was itself wrong, and is now a unit
   test.** The first rewrite put it in the live suite, committing with the dead
   coordinator's nonce after case (b). But (b) ends in `freeze-abort`, so the
   record is `live`, and `freeze_commit` validates **state before nonce**
   (`_require_state` :917 → `_require_nonce` :918): the call returns
   `TRANSITION_REFUSED:<id>|live|freeze-commit` (exit 5) and never reaches the
   nonce guard, so it would have proven nothing about stale-nonce safety. Moved
   to `tests/test_agent_freeze.py`, where `lease_take`'s injectable `now=` /
   `pid_alive=` (:1073-1088) produce a **`freezing`** record with a rotated
   nonce — the only state in which the nonce guard is reachable — plus a
   negative control asserting the `live` case raises `TransitionRefused`
   instead. A live `NONCE_MISMATCH` is unreachable for a correct coordinator;
   see the rationale in `## Live tests`.
7. **`reconcile()`'s per-session pass had no `-t` target.** Step 5 said "for
   every session, one `list-panes -s`" — but untargeted, `list-panes -s`
   resolves to the *current* session, and reconcile runs detached where that is
   arbitrary or absent, so the loop would enumerate one session N times. The
   established call sites all pass `-t tmux_session_target(session)`
   (`agent_launch_utils.py:881`, `:914`, `:1424`); step 5 now does too. The
   consequence is **data loss, not just missed repair**: `purge` drops a `live`
   record whose root is in `observed.roots` but whose window was not observed
   (`agent_sessions.py:1176-1178` → `dead_window`), so a `ROOT` row written for
   an unenumerated root deletes every live record in every other project. Step 5
   gains a fail-closed rule (emit `ROOT` only on `rc == 0`, else `INCOMPLETE`)
   and the two-session live test now asserts two **distinct** `-t` targets plus
   a forced-enumeration-failure case proving the other session's records
   survive.
8. **Freeze-All's selection would have destroyed every companion minimonitor.**
   Step 7 selected on `classify_pane == AGENT`, but `classify_pane`
   (:2048-2056) reads **only the window name** — so the companion minimonitor
   sitting in the agent's own `agent-*` window qualifies, and Freeze-All would
   have `respawn-pane -k`'d it into a stand-in viewer. Companion exclusion is a
   separate two-rung identity check (`_is_companion_pane`, :2058) applied after
   classification inside `_parse_list_panes`. Selection now goes through
   `TmuxMonitor.discover_panes()` (:2305-2313), the documented agent-facing
   contract, which applies both the shadow and companion filters and carries the
   right `-t` target. Same window-name-vs-process-identity confusion as
   t1382/t1686. A companion fixture with a `pane_pid`-based assertion and a
   negative control is added to the live suite.
9. **This pass could not run anything.** Step 0 returned `PREFLIGHT_BLOCKED`
   (inside tmux). Recorded in full under "Execution context of the 2026-09-07
   pass" above; the short form is that every claim in `## Verification` is
   unexecuted and the implementing session owes Step 0 and the whole suite.

Also confirmed as already landed by t1705_2, so **not** in this task's scope:
the store's `PANE`-row parsing and `dead_pane` purge rule
(`agent_sessions.py:1117-1190`) and the marks reader's explicit `PANE` skip
(`agent_marks.py:587-607`). Scope decision: `_write_observation_file(panes=)`
wiring stays with **t1705_7**; this task adds only the
`last_discovered_panes()` accessor plus reconcile's own observation file.

Line-number drift corrected below (`_LIST_PANES_FORMAT` is :2120-2132, not
:2124-2127; `TmuxPaneInfo` :915; `maybe_spawn_minimonitor` occupancy pass
:1723-1725; `kill_agent_pane_smart` format :3237-3240). Note that
`tests/test_multi_agent_window_substrate.sh:386` is a **stale comment**
("9 fields incl. @aitask_shadow_target"), not an assertion — fix the comment,
there is no arity pin to update there.

## Files

- **New** `.aitask-scripts/lib/agent_freeze.py`, `.aitask-scripts/aitask_frozen.sh`
- **New tests** `tests/test_list_panes_arity_characterization.py` (pre-phase),
  `tests/test_freeze_engine_live.sh`, `tests/test_cleanup_rule_parity.sh`
  (post-phase), `tests/test_agent_freeze.py` (unit, fake `TmuxClient` + fake
  wrapper), `tests/lib/fake_standin.sh`
- **Edit** `.aitask-scripts/monitor/monitor_core.py` — option constants beside
  `SHADOW_TARGET_OPTION` (:385), `_LIST_PANES_FORMAT` (:2120-2132),
  **`_LIST_PANES_ARITIES` (:2138)**, parser (:2140-2183), `TmuxPaneInfo`
  (:915-937), `last_discovered_panes()` beside `last_discovered_agents()`
  (:1878) recorded in `_record_discovery_facts` (:1829),
  `kill_agent_pane_smart` (:3220-3277, its own format :3237-3240)
- **Edit** `.aitask-scripts/lib/agent_sessions.py` — `AITASKS_STALE_OP_GRACE`
  test seam (:73, :617) only
- **Edit** `.aitask-scripts/aitask_companion_cleanup.sh` (:46-47, :78-79)
- **Edit** `.aitask-scripts/lib/agent_launch_utils.py` `maybe_spawn_minimonitor`
  occupancy (:1723-1725)
- **Edit** arity pins: `tests/test_monitor_companion_filter.py` (:104-106 row
  builder, :477-511 `ArityToleranceTests`),
  `tests/test_agent_marks_generation.py` (:159-160 `_FIELDS`, :164-168 `_row`);
  **comment only** `tests/test_multi_agent_window_substrate.sh:386`
- **Edit** `lib/agent_sessions.py` constant-parity test (from t1705_2) to import
  the `monitor_core` spellings

## Implementation steps

### Pre-phase (risk mitigations)

1. `[characterize_list_panes_arity]` Write
   `tests/test_list_panes_arity_characterization.py` against the **unmodified**
   `monitor_core.py`. It pins the *real* contract, which is stricter than the
   original plan assumed:
   - a row built from the real `_LIST_PANES_FORMAT` (11 fields, last is
     `@aitask_monitor_kind`) parses and every field lands;
   - a row with one extra **trailing** tab-field (12) is **dropped whole** —
     appending is NOT transparently safe; it is safe only when
     `_LIST_PANES_ARITIES` is extended in the same change. Assert the empty
     result and name the arity set in the failure message;
   - a field **inserted** before `history_size` at the same arity (11) parses
     but yields the *wrong* `history_size` — the silent field shift the append
     rule exists to prevent. This is the negative control: it demonstrates the
     hazard, it is not a "good" outcome;
   - a trailing empty `@option` still yields 11 fields (t1686's `strip()`
     regression).

   Commit it green against unmodified `monitor_core.py` before step 2. After
   step 2 it must be updated in the same commit as the format change — the
   12-field case becomes a 16-field case and the 11-field case becomes 15.

### Main body

2. **Constants + format + the arity set.** In `monitor_core.py` beside
   `SHADOW_TARGET_OPTION` (:385): `RECORD_OPTION = "@aitask_record"`,
   `FROZEN_OPTION = "@aitask_frozen"`,
   `STANDIN_READY_OPTION = "@aitask_standin_ready"`,
   `AGENT_SESSION_OPTION = "@aitask_agent_session"`. **Append** to
   `_LIST_PANES_FORMAT`, in this order: `#{@aitask_frozen}`,
   `#{@aitask_record}`, `#{@aitask_standin_ready}`, `#{pane_dead}` → parts
   `[11]`, `[12]`, `[13]`, `[14]`, arity 11 → 15.

   **Then extend `_LIST_PANES_ARITIES` to `(9, 10, 11, 15)`** — without this the
   append is a silent total failure (see Verification pass §1). Keep the set
   closed and keep the legacy arities for older stubs; do **not** widen it to a
   range. Extend the docstring comment to say that 15 is current and 11/10/9 are
   legacy.

   Extend the parser (:2166-2183) with `len(parts) > N` guards matching the
   existing `history_size` / `monitor_kind` style, and `TmuxPaneInfo`
   (:915-937) with `frozen_record: str = ""`, `record_id: str = ""`,
   `standin_ready: str = ""`, `pane_dead: bool = False`. Populate them on
   **both** construction sites in `_parse_list_panes` (the shadow branch and the
   agent branch) — the shadow branch is easy to miss.

   Do the same append to the `kill_agent_pane_smart` format (:3237-3240 → add
   `\t#{@aitask_frozen}`), `aitask_companion_cleanup.sh` (:47, :79 →
   `|#{@aitask_frozen}`, keep `IFS='|'` — it is what preserves empty fields),
   and `maybe_spawn_minimonitor` (:1725). Each of these three has its **own**
   ad-hoc format and its own implicit arity; they do not share
   `_LIST_PANES_ARITIES`, so each needs its own field-count review.

   Update the arity pins with a comment naming t1705_4:
   `test_monitor_companion_filter.py` (:104-106 builder → 15 fields; :477-511
   `ArityToleranceTests` → current arity 15, legacy 9/10/11 still parse,
   over-length case becomes 16), `test_agent_marks_generation.py` (:159-160
   `_FIELDS = 15`, `_row` :164-168 gains the four fields). Fix the stale
   "9 fields" comment at `test_multi_agent_window_substrate.sh:386`.

   Add
   `TmuxMonitor.last_discovered_panes() -> dict[(root, window), list[(pane_id, pane_pid, pane_dead)]]`
   beside `last_discovered_agents()` (:1878), recorded in
   `_record_discovery_facts` (:1829). It has **no consumer in this task** — the
   `_write_observation_file(panes=)` wiring is t1705_7's. Say so in its
   docstring so it does not read as dead code.

3. **Cleanup contract.** `count_other_real_agents` (:896-912) keeps its pure
   `(pane_id, is_helper)` signature — **do not add a flag to it**. The change is
   in `kill_agent_pane_smart` (:3220-3277), which computes `is_helper`: a
   `@aitask_frozen`-stamped pane is **never** a helper. If the *target* pane is
   itself frozen, run `aitask_agent_sessions.sh drop <id>` first (removes
   captures), then apply the existing kill-by-sibling rule unchanged.

   `aitask_companion_cleanup.sh`: read `#{@aitask_frozen}` of `$primary` in the
   existing single window-scoped `list-panes` pass (:78-79); if non-empty →
   `exit 0` **before** any kill (abstain: the pane is being respawned, not
   departing). In the sibling loop a stamped pane counts toward `others`.

   Docstring both sites: "must agree with the other — pinned by
   `tests/test_cleanup_rule_parity.sh`". Note in the comment that the
   "counts as real" half currently holds incidentally (a stand-in carries no
   helper marker) and that the test is what keeps it true.

4. **`lib/agent_freeze.py`.**
   ```python
   _TMUX = TmuxClient()
   SESSIONS_SH = Path(__file__).resolve().parent.parent / "aitask_agent_sessions.sh"
   @dataclass class FreezeResult: record_id: str; ok: bool; stage: str; line: str
   def _store(*argv, timeout=20) -> (rc, out)   # subprocess.run of SESSIONS_SH, never raises (OSError → (1, "ERROR:…"))
   def _pane_facts(pane_id) -> dict            # one display-message: session_name, window_name, pane_id, pane_pid, pane_dead, @aitask_record, @aitask_frozen, @aitask_standin_ready, @aitask_agent_session
   def _capture(pane_id, cap) -> (ansi_path, txt_path, lines)   # capture-pane -p -e -J -S -<cap>; ansi_utils.strip_ansi → .txt; 0600 files in capture_dir(id) (0700)
   def freeze_pane(pane_id, *, cap=None) -> FreezeResult
   def freeze_all() -> list[FreezeResult]
   def reconcile() -> list[str]
   ```
   All tmux goes through `TmuxClient` (`lib/tmux_exec.py` — `run` / `spawn`);
   all store writes through the shell wrapper, never by importing the store's
   mutators. `freeze_pane` implements §C 1–6 literally, with `_fail_at(stage)`
   raising under `AITASKS_TEST_MODE=1` when `AITASKS_FREEZE_FAIL_AT == stage`,
   and `_pause_at(stage)` doing `os.kill(os.getpid(), SIGSTOP)` when
   `AITASKS_FROZEN_PAUSE_AT == stage`.

   Rollback per stage exactly as §C: stages `capture|begin` → remove temp files;
   `stamp` → `freeze-abort --nonce`; `respawn` → `set-option -pu` both options +
   `freeze-abort --nonce`; `commit` failure with `LOCK_BUSY` → leave `freezing`
   (reconcile finishes); `NONCE_MISMATCH` → return `FreezeResult(ok=False,
   stage="commit", line=out)` **without touching the pane**.

   The record is resolved before capture: `@aitask_record` → `show`; else
   `upsert --root <realpath of pane_current_path walk-up> --window --pane
   --pane-pid --agent-string "" --session-id <@aitask_agent_session or
   newest_transcript_for()>`, then `ait_stamp_record` per amendment A8. Pass
   `--owner-pid` on `freeze-begin` / `lease-take` per amendment A7 — the
   **coordinator's** pid, never a subshell's `$$`.

   Cap from `project_config.yaml` `frozen.capture_max_lines` (default 50000)
   read via `config_utils.load_yaml_config(path, defaults)` — do not hand-parse
   YAML. There is no `frozen:` section in the shipped
   `aitasks/metadata/project_config.yaml`, so the default is the normal path;
   do not add the section.

4a. **`AITASKS_STALE_OP_GRACE` test seam** (`lib/agent_sessions.py`). There is
   exactly **one** call site: `_lease_stale()` (:604-618) reads
   `STALE_OP_GRACE_DEFAULT` directly at :617. Replace that read with a
   `_stale_op_grace()` helper returning the env value (positive float) **only**
   when `AITASKS_TEST_MODE=1`, else `STALE_OP_GRACE_DEFAULT`. Gate on the test
   mode exactly as `agent_freeze`'s own seams are gated, so production can never
   be reconfigured by a stray env var. Document it beside the other seams in
   §C's failure-injection list.

   **Do not touch the liveness half.** `_lease_stale` is
   `grace elapsed AND owner dead`, and `_pid_alive` (:317-330) is fail-closed —
   only `ESRCH` proves death, `EPERM` counts as alive. That conjunction is what
   makes case (a) below refuse takeover from a *paused* coordinator forever;
   shortening the grace must not become a way to seize a live owner. Note
   `_lease_stale` already takes an injectable `pid_alive=` — use it for the
   **unit** tests; the live tests need the env seam because they cross a
   process boundary.

5. **`reconcile()`** — for every `discover_aitasks_sessions()` session, one
   **explicitly targeted** pass:

   ```python
   rc, out = _TMUX.run(["list-panes", "-s",
                        "-t", tmux_session_target(session.session),   # NOT optional
                        "-F", _RECONCILE_FORMAT])
   ```

   **`-t` is load-bearing, and omitting it corrupts the store rather than merely
   under-reporting.** `list-panes -s` with no target resolves to the *current*
   session, so the loop would enumerate the same session on every iteration —
   and reconcile runs **detached** (`run-shell -b`, or a plain shell with no
   attached client), where "current" is arbitrary or absent. The damage is not
   confined to missed repairs: `purge` drops any `live` record whose root is in
   `observed.roots` but whose window is not in that root's observed windows
   (`agent_sessions.py:1176-1178` → `dead_window`). Emitting a `ROOT` row for a
   root you did not actually enumerate therefore makes **every live record in
   every other project look dead and get dropped**. Use
   `tmux_session_target()` from `lib/agent_launch_utils.py:46`, the same helper
   the established call sites use (`:881`, `:914`, `:1424`).

   **Fail-closed rule that makes the above unreachable even if targeting
   regresses:** emit a `ROOT` row for a root **only** when that session's
   targeted `list-panes` returned `rc == 0`. On any non-zero rc, omit the root's
   `ROOT` row and write `INCOMPLETE`. A root that was never successfully
   enumerated must never be presented to `purge` as successfully enumerated —
   the observation file's `ROOT` row is an *assertion of coverage*, not a list of
   roots you intended to visit.

   Build the observation file (`ROOT`/`WINDOW`/`PANE`/`INCOMPLETE`) via
   `tempfile.mkstemp`; for every non-`live` record apply the §C
   table **only after** `lease-take` succeeds (skip on `LEASE_HELD`). The
   indeterminate rows **return without a verb** — pin that. Every stand-in
   respawn is `set-option -pu @aitask_standin_ready` → `respawn-pane -k` →
   `standin-respawned --nonce --pane --pane-pid`. End with
   `purge --observed <file>` — the store already parses `PANE` rows and applies
   the `dead_pane` rule (t1705_2, `agent_sessions.py:1117-1190`), so nothing is
   owed on the consumer side. Returns the wire lines it produced. Must be safe
   to call every 600 s (t1705_7 dispatches it from the maintenance tick).

6. **`aitask_frozen.sh`** — `freeze <pane_id>`, `freeze --all`, `reconcile`
   (`restore` arrives in t1705_5): `require_ait_python` (from
   `lib/python_resolve.sh:102`), exec `python3 lib/agent_freeze.py <verb> …`;
   prints the wire lines; exit 0 when every result `ok`, else 1. Header: not
   skill-invoked, no allow-list entries, no `ait` dispatcher case. It issues no
   raw tmux itself, so `tests/test_no_raw_tmux.sh` needs no allowlist entry —
   `aitask_companion_cleanup.sh` is already allowlisted (:52, "raw by design").

7. **Freeze-All** — selection goes through **`TmuxMonitor.discover_panes()`**
   (one monitor per `discover_aitasks_sessions()` session, or `multi_session`
   mode), then filters `category == PaneCategory.AGENT` and
   `frozen_record == ""`. Freezes sequentially (each freeze is one respawn —
   parallel respawns are not worth the tmux churn); returns every result and
   never aborts the batch.

   **Never hand-roll `list-panes` + `classify_pane` here.** `classify_pane`
   (:2048-2056) inspects **only the window name**, so *every* pane in an
   `agent-*` window classifies as `AGENT` — including the companion minimonitor
   that `maybe_spawn_minimonitor` puts there, and including a `TUI`-named pane
   split into an agent window. Companion exclusion is a **separate** two-rung
   check, `_is_companion_pane` (:2058) — the pane's own `@aitask_monitor_kind`
   marker first, cmdline identity second — applied inside `_parse_list_panes`,
   *after* `classify_pane`. A category-only selection would therefore
   `respawn-pane -k` the companion of every agent it froze, destroying the exact
   pane the freeze design goes out of its way to keep alive. This is the same
   window-name-vs-process-identity confusion t1382/t1686 fixed in the monitor;
   do not reintroduce it. `discover_panes()` is documented as the "agent-facing
   panes only (shadow companions excluded)" contract "every non-shadow consumer
   relies on" (:2305-2307) — Freeze-All is such a consumer, and using it also
   inherits the correct `-t tmux_session_target()` targeting (:2311).

   **This is deliberately NOT how `reconcile()` enumerates.** Step 5 keeps its
   own raw targeted pass precisely because the observation protocol needs
   **every** pane of the window — companions, stand-ins and dead panes included
   — to emit complete `PANE` rows. The two passes have opposite requirements:
   reconcile must see everything; Freeze-All must never act on a helper. Do not
   "unify" them.

### Post-phase (risk mitigations)

8. `[cleanup_rule_parity_test]` `tests/test_cleanup_rule_parity.sh` (isolated
   tmux, `require_clean_ait_server`): a table of windows — `[agent, agent]`,
   `[agent, frozen]`, `[frozen, companion]`, `[agent, shadow, companion]`,
   `[frozen, frozen]`, `[agent(dead), frozen]`, each with the dying pane at
   every index. For each row: build the window (stub processes, stamp options),
   run `aitask_companion_cleanup.sh <dying> <companion>` with
   `tmux kill-pane`/`kill-window` replaced by a logging wrapper on `PATH`, and
   compute the same decision through `count_other_real_agents` via a
   `python3 -c`; assert the script's kill decision (window / pane / **abstain**)
   equals the Python rule's. Include a negative control: patch one side and
   prove the test fails.

## Live tests — `tests/test_freeze_engine_live.sh`

Isolated server; `AITASKS_FROZEN_STANDIN_CMD="tests/lib/fake_standin.sh"` (new
helper: stamps `@aitask_standin_ready=<id>` on `$TMUX_PANE` then sleeps;
`FAKE_STANDIN_NO_STAMP=1` skips the stamp to model a booting/broken viewer).
Run the lease-takeover cases with `AITASKS_TEST_MODE=1
AITASKS_STALE_OP_GRACE=1` (step 4a) so they complete in seconds.

Cases: happy freeze (record `frozen`, capture files 0600 with the right line
count, companion alive, options set, `standin_pid == #{pane_pid}`); each
`AITASKS_FREEZE_FAIL_AT` stage → agent still running, no stamp, record `live`,
no capture dir.

**The three lease-contention cases are separate, and must not be written as one
narrative.** The original plan collapsed them into "coordinator SIGKILLed →
reconcile takes over → the resumed coordinator's `freeze-commit` gets
`NONCE_MISMATCH`", which cannot happen: a `SIGKILL`ed coordinator never resumes
to issue any verb, and a `SIGSTOP`ped one is **alive** — `_pid_alive`
(`agent_sessions.py:317-330`) is fail-closed and only `ESRCH` proves death, so
`_lease_stale` (:604-618) returns `False` for a paused owner *no matter how much
grace has elapsed*, and takeover is refused indefinitely. Split into:

- **(a) Paused owner keeps its lease.** `AITASKS_FROZEN_PAUSE_AT=begin` →
  coordinator `SIGSTOP`s itself holding the lease. Run `reconcile` concurrently:
  it must report `LEASE_HELD` and leave the record untouched. Then sleep **past**
  `AITASKS_STALE_OP_GRACE` and run `reconcile` **again** — it must *still* refuse.
  That second assertion is the load-bearing one: it pins the `and` in
  `_lease_stale`, and it is what a grace-only implementation would fail.
  `SIGCONT` → the coordinator finishes its own freeze, `freeze-commit` succeeds
  with its own nonce, record `frozen`.
- **(b) Dead owner is taken over.** `SIGKILL` the coordinator between stamp and
  respawn (`AITASKS_FROZEN_PAUSE_AT=stamp`, then kill it). Sleep past the grace,
  run `reconcile`: `lease-take` now succeeds (grace elapsed **and** owner dead)
  and the §C row "agent alive, stand-in not up" applies → both options unstamped,
  `freeze-abort`, record back to `live`, captures deleted, **agent still
  running**. Capture the *new* nonce that `lease-take` minted.
- **(c) Stale nonce — NOT a live case. Moved to unit level; see
  `tests/test_agent_freeze.py` below.** Asserting it here would be worse than
  omitting it: case (b) ends in `freeze-abort`, so the record is `live`, and
  `freeze_commit` checks **state before nonce** (`_require_state` :917, then
  `_require_nonce` :918). A stale-nonce commit at that point returns
  `TRANSITION_REFUSED:<id>|live|freeze-commit` (exit 5) and never reaches the
  nonce check at all — a test that passed would be pinning the wrong guard.

**Stale-nonce safety — unit test in `tests/test_agent_freeze.py`.** Drive the
store's Python API directly; it needs no processes, no sleeping and no env seam,
because `lease_take` (:1073-1088) accepts injectable `now=` and `pid_alive=`, and
`_mint_lease` rewrites only the lease fields — **the record stays `freezing`**,
which is the state `freeze_commit` requires:

```python
sf, _  = freeze_begin(sf, rid, ...)                      # freezing, nonce N1, owner P
sf, ln = lease_take(sf, rid, owner_pid=999,
                    now=t0 + STALE_OP_GRACE_DEFAULT + 1,
                    pid_alive=lambda _pid: False)        # LEASED:<id>|N2, still freezing
before = copy.deepcopy(sf.by_id(rid))
with self.assertRaises(NonceMismatch):                   # → NONCE_MISMATCH:<id>, exit 6
    freeze_commit(sf, rid, nonce=N1, pane="%1", pane_pid=123)
self.assertEqual(sf.by_id(rid), before)                  # byte-identical: nothing written
```

Pair it with the negative control that motivated the move: with the record back
in `live`, the same call raises `TransitionRefused`, **not** `NonceMismatch` —
so the two guards are pinned as distinct rather than conflated.

**Why this cannot be a live test at all.** For a correctly-implemented
coordinator a live `NONCE_MISMATCH` at commit is **unreachable by construction**:
`_lease_stale` requires the owner to be dead, and a dead coordinator issues no
further verbs. The one path that does reach it is the **A7 anti-pattern** —
recording an ephemeral subshell's `$$` as `op_owner_pid`, so the owner reads as
dead while the real coordinator runs on, reconcile seizes the lease, and the
coordinator's commit is refused. That is a real regression worth a live test one
day, but it needs a seam to inject a bogus owner pid; it is **not** built here.
Treat `agent_freeze.py`'s `NONCE_MISMATCH` branch as defensive, and keep A7's
"pass the coordinator's pid" rule as the thing that actually prevents it.

Remaining cases: coordinator killed after the respawn with the stand-in up →
reconcile `freeze-commit`s; stand-in without stamp
(`FAKE_STANDIN_NO_STAMP=1`) → indeterminate, **no transition** (assert state
unchanged after two passes); `kill -9` the stand-in → `pane_dead=1` → reconcile
respawns it; `kill-window` while `freezing` → `freeze-commit --pane "" --pane-pid 0`;
`kill_agent_pane_smart` on a frozen pane → record dropped, captures removed,
sibling rule honoured.

**Freeze-All must not touch helpers — fixture with a companion.** Build one
`agent-pick-<n>` window holding a live agent **and** a companion minimonitor
(marker `@aitask_monitor_kind` set, its recorded pid alive), plus a shadow pane
in a second row of the table. Run Freeze-All and assert:

- the agent's pane was respawned into the stand-in (record `frozen`,
  `@aitask_frozen` stamped);
- the companion's `pane_id` **and** `#{pane_pid}` are **unchanged**, its
  `@aitask_monitor_kind` marker still live, and no store record was created for
  it;
- the shadow pane is likewise untouched;
- exactly **one** `FreezeResult` came back for that window.

The pid assertion is the one that matters: `respawn-pane -k` preserves the pane
id, so checking the id alone would pass even if the companion had been respawned
into a stand-in. Include the negative control — select by
`classify_pane == AGENT` alone and prove the companion *is* respawned, so the
test is known to be able to fail.

**Two-session case — assert the targeting, not just the outcome.** Build two
isolated tmux sessions, each with its own project root and its own agent.
Freeze-All must freeze in **both**, and reconcile must observe and repair in
**both**. Because an untargeted `list-panes -s` silently returns whichever
session tmux considers current, a test that only checks aggregate outcomes can
pass while one session is enumerated twice. So assert both halves:

- **Calls:** with `TmuxClient` wrapped by a recording shim (or
  `AITASKS_TMUX_LOG=<file>` if a log seam is cheaper), assert exactly two
  `list-panes -s` invocations and that their `-t` arguments are the **two
  distinct** session targets. A run whose two calls carry the same target fails
  here even if every record happens to end up correct.
- **Outcomes:** a per-session assertion — session A's record repaired and
  session B's record repaired — never a combined count, which one session can
  satisfy alone.
- **Purge safety:** run reconcile with session B's enumeration forced to fail
  (kill its server, or point the target at a non-existent session) and assert
  that B's `live` records **survive** — no `dead_window` drops — and that the
  observation file carries `INCOMPLETE` and no `ROOT` row for B. This is the
  regression test for the fail-closed rule in step 5; without it the targeting
  bug's worst outcome (silent destruction of another project's live records) has
  no coverage at all.

## Verification

```bash
bash tests/run_all_python_tests.sh                       # characterization + unit + arity pins
bash tests/test_freeze_engine_live.sh                     # outside -L ait
bash tests/test_cleanup_rule_parity.sh                    # outside -L ait
bash tests/test_frozen_standin_spike.sh                   # control still green
bash tests/test_kill_agent_pane_smart.sh tests/test_multi_agent_window_substrate.sh tests/test_no_raw_tmux.sh tests/test_guard_live_tmux.sh
shellcheck .aitask-scripts/aitask_frozen.sh .aitask-scripts/aitask_companion_cleanup.sh
```

**Arity smoke — run this before trusting any green suite.** The format change's
failure mode is silent absence, and a stubbed unit test can pass vacuously while
live discovery returns nothing. With `ait ide` running, confirm `ait minimonitor`
still lists live agents:

```bash
python3 -c "import sys; sys.path.insert(0, '.aitask-scripts'); \
from monitor.monitor_core import TmuxMonitor; \
m = TmuxMonitor(session='aitasks'); print(len(m.discover_panes()))"
```

A zero here with agents on screen is the arity regression, not an empty server.

## Risk

### Code-health risk: high
- The `list-panes` format gains four fields across **four** call sites, each
  with its own ad-hoc format, plus a CLOSED arity set (`_LIST_PANES_ARITIES`)
  and three test pins. A missed site fails **silently by absence** — records are
  dropped whole, so monitor/minimonitor/board show no agents at all rather than
  erroring · severity: high · → mitigation: inline pre-phase
  characterize_list_panes_arity (rewritten this pass to pin the closed-set
  behaviour the original test would have mis-asserted), plus the arity smoke in
  `## Verification`
- The sibling/kill rule is duplicated between `aitask_companion_cleanup.sh`
  (bash) and `count_other_real_agents` (Python); a frozen-aware change to one
  without the other kills a window holding a live agent · severity: high · →
  mitigation: inline post-phase cleanup_rule_parity_test
- Pane **category** (window name) and pane **identity** (companion / shadow
  markers and process identity) are distinct in `monitor_core`, and every
  consumer that conflates them acts on helper panes; here that means Freeze-All
  respawning the companions it exists to preserve · severity: high · →
  mitigation: selection routed through `discover_panes()` rather than
  `classify_pane`, plus the companion fixture asserting an unchanged
  `#{pane_pid}` and its negative control
- `monitor_core.py` is the shared discovery core for monitor, minimonitor,
  board and applink; `TmuxPaneInfo` gains four fields populated at two
  construction sites in `_parse_list_panes`, and the shadow branch is easy to
  miss · severity: medium · → mitigation: inline pre-phase
  characterize_list_panes_arity (covers both branches)
- `reconcile()` feeds `purge`, whose `dead_window` rule **deletes** live records
  for any root it presents as enumerated; an enumeration bug (a missing `-t`, a
  failed pass still credited with a `ROOT` row) therefore destroys another
  project's records rather than merely under-reporting · severity: high · →
  mitigation: explicit `tmux_session_target()` in step 5, the fail-closed
  `ROOT`-only-on-`rc == 0` rule, and the two-session live test's
  distinct-targets assertion plus its forced-failure survival case
- The task edits a **landed sibling's** file (`lib/agent_sessions.py`, t1705_2)
  to add the `AITASKS_STALE_OP_GRACE` seam · severity: low · → mitigation: the
  seam is gated on `AITASKS_TEST_MODE=1`, so production behaviour is unchanged
  by construction

### Goal-achievement risk: high
- The freeze transaction spans several locked verbs and a detached coordinator;
  a concurrent `reconcile`, a crash between stamp and respawn, or a coordinator
  death after clearing the ready mark could double-act or mis-acknowledge ·
  severity: high · → mitigation: the lease/nonce contract, `@aitask_standin_ready`
  + `standin_pid` positive evidence and the persisted `last_error` channel in
  §A/§C, exercised by the paused-coordinator and killed-coordinator live cases
- The stand-in viewer does not exist until t1705_6, so the happy path is only
  ever exercised through the `AITASKS_FROZEN_STANDIN_CMD` stub; a real viewer
  that boots slowly or never stamps `@aitask_standin_ready` lands on the
  indeterminate row and would look like a hang · severity: medium · →
  mitigation: the `FAKE_STANDIN_NO_STAMP=1` case pins "indeterminate → no
  transition" explicitly, and t1705_8's acceptance test closes it end-to-end
- The reconcile table has three indeterminate rows that deliberately make no
  transition; if the grace or the re-check cadence is wrong a record can sit
  `freezing` indefinitely with the agent already gone · severity: medium · →
  mitigation: the two-pass "state unchanged" assertion, plus reconcile being
  idempotent and dispatched every 600 s from t1705_7
- Verification depends on a live isolated tmux server and cannot run from
  inside tmux, so the suite is easy to leave un-run · severity: medium · →
  mitigation: the blocking Step 0 preflight above, and `require_clean_ait_server`
  failing rather than skipping
- **This plan was verified from inside tmux, so nothing in `## Verification` has
  actually been executed**; a later session could mistake the design approval
  (and the fresh `plan_verified` entry, which suppresses re-verification for
  24 h) for evidence that the suite is green · severity: high · → mitigation:
  the "Execution context of the 2026-09-07 pass" block states the limitation at
  the top of the plan and spells out that `DECISION:SKIP` skips plan
  re-verification but never Step 0
- The lease contract's `grace AND owner-dead` conjunction is easy to test
  vacuously — a suite that only ever pauses the owner, or only ever kills it,
  proves half the rule while reading as if it proved both · severity: medium ·
  → mitigation: live cases (a)/(b), where (a)'s second `reconcile` **after** the
  grace is the assertion a grace-only implementation fails
- The store validates **state before nonce**, so a test aimed at the nonce guard
  can silently land on the state guard instead and pass while proving nothing —
  the failure mode is a green test, not a red one · severity: medium · →
  mitigation: the stale-nonce unit test runs against a still-`freezing` record
  (the only state where the nonce guard is reachable) and ships with a negative
  control asserting the `live` case raises `TransitionRefused` instead

### Planned mitigations
- timing: pre-phase | name: characterize_list_panes_arity | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: pinned list-panes arity + the CLOSED arity set | desc: characterization test pinning the current 11-field arity, that an appended 12th field is dropped whole (appending is safe only with the arity-set extension), the inserted-field shift as a negative control, and the trailing-empty-option case; run green before the format change and updated to 15/16 in the same commit as it — **priority raised from medium to high and the premise corrected during the 2026-09-07 verification pass**
- timing: post-phase | name: cleanup_rule_parity_test | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: duplicated sibling rule across bash and Python | desc: one pane-record table driven through `aitask_companion_cleanup.sh` (isolated tmux) and `count_other_real_agents`, asserting agreement for every frozen/live/helper combination and that a dying stamped pane makes the script abstain

## Amendments from t1705_2 (store implementation, 2026-09-06)

**A3 — `standin-respawned` is legal from `freezing`, and KEEPS the lease.** The
reconcile row "`freezing` / `@aitask_frozen==id`, pane dead → respawn the
stand-in (clear ready first), `standin-respawned`, then re-check" calls the verb
on a `freezing` record, which the original verb list did not admit. The store now
implements `freezing → freezing` with the lease retained (the freeze is still in
flight; the re-check then matches the "stand-in up" row and commits). Nothing
else about the row changes — but do not "fix" a `TRANSITION_REFUSED` here by
committing early: the retained lease is what makes the re-check safe.

**A7 — `freeze-begin` and `lease-take` REQUIRE `--owner-pid <pid>`.** Pass the
**coordinator's** pid — this detached `aitask_frozen.sh` process — never `$$` of
a subshell that exits when the verb returns. The wrapper rejects a missing or
non-positive value with exit 2 and has no fallback, deliberately: a defaulted
pid is dead immediately, which turns the lease's staleness test into a bare 60 s
timer and lets a later reconcile pass seize this coordinator's own in-flight
freeze. Note the freeze flow can easily exceed 60 s — spike finding 5b requires
letting the agent persist before respawning its pane. (A live owner is protected
regardless of duration: `lease-take` refuses while `op_owner_pid` is alive, not
only within the grace.)

**A8 — the freeze engine stamps `@aitask_record` on its fallback path.** When the
hook never fired and step 1 falls back to `upsert`, call
`ait_stamp_record "<pane>" "<id>"` from `lib/agent_sessions.sh` after the
`UPSERTED:` line. (`@aitask_frozen` stamping in step 4 is unchanged and is this
child's own.)

**A4 — refusal wire lines.** A stray `upsert` in a transacting pane now returns
`UPSERT_REFUSED:<id>|freezing_unacknowledged` (not `…|freezing`); `frozen`
still returns `…|frozen`.

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
