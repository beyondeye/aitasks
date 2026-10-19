---
Task: t2043_fix_shadow_self_phase_socket_guard.md
Base branch: main
Output branch: main
---

# t2043 — Fix `shadow_self_phase()` cross-server socket guard

## Context

`shadow_self_phase()` in `.aitask-scripts/aitask_shadow_capture.sh` (~line 316)
reads the advisory `@aitask_shadow_phase` stamp off its own pane. Its comment
says it applies "the same socket check" as `shadow_self_target`, but both sides
of the comparison come from the gateway server:

```bash
own_sock="$(ait_tmux display-message -p "#{socket_path}" ...)"          # gateway
out="$(ait_tmux display-message -p -t "$own_pane" "#{socket_path}..." )" # gateway
[[ "$own_sock" == "$sock" ]] || return 0                                # always equal
```

`ait_tmux` always talks to the gateway socket, so the guard never fires. A
shadow running in a pane on a foreign server (for example the user's own tmux)
whose `%N` happens to match a gateway pane gets that unrelated pane's phase stamp
printed as its own. `shadow_self_target` (same file) and
`lib/tmux_exec.sh::ait_tmux_self_pane_pid` already do this correctly: they
compare against `${TMUX%%,*}`, the socket of the server this process actually
lives on.

This is the only site with the bug: a grep for `socket_path` across
`.aitask-scripts/*.sh` turns up just these three functions, plus a
`tmux_bootstrap.sh` listing that does not compare sockets.

## Changes

### 1. `.aitask-scripts/aitask_shadow_capture.sh` — `shadow_self_phase()`

- Take `own_sock` from `${TMUX:-}` stripped to `%%,*`, the same way
  `shadow_self_target` does. Return 0 (print nothing) when it is empty: that
  means no `$TMUX`, or a stale/inherited `TMUX_PANE`.
- Remove the gateway `display-message -p "#{socket_path}"` round trip. Keep the
  single `-t "$own_pane"` display-message that reads socket and stamp together.
- Update the comment so it says the socket is compared against `$TMUX`, the
  server this process lives on, not the gateway.
- Tidy-up in the same block: `shadow_self_phase()` and its comment were inserted
  between `shadow_stamp_analyzed_at`'s doc comment and that function, so the
  stamp's comment (`$1 = captured pane id`, `$2 = …`) now sits above the wrong
  function. Move the `shadow_self_phase` block (plus `shadow_report_phase`,
  which follows it) above that doc comment, so every comment sits directly
  above its own function. No code in the move changes.

### 2. `tests/test_shadow_capture.sh` — cross-server phase assertions

Add these inside the existing case 7 cross-server fixture (t1319). That fixture
already builds `x_pane` on server `XSOCK` with the same id as the gateway's
(`BSOCK`) `b_shadow`, which is exactly the collision this bug needs.

- Stamp `@aitask_shadow_phase` on the gateway's `b_shadow` with a unique
  sentinel line, `PHASE:IMPLEMENT|…|DETAIL:T2043_PHASE_SENTINEL`.
- **Fix check:** run `--phase` with `TMUX="$XTMUX" TMUX_PANE="$x_pane"
  AITASKS_TMUX_SOCKET="$BSOCK"`. Assert the output does not contain the sentinel
  and ends `VIA:none`, i.e. the stamp was not used.
- **Control (same-server):** run `--phase` with `TMUX="$BTMUX"
  TMUX_PANE="$b_shadow"` against the same gateway. Assert the output contains the
  sentinel and `VIA:pane-option`. This proves the fixture stamp can be read, so
  the fix check really tests the guard.
- **Empty-`$TMUX` case:** `TMUX="" TMUX_PANE="$b_shadow"` → no sentinel (fails
  closed).

These follow the file's existing `assert_contains` / `assert_not_contains` /
`set -e`-safe `|| true` idiom. The test body does not run in a `( … )`
subshell, so no counter opt-in is needed.

### 3. `tests/test_shadow_phase_advisory.sh` — move Layer 1b onto a private fixture server

*(Added after plan review — the concern was checked and is valid.)* Layer 1b is
currently gated on the ambient `$TMUX_PANE`. It then writes and unsets
`@aitask_shadow_phase` on that pane id through the gateway (`ait_tmux`, which is
`-L ait` by default), and never restores the old value:

- **From a foreign server**, it overwrites and then deletes the stamp on an
  unrelated gateway pane that happens to share the id: the same wrong-pane
  hazard this task fixes.
- **After the fix**, the reader correctly rejects those cross-server stamps, so
  the "served verbatim" checks would fail.
- **From the gateway itself** (this session: `TMUX=/tmp/tmux-1000/ait,…`), it
  still wipes the invoking pane's real monitor stamp.

The rewrite:

- Gate Layer 1b on `command -v tmux` instead of `$TMUX_PANE`. Start a private
  server `FSOCK="ait_phasetest_$$"` with one `sleep` pane, using a bounded
  pane-id poll like the one in `test_shadow_capture.sh`.
- Derive the fixture's `$TMUX` the same way that file does:
  `tmux -L "$FSOCK" display-message -p -t "$fpane" '#{socket_path},#{pid},0'`.
- Stamp and unset the option with raw `tmux -L "$FSOCK" set-option -p -t "$fpane"
  …`. Tests are outside `test_no_raw_tmux.sh`'s scan scope, and the sibling
  suite does the same. Drop the `source lib/tmux_exec.sh` that only served this.
- Run every `$CAPTURE --phase` call in 1b with matching
  `TMUX="$FTMUX" TMUX_PANE="$fpane" AITASKS_TMUX_SOCKET="$FSOCK"`. That keeps
  the wrong/corrupt-stamp checks independent of where the suite is invoked from.
- Keep every existing assertion unchanged: the wrong phase is served verbatim,
  a corrupt stamp falls back to `VIA:ledger-cli`, and the garbage-stamp call
  exits 0.
- Kill the fixture server at the end of the block. Add a `trap … EXIT` for it,
  next to the existing `CLEANUP_DIRS` loop, so an interrupted run does not leak
  a server. If the fixture pane cannot be started, print SKIP, as the sibling
  suite does.
- Layer 1's existing untargeted calls are unchanged. The fix makes "outside a
  shadow pane" fail closed, which is the case they test.

## Verification

1. `bash tests/test_shadow_capture.sh` — all pass.
2. **Mutant (red proof):** temporarily put back the gateway-sourced `own_sock`
   line in a scratch copy of the script, never with a `git restore` of the
   working tree, and confirm the new cross-server assertion fails while the
   same-server control still passes. Then confirm the fixed script passes.
3. `bash tests/test_shadow_phase_advisory.sh`:
   - It is green, Layer 1b runs (no SKIP), and `--phase` stays total.
   - Read the invoking pane's `@aitask_shadow_phase` on the gateway before and
     after the run. The two values must be identical, which proves the suite no
     longer touches the ambient pane.
   - Run the suite once more from a foreign-server environment (`TMUX` naming
     a scratch server) and confirm Layer 1b still passes.
4. `shellcheck .aitask-scripts/aitask_shadow_capture.sh`.
5. `bash tests/test_no_raw_tmux.sh` — still green (no new raw tmux in scripts).

## Step 9

Current-branch mode under the `fast` profile: no branch to merge. Step 9 runs
build verification and then archives t2043.

## Risk

### Code-health risk: low
None identified. One function changes inside a single file, and it copies an
existing in-file pattern (`shadow_self_target`). The function relocation is a
pure move. The Layer 1b rewrite copies the sibling suite's existing private
fixture-server pattern and strictly reduces what the test touches outside
itself.

### Goal-achievement risk: low
None identified. The fix is the one the task suggests, and the new test uses an
existing fixture that already produces the pane-id collision, with a same-server
control and a mutant red proof.
