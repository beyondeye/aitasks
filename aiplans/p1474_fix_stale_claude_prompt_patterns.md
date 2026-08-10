---
Task: t1474_fix_stale_claude_prompt_patterns.md
Worktree: (none — current-branch mode, profile `fast`)
Branch: main
Base branch: main
Output branch: main
---

# t1474 — Fix stale Claude prompt patterns

## Context

`ait monitor` / `ait minimonitor` flag an agent as "waiting on you" by regex-matching
its captured pane text against `.aitask-scripts/monitor/prompt_patterns.py`. t1420
measured four live Claude Code 2.1.226 widgets through the monitor's own capture path
and found three defects; it fixed only the two its own feature needed and spawned this
task for the rest:

1. `claude_proceed`'s comment claims it covers the "plan-mode and tool-permission
   confirmation prompt". It does not, and t1420 measured it matching nothing.
2. The first-run **workspace-trust dialog** is matched by nothing, so an agent blocked
   on it reads as **idle** — the user is never told it is waiting.
3. `strip_ansi` strips only CSI sequences. `tmux capture-pane -e` re-emits OSC 8
   hyperlinks verbatim, so URLs survive into `compare_value` and every text match built
   on it.

### Ground truth gathered during planning (independent of t1420's captures)

Grepping the installed `claude` 2.1.226 binary and probing tmux live:

- **`Do you want to proceed?` is still live.** It is the default `question` prop of
  Claude Code's permission-dialog component and is rendered verbatim by the
  Bash/command permission prompt and by the Read/Edit file permission prompt. What
  makes it *effectively* dead is structural, not wording: matching only scans the last
  `_PROMPT_DETECTION_TAIL_LINES` (6) lines, and that question renders **above** the
  option list, so it normally falls outside the window — the bottom-anchored
  `claude_help_bar` is what actually fires for those dialogs. **User decision: keep the
  pattern, fix the comment.** The regex is unchanged.
- **Workspace-trust dialog confirmed.** It renders `Accessing workspace:`, the cwd,
  `Quick safety check: Is this a project you created or one you trust? …`,
  `Claude Code will be able to read, edit, and execute files here.`, and the confirm
  labels `Yes, I trust this folder` / `No, exit`. Footers are composed from chord
  components at render time, so only question and label text exists as literals.
- **OSC 8 confirmed live.** `tmux capture-pane -p -e` returns
  `ESC]8;;<url>ESC\ <text> ESC]8;;ESC\` byte-for-byte (probed on tmux 3.7b); today's
  `strip_ansi` leaves all of it.
- **A canonical OSC regex already exists** in `.aitask-scripts/applink/content.py:81`
  (`_OSC_SEQ`) — the new strip mirrors its shape.

Outcome: the monitor stops reporting a trust-blocked agent as idle, pane text used for
matching is free of hyperlink markup, and the pattern registry stops documenting a
behaviour it does not have.

## Implementation

### Pre-phase (risk mitigations)

1. `[pin_osc_fixture_from_live_tmux]` **Before editing `strip_ansi`**, capture the test
   fixture from real tmux rather than writing escape bytes by hand. Start a scratch tmux
   server on a private socket (`env -u TMUX tmux -L <sock> -f /dev/null new-session -d
   …`), have the pane `printf` an OSC 8 hyperlink
   (`ESC]8;;https://example.com/x ESC\ LINKTEXT ESC]8;; ESC\`), read it back with
   `capture-pane -p -e`, and write those exact bytes to
   `tests/fixtures/osc8_capture_pane.txt`. Kill the server afterwards. Then write the
   first check of `tests/test_ansi_utils.py` against that fixture, asserting **both**
   directions — the hyperlink markup is gone **and** `LINKTEXT` survives (the second
   half is the guard against a regex that swallows visible text) — and confirm it
   **fails** against the current CSI-only `strip_ansi` before changing anything. A
   check that cannot fail proves nothing. Only then proceed to step 1 below.

