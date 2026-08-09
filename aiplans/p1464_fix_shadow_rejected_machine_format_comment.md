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
