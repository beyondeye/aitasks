---
Task: t1083_fix_failed_verification_t717_5_item17.md
Base branch: main
plan_verified: []
---

# t1083 — Fix failed verification (t717_5 item #17): `./ait stats tui` doesn't route to the TUI

## Context

t717_5 item #17 read: *"Open `./ait stats tui`, navigate to verified pane. Press `]` repeatedly."*
Auto-verification (archived `p717_5_manual_verification_auto.md`, Item 17) ran
`./ait stats tui` and got:

> dispatcher runs `aitask_stats.sh` and reports `unrecognized arguments: tui`;
> `ait` exposes `stats-tui` as the TUI route instead.

**The failure is a command-surface gap, not a bug in the `]` window-cycling code.**
The `ait` dispatcher (`ait:206-207`) routes `stats` → `aitask_stats.sh` (the text
CLI, argparse-based) and the TUI under a *separate* hyphenated command `stats-tui`
→ `aitask_stats_tui.sh`. A user (or verifier) who naturally types `ait stats tui`
hits argparse's `unrecognized arguments: tui` instead of the TUI.

The window-cycling behavior itself is sound: item #18 (line 42 of the archived
checklist) exercised the *identical* `WINDOWS` / `cycle_window` code on the usage
pane via a direct `.aitask-scripts/aitask_stats_tui.sh` launch and **passed**. The
verified pane (`VerifiedRankingsPane`) shares that exact code path
(`panes/agents.py`). So the only defect to fix is the invocation surface.

**Reproduced locally:** `./ait stats tui` → `aitask_stats.sh: error: unrecognized arguments: tui`.

## Fix

Make `ait stats tui` an alias for `ait stats-tui` by adding a sub-arg check in the
dispatcher's `stats)` case — mirroring the existing `crew)` / `brainstorm)`
sub-command routing pattern (`ait:222-257`). `stats-tui` remains the canonical
route; this only adds the natural two-word form.

### `ait` — `stats)` case (currently line 206)

Replace:
```bash
    stats)        shift; exec "$SCRIPTS_DIR/aitask_stats.sh" "$@" ;;
```
with:
```bash
    stats)
        shift
        # `ait stats tui` is a natural alias for the hyphenated `ait stats-tui`
        # route; forward it there. All other args go to the text CLI.
        if [ "${1:-}" = "tui" ]; then
            shift; exec "$SCRIPTS_DIR/aitask_stats_tui.sh" "$@"
        fi
        exec "$SCRIPTS_DIR/aitask_stats.sh" "$@" ;;
```

Rationale for fixing in the dispatcher (not in `aitask_stats.py` argparse): the
dispatcher is the routing seam and already owns the split between the two scripts;
adding a phantom `tui` positional to the argparse CLI would conflate the two
entrypoints. `stats` has no positional args (only `-d/-w/-v/--csv`), so `tui` as
first token is unambiguous.

Note: the pre-case update check (`ait:183-185`) already runs `check_for_updates`
for `stats` in the background (`&`/disown) — non-blocking, unaffected by the
re-route.

## Test

New `tests/test_stats_tui_dispatch.sh` — behavioral test of the **real dispatcher**
routing without launching Textual, by stubbing the two target scripts in a copied
minimal tree (pattern from `tests/test_migrate_archives.sh:24-46`):

- Copy real `ait` + `.aitask-scripts/lib/aitask_path.sh` + `.aitask-scripts/VERSION`
  into a `mktemp -d`.
- Write **stub** `aitask_stats.sh` (echoes `STATS_CLI $*`) and `aitask_stats_tui.sh`
  (echoes `STATS_TUI $*`), both `chmod +x`.
- Assert:
  1. `bash ./ait stats tui` → output contains `STATS_TUI` (routed to TUI), not `STATS_CLI`.
  2. `bash ./ait stats tui --foo` → `STATS_TUI --foo` (extra args forwarded, `tui` consumed).
  3. `bash ./ait stats -d 7` → `STATS_CLI -d 7` (plain text CLI still works; `tui` not swallowed from normal flags).
  4. `bash ./ait stats-tui` → `STATS_TUI` (canonical hyphenated route intact).
- Negative control: assert case 3 output does **not** contain `STATS_TUI` (a
  greedy/incorrect match would misroute normal stats invocations).