### 1. `.aitask-scripts/monitor/ansi_utils.py` — strip OSC alongside CSI

Add `ANSI_OSC_RE` and apply it before the CSI pass:

```python
# OSC sequence: ESC ] <body> ST, where ST is BEL (\x07) or ESC \ .
# `tmux capture-pane -p -e` re-emits OSC 8 hyperlinks verbatim
# (ESC]8;;<url>ESC\ text ESC]8;;ESC\), so a CSI-only strip left the URL in the
# text and polluted compare_value and every match built on it (t1474).
# The body is BOUNDED (`[^\x07\x1b]*`) rather than a non-greedy `.*?`: an OSC
# body can never legitimately contain BEL or ESC, so a truncated / unterminated
# sequence is left intact instead of swallowing the visible text after it —
# eating a footer would turn a blocked pane back into a silent "idle" one.
# `applink/content.py::_OSC_SEQ` uses the `.*?` form because it *parses* the
# body into hyperlink spans; this one only strips, so it takes the fail-safe bound.
ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def strip_ansi(s: str) -> str:
    """Remove OSC and CSI escape sequences, preserving the visible text."""
    return ANSI_CSI_RE.sub("", ANSI_OSC_RE.sub("", s))
```

`ANSI_CSI_RE` keeps its name and value — `aitask_shadow_capture.sh` and
`monitor_core.py:151` reference it by name.

### 2. `.aitask-scripts/monitor/prompt_patterns.py` — one new pattern, one corrected comment

Insert `claude_trust_folder` in the `claude` list **after `claude_plan_approval` and
before `claude_proceed`** (matching is first-wins; the specific widgets stay ahead of
the generic confirmations):

```python
# Both option lines of the workspace-trust confirm dialog, adjacent, each
# holding nothing but its (optionally pointer-prefixed) label.
_TRUST_YES = r"^[ \t]*(?:❯[ \t]*)?Yes, I trust th(?:is folder|ese settings)[ \t]*$"
_TRUST_NO = (r"^[ \t]*(?:❯[ \t]*)?"
             r"No, (?:exit(?: Claude Code)?|continue without these permissions)[ \t]*$")

PromptPattern("claude_trust_folder",
              re.compile(rf"(?m){_TRUST_YES}\n{_TRUST_NO}|{_TRUST_NO}\n{_TRUST_YES}")),
```

Two mechanical constraints, both verified by compiling and exercising the pattern during
planning rather than by inspection:

- **`(?m)` appears exactly once, at the very start.** Repeating it in the second
  alternative is a hard `re.error: global flags not at the start of the expression` on
  modern Python (checked on 3.14) — the pattern would not import, taking the whole
  monitor down with it.
- **`exit(?: Claude Code)?`** — the settings-trust dialog's cancel label is
  `No, exit Claude Code`. With `[ \t]*$` closing the line, a bare `exit` alternative
  silently failed to match that variant; the `these settings` arm would have been dead
  on arrival.

Four deliberate choices, all in the comment:

- **Anchored on the confirm labels**, not on the footer (`Enter to confirm · Esc to
  cancel`) that t1420 measured. The labels are the bottom-most lines of the dialog, so
  they land inside the 6-line window whichever way the question wraps, and the footer is
  shared with unrelated confirm dialogs (terms acceptance) that this pattern's name
  would misdescribe.
- **No `Quick safety check` alternative.** A bare phrase match would classify *any*
  pane whose last six lines quote it as a live dialog — and this task itself puts that
  phrase into the plan file, the framework docs and the test fixtures, so an agent
  displaying its own plan would self-trigger a false "waiting on you". It also buys
  nothing: the question renders several lines *above* the labels, so a rendering that
  pushes the labels off-window has already pushed the question off too.
