---
Task: t1581_prune_orphaned_skillrun_render_dirs.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1581 — Prune orphaned `_skillrun_` rendered skill dirs

## Context

`ait skillrun` and the board's agent-launch dialog can start an agent under a
**per-run profile override**. Each one writes an ephemeral profile
`aitasks/metadata/profiles/local/_skillrun_<unique>.yaml`, and rendering that
profile produces a full **rendered skill closure** at
`<agent_skill_root>/<skill>-_skillrun_<unique>-/` (plus the shared-root codex
variant `…-<agent>-/`).

`_prune_stale_skillrun_overrides()`
(`.aitask-scripts/lib/agent_command_screen.py:93-108`) cleans up the **YAML**
after an hour. Nothing ever cleans up the **render trees**. The asymmetry is the
defect: the profile is ephemeral, the render tree it produced is permanent.

Observed on this workspace on 2026-08-24 — two orphans from 2026-05-25, three
months old, whose originating profile YAML was pruned long ago:

```
.claude/skills/aitask-pick-_skillrun_416236_1779701547729-
.claude/skills/task-workflow-_skillrun_416236_1779701547729-
```

Why it matters: stale skill text lingers (the orphaned
`task-workflow-…/plan-externalization.md` predates the whole `<branch-flags>`
section and still says "Gemini CLI"); the dirs are gitignored
(`.gitignore:52-54`) so no review surface catches them; they pollute repo-wide
`grep -r` over the skill trees (this already forced t1578's propagation check to
be rebuilt on `git ls-files`); and nothing caps the count.

**Nothing existing covers this.** The repo's only deleter of rendered dirs is
`aitask_prune_retired_skills.sh:198-217`, and it is **stem-driven** — a dir is a
candidate only if its skill prefix appears in `retired_skills_manifest.txt`, and
even then only behind `--prune-rendered`, which neither caller
(`install.sh:1333`, `aitask_setup.sh:2552`) passes. `aitask-pick-_skillrun_…-`
has a live stem, so it is invisible to that script under any flag.
`aitask_skill_rerender.sh` globs by a caller-supplied profile name and, on
finding an orphan, explicitly *skips* rather than deletes (`:63-67`).

Outcome: render trees share the profile's lifecycle, with a threshold chosen so
the cleanup can never delete a tree an in-flight agent is still reading.

## Approach

### 1. New sibling helper in `.aitask-scripts/lib/agent_command_screen.py`

Add `_prune_stale_skillrun_renders()` directly below
`_prune_stale_skillrun_overrides()`, and call it on the line after the existing
call in `AgentCommandScreen.__init__` (currently line 437). Same best-effort
contract: never raises, never blocks the dialog.

**Agent roots — reuse the canonical Python seam.** Import `AGENT_ROOTS` from
`skill_template.py` (same `lib/` dir, already on `sys.path` via `_LIB_DIR`,
slotting into the existing import block at line 62). That dict
(`skill_template.py:50-54`) is the existing Python mirror of
`lib/agent_skills_paths.sh`; its module-level imports are stdlib-only
(`minijinja` is imported lazily inside `render_skill`), so it is safe to import
from a TUI module that also runs under PyPy. Do **not** hardcode the three roots.

**Glob:** `*-_skillrun_*-` per root.
- Matches the non-shared shape `aitask-pick-_skillrun_<unique>-` and the
  shared-root codex shape `aitask-pick-_skillrun_<unique>-codex-`
  (`skill_template.py:67-74`).
- The trailing hyphen is the established "generated" marker (the same one
  `.gitignore:52-54` keys on); the leading `-` anchors on the skill/profile
  boundary, so a committed authoring/stub dir can never match.
- **Validated against the live tree:** across the 130 rendered dirs currently on
  disk (46 + 42 + 42), this glob selects exactly the 2 known orphans and nothing
  else.

**Threshold — a separate, much longer constant.** Add
`_SKILLRUN_RENDER_PRUNE_AGE_SECONDS = 7 * 24 * 3600` next to the existing
`_SKILLRUN_PRUNE_AGE_SECONDS = 3600`, with the reason in a comment:

> The profile YAML stops being load-bearing once the agent has read it — hence
> one hour. The **rendered tree does not**: the stub dispatches into it at
> session start and the workflow keeps reading `planning.md`, `task-abort.md`,
> `satisfaction-feedback.md` out of it at Steps 6/7/8/9, hours later. Reusing
> the 1h threshold would delete the live skill tree out from under a running
> agent.

