---
Task: t1889_fix_extract_multi_extension_truncation.md
Base branch: main
Output branch: main
---

# t1889 — right boundary for `plan_paths.extract()`

## Context

`.aitask-scripts/lib/plan_paths.py` `_TOKEN`
(`[A-Za-z0-9_./-]+\.(?:sh|py|md|yaml|yml|json|toml)`) has no right boundary, so
a path with a longer extension is truncated to a *different* file:
`.claude/skills/aitask-pick/SKILL.md.j2` → `.claude/skills/aitask-pick/SKILL.md`
(the rendered stub). Parallel admission (`lib/parallel_admission_collect.py`,
`plan_extraction` / task-body path) and the trail gatherer
(`lib/trail_gather.py` `_classify_plan_paths`) still use `extract()`, so a plan
that only edits a template can collide with whatever task touches the stub.
Risk-mitigation "after" follow-up of t1877 (findings doc §7 names this exact fix).

Planning probe (read-only, current tree): over 454 plans (archived + active),
the proposed rule changes 51 plans / 70 token occurrences, adds no token, and
empties no plan's surface. Every removed token is a real truncation: `.md.j2`
(108 occurrences of the pattern), `.jsonl`, `.shadow_*` (`foo.sh` + `adow…`),
`.md.orig`, `.sha256`, `.json.tmp`, URLs like `brew.sh/Taps`, and two
`x.py._attr` Python attribute mentions (the one accepted recall cost).

## Decision: the boundary rule

A match must not be immediately followed by a token character
(`[A-Za-z0-9_./-]`), **except** one sentence-final `.` that is itself not
followed by a token character — the same rule `find_references` already applies
(findings §3), so the two entry points agree on the right edge:

```python
_TOKEN = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:" + "|".join(_EXTENSIONS) + r")"
    r"(?![A-Za-z0-9_/-]|\.[A-Za-z0-9_./-])")
```

Pinned outcomes:

| input | before | after | why |
|---|---|---|---|
| `x/SKILL.md.j2` | `x/SKILL.md` | — | the bug |
| `a.mdx` | `a.md` | — | different extension |
| `a.md.` / `a.md.\n` | `a.md` | `a.md` | sentence-final period kept |
| `` `a.md`. `` / `a.md,` | `a.md` | `a.md` | delimiter |
| `a.md..` (ellipsis) | `a.md` | — | accepted: same as `find_references` |
| `x/a.py/b` | `x/a.py` | — | `/` continues the path (a dir named `a.py`) |
| `foo.json.tmp` | `foo.json` | — | |

