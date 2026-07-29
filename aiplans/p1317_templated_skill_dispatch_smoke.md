---
Task: t1317_templated_skill_dispatch_smoke.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1317 — Templated skill dispatch-contract smoke test

## Context

t1311 converts `aitask-shadow` — a **live, minimonitor-spawned** skill — to the
stub + `SKILL.md.j2` pattern. That conversion rewrites four stub surfaces,
deletes three "Source of Truth" redirects, and newly renders nine sub-procedures
into the Codex and OpenCode trees. A mistake breaks shadow launch from
minimonitor for every agent, and the goldens only prove those sub-procedures
*render*, not that they *land where the stub says to read them*.

This task is the "before" risk mitigation t1311 depends on: a **generic,
discovery-based dispatch-contract smoke test** over every templated skill ×
every agent surface. Written against the skills already templated so it lands
independently, and discovering its subjects at runtime so `aitask-shadow` is
covered automatically the moment t1311 converts it.

### What already exists (do not reinvent)

`.aitask-scripts/aitask_skill_verify.sh` already checks, per (skill, agent) over
3 surfaces: stub exists, stub contains a resolver call, a render call, and a
trailing-hyphen Read path; template renders; `walk-check` closure is clean.

It does **not** do the four things this test adds, which are exactly the ones
t1311's risk is about:

| Gap in `aitask_skill_verify.sh` | Why it matters for t1311 |
|---|---|
| Greps the Read path against a regex built from its **own** restatement of the §3g mapping — never renders to disk and confirms the file is actually there | A stub can name a path nothing ever produces |
| Never executes `aitask_skill_render.sh` (uses `skill_template.py` stdout) | The on-disk dispatch target is never proven to exist |
| Never checks `.opencode/skills/<skill>/SKILL.md` (the 4th surface) | This is how the `aitask-trail` gap below went unnoticed |
| Never checks closure **completeness** against the authoring dir | "Nine sub-procedures never reach the Codex/OpenCode trees" is invisible |
| Never executes `aitask_skill_resolve_profile.sh` | Step 1 of the stub is unexercised |

## Pre-existing defect found while planning (in scope, user-confirmed)

`.opencode/skills/aitask-trail/SKILL.md` **does not exist**. 11 of the 12
templated skills have this stub; `aitask-trail` only has
`.opencode/commands/aitask-trail.md` — an oversight from t1210_3.
`tests/test_opencode_setup.sh:22` cannot catch it because it derives the expected
count from the tree itself (`git ls-files '.opencode/skills/aitask-*/SKILL.md'`),
so the missing file simply lowers both sides of the comparison.

The new test treats all four surfaces as mandatory, so this stub is created as
part of this task.

---

## Implementation

### 1. Add the missing OpenCode skill stub

**New file:** `.opencode/skills/aitask-trail/SKILL.md`

Body identical to `.opencode/commands/aitask-trail.md` (already correct:
resolver key `trail`, `--agent opencode`, target
`.opencode/skills/aitask-trail-<profile>-/SKILL.md`). Frontmatter follows the
`.opencode/skills/` convention seen in `.opencode/skills/aitask-pick/SKILL.md` —
`name:` **and** `description:` (the command form carries `description:` only):

```markdown
---
name: aitask-trail
description: Create, refresh, or show an implementation trail — a durable, wave-structured, evidence-backed task-sequencing artifact stored via ait artifact.
---
```

### 2. New test: `tests/test_skill_dispatch_contract.sh`

House style copied from `tests/test_skill_render_aitask_pick.sh` /
`tests/test_opencode_skill_legacy_pointers.sh`: `#!/usr/bin/env bash`, `set -e`
(the plurality in the skill-test set — not `set -euo pipefail`),
`SCRIPT_DIR`/`PROJECT_DIR` resolution, `PASS/FAIL/TOTAL` counters, and
`. "$PROJECT_DIR/tests/lib/asserts.sh"`. Ends with
`echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"` and
`[[ "$FAIL" -eq 0 ]] || exit 1`.

