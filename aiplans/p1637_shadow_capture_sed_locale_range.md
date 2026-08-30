---
Task: t1637_shadow_capture_sed_locale_range.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

`shadow_strip_ansi()` in `.aitask-scripts/aitask_shadow_capture.sh` stripped CSI
sequences with `sed 's|ESC\[[0-?]*[ -/]*[@-~]||g'`. `[0-?]` is a bracket *range*,
and POSIX compares a range's endpoints by the locale's collating sequence rather
than by byte value. Under `en_US.UTF-8` the punctuation block sorts before the
digits, so `?` precedes `0` and the range is reversed.

GNU sed accepted the reversed range through 4.9 and rejects it from 4.10. The
host upgraded `sed 4.10-1 -> 4.10-2` and `glibc 2.44+r5 -> 2.44+r24` on
2026-08-29 (per `/var/log/pacman.log`), at which point the expression became a
hard `sed: -e expression #3, char 25: Invalid range end`.

Because the script is `set -euo pipefail` and `shadow_strip_ansi` feeds
`shadow_clean` — the entire stdout path — the failure took out *every* shadow
capture, not just the one the user reported. `monitor_core.capture_shadow_text()`
routes the helper's stderr to `DEVNULL` and returns `None` on a non-zero exit, so
the real cause was invisible and surfaced only as minimonitor's bland
"Could not read the shadow pane".

The fix pins `LC_ALL=C` on that one `sed`, restoring the byte-value semantics the
three expressions were written against.

## Files Modified

**`.aitask-scripts/aitask_shadow_capture.sh`** (+17/-1)

- `shadow_strip_ansi()`: `sed -e ...` -> `LC_ALL=C sed -e ...`. The three
  expressions are unchanged.
- Added a comment block above the function recording why the pin is load-bearing:
  the collation rule, the 4.9/4.10 behaviour change, the blast radius through
  `shadow_clean`, the BSD-sed equivalence, and why byte-wise matching is correct
  for UTF-8 input here.

**`aidocs/framework/sed_macos_issues.md`**

- New row in the incompatibility table for bracket ranges.
- New section "Bracket ranges are ordered by the locale, not by ASCII": the
  reproduction, the measured collation order, a verdict table, and the two
  portable fixes.
- "Safe Features" bullet split *classes* (locale-independent) from *ranges*
  (locale-dependent) — it previously implied both were safe.
- Second note under the Safe Features blockquote.

## Probable User Intent

Reported as a minimonitor symptom: pressing `c` for the concern picker in window
`agent-pick-339` said "could not read shadow pane", with the suspicion that the
omarchy 4 upgrade had changed the tmux config and broken shadow-agent detection.

That diagnosis was wrong in both halves, and the exploration said so: detection
worked (`find_shadow_pane` resolved the bound `%30` correctly every time), and
tmux was not involved at all. The intent behind the request was to get shadow
agents working again; the deeper intent, given the framework's standards, was to
find the actual cause rather than the nearest plausible one.

## Final Implementation Notes

- **Actual work done:** one-line `LC_ALL=C` pin plus its explanatory comment, and
  the portability-doc section that would have prevented the bug.

- **Deviations from plan:** wrapped against the pre-existing t1637 (created by
  `/aitask-explore` minutes earlier for this exact diff) instead of minting a new
  task, which would have duplicated it. Before archiving, the one outstanding
  acceptance criterion — the `sed_macos_issues.md` row — was completed, so the
  task is closed against criteria it actually meets.

- **Issues encountered:** the first draft of the doc asserted a rule I had not
  measured — that ranges "crossing collation classes" are rejected. Probing 361
  endpoint pairs falsified it: `[!-~]`, `[@-~]`, `[:-@]`, `[0-A]` and `[9-a]` all
  cross classes and are all accepted. That draft was reverted and rewritten from
  measurement. The real order under glibc `en_US.UTF-8` is

      space + punctuation (ASCII order) < digits < lowercase < uppercase

  which explains both real failures: `[0-?]` (punctuation sorts before digits)
  and `[A-z]` (lowercase is a *block* before uppercase, so `z < A`). The ordering
  is blocked, not interleaved — `[a-B]` is accepted while `[A-b]` is not. Every
  one of the 13 verdicts in the doc table was re-run against `sed` before the
  file was written.

- **Key decisions:**
  - `LC_ALL=C` over enumerating `[0-9:;<=>?]`. It matches the established repo
    idiom (`lib/task_utils.sh`, `lib/pid_anchor.sh`, `lib/stale_lock.sh`), fixes
    GNU and BSD in one move, and additionally hardens the strip against capture
    text that is not valid UTF-8. Both options are recorded in the doc.
  - UTF-8 safety was measured, not assumed: Hebrew, CJK, a 4-byte emoji and
    box-drawing characters through the strip came out **byte-identical** to the
    Python `ANSI_CSI_RE` reference in `monitor/ansi_utils.py`.
  - The shell/Python mirror contract is untouched — `tests/test_shadow_strip_ansi.sh`
    still asserts the two implementations agree, and that mirror is the reason
    this was catchable at all.

- **Verification:** `tests/test_shadow_strip_ansi.sh` 9/9 (was 3/9 — six failures
  all carrying the exact sed error, a deterministic pre-existing red proof);
  `tests/test_shadow_capture.sh` 40/40; `tests/test_no_raw_tmux.sh` 5/5. Live
  end-to-end: `aitask_shadow_capture.sh --deep --any-pane %30` exits 0 with 137
  lines of real Codex pane content (was exit 1, zero bytes).

- **Sweep:** `[0-?]` had exactly one shell call site repo-wide
  (`aitask_shadow_capture.sh:168`, plus its mirror comment at :148). The Python
  occurrences (`monitor/ansi_utils.py:13`, `applink/content.py:79`) are
  unaffected — `re` matches ranges by code point, not collation.

- **Not covered here:** the six downstream installs each carry their own synced
  copy of the helper and were all broken. `thinking_app` and `thinking_backend`
  were patched by hand to unblock live tmux sessions; `aitasks_go`,
  `aitasks_mobile`, `timexchange` and `teamim` still carry the broken copy and
  will be fixed by the next framework release.
