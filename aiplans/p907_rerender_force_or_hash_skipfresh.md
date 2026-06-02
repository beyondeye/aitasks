---
Task: t907_rerender_force_or_hash_skipfresh.md
Base branch: main
plan_verified: []
---

# Plan: t907 — Fix rerender skip-if-fresh masking git-induced source drift

## Context

`aitask_skill_rerender.sh` is the auto-repair path that refreshes committed,
git-tracked headless prerenders (`task-workflow-remote-/`,
`aitask-pickrem-remote-/`, `aitask-pickweb-remote-/`). It calls
`aitask_skill_render.sh`, whose skip-if-fresh logic
(`skill_template.py::_is_stale`) is **mtime-based**.

The bug (surfaced in t903): when a source closure file
(`.claude/skills/task-workflow/*.md`) is edited and committed *without* a
same-commit re-render, the committed prerender drifts. On any later
`git checkout`/clone, git resets the mtimes of source **and** target to the
checkout timestamp, so `target.mtime < max_source.mtime` is **false** →
`_is_stale` returns "fresh" → the write is skipped. `rerender` then reports
`RERENDERED:N` with an empty diff and the stale prerender is never repaired.
Recovering t903's renders required a manual `--force`.

Confirmed during exploration:
- Only the three `*-remote-` prerenders above are git-tracked; all other
  rendered dirs (e.g. `aitask-pick-fast-/`) are gitignored, generated on the
  fly, and never hit the git-mtime-equalization case. So the bug's blast
  radius is exactly the committed headless prerenders.
- In `walk_closure`, **rendering always happens** — the `plan` list of
  `(src, target, rendered_content)` is built unconditionally. Only the disk
  *write* is gated by `_is_stale`. So a content comparison is essentially
  free: the fresh content is already in memory.

## Chosen approach: additive content-diff safety net (task option (b))

Fix at the renderer level (`skill_template.py`) so **every** caller benefits,
not just the rerender driver. Keep the existing mtime fast-path and **add** a
content comparison as an authoritative fallback. Write the closure if:

```
force  OR  _is_stale(...)  OR  any target's on-disk content != freshly rendered content
```

### Edit 1 — `.aitask-scripts/lib/skill_template.py`

Add a helper near `_is_stale` (~line 284):

```python
def _any_target_differs(plan: list) -> bool:
    """True if any target is missing or its on-disk content differs from the
    freshly rendered content. Used as a safety net alongside the mtime-based
    `_is_stale`: git checkout/clone equalizes source and target mtimes, which
    can mask real source drift in committed prerenders (t907). Content
    comparison is authoritative and effectively free — `walk_closure` already
    renders every target's content into the plan."""
    for _src, target, content in plan:
        try:
            if target.read_text(encoding="utf-8") != content:
                return True
        except OSError:
            return True  # missing/unreadable target → must (re)write
    return False
```

Change the write gate in `walk_closure` (~line 369):

```python
    if write:
        if force or _is_stale(plan, profile_yaml, include_deps) or _any_target_differs(plan):
            for _src, target, content in plan:
                _atomic_write(target, content)
```

Update the `walk_closure` docstring + the module header comment in
`aitask_skill_render.sh` to mention the content-diff safety net.

**Why additive, not replacement:** existing tests (Test7 / Test7b in
`test_skill_render_uniform.sh`) assert that `touch`-ing a source (mtime bump,
identical content) re-renders the chain. A pure content-replacement would
make those skip (output unchanged) and break the tests. The additive gate
preserves all current behavior (touch → mtime-stale → rewrite; identical
re-render → skip) and *only adds* writes in the drift case the bug is about.

### Edit 2 — `tests/test_skill_render_uniform.sh`

Add **Test 7c** reproducing the t903 git-equalization scenario:
1. Render skill A fresh (target written).
2. Overwrite the target with stale content (simulating a drifted commit).
3. Force source.mtime == target.mtime (or target newer) via `touch -r` so
   `_is_stale` alone would report "fresh".
4. Re-render **without** `--force`.
5. Assert the target's content was restored to the real render (stale marker
   gone) — proves content-diff recovery independent of mtime.

This directly encodes the task's requested repro ("revert the renders to
stale state, run without `--force`, confirm restored").

### Edit 3 — docs

- `.aitask-scripts/skill_templates/README.md` (§Staleness, ~line 56): note
  that, alongside the mtime fold into `_is_stale()`, a content-diff safety
  net guarantees committed prerenders are repaired even when git checkout
  equalizes mtimes.

## Out of scope / rejected alternatives

- **Option (a): pass `--force` from `aitask_skill_rerender.sh`.** One-line,
  but only patches the rerender driver (not other `render.sh` callers) and
  re-introduces redundant unconditional writes across the 30 overlapping
  closure calls the driver makes. The renderer-level fix is more complete and
  keeps skip-if-fresh's write-avoidance benefit. Not chosen.
- **Pure content-hash replacement of `_is_stale`.** More invasive: forces
  rewriting Test7/Test7b (touch-based) and discards the cheap mtime fast
  path. The additive net achieves the same robustness with smaller blast
  radius. Not chosen.
- No change to `aitask_skill_rerender.sh` logic, the `--force` flag, or
  `walk-check` (write=False path is unaffected).

## Blast radius

- Behavior change is strictly "write in one more case" (content drift under
  equal mtimes). Content written is unchanged → **goldens and parity tests
  unaffected**; no `.md.j2`/closure edits → **no goldens regen needed**.
- Tiny added cost: when not forced/stale, read N small target md files and
  compare (microseconds; N≈ a handful per closure). `render_skill` is
  deterministic given (source, profile, agent), so no rewrite churn.

## Verification

1. `bash tests/test_skill_render_uniform.sh` — existing Test7/7b/8 stay green;
   new Test 7c passes.
2. `python3 tests/run_all_python_tests.sh` (or the skill_template suite) — no
   regressions.
3. `./.aitask-scripts/aitask_skill_verify.sh` — OK (no stub/template changes).
4. Manual t903 repro: revert the three `task-workflow-remote-*/planning.md`
   (and pickrem/pickweb closures) to a stale state, equalize mtimes, run
   `./.aitask-scripts/aitask_skill_rerender.sh remote`, confirm the Step 6.0a
   block is restored with a **non-empty** git diff and no manual `--force`.
5. `shellcheck` on any touched shell (only comment edits expected).

## Risk

### Code-health risk: low
- None identified. Additive write gate (strictly one more write-case); content
  written is unchanged so goldens/parity are unaffected; mtime fast-path and
  `walk-check` path preserved; small, localized blast radius.

### Goal-achievement risk: low
- None identified. Content comparison definitively fixes the mtime
  false-negative; new Test 7c encodes the task's requested repro.

## Step 9 (Post-Implementation)

Standard cleanup/archival per task-workflow Step 9 (working on current branch;
no worktree). Commit code (`skill_template.py`, test, README) with
`bug: <desc> (t907)`; plan file via `./ait git`.