**Preamble.** The `minijinja` SKIP guard, verbatim from
`tests/test_skill_render_aitask_pick.sh:33-39` (source
`.aitask-scripts/lib/python_resolve.sh`, `require_ait_python`, exit 0 with a
`SKIP:` line if `minijinja` is absent).

**Reuse the canonical seam, don't restate §3g.** Source
`.aitask-scripts/lib/agent_skills_paths.sh` and call
`agent_skill_dir <agent> <skill> <profile>` for the expected rendered dir. That
helper (lines 59-77) is the bash half of the mapping the renderer's
`skill_template.py` mirrors, so the test never hardcodes the `-codex-` segment.

**Discovery** — mirrors `aitask_skill_verify.sh:35-37` exactly:

```bash
mapfile -t templates < <(
    find ".claude/skills" -mindepth 2 -maxdepth 3 -name 'SKILL.md.j2' -type f 2>/dev/null | sort
)
```

Skill name = `basename(dirname(tpl))`. **Never a hardcoded list** — this is what
makes the mitigation pick up `aitask-shadow` after t1311. (`mapfile` is already
used by the closest precedent, `tests/test_opencode_skill_legacy_pointers.sh`; a
`while read -r` loop is the bash-3.2-safe fallback if macOS portability bites.)

**Surface table** (4 rows per skill; only the *stub* locations are named here —
the rendered path always comes from `agent_skill_dir`):

| key | agent | stub path |
|---|---|---|
| `claude` | claude | `.claude/skills/<skill>/SKILL.md` |
| `codex` | codex | `.agents/skills/<skill>/SKILL.md` |
| `opencode-cmd` | opencode | `.opencode/commands/<skill>.md` |
| `opencode-skill` | opencode | `.opencode/skills/<skill>/SKILL.md` |

**Profile: `default` only.** The stub body is profile-agnostic by contract
(§3b/§3f), so the dispatch shape is profile-invariant and one profile proves it
while keeping 36 renders bounded. `default` also avoids touching the **committed**
`*-remote-` prerender dirs that `.gitignore:57-65` un-ignores.

**Core checker** — `check_surface <skill> <agent> <stub_path>`, prints one
`  - <problem>` line per problem to stdout and returns 0 (clean) / 1 (problems).
It does **not** touch `PASS/FAIL`, so the negative controls can invoke it and
assert the opposite outcome. Assertions, matching the task's list 1-5:

1. **Stub exists** at `<stub_path>`.
2. **Parse the Step-3 dispatch target out of the stub body** (never
   reconstruct it): grep the backticked path token ending in `/SKILL.md` that
   contains the literal `-<profile>-`, e.g.
   `` `.agents/skills/aitask-pick-<profile>-codex-/SKILL.md` ``. Substitute the
   literal `<profile>` → `default`, then assert it equals
   `$(agent_skill_dir "$agent" "$skill" default)/SKILL.md`. **This is the check
   that fails a codex stub missing the `-codex-` shared-root segment.**
3. **Rendering produces that exact path.** Run
   `./.aitask-scripts/aitask_skill_render.sh <skill> --profile default --agent <agent>`
   (silent + exit 0 on success; no `--force` needed — skip-if-fresh plus the
   t907 content-diff net still yield canonical output). Assert exit 0, then
   assert the file the **stub named** now exists.
4. **Closure completeness.** Every `*.md` in the authoring dir
   `.claude/skills/<skill>/` must have a same-named counterpart in the rendered
   dir. The stub `SKILL.md` maps 1:1 onto the `.j2`-rendered `SKILL.md`, so the
   rule is a plain set-containment check. Verified to hold today for the two
   skills that have sibling procedures — `aitask-qa` (6 procedures) and
   `aitask-pickrem` (`materialize-active.md`) — across all three agents. This is
   the assertion covering t1311's "rendered but never executed there" risk.
