---
Task: t894_generalize_skill_verify_headless_prerender_check.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: Generalize the headless-prerender freshness check (t894)

## Context

`aitask_skill_verify.sh` is the pre-commit gate that keeps the four agent skill
trees consistent. Its **headless-prerender check** verifies that the committed
`*-remote-` prerenders (shipped so headless skills work on Claude Code Web where
`ait setup` never ran) stay in sync with their source `.md.j2` closures.

Today that check has two defects:

1. **Hardcoded scope.** It only fires for `if [[ "$skill" == "aitask-pickrem" ]]`
   (`aitask_skill_verify.sh:151-164`, tagged `TODO(t777_29)` — a task that does
   not exist). The committed `aitask-pickweb-remote-` and, critically, the
   `task-workflow-remote-` **closure** are never checked.
2. **Existence-only, not freshness.** Even for pickrem it only tests
   `[[ ! -f "$committed" ]]` — file present/absent. It never compares committed
   content against a fresh render, so source-vs-committed **drift** goes
   unnoticed. This is exactly the t888 failure: a source edit to
   `.claude/skills/task-workflow/planning.md` without a `aitask_skill_rerender.sh
   remote` left the committed `task-workflow-remote-` closure stale and nothing
   failed.

This task makes the check **declarative** (discover prerender-bearing skills via
a `prerender_for_headless: true` j2-frontmatter marker × profiles flagged
`headless: true`) and **content-based** (fail loudly on drift, not just absence),
so the whole drift class — across all three headless skills and every committed
closure file — fails at verify time.

The drift-detection machinery already exists: `_any_target_differs()` in
`skill_template.py:287` compares each closure target's on-disk content to a fresh
render (added in t907 precisely because git-equalized mtimes mask drift). It is
currently only consulted inside `walk_closure(..., write=True)`. We expose it
read-only via a new `walk-verify` CLI mode.

## Design decision (user-approved)

The `prerender_for_headless` marker lives in **j2 frontmatter** (per the task
suggestion). It propagates into rendered output, so the committed remote
prerenders and the affected SKILL goldens are regenerated in the same commit
(mechanical; enumerated under Verification).

## Scope boundary

`TODO(t777_29)` also tags a `.gitignore` block (`.gitignore:37`) for a future
`aitask_regen_gitignore_prerender.sh` that would auto-generate the hardcoded
`!...-remote-/` un-ignore list from the same two markers this task introduces.
That tool is **out of scope** here — this task only adds the markers and the
verify check. The gitignore TODO is left in place (its comment already names the
markers); building the regen tool is a separate follow-up.

## Changes

### 1. Add `headless: true` to the remote profile
**File:** `aitasks/metadata/profiles/remote.yaml`
Add `headless: true`. `remote` is the only shipped headless profile. Profiles are
loaded as plain dicts; an extra key is inert (strict-undefined only triggers when
a *template references* an undefined key — no template references `headless`).

### 2. Document the two markers
**File:** `.claude/skills/task-workflow/profiles.md` (profile schema reference)
Document `headless: true` as a profile key. Also note the companion
`prerender_for_headless: true` j2-frontmatter marker and that the pair drives the
`aitask_skill_verify.sh` headless-prerender freshness check. (profiles.md is a
closure leaf of task-workflow → it auto-renders to the other agents; per memory
`closure_changes_autorender_no_port`, no cross-agent port task is needed.)

### 3. Add `prerender_for_headless: true` to the three headless skills' j2 frontmatter
**Files:**
- `.claude/skills/aitask-pickrem/SKILL.md.j2`
- `.claude/skills/aitask-pickweb/SKILL.md.j2`
- `.claude/skills/task-workflow/SKILL.md.j2`

Add the marker line to each frontmatter block. These three are exactly the skills
with committed `*-remote-` dirs (confirmed against `.gitignore:46-57` and
`git ls-files`).

### 4. New `walk-verify` CLI mode in skill_template.py
**File:** `.aitask-scripts/lib/skill_template.py`
Add a read-only mode that renders the closure (`walk_closure(..., write=False)`)
then reports any committed target whose on-disk content is missing or differs
from the fresh render — reusing the existing `_any_target_differs` logic but with
per-file reporting for a useful diagnostic. Wire `walk-verify` into `__main__`
alongside `walk-write`/`walk-check`.

```python
def _main_walk_verify(argv: list) -> int:
    """Verify committed prerender freshness: render the closure in-memory and
    confirm every committed target matches the fresh render. Read-only; used by
    aitask_skill_verify.sh for prerender_for_headless skills (t894)."""
    if len(argv) != 4:
        sys.stderr.write(
            "usage: skill_template.py walk-verify "
            "<entry.j2> <profile.yaml> <agent> <repo_root>\n")
        return 2
    entry = Path(argv[0]).resolve()
    profile_yaml = Path(argv[1]).resolve()
    agent = argv[2]
    repo_root = Path(argv[3]).resolve()
    if agent not in AGENT_ROOTS:
        sys.stderr.write(f"skill_template: unknown agent '{agent}'\n")
        return 2
    profile = _load_profile(profile_yaml)
    profile_name = _profile_name(profile, profile_yaml)
    try:
        plan = walk_closure(entry, profile, agent, profile_name,
                            profile_yaml, repo_root, write=False, force=False)
    except Exception as e:
        sys.stderr.write(f"skill_template walk error: {e}\n")
        return 1
    drifted = []
    for _src, target, content in plan:
        try:
            if target.read_text(encoding="utf-8") != content:
                drifted.append(f"{target} (stale)")
        except OSError:
            drifted.append(f"{target} (missing)")
    if drifted:
        sys.stderr.write("committed prerender drift:\n  " + "\n  ".join(drifted) + "\n")
        return 1
    return 0
```
Add to `__main__`: `if args[0] == "walk-verify": sys.exit(_main_walk_verify(args[1:]))`.

