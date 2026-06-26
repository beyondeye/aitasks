---
Task: t1055_applink_pause_flow_control_verb.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t1055 — AppLink server: handle the `pause` flow-control verb

## Context

`content_transport.md` §Back-pressure specifies that a mobile client MAY send a
`pause` push (`verb: "pause"`) **when backgrounded but not yet `Suspended`**
(screen off but socket alive) — the server must then **stop all pushes until a
`resume`**, with **no state lost**.

The server does not implement this. `applink/router.py` registers only
`{pair, resume, bye}` as `SESSION_VERBS` and has no `pause` in any verb set, so a
`pause` frame falls through to `UNKNOWN_VERB`. Meanwhile the mobile client
(aitasks_mobile `MonitorSessionMediator.kt`) sends `pause` and optimistically
treats itself as paused, so the two sides disagree: the phone believes pushes
are halted while `PushScheduler` keeps streaming binary frames + `pane_status`
heartbeats over the live socket (wasted bandwidth / battery while backgrounded).

**Outcome:** add a `pause` verb that halts the per-connection `PushScheduler`
until `resume`, preserving all subscription state, gated at the `read_only` tier.

**Cross-repo status — the mobile half is already shipped; no coordination task
needed.** In `aitasks_mobile` the client capability already exists and has
tests: `ControlFrames.kt:78` (pause request frame), `MonitorSessionMediator.pause()`
(`:205`, sends `verb:"pause"` fire-and-forget + optimistic Suspended), and
`MonitorSessionMediatorTest.kt:149` (`pause_then_resume_round_trips_state`). It
landed under the archived `t14` epic and the server gap was surfaced by the
archived audit `t14_11`. So t1055 is purely the **server half** that makes the
existing mobile behavior take effect — there is no open mobile task to wire to.

## Design decisions (and trade-offs)

**1. How `pause` halts pushes — a `paused` flag on `ConnState`, not a state
transition.** The spec is explicit that pause happens "not yet `Suspended`" and
loses no state, so `pause` must **not** move the connection to `STATE_SUSPENDED`
(that path is for dropped sockets and is driven by `server.py::_suspend`, which
also tears the pusher down). Instead `ConnState` gains a `paused: bool` (default
`False`); `PushScheduler._run_once` early-returns while it is set. This mirrors
the existing `self._conn.subscription` coupling the pusher already reads — no new
coupling direction is introduced, and the subscription/force set is untouched so
"no state lost" holds and any pending forced keyframes flush on resume.
  - *Rejected:* reusing `conn.state == STATE_SUSPENDED` as the halt signal —
    contradicts the spec ("not yet Suspended") and collides with the socket-drop
    suspend path.

**2. Gating — `pause` is a `read_only` profile-gated command verb (per the
task), while `resume` stays an ungated session verb.** The task says "Gate at
the `read_only` tier (it is a self-throttle, like `subscribe`/`request_keyframe`)".
Those two are exactly read_only-gated command verbs, so `pause` joins
`IMPLEMENTED_COMMAND_VERBS` and the `read_only` `allowed_verbs`. Because profiles
are **cumulative** (read_only is the floor; monitor_control and full re-list every
read_only verb), gating at read_only means **every** profile can pause — same
reachability as `resume` (ungated), so there is no asymmetry in who can pause vs.
resume. `resume` remains a `SESSION_VERB` because it is the reconnect-recovery
path that must work regardless of profile; it simply gains the duty of clearing
the `paused` flag (un-pause).
  - *Blast-radius note for a future editor:* a custom user profile that omits
    `pause` would get `PERMISSION_DENIED` on pause and degrade to today's
    behavior (server keeps pushing). All three shipped profiles + the in-code
    `DEFAULT_ALLOWED` fallback are updated, so the shipped config is correct.

## Changes

### 1. `.aitask-scripts/applink/router.py`
- Add `"pause"` to the `IMPLEMENTED_COMMAND_VERBS` frozenset (near the
  `subscribe`/`request_keyframe` data-plane control entries), with a short
  comment that it is a connection-level self-throttle gated like them.
- `ConnState.__init__`: add `self.paused: bool = False` with a comment
  ("data plane halted by a `pause` verb until `resume`; preserves subscription").
- `resume` handler (currently `handle()` ~line 208): add `conn.paused = False`
  so `resume` un-pauses (it already sets state → `STATE_CONNECTED`). Comment that
  resume doubles as the pause-clear.
- `_dispatch`: add a `pause` case (payload-less, connection-level):
  ```python
  if verb == "pause":
      # Self-throttle: halt this connection's PushScheduler until `resume`.
      # No pane arg; preserves the subscription (content_transport.md §Back-pressure).
      conn.paused = True
      return self._res(msg_id, verb, {"ok": True})
  ```

### 2. `.aitask-scripts/applink/pusher.py`
- `_run_once`: early-return at the top when paused, before the subscription
  check, so **both** binary frames and the `pane_status` heartbeat are halted:
  ```python
  async def _run_once(self) -> None:
      if self._conn.paused:
          return  # `pause` verb: halt all pushes until `resume` (content_transport.md §Back-pressure)
      sub = self._conn.subscription
      ...
  ```
  (Read directly like the existing `self._conn.subscription` access — `ConnState`
  always defines `paused`.)

### 3. `.aitask-scripts/applink/profiles.py`
- `DEFAULT_ALLOWED` (no-config fallback): add `"pause"` to the `read_only`,
  `monitor_control`, and `full` lists (keeps the fallback cumulative and in sync
  with the shipped YAMLs).