- **Line-anchored, with `❯` as the only accepted marker.** The dialog renders the label
  at the start of its own line, prefixed by `❯` when focused and by a space when not.
  `❯` is the only marker Claude Code can emit: it comes from a figures-style table
  (`pointer:"❯"`, with `" "` for unfocused) and the binary carries **no**
  `fallbackSymbols` / `isUnicodeSupported` / `mainSymbols` table, so there is no ASCII
  degradation path. ASCII `>` is therefore deliberately **not** accepted — it is the
  Markdown blockquote prefix, and `> Yes, I trust this folder` in quoted prose would
  otherwise fire. A numeric prefix (`1.`) is not accepted either, for the same reason:
  this dialog is a pointer-select, not a numbered menu, so allowing it would only open
  the door to numbered lists in plans and checklists.
- **Constrained to the option-line geometry, not to "both phrases appear nearby".** An
  earlier draft allowed `[\s\S]{0,120}?` between the two labels; that is not structural
  — arbitrary prose and newlines fit in 120 characters, so any document discussing the
  dialog would satisfy it. The shipped form requires the two labels on **adjacent
  lines**, each line containing *nothing* but the label and its optional pointer/padding
  (`[ \t]*$` closes both). Prose loses on every count: it quotes the label mid-sentence,
  prefixes it with `-`/`>`/`1.`, or leaves trailing words on the line. Both orders are
  accepted because which label carries `❯` depends on the dialog's initial focus, and
  the render order of the two options was not measurable from the binary.

**Irreducible residue — state this in the comment.** No text matcher can separate the
dialog from a *verbatim, geometry-faithful reproduction* of it: a pane displaying this
task's own test fixture, or a doc quoting the widget as a two-line block, is the dialog
as far as the captured text is concerned. That case is accepted rather than solved — the
signal is advisory, the cost is a transient wrong badge on one pane, and the alternative
is the miss this task exists to fix. The practical consequence is a **documentation
rule**, carried in the comment and in the framework doc: describe these labels inline in
prose, never as a copied two-line option block. This plan's own doc changes follow it.

The `these settings` arm covers the sibling settings-trust dialog, which blocks the
agent identically.

Rewrite the `claude_proceed` comment to state what was verified: it is the permission
dialog's **default** question (Bash/command + the Read/Edit fallback), it is **not** the
plan-mode prompt (ExitPlanMode says "Would you like to proceed?" and is
`claude_plan_approval`'s job), and it rarely fires because it renders above the option
list and so usually sits outside `_PROMPT_DETECTION_TAIL_LINES` — retained as a cheap
backstop for short renderings.

### 3. `.aitask-scripts/aitask_shadow_capture.sh` — mirror the OSC strip

`shadow_strip_ansi` (line 148) documents itself as mirroring the Python regex. The tmux
path omits `-e` and sees no OSC, but the `-` **stdin** form cleans whatever the user
pasted — which can be a `capture-pane -e` transcript. Add two OSC expressions ahead of
the CSI one, as **separate `-e` expressions**: `\|` alternation in a BRE is a GNU
extension that BSD sed rejects (`aidocs/framework/sed_macos_issues.md`).

```bash
shadow_strip_ansi() {
    local esc bel
    esc=$(printf '\033')
    bel=$(printf '\007')
    sed -e "s|${esc}\][^${bel}${esc}]*${bel}||g" \
        -e "s|${esc}\][^${bel}${esc}]*${esc}\\\\||g" \
        -e "s|${esc}\[[0-?]*[ -/]*[@-~]||g"
}
```

Update its comment to name `monitor/ansi_utils.py` (both regexes) as the mirrored source.

### 4. Keep the drift guards complete

- `.aitask-scripts/lib/workflow_phase.py:112` — the comment enumerates the kinds that
  are *deliberately absent* from `NATIVE_KIND_PHASE` because a generic confirmation
  carries no workflow phase. Add `claude_trust_folder` to that list (a trust dialog is
  not a workflow phase).
- `tests/test_workflow_phase_prompt_drift.sh:126` — add `claude_trust_folder` to the
  `generic` list so the "no generic confirmation carries a phase" guard covers it.

### Post-phase (risk mitigations)

1. `[parity_test_shadow_strip_mirror]` Add `tests/test_shadow_strip_ansi.sh` so the bash
   mirror stops being covered by manual verification only. Details in **Tests** below.

## Tests

### `tests/fixtures/osc8_capture_pane.txt` (new)

The real bytes produced by the pre-phase capture, shared by both new test modules so
the Python implementation and its bash mirror are proven against **one** fixture rather
than two hand-copied strings.

### `tests/test_ansi_utils.py` (new)

There is no test for the shared `ansi_utils` module today. New script-style module with
the repo's `main()` + `ScriptChecksTest` wrapper (same shape as
`tests/test_prompt_detection.py`) so both the pytest and `unittest discover` lanes
collect it:

