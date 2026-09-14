---
Task: t1783_converge_freeze_side_destructive_sites_on_stamp_conditional_.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1783 — Converge freeze-side destructive sites on the stamp-conditional dispatch

## Context

t1773 measured (tmux 3.6a) that pane ids are monotonic within one tmux server and
never reused, but a **restarted** server renumbers from `%0`. So the only way a
recorded `%N` can name a different pane is a server restart, and any
probe-in-one-call / act-in-another sequence leaves exactly that window open.
t1773 closed it for `restore` with `agent_frozen_ops.respawn_if_stamped()`: the
stamp check and the destructive `respawn-pane -k` travel as **one** `if-shell -F`
dispatch, and success is proved by a per-call token written last in the matched
branch (never by a pid delta). `tests/test_frozen_respawn_atomic_live.sh` pins the
tmux facts (Part A) and drives the real restart race (Part B).

The freeze side still carries the two-call shape at three places in
`.aitask-scripts/lib/agent_freeze.py`:

| site | today | race |
|---|---|---|
| `drop_record()` (~:902-1010) | `probe_pane` (:964) then bare `kill-window`/`kill-pane` via `frozen_ops.run` (:981), then a second `probe_pane` to verify | restart between probe and kill hands the kill a recycled `%N` — and `drop` is the one path that deletes a session's only capture |
| `_respawn_standin()` (:659-676) | bare `frozen_ops.respawn()` on the pane reconcile enumerated a moment earlier | same race; reconcile runs unattended every 600 s |
| freeze transaction step 5 (:384) | `set_option(FROZEN_OPTION)` in one call, bare `frozen_ops.respawn()` in the next | same class, adjacent site — **not named by the task**; included because the fix is the same one-line routing and leaving one bare `respawn-pane -k` in the module defeats "converge". Strike step 3 at the checkpoint if you want the task held to the two named sites. |

Goal: every destructive tmux verb in `agent_freeze.py` is stamp-conditional in the
same dispatch, with the same evidence rule as `restore`, and the live suite proves
the kill side against a real restart exactly as it proves the respawn side.

## Design decisions

1. **A kill needs different evidence than a respawn.** The branch-token trick
   cannot apply verbatim: the token would be a pane option on the pane the branch
   just killed. For a kill the *safety* property is "never kill a `%N` that is not
   ours", which the single `if-shell -F` dispatch delivers on its own; the
   *outcome* the caller needs is "the stand-in is gone", which one after-read
   answers. Whether the pane vanished because our branch fired or because the
   server that held it restarted does not change what `drop` does next (the
   stand-in is gone either way, the capture is intact, and the store write is
   still gated on the claimed nonce). So `kill_if_stamped` returns a tri-state
   **verdict** (`gone` / `present` / `unknown`) plus a diagnostic reason, and
   `drop_record` keeps failing closed on anything but `gone`.
2. **A miss must say whether the pane is still ours.** Today a bare `respawn`
   that returns non-zero means "the pane is ours and the respawn failed" and the
   callers unstamp / retry. Under `respawn_if_stamped` a miss can also mean "the
   pane is not ours" (stranger / gone), where unstamping would clear a *stranger's*
   stamp. The after-read gains the stamp itself (a 5th field), and the reason
   vocabulary gains `respawn-failed` = "no token, stamp still ours, same server":
   the branch matched and the respawn did not take. Callers unstamp/retry only on
   that reason; every other miss touches nothing (nothing of ours is in that pane).
   This is a diagnostic-only extension for `restore` (it branches on `fired`
   only and prints `why` in a warning), so its behaviour is unchanged.
3. **On a miss that is not `respawn-failed`, `_respawn_standin` commits the
   gone-pane pair** (`standin-respawned --pane "" --pane-pid 0` →
   `STANDIN:<id>|pane_gone`), exactly what `agent_restore._rollback` does for the
   mirror-image case and what `_reconcile_aborting`'s `observed is None` row
   already commits. The record stays restorable into a new window. A
   `respawn-failed` miss keeps today's `RECONCILE_FAILED:<id>|respawn refused`
   (retried on the next pass; stamps intact).
