---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, shadow, minimonitor, macos]
gates: [risk_evaluated]
created_at: 2026-08-30 11:25
updated_at: 2026-08-30 11:25
---

## Symptom

In minimonitor, pressing `c` (concern picker) on a window that has a live
shadow agent reports **"Could not read the shadow pane"**. Observed on
`thinkingapp:5` (window `agent-pick-339`) after upgrading the host to
omarchy 4.

The message is misleading: shadow *detection* works fine. The reported
suspicion — a changed tmux config breaking shadow-agent detection — is **not**
the cause.

## Root cause (reproduced, exit-code level)

`shadow_strip_ansi()` in `.aitask-scripts/aitask_shadow_capture.sh:162-168`
strips CSI sequences with:

```
sed -e "s|${esc}\[[0-?]*[ -/]*[@-~]||g"
```

`[0-?]` is a bracket **range**. POSIX specifies that a range's endpoints are
compared by the **locale's collating sequence**, not by byte value. Under
`en_US.UTF-8`, `?` collates *before* `0`, so `[0-?]` is a reversed range.

GNU sed 4.9 accepted it. **GNU sed 4.10 rejects it**:

```
$ printf 'x\n' | sed -e "s|$(printf '\033')\[[0-?]*[ -/]*[@-~]||g"
sed: -e expression #1, char 25: Invalid range end     # rc=1
$ printf 'x\n' | LC_ALL=C sed -e "s|...same...||g"
x                                                     # rc=0
```

Isolated per-bracket: `[ -/]` -> rc 0, `[@-~]` -> rc 0, **`[0-?]` -> rc 1**.
`[0-?]` is the sole offender.

Trigger confirmed in `/var/log/pacman.log`: `sed 4.10-1 -> 4.10-2` and
`glibc 2.44+r5 -> 2.44+r24`, both at `2026-08-29T20:18`, i.e. the omarchy 4
update.

### End-to-end reproduction

```
$ ./.aitask-scripts/aitask_shadow_capture.sh --deep --any-pane %30
sed: -e expression #3, char 25: Invalid range end
# exit 1, zero bytes on stdout
```

`monitor_core.capture_shadow_text()` sends the helper's stderr to `DEVNULL`
and returns `None` on a non-zero exit, so the real error was invisible and
surfaced only as the bland picker warning
(`minimonitor_app.py:4208`, and identically `monitor_app.py:3056`).

## Blast radius — larger than the concern picker

`shadow_strip_ansi` feeds `shadow_clean`, which is the **entire stdout path**
of `aitask_shadow_capture.sh` (the script is `set -euo pipefail`). So on any
host with sed 4.10 **every shadow capture is dead**, not just the picker:

- the shadow agent's own no-argument read of its followed pane (the shadow
  skill's runtime data source — the shadow can see nothing at all);
- the full monitor's concern picker (`monitor_app.py:3056`);
- minimonitor's picker and its refresh-tick auto-offer.

Unaffected: `--phase` (always exits 0); `capture_raw_tail` (pure tmux, no
sed); the Python-side `ANSI_CSI_RE` in `monitor/ansi_utils.py` and
`applink/content.py` — `re` matches ranges by code point, not collation.

## Already red

`tests/test_shadow_strip_ansi.sh` currently fails **6/9** on this host, every
failure carrying the exact `sed: -e expression #3, char 25: Invalid range end`
line. A deterministic pre-existing red proof — no new red proof needs
inventing, but confirm it goes green.

## macOS / BSD sed — same bug, latent

This is **not** a GNU-only regression. BSD sed goes through the same libc
`regcomp`, and macOS `en_US.UTF-8` also collates punctuation before digits, so
`[0-?]` should return `REG_ERANGE` there too. Strong likelihood this has been
broken on macOS all along; GNU sed 4.9 was the lenient outlier and 4.10 merely
brought Linux in line with BSD's long-standing behaviour.

**Unverified** — there is no Mac on this host and the repo has no macOS CI job
(only `Darwin` branches inside a few test helpers). Do not claim it as
measured; state it as the structural argument it is. One fix cures both.

## Fix direction

The repo already has an established `LC_ALL=C` byte-wise-determinism idiom
(`lib/task_utils.sh`, `lib/pid_anchor.sh`, `lib/stale_lock.sh`,
`aitask_task_worktree.sh`), so pinning collation is idiomatic here rather than
novel. Candidate approaches, to be weighed at planning time:

1. `LC_ALL=C sed …` inside `shadow_strip_ansi` — smallest change, restores the
   intended byte-value semantics, fixes GNU and BSD in one move. Note the
   input is UTF-8 terminal text; confirm `LC_ALL=C` does not corrupt
   multi-byte characters through a pure `s///` pass (it should not — sed is
   byte-transparent for non-matching bytes — but **measure it**, do not assume).
2. Enumerate the range instead of relying on collation
   (`[0-9:;<=>?]` for the CSI parameter bytes), which is locale-proof without
   changing the process locale.

Whichever is chosen, keep the **checked-mirror** contract with
`monitor/ansi_utils.py` intact: `tests/test_shadow_strip_ansi.sh` asserts the
shell and Python implementations agree, and that agreement is the reason this
was catchable at all.

## Documentation gap to close in the same change

`aidocs/framework/sed_macos_issues.md` has **no row** for locale-collated
bracket ranges — precisely the class of bug that just bit — and its "Safe
Features" section currently lists character classes in a way that implies
plain bracket expressions are portable. Add:

- an incompatibility row for ranges whose endpoints cross collation classes
  (digits/punctuation/letters), with `[0-?]` as the worked example;
- the guidance: either pin `LC_ALL=C` or enumerate the members explicitly;
- a note that `[[:alpha:]]`-style **classes** stay safe — it is **ranges** that
  are locale-dependent.

## Acceptance criteria

- `tests/test_shadow_strip_ansi.sh` passes 9/9 under the host's default
  `en_US.UTF-8` locale on GNU sed 4.10 (currently 6 failures).
- `./.aitask-scripts/aitask_shadow_capture.sh --deep --any-pane <shadow_pane>`
  exits 0 and emits non-empty cleaned text for a live shadow pane.
- Minimonitor's `c` concern picker on a window with a live shadow no longer
  reports "Could not read the shadow pane" (manual check against a real
  shadow, e.g. the `agent-pick-339` shape: followed `claude` pane + bound
  `codex` shadow pane).
- A red proof that the shell/Python mirror still holds: mutating one side
  makes `test_shadow_strip_ansi.sh` fail.
- Multi-byte (UTF-8) content in a captured pane survives the strip unmangled —
  asserted, not assumed, if approach (1) is taken.
- `aidocs/framework/sed_macos_issues.md` carries the new locale-range row.
- A repo-wide sweep confirms `[0-?]` (and any other cross-class bracket range
  in shell) has no remaining shell call site. Current sweep found exactly one:
  `aitask_shadow_capture.sh:168` (plus its mirror comment at :148).