1. CSI stripping still works (regression guard on the unchanged behaviour).
2. OSC 8 with **ST** terminator: markup removed, `LINKTEXT` preserved.
3. OSC with **BEL** terminator (`ESC]0;title BEL`) removed.
4. **Fail-safe:** an unterminated `ESC]8;;http://x` is left intact and the text after it
   is not eaten.
5. **Real-bytes fixture:** `tests/fixtures/osc8_capture_pane.txt`, asserted to strip to
   plain text with `LINKTEXT` intact and no `example.com` left behind.
6. Negative control: text with no escapes is returned unchanged.

### `tests/test_prompt_detection.py` (extend)

- `_check_trust_dialog_detected` — four positives, all confirmed to match during
  planning: focus on the confirm option, focus on the cancel option, the settings-trust
  variant (`these settings` + `No, exit Claude Code`), and the
  `No, continue without these permissions` cancel variant. At least one must be embedded
  in a realistic ≥6-line pane tail so the check exercises
  `_PROMPT_DETECTION_TAIL_LINES` windowing, not just the regex. Each sets
  `awaiting_input_kind == "claude_trust_folder"`.
- `_check_trust_pattern_negative_controls` — five panes that must **not** match, each
  targeting a specific way the matcher could over-fire:
  1. agent output quoting `Quick safety check: Is this a project you created or one you
     trust?` verbatim in prose — the phrase this task adds to its own plan and docs;
  2. the confirm label quoted mid-sentence (`the button reads "Yes, I trust this
     folder" so we anchor on it`) — proves the line anchor discriminates;
  3. a Markdown **blockquote** (`> Yes, I trust this folder`) directly followed by
     `> No, exit` — the case ASCII `>` in the marker class would have let through, and
     the reason it was removed;
  4. a Markdown bullet / numbered list (`- Yes, I trust this folder` /
     `1. Yes, I trust this folder`) — the shape a plan or checklist would use;
  5. the confirm label line-anchored but with **no** cancel label anywhere after it —
     proves the paired-label requirement is load-bearing rather than decorative;
  6. **both** labels copied into prose, in the shapes documentation actually takes:
     quoted in one sentence (`the options are "Yes, I trust this folder" and
     "No, exit"`), as a two-item bullet list, and on adjacent lines where the first
     carries trailing commentary (`Yes, I trust this folder   ← the confirm`). This is
     the control for the paired-label matcher specifically: it must reject text that
     contains *both* labels but not the option-line geometry;
  7. a blank line between the two option lines, and the sibling terms dialog
     (`Yes, I accept` / `No, exit`) — the latter is a *scope* control: it is a different
     widget and must not be claimed under this name.
  If any of these matches, the regex is wrong and must be tightened before the pattern
  ships — a matcher that fires on prose is worse than the missing pattern it replaces.
- `_check_trust_pattern_known_false_positive` — a **documented, asserted** positive: a
  verbatim two-line reproduction of the option block *does* match. This pins the
  irreducible limit as a known property rather than leaving it as an untested belief, so
  a future reader sees it was decided, not missed.