This is not a hypothetical: `aitask_skill_rerender.sh:12-16` already records the
repo's position — it re-renders instead of `rm -rf` *precisely* because
"rendered files may be open in active agent sessions" and a tree delete "would
not have that guarantee". This fix does delete the tree, so the age threshold is
what buys that safety back. The costs are asymmetric — a leaked orphan is a few
hundred KB, a wrong delete breaks a live session — so the threshold is
deliberately conservative.

**What this deliberately does not do.** The task's option 2 ("prune any dir whose
originating profile YAML no longer exists") is **not** implemented, and is not
added as an extra conjunct either. Two reasons, and the first is decisive:

- On the TUI path the YAML is written by `_on_profile_saved_one_shot`
  (`agent_command_screen.py:1014-1030`) and then pruned at the 1h mark, while
  the agent it launched runs detached in tmux for much longer. Option 2 would
  therefore delete the live render tree ~1 hour into every board-launched
  session. (On the `ait skillrun` CLI path the YAML happens to outlive the
  session — `aitask_skillrun.sh:258-263` forks and cleans up *after* agent
  termination — so the two paths disagree, and the unsafe one is the default.)
- As an added conjunct it would be vacuous rather than unsafe: at 7 days the
  YAML is unconditionally gone on both paths, so the age test dominates it. It
  would buy nothing while making the rule read as if it had a second safeguard.

Age alone, with that reasoning in the comment.

**mtime signal:** the newest of the directory's own mtime and its immediate
children's mtimes. Dir mtime is *usually* sufficient — `_atomic_write`
(`skill_template.py:258-263`) creates `<name>.tmp` in the target's parent then
`os.replace`s it, and both mutate the parent's entry list — but that only holds
for files written directly into the render dir. The max over immediate children
is one `scandir` and closes the nested-file case, and it errs in the safe
direction (a dir reads *fresher*, so it survives).

**Deletion:** `shutil.rmtree` (new `import shutil`), guarded by
`p.is_dir() and not p.is_symlink()` so the helper can never follow a symlink out
of the skill root, and wrapped in the same `except OSError: continue` as the
existing loop.

**Testability:** give the helper an optional `project_root: Path | str = "."`
parameter, defaulted in the helper so the call site stays a bare
`_prune_stale_skillrun_renders()`. A root-scoped signature lets the test point
at a temp tree without either `os.chdir` (which `run_all_python_tests.sh` has to
work around with `--dist loadfile`) or patching a private module global — both
of which the house style flags as last resorts. It is a deliberate small
divergence from the cwd-relative `_prune_stale_skillrun_overrides()`, which
works only because `ait` cds to the repo root (`ait:9`).

**Rejected call site:** the `cleanup_override` EXIT trap in
`aitask_skillrun.sh:254-265`, which already removes the YAML tempfile. It cannot
also remove the render dir — on the board path the launched agent is still
reading that tree when the trap fires.

### 2. Regression test — `tests/test_agent_command_skillrun_prune.py`

House style is `unittest.TestCase` with `tempfile.TemporaryDirectory()` in
`setUp` + `addCleanup` (no pytest fixtures, no `tmp_path`), the
`REPO_ROOT / ".aitask-scripts" / "lib"` `sys.path` bootstrap from
`tests/test_agent_command_open_debounce.py:16-31`, and a `Run:` footer in the
module docstring. There is currently **no test at all** for
`_prune_stale_skillrun_overrides`, so this file pins both helpers.

Build a synthetic repo root, backdate mtimes with `os.utime`, run both prunes,
and assert on survivors as well as deletions. Every seeded entry is doing work —
the kept ones are the negative controls:

| seeded | expected |
|---|---|
| aged `.claude/skills/aitask-pick-_skillrun_1_2-/` | **pruned** |
| aged `.agents/skills/aitask-pick-_skillrun_5_6-codex-/` | **pruned** (shared-root shape) |
| aged `.opencode/skills/task-workflow-_skillrun_7_8-/` | **pruned** (third root reached) |
| **fresh** `.claude/skills/aitask-pick-_skillrun_3_4-/` | **kept** — proves the age check is load-bearing |
| aged `.claude/skills/aitask-pick-fast-/` | **kept** — a real-profile render must not match |
| aged `.claude/skills/aitask-pick/` (committed stub) | **kept** |
| aged `profiles/local/_skillrun_1_2.yaml` | **pruned** (existing behavior, re-pinned) |

A test that only asserted deletions would pass on a helper that wiped the whole
root, so the "kept" rows are load-bearing, not decoration.

### 3. Documentation

