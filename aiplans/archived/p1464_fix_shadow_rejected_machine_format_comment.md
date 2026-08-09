---
Task: t1464_fix_shadow_rejected_machine_format_comment.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# t1464 — Fix the `list --machine` format comment in the rejection-store helper

## Context

`aitask_shadow_rejected.sh list --machine` emits **`r`-prefixed** entry ids —
the emitter at `:339` is
`printf "REJECTED:r%s|%s|%s|%s\n", id, ts, prod, marker`. Two documentation
sites still describe the wire format without the `r`:

- `.aitask-scripts/aitask_shadow_rejected.sh:61` — the helper's own verb-list
  comment: `REJECTED:<id>|<ts>|<producer>|<marker line> per entry`.
- `.aitask-scripts/monitor/monitor_shared.py:1852` — the `RejectedEntry`
  docstring: ``Mirrors a single ``REJECTED:<id>|<ts>|<producer>|<marker line>``
  line``. (Its field comment at `:1858` *does* say the id is `r`-prefixed, so the
  docstring contradicts itself.)

The id is what `remove` consumes. `cmd_remove` (`:377`) normalizes both `r3` and
`3` to the bare number, so a consumer built from the wrong comment works **by
luck of that tolerance** — a latent mismatch that breaks the day the tolerance is
tightened. t1427_4 already hit this: the first draft of
`aidocs/framework/shadow_agent.md` was written from the `:61` comment and had to
be corrected against the emitter (the aidocs text at `:412` is now right).

Intended outcome: every place that states the machine format states the one the
emitter actually produces, and a test pins the whole shape so the two cannot
drift apart again silently.

## Changes

### 1. `.aitask-scripts/aitask_shadow_rejected.sh:61`

```
-#                         REJECTED:<id>|<ts>|<producer>|<marker line> per entry
+#                         REJECTED:r<id>|<ts>|<producer>|<marker line> per entry
```

(Ids are `r`-prefixed on the wire, matching `### r<N>` in the store body and the
`REMOVED:`/`NOT_FOUND:` csv that `remove` prints.)

### 2. `.aitask-scripts/monitor/monitor_shared.py:1852`

Same one-token correction inside the `RejectedEntry` docstring, so it agrees
with its own `id:` field comment two lines below:

```
-    Mirrors a single ``REJECTED:<id>|<ts>|<producer>|<marker line>`` line from
+    Mirrors a single ``REJECTED:r<id>|<ts>|<producer>|<marker line>`` line from
```

### 3. `tests/test_shadow_rejected.sh` — pin the emitted shape

Test 2 already asserts `field 1 is the entry id` == `r1` (`:99`), so the prefix
*is* pinned today — but only as an incidental equality on one field's value.
Add an explicit whole-line format pin right after the existing
`one REJECTED line per entry` assertion (`:92`), so the assertion that fails on
a format change names the format:

```bash
assert_eq "machine line matches the documented REJECTED:r<id>|… shape" "1" \
    "$(printf '%s\n' "$mout" | grep -c '^REJECTED:r[0-9][0-9]*|')"
```

and retitle `:99` to `field 1 is the r-prefixed entry id` so it reads as a
deliberate format pin.

## Out of scope

- Archived plans `aiplans/archived/p1427/p1427_1_*.md` and `p1427_2_*.md`
  disagree on this point (the task cites them as evidence the comment misled a
  reader). Archived plans are a historical record — not corrected.
- `aidocs/framework/shadow_agent.md:412` is already correct.
- `remove`'s verb comment (`:64-66`) does not state that its `REMOVED:` /
  `NOT_FOUND:` csv is `r`-prefixed. It is underspecified, not *wrong*, and the
  reported defect is the `list --machine` line — left alone.

## Verification

```bash
bash tests/test_shadow_rejected.sh          # expect PASS; the new assertion included
shellcheck .aitask-scripts/aitask_shadow_rejected.sh
```

Negative control for the new assertion — confirm it actually fails on the
mismatch it exists to catch: temporarily change `:339` to
`printf "REJECTED:%s|..."` (drop the `r`), re-run
`bash tests/test_shadow_rejected.sh`, and check that the new
`machine line matches the documented REJECTED:r<id>|… shape` assertion FAILS,
then revert.

Comment/docstring correctness (a diff read against `:339`):

```bash
grep -n 'REJECTED' .aitask-scripts/aitask_shadow_rejected.sh \
    .aitask-scripts/monitor/monitor_shared.py
```

Every non-code line should now read `REJECTED:r<id>|<ts>|<producer>|<marker line>`.

Python consumers are untouched (parsing is unchanged), but the two monitor
suites that carry the literal wire line should stay green:

```bash
bash tests/run_all_python_tests.sh --test-dir tests 2>&1 | tail -n 3
# or, narrowly:
~/.aitask/venv/bin/python -m pytest tests/test_monitor_concern_action.py \
    tests/test_minimonitor_concern_action.py
```

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch cleanup. Merge target is `main`
(recorded in the header above). Gates: `risk_evaluated`. Then
`./.aitask-scripts/aitask_archive.sh 1464`.

## Risk

### Code-health risk: low
- None identified. Two comment/docstring tokens and one additive test
  assertion; no executable behavior changes, and `shellcheck` plus the existing
  suite cover the touched files.

