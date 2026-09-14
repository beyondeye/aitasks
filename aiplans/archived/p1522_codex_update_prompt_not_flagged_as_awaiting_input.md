---
Task: t1522_codex_update_prompt_not_flagged_as_awaiting_input.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1522 — Codex update-available prompt not flagged as awaiting input

## Context

`ait monitor` / `ait minimonitor` do not flag a followed Codex pane parked on the
startup **update-available prompt** as awaiting input. The task asks for a
bottom-anchored `codex` prompt pattern plus unit tests.

**Measured during planning (live, codex-cli 0.154.0, npm-managed via
`CODEX_MANAGED_BY_NPM=1`, private tmux socket, captured with the monitor's own
`capture-pane -p -e -S -200`):** the dialog is an **inline pre-TUI screen
(`alternate_on=0`) rendered TOP-aligned**. Its bottom hint line sits at row
-15 / -21 / -41 at 80x24 / 120x30 / 120x50, followed by 14 / 20 / 40 blank rows.
`_prompt_detection_text` (`monitor_core.py:186`) takes the last 6 lines with no
blank-trimming, so the detection window is **entirely blank** on every real pane.
A pattern alone would pass its unit test and be dead in production — the same
failure t1540 found for `claude_trust_folder`. The committed
`CODEX_UPDATE_PROMPT_RAW` fixture looks bottom-anchored only because its capture
was trimmed of trailing blank rows. Wording and row structure are identical to
the 0.146.0 fixture (header, release-notes line, three numbered options with the
`›` glyph on the selected one, blank row, hint).

**Global trim rejected, by measurement:** patching the shared window to drop
trailing blank rows makes 10 currently-green tests fail (8 in
`test_review_loop.py` — `ClaudePermissionBoundaryTests` geometry + t1557
`TypedAmendCannotFlipTheReportedKindTests`; 2 in
`test_minimonitor_concern_smoke.py`). Claude's dialogs carry trailing blank
rows, so a global trim would change which kind production reports for Claude.

**Approach:** a per-pattern opt-in. `PromptPattern` gains a defaulted
`skip_trailing_blank_rows: bool = False`; `classify_content` matches a pattern
that sets it against the last 6 rows *after dropping trailing blank rows*. Every
existing pattern keeps the byte-identical shared window. On the live captures
that trimmed window is exactly the measured dialog tail (blank, three option
rows, blank, hint).

Working on the current branch (profile `fast`).

## Implementation steps

1. **`.aitask-scripts/monitor/prompt_patterns.py`**
   - `PromptPattern`: add `skip_trailing_blank_rows: bool = False` with a comment:
     pre-TUI inline screens render top-aligned, so their bottom element sits
     above blank rows; per-pattern because a global trim was measured to change
     Claude's kind selection (t1522). All 4 existing constructions pass two
     positional args, so the default is compatible (`tests/test_pane_state_probe.py:120,124`,
     `tests/test_review_loop.py:1348,1374`).
   - Append to the `codex` group:
     ```python
     PromptPattern("codex_update_prompt",
                   re.compile(r"(?m)^[ \t]*(?:›[ \t]*)?3\. Skip until next version[ \t]*\n"
                              r"[ \t]*\n"
                              r"[ \t]*Press enter to continue[ \t]*$"),
                   skip_trailing_blank_rows=True),
     ```
     Comment block, matching the file's style: measured distances (above); why it
     anchors on the **last option row + hint** — option 1's label embeds the
     install command, which varies by install method, while option 3 is stable
     and is the row adjacent to the hint; a bare hint is generic prose and is
     shared with the Codex sign-in onboarding screen, whose last option differs
     (scope control); both rows must hold nothing but their label, with exactly
     the measured one blank row between them; `›` is the only selection marker recognised when
     present — optional in the regex on purpose, because the option-3 row carries
     it only while option 3 is selected (wording corrected in Change Request 1); KNOWN LIMIT: a verbatim reproduction is
     indistinguishable (rule 3). Also state which consumer gains coverage: the
     followed-pane window via the opt-in; the review loop already classified this
     pane `SHADOW_DIALOG` structurally and now also matches it in its whole-tail
     negative half (same verdict).