5. **Resolver key resolves.** Parse the key from
   `` `./.aitask-scripts/aitask_skill_resolve_profile.sh <key>` `` in the stub
   body, run it, assert exit 0 and exactly one non-empty output line.
   *Honest scope:* the resolver falls back to `default` for any unknown key and
   always exits 0, so this mainly proves the stub carries a well-formed, runnable
   Step-1 call — its distinct value over `aitask_skill_verify.sh` is that it
   actually **executes** it.

Render is idempotent, so the two OpenCode rows re-invoking the same
(skill, opencode) render is a cheap no-op; no caching needed.

**Main loop** — one assertion per (skill, surface) ≈ 48 tests:

```bash
for skill in ...; do
  for row in claude codex opencode-cmd opencode-skill; do
    problems="$(check_surface "$skill" "$agent" "$stub" 2>&1)"; rc=$?
    [[ -n "$problems" ]] && echo "$problems"
    assert_exit_zero_rc "dispatch contract: $skill [$row]" "$rc"
  done
done
```

### 3. Negative controls (AC #3)

Follows the scratch-prefix pattern of `tests/test_skill_render.sh:35-51` and
`tests/test_skill_verify.sh:34-52`, and the rationale of
`tests/test_prune_retired_skills.sh:221-224` ("A passing suite proves nothing
unless a weakened guard actually breaks it"). It **never mutates a committed
file**, so restore is `rm -rf` of the scratch dirs under a `trap cleanup EXIT`
plus a pre-clean — explicitly **not** `git checkout`, which would discard the
unrelated in-flight work currently in this worktree.

Build a scratch templated skill `_t1317_ctrl` with correct stubs at all four
surfaces, a `SKILL.md.j2` that references one sibling procedure, and that
procedure file. Then:

- **Positive control** — `check_surface` returns 0 for all four surfaces
  (proves the harness can *pass*, so a later failure is meaningful).
- **NC-1** — rewrite the claude stub's Step-3 target to a wrong dir →
  `check_surface … claude` must return non-zero.
- **NC-2** — strip the `-codex-` segment from the codex stub's Step-3 target →
  must return non-zero. This is the precise t1311 failure mode.
- **NC-3** — drop an unreferenced `orphan_proc.md` into the authoring dir (it can
  never enter the closure) → assertion 4 must return non-zero.

Each control asserts the mutation is real before asserting the failure (per
`test_prune_retired_skills.sh`), so a control that silently no-ops cannot pass.

**AC #3 is also demonstrated end-to-end at the top level**, not only inside the
suite: the verification section below runs the whole file against a temporarily
broken real stub and shows it exits non-zero.

### 4. Doc cross-reference

Add one sentence to `aidocs/framework/stub-skill-pattern.md` §3g pointing at
`tests/test_skill_dispatch_contract.sh` as the generic enforcement of the table
(mirroring how §3j already names its two enforcing tests). The mapping itself is
**not** restated — the doc stays the single source of truth.

## Out of scope

- Extending `aitask_skill_verify.sh` to the 4th surface — that changes a
  production script; the new test covers it. Worth a follow-up if desired.
- Goldens: this test asserts *paths and closure membership*, not rendered
  content, so no `tests/golden/` files are added or regenerated.

## Verification

```bash
# 1. Passes against the current tree (AC #2) — after the trail stub is added
bash tests/test_skill_dispatch_contract.sh

# 2. Nothing regressed in the existing skill suite
./.aitask-scripts/aitask_skill_verify.sh
bash tests/test_opencode_setup.sh
bash tests/test_opencode_skill_legacy_pointers.sh
bash tests/test_skill_render_aitask_trail.sh

# 3. shellcheck clean (AC #4)
shellcheck tests/test_skill_dispatch_contract.sh

# 4. Top-level negative control (AC #3) — restore by undoing the mutation only
cp .agents/skills/aitask-pick/SKILL.md /tmp/t1317_stub.bak
sed -i 's|aitask-pick-<profile>-codex-|aitask-pick-<profile>-|' .agents/skills/aitask-pick/SKILL.md
bash tests/test_skill_dispatch_contract.sh; echo "exit=$?"   # MUST be non-zero
cp /tmp/t1317_stub.bak .agents/skills/aitask-pick/SKILL.md   # NOT git checkout
git diff --stat .agents/skills/aitask-pick/SKILL.md          # MUST be empty

# 5. No stray state left behind
git status --porcelain          # only the intended new/changed files
```

Expected: ~48 (skill × surface) assertions plus the control block, all passing;
step 4 exits non-zero and step 5 shows a clean restore.

## Risk

### Code-health risk: low

- The deliverable is a new, self-contained test file plus one 20-line stub; the
  only production-surface change is the `aitask-trail` OpenCode stub, which is
  additive and mirrors 11 existing siblings · severity: low · → mitigation: none
- The test renders 12 skills × 3 agents into gitignored trailing-hyphen dirs.
  It uses `default` (never the committed `*-remote-` prerenders) and writes only
  canonical output, so it cannot leave state a later `aitask_skill_verify.sh`
  trips over · severity: low · → mitigation: none

### Goal-achievement risk: low

- Assertion 5 is weaker than it reads: `aitask_skill_resolve_profile.sh` exits 0
  for any single argument, so it can only fail on a missing/malformed Step-1
  call. Stated explicitly above rather than left as an implied guarantee ·
  severity: low · → mitigation: none
- The mitigation is only useful if it stays discovery-based. Discovery mirrors
  `aitask_skill_verify.sh`'s `find`, and NC-1/NC-2/NC-3 prove the assertions
  bite, so an inert (always-green) test is ruled out by construction ·
  severity: low · → mitigation: none

## Step 9 (Post-Implementation)

Standard: merge approval, `ait gates run 1317` (declared gate: `risk_evaluated`),
worktree/branch cleanup (n/a — current-branch profile), then
`./.aitask-scripts/aitask_archive.sh 1317`. Archival unblocks **t1311**, whose
`depends:` names this task.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, three files:
  - `tests/test_skill_dispatch_contract.sh` (new, 366 lines) — Test 1 discovery
    (12 skills via the `aitask_skill_verify.sh:35-37` `find`), Test 2 the
    dispatch contract over 12 skills × 4 surfaces = 48 assertions, Test 3 the
    negative-control block (12 assertions). 61 total, all passing.
  - `.opencode/skills/aitask-trail/SKILL.md` (new) — the missing 4th-surface
    stub, body mirroring `.opencode/commands/aitask-trail.md` with the
    `.opencode/skills/` frontmatter convention (`name:` + `description:`).
  - `aidocs/framework/stub-skill-pattern.md` — two §3g notes: the OpenCode
    skill-dir stub as a required surface, and the enforcement pointer to the new
    test (bidirectional doc↔test cross-ref; the table itself is not restated).

- **Deviations from plan:** Two, both mechanical.
  1. Discovery uses a `while IFS= read -r` loop instead of `mapfile` (the plan
     named `mapfile` with a bash-3.2 fallback noted); the loop is the fallback,
     taken up front rather than deferred.
  2. NC-1's mutation was planned as `sed -i` on the fixture. Replaced with a
     second `write_ctrl_stub` call naming a wrong target — same effect, and it
     sidesteps the BSD/GNU `sed -i` divergence entirely (see
     `aidocs/framework/sed_macos_issues.md`).

- **Issues encountered:**
  - **The negative controls caught a real bug in the first draft of the test
    itself.** `check_surface` toggled `set +e` / `set -e` around the resolver
    invocation. Because `set -e` is shell-global (not function-scoped), the
    inner `set -e` re-enabled errexit *inside* `probe()`'s command substitution,
    so `check_surface`'s `return 1` killed the subshell before `probe` could
    echo `problems`. All three in-suite controls reported `''` instead of
    `problems` — a suite that looked structurally complete but proved nothing.
    Fixed by removing errexit toggling in both functions and using the
    condition-context idiom `out="$(cmd)" || rc=$?`. This is the concrete
    argument for the `feedback_negctrl_proves_test_discriminates` rule: the
    positive path was green throughout.
  - `shellcheck` (no `-x`) reports three SC1091 infos for the sourced libs;
    `shellcheck -x` is clean. One SC2016 on the parse regex is a false positive
    (the backticks are literal markdown in the stub, not command substitution)
    and carries an inline `disable` with that reason.

- **Key decisions:**
  - **Reuse the canonical seam, don't restate §3g.** The expected rendered path
    comes from `agent_skill_dir` in `.aitask-scripts/lib/agent_skills_paths.sh`,
    compared against the path *parsed out of the stub body*. Three-way agreement
    (hand-authored stub ↔ bash helper ↔ actual render output) is what makes a
    codex stub missing `-codex-` fail; reconstructing the path from the same
    mapping the stub is supposed to satisfy would have been circular.
  - **One profile (`default`), not all three.** The stub body is profile-agnostic
    by contract (§3b/§3f) so the dispatch shape is profile-invariant; `default`
    also keeps the test away from the *committed* `*-remote-` prerender dirs that
    `.gitignore:57-65` un-ignores.
  - **Controls mutate a scratch fixture, never a committed file.** Restore is
    `rm -rf` of the `_t1317_ctrl` prefix under `trap cleanup EXIT` plus a
    pre-clean — deliberately not `git checkout`, which would have discarded an
    unrelated concurrent session's in-flight minimonitor work present in this
    checkout throughout the task.
  - **Closure rule scoped to the skill's own authoring dir.** Every `*.md` in
    `.claude/skills/<skill>/` must have a same-named counterpart in the rendered
    dir (the stub `SKILL.md` maps 1:1 onto the `.j2`-rendered `SKILL.md`).
    Verified to hold today for the only two skills with sibling procedures —
    `aitask-qa` (6) and `aitask-pickrem` (1). A whole-transitive-closure rule
    would have been wrong: `task-workflow` renders 29 of its 32 files into any
    given closure, so three legitimately-unreachable files would fail it.

- **Verification performed:** new suite 61/61 exit 0; `shellcheck -x` clean;
  `aitask_skill_verify.sh` OK (12 × 3); `test_opencode_skill_legacy_pointers.sh`
  108/108; `test_opencode_setup.sh` 31/31; `test_skill_render_aitask_trail.sh`
  52/52; `test_skill_verify.sh` 24/24. Two top-level negative controls against
  *real* stubs (codex `-codex-` strip; trail stub hidden) each drove the suite to
  exit 1 with a precise diagnostic and were restored from a scratchpad copy with
  an empty resulting `git diff`. No scratch dirs left behind.

- **Upstream defects identified:**
  - `.opencode/skills/aitask-trail/SKILL.md` — missing entirely since t1210_3
    (`3386e1f43`); 11 of 12 templated skills had this stub. **Fixed in this
    task** at the user's direction, since the new test treats all four surfaces
    as mandatory and AC #2 requires a green suite.
  - `tests/test_opencode_setup.sh:22` — derives `expected_skill_count` from the
    tree under test (`git ls-files '.opencode/skills/aitask-*/SKILL.md'`), so a
    missing wrapper lowers both sides of the comparison and the test stays green.
    This is why the trail gap survived. Self-referential expectation, not fixed
    here (out of scope); worth a separate task if the count is meant to be a
    real guard.
  - `.aitask-scripts/aitask_skill_verify.sh:57-64` — `_stub_path_for` covers only
    3 surfaces and omits `.opencode/skills/<skill>/SKILL.md`; its Read-path check
    also greps a regex rebuilt from its own restatement of §3g rather than
    confirming the rendered file exists. Left alone deliberately (production
    script; the new test covers both gaps).
  - `.gitignore:43` — comment points at the stale path
    `.claude/skills/task-workflow/stub-skill-pattern.md`; the live doc is
    `aidocs/framework/stub-skill-pattern.md`. Cosmetic.
