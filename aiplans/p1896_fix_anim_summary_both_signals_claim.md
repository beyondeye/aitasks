---
Task: t1896_fix_anim_summary_both_signals_claim.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1896 — anim summary: stop claiming "both signals are in curve.tsv" when p_edge is blank

## Context

`_write_anim_summary()` in `.aitask-scripts/screen_recording/video_prep.py:709-710`
prints, for every analysed segment with a fitted signal:

```
- fitted signal: <signal> (both signals are in curve.tsv)
```

That parenthetical is false whenever `vp_core.analyze_frames()` found no edge
track (fades, cross-fades): it sets `p_edge=None`
(`.aitask-scripts/screen_recording/vp_core.py:590`), and `_write_curve_tsv()`
(`video_prep.py:535-552`, `opt()` helper) then writes blank `p_edge` cells.
The docs were corrected in t1893_1; the helper's own output still makes the
false claim. Spawned as an upstream_defect follow-up of t1893_1.

`signal` is non-None only on the final branch of `analyze_frames()`, where
`p_blend` is always set — so the only variable is `p_edge`.

## Changes

### 1. `.aitask-scripts/screen_recording/video_prep.py` (~line 709)

Replace the unconditional line with a branch on `p_edge`:

```python
        if r.get("signal"):
            where = ("both signals are in curve.tsv" if r.get("p_edge") is not None
                     else "p_blend in curve.tsv; no edge track, so p_edge is blank")
            lines.append(f"- fitted signal: {r['signal']} ({where})")
```

Same key/predicate `_write_curve_tsv()` uses (`res.get("p_edge")` / `seq is None`),
so the summary and the TSV are decided by the same value.

### 2. `tests/test_screen_recording_cli.py`

- **`test_fade_uses_blend_signal`** (line 117): capture `out` (currently `_`),
  then:
  - read `out/"s01"/"curve.tsv"` with `csv.DictReader(..., delimiter="\t")`
    (`csv` already imported) and assert every `p_edge` cell is `""` and every
    `p_blend` cell is non-empty — pins the fixture precondition so that if the
    synthetic fade ever gains an edge track, the test fails loudly instead of
    silently exercising the other branch;
  - assert the summary contains
    `"- fitted signal: blend (p_blend in curve.tsv; no edge track, so p_edge is blank)"`
    and does **not** contain `"both signals are in curve.tsv"`.
- **`test_slide_right_ease_out`** (line 89): it already reads `summary`; add the
  positive-branch assertions — `curve.tsv` has non-empty `p_edge` cells and the
  summary contains `"- fitted signal: edge (both signals are in curve.tsv)"`.

No doc change: a repo-wide grep finds no doc quoting the summary line.

## Verification

```bash
python3 tests/test_screen_recording_cli.py -v          # needs ffmpeg; module skips without it
bash tests/run_all_python_tests.sh --test-dir tests 2>&1 | tail -3   # read last line verdict; check PIPESTATUS
```

Red proof: land the test edits (step 2) **before** the code fix (step 1), run the
module, and confirm the fade assertion fails on the old text while the slide
assertion passes; then apply step 1 and re-run green.

## Step 9 reference

Post-implementation: commit code (`bug: ... (t1896)`), then Step 9 archival via
the task-workflow (current-branch mode, no merge).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
