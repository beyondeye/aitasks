---
Task: t2317_fix_sitrep_stale_lock_background_overclaim.md
Base branch: main
Output branch: main
---

# t2317 — Stop the `stale_lock` background claiming the holder is gone

## Context

`BACKGROUND["stale_lock"]` in `.aitask-scripts/lib/sitrep_crash.py:139-140`
reads "A lock remains for this task but no live session holds it (no PID
anchor, or the task is no longer Implementing)." The decision table
(`recovery_verdict`) reaches `stale_lock` by two routes:

- row 5 — the lock has no PID anchor (any task status). There is no process to
  check, so the holder's liveness is **unknown**, not proven dead.
- row 7 — an anchored holder proven dead, on a task that is no longer
  Implementing.

(A holder proven alive is row 3 and never makes an item.) The text is right for
row 7 only. t2299_4 already corrected the skill, `aidocs/framework/sitrep.md` and
the website to say a stale lock means "check who holds it, never proof that
nobody does"; this stored background — written into every `stale_lock` item's
context — is the last surface that still over-claims.

## Steps

1. **Reword the constant** — `.aitask-scripts/lib/sitrep_crash.py`, the
   `"stale_lock"` entry of `BACKGROUND`:

   ```python
   "stale_lock": ("A lock remains for this task: either it records no PID "
                  "anchor, so whether its holder still runs cannot be checked, "
                  "or its holder is gone and the task is no longer "
                  "Implementing. Check who holds it before releasing it."),
   ```

   Wording mirrors the skill's `stale_lock` bullet
   (`.claude/skills/aitask-sitrep/SKILL.md.j2:95-99`). Well under
   `sitrep_todo.MAX_BACKGROUND` (400).

2. **Regression test** — `tests/test_sitrep_crash.py`, new method in the
   `Rendering` class (it already covers per-category title/group rendering):
   `test_stale_lock_background_never_claims_the_holder_is_gone`:
   - the text does not contain "no live session holds" (the over-claim);
   - it names both routes ("no PID anchor" and "no longer Implementing");
   - every `BACKGROUND` value fits `st.MAX_BACKGROUND` (so `context_entry`'s
     slice never truncates it) — import `sitrep_todo as st` if not already.

No test pins the old text (grep: only the definition and the
`context_entry` consumer at `sitrep_crash.py:1098`), and the bash suite asserts
categories/outcomes, not background prose.

## Idempotence consequence (record in the commit body)

`Pass` compares the proposed context `body_lines()` with the recorded one
(`sitrep_crash.py:1230-1235`). Every **open** `stale_lock` item therefore differs
once: the next detector pass rewrites it (`APPLIED`, new `checked_at`), and
later passes are `unchanged` again. Dismissed items with the same episode key
are kept dismissed (the `recorded == key` dismissed branch runs first), so no
dismissed item reopens. Acceptable: a one-time context refresh carrying the
corrected text is the point of the change. The commit body states it.

## Verification

```bash
python3 tests/test_sitrep_crash.py
bash tests/test_sitrep_crash.sh
```

Both must pass. Step 9 (Post-Implementation) handles archival — current-branch
mode, nothing to merge.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
