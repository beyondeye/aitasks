---
Task: t777_22_extend_renderer_for_uniform_recursive_rendering.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md, aitasks/t777/t777_7_convert_task_workflow_shared_procs.md, aitasks/t777/t777_8_convert_aitask_explore.md, aitasks/t777/t777_9_convert_aitask_review.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md
Base branch: main
plan_verified: []
---

# Plan: t777_22 — Extend renderer for uniform recursive rendering

## Context

The current renderer (`aitask_skill_render.sh` + `lib/skill_template.py`) discovers cross-skill dependencies via Jinja `{% include "<other_skill>/SKILL.md.j2" %}` directives. The audit in t777_21 found that aitask-pick's real production closure (23 files) is composed almost entirely of plain **markdown references** (`see \`planning.md\``, `.claude/skills/task-workflow/SKILL.md`), not `{% include %}` directives. The existing model also requires a runtime "classify each file" step (does it use profile keys? if so, has-template form; else, identity).

Per task description and the user-confirmed render model, t777_22 replaces both: **every referenced `.md` is rendered through minijinja into a per-profile sibling location, identity-transform when no Jinja markers, with cross-references rewritten to point at the rendered tree.** The audit/classification step disappears. Drift is self-healing — if a shared proc grows a `{% if profile.X %}` later, the renderer handles it without any "is this file a template?" wiring.

This child is the **infrastructure prerequisite** for t777_6 (pilot pick conversion), t777_7 (task-workflow profile branches), and t777_8..t777_15 (per-skill conversions). It ships the dep-walker + tests + sibling-task metadata so subsequent conversions can run in any order with the walker already in place.

## Decisions (settled during planning)

1. **Entry-point template extension convention.** `.md.j2` only for entry-point SKILL.md templates. Referenced procedures stay as `.md` files (their extension does not change even if they grow Jinja markers under t777_7). The renderer treats every reachable `.md` as a Jinja template regardless of extension.

2. **Reference-discovery scope.** The walker supports all three reference shapes the audit walker enumerates:
   - **Full path:** `(\.claude|\.agents|\.gemini|\.opencode)/skills/<dir>/<file>.md`
   - **Sibling:** bare `<file>.md` (no `/`) — resolved against the current source file's parent dir
   - **Skill-relative:** `<dir>/<file>.md` (one `/`, no leading `.claude/...`) — resolved against the source agent root (`.claude/skills/`)

   Every resolved candidate must exist as a real file; missing candidates are skipped silently (no error) so prose like "edit the planning.md file" doesn't break the walker.

3. **Reference-rewriting policy.** Inside rendered output:
   - **Full-path ref** → full-path ref pointing at target agent's per-profile dir: `<target_root>/<dir>-<profile>-/<file>.md`. Source `<source_root>` is always `.claude/skills/` (single source of truth); the rewrite swaps `<source_root>` for `<target_root>` based on `--agent`.
   - **Sibling ref** → stays as `<file>.md` (the file is rendered into the SAME per-profile dir as the calling file).
   - **Skill-relative ref** → rewritten to full path `<target_root>/<dir>-<profile>-/<file>.md` (would otherwise resolve incorrectly against the per-profile dir).

4. **Skip-list for path scanning.** None. Identity-transform on all reachable files. The regex naturally rejects placeholder strings (`<skill>-<profile>-/SKILL.md` in stub-skill-pattern.md does not match any of the three shapes because `<` is not in the path char class). Files referenced only from CLAUDE.md (e.g., `stub-skill-pattern.md`) are not in any runtime closure.

5. **Skip-if-fresh closure-aware.** Any stale leaf in the dep closure invalidates the entire chain. Implementation: the dep-walker enumerates all (source, target) pairs first; if ANY target is missing or older than ANY of its sources (template OR profile YAML OR transitively-reachable source), re-render every pair. The bash-side mtime check on the entry target is dropped in favor of the closure-aware check in Python.