- `_check_osc_wrapped_prompt_still_matches` — an `AskUserQuestion` footer wrapped in an
  OSC 8 hyperlink still matches `claude_askuserquestion` end-to-end through
  `_finalize_capture`. This is the behavioural link between the two fixes: without the
  OSC strip the escape bytes land mid-regex and the match fails.
- Extend `_check_all_patterns_flattens_per_agent_groups` to assert `claude_trust_folder`
  is present (`claude_proceed` stays asserted — it is being kept).
- Register the new checks in `main()`'s list and refresh the module docstring's numbered
  summary.

### `tests/test_shadow_strip_ansi.sh` (new)

`shadow_strip_ansi` is a hand-maintained sed mirror of the Python regexes, and nothing
automated covers it today — the mirror can silently start retaining or corrupting OSC
markup while every Python test still passes. This test closes that gap, driving the
**documented entry point** (`aitask_shadow_capture.sh -`, the stdin seam, which
short-circuits before any tmux access and so is hermetic) rather than sourcing the
function.

Bash test in the repo's style (`source tests/lib/asserts.sh`, own PASS/FAIL tally,
non-zero exit on failure). For each of four inputs — the real fixture above, a
BEL-terminated OSC (`ESC]0;title BEL`), an unterminated `ESC]8;;http://x` (the fail-safe
case), and a CSI-coloured line (regression) — assert **both**:

- **Parity** — the output equals `strip_ansi()` run over the same bytes. `ansi_utils.py`
  is an import-only module with no CLI or stdin behaviour, so the test supplies its own
  one-line adapter and pipes the data through it:

  ```bash
  PY="$( . .aitask-scripts/lib/python_resolve.sh; resolve_python )"
  PY_STRIP='import sys; sys.path.insert(0, sys.argv[1]); from ansi_utils import strip_ansi
d = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
sys.stdout.buffer.write(strip_ansi(d).encode("utf-8", "surrogateescape"))'
  py_strip_ansi() { "$PY" -c "$PY_STRIP" "$PROJECT_DIR/.aitask-scripts/monitor"; }
  ```

  Three details are load-bearing: `-c` (a `<<'PYEOF'` heredoc would occupy stdin, the
  very channel the fixture needs); the module directory passed as `argv[1]` rather than
  interpolated into the code string; and the `surrogateescape` byte round-trip, so a
  capture that is not valid UTF-8 cannot corrupt the comparison. The expectation is the
  live Python implementation, never a copied string, so drift cannot pass.

  **Oracle self-check before any comparison** — run
  `printf 'A\033]8;;u\033\\B' | py_strip_ansi` and require exit 0 and exactly `AB`. If
  the adapter cannot import the module, the test aborts here rather than comparing the
  shell output against an empty or unrelated string. Every later comparison also checks
  both sides' exit status, so a crashed adapter can never read as agreement.
  `resolve_python` returning empty is a hard failure too — not a skip; this test's whole
  purpose is the cross-language comparison.
- **Absolute** — on the real fixture, the output contains `LINKTEXT` and contains
  neither an ESC byte nor `example.com`. Parity alone would pass if *both*
  implementations broke the same way; this is the independent ground truth.

Include a positive control: the untouched fixture bytes must **not** equal the expected
output, so a test that silently processed nothing fails.

Both surfaces are compared on the OSC line alone; note in the test that `shadow_clean`
additionally right-trims lines and drops trailing blank lines, which is why the fixture
is chosen to have neither (tmux does not pad captured lines).

## Documentation

`aidocs/framework/monitor_idle_and_prompt_detection.md` — two additions to
"When to edit `prompt_patterns.py`":

- **Bottom-anchor the regex.** Matching runs against the last
  `_PROMPT_DETECTION_TAIL_LINES` (6) lines of the stripped capture, so anchor on text
  that renders at the very bottom — a footer or the option/confirm labels — never on the
  question line. A question rendered above an option list normally falls outside the
  window; `claude_proceed` is the worked example (live wording, almost never matches).