2. **`.aitask-scripts/monitor/monitor_core.py`**
   - `_prompt_detection_text(s, *, skip_trailing_blank_rows=False)`: the default
     path stays byte-identical (including `return s` when there are ≤6 lines);
     the opt-in pops trailing whitespace-only lines, then returns
     `"\n".join(lines[-_PROMPT_DETECTION_TAIL_LINES:])`.
   - `classify_content`: compute the trimmed text lazily, only once a pattern
     with the flag is reached; each pattern searches its own window;
     first-match-wins order unchanged. Update the docstring. `pane_state_probe`
     (sync sweep) and the applink pusher inherit this through `_classify_one` /
     the snapshot, with no change of their own. `awaiting_input_kind` is an
     open wire string, so no protocol bump.

3. **`.aitask-scripts/monitor/review_loop.py`** — add
   `("codex", "codex_update_prompt")` to `DELIBERATELY_UNANCHORED_KINDS`. Reason:
   a pre-TUI startup gate shown before the session has done any work; only one
   selection state has been captured, so no selection-stable boundary is
   measured, and UNKNOWN (no recheck) is the conservative answer (t1522).
   Without an entry, `test_every_armed_agent_kind_resolves` fails.

4. **`tests/test_prompt_detection.py`** (script-style checks, registered in `main()`):
   - `_check_codex_update_prompt_detected`: the stripped fixture on a `codex`
     pane; the fixture followed by 14 / 20 / 40 blank rows (the three measured
     geometries); option 2 or option 3 selected (the `›` moved); and an
     unresolved `node` pane (Codex's npm launcher) — all report
     `codex_update_prompt`. Bodies are derived from `fx.CODEX_UPDATE_PROMPT_RAW`
     rather than retyped (`import review_loop_fixtures as fx`, the idiom
     `tests/test_minimonitor_concern_action.py:1780` uses; works under both the
     script runner and pytest).
   - `_check_update_prompt_trim_is_load_bearing_and_per_pattern`: the same
     pattern copied via `dataclasses.replace(..., skip_trailing_blank_rows=False)`
     does **not** match the realistic tail, which proves the opt-in is needed.
     And a Claude help-bar body followed by ≥6 blank rows still reports no kind,
     which pins that the trim did not leak into the shared window.
   - `_check_codex_update_prompt_negative_controls` (codex pane, kind must not be
     `codex_update_prompt`): hint alone on its own line; hint inline in prose;
     bulleted hint; blockquoted option + hint; the option label quoted in prose
     above the hint; option row with trailing commentary; option row and hint
     with no blank row, and with two blank rows; a synthetic sign-in onboarding
     tail (same hint, different last option); the update prompt followed by >6
     lines of later output (scrollback); the permission footer still reports
     `codex_permission`.
   - `_check_codex_update_prompt_known_false_positive`: a verbatim reproduction
     still matches (pinned, like `_check_trust_pattern_known_false_positive`).
   - Extend `_check_cross_agent_negative_control` with `claude` / `opencode`
     panes showing the update-prompt body. Extend the characterization matrix
     body list and flips (`claude`→"", `opencode`→""). Add the name to
     `_check_all_patterns_flattens_per_agent_groups`, and add a docstring item.

5. **`tests/test_review_loop.py`**
   - Replace `test_the_unpatterned_update_prompt_is_a_dialog_not_typed_text` with
     `test_the_update_prompt_is_a_dialog_with_or_without_its_pattern`: exactly
     `{codex_update_prompt}` among the codex patterns matches the fixture, and
     `_codex_state` is `SHADOW_DIALOG`; with the codex list emptied (try/finally)
     it is **still** `SHADOW_DIALOG`, so the structural proof t1509 needed is
     kept, not lost.
   - `ConservativeDefaultSurvivesTests`: add
     `test_codex_update_prompt_is_unanchored_and_unknown` (mirrors the palette
     test; its reason contains `t1522`).

6. **`tests/test_minimonitor_concern_action.py`** — rename
   `test_the_unpatterned_update_prompt_arms_the_latch_too` →
   `test_the_update_prompt_arms_the_latch_too`, and fix its docstring (the latch
   arms from the verdict, and the verdict is structural with or without the
   pattern). The assertions are unchanged.

7. **`tests/review_loop_fixtures.py`** — update the provenance paragraph: the
   pattern now matches `CODEX_UPDATE_PROMPT_RAW`; the structural exclusion is
   still pinned with the pattern list disabled; the fixture was trimmed of
   trailing blank rows, and live the dialog is top-aligned (t1522 distances), so
   it does not represent followed-pane window geometry.

8. **`tests/test_workflow_phase_prompt_drift.sh`** — add `codex_update_prompt` to
   the `generic` leak list (a startup gate carries no workflow phase).

9. **`aidocs/framework/monitor_idle_and_prompt_detection.md`** — fix the stale
   codex inventory (it lists only `codex_yes_proceed`; it should list
   `codex_question`, `codex_permission`, `codex_yes_proceed`,
   `codex_update_prompt`). Under "Bottom-anchor it", add the pre-TUI
   top-aligned case and the `skip_trailing_blank_rows` opt-in, with why it is
   per-pattern (the measured global-trim regression), and note that it is the
   tool for `claude_trust_folder`'s geometry half too (its wording half is still
   separate). Describe the dialog in prose only, never as an option block.