6. **`{% include %}` cross-skill recursion is removed.** Within-skill `{% include "_partial.j2" %}` (Jinja-native, scoped to the template's parent dir) stays. Cross-skill `{% include "<other_skill>/SKILL.md.j2" %}` is no longer supported — the new dep-walker handles cross-skill via plain `.md` refs. Existing test_skill_render.sh Test 6 is updated accordingly.

## Key Files to Modify

- `.aitask-scripts/lib/skill_template.py` — add dep-walk closure functions and CLI sub-commands.
- `.aitask-scripts/aitask_skill_render.sh` — simplify: drop the `{% include %}` regex scan + recursive shell call, delegate the full closure to Python `walk-write`.
- `.aitask-scripts/aitask_skill_verify.sh` — extend each per-template loop to call `walk-check` so transitive deps are validated.
- `CLAUDE.md` — add a "stub + `.md.j2` pair convention" bullet under `### Skill / Workflow Authoring Conventions` so future profile-aware skill conversions follow the same authoring pattern (see Step 4a).
- **Move `.claude/skills/task-workflow/stub-skill-pattern.md` → `aidocs/stub-skill-pattern.md`** (authoring reference doc, never in any runtime closure per p777_21 audit). Update the 4 path references found in `CLAUDE.md:269`, `.aitask-scripts/aitask_skill_verify.sh:5,52,86` (path-only comments), `.aitask-scripts/lib/agent_skills_paths.sh:27`. The `aitask_skillrun.sh:73` mention is filename-only (no path) and stays.
- `aidocs/stub-skill-pattern.md` — add a §3i "Reference resolution" section documenting the 3 shapes and rewrite policy so per-skill converters in t777_7 / t777_8..15 follow it.
- `tests/test_skill_template.sh` — add unit tests for `discover_refs`, `rewrite_ref`, agent-root mapping.
- `tests/test_skill_render.sh` — replace Test 6 (cross-skill `{% include %}`) with full-path .md-ref equivalent; keep Tests 7 (within-skill include), 8 (raw escape), 15 (missing ref non-crash) adapted to the new walker.
- New `tests/test_skill_render_uniform.sh` — integration suite for the dep-walker: synthetic skill tree, cycle test, identity-transform test, closure-aware skip-if-fresh, --force.
- `aitasks/t777/t777_8_*..t777_15_*.md` — add `777_22` and `777_7` to `depends:` via `aitask_update.sh --batch <id> --add-depends 777_22 --add-depends 777_7`.

## Reference Files for Patterns

- `.aitask-scripts/aitask_skill_render.sh` — current renderer (drop `{% include %}` regex scan at lines 134-181; keep arg parsing + skip-if-fresh wiring).
- `.aitask-scripts/lib/skill_template.py:render_skill` — existing single-file renderer (keep as legacy CLI mode for back-compat with tests + library callers).
- `.aitask-scripts/lib/agent_skills_paths.sh:agent_skill_root` / `agent_skill_dir` — agent-root mapping helpers; reuse from Python by calling them OR mirror the case-statement in `skill_template.py` (mirror is simpler and dependency-free).
- `aiplans/archived/p777/p777_21_*.md` — closure walk methodology + cycle examples (use the BFS pseudocode + visited-set design).
- `tests/test_skill_render.sh` — existing test scaffolding (assert_eq/assert_contains, scratch-skill pattern under `_t777_22_test_*` prefix, cleanup trap).

## Implementation Plan

### Step 1 — Extend `lib/skill_template.py` (Python core)

Add the following top-level functions to `skill_template.py`:

```python
# Regex for full-path refs: <source_root>/skills/<dir>/<file>.md
FULL_PATH_REF_RE = re.compile(
    r'(?P<root>\.claude|\.agents|\.gemini|\.opencode)/skills/'
    r'(?P<dir>[A-Za-z0-9._-]+)/'
    r'(?P<file>[A-Za-z0-9._-]+\.md)\b'
)
# Regex for path-shaped refs not matching the full-path form: one or zero `/`
# Resolved against context (sibling: current_dir; skill-relative: source_agent_root)
SHORT_REF_RE = re.compile(
    r'(?<![A-Za-z0-9._/-])'   # left anchor: not preceded by a path char
    r'(?P<inner>(?:[A-Za-z0-9._-]+/)?[A-Za-z0-9._-]+\.md)'
    r'(?![A-Za-z0-9./-])'     # right anchor: not followed by a path char
)

AGENT_ROOTS = {
    "claude":   ".claude/skills",
    "codex":    ".agents/skills",
    "gemini":   ".gemini/skills",
    "opencode": ".opencode/skills",
}
SOURCE_AGENT_ROOT = ".claude/skills"  # claude is source of truth per t777_1

def discover_refs(text, current_source_path, repo_root):
    """Yield (match_start, match_end, original_str, resolved_abs_source_path, kind)
    for every ref. kind ∈ {full, sibling, skill_relative}.
    Filters: resolved file must exist."""
    # 1) Full-path matches.
    # 2) Short refs (sibling or skill-relative) - dedupe against full-path spans.

def rewrite_ref(original_str, kind, agent, profile_name, dir_hint):
    """Return the rewritten reference string for the target tree."""
    # full:  .claude/skills/X/Y.md  → <target_root>/X-<profile>-/Y.md
    # sibling: Y.md → Y.md (unchanged)
    # skill_relative: X/Y.md → <target_root>/X-<profile>-/Y.md

def render_source_file(source_path, profile, agent):
    """Render a single source file's text through minijinja with the same
    loader path policy as render_skill (parent + parent.parent for within-skill
    includes). Returns the rendered text. Identity-transform when no Jinja
    markers, since minijinja env.render_str passes plain text through."""

def walk_closure(entry_template, profile, agent, profile_name, repo_root,
                 write, force):
    """BFS over the dep closure starting at entry_template.

    Algorithm:
      visited = {entry_template (source path)}
      queue   = [(entry_template, agent_skill_dir(agent, skill, profile)/SKILL.md)]
      plan    = []   # list of (source_path, target_path, rewritten_content)

      while queue:
          src, target = queue.popleft()
          raw = render_source_file(src, profile, agent)
          new_raw = raw
          for match in discover_refs(raw, src, repo_root):
              new_raw = new_raw.replace(match.original_str, rewrite_ref(...), 1)
              if match.resolved not in visited:
                  visited.add(match.resolved)
                  child_target = compute_child_target(match.resolved, agent,
                                                     profile_name, repo_root)
                  queue.append((match.resolved, child_target))
          plan.append((src, target, new_raw))

      # Closure-aware skip-if-fresh
      stale = force or any_target_missing_or_older_than_sources(plan, repo_root,
                                                               profile_yaml)
      if write and stale:
          for src, target, content in plan:
              atomic_write(target, content)
      return plan
    """
```

CLI sub-commands:

```python
# usage:
#   skill_template.py <tpl> <profile.yaml> <agent>              # legacy single-file render to stdout
#   skill_template.py walk-write <entry> <profile.yaml> <agent> <repo_root> [--force]
#   skill_template.py walk-check <entry> <profile.yaml> <agent> <repo_root>
```

`walk-check` performs the closure walk in memory and exits non-zero if any source fails to render or any reference fails to resolve. No disk writes.

### Step 2 — Simplify `aitask_skill_render.sh`

Replace the body after arg parse (currently lines 80-181 doing skip-if-fresh + single render + `{% include %}` recursion) with:

```bash
PYTHON="$(require_ait_python)"
extra=()
[[ "$force" == true ]] && extra+=(--force)

"$PYTHON" "$SCRIPT_DIR/lib/skill_template.py" walk-write \
    "$template_path" "$profile_yaml" "$agent" "$REPO_ROOT" "${extra[@]}"
```

Keep arg parsing, profile-name → YAML path resolution (`aitask_scan_profiles.sh` lookup), and the agent_skill_root/agent_authoring_template helper sourcing. Drop the entire `_get_mtime` helper, the mtime-comparison block, the tempfile/mv pair (now Python's job via `atomic_write`), and the entire cross-skill `{% include %}` recursion (lines 134-181).

### Step 3 — Extend `aitask_skill_verify.sh`

Inside the per-template loop, after the existing per-agent render check (lines 73-83), add a per-agent walk-check:

```bash
for agent in "${agents[@]}"; do
    if ! out="$("$PYTHON" "$SKILL_TEMPLATE_PY" walk-check "$tpl" "$DEFAULT_PROFILE_YAML" "$agent" "$REPO_ROOT" 2>&1)"; then
        printf 'VERIFY_FAIL: %s agent=%s closure error:\n%s\n' "$skill" "$agent" "$out" >&2
        failures=$((failures + 1))
    fi
done
```

This is the only change to verify; stub-pattern checks remain.

### Step 4a — Document the stub + `.md.j2` pair convention in `CLAUDE.md`

Add a new bullet under `## WORKING ON SKILLS / CUSTOM COMMANDS` → `### Skill / Workflow Authoring Conventions` (near the existing "SKILL.md files are re-read during execution" and "Use recognizable name-suffix conventions" bullets):

```markdown
- **Profile-aware skills require a stub + `.md.j2` pair, not a single `SKILL.md`.** An entry-point skill that needs to vary by execution profile MUST be authored as two files in `.claude/skills/<skill>/`:
  1. `SKILL.md` — the committed, profile-agnostic **stub** (per `task-workflow/stub-skill-pattern.md` §3b). Resolves the active profile, calls `ait skill render`, and Read-and-follows the per-profile rendered variant.
  2. `SKILL.md.j2` — the **authoring template** rendered by minijinja against the active profile YAML. May reference other `.md` procedures (full-path, sibling, or skill-relative — see `stub-skill-pattern.md` §3i); the dep-walker recursively renders all reachable refs into the per-profile sibling tree.

  Profile-agnostic skills that do not vary by profile keep a single `SKILL.md` and skip the `.j2` template entirely.

  **Why:** A single `SKILL.md` cannot carry profile-conditional content because the agent re-reads it during execution; mutating it mid-session would produce torn reads (see the "SKILL.md files are re-read during execution" rule above). The stub + render-on-invocation model materialises a stable per-(skill, profile) snapshot once per invocation, then the agent reads that frozen file.

  **How to apply:** When converting a skill to be profile-aware (t777_6 pilot, t777_8..t777_15 follow-ups), author the `.md.j2` template first, then drop the canonical stub from `task-workflow/stub-skill-pattern.md` §3b at the existing `SKILL.md` path. The 3 sibling stubs (Codex SKILL.md, Gemini command TOML, OpenCode command MD) follow §3c-§3d. Run `./ait skill verify` to confirm all 4 stub surfaces + the closure render cleanly.
```

### Step 4b — Move `stub-skill-pattern.md` to `aidocs/` and document the reference convention

Move the file:
```bash
mkdir -p aidocs
git mv .claude/skills/task-workflow/stub-skill-pattern.md aidocs/stub-skill-pattern.md
```

Update the 4 path references so they point at the new location:
- `CLAUDE.md:269` — replace `.claude/skills/task-workflow/stub-skill-pattern.md` with `aidocs/stub-skill-pattern.md`.
- `.aitask-scripts/aitask_skill_verify.sh:5` (header comment) — same path swap.
- `.aitask-scripts/aitask_skill_verify.sh:52,86` (`§3g`, `§3b-§3d` markers) — update the `mirrors stub-skill-pattern.md §3g` comments to reference `aidocs/stub-skill-pattern.md`.
- `.aitask-scripts/lib/agent_skills_paths.sh:27` — replace the path in the comment with `aidocs/stub-skill-pattern.md`.

`.aitask-scripts/aitask_skillrun.sh:73` mentions the filename only (no path) and does not need to change.

Then append §3i to the **moved** file (`aidocs/stub-skill-pattern.md`):

Add §3i to `.claude/skills/task-workflow/stub-skill-pattern.md`:

```markdown
## 3i. Reference resolution (for the t777_22 dep-walker)

Authoring templates and shared `.md` procedures should use one of three
reference shapes when linking to another procedure file. The dep-walker
discovers all three and renders the targets into the per-profile sibling tree:

| Shape | Example | Resolution |
|-------|---------|-----------|
| Full path | `.claude/skills/task-workflow/planning.md` | Direct path under source agent root |
| Sibling | `planning.md` | Relative to the current source file's parent dir |
| Skill-relative | `task-workflow/planning.md` | Relative to source agent root (`.claude/skills/`) |

After rendering, refs are rewritten:
- Full-path → `<target_root>/<dir>-<profile>-/<file>.md` (target_root depends on `--agent`)
- Sibling → unchanged (rendered into the same per-profile dir)
- Skill-relative → rewritten to full-path form in the target tree

If a candidate path does not resolve to a real file, the walker silently
skips it. Prose mentions of filenames in narrative text are safe — false
positives are filtered by existence check.
```

### Step 5 — Tests

**5a. Extend `tests/test_skill_template.sh`** — unit tests for the new Python helpers:

- `discover_refs`: positive cases for each of the 3 ref shapes; negative cases for `<placeholder>` strings, in-prose mentions of non-existent filenames, raw-escaped `{% raw %}{% include "..." %}{% endraw %}`.
- `rewrite_ref`: 4 agents × {full, skill-relative} × multiple input paths. Sibling refs assert unchanged.
- Agent-root mapping: `claude` → `.claude/skills`, etc.
- Exercise via CLI: pipe text to a small Python wrapper that calls `discover_refs`/`rewrite_ref` and prints results; assert via grep/assert_contains.

**5b. New `tests/test_skill_render_uniform.sh`** — integration suite using the existing `_t777_22_test_` scratch-prefix convention and `cleanup` trap:

1. **Synthetic single-ref:** skill A → skill B (full path). After render: both `A-fast-/SKILL.md` and `B-fast-/SKILL.md` exist; A's ref is rewritten to `.claude/skills/B-fast-/SKILL.md`.
2. **Sibling ref preserved:** skill A's SKILL.md.j2 references `partial.md` (sibling). After render: `A-fast-/SKILL.md` references `partial.md` unchanged; `A-fast-/partial.md` exists.
3. **Skill-relative rewrite:** skill A references `B/SKILL.md`. After render: A's ref becomes `.claude/skills/B-fast-/SKILL.md` and B is rendered.
4. **Identity transform:** source `.md` with NO Jinja markers → byte-identical output (modulo any trailing-newline handling we adopt — verify exact bytes match).
5. **Cycle detection:** A → B → A. Walker visits A and B exactly once; no infinite loop.
6. **Missing ref is silent:** ref to a non-existent file does not crash; existing file still rendered.
7. **Closure-aware skip-if-fresh:** initial render writes targets; second run no-op (mtimes preserved); `touch` a deep leaf source → next run re-renders ALL targets (mtimes bump for every target in closure).
8. **--force:** unconditional re-render regardless of mtimes.
9. **Cross-agent rewriting:** render skill A → B for `--agent gemini`; A's ref `.claude/skills/B/SKILL.md` rewrites to `.gemini/skills/B-fast-/SKILL.md`.
10. **Within-skill `{% include "_partial.j2" %}`:** still works (regression check for existing native Jinja behavior).
11. **walk-check** mode: errors on broken ref AND on bad Jinja syntax in a leaf; writes nothing to disk on success.

**5c. Update `tests/test_skill_render.sh`** — port over to new model:

- Test 6: replace cross-skill `{% include "<other>/SKILL.md.j2" %}` with cross-skill `.md` reference (full path); assert same end state (both targets exist in `*-fast-/` dirs).
- Tests 1-5, 7, 8, 10-13, 15-18: keep as-is (still valid against the new renderer).
- Test 9 (missing template): keep, the error message stays the same.

### Step 6 — Update sibling task metadata

For each of t777_8..t777_15, add `777_22` and `777_7` to `depends:`:

```bash
for id in 777_8 777_9 777_10 777_11 777_12 777_13 777_14 777_15; do
    ./.aitask-scripts/aitask_update.sh --batch "$id" --add-depends 777_22 --add-depends 777_7
done
```

Verify each file with `grep '^depends:' aitasks/t777/t777_*_*.md`.

### Step 7 — Verification

1. `bash tests/test_skill_template.sh` passes (existing + new unit tests).
2. `bash tests/test_skill_render.sh` passes (after Test 6 swap).
3. `bash tests/test_skill_render_uniform.sh` passes (new suite).
4. `shellcheck .aitask-scripts/aitask_skill_render.sh .aitask-scripts/aitask_skill_verify.sh` clean.
5. `./ait skill verify` exits 0 — no `.j2` templates yet exist in production, so this prints the "nothing to verify" message but exercises the verify-script entrypoint without errors.
6. `grep '^depends:' aitasks/t777/t777_{8,9,10,11,12,13,14,15}_*.md` shows `777_22, 777_7` in each.

End-to-end check against the real pick closure is **deferred to t777_6** (the pilot) because no `.j2` authoring template exists today for aitask-pick. Synthetic-fixture coverage in test_skill_render_uniform.sh is the closure-coverage proxy for this child.

## Notes for sibling tasks

- **t777_6 (PILOT pick conversion):** Once t777_22 + t777_7 land, run `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast --agent claude` and confirm the full 23-file closure (per p777_21 table) renders into `.claude/skills/aitask-pick-fast-/` + `.claude/skills/task-workflow-fast-/`. Add golden-file tests for the pick closure's profile combinations (2× for `skip_task_confirmation`, 8× for `planning.md`'s combinatoric matrix).
- **t777_7 (convert task-workflow shared procs):** The 5-file edit list from p777_21 (SKILL.md, planning.md, manual-verification-followup.md, remote-drift-check.md, satisfaction-feedback.md). Total 9 `{% if profile.X %}` wrapping sites. No file-extension changes (stays `.md`). After landing, the walker will discover the full closure via existing sibling refs — no ref-shape conversion needed.
- **t777_8..t777_15 (per-skill conversions):** Mirror the t777_6 stub-pattern via `.claude/skills/<skill>/SKILL.md.j2`. Reference shared procs using whichever shape is natural (full-path for cross-skill, sibling for within-task-workflow). The dep-walker handles all three.

## Step 9 — Post-Implementation

Standard child-task archival via `./.aitask-scripts/aitask_archive.sh 777_22`. Commit code changes (Python helpers, bash simplifications, tests, stub-skill-pattern.md doc update) under `feature: Extend renderer for uniform recursive rendering (t777_22)`. Commit plan file separately via `./ait git`. Push.

## Final Implementation Notes

- **Actual work done:** Implemented the dep-walker in `lib/skill_template.py` (≈220 LOC new): `FULL_PATH_REF_RE` / `SHORT_REF_RE`, `discover_refs` (yields full / sibling / skill-relative kinds, filters non-existent), `rewrite_ref` (per-kind rewrite policy), `walk_closure` (BFS with visited-set keyed on source path, in-memory closure rendering, closure-aware skip-if-fresh based on max source mtime), atomic per-file writes, two new CLI sub-commands `walk-write` and `walk-check`. Simplified `aitask_skill_render.sh` from 182 lines to 99 lines by removing the bash-side `{% include %}` regex scan and mtime check (both moved to Python). Extended `aitask_skill_verify.sh` with a per-template `walk-check` pass. Moved `stub-skill-pattern.md` from `.claude/skills/task-workflow/` to `aidocs/` and appended a §3i "Reference resolution" section. Added a CLAUDE.md bullet documenting the stub + `.md.j2` pair convention. Updated 4 path references (CLAUDE.md, agent_skills_paths.sh comment, verify-script header + 2 marker comments). Tests: extended `test_skill_template.sh` with +35 cases for `discover_refs`/`rewrite_ref`/`AGENT_ROOTS`; ported `test_skill_render.sh` Test 6 to the new ref model and removed obsolete Test 14 (bash-side stat portability); added `test_skill_render_uniform.sh` with 29 integration cases covering all the documented behaviors. Sibling-task metadata: added `t777_22` (and `t777_7` where missing) to `depends:` on t777_8..t777_15 via `aitask_update.sh`.

- **Deviations from plan:** None of substance. Two minor adjustments during implementation:
  - The "render any reachable `.md` through minijinja" function in the plan sketch (`_render_source_text`) was inlined as a direct call to `render_skill` instead of a separate wrapper — they would have had identical bodies.
  - The `--add-depends` flag mentioned in the plan does not exist in `aitask_update.sh`; only `--deps DEPS` (replace-all). Worked around by reading current deps and merging in a small shell loop.

- **Issues encountered:** Initial draft of `discover_refs` matched a path *anywhere* in text, which would have produced false-positive rewrites against placeholder strings like `<skill>-<profile>-/SKILL.md` (used in `aidocs/stub-skill-pattern.md` examples). Resolved by anchoring `SHORT_REF_RE` on non-path-char boundaries (negative lookbehind/lookahead) and filtering all candidates through an existence check (`resolved.is_file()`). Placeholder strings naturally do not resolve to real files and are silently skipped — same path that handles prose mentions of nonexistent filenames.

- **Key decisions:**
  - Reference-discovery scope is **full + sibling + skill-relative**, not "full only" (per user direction in planning). The walker resolves all three shapes and filters via existence check.
  - The walker normalises full-path refs from any of the four agent roots to `.claude/skills/...` for source resolution (Claude is SoT per t777_1). Rewriting always targets the requested `--agent`'s root.
  - Skip-if-fresh moved entirely to Python and is closure-aware: a single stale leaf invalidates the chain. Bash retains only arg parsing + profile YAML resolution + delegation.
  - Within-skill `{% include "_partial.j2" %}` (native Jinja, scoped to the template's parent dir) is preserved. Cross-skill `{% include "<other>/SKILL.md.j2" %}` was removed — the new dep-walker covers cross-skill via plain `.md` refs.
  - `stub-skill-pattern.md` was moved to `aidocs/` rather than kept under `.claude/skills/task-workflow/`. Confirmed it is referenced only from CLAUDE.md and from comments in scripts (verify script + paths-lib comment + skillrun comment) — never from any runtime skill closure (per p777_21 audit), never copied to `seed/`, never read at install or runtime. Moving it removes a runtime-vs-authoring ambiguity.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t777_6 (PILOT pick conversion):** Walker is ready; once aitask-pick's `SKILL.md.j2` and the canonical stub land, `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast --agent claude` will recursively render the full 23-file closure into `.claude/skills/aitask-pick-fast-/` plus `task-workflow-fast-/`. Golden-file coverage for production closure is t777_6's responsibility; t777_22 ships only synthetic-fixture coverage.
  - **t777_7 (convert task-workflow shared procs):** No file-extension changes required (every shared proc stays `.md`). The walker handles sibling refs out-of-the-box — t777_7 does not need to convert sibling refs to full paths.
  - **t777_8..t777_15:** All sibling tasks now declare `depends: [..., t777_7, t777_22]`. They can author their `.md.j2` templates using whichever ref shape is natural (full-path for cross-skill, sibling for within-skill). See `aidocs/stub-skill-pattern.md` §3i for the full reference-resolution contract.
  - **Convention to publicise:** The "stub + `.md.j2` pair" requirement is now in CLAUDE.md under `### Skill / Workflow Authoring Conventions`. Future skill authors converting a skill to be profile-aware should follow it.