### 5. Generalize the check in aitask_skill_verify.sh
**File:** `.aitask-scripts/aitask_skill_verify.sh`
- Source `yaml_utils.sh` (already in `ait`'s baseline source chain + test scaffold
  per CLAUDE.md, so no scaffold change needed) to get `read_yaml_field`.
- Before the per-template loop, discover headless profiles once:
  ```bash
  headless_profiles=()
  for pf in aitasks/metadata/profiles/*.yaml; do
      [[ -f "$pf" ]] || continue
      [[ "$(read_yaml_field "$pf" headless)" == "true" ]] && \
          headless_profiles+=("$(basename "$pf" .yaml)")
  done
  ```
  (Top-level profiles only — `local/` profiles are per-user and ship no committed
  prerenders.)
- Replace the hardcoded `if [[ "$skill" == "aitask-pickrem" ]]` block (and its
  `TODO(t777_29)` comment) with: if the template's frontmatter has
  `prerender_for_headless: true`, loop `headless_profiles × agents` and for each
  (a) verify the committed `agent_skill_dir <agent> <skill> <profile>/SKILL.md`
  exists, then (b) run `walk-verify` for content freshness, incrementing
  `failures` with a `PRERENDER_FAIL:` diagnostic on either failure.

### 6. Regenerate committed prerenders + goldens (same commit)
Required by CLAUDE.md ("after editing any `.md.j2` … regenerate the affected
goldens in the same commit"). See Verification for exact commands.

## Verification

1. **Regenerate committed prerenders** (picks up the new frontmatter field):
   ```bash
   ./.aitask-scripts/aitask_skill_rerender.sh remote
   ```
   This re-renders every `*-remote-` closure for all agents in place.
2. **Regenerate the affected SKILL goldens** (only SKILL.md carries frontmatter):
   ```bash
   P=.aitask-scripts/lib/skill_template.py
   PR=aitasks/metadata/profiles
   $PYTHON $P .claude/skills/aitask-pickrem/SKILL.md.j2 $PR/remote.yaml claude \
     > tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md
   $PYTHON $P .claude/skills/aitask-pickweb/SKILL.md.j2 $PR/remote.yaml claude \
     > tests/golden/skills/aitask-pickweb/SKILL-remote-claude.md
   for prof in default fast remote; do
     $PYTHON $P .claude/skills/task-workflow/SKILL.md.j2 $PR/$prof.yaml claude \
       > tests/golden/procs/task-workflow/SKILL-$prof.md
   done
   ```
   (`require_ait_python` resolves `$PYTHON`.) Inspect `git diff` on the goldens —
   the only change must be the added `prerender_for_headless: true` frontmatter
   line; any other diff means an unintended change.
3. **Verifier is green and now content-based:**
   ```bash
   shellcheck .aitask-scripts/aitask_skill_verify.sh
   bash .aitask-scripts/aitask_skill_verify.sh   # expect: OK
   ```
4. **Drift is caught (manual smoke):** temporarily append a line to a committed
   `task-workflow-remote-/SKILL.md`, re-run the verifier → expect non-zero exit
   with a `PRERENDER_FAIL … (stale)` line naming that file; revert.
5. **Regression suites:**
   ```bash
   bash tests/test_skill_verify.sh
   bash tests/test_skill_render_aitask_pickrem.sh
   bash tests/test_skill_render_aitask_pickweb.sh
   bash tests/test_skill_render_task_workflow.sh
   bash tests/test_skill_rerender.sh
   ```
6. **New negative test** in `tests/test_skill_verify.sh`: a scratch skill with
   `prerender_for_headless: true` in its `.md.j2` + canonical stubs, but no
   committed `*-remote-` dir → assert non-zero exit and stderr contains
   `PRERENDER_FAIL` naming the scratch skill. (Uses the real `remote` profile, now
   `headless: true`, so no fake profile file is needed; cleaned up via the trap.)

## Risk

### Code-health risk: medium
- The j2-frontmatter marker propagates into generated output, so 9 committed
  `*-remote-/SKILL.md` prerenders + ~5 SKILL goldens must be regenerated in the
  same commit; an incomplete regen leaves the tree inconsistent · severity: medium
  · → mitigation: TBD (handled in-commit: `git diff` review of goldens +
  render-test suites gate it — every miss fails loudly, never silently)
- The verify check is load-bearing pre-commit infrastructure; a logic bug in the
  generalized bash loop could regress to silent pass · severity: medium
  · → mitigation: TBD (new negative test asserts the drift/missing case fails)

### Goal-achievement risk: low
- None identified. The approach is grounded in verified primitives
  (`_any_target_differs`, `read_yaml_field` on both frontmatter and plain-YAML
  shapes) and directly addresses both the hardcoded-scope and existence-only
  defects.

## Step 9 (Post-Implementation)
Standard archival per task-workflow Step 9: commit code (`.aitask-scripts`,
`.claude/skills`, profiles, goldens, regenerated prerenders, tests) with
`bug: … (t894)`, then `aitask_archive.sh 894`. No worktree to clean (current
branch).