### Post-phase (risk mitigations)

1. [live_update_prompt_probe] After steps 1–9 pass their tests, run a scratchpad
   probe on a **private** tmux socket (`tmux -L t1522verify`; kill only that
   server): a throwaway `CODEX_HOME` whose `version.json` reports
   `latest_version` newer than the installed codex with a current
   `last_checked_at`, `CODEX_MANAGED_BY_NPM=1`, no auth, and **never press
   Enter** (option 1 would run an install). At 80x24, 120x30 and 120x50:
   capture with `TmuxMonitor._capture_args` (the production args), feed the
   capture to `TmuxMonitor._finalize_capture` on a `PaneCategory.AGENT` pane
   with `current_command="codex"`, and assert
   `awaiting_input_kind == "codex_update_prompt"`; then send `Down` once and
   twice (selection only) and re-assert — 9 captures in total. Negative
   control: the same captures with the pattern's opt-in disabled report no
   kind.

   **Dismissal transition (the kind must CLEAR, not only fire).** The opt-in
   discards an arbitrary run of blank rows, so a post-dismissal screen that
   leaves the old option and hint rows as the last non-blank rows would hold the
   pane in awaiting-input state. Prove it does not:
   - **Safe dismissal only.** Move the selection with `Down` to option 2 (Skip)
     or option 3 (Skip until next version). **Before sending Enter, capture and
     assert the `›` row is NOT option 1**; if that guard fails, send nothing,
     kill the private session and abort. Option 3 writes `dismissed_version`, so
     recreate the throwaway `CODEX_HOME` (fresh `version.json`) for every rep.
   - **Sampling:** 0.25 s for 5 s after Enter, each sample through
     `_capture_args` → `_finalize_capture`, recording `awaiting_input_kind`,
     `#{alternate_on}`, and the row shape of the trimmed window.
   - **Ship criterion (blocking) — unauthenticated path, 120x30, two reps: one
     per safe dismissal action (option 2, option 3).** With no auth, Codex
     advances to its inline sign-in onboarding screen (same hint, different
     options). Pre-registered pass rule: within the window the kind stops being
     `codex_update_prompt` and **never reports it again**, and the
     post-dismissal sign-in captures report no `codex_update_prompt`; record
     time-to-clear per rep. **Stop rule:** if either rep keeps reporting
     `codex_update_prompt` after the dialog was dismissed, the opt-in is
     unsound as designed — do **not** ship; record the offending capture's row
     shape in the plan and return to planning.
   - **Best-effort (non-blocking, one time-boxed attempt):** (b) a throwaway
     home holding a **dummy** API key written by
     `printf 'sk-dummy' | CODEX_HOME=<tmp> codex login --with-api-key` (no real
     credential is ever copied; never substitute the user's real `~/.codex`),
     dismissed the same guarded way, to observe the advance towards the main
     TUI; plus one 80x24 repeat of the ship-criterion rep. Run each once; if a
     run is unreliable or cannot get past the dialog without network, record
     that as a measured limit and offer the authenticated-path check as a
     follow-up at Step 8c. A best-effort result never blocks shipping — **but**
     a best-effort run that *does* complete and shows the kind failing to clear
     triggers the stop rule like the ship criterion.

   Record every result (distances, kinds, time-to-clear, `alternate_on`) in
   Final Implementation Notes. Delete the throwaway `CODEX_HOME`s afterwards.

## Verification

- `python3 tests/test_prompt_detection.py`
- `bash tests/test_workflow_phase_prompt_drift.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the final
  `PYTHON SUITE:` line (with `set -o pipefail` if piped).
- `shellcheck` is not applicable (no `.aitask-scripts/*.sh` edits).
- Live end-to-end check: Post-phase step 1 `[live_update_prompt_probe]`.

Post-implementation: Step 9 (Post-Implementation) — current-branch mode, so there
is no merge; the build is verified per `verify_build`, then archival.

## Risk

### Code-health risk: low
- `classify_content` is the per-tick hot path shared by monitor, minimonitor, the sync-sweep holder probe (`lib/pane_state_probe.py`) and applink; a default path that is not byte-identical would silently shift existing kinds · severity: low · → mitigation: none — pinned by the existing characterization matrix, the t1540/t1557 geometry tests, the finalize-offload golden, and step 4's scope-guard check
- Rewriting t1509's premise test could weaken the structural-exclusion proof · severity: low · → mitigation: none — the rewrite asserts `SHADOW_DIALOG` with the codex pattern list disabled

### Goal-achievement risk: low
- The pattern is proven live only with option 1 selected; other selection states are covered by synthetic bodies only, and a future Codex release can change wording or geometry and leave the pattern dead while every unit test stays green (t1540's `claude_trust_folder` lesson) · severity: low (residual — addressed by inline post-phase live_update_prompt_probe for today's version and every selection state; future-release drift stays a documented limit) · → mitigation: inline post-phase live_update_prompt_probe
- Dismissal transition (raised in plan review): because the opt-in skips an arbitrary run of blank rows, a sparse or transient post-dismissal screen could leave the dismissed dialog's option and hint rows as the last non-blank rows and falsely hold the pane in awaiting-input state; no probe so far pressed Enter, so the clearing half was unproven · severity: low (residual — addressed by inline post-phase live_update_prompt_probe's guarded unauthenticated dismissal check, the blocking ship criterion with a pre-registered stop rule; the authenticated main-TUI advance is best-effort and, if unavailable, becomes a Step 8c follow-up) · → mitigation: inline post-phase live_update_prompt_probe
- The sync sweep's `--require-waiting` gate will now read a Codex holder parked on its update prompt as `waiting_codex_update_prompt` and may commit its files on its behalf · severity: low · → mitigation: none — the signal is truthful, and the gate's contract is "parked on a prompt"

### Planned mitigations
- timing: post-phase | name: live_update_prompt_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risks 1 and 2 (pattern proven live only in one selection state; dismissal transition unproven) | desc: Drive the real TmuxMonitor capture+classify path against a live Codex update prompt at three geometries and all three selection states, with an opt-in-disabled negative control, plus a guarded dismissal check (never Enter on option 1) — unauthenticated at 120x30 as the blocking ship criterion, authenticated-dummy-key and 80x24 as best-effort — asserting the kind clears and stays cleared

## Post-phase results — [live_update_prompt_probe]

Run **2026-09-14 13:19** against the **final** code (after Change Request 1's
comment edit): codex-cli 0.154.0 (npm-managed via `CODEX_MANAGED_BY_NPM=1`),
tmux 3.7c, private socket `tmux -L t1522verify -f /dev/null`, throwaway
`CODEX_HOME`s under the scratchpad (deleted afterwards; no real credential
used). Every capture went through the production path —
`TmuxMonitor._capture_args` → `TmuxMonitor._finalize_capture` on an AGENT pane
with `current_command="codex"`, `pane_pid=0`. Base HEAD `b92aebc20`.

Code under test, as git blob ids (verifiable against the t1522 commit with
`git ls-tree <commit> -- <path>`):

- `df814a2d91d49351543bf9f05db7c30341d7b6a9` `.aitask-scripts/monitor/prompt_patterns.py`
- `3f18bd359bdc7c2e05cc3948edd34df5dc0d1524` `.aitask-scripts/monitor/monitor_core.py`
- `3776d2f1bce4df6fa23b5ead7818864a45bc8350` `.aitask-scripts/monitor/review_loop.py`

Probe script: Appendix A below, byte-identical to the run (sha256 prefix
`b02b935d177e5f68`). A first run during implementation, before the comment-only
edits, produced identical results.

**Entry — 9/9 PASS; opt-in-off negative control 9/9 PASS**

| geometry | selected option | kind | kind with opt-in off | `alternate_on` | hint row |
|---|---|---|---|---|---|
| 80x24 | 1, 2, 3 | `codex_update_prompt` ×3 | `""` ×3 | 0 | -15 |
| 120x30 | 1, 2, 3 | `codex_update_prompt` ×3 | `""` ×3 | 0 | -21 |
| 120x50 | 1, 2, 3 | `codex_update_prompt` ×3 | `""` ×3 | 0 | -41 |

**Dismissal — sampled every 0.25 s for 5 s after Enter.** In every rep the guard
confirmed from a capture that `›` was on the intended safe option (never option 1)
before Enter was sent.

| run | class | kind before Enter | time to clear | ever returns? | screen reached (trimmed window) | final kind |
|---|---|---|---|---|---|---|
| ship_opt2 — 120x30, Skip | **blocking** | `codex_update_prompt` | 0.25 s (first sample) | no | sign-in onboarding | `""` |
| ship_opt3 — 120x30, Skip until next version | **blocking** | `codex_update_prompt` | 0.25 s (first sample) | no | sign-in onboarding | `""` |
| best_dummykey — 120x30, Skip, dummy API key | best-effort | `codex_update_prompt` | 0.25 s | no | directory-trust screen — the dismissed dialog's text is **still in scrollback** above it | `""` |
| best_80x24 — 80x24, Skip | best-effort | `codex_update_prompt` | 0.25 s | no | sign-in onboarding | `""` |

**Ship criterion: PASS. Stop rule: not tripped** (no best-effort run showed the
kind failing to clear). `best_dummykey` is the direct answer to the dismissal
concern: stale dialog text left in scrollback does not hold the kind, because the
trimmed window ends on the next screen's rows.

Measured limits:

- The authenticated **main TUI** was not reached: with a dummy key Codex advanced
  to its directory-trust screen (still inline, `alternate_on=0`). Clearing is
  proven into both inline screens that follow the dialog; into the main TUI it
  rests on structure (the main TUI replaces the screen, so the dialog cannot be
  the trimmed tail) — not measured. Offered as a Step 8c follow-up.
- Codex's sign-in and directory-trust screens are awaiting-input screens too,
  ending with the same hint over different options; no pattern matches them
  (outside this task's scope). Candidate for Step 8b.

## Post-Review Changes

### Change Request 1 (2026-09-14 13:19)
- **Requested by user:** (1) record the live probe's evidence so the post-phase
  can be verified independently rather than inferred from a source comment;
  (2) reword the matcher comment — `›` is recognised when present, not required.
- **Changes made:** re-ran the probe against the final code and recorded it above,
  bound to blob ids, with the script in Appendix A; reworded the `›` bullet in the
  `codex_update_prompt` comment (optional on purpose: the option-3 row carries it
  only while selected, so requiring it would break two pinned selection states);
  corrected the same stale wording in step 1 of this plan.
- **Files affected:** `.aitask-scripts/monitor/prompt_patterns.py` (comment only),
  this plan.

## Appendix A — probe script (as run)

```python
#!/usr/bin/env python3
"""t1522 post-phase [live_update_prompt_probe].

Drives a LIVE codex update-available prompt on a PRIVATE tmux socket and runs
every capture through the production capture args + classifier
(TmuxMonitor._capture_args / _finalize_capture).

Safety: throwaway CODEX_HOMEs under the scratchpad (never ~/.codex), no real
credential, and Enter is only ever sent after a capture proves the selection
is NOT option 1 (option 1 runs an install).

Sections:
  entry     — 3 geometries x 3 selection states, kind must be
              codex_update_prompt; control: same captures with the opt-in off
              must report no kind.
  dismiss   — BLOCKING ship criterion: unauthenticated, 120x30, one rep per
              safe dismissal action (option 2, option 3).
  best      — best-effort: dummy-API-key home (120x30, option 2) and an 80x24
              unauthenticated repeat (option 2).
"""
from __future__ import annotations

import dataclasses
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO = "/home/ddt/Work/aitasks"
sys.path.insert(0, f"{REPO}/.aitask-scripts")
from monitor.ansi_utils import strip_ansi  # noqa: E402
from monitor.prompt_patterns import all_patterns  # noqa: E402
from monitor.tmux_monitor import (  # noqa: E402
    PaneCategory,
    TmuxMonitor,
    TmuxPaneInfo,
)

SP = os.path.dirname(os.path.abspath(__file__))
SOCK = "t1522verify"
CODEX = "/home/ddt/.local/share/mise/installs/codex/latest/bin/codex"
WORK = f"{SP}/work"
KIND = "codex_update_prompt"
DIALOG_MARK = "Skip until next version"


def tmux(*args: str, check: bool = True) -> str:
    r = subprocess.run(["tmux", "-L", SOCK, "-f", "/dev/null", *args],
                       capture_output=True, text=True, timeout=15)
    if check and r.returncode != 0:
        raise RuntimeError(f"tmux {args!r} rc={r.returncode}: {r.stderr.strip()}")
    return r.stdout


def fresh_home(tag: str, dummy_key: bool = False) -> str:
    home = f"{SP}/cxhome_{tag}"
    shutil.rmtree(home, ignore_errors=True)
    os.makedirs(home)
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000000000Z")
    with open(f"{home}/version.json", "w") as f:
        json.dump({"latest_version": "0.999.0", "last_checked_at": now}, f)
    if dummy_key:
        r = subprocess.run([CODEX, "login", "--with-api-key"],
                           input="sk-dummy-t1522-not-a-real-key\n", text=True,
                           env={**os.environ, "CODEX_HOME": home},
                           capture_output=True, timeout=30)
        print(f"  [dummy login rc={r.returncode}] "
              f"{(r.stdout + r.stderr).strip()[:160]!r}")
    return home


_MON = TmuxMonitor(session="t1522", idle_threshold=0.05)


def capture() -> str | None:
    r = subprocess.run(["tmux", "-L", SOCK, "-f", "/dev/null",
                        *_MON._capture_args("p")],
                       capture_output=True, text=True, timeout=15)
    return r.stdout if r.returncode == 0 else None


def pane(w: int, h: int) -> TmuxPaneInfo:
    return TmuxPaneInfo(window_index="0", window_name="agent-t1522",
                        pane_index="0", pane_id="%probe", pane_pid=0,
                        current_command="codex", width=w, height=h,
                        category=PaneCategory.AGENT, session_name="t1522")


_OPT_OFF = [dataclasses.replace(p, skip_trailing_blank_rows=False)
            if p.skip_trailing_blank_rows else p for p in all_patterns()]


def classify(content: str, w: int, h: int, patterns=None) -> str:
    kwargs = {} if patterns is None else {"prompt_patterns": patterns}
    mon = TmuxMonitor(session="t1522", idle_threshold=0.05, **kwargs)
    return mon._finalize_capture(pane(w, h), content).awaiting_input_kind


def selected_option(content: str) -> int | None:
    for line in strip_ansi(content).splitlines():
        m = re.match(r"›\s*([123])\.", line.strip())
        if m:
            return int(m.group(1))
    return None


def shape(content: str) -> list[list[str]]:
    """First two words of each row in the trimmed 6-row window."""
    lines = strip_ansi(content).splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    return [line.split()[:2] for line in lines[-6:]]


def hint_row(content: str) -> int | None:
    lines = strip_ansi(content).splitlines()
    idx = [i for i, line in enumerate(lines) if "Press enter to continue" in line]
    return (idx[-1] - len(lines)) if idx else None


def alt_on() -> str:
    return tmux("display", "-p", "-t", "p", "#{alternate_on}", check=False).strip()


def start(w: int, h: int, home: str) -> str:
    tmux("kill-session", "-t", "p", check=False)
    tmux("new-session", "-d", "-s", "p", "-x", str(w), "-y", str(h), "-c", WORK,
         f"env CODEX_HOME={home} CODEX_MANAGED_BY_NPM=1 {CODEX}")
    tmux("set-option", "-t", "p", "remain-on-exit", "on", check=False)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 12:
        c = capture()
        if c and DIALOG_MARK in strip_ansi(c) and selected_option(c):
            return c
        time.sleep(0.25)
    raise RuntimeError("update prompt never appeared")


def entry_matrix() -> list[dict]:
    out = []
    for w, h in ((80, 24), (120, 30), (120, 50)):
        c = start(w, h, fresh_home(f"entry_{w}x{h}"))
        for step in range(3):
            if step:
                tmux("send-keys", "-t", "p", "Down")
                time.sleep(0.5)
                c = capture() or ""
            out.append(dict(geo=f"{w}x{h}", selected=selected_option(c),
                            kind=classify(c, w, h),
                            kind_optin_off=classify(c, w, h, _OPT_OFF),
                            alt=alt_on(), hint_row=hint_row(c)))
        tmux("kill-session", "-t", "p", check=False)
    return out


def dismiss_rep(w: int, h: int, option: int, tag: str,
                dummy_key: bool = False) -> dict:
    assert option in (2, 3), "only safe dismissal options are allowed"
    c = start(w, h, fresh_home(tag, dummy_key))
    for _ in range(option - 1):
        tmux("send-keys", "-t", "p", "Down")
        time.sleep(0.4)
    c = capture() or ""
    sel = selected_option(c)
    if sel != option or sel == 1:
        tmux("kill-session", "-t", "p", check=False)
        return dict(tag=tag, guard="REFUSED", selected=sel,
                    note="selection not on the intended safe option — Enter NOT sent")
    pre = classify(c, w, h)
    tmux("send-keys", "-t", "p", "Enter")
    t0 = time.monotonic()
    samples = []
    while time.monotonic() - t0 < 5.0:
        time.sleep(0.25)
        cap = capture()
        if cap is None:
            samples.append(dict(t=round(time.monotonic() - t0, 2), kind="<no pane>"))
            continue
        samples.append(dict(t=round(time.monotonic() - t0, 2),
                            kind=classify(cap, w, h), alt=alt_on(),
                            dialog_text=DIALOG_MARK in strip_ansi(cap),
                            window=shape(cap)))
    tmux("kill-session", "-t", "p", check=False)
    kinds = [s["kind"] for s in samples]
    first_clear = next((i for i, k in enumerate(kinds) if k != KIND), None)
    passed = (pre == KIND and first_clear is not None
              and all(k != KIND for k in kinds[first_clear:]))
    return dict(tag=tag, geo=f"{w}x{h}", option=option, dummy_key=dummy_key,
                guard="ok", pre_kind=pre, passed=passed,
                time_to_clear=(samples[first_clear]["t"]
                               if first_clear is not None else None),
                final=samples[-1] if samples else None,
                kinds=kinds)


def main() -> int:
    os.makedirs(WORK, exist_ok=True)
    res: dict = {}
    try:
        res["entry"] = entry_matrix()
        res["dismiss"] = [dismiss_rep(120, 30, 2, "ship_opt2"),
                          dismiss_rep(120, 30, 3, "ship_opt3")]
        res["best"] = []
        for args in ((120, 30, 2, "best_dummykey", True),
                     (80, 24, 2, "best_80x24", False)):
            try:
                res["best"].append(dismiss_rep(*args))
            except Exception as e:  # best-effort: record, never block
                res["best"].append(dict(tag=args[3], error=repr(e)))
    finally:
        tmux("kill-server", check=False)
        for d in os.listdir(SP):
            if d.startswith("cxhome_"):
                shutil.rmtree(os.path.join(SP, d), ignore_errors=True)
    with open(f"{SP}/t1522_probe_results.json", "w") as f:
        json.dump(res, f, indent=1, default=str)

    entry_ok = all(r["kind"] == KIND and r["kind_optin_off"] == ""
                   for r in res["entry"])
    ship_ok = all(r.get("guard") == "ok" and r.get("passed")
                  for r in res["dismiss"])
    best_fail = [r["tag"] for r in res["best"]
                 if r.get("guard") == "ok" and r.get("passed") is False]
    print("ENTRY:", "PASS" if entry_ok else "FAIL")
    for r in res["entry"]:
        print(f"  {r['geo']:>7} sel={r['selected']} kind={r['kind']!r} "
              f"optin_off={r['kind_optin_off']!r} alt={r['alt']} hint_row={r['hint_row']}")
    print("SHIP (blocking):", "PASS" if ship_ok else "FAIL")
    for r in res["dismiss"] + res["best"]:
        if "error" in r:
            print(f"  {r['tag']}: ERROR {r['error']}")
            continue
        if r.get("guard") != "ok":
            print(f"  {r['tag']}: GUARD {r['guard']} sel={r.get('selected')}")
            continue
        fin = r["final"] or {}
        print(f"  {r['tag']}: pre={r['pre_kind']!r} passed={r['passed']} "
              f"clear_at={r['time_to_clear']}s final_kind={fin.get('kind')!r} "
              f"final_alt={fin.get('alt')} final_dialog_text={fin.get('dialog_text')} "
              f"final_window={fin.get('window')}")
    print("BEST-EFFORT stop-rule trips:", best_fail or "none")
    return 0 if (entry_ok and ship_ok and not best_fail) else 1


if __name__ == "__main__":
    sys.exit(main())
```

## Final Implementation Notes
- **Actual work done:** As planned. `PromptPattern.skip_trailing_blank_rows` opt-in (default off) and the `codex_update_prompt` pattern in `prompt_patterns.py`; `_prompt_detection_text` gained the opt-in trim and `classify_content` builds the trimmed window lazily, only for opted-in patterns, with the default path byte-identical (`monitor_core.py`); review-loop exemption for the new kind (`review_loop.py`); 4 new script checks plus matrix / cross-agent / flatten extensions (`test_prompt_detection.py`, 26/26); t1509's premise test re-grounded (still `SHADOW_DIALOG` with the codex pattern list emptied) plus an exemption test (`test_review_loop.py`); latch-test rename (`test_minimonitor_concern_action.py`); fixture provenance corrected (`review_loop_fixtures.py`); phase-leak guard list (`test_workflow_phase_prompt_drift.sh`, 17/17); doc inventory fixed and the "Bottom-anchor it" rule extended to top-aligned pre-TUI screens (`monitor_idle_and_prompt_detection.md`). The post-phase live probe ran against the final code and is recorded above.
- **Deviations from plan:** None in approach. Implementation details: `_codex_snap` builds its panes with `pane_pid=0` via `dataclasses.replace`, so the `node` fail-open case is host-independent without depending on t1763's fixture fix (on origin/main, not yet on local main); the new `main()` entries are appended at the end of the list to stay clear of t1763's hunk. The pattern comment additionally records the measured dismissal-clearing evidence, and its `›` bullet was corrected in Change Request 1.
- **Issues encountered:** (1) The first planning probe reached Codex's sign-in screen, not the update prompt: the mise-installed native binary offers no update action; `CODEX_MANAGED_BY_NPM=1` makes the dialog render. (2) Remote drift at the checkpoint: origin/main was 2 commits ahead touching `monitor_core.py` and `test_prompt_detection.py` (t1773, t1763), while local main is 10 commits ahead (diverged) and the tree held another session's uncommitted board work — so the agreed ff-only pull was refused rather than forced. Continued on local main and proved with `git merge-tree` (a throwaway index and commit object; the real index untouched) that local main plus these changes merges cleanly with origin/main. (3) The full suite reported 4 failures, all in `tests/test_parallel_admission_collect.py`; they reproduce identically on a `git archive` of HEAD without t1522 and are the clock-dependent fixture that t1763 fixes on origin/main — they resolve when local main integrates it. Everything else passed (7479 + 11 serial).
- **Key decisions:** A per-pattern opt-in over a global trim (a global trim was measured to break 10 Claude kind-by-pane-height tests). Anchor = last option row + hint with exactly one blank row between (option 1's label embeds the install command; the hint alone is shared with the sign-in and directory-trust screens). Exempt the kind from review-loop boundaries (UNKNOWN) rather than ship an unmeasured boundary. Blocking verification = the guarded unauthenticated dismissal; the authenticated and 80x24 runs best-effort.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_core.py:676 — capture_raw_tail's docstring states every supported agent CLI runs on the alternate screen with no scrollback, so the capture is the whole visible pane; Codex's pre-TUI screens (update prompt, sign-in onboarding, directory-trust) were measured at alternate_on=0 with scrollback, so that premise does not hold for them`
  - `.aitask-scripts/monitor/prompt_patterns.py:217 — Codex's sign-in onboarding and directory-trust screens are awaiting-input screens (same "press enter to continue" hint over different options, top-aligned pre-TUI) that no pattern matches, so a followed Codex pane parked on either reads idle`