`aidocs/framework/stub-skill-pattern.md` documents the rendered-dir naming
convention but has **no lifecycle/cleanup section** — which is the gap that let
this asymmetry ship. Add `## 3k. Rendered-dir lifecycle`: persistent-profile
renders live until re-rendered in place; `_skillrun_` renders are ephemeral and
pruned by `_prune_stale_skillrun_renders()` on launch-dialog open;
`aitask_skill_rerender.sh` never deletes; `aitask_prune_retired_skills.sh`
covers only *retired stems*, a disjoint concern. Name the module from the doc
and the doc from the module's comment so the two point at each other.

## Risk

### Code-health risk: medium
- Introduces the framework's first **age-driven `rm -rf`** over the agent skill
  roots, executed from a TUI constructor — a wrong glob or a wrong root would
  delete live rendered closures. Blast radius is contained (the targets are
  gitignored generated trees that the next stub invocation re-renders, and the
  committed `-remote-` prerenders are git-tracked so any mistake would show in
  `git status`), and the glob is validated against all 130 real dirs, but the
  operation is destructive by nature · severity: medium · → mitigation: inline
  pre-phase `dry_run_candidate_audit`
- Deleting a tree that a long-lived agent session is still reading, against the
  explicit precedent in `aitask_skill_rerender.sh:12-16` · severity: medium ·
  → mitigation: the 7-day threshold (user-confirmed) plus the fresh-dir negative
  control in the test

*Reassessed after the inline mitigation was confirmed: code-health stays
**medium**, not low. The pre-phase audit gates my first deletion on this
workspace; it does not run on any user's machine afterwards, so the deployed
`rm -rf` is unchanged. The durable safeguards are the validated glob, the
symlink/is_dir guards, the 7-day threshold, and the test's negative controls.*

### Goal-achievement risk: low
- None material. The defect is precisely characterized, the fix is a direct
  lifecycle symmetry, the one judgment call (threshold) is settled, and a live
  end-to-end check exists on this very workspace — two genuine orphans that must
  disappear while 128 sibling dirs survive.

### Planned mitigations
- timing: pre-phase | name: dry_run_candidate_audit | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: age-driven rm -rf over the agent skill roots | desc: Before the first real deletion, enumerate the helper's candidate set against the real repo and confirm it is exactly the two known orphans

## Implementation steps

### Pre-phase (risk mitigations)

0. **`dry_run_candidate_audit`** — with the helper written but before invoking
   it destructively, run its selection logic in enumerate-only form against the
   real repo root and print the candidate set plus the surviving count. Proceed
   only if the set is exactly the two known orphans and all 128 other rendered
   dirs are absent from it.

1. Add `import shutil` and `from skill_template import AGENT_ROOTS`, plus the
   `_SKILLRUN_RENDER_PRUNE_AGE_SECONDS` constant with its rationale comment.
2. Add `_prune_stale_skillrun_renders(project_root=".")` below
   `_prune_stale_skillrun_overrides()`.
3. Call it after the existing prune call in `AgentCommandScreen.__init__`.
4. Add `tests/test_agent_command_skillrun_prune.py`.
5. Add `## 3k. Rendered-dir lifecycle` to
   `aidocs/framework/stub-skill-pattern.md` and the reciprocal reference in the
   helper's comment.

## Verification

1. `bash tests/run_all_python_tests.sh --test-dir tests` narrowed to the new
   module, then the full suite for regressions. Read **only** the last line —
   `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)` — and use `pipefail` or
   `${PIPESTATUS[0]}` if piping, since piping discards the status.
2. **Negative control:** flip the threshold comparison in the helper and confirm
   the *fresh-dir* assertion is the one that fails, by name; then revert. A
   passing negative control means the test is not pinning what it claims to.
3. **Live end-to-end on the real workspace** — the strongest check available.
   After the pre-phase audit passes, run the helper against the real repo root
   and confirm exactly `aitask-pick-_skillrun_416236_1779701547729-` and
   `task-workflow-_skillrun_416236_1779701547729-` disappear from
   `.claude/skills/`, every `-default-`/`-fast-`/`-remote-` render dir and every
   committed stub dir survives, and `git status` stays clean.
4. Open the board's agent launch dialog (`ait board` → launch) to confirm the
   prune fires from the real call site with no visible stall.
5. `shellcheck` is not needed (no shell changes); `./.aitask-scripts/aitask_skill_verify.sh`
   is unaffected but cheap to run given the doc touch.
6. Step 9 (Post-Implementation) handles cleanup, archival, and merge.
