---
Task: t1777_align_frozen_drop_dialog_copy_and_verb.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1777 — Align the frozen-drop dialog copy and verb

## Context

Two defects in **shipped UI copy** around the frozen-agent drop flow. The code
does the right thing and describes it inaccurately. Both were found during
t1705_9 while writing the frozen-agent docs.

**1. The monitors' drop dialog promises retention it does not provide.**
`monitor_app.py:3549` and `minimonitor_app.py:3018` both end with
"restore or re-pick it instead if you still want it", which reads as "those
routes keep the capture". They do not. Verified in the tree:

| action | capture |
|---|---|
| verified restore (`ack=hook`) | **deleted** |
| verified re-pick (`ack=hook`) | **deleted** |
| liveness-only restore | kept |
| failed restore | kept |
| drop | deleted |

`lib/agent_sessions.py:823` is the single deletion site — the hook-ack success
path sets `rec.ack = "hook"` and calls `remove_captures(rec.id)`. Both `resume`
and `repick` reach it (repick adopts the new session id and falls through to the
same block). The comment there records the rule as deliberate. The dialog is
right about not losing the *agent* and wrong about keeping the *transcript* —
and that same wrong belief was written into the t1705_9 docs three times before
review caught it, which is why it is worth fixing at the source.

**2. One destructive operation has two verbs across three surfaces.**
`frozenagent_app.py:134,927` says **"Remove"**; both monitors say **"Drop"**,
deliberately chosen in t1705_7 so the destructive verb names itself. The
viewer's own `k` binding (`frozenagent_app.py:205`) already reads `Drop`, so the
viewer contradicts its own footer. "Drop" is the verb with a recorded rationale
and it matches the engine verb (`aitask_frozen.sh drop`).

**Outcome:** one verb — `Drop` — on all three surfaces, and a monitor dialog
that tells the truth about what keeps a capture.

## Code changes

### 1. `.aitask-scripts/monitor/monitor_app.py` — `_confirm_drop_frozen` (~3545-3550)

Replace the body tail. Keep the `[bold red]…[/]` markup and the string-literal
concatenation shape exactly as they are:

```python
                f"[bold]{escape(window)}[/]\n\n"
                "[bold red]Its captured output is deleted[/] along with the "
                "record, and the stand-in pane is closed. This cannot be "
                "undone, and a verified restore or re-pick deletes the "
                "capture too — copy it from the viewer first.",
```

Add a short comment above the body recording *why* the tail says this, so the
next edit does not regress it:

```python
                # NOT "restore or re-pick it instead": a VERIFIED restore or
                # re-pick deletes the capture too (agent_sessions.py, the
                # `ack = "hook"` branch). Only a failed or liveness-only one
                # keeps it, so the only reliable way to keep the transcript is
                # to copy it out of the viewer (t1777).
```

### 2. `.aitask-scripts/monitor/minimonitor_app.py` — `_confirm_drop_frozen` (~3014-3019)

The identical block. Apply the **same** replacement and the same comment —
these two dialogs are duplicated verbatim today and must stay identical.

### 3. `.aitask-scripts/frozenagent/frozenagent_app.py` — verb alignment

- **Line 134** — `Button("Remove", …)` → `Button("Drop", …)`, with the
  rationale comment (confirmed approach: hardcode, do **not** parameterize —
  `ConfirmDialog` has exactly one call site and a `"Drop"` default would add no
  real safety):

  ```python
                  # The destructive verb must name itself, and it must be the
                  # SAME verb the monitors and the `k` binding use (t1705_7,
                  # t1777) — "Remove" was a third name for one operation.
                  yield Button("Drop", variant="error", id="fa-confirm-yes")
  ```

- **Line 927** — the confirmation message:

  ```python
              ConfirmDialog("Drop the frozen record and its capture? "
                            "This cannot be undone."),
  ```

Leave the message otherwise alone: unlike the monitors', it makes no claim about
restore/re-pick, so it is not misleading — only its verb was wrong.

**Not in scope:** `aitask_frozen.sh:19` ("drop <id>  remove a frozen record…")
and `agent_freeze.py:933` are a source comment and a docstring glossing the verb,
not competing user-facing verb names. `usage()` does not print either.

## Documentation changes

All four passages move with the strings.

- **`website/content/docs/tuis/frozenagent/how-to.md`**
  - Line 99: heading `## Remove a frozen record` → `## Drop a frozen record`.
    Verified safe: nothing links to `#remove-a-frozen-record` anywhere in
    `website/`.
  - Line 102: quoted string → `Drop the frozen record and its capture? This
    cannot be undone.`
  - The surrounding prose (lines 104-112) **already states the retention rule
    correctly** — leave it.