### 4. Shipped permission profiles (`aitasks/metadata/applink_profiles/`)
- Add `- pause` to `allowed_verbs` in `read_only.yaml`, `monitor_control.yaml`,
  and `full.yaml`. (No `seed/` copy exists — these three are the only on-disk
  source.)

### 5. Canonical verb-table docs (keep the audited inventories in sync)
- `aidocs/applink/monitor_port_design.md` — add a `pause` row to the canonical
  Command-verb inventory table (gate `read_only`, modal `N`), alongside the
  `subscribe`/`request_keyframe` row.
- `aidocs/applink/permissions.md` — add a `pause` row to the §Verb gating table
  (✓ / ✓ / ✓), matching the inventory.

### Tests
- `tests/test_applink_router.sh`:
  - `pause` under `read_only` → `res ok` (not `PERMISSION_DENIED`) and sets
    `conn.paused is True`.
  - `resume` on a paused conn clears it (`conn.paused is False`) — drive a conn
    through `pause` then `resume`, assert the flag toggles both ways.
  - `"pause" in KNOWN_VERBS`; fallback `DEFAULT_ALLOWED` permits `pause` under
    `read_only` (use the existing missing-dir `gate_default` pattern, ~line 288).
- `tests/test_applink_pusher.sh`:
  - Add a `paused=False` parameter to `FakeConn.__init__`.
  - New case: with `conn.paused = True`, `_run_once()` emits **zero** binary and
    **zero** text frames; flipping back to `False` and re-running emits again.

## Verification

```bash
bash tests/test_applink_router.sh     # router gating + pause/resume flag toggling
bash tests/test_applink_pusher.sh     # paused conn emits nothing; unpaused resumes
shellcheck .aitask-scripts/aitask_*.sh   # (unchanged scope; sanity)
```
Both bash suites are self-contained (PASS/FAIL summary). Expected: all `ok -`
lines, new pause assertions included.

## Step 9 (Post-Implementation)
No separate branch (profile 'fast' → current branch). After review/commit: run
the verification suites, then archive via `./.aitask-scripts/aitask_archive.sh 1055`.

## Risk

### Code-health risk: low
- New `paused` field + early-return is additive and localized to two files that
  already share the `conn` object; no existing behavior path is altered when
  `paused` stays `False` (the default). · severity: low · → mitigation: covered by new pusher test
- Doc/profile edits touch 5 surfaces (2 docs, 3 YAMLs, 1 fallback dict) that must
  agree; drift would only mis-document, not break runtime. · severity: low · → mitigation: enumerated in plan; tests assert the runtime fallback

### Goal-achievement risk: low
- Spec is explicit and the mirror verb (`resume`) already exists; the only
  judgment call (read_only gating vs. session verb) is resolved per the task's
  explicit instruction. · severity: low · → mitigation: documented trade-off above
- Cannot run the live mobile round-trip here (sibling repo); coverage is the
  server-side unit tests asserting pushes halt/resume. · severity: low · → mitigation: None identified (server-side contract fully unit-testable)

### Planned mitigations
None — both dimensions are low; no before/after mitigation tasks warranted.

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned across 7 files. `router.py`:
  `pause` added to `IMPLEMENTED_COMMAND_VERBS`, `ConnState.paused` flag (default
  `False`), `resume` clears it, `_dispatch` `pause` case sets it and returns
  `{ok:True}`. `pusher.py`: `_run_once` early-returns when `conn.paused` (halts
  binary frames + `pane_status` heartbeat, preserves subscription/force set).
  `profiles.py` `DEFAULT_ALLOWED` + the 3 shipped YAMLs gained `pause` at the
  `read_only` tier. `monitor_port_design.md` and `permissions.md` gained a `pause`
  row. Tests added to `test_applink_router.sh` (gating + flag toggle) and
  `test_applink_pusher.sh` (paused emits nothing; un-pause flushes preserved keyframe).
- **Deviations from plan:** None.
- **Issues encountered:** None. Discovered that `test_applink_router.sh` already
  contains an auto-validator loop asserting every profile's `allowed_verbs` entry
  is a member of `KNOWN_VERBS` — so the YAML + `IMPLEMENTED_COMMAND_VERBS` additions
  produced passing "profile verb 'pause' is registered" checks for free, confirming
  no orphaned verb name.
- **Key decisions:** `pause` halts pushes via a `ConnState.paused` flag (not a
  `STATE_SUSPENDED` transition) — the spec mandates pause happens "not yet
  Suspended" with no state lost, and `STATE_SUSPENDED` is the socket-drop path that
  tears the pusher down. `pause` is a `read_only`-gated command verb (per task);
  `resume` stays an ungated session verb and doubles as the un-pause. Cumulative
  profiles make read_only the floor, so every profile can pause — matching `resume`'s
  reachability.
- **Cross-repo:** The mobile half (`aitasks_mobile`) is already shipped and tested
  (`MonitorSessionMediator.pause()`, `ControlFrames.kt`, `MonitorSessionMediatorTest`);
  this is purely the server half. No coordination task needed.
- **Upstream defects identified:** None.
- **Verification:** `test_applink_router.sh` 150/150, `test_applink_pusher.sh` 73/73,
  plus smoke/pairing/sessions/server_limits/headless/content/devices suites all pass.