`/` is in the lookahead (task text's example omitted it): `a.py/b` names a
directory, and the corpus hits (`brew.sh/Taps`, `…md/seed`) are all non-files.

## Steps

### 1. `.aitask-scripts/lib/plan_paths.py`

- Replace `_TOKEN` with the rule above; rewrite the comment above it (no longer
  "byte-identical to the grep pipeline": the right boundary was added in t1889,
  mirroring `find_references`' `_AFTER` rule).
- Module docstring: the GRAMMAR paragraph says "deliberately unchanged from the
  pipeline this replaces" — add that the right boundary (t1889) is the one
  deliberate change, with the `.md.j2` reason; update the closing sentence that
  says the gatherer/admission "keep the extension grammar above, unchanged".
- Keep `extract()`'s signature and everything else untouched (seam guard (b)
  stays green: the change is inside `plan_paths.py`).

### 2. `tests/test_plan_paths.py`

In `ExtractionTests` add `test_a_longer_extension_is_not_truncated_to_another_file`
(`x/SKILL.md.j2` → `[]`; template+stub text → stub only; `foo.json.tmp`,
`a.mdx`, `x/a.py/b` → `[]`) and `test_sentence_final_period_is_a_boundary_but_an_ellipsis_is_not`
(`a.md.`, `see a.md.\nnext`, `` `a.md`. ``, `a.md,` → `["a.md"]`; `a.md..` → `[]`).
Update the stale comment in `ReferenceKindsTests.test_longer_extension_is_not_a_reference`
("extract() yields `x/SKILL.md`…") and assert extract now agrees (`[]`).

### 3. `tests/test_remote_drift_check.sh` Test 14

Fixture is unaffected (no token is followed by a path char). Add `14f`: run
`plan_paths.py "$plan_path"` and assert its sorted output equals
`EXTRACTION_GOLDEN`, so the golden keeps documenting the live grammar instead of
silently drifting from it. Note in the golden's comment that t1889's boundary
leaves it unchanged.

### 4. Paired before/after measurement — one snapshot, two grammars

Separate CLI runs before and after the edit don't compare cleanly. The edit and
the tests sit between them, and identical task ids don't guarantee identical plan
contents, claim states, lock ages or committed surfaces. So both grammars are
scored **inside one process, against one frozen snapshot**. The grammar is the
only thing that varies.

Driver: a scratchpad script (`$SP/t1889_paired.py`, never committed). Its text
also goes into findings §7 as the reproduction, the same way t1877 did it.

- **"Before" grammar = the real prior code, not a hand-copied literal.** Load
  `git show <pre-edit sha>:.aitask-scripts/lib/plan_paths.py` into a throwaway
  module and take its `_TOKEN`. "After" = the edited module's `_TOKEN`. Each
  run sets `plan_paths._TOKEN` before it starts. `extract()` reads the global
  at call time, so every consumer that imported `plan_paths` picks it up.
  Nothing else in the code differs between the runs.
- **Freeze the volatile inputs once by rebinding the references the code
  actually calls.** The original function names don't work for this:
  `parallel_admission_collect` binds them at import time (`_GATE_PROBE =
  probe_gate_source`, …, `_LIVENESS = lock_holder_liveness`, lines ~381-417),
  and `collect` / `classify_liveness` call those saved names. Patching
  `probe_gate_source` or `lock_holder_liveness` would leave the live calls in
  place. Wrap each reference in a record/replay memo keyed on its arguments:
  - admission: `_GATE_PROBE`, `_LOCK_PROBE`, `_STATUS_PROBE`, `_LIVENESS`,
    `_TRACKED_SETS`, `_DATA_TREE`, `_FETCH`, `_BATCH_MAP` (bound seams), plus
    the module globals `locks_cache_age` and `resolve_corpora` (called by
    global name at call time, so rebinding the module attribute takes effect),
    plus `_LOCAL_HOST` pinned to a fixed string. Pass one fixed `now` to
    `collect_population(...)`. `now=` is the only clock read in `collect`
    (`time.time()` at line ~530 runs only when `now is None`).
  - trail gatherer: `trail_gather._GATE_PROBE`, `trail_gather._LOCK_PROBE`
    (its lock result embeds the `time.time()`-based cache age, so it has to be
    frozen), and `plan_paths.tracked_sets` (called by module attribute at
    `trail_gather.py:~930`). Then call `emit_inflight` once per grammar.
  - **Run A records, run B only replays.** In run B every memo raises on a
    cache miss, so a seam called with arguments run A never saw fails the
    measurement and can't quietly read live state. A missed seam then shows
    up as an error, not as a plausible verdict change.
- **Assert that the admission evidence outside the paths is identical before
  attributing anything to extraction.** Project `population.base` (the
  `AdmissionInput`) to every field except path surfaces and path tokens: the
  in-flight claim set, each claim's status / liveness / age, the per-source
  evidence, `now`, and the lock-cache age. The two runs' projections must be
  equal. A difference means a liveness or claim change, not a grammar change:
  rerun, don't report.
- **Validity fingerprint, taken before run A and after run B.** It covers code
  HEAD, task-data HEAD (`./ait git rev-parse HEAD`), `origin/aitask-locks`, and
  a sha256 over every `aiplans/**/*.md` and `aitasks/**/*.md`. If the two
  fingerprints differ, discard and rerun, and record the fingerprint in §7. For
  the trail gatherer, the `INFLIGHT:`/`INFLIGHT_SOURCE:` lines must also be
  identical between runs (same population).
- **Replay** (the `_run_replay` body: per-candidate `VERDICT_FOR` + `RATES` /
  `CAUSE_RATE`, `--candidates auto` population): report both rate lines.
  Diff verdicts per candidate. **For every candidate whose verdict changed**,
  print the token sets removed from its surface and from each colliding
  in-flight surface under the new grammar. The move is accepted only if every
  removed token has a longer-extension tail (`.md.j2`-style). Anything else is
  listed and explained in §7.
- **Sweep** (`--source plan`): run `_run_sweep` (or `sweep_population` +
  rows) under each grammar in the same process. The two `SWEEP_COHORT` digests
  must be equal, otherwise the archive moved and the run is rerun. Report
  `SWEEP` / `SWEEP_METRIC` before/after.
- **Trail `corpus_status`**: `INFLIGHT_SCAN:` before/after, plus the per-task
  `INFLIGHT_PATH:` diff. List every task whose surface becomes
  `no_extractable_paths` / `no_tokens`.
- **Fixed-corpus extraction diff** (all archived + active plans, both grammars
  in the same process): plans changed, removals grouped by tail, tokens added
  (must be 0), plans whose surface became empty (listed; the planning probe
  found none). This is the population-independent number. The paired runs
  above are the verdict-level ones.

`aidocs/framework/plan_path_reference_extraction_findings.md`:
- §7 "Parallel admission and the trail gatherer" — replace the "They keep the
  `.md.j2` truncation false positive…separate task" bullet with the resolution
  and a new "Right boundary (t1889)" block: the rule, the pinned table, the
  fixed-corpus counts, replay RATES/CAUSE_RATE before/after, sweep before/after,
  trail `corpus_status` before/after, and the accepted cost (`x.py._attr`,
  ellipsis).
- §2: one sentence that the truncation of a *longer extension* is fixed by the
  right boundary (the charset issues there remain).
- Related: mention the new 14f / test_plan_paths cases.

### 5. Verification

```bash
# shell suites — each run individually, every exit status checked
rc=0
for t in tests/test_plan_paths_seam.sh tests/test_remote_drift_check.sh \
         tests/test_parallel_admission_cli.sh tests/test_parallel_admission_preflight.sh; do
    bash "$t" || { echo "FAILED: $t"; rc=1; }
done
echo "shell rc=$rc"

# python coverage of the two extract() consumers, named explicitly
python3 -m pytest -q tests/test_plan_paths.py tests/test_trail_gather.py \
    tests/test_parallel_admission_collect.py tests/test_parallel_admission.py \
    tests/test_parallel_admission_sweep.py tests/test_parallel_admission_purity.py
# then the whole suite; read only the final verdict line
bash tests/run_all_python_tests.sh; echo "suite exit=$?"
```

Then Step 9 (Post-Implementation): commit code+docs as
`bug: Add right boundary to plan-path extraction (t1889)`, archive.

## Risk

### Code-health risk: low
- Recall loss for genuine references written as `file.py._attr` or followed by an ellipsis (2 + 0 corpus occurrences) — admission/trail lose that path. Accepted by design; same rule as `find_references`; documented in §7 · severity: low · → mitigation: none (accepted, measured in step 4)
- Two consumers (admission, trail gatherer) change verdicts on the live corpus — bounded to the 51 changed plans; measured before/after in step 4 · severity: low · → mitigation: none (in-plan measurement)

### Goal-achievement risk: low
- Replay/trail read a moving in-flight population, so a naive before/after could differ for reasons unrelated to the grammar · severity: low (residual — step 4 scores both grammars in one process against one frozen snapshot, with a fingerprint/cohort-digest validity check) · → mitigation: none (in-plan paired measurement)
- The paired driver freezes collector seams. A missed seam would let run B re-read live state (e.g. `_LIVENESS` dropping a claim whose holder exited, with no change to git or the files) · severity: low (residual: the bound references are rebound, not the original names; run B raises on any memo miss; the projection of the non-path `AdmissionInput` must be equal) · → mitigation: none (in-plan guards)