Uses `tests/lib/asserts.sh` (`assert_contains`) and prints a PASS/FAIL summary,
per repo test conventions (self-contained bash, no runner).

## Files to modify

- `ait` — expand the `stats)` dispatcher case (~line 206) to re-route `tui`.
- `tests/test_stats_tui_dispatch.sh` — **new** behavioral routing test.

## Out of scope

- No change to `panes/agents.py` / `stats_app.py` window-cycling code — verified
  sound via item #18's passing check on the shared code path.
- Not adding `stats tui` to `ait` help text or `show_usage` — `stats-tui` stays the
  documented canonical command; the alias is a convenience. (Can revisit if desired.)
- No docs changes: no `website/`, `aidocs/`, or skill file references the space form
  `ait stats tui` (grep-verified clean), so nothing to redirect.

## Risk

### Code-health risk: low
- Dispatcher change is a 5-line additive re-route in an isolated `case` arm, mirroring an
  established in-file pattern (`crew)`/`brainstorm)`); `stats-tui` and plain `stats` paths
  are preserved and pinned by the new test · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Root cause is unambiguous and reproduced; the fix makes the exact failing invocation
  (`./ait stats tui`) work, and the underlying `]` behavior was independently confirmed
  working (item #18) · severity: low · → mitigation: TBD

## Verification

1. `bash tests/test_stats_tui_dispatch.sh` → all assertions PASS.
2. `shellcheck ait` → clean (no new warnings from the edited case).
3. Manual: `./ait stats tui` launches the stats TUI (verified pane); `q` quits.
   Press `]` on the verified pane → window cycles `recent → all_time → month →
   prev_month → week`. `./ait stats-tui` still launches; `./ait stats` still prints
   the text report.

## Step 9: Post-Implementation

Standard archival via `./.aitask-scripts/aitask_archive.sh 1083`. Folded tasks: none.
The task is risk-gated (`risk_evaluated` in the profile's effective gates); Step 7
writes `risk_code_health: low` / `risk_goal_achievement: low` and the gate is recorded.

## Final Implementation Notes

- **Actual work done:**
  - `ait` — expanded the `stats)` dispatcher case (was a one-line `exec
    aitask_stats.sh`) to check for a leading `tui` arg and, if present, `shift`
    it and `exec "$SCRIPTS_DIR/aitask_stats_tui.sh" "$@"`. Plain `stats` and the
    hyphenated `stats-tui` route are unchanged.
  - `tests/test_stats_tui_dispatch.sh` (new) — behavioral test of the real
    dispatcher. Copies `ait` + `lib/aitask_path.sh` into a `mktemp -d` tree with
    STUB `aitask_stats.sh` / `aitask_stats_tui.sh` (each echoes a marker), then
    asserts: `stats tui` → TUI (not CLI); `stats tui --foo bar` forwards trailing
    args; `stats -d 7` → CLI (negative control, NOT the TUI); `stats-tui` → TUI.
    6/6 assertions pass.
- **Deviations from plan:** None. Implemented exactly as planned. One refinement
  vs. the plan's test sketch: the stub tree deliberately omits the `VERSION`
  file, so the dispatcher's daily update check (`check_for_updates`) bails at its
  `[[ -f "$version_file" ]] || return 0` guard — no background `curl`, fully
  deterministic/offline. `HOME` is also pointed at the temp tree.
- **Issues encountered:** None. Root cause (dispatcher routing gap, per the
  archived `p717_5_manual_verification_auto.md` Item 17 output) was reproduced
  immediately (`./ait stats tui` → `unrecognized arguments: tui`) and the fix
  confirmed live (`timeout 3 ./ait stats tui` launches the TUI, no argparse error).
- **Key decisions:** Fixed at the dispatcher (the routing seam that already owns
  the stats/stats-tui split) rather than adding a phantom `tui` positional to
  `aitask_stats.py`'s argparse, which would conflate the two entrypoints. `stats`
  takes no positional args, so a leading `tui` token is unambiguous. Kept
  `stats-tui` as the documented canonical command — `stats tui` is an additive
  convenience alias; help text was intentionally not expanded (revisitable).
- **Upstream defects identified:** None.