- **`website/content/docs/tuis/frozenagent/_index.md`** (lines 117-119): quoted
  string as above, and **Remove** button → **Drop** button.

- **`website/content/docs/tuis/minimonitor/how-to.md`** (lines 343-346): update
  the verbatim quote to the new monitor string so it matches the code again.

- **`website/content/docs/tuis/monitor/how-to.md`** (line 284): quotes nothing
  verbatim and its claim ("a red **Drop** button, because it deletes the captured
  output along with the record") stays true. Add one sentence so the monitor page
  carries the same correction as its sibling — that a verified restore or re-pick
  deletes the capture too, and copying from the viewer is the only way to keep it.

## Verification

0. **Scope every grep to the two live trees.** All checks below scan exactly
   `.aitask-scripts` and `website/content`, with `--exclude-dir=__pycache__`.
   An unscoped `grep -r .` is **not** a usable control here — measured on this
   tree it returns 19 hits for the monitor sentence, 16 of them irrelevant:
   `.aitask-data/` (this task's own file, plus the archived `p1705_9` plan),
   `.aitask-shadow/1777/plan_r*.md` (review snapshots), `__pycache__/*.pyc`
   (stale bytecode), and `website/public/` (built HTML plus five
   `offline-search-index.*.json` blobs). Historical and generated text would keep
   the control red forever while a real missed surface stayed invisible.

   **Do not trust a hit count taken from an interactive shell.** Some agent
   sessions shim `grep` to a gitignore-aware `ugrep` that silently skips
   `website/public/`, `.aitask-data/` and `*.pyc`; the same command then returns
   3 instead of 19. The scoped form below was checked against **both**
   `/usr/bin/grep` and the shim and returns the identical 8 lines, which is why
   it is the form to use.

   ```bash
   SCAN=(--exclude-dir=__pycache__ .aitask-scripts website/content)
   ```

1. **Pre-fix control — run the absence greps BEFORE editing** and confirm they
   find exactly the eight sites this plan edits. Scoping to `.aitask-scripts/`
   alone is not enough either: the stale monitor sentence is also quoted in
   `website/content/docs/tuis/minimonitor/how-to.md:346`, so a code-only grep
   would pass green while the docs still carry the false retention promise.

   ```bash
   grep -rn "${SCAN[@]}" -e "restore or re-pick it instead" \
                         -e "Remove the frozen record" \
                         -e '\*\*Remove\*\* button' \
                         -e '^## Remove a frozen record'
   ```

   Expected pre-fix — exactly these 8 lines, no more and no fewer:

   | file | line |
   |---|---|
   | `.aitask-scripts/monitor/monitor_app.py` | 3549 |
   | `.aitask-scripts/monitor/minimonitor_app.py` | 3018 |
   | `.aitask-scripts/frozenagent/frozenagent_app.py` | 927 |
   | `website/content/docs/tuis/minimonitor/how-to.md` | 346 |
   | `website/content/docs/tuis/frozenagent/how-to.md` | 99, 102 |
   | `website/content/docs/tuis/frozenagent/_index.md` | 118, 119 |

   A hit outside this table is a live surface the plan missed — widen the change,
   not the check. (`frozenagent_app.py:134`'s bare `"Remove"` button label is not
   in the table because it matches none of these four phrases; step 2 covers it.)

2. **Post-fix absence — the same grep, unchanged, must return nothing**
   (`grep` exits 1 on no match). Plus the bare button label:
   `grep -n '"Remove"' .aitask-scripts/frozenagent/frozenagent_app.py` → nothing.

3. **Post-fix presence — assert the replacement landed in each intended
   passage.** Absence alone is satisfied by deleting a sentence, so each of the
   seven edited files gets a positive assertion. Note the code/prose split: the
   new sentence spans three Python string literals, so a whitespace-normalized
   match for the whole sentence breaks on the `" "` literal boundary in code —
   use a fragment that sits inside one literal there, and the full normalized
   sentence in prose.

   ```bash
   # code: fragment probes (each lives within a single string literal)
   for f in .aitask-scripts/monitor/monitor_app.py \
            .aitask-scripts/monitor/minimonitor_app.py; do
     grep -q "a verified restore or re-pick deletes the" "$f" &&
     grep -q "copy it from the viewer first" "$f" &&
     echo "OK  $f" || echo "FAIL $f"
   done
   grep -q 'Button("Drop", variant="error", id="fa-confirm-yes")' \
     .aitask-scripts/frozenagent/frozenagent_app.py && echo OK || echo FAIL
   grep -q '"Drop the frozen record and its capture? "' \
     .aitask-scripts/frozenagent/frozenagent_app.py && echo OK || echo FAIL

   # prose: whitespace-normalized full-sentence match (survives line wrapping)
   probe() {  # <file> <sentence>
     tr -s '[:space:]' ' ' < "$1" | grep -qF "$2" && echo "OK  $1" || echo "FAIL $1"
   }
   probe website/content/docs/tuis/minimonitor/how-to.md \
     "a verified restore or re-pick deletes the capture too — copy it from the viewer first."
   probe website/content/docs/tuis/monitor/how-to.md \
     "copy it from the viewer"
   probe website/content/docs/tuis/frozenagent/how-to.md \
     "Drop the frozen record and its capture? This cannot be undone."
   probe website/content/docs/tuis/frozenagent/_index.md \
     "Drop the frozen record and its capture? This cannot be undone."
   grep -q '^## Drop a frozen record' website/content/docs/tuis/frozenagent/how-to.md \
     && echo OK || echo FAIL
   grep -q '\*\*Drop\*\* button' website/content/docs/tuis/frozenagent/_index.md \
     && echo OK || echo FAIL
   ```

   **Pre-validate `probe` before trusting it.** Run it against the **old**
   sentence on the one prose file that quotes it verbatim — it must report `OK`:

   ```bash
   probe website/content/docs/tuis/minimonitor/how-to.md \
     "restore or re-pick it instead if you still want it."
   ```

   That is what proves the whitespace normalization actually matches wrapped
   prose, rather than a `FAIL`-free run that never matched anything. (Verified
   against this tree under both `/usr/bin/grep` and the `ugrep` shim.)

4. **The two monitor dialogs are still byte-identical:** diff the two
   `_confirm_drop_frozen` bodies.
5. **Render the dialog at the minimonitor's host width.** The new body is ~29
   characters longer, and `monitor_shared.FreezeConfirmDialog`'s docstring records
   that the minimonitor hosts it at **40 columns** with a ~32-column content area.
   Drive `FreezeConfirmDialog` under `App.run_test(size=(40, 20))` with the new
   title and body and assert the dialog and **both** buttons are fully on screen
   (the docstring records that an over-wide button renders but is unclickable).
   `tests/test_monitor_frozen_filter.py:1100/1117/1192` already construct this
   dialog directly — reuse that harness shape.
6. **Targeted Python tests** (these import the touched modules):
   `bash tests/run_all_python_tests.sh` is the whole suite; for a fast loop run
   `tests/test_frozenagent_app.py`, `tests/test_monitor_frozen_filter.py`,
   `tests/test_textual_markup_structure.py`. Read only the last line for the
   verdict (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`), and use
   `set -o pipefail` if piping.
7. **Docs:** `cd website && python3 check_links.py --build` — mandatory after
   editing any page under `website/content/`, and specifically load-bearing here
   because step 1 renames a heading (and therefore an anchor).
8. **Manual (optional, needs an external terminal — not from inside tmux):**
   freeze an agent, then press `k` in minimonitor at a narrow pane width and read
   the dialog; press `k` in the viewer and check the button says **Drop**.

## Risk

### Code-health risk: low
- The new monitor body is ~29 characters longer, and the dialog is hosted at 40
  columns in the minimonitor — one extra wrapped line could push a `height: auto`
  dialog past a short companion pane, making a button unreachable (the failure
  mode `FreezeConfirmDialog`'s own docstring records). · severity: low · →
  mitigation: inline post-phase `render_dialog_at_40_cols`
- The two `_confirm_drop_frozen` bodies are duplicated verbatim between
  `monitor_app.py` and `minimonitor_app.py`; editing one and not the other
  re-opens the same class of split this task exists to close. · severity: low ·
  → mitigation: inline post-phase `assert_monitor_bodies_identical`

### Goal-achievement risk: low
- The change spans code **and** four doc pages, and the natural completeness
  check — a grep for the old wording — is easy to get wrong in two ways that both
  fail *silently green*: scoping it to `.aitask-scripts/` misses the doc copy of
  the sentence, and running it unscoped buries the three live hits under 16
  archival/generated ones. A session whose `grep` is shimmed to gitignore-aware
  `ugrep` sees a third reading again. · severity: medium · → mitigation: inline
  post-phase `scoped_grep_control` (Verification steps 0-2)
- Otherwise none identified. The retention claim the new copy makes was
  verified against the single deletion site (`agent_sessions.py:823`) rather than
  taken from the task description, the "Drop" verb has a recorded rationale
  (t1705_7), and no test asserts any of the strings being changed — so nothing
  passes green on a wrong string.

### Planned mitigations
- timing: post-phase | name: render_dialog_at_40_cols | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: dialog overflow at the minimonitor's 40-column host | desc: drive FreezeConfirmDialog under App.run_test(size=(40,20)) with the new body and assert the dialog and both buttons render fully on screen
- timing: post-phase | name: scoped_grep_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: a completeness grep that passes green while a live surface still carries the old wording | desc: scope the before/after greps to .aitask-scripts and website/content with --exclude-dir=__pycache__, pin the expected 8 pre-fix sites in a table, and assert the replacement is present in all seven edited files
- timing: post-phase | name: assert_monitor_bodies_identical | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: verbatim duplication of _confirm_drop_frozen across the two monitors | desc: diff the two _confirm_drop_frozen bodies after the edit and confirm they are byte-identical

### Post-phase (risk mitigations)

- **`scoped_grep_control`** — Verification steps 0-2: run the scoped absence
  grep before editing (expect exactly the 8 tabulated sites), then again after
  (expect nothing), then the per-file presence assertions of step 3.

- **`render_dialog_at_40_cols`** — after the code edits land, run the 40-column
  render check described in Verification step 5 before running the wider suite.
- **`assert_monitor_bodies_identical`** — run Verification step 4 in the same
  pass.

## Step 9 (Post-Implementation)

Standard: commit with `bug: Align the frozen-drop dialog copy and verb (t1777)`,
then the usual cleanup, gate run (`risk_evaluated`) and archival.

---

## Implementation Notes

All seven files changed as planned. Three deviations, each measured rather than
assumed.

### 1. Final wording is shorter than the approved draft (user-confirmed)

The approved body tail was *"This cannot be undone, and a verified restore or
re-pick deletes the capture too — copy it from the viewer first."* Driving
`FreezeConfirmDialog` at the minimonitor's 40-column host showed it raises the
dialog from **18 to 19 rows**, so the minimum viable pane height rose by one.
(Both fit the documented 40×20; below 18 rows the *old* body already overflowed,
so this was a one-row narrowing of a pre-existing limit, not a new break.)

Measured alternatives at 40 columns:

| wording | rows |
|---|---|
| old (pre-fix) | 18 |
| approved draft | 19 |
| **shipped** — "This cannot be undone. A verified restore or re-pick deletes it too — copy it first." | **18** |
| "…Restore and re-pick delete it too — copy it from the viewer first." | 18 |

The user chose the shipped wording: it keeps the `verified` qualifier — which is
the load-bearing word, since a *failed* or liveness-only restore does keep the
capture — and restores exact height parity with the pre-fix dialog, so this
change costs no layout headroom. It gives up only the words "from the viewer".
The third row was rejected because dropping `verified` over-claims.

`website/content/docs/tuis/minimonitor/how-to.md` quotes the dialog verbatim and
was updated to the shipped wording, not the draft.

### 2. The absence check needed a comment exemption (code only)

Both monitors gained a regression-guard comment that deliberately quotes the old
phrasing (`# NOT "restore or re-pick it instead": …`), and the viewer's button
comment quotes `"Remove"`. The plan's flat absence grep therefore fired on the
fix itself. Split it by tree instead — the exemption applies **only** to Python
comments, never to prose, because a markdown `## Remove a frozen record` heading
also begins with `#` and must stay caught:

```bash
# code: the old phrasing may survive ONLY inside a guard comment
grep -rn --exclude-dir=__pycache__ -e "restore or re-pick it instead" \
     -e "Remove the frozen record" .aitask-scripts | grep -v ':[[:space:]]*#'
grep -n '"Remove"' .aitask-scripts/frozenagent/frozenagent_app.py | grep -v ':[[:space:]]*#'
# docs: no exemption
grep -rn website/content -e "restore or re-pick it instead" \
     -e "Remove the frozen record" -e '\*\*Remove\*\* button' \
     -e '^## Remove a frozen record'
```

All three return nothing; a positive control confirms the guard comments exist.

### 3. Test coverage: full suite NOT run here

`$TMUX` was set and the `ait` socket had a live attached session, so the four
live-TUI carve-out modules were not run — `test_board_header_row_live.py` also
takes `.git/index.lock` on the real repo. **`bash tests/run_all_python_tests.sh`
still needs one clean run from an external terminal.**

What did run, all green:

- 66 monitor / frozen / dialog / shortcut / markup modules — **1696 tests, OK**
  (3 skipped).
- 316 of 320 Python modules (everything except the four live carve-outs) —
  **7656 tests, OK (skipped=10)** in 980s, zero failures or errors. Read from
  the unittest process's own exit status (`EXIT=0`), not from a pipeline: an
  earlier attempt piped to `tail`, whose exit is always 0 and whose last lines
  were sub-module summaries printed *after* the framework verdict — the exact
  trap `CLAUDE.md` documents.
- `tests/test_website_doc_lists.sh` 47/47, `tests/test_docs_vocabulary_coverage.sh`
  30/30, `tests/test_shortcuts_registry_coverage.sh` PASS.
- `website/check_links.py --build` → `SWEEP: PASSED`, 0 broken (the load-bearing
  one: this change renames a heading, and therefore an anchor).

### Mitigation outcomes

- **`scoped_grep_control`** — done. Pre-fix control returned exactly the 8
  tabulated sites under *both* `/usr/bin/grep` and the gitignore-aware `ugrep`
  shim; post-fix absence is clean and all ten presence assertions pass.
- **`render_dialog_at_40_cols`** — done, and it earned its place: it is what
  caught the one-row growth and drove deviation 1. Final dialog is 18 rows,
  identical to pre-fix, with both buttons fully on screen at 40×18/19/20.
- **`assert_monitor_bodies_identical`** — done. The two `_confirm_drop_frozen`
  bodies are byte-identical after the edit.

## Final Implementation Notes

- **Actual work done:** Exactly the planned seven files. The two monitors'
  drop-confirmation tail no longer claims restore/re-pick preserves the capture,
  and each carries a regression-guard comment pointing at the deletion site. The
  frozenagent viewer's `ConfirmDialog` now says **Drop** on both its button and
  its message, matching the monitors, the `k` binding's own footer label and the
  engine verb `aitask_frozen.sh drop`. Four website pages moved with the strings,
  including a heading rename (`## Remove a frozen record` → `## Drop a frozen
  record`) and a new retention sentence on `monitor/how-to.md`, which previously
  quoted nothing verbatim and so carried no correction at all.

- **Deviations from plan:** Three, each recorded in full under **Implementation
  Notes** above — (1) the shipped body text is shorter than the approved draft,
  chosen by the user after the 40-column measurement showed the draft cost a row
  of pane height; (2) the absence grep needed a Python-comments-only exemption,
  because the regression-guard comments deliberately quote the old wording; (3)
  the four live-TUI modules were not run from this session.

- **Issues encountered:** The plan's completeness grep was wrong twice before it
  was right, and both failures were silent-green. First it was scoped to
  `.aitask-scripts/` and missed the doc copy of the sentence. Then, unscoped, it
  returned 19 hits — 16 of them archival or generated — and the "expected 3" I
  had written came from a session whose `grep` is shimmed to gitignore-aware
  `ugrep`, so it never transferred to the literal command in the plan. The final
  form is scoped to the two live trees and was validated under **both** grep
  implementations. Separately, two attempts to run the suite produced no usable
  verdict: a `nohup … &` whose process was killed with its parent shell, and a
  `| tail -25` whose exit status is `tail`'s and whose last lines were sub-module
  summaries printed *after* the framework verdict — the trap `CLAUDE.md`
  documents. The real number came from an unpiped run reporting `EXIT=0`.

- **Key decisions:** Hardcode `"Drop"` in the viewer rather than parameterize
  `confirm_label` — `ConfirmDialog` has exactly one call site, so a `"Drop"`
  default would add no real safety, and a rationale comment carries the intent
  instead. Keep the word *verified* in the new copy: a **failed** or
  liveness-only restore does keep the capture, so dropping the qualifier would
  have replaced one inaccurate dialog with another, which is the one outcome this
  task must avoid. The viewer's message was left otherwise untouched because,
  unlike the monitors', it never claimed anything about restore or re-pick — only
  its verb was wrong.

- **Upstream defects identified:**
  - `monitor/monitor_shared.py:2594-2606 — FreezeConfirmDialog sets height: auto
    with no max-height and a non-scrollable Container, so at 40 columns its
    buttons land off-screen at a 16-row host. Measured on unmodified code: at
    40×16 both #btn-confirm and #btn-cancel render at bottom=17 against a 16-row
    screen, leaving Escape as the only way out of a destructive confirmation; at
    40×15 the dialog body itself is clipped (y=-2). Pre-existing and independent
    of this task's copy change — the shipped body is 18 rows, identical to the
    pre-fix body, so t1777 neither introduces nor widens it. The existing
    coverage (tests/test_monitor_frozen_filter.py, "both buttons fit inside a
    forty column screen") only ever asserts the width axis and passes a
    placeholder `"body"`, so the height axis is untested with real content.`
