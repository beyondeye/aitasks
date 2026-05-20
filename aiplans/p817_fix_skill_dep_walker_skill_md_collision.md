---
Task: t817_fix_skill_dep_walker_skill_md_collision.md
Base branch: main
plan_verified: []
---

# Plan: Fix skill dep-walker SKILL.md target-path collision (t817)

## Context

`.aitask-scripts/lib/skill_template.py` implements the t777_22 dep-walker that
recursively renders a templated skill's closure (`SKILL.md.j2` entry + every
referenced `.md` procedure file) into a per-profile sibling tree
`<skill>-<profile>-/`.

`discover_refs` uses `SHORT_REF_RE` to find sibling refs like `proc.md`. A bare
`SKILL.md` token appearing **in prose** inside a procedure file (e.g. a header
"Referenced from Step N of the main SKILL.md workflow") is matched as a sibling
ref. It resolves to the skill's real stub file `.claude/skills/<skill>/SKILL.md`
(which genuinely exists, so the existence-based false-positive filter cannot
catch it). The walker enqueues that stub as a closure node.

The bug: `walk_closure` computes the entry-point target as
`entry_target = <repo>/<root>/<skill>-<profile>-/SKILL.md` (hardcoded
`SKILL.md`), while the entry **source** is `<skill>/SKILL.md.j2`. When the stub
`<skill>/SKILL.md` is enqueued, `_target_path_for` maps it to the *same*
`<skill>-<profile>-/SKILL.md` path. The `plan` list then holds two entries
writing the same target; in the write loop the last write (the stub) silently
overwrites the rendered entry-point.

t777_11 worked around this by rewording aitask-qa's 6 procedure-file headers to
drop the bare `SKILL.md` token. This plan fixes the root cause so any future
templated skill is safe. (The t777_11 rewording is harmless and stays as-is —
not in scope.)

## Root cause trace

`walk_closure` (`skill_template.py:205-262`):
- `entry_target` (line 223): `<skill>-<profile>-/SKILL.md`.
- Enqueue loop (lines 247-253): a discovered ref to `<skill>/SKILL.md` resolves
  via `_target_path_for` to exactly `entry_target` — collision.
- Write loop (lines 258-260): iterates `plan` in append order; last write wins.

Note: `_target_path_for` is injective on real source files (skill, rest) →
target, so the **only** collision possible is this entry stub vs. the entry
template. A general collision is otherwise unreachable, but a guard makes any
future regression loud instead of silent.

## Changes

### 1. `.aitask-scripts/lib/skill_template.py` — skip the entry-target self-ref

In `walk_closure`'s enqueue loop (currently lines 247-253), compute
`child_target` *before* marking visited, and skip when it equals `entry_target`:

```python
        # Enqueue unvisited children for further walking.
        for ref in refs:
            child_src = ref["resolved_source"]
            if child_src in visited:
                continue
            child_target = _target_path_for(child_src, agent, profile_name, repo_root)
            if child_target == entry_target:
                # A prose mention of the skill's own SKILL.md resolves to the
                # entry-point stub, whose target path collides with the
                # rendered entry-point. The stub is not a real closure
                # dependency — skip it so it never overwrites the entry.
                visited.add(child_src)
                continue
            visited.add(child_src)
            queue.append((child_src, child_target))
```

### 2. `.aitask-scripts/lib/skill_template.py` — collision guard (tripwire)

After the BFS `while queue` loop and before `if write:` (currently line 257),
fail loudly on any *remaining* target-path collision:

```python
    # Guard: every closure source must map to a distinct target path. The
    # entry-target collision (prose SKILL.md ref) is filtered above; any
    # remaining collision is a walker bug — fail loudly instead of letting
    # the last write silently win.
    targets_seen: dict[Path, Path] = {}
    for src, target, _content in plan:
        prior = targets_seen.get(target)
        if prior is not None and prior != src:
            raise RuntimeError(
                f"Closure target-path collision: '{prior}' and '{src}' "
                f"both render to '{target}'"
            )
        targets_seen[target] = src
```

Placed before `if write:` so `walk-check` (no-write validation) catches it too.
`_main_walk` already wraps `walk_closure` in `try/except` and reports a non-zero
exit, so the `RuntimeError` surfaces cleanly on the CLI.