4. **The unit-test fake executes `if-shell` branches recursively**, so nested
   `respawn-pane` / `kill-pane` / `kill-window` / `set-option` calls are still
   recorded in `tmux.calls` and the existing `calls_of("kill-pane")`-style
   assertions keep meaning what they mean. A rejected branch records nothing —
   which is the assertion the new recycled-`%N` cases need.

## Implementation steps

### Pre-phase (risk mitigations)

1. **[pre_fix_control_recycled_pane]** Before touching any engine code, add
   `DropVerbTests.test_a_pane_recycled_between_preflight_and_kill_is_not_killed`
   to `tests/test_agent_freeze.py`. Its fake wraps `_TMUX.run` and, on the
   **first destructive call it sees** (`kill-pane` / `kill-window` today,
   `if-shell` after the fix), flips the target pane's `@aitask_frozen` to
   `"deadbeef"` and its `pid` to a new value *before* forwarding the call —
   modelling the server restart landing between the preflight probe and the
   kill. Assert: `DROP_FAILED:<rid>|kill:pane not verified gone (…)`, record and
   capture kept, the pane still present in the model with the foreign stamp, and
   no top-level `kill-*` call recorded. Run it against the **unfixed**
   `drop_record` and confirm it FAILS (the stranger's pane is popped from the
   model and the drop reports `DROPPED`). Record the failing output in the Final
   Implementation Notes. Only then proceed to step 1.

### 1. `agent_frozen_ops.py` — the shared primitives

**1a. Extend `respawn_if_stamped`'s after-read with the stamp.**