- **Anchor on dialog structure, not on a quotable phrase.** Panes display plans, docs
  and test fixtures, so any pattern that is a single phrase will eventually fire on text
  *about* the dialog rather than the dialog. Prefer a line anchor plus a second element
  that only ever co-occurs in the real widget (as `claude_trust_folder` requires both
  the confirm and the cancel label, on adjacent lines holding nothing else), and ship a
  negative control for each way prose could reproduce the anchor — quoted inline,
  blockquoted, bulleted, numbered, or both labels present but not in option geometry.
- **A verbatim reproduction is indistinguishable — so do not write one.** Whatever the
  matcher, a doc or fixture that reproduces a dialog *with its exact line geometry* will
  be matched when displayed in a pane. Describe dialog labels inline in prose; never
  paste an option block into this doc or into a task/plan file.
- **What the capture contains.** `capture-pane -p -e` re-emits SGR runs *and* OSC 8
  hyperlinks; `strip_ansi` (`monitor/ansi_utils.py`) removes both, and anything matching
  on pane text must go through it. Name the current claude kinds, including
  `claude_trust_folder`.

`awaiting_input_kind` reaches the applink wire (`applink/pusher.py:420`), so note there
that this change is **additive** — a new value, no existing value renamed or removed —
which is why no protocol `v` bump is needed (per `aidocs/applink/protocol.md`
"Versioning": clients ignore values they don't recognise).

## Verification

```bash
python3 tests/test_ansi_utils.py
python3 tests/test_prompt_detection.py
bash tests/test_shadow_strip_ansi.sh
bash tests/test_workflow_phase_prompt_drift.sh
shellcheck .aitask-scripts/aitask_shadow_capture.sh
bash tests/test_no_raw_tmux.sh
```

Regression sweep over the modules that consume `strip_ansi` / `all_patterns()`:

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
```

Both surfaces are covered by the automated tests above; the live tmux run happens once
in the pre-phase, to *produce* the fixture. Re-run it by hand only if tmux's capture
encoding is suspected of having changed.

Step 9 then runs the `risk_evaluated` gate via `./ait gates run 1474`.

## Step 9 (Post-Implementation)

Current-branch mode: no worktree or branch cleanup. Merge target is `main`
(plan header). Archive with `./.aitask-scripts/aitask_archive.sh 1474`.

## Risk

### Code-health risk: medium
- `strip_ansi` is on the monitor's per-tick hot path and is shared by `monitor_core`
  (idle detection, `compare_value`) and `concern_parser`; broadening it changes the
  compare value for **every** pane, so a regex that swallows visible text would turn
  blocked panes into silently-idle ones — the exact failure class this task exists to
  fix · severity: medium · → mitigation: inline pre-phase pin_osc_fixture_from_live_tmux
- The `claude_trust_folder` anchor is derived from string literals in the Claude Code
  binary, not from a capture of the dialog as it actually renders; a numbered/wrapped
  rendering could place the labels differently than assumed. The tightening needed to
  kill the prose false-positives (line anchor, `❯`-only marker, paired cancel label)
  trades some of this away: a rendering that puts anything else on an option line, or
  separates the two options by a blank line, would now miss · severity: medium ·
  → mitigation: t1477
- **Accepted, not mitigated:** a pane displaying a verbatim two-line reproduction of the
  option block — this task's own test fixture, or any doc that pastes it — is
  indistinguishable from the live dialog to any text matcher and will be reported as
  `claude_trust_folder`. Bounded (advisory badge on one pane, clears on the next tick
  once the text scrolls) and pinned by an asserted test, with a documentation rule to
  keep the framework's own files from triggering it · severity: low ·
  → mitigation: none — accepted, see `_check_trust_pattern_known_false_positive`
- `shadow_strip_ansi` is a hand-maintained sed mirror of the Python regexes in a
  different language; without a parity test the two can diverge silently, leaving pasted
  captures uncleaned while the Python suite stays green · severity: medium ·
  → mitigation: inline post-phase parity_test_shadow_strip_mirror

### Goal-achievement risk: medium
- The workspace-trust dialog cannot be reproduced in this session (it only appears on
  first run in an untrusted folder), so the central fix ships **unverified against the
  real widget** — the pattern could be right in wording and still never fire ·
  severity: medium · → mitigation: t1477
- Defect 1 is delivered as a comment correction rather than the retirement the task
  suggested, because the wording turned out to be live. Confirmed with the user;
  the residual risk is only that the corrected comment under-sells how rarely the
  pattern fires · severity: low · → mitigation: TBD

### Planned mitigations
- timing: pre-phase | name: pin_osc_fixture_from_live_tmux | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a broadened strip_ansi on the monitor hot path could swallow visible text | desc: Capture a real OSC-8-bearing pane with tmux capture-pane -p -e and freeze those exact bytes as the tests/test_ansi_utils.py fixture, asserting both markup removal and visible-text survival, and confirming the check fails against the current CSI-only strip first.
- timing: post-phase | name: parity_test_shadow_strip_mirror | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the bash sed mirror of strip_ansi has no automated coverage and can drift from the Python implementation silently | desc: Add tests/test_shadow_strip_ansi.sh driving the aitask_shadow_capture.sh - stdin seam over the shared real-tmux fixture plus BEL/unterminated/CSI cases, asserting parity against the live Python strip_ansi and absolute properties on the fixture. Confirmed by the user in chat.
- timing: after | name: verify_trust_dialog_live | type: manual_verification | priority: medium | effort: low | inline_risk: high | added_complexity: high | addresses: goal-achievement — the workspace-trust dialog cannot be reproduced in this session, so claude_trust_folder ships unverified against the real widget | desc: Run a code agent for the first time in an untrusted scratch folder inside the framework tmux session and confirm ait monitor / ait minimonitor render PROMPT for that pane with awaiting_input_kind claude_trust_folder. | created: t1477

## Final Implementation Notes

- **Actual work done:** All three defects addressed, plus both confirmed inline
  mitigations. `monitor/ansi_utils.py` gained `ANSI_OSC_RE` and `strip_ansi` now runs
  OSC-then-CSI; `monitor/prompt_patterns.py` gained `claude_trust_folder` (built from
  the `_TRUST_YES` / `_TRUST_NO` fragments) and a corrected `claude_proceed` comment with
  its regex unchanged; `aitask_shadow_capture.sh::shadow_strip_ansi` mirrors both
  regexes as separate BREs. Drift guards updated in `lib/workflow_phase.py` and
  `tests/test_workflow_phase_prompt_drift.sh`. Docs updated in
  `aidocs/framework/monitor_idle_and_prompt_detection.md`. New tests:
  `tests/test_ansi_utils.py` (6 checks), `tests/test_shadow_strip_ansi.sh` (9), and
  5 added to `tests/test_prompt_detection.py` (12 total), against the shared real-tmux
  fixture `tests/fixtures/osc8_capture_pane.txt`.

- **Deviations from plan:**
  - Added `.gitattributes` (not in the plan) marking the fixture `-text`. The repo had
    no `.gitattributes` at all, and the fixture holds raw ESC bytes; without this, EOL
    normalisation could silently alter the bytes both tests compare against.
  - The planned `_check_osc_wrapped_prompt_still_matches` was **replaced**, not just
    written. As specified it wrapped the hyperlink *around* the whole footer, which
    leaves the pattern's text contiguous — it passed against the pre-fix stripper too,
    so it proved nothing. Split into `_check_osc_inside_prompt_footer_still_matches`
    (escape lands mid-phrase, the case that genuinely fails without the fix) and
    `_check_osc_url_churn_does_not_defeat_idle` (same visible text, changing link
    target, must still reach idle — the defect the task reports most directly). Both
    were confirmed to discriminate against the pre-t1474 stripper before being kept.
  - Negative controls grew from the planned 5 groups to 10 cases while implementing
    (numbered list and blank-line-between were folded in as separate entries).

- **Issues encountered:**
  - `(?m)` repeated in the second alternative is a hard `re.error: global flags not at
    the start of the expression` on Python 3.14 — caught by compiling the pattern during
    planning rather than by reading it. Single leading `(?m)` covers both alternatives.
  - The settings-trust dialog's cancel label is `No, exit Claude Code`; with `[ \t]*$`
    closing the line, a bare `exit` alternative never matched it, so the
    `Yes, I trust these settings` arm would have shipped dead. Fixed with
    `exit(?: Claude Code)?`.
  - `assert_not_contains` in `tests/lib/asserts.sh` takes `(desc, needle, haystack)`;
    the first draft of the parity test passed haystack and needle inverted, which makes
    the assertion **vacuous rather than wrong** — it passes forever and silently. Only
    running the parity test against a deliberately broken mirror exposed it. The
    argument order is now called out in a comment at that call site.

- **Key decisions:**
  - **`claude_proceed` kept, not retired** (user-confirmed). The task's premise that the
    wording is dead is incorrect: `Do you want to proceed?` is the permission dialog's
    default question in 2.1.226, used by the command/Bash prompt and the Read/Edit
    fallback. What makes it near-dead is structural — it renders above the option list
    and so falls outside `_PROMPT_DETECTION_TAIL_LINES`, leaving the bottom-anchored
    `claude_help_bar` to match those dialogs. The comment now says exactly that.
  - **Trust pattern anchors on option-line geometry, not on a phrase.** Successive
    review rounds killed three weaker forms: a bare `Quick safety check` arm (this task
    writes that phrase into its own plan and docs), an ASCII `>` in the marker class
    (Markdown blockquote prefix), and a `[\s\S]{0,120}?` gap between the labels (prose
    fits in 120 characters). The shipped form requires both labels on adjacent lines
    holding nothing else, in either order.
  - **The irreducible false positive is asserted, not hidden.** A verbatim,
    geometry-faithful reproduction of the option block is indistinguishable from the
    dialog to any text matcher. `_check_trust_pattern_known_false_positive` pins it, and
    the mitigation is a documentation rule (describe labels inline in prose, never as a
    copied option block) now recorded in the pattern comment and the framework doc.
  - **`ANSI_OSC_RE` uses a bounded body**, unlike `applink/content.py::_OSC_SEQ`'s
    non-greedy `.*?`. The two are intentionally different: `content.py` *parses* the
    body into hyperlink spans and needs to capture it, whereas this one only strips, so
    it takes the fail-safe bound — an unterminated OSC is left intact rather than
    reaching forward and deleting the visible text in between (which, for a footer,
    would turn a blocked pane back into a silently idle one).
  - **The parity test drives `aitask_shadow_capture.sh -`**, the documented stdin seam,
    rather than sourcing `shadow_strip_ansi`, and computes its expectation by running
    the live Python module through a `python -c` adapter (not a heredoc — that would
    occupy the stdin the fixture needs). An oracle self-check aborts before any
    comparison if the adapter cannot import, so a broken oracle can never read as
    agreement.

- **Upstream defects identified:** None.

- **Build verification:** `bash tests/run_all_python_tests.sh --test-dir tests` →
  `PYTHON SUITE: PASSED (runner=pytest, exit=0)` (3953 passed, 2 skipped, plus the
  2-test serial carve-out). `bash tests/test_no_raw_tmux.sh` 5/5.
  `bash tests/test_workflow_phase_prompt_drift.sh` 13/13. shellcheck on the changed and
  new shell files reports only pre-existing SC1091 (unfollowed `source`), identical in
  count to the committed version. Note: the working tree also carried unrelated
  in-progress changes from a concurrent session (`aitask_gate.sh`, `aitask_ls.sh`,
  `lib/gate_ledger.py`, `aidocs/gates/*`), so the suite run covered a mixed tree; none
  of those files were touched or staged by this task.