### Goal-achievement risk: low
- None identified. The defect is a known, exactly-located string mismatch
  against a verified emitter (`:339`); the fix is that string, and the added
  assertion has a stated negative control proving it discriminates.

## Post-Review Changes

### Change Request 1 (2026-08-09 11:31)

- **Requested by user:** The plan's test change (an output-only assertion on
  `list --machine`) did not deliver the task's stated objective that the emitted
  format and its documentation "cannot drift again". Nothing reads
  `aitask_shadow_rejected.sh:61` or `monitor_shared.py:1852`, so either comment
  could revert to `REJECTED:<id>` with all 124 tests still green. Add explicit
  assertions for both documentation strings, or narrow the task. **Verdict:
  confirmed** — the original plan's Step-3 rationale over-claimed.
- **Changes made:** Kept the scope (the drift property is the task's own
  "Suggested fix") and added the documentation half.
  - New **Test 2b** in `tests/test_shadow_rejected.sh`: for each documentation
    site it asserts (a) the file contains `REJECTED:r<id>|` at least once and
    (b) it contains **no** `REJECTED:<id>|`. Per-file so a failure names the
    site that drifted; the "at least once" half is the vacuity guard — a file
    that merely *deletes* its format spec must not read as clean. The tail is
    unpinned on purpose (`REJECTED:r<id>|`, not the full spec): rewording
    `<marker line>` is not drift, dropping the `r` is. Only prose can match
    these patterns — the awk emitter writes `REJECTED:r%s` and the Python
    parser slices the bare literal `REJECTED:`.
  - Sites covered: `.aitask-scripts/aitask_shadow_rejected.sh`,
    `.aitask-scripts/monitor/monitor_shared.py`, and — beyond the two the
    review named — `aidocs/framework/shadow_agent.md`, which is the *third*
    party to the original disagreement (t1427_4 corrected it against the
    emitter) and is now held to the same rule.
  - Rewrote the over-claiming comment above the Test 2 assertion: it now says
    what that assertion actually pins (the emitted line) and points at Test 2b
    for the documentation half.
- **Files affected:** `tests/test_shadow_rejected.sh` (Test 2 comment + new
  Test 2b). The two source-comment fixes are unchanged.
- **Verification:** `bash tests/test_shadow_rejected.sh` → **130/130 passed**
  (was 124). Two negative controls, each reverted after:
  - reverting `aitask_shadow_rejected.sh:61` to `REJECTED:<id>|…` → 128/130,
    failing *both* of that file's new assertions by name;
  - deleting the spec from the `monitor_shared.py` docstring (replacing it with
    prose) → 129/130, failing only `documents the r-prefixed wire spec` —
    proving the vacuity guard fires rather than passing silently.

## Final Implementation Notes

- **Actual work done:** Exactly the two one-token comment corrections the task
  named — `.aitask-scripts/aitask_shadow_rejected.sh:61` and (found during
  implementation) `.aitask-scripts/monitor/monitor_shared.py:1852`, both now
  reading `REJECTED:r<id>|<ts>|<producer>|<marker line>` in agreement with the
  awk emitter at `:339`. On the test side the plan's single output-shape
  assertion grew, after review, into two complementary pins: Test 2's
  `^REJECTED:r[0-9]+|` line check (what the helper *prints*) and a new Test 2b
  (what the three documentation sites *say*). `tests/test_shadow_rejected.sh`
  goes 124 → 130 assertions.
- **Deviations from plan:** One, driven by the Step-8 review. The plan asserted
  its test change would make "the emitter and its documentation fail together";
  it would not — nothing read either comment, so both could silently revert with
  every test green, which is the exact property the task asked for. Test 2b was
  added to close that (see Post-Review Changes above), and it also covers
  `aidocs/framework/shadow_agent.md`, the third party to the original
  disagreement, which the plan had listed as out of scope on the grounds that it
  was already correct — correct today is not the same as pinned.
- **Issues encountered:** The plan's premise that the test suite did not pin the
  `r` prefix was wrong — `:99` already asserted field 1 == `r1`. That made the
  planned assertion partly redundant on the emitter side, which is what left the
  documentation side (the actual gap) unaddressed until review. Also worth
  recording: the reason this class of bug survives review is `cmd_remove`'s
  `${a#r}` normalization at `:377` — it accepts `rN` and `N` alike, so code
  written from the wrong comment works, and no test fails, until that tolerance
  is ever tightened.
- **Key decisions:**
  - Scope kept rather than narrowed. The review offered "narrow the task and
    comment to pinning the emitter only" as an alternative; the task's own
    Suggested fix says "so the emitted format and its documentation cannot drift
    again", so narrowing would have been an unstated AC change.
  - Test 2b pins `REJECTED:r<id>|` and not the full spec. Rewording
    `<marker line>` is not drift; dropping the `r` is. Pinning the whole string
    would fail on legitimate prose edits and train people to weaken the guard.
  - Each site is checked with a *pair* of assertions (spec present ≥1 AND
    prefix-less spec absent). The presence half is the vacuity guard: without
    it, deleting a file's format documentation would make the guard pass.
  - Checked per file rather than with one repo-wide grep, so a failure names the
    site that drifted.
  - `remove`'s verb comment (`:64-66`) does not say its `REMOVED:` /
    `NOT_FOUND:` csv is `r`-prefixed. Left alone: underspecified, not wrong, and
    outside the reported defect.
- **Upstream defects identified:** None.