- After-read format becomes `RESPAWN_PROBE_FORMAT + "\t" + f"#{{{option}}}"`
  (5 fields; keep the 4-field constant, its docstring now says "the four fixed
  after-facts — the caller's stamp option is appended per call").
- `len(parts) != 5` → `pane-gone`.
- Decision order after the read: our token → fired; `server_after != server_before`
  → `server-restarted`; `stamp == expect` → **`respawn-failed`** (new); else
  `stamp-mismatch`.
- Docstring: add `respawn-failed` to the `reason` list with its contract: *"the
  pane still carries `expect`, so it is still the caller's — the branch matched
  and the respawn itself did not take; the only miss on which a caller may
  unstamp or retry. Every other miss means nothing of the caller's is in that
  pane."*

**1b. Add `kill_if_stamped`.**

```python
def kill_if_stamped(pane_id: str, *, option: str, expect: str,
                    window: bool = False) -> tuple[str, str]:
    """`kill-pane` (or `kill-window` when ``window``) on ``pane_id``, ONLY if the
    pane still carries ``option == expect``. Returns ``(verdict, reason)``:
    ``"gone"`` — the pane no longer exists (our branch fired, or the server that
    held it restarted; either way there is nothing left to kill);
    ``"present"`` — untouched: ``reason`` is ``kill-failed`` (still stamped
    ours: the branch matched, the kill did not take), ``server-restarted`` or
    ``stamp-mismatch``;
    ``"unknown"`` — tmux unreachable; decide NOTHING on it.
    """
    rc, out = run(["display-message", "-p", "-t", pane_id, "#{pid}"])
    if rc == TMUX_UNREACHABLE:
        return "unknown", "tmux unreachable"
    if rc != 0:
        return "gone", "pane-gone"
    server_before = (out.splitlines() or [""])[0].strip()
    verb = "kill-window" if window else "kill-pane"
    pause_at("kill_dispatch")
    run(["if-shell", "-F", "-t", pane_id,
         f"#{{==:#{{{option}}},{expect}}}", f"{verb} -t {pane_id}"])
    rc, out = run(["display-message", "-p", "-t", pane_id,
                   "\t".join(["#{pane_id}", f"#{{{option}}}", "#{pid}"])])
    if rc == TMUX_UNREACHABLE:
        return "unknown", "tmux unreachable"
    if rc != 0:
        return "gone", ""
    parts = (out.splitlines() or [""])[0].split("\t")
    if len(parts) != 3 or not parts[0].strip():
        return "gone", ""
    _, stamp, server_after = (p.strip() for p in parts)
    if stamp == expect:
        return "present", "kill-failed"
    if server_after != server_before:
        return "present", "server-restarted"
    return "present", "stamp-mismatch"
```

Docstring must carry the "why no token" reasoning from design decision 1 and
note the `-t <pane>` → window resolution that `kill-window` relies on (already
the shape `drop_record` used; the live suite pins it in K3). `pause_at` seam
name: `kill_dispatch` (mirrors `respawn_dispatch`).

### 2. `agent_freeze.py` — `drop_record`

Replace the kill + verify block (`if must_kill:` … `pane not verified gone`) with:

```python
        if must_kill:
            _drop_fail_at("kill")
            others = _other_real_agents(pane_id)
            # `None` (the listing failed) downgrades to kill-pane rather than
            # collapsing a window that may still hold a live agent.
            verdict, why = frozen_ops.kill_if_stamped(
                pane_id, option=FROZEN_OPTION, expect=record_id,
                window=(others == 0))
            _drop_fail_at("verify")
            if verdict != "gone":
                _release()
                return (f"DROP_FAILED:{record_id}|kill:pane not verified gone "
                        f"({why})")
```

Keep the `verify` seam where it is (between dispatch and interpretation) so
`test_an_injected_verify_failure_keeps_everything` keeps its meaning. Error
strings keep the `DROP_FAILED:<id>|kill:` prefix the tests and docs pin.

Docstring edits in `drop_record`:
- step 2 "**kill** the stand-in" → say the stamp check and the kill are one
  `if-shell -F` dispatch (`frozen_ops.kill_if_stamped`), so a server restart
  between preflight and kill cannot hand it a recycled `%N`; pane options die
  with the pane, so no unstamp step is needed (unchanged).
- Rewrite the "one residual, accepted deliberately" paragraph: the kill *is*
  now conditional. The residual that remains is that the sibling count
  (`_other_real_agents`) is a separate read, so within one server generation an
  agent joining the window between the count and the dispatch could turn a
  `kill-window` into a wider kill than intended — that read decides *window vs
  pane*, never *whether*, and the stamp check still gates the verb. Keep the
  "do not reorder" guidance for the store write.

### 3. `agent_freeze.py` — freeze transaction step 5 (adjacent site, flagged)

```python
    pane_ours = True
    try:
        _fail_at("respawn")
        command = agent_sessions.standin_command(record_id)
        fired, _, _, why = frozen_ops.respawn_if_stamped(
            pane_id, command, option=FROZEN_OPTION, expect=record_id)
        if not fired:
            pane_ours = why == "respawn-failed"
            raise OSError(f"respawn-pane not fired for {pane_id} ({why})")
    except (_StageFailure, OSError, ValueError) as exc:
        if pane_ours:
            frozen_ops.unset_option(pane_id, FROZEN_OPTION)
            frozen_ops.unset_option(pane_id, STANDIN_READY_OPTION)
        frozen_ops.store("freeze-abort", record_id, "--nonce", nonce)
        return FreezeResult(record_id, False, "respawn", ...)
```

Step 4 keeps clearing the ready mark itself (no `unset=` here — the stamp step
already did it, and the existing test pins that order). Comment: a miss that is
not `respawn-failed` means the pane is not ours any more (restart / recycled
`%N`), and unstamping it would clear a stranger's — possibly another record's —
stamp.

### 4. `agent_freeze.py` — `_respawn_standin`

```python
    nonce = lease()
    try:
        command = agent_sessions.standin_command(record_id)
    except ValueError as exc:
        return f"RECONCILE_FAILED:{record_id}|{exc}"
    fired, new_pane, new_pid, why = frozen_ops.respawn_if_stamped(
        pane_id, command, option=FROZEN_OPTION, expect=record_id,
        unset=STANDIN_READY_OPTION)
    if not fired:
        if why == "respawn-failed":
            return f"RECONCILE_FAILED:{record_id}|respawn refused"
        # The %N stopped being ours between enumeration and dispatch (server
        # restart / recycled id). Nothing was touched; record the gone-pane pair
        # so the record stays restorable into a NEW window — the same pair
        # `agent_restore._rollback` commits for its mirror-image miss.
        new_pane, new_pid = "", 0
    rc, out = frozen_ops.store("standin-respawned", record_id, "--nonce", nonce,
                               "--pane", new_pane, "--pane-pid", str(new_pid))
    if rc != 0:
        return f"RECONCILE_FAILED:{record_id}|{out}"
    return f"STANDIN:{record_id}" if fired else f"STANDIN:{record_id}|pane_gone"
```

The separate `unset_option(STANDIN_READY_OPTION)` call goes away — the clear now
rides inside the branch (`unset=`), so it is not applied to a pane the dispatch
declines to touch. Update the docstring accordingly ("cleared BEFORE the respawn"
still holds — it is first in the branch).

### 5. Unit tests — `tests/test_agent_freeze.py`

**5a. `_FakeTmux` learns `if-shell`** (new `_if_shell` handler in `run`):
- parse the condition `#{==:#{<option>},<expect>}` with a regex; target pane
  missing → `(1, "")`; compare `pane.get(option, "") == expect`;
- on match, split the branch on `" ; "`, `shlex.split` each piece, and call
  `self.run(argv)` for each — **stop at the first non-zero rc** (tmux aborts an
  `if-shell` sequence on a failing command; this is what makes `respawn_ok=False`
  and `kill_ok=False` leave no token / keep the pane present);
- always return `(0, "")` from the `if-shell` itself (tmux does).
- `_display` needs no change: the new 5th field and `#{pid}` fall out of the
  pane model (`pid` absent → `""` on both reads → "same server").

**5b. New / adjusted cases**

- `FreezeTransactionTests`: `test_a_recycled_pane_is_never_respawned_by_the_freeze`
  — after `freeze-begin`… simplest form: set `panes[AGENT_PANE][FROZEN_OPTION]`
  to `"deadbeef"` via a `set_option_ok`-style hook that flips the stamp right after
  step 4 writes it (subclass the fake so `_set_option` of `FROZEN_OPTION` stores
  a foreign value); assert stage `respawn`, `calls_of("respawn-pane") == []`, the
  foreign stamp is **still** `"deadbeef"` (not unstamped), state back to `live`.
- `test_a_real_respawn_refusal_takes_the_same_path` — additionally assert both
  stamps were cleared (reason is `respawn-failed`, the pane is ours).
- `ReconcileFreezing/FrozenTests`: `test_a_recycled_standin_pane_commits_the_gone_pane_pair`
  — observed says stamped+dead, but the pane model's stamp is `"deadbeef"`;
  assert line `STANDIN:<rid>|pane_gone`, no `respawn-pane` call, the
  `standin-respawned` store call carries `--pane ""`/`--pane-pid 0`, the stranger's
  stamp and `pane_pid` untouched.
- `test_a_refused_standin_respawn_is_reported_not_committed` — `respawn_ok=False`;
  assert `RECONCILE_FAILED:<rid>|respawn refused` and no `standin-respawned`.
- `test_the_ready_mark_is_cleared_BEFORE_every_respawn` — unchanged (the recursive
  fake preserves the order).
- `DropVerbTests`: `test_the_kill_is_one_stamp_conditional_dispatch` — after a
  drop, exactly one `if-shell` call, its condition is
  `#{==:#{@aitask_frozen},<rid>}`, its branch starts with `kill-window -t <pane>`;
  no bare top-level kill (every kill in `calls` sits after the `if-shell`).
- `test_a_pane_recycled_between_preflight_and_kill_is_not_killed` — a fake whose
  `run` flips the pane's stamp to `"deadbeef"` on the first `if-shell` **before**
  evaluating it (simulating the restart between the two); assert
  `DROP_FAILED:<rid>|kill:pane not verified gone (stamp-mismatch)`, record and
  capture kept, the pane still in `panes`, no `kill-*` recorded. (Also flip
  `pane["pid"]` to model a restart → reason `server-restarted`.)
- Existing `test_a_failed_kill_changes_nothing` — extend the prefix assertion to
  the exact `(kill-failed)` reason.

### 6. Unit tests — `tests/test_agent_frozen_ops.py`

- `PROMISED_CALLABLES` += `"kill_if_stamped"`.
- `RespawnIfStampedTests`: append a 5th field to the six 4-field answers
  (`"…\t9999\tabc123"` on the success/ours paths, `"…\tf00dfeed"` on the
  stranger paths so `stamp-mismatch` / `server-restarted` expectations hold); add
  `test_no_token_with_our_stamp_intact_is_respawn_failed` (`"\t%104\t51000\t9999\tabc123"`
  → `(False, "", 0, "respawn-failed")`) and assert the dispatch's after-read
  format ends with `#{@aitask_frozen}`.
- New `KillIfStampedTests` (same `_Seq` fake): dispatch shape (`if-shell -F -t
  %104 #{==:#{@aitask_frozen},abc123} kill-pane -t %104`, and `kill-window` with
  `window=True`); after-read `(1,"")` → `("gone","")`; `("%104\tabc123\t9999")`
  → `("present","kill-failed")`; `("%104\tf00dfeed\t12345")` →
  `server-restarted`; `("%104\tf00dfeed\t9999")` → `stamp-mismatch`; empty
  pane_id → gone; pre-read `(-1,"")` → `("unknown", …)` **and no `if-shell`
  dispatched**; pre-read `(1,"")` → `("gone","pane-gone")` and nothing dispatched.

### 7. Unit tests — `tests/test_agent_restore.py`

Append the 5th field to the four arity-4 scripted answers (lines ~350, 593, 637,
652): `\t7f3a2c1d` where the pane is ours (350, 593), `\tf00dfeed` where it is a
stranger (637, 652). Re-read each test's expectation before choosing; the
`_ScriptedTmux` fake keys on arity, so a 4-field answer would now silently read
as `pane-gone`.

### 8. Live suite — `tests/test_frozen_respawn_atomic_live.sh`

Add a second driver (`kill_driver.py`, printing `verdict|reason`) and:

**Part A (kill facts)** — every case builds a *second* window so the killed pane
is never the server's last one (`fresh_server "sleep …"; tm new-window -d
"sleep …"` → `%1`, `tm split-window -d -t %1 "sleep …"` → `%2` where a sibling is
needed):
- K1 matched `kill-pane` dispatch: verdict `gone`, reason empty, `%1` gone, `%2`
  and `%0` alive.
- K2 rejected dispatch (`expect=somebody-else`): verdict `present`, reason
  `stamp-mismatch`, `%1`'s pid and command unchanged.
- K3 `window=True` via a **pane** target kills the sibling too: `%1` and `%2`
  gone, `%0` alive (pins the `-t <pane>` → window resolution `drop` relies on).
- K4 pane already gone before dispatch: verdict `gone`, reason `pane-gone`.

**Part B (kill)** — mirror the respawn Part B with the `kill_dispatch` seam:
driver paused after its pre-read, `fresh_server` + `tm new-window -d "sleep 4242"`
recreates `%1` under a stranger, resume; assert verdict `present`, reason
`server-restarted`, the stranger's pid still holds `%1`, its command intact.

Add a one-line note in the header comment that the suite now pins both
stamp-conditional primitives. Follow the file's existing conventions:
`assert_counters_init`/`assert_counters_load`, `require_isolated_tmux`, `tm`,
`pane_fmt`, `pane_exists`, `wait_stopped`, per-run `TMUX_TMPDIR`.

### 9. Docs

No website or `aidocs/` page describes the drop residual (checked
`website/content/docs/tuis/frozenagent/*`, `aidocs/`); the docstrings in steps 1,
2, 4 are the documentation. No `.md` change.

### Post-phase (risk mitigations)

1. **[scripted_fake_unknown_arity_fails_loudly]** In `tests/test_agent_restore.py`,
   change `_ScriptedTmux.run` so that a `display-message` whose arity has no
   entry in `self.answers` raises `AssertionError("unscripted display-message
   arity N: <args>")` **whenever `answers` is non-empty** (a fake constructed
   with no answers keeps the permissive `DEFAULT`). Update the class docstring:
   the arity key is what the real parsers validate, so an unscripted arity must
   fail the test rather than read as `pane-gone`. Run
   `python3 tests/test_agent_restore.py` and confirm every test still passes —
   any failure here is a fixture that the 5-field after-read (step 1a) left
   behind, and is fixed by scripting the missing arity, never by weakening the
   guard.

## Verification

Run the pre-fix control first (see the inline pre-phase if confirmed), then:

```bash
python3 tests/test_agent_frozen_ops.py
python3 tests/test_agent_freeze.py
python3 tests/test_agent_restore.py
bash tests/test_frozen_respawn_atomic_live.sh     # Parts A/B respawn + new kill A/B
bash tests/test_freeze_engine_live.sh             # freeze transaction on real tmux
bash tests/test_restore_flows_live.sh             # restore + rollback respawns
bash tests/test_frozen_agents_acceptance.sh       # cases 10a/10b (drop) + reconcile
bash tests/test_cleanup_rule_parity.sh
bash tests/test_no_raw_tmux.sh                    # gateway rule still holds
bash tests/run_all_python_tests.sh --test-dir tests   # last line PYTHON SUITE: PASSED
```

Expected: no `DROP_FAILED:…|kill:` or `…|preflight:` line in the acceptance drop
cases; `grep -n "frozen_ops.respawn(\|frozen_ops.run(\[.kill" .aitask-scripts/lib/agent_freeze.py`
returns nothing (no bare destructive verb left in the module).

## Step 9 (Post-Implementation)

Current-branch mode, no worktree, no merge. Commit as
`bug: Converge freeze-side destructive sites on stamp-conditional dispatch (t1783)`,
then archive task + plan per the shared workflow Step 9.

## Risk

### Code-health risk: medium
- The shared `respawn_if_stamped` after-read grows from 4 to 5 fields; `tests/test_agent_restore.py`'s `_ScriptedTmux` keys answers on arity and answers an unknown arity with `(0, "")`, so a missed fixture silently reads as `pane-gone` and diverts a restore test into a branch it was not written for · severity: low (residual — addressed by inline post-phase scripted_fake_unknown_arity_fails_loudly) · → mitigation: inline post-phase scripted_fake_unknown_arity_fails_loudly
- Step 3 changes the freeze transaction's respawn, the most-exercised path in the module; a regression there breaks every freeze, not only the racy ones (bounded by `test_freeze_engine_live.sh` + acceptance on real tmux) · severity: medium · → mitigation: none (covered by the live-suite verification sweep)
- The new recursive `if-shell` emulation in `_FakeTmux` is test infrastructure: if it mis-models tmux (abort-on-first-failure, condition parsing) the unit suite stays green while the real dispatch differs (bounded by the live suite pinning the same facts) · severity: low · → mitigation: none

### Goal-achievement risk: low
- The kill-side evidence rule ("gone after the dispatch is sufficient") is argued, not yet measured against a real restart; the new live Part B (kill) is the measurement, and it only proves the fix if a version of the same scenario is first seen to fail against the unfixed two-call `drop_record` · severity: low (residual — addressed by inline pre-phase pre_fix_control_recycled_pane, plus the live Part B kill case) · → mitigation: inline pre-phase pre_fix_control_recycled_pane
- Requirement coverage: the task names two sites and the plan also converts the adjacent freeze-transaction respawn (step 3) — if the user strikes it, the "no bare destructive verb left" verification grep must be relaxed to exclude that site · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: pre_fix_control_recycled_pane | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the kill-side evidence rule is argued, not measured | desc: Write the recycled-pane drop unit test first, keyed on the first destructive call, and watch it fail against the unfixed two-call drop_record before implementing
- timing: post-phase | name: scripted_fake_unknown_arity_fails_loudly | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the arity-keyed restore fake silently answers an unscripted after-read arity as pane-gone | desc: Make _ScriptedTmux raise on an unscripted display-message arity when answers are scripted, so the 5-field after-read cannot divert a restore test unnoticed