### 3. `tests/test_skill_render_uniform.sh` — regression test (Test 12)

Insert a new test before the `Summary` section (after Test 11, line 366). It
creates a synthetic skill whose procedure file mentions the skill's own
`SKILL.md` in prose, renders it, and asserts the entry target keeps the
**rendered template** content — not the stub content:

```bash
# ============================================================================
# Test 12 — Procedure file mentions the skill's own SKILL.md in prose:
#   the stub must NOT overwrite the rendered entry-point (t817).
# ============================================================================

SK_STUBREF="${PREFIX}stubref"
mkdir -p ".claude/skills/$SK_STUBREF"
# Templated entry: distinguishing rendered content + a Jinja marker.
cat > ".claude/skills/$SK_STUBREF/SKILL.md.j2" <<'EOF'
# Stubref RENDERED ENTRY (agent={{ agent }})
See proc_step.md for the procedure.
EOF
# Stub SKILL.md dispatch surface — must never leak into the entry target.
cat > ".claude/skills/$SK_STUBREF/SKILL.md" <<'EOF'
# Stubref STUB SURFACE — must not overwrite the rendered entry
EOF
# Procedure file mentions the skill's own SKILL.md in prose.
cat > ".claude/skills/$SK_STUBREF/proc_step.md" <<'EOF'
# Procedure step
Referenced from Step 3 of the main SKILL.md workflow.
EOF

set +e
"$RENDER" "$SK_STUBREF" --profile fast --agent claude
RC=$?
set -e
assert_eq "Test12: stub-ref render exits 0" "0" "$RC"
assert_file_exists "Test12: entry target rendered" \
    ".claude/skills/${SK_STUBREF}-fast-/SKILL.md"
assert_file_exists "Test12: procedure file rendered" \
    ".claude/skills/${SK_STUBREF}-fast-/proc_step.md"

STUBREF_OUT="$(cat ".claude/skills/${SK_STUBREF}-fast-/SKILL.md")"
assert_contains "Test12: entry target keeps rendered template content" \
    "RENDERED ENTRY (agent=claude)" "$STUBREF_OUT"
TOTAL=$((TOTAL + 1))
if echo "$STUBREF_OUT" | grep -qF 'STUB SURFACE'; then
    FAIL=$((FAIL + 1))
    echo "FAIL: Test12: stub content leaked into rendered entry-point"
else
    PASS=$((PASS + 1))
fi
```

The existing `cleanup()` trap already removes `.claude/skills/${PREFIX}*`, so
`_t777_22_test_stubref` and its `-fast-` output dir are cleaned up automatically.

## Why this is safe for existing skills/goldens

No real templated skill currently has a procedure file mentioning a bare
`SKILL.md` token (t777_11 reworded aitask-qa's headers). The skip therefore
changes no real render output, and the collision guard never fires for real
skills. Existing golden outputs in `tests/golden/` should be unchanged — to be
confirmed in verification (no golden regeneration expected).

Test 5 (cycle A→B→A, which creates a `SK_CY_A/SKILL.md` stub) only does
`assert_file_exists` on the entry target, so it passes both before and after;
post-fix the entry target simply keeps its rendered content instead of being
clobbered by the stub.

## Verification

1. Targeted regression suite (includes the new Test 12):
   ```bash
   bash tests/test_skill_render_uniform.sh
   ```
2. Full skill-render / template suites — confirm no collateral breakage and no
   golden drift:
   ```bash
   bash tests/test_skill_render.sh
   bash tests/test_skill_template.sh
   bash tests/test_skill_render_aitask_qa.sh
   ```
   (and the other `tests/test_skill_render_*.sh` golden drivers)
3. Skill closure verification:
   ```bash
   ./.aitask-scripts/aitask_skill_verify.sh
   ```
4. Lint:
   ```bash
   shellcheck tests/test_skill_render_uniform.sh
   ```

## Step 9 — Post-Implementation

After review/approval: commit code + plan separately, then merge, run
`verify_build` if configured, archive via `aitask_archive.sh 817`, and push per
the task-workflow Step 9 procedure.

## Files modified

- `.aitask-scripts/lib/skill_template.py` — enqueue-loop skip + collision guard
- `tests/test_skill_render_uniform.sh` — new Test 12 regression test
