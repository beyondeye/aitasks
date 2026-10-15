---
Task: t1989_trail_gather_owner_validation_archived_owner.md
Branch: main
Base branch: main
Output branch: main
---

# t1989 (+ folded t1958): one owner rule for `trail_gather snapshot`

## Context

`aitask_trail_gather.sh snapshot` has two owner paths that disagree
(`.aitask-scripts/lib/trail_gather.py` `cmd_snapshot`, ~1045-1137):

- **Explicit `--owner`** is checked against `fresh[proj].by_own_id`, which holds
  only the **active** tree. An archived owner fails with `ERROR:unknown_task`.
  Reproduced on the real repo: `snapshot --scope topic --owner 1852 1852` →
  `ERROR:unknown_task:aitasks#1852` (t1852 is archived, loose file).
- **Implicit owner** (no `--owner`, one scope id) is echoed with **no
  validation**: `snapshot --scope topic 1852` → `OWNER:aitasks#1852`. A
  mistyped, deleted, or foreign id passes silently.

The trail skill's refresh step (Step 3.3) tells the agent to **always** pass
`--owner`, so a trail whose owner has since been archived cannot be refreshed
without breaking that rule. Trails outlive their owners by design.

**Folded t1958** (user chose to fold): with `/aitask-trail proj#42` the implicit
owner is the foreign `proj#42`. The skill strips it to `42` and runs
`aitask_artifact.sh create 42`, which attaches the trail to the unrelated local
t42, or fails. A foreign owner is never valid. Both bugs are in the same
owner-resolution block and the same skill text.

**Two review concerns, both verified by a scratch probe:**
1. **Refresh strips the stored owner's prefix.** A trail whose stored owner is
   `trailtest-zz9#12` passes schema validation (`owner` is a plain `task_ref`)
   and drift reports `CURRENT`. Step 3.3's conversion (`aitasks#1210` → `1210`)
   then passes `--owner 12`, which resolves to the unrelated local
   `mainproj#12`. The foreign-owner guard can only fire if refresh passes the
   **full stored ref**. `--owner mainproj#100` already works today, because
   `canonical_id` → `parse_ref` accepts a local-qualified ref.
2. **Owner errors leave J4 without candidates.** An owner error prints only
   `ERROR:` lines (`'ERROR:unknown_task:mainproj#999\n'`), never `SCOPE:` or
   `MEMBER:`. A foreign-only task scope has no local member at all. Recovery
   therefore needs a complete candidate run and a strict rerun.

## Design: the owner rule

The rule covers the explicit `--owner` and the implicit single-scope-id owner.
Checks run in this order:

| Owner state | Result |
|---|---|
| other project (`proj#id`, proj ≠ local) | `ERROR:foreign_owner:<ref>` |
| active local task | valid |
| only in the archive (loose, `_b*/old*.tar.zst` or legacy `old.tar.zst`), **no** `--allow-archived-owner` | `ERROR:archived_owner:<ref>` |
| only in the archive, **with** `--allow-archived-owner` | valid |
| archive lookup could not be completed (corrupt bundle, no zstd, unlistable dir) | `ERROR:owner_unverifiable:<ref>` (+ `trail_gather:` diagnostic on stderr) |
| nowhere | `ERROR:unknown_task:<ref>` (unchanged) |

- **Create refuses an archived owner by default. Refresh opts in with
  `--allow-archived-owner`.** The `OWNER:` line feeds
  `aitask_artifact.sh create <owner_id>`. `resolve_task_file`
  (`lib/task_utils.sh:2324`) also resolves archived files, so create would write
  an `artifacts:` entry into an archived task. A new trail must attach to a live
  task. Refusing by default is the safe direction: a caller that forgets the flag
  gets a named refusal, never a write into the archive.
  `roadmap_run.py`, the only other caller, uses `--scope task` with local active
  ids, so its implicit owner is always a valid active member. Its behaviour does
  not change.
- **New `--no-owner` flag** (mutually exclusive with `--owner`, enforced by
  argparse, so passing both is a usage error with exit 2). It resolves no owner
  and emits `OWNER:none`, the same shape a multi-id scope already produces. This
  is the complete candidate run that J4 recovery needs (concern 2). Membership,
  records and digest are identical to an owned run, because the owner is not a
  digest input.
- `owner_unverifiable` exists because `find_archived_markdown_by_id(..., errors=)`
  can return "not found" without having read the bundle. Reporting that as
  `unknown_task` would claim the task does not exist when it was never checked.
  This is the fail-closed rule that an incomplete scan is not an empty one.

## Implementation steps

### 1. Fold t1958 into t1989 (first write after plan approval)
```bash
./.aitask-scripts/aitask_fold_content.sh aitasks/t1989_trail_gather_owner_validation_archived_owner.md \
  aitasks/t1958_trail_snapshot_foreign_scope_owner.md \
  | ./.aitask-scripts/aitask_update.sh --batch 1989 --desc-file -
./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh 1989 1958
```
(`aitask_fold_validate.sh --exclude-self 1989 1958` → `VALID:1958`, already run.)

### 2. `.aitask-scripts/lib/trail_gather.py`

a. New helper next to `_resolve_scope_ids`. It reuses the already-imported
   `find_archived_markdown_by_id` from `lib/archive_iter.py`:
```python
def _owner_error(owner: tuple[str, str], fresh: dict[str, ProjectTree],
                 local_name: str, allow_archived: bool) -> str | None:
    """The owner rule (t1989), one definition for the explicit --owner and the
    implicit single-scope-id owner. None = valid; else a staged error."""
    proj, bare = owner
    ref = f"{proj}#{bare}"
    if proj != local_name:
        return f"foreign_owner:{ref}"          # trails are local-task-owned
    tree = fresh[local_name]
    if tree.by_own_id.get(bare) is not None:
        return None
    lookup_errors: list[str] = []
    if find_archived_markdown_by_id(bare, tree.archived_dir,
                                    errors=lookup_errors) is not None:
        return None if allow_archived else f"archived_owner:{ref}"
    if lookup_errors:                           # could not rule archived out
        for err in lookup_errors:
            print(f"trail_gather: owner {ref}: {err}", file=sys.stderr)
        return f"owner_unverifiable:{ref}"
    return f"unknown_task:{ref}"
```

b. `cmd_snapshot`, up-front argument stage:
   - after `canonical_id(args.owner)` succeeds, a foreign explicit owner →
     `errors.append(f"foreign_owner:{p}#{b}")`. This is staged with the other
     argument errors and comes before project resolution, so an unregistered
     foreign owner reports `foreign_owner`, not `unresolved_project`.
   - only a **local** owner adds its project to `projects`, so a foreign owner's
     tree is never loaded.
   - compute the owner candidate once: `None` under `--no-owner`; else
     `owner_parsed`; else `ids[0]` when `len(ids) == 1`; else `None`.

c. `scan()`: remove the inline "Validate --owner" block. On error, return the
   fresh trees: `return [], (scan_errors, [], fresh)`. Owner validation moves
   **after** `stable_records`, so it runs once (one archive lookup, one stderr
   diagnostic) against the accepted scan's `fresh` trees. Its error is merged
   with any scan errors and emitted together as `sorted(set(...))`. This keeps
   today's all-errors-together behaviour, and a duplicate `unknown_task:<ref>`
   (a topic id with no members that is also the implicit owner) collapses to one
   line.

d. The OWNER emission is unchanged: a valid candidate's ref, else `none`.

e. argparse: put `--owner` and `--no-owner` in an `add_mutually_exclusive_group()`.
   Add `--allow-archived-owner` (store_true). Help text:
   "accept an owner found only in the archive -- refresh of an existing trail;
   a new trail must attach to a live task" /
   "emit OWNER:none without resolving an owner -- the candidate run of owner
   recovery". Read both with `getattr(args, ..., False)`, matching
   `with_inflight`.

f. Module docstring: add both flags to the verb synopsis, a short "OWNER RULE"
   paragraph (the table above, condensed), and
   `archived_owner, foreign_owner, owner_unverifiable` to the error vocabulary.

### 3. `.aitask-scripts/aitask_trail_gather.sh`
Header usage comment:
`snapshot --scope ... [--owner <id> | --no-owner] [--allow-archived-owner] <ids...>`.
Arguments already pass through to Python, so no logic changes.

### 4. `.claude/skills/aitask-trail/SKILL.md.j2`

- **Gatherer contract** (~line 54): update the synopsis, and add a short
  owner-rule paragraph covering: the rule applies to both explicit and implicit
  owners; the four owner errors; `--allow-archived-owner` is for refresh only;
  `--no-owner` is for the recovery candidate run only.

- **Step 2b: owner recovery (create only)**, replacing "Any `ERROR:` → report
  and stop" for one case:
  1. **Classify.** Recovery applies only when **every** `ERROR:` line is an
     owner error naming the owner candidate. Owner errors are `archived_owner`,
     `foreign_owner`, `owner_unverifiable`, and `unknown_task`. The owner
     candidate is the `--owner` value, or the single scope id when no `--owner`
     was passed. Anything else stops the flow with no recovery: a nonzero exit,
     any other kind (`unresolved_project`, `cross_repo_topic_unsupported`,
     `unstable_repository_state`, …), or `unknown_task` naming a different id.
  2. **Candidate run.** Re-run the **same scope and ids** with `--no-owner`. If
     it exits nonzero or prints **any** `ERROR:` line, stop: the scope itself is
     invalid, e.g. a topic with no members (this is what tells "the root is
     gone" apart from "the topic does not exist"). Otherwise take candidates
     from its `MEMBER:` lines whose ref is in this repository. Members are
     active by construction. **Never analyze or write from this run.**
  3. **Ask (J4).** Offer up to three local candidates, plus free text via
     "Other". If there are **no** local candidates (e.g. a foreign-only task
     scope), ask for an explicit local task id instead: options "Enter a local
     task id" / "Cancel trail creation".
  4. **Strict rerun.** Run `--owner <choice>` without `--allow-archived-owner`.
     Proceed to 2c **only** if it exits 0, prints no `ERROR:` line, and echoes
     `OWNER:<this repo>#<choice>`. Only this run's SCOPE/MEMBER/INPUT/DIGEST
     lines feed analysis and the trail document. If it fails with an owner error
     naming the choice, return to 3 and say why. Any other error → stop.

  The existing `OWNER:none` path (multi-topic / multi-id) joins at step 3,
  taking candidates from that already-complete run. The owner sentence becomes:
  "must be a live (active) task in this repository — never archived, never
  another repository's".

- **Step 2e.4** (~485): the strict rerun guarantees a local `OWNER:`, so
  stripping `<this repo>#` to get the bare id for `aitask_artifact.sh create` is
  safe. Never strip any other project's prefix (t1958).

- **Step 3.3 refresh** (concern 1): "Always pass `--owner <owner>
  --allow-archived-owner`, where `<owner>` is the loaded trail's `owner` field
  **verbatim**, the full `<project>#<id>` ref. Never strip its prefix: a stripped
  foreign owner silently resolves to an unrelated local task." The loaded owner
  may have been archived since; the flag accepts it. Any owner error stops the
  refresh, and refresh never re-opens ownership. `foreign_owner` means the
  stored owner is another repository's task, written before t1958's fix: report
  that the trail's owner is invalid and that it must be recreated under a local
  owner.

Then regenerate the 3 goldens (`tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`)
with the command in `aidocs/framework/skill_authoring_conventions.md`. The diff
must show only these edits.

**Other agent trees:** Codex (`.agents/skills/aitask-trail/SKILL.md`) and
OpenCode (`.opencode/skills/aitask-trail/SKILL.md`, `.opencode/commands/aitask-trail.md`)
are stubs that render this same `.j2` with `--agent codex|opencode`, so the
edit reaches them on render. The render test's Test 1b (agent invariance)
checks this. No port task is needed; I'll say so in the final notes.

### 5. `aidocs/implementation_trail_design.md`
Add one sentence under the §3 invocation matrix: a **new** trail's owner must be
a live local task. If J2/J3's default owner is archived, missing, or in another
repository, the owner is chosen as in J4. An existing trail keeps its stored
owner, passed verbatim on refresh, after that task is archived (J5/J6).

### 6. Tests: `tests/test_trail_gather.py`
New `OwnerRuleTests(TrailGatherCase)` after `OwnerHandoffTests`. Fixture: active
t100 (topic root) plus an archived t500.
- explicit archived owner + `--allow-archived-owner` → `OWNER:mainproj#500`, no
  errors;
- explicit archived owner without the flag → errors ==
  `["archived_owner:mainproj#500"]`, no `SCOPE:` line;
- explicit nonexistent owner, with and without the flag → `unknown_task`;
- **stored-owner refresh form (concern 1):** `--owner mainproj#500
  --allow-archived-owner` (the qualified ref a refresh passes verbatim) →
  `OWNER:mainproj#500`;
- implicit topic owner whose root exists nowhere (t104 `anchor: 200`) → errors
  `["unknown_task:mainproj#200"]`, no `OWNER:` line. `--no-owner` →
  `OWNER:none` with members `[mainproj#104]`;
- implicit archived topic root (archived t200, t104 `anchor: 200`; the real
  t1852 shape) → `archived_owner` without the flag. With the flag:
  `OWNER:mainproj#200`, members `[mainproj#104]`;
- `--no-owner` on a topic with no members → `unknown_task`, so the candidate run
  still stops on a scope error;
- `--no-owner` together with `--owner` → exit 2;
- the digest is identical across `--no-owner`, an active `--owner`, and an
  archived owner with the flag. The owner is not a digest input, so the
  candidate run and the strict rerun agree;
- owner only in an `aitasks/archived/old.tar.zst` bundle (built with tarfile +
  `zstd`, `skipUnless(shutil.which("zstd"))`) + flag → accepted;
- corrupt `old.tar.zst` (`b"not a zstd frame"`), owner not loose →
  `owner_unverifiable:mainproj#500`, never `unknown_task`.

`CrossRepoTests` additions (t1958 + concern 1). The fixture adds a local t12
next to the foreign t12:
- **stored foreign owner on refresh:** `--owner trailtest-zz9#12
  --allow-archived-owner --scope task 100` → `["foreign_owner:trailtest-zz9#12"]`,
  never `OWNER:mainproj#12`. The same test pins the hazard: the stripped form
  `--owner 12` resolves to `OWNER:mainproj#12`. The comment explains this is why
  refresh passes the stored ref verbatim;
- explicit foreign owner of an **unregistered** project → `foreign_owner`, not
  `unresolved_project`;
- implicit single foreign scope id `--scope task trailtest-zz9#12` →
  `foreign_owner`. `--no-owner` → `OWNER:none`, member `trailtest-zz9#12`, and
  no local member (the "no local candidates" case). `--owner 100` → succeeds
  with `OWNER:mainproj#100`.

Existing test adjusted: `TopicScopeTests.test_anchor_to_archived_root_still_keys_by_anchor`
(no t200 anywhere) now passes `--no-owner`. It pins topic *membership*, and an
unknown root can no longer be the implicit owner. The ownership side is pinned
above. `test_unregistered_project_error`, `test_unknown_owner_error_alone`, and
`test_cross_repo_topic_rejected` stay unchanged and must still pass.

### 7. Tests: `tests/test_skill_render_aitask_trail.sh`: new Test 6 (owner prose)
Over the fast render, extract the `### Step 3: Refresh Flow` section up to the
next `### `/`## ` heading, and the `#### 2b` section. Assert:
- Step 3 contains `--allow-archived-owner` and `verbatim`;
- Step 3 does **not** contain the old strip example (`` `aitasks#1210` → `1210` ``).
  A golden diff alone would not stop a later edit from restoring the strip, so
  this negative assertion carries concern 1 into the skill layer;
- 2b contains `--no-owner`, and the strict-rerun phrase "no `ERROR:` line".
Each assertion is checked once against the pre-edit template (expected to fail)
before the template is edited.

**Negative control (throwaway, recorded verbatim in Final Implementation Notes):**
create a scratch `git worktree add --detach <scratch>/pre HEAD` (no stash), copy
the new `tests/test_trail_gather.py` into it, and run `OwnerRuleTests` +
`CrossRepoTests`. The archived-owner-accepted, implicit-unknown, and foreign
tests must FAIL against the pre-fix module. Then remove the worktree.

### Post-phase (risk mitigations)
1. [live_archived_owner_smoke] On the real repository (cwd = repo root), after
   the unit tests pass, run and check each line:
   - `./.aitask-scripts/aitask_trail_gather.sh snapshot --scope topic --owner aitasks#1852 --allow-archived-owner 1852`
     (the verbatim-ref refresh form) → `OWNER:aitasks#1852` and a `DIGEST:`
     line. t1852 is a loose archived file;
   - the same without `--allow-archived-owner` → exactly
     `ERROR:archived_owner:aitasks#1852`;
   - `snapshot --scope topic 1852` (implicit) → `ERROR:archived_owner:aitasks#1852`;
     `--no-owner` → `OWNER:none` plus the topic's members. Its `DIGEST:` must
     equal the first command's;
   - one bundled owner: an id present only in a numbered bundle (no loose file
     under `aitasks/archived/`, e.g. in `_b0/old*.tar.zst`) →
     `snapshot --scope topic --owner aitasks#<id> --allow-archived-owner 1852`
     → `OWNER:aitasks#<id>`.
   Record the commands and their exact output in the plan's Final
   Implementation Notes.

## Verification
- `python3 -m unittest tests.test_trail_gather -v` (whole module green)
- `bash tests/test_skill_render_aitask_trail.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `shellcheck .aitask-scripts/aitask_trail_gather.sh`
- Other snapshot consumers: `python3 -m unittest tests.test_roadmap_drift_contract
  tests.test_roadmap_integration` (they run `snapshot --scope task`).
- The post-phase real-repo smoke above.

## Risk

### Code-health risk: low
- `snapshot` without `--owner` now refuses three cases it used to accept: a
  topic whose root is archived or missing, and a single foreign task scope.
  Only the trail skill (owner recovery, step 4) and roadmap_run (task scope,
  local active ids, so not affected) call it · severity: low · → mitigation: inline post-phase live_archived_owner_smoke
- Three new `ERROR:` kinds and two flags widen the contract consumers must know.
  They are documented in the module docstring and the skill contract, and the
  skill's recovery prose is pinned by render Test 6 · severity: low · → mitigation: None (documented in-plan)

### Goal-achievement risk: low
- Fixtures could miss the real archive layout (t1852 is a loose archived file;
  others sit in `_b*/old*.tar.zst`), so the fix could pass unit tests and still
  fail on the real trail · severity: low · → mitigation: inline post-phase live_archived_owner_smoke

### Planned mitigations
- timing: post-phase | name: live_archived_owner_smoke | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: behaviour change on real archived owners; fixture/real-layout mismatch | desc: real-repo snapshot of topic 1852 with/without --allow-archived-owner, implicit, --no-owner, plus one numbered-bundle owner

(Post-inline reassessment: the phase adds a read-only check and no code, so
both levels stay **low**.)

## Step 9
Current-branch profile. Commit code as `bug: … (t1989)`, then
archive t1989 via `aitask_archive.sh 1989`. The archive deletes the folded t1958.

## Post-Review Changes

### Change Request 1 (2026-10-15 09:28)
- **Requested by user:** moving owner validation after `stable_records` lost
  detection of an owner archived between scans. The owner is outside the input
  records, so both scans digest identically, and `stable_records` returned the
  earlier scan's stale tree: `OWNER:mainproj#500` without
  `--allow-archived-owner`. Validate from a current lookup, or keep owner state
  in the cross-scan comparison while the public digest stays owner-independent;
  add a transition regression test.
- **Verified:** `test_owner_archived_between_scans_is_refused` (archives t700
  right after the first scan's `build_input_records`) failed on the pre-change
  code with `Lists differ: [] != ['archived_owner:mainproj#700']`.
- **Changes made:**
  - `stable_records(scan_fn, max_scans, state_fn=None)` now compares
    `(digest, state_fn(payload))` across the pair. `state_fn` names state the
    caller acts on that is not in the records; it never enters the digest.
    drift passes no `state_fn`, so its behaviour is unchanged.
  - `cmd_snapshot` passes `owner_presence`: whether a local owner candidate is
    in that scan's active tree. An owner archived mid-read therefore forces
    another scan, and the accepted payload carries the settled presence. The
    archive lookup still runs once afterwards.
  - Tests: two transition tests (refused without the flag, accepted with it),
    a direct `stable_records` unit test for `state_fn`, and the
    `test_cmd_surface_reports_unstable` stub updated to the new signature.
  - New mutant M7 (stop passing `state_fn`) → caught by
    `test_owner_archived_between_scans_is_refused`.
- **Files affected:** `.aitask-scripts/lib/trail_gather.py`, `tests/test_trail_gather.py`

## Final Implementation Notes
- **Actual work done:**
  - `lib/trail_gather.py`: `_owner_error()` is the one owner rule for the
    explicit `--owner` and the implicit single-scope-id owner: foreign →
    `foreign_owner`; active → valid; archive-only → `archived_owner`, or valid
    under `--allow-archived-owner`; archive lookup incomplete →
    `owner_unverifiable` (stderr diagnostic); nowhere → `unknown_task`.
  - An explicit foreign owner is refused up front, before project
    resolution.
  - The new `--no-owner` flag (exclusive with `--owner`) is the owner-recovery
    candidate run.
  - Owner validation runs once after the stable read. The owner's per-scan
    active presence is part of the stability key (Change Request 1).
  - The docstring carries the rule and the three new error kinds.
  - `aitask_trail_gather.sh` usage comment.
  - `aitask-trail/SKILL.md.j2`, with goldens regenerated (their diff equals
    the template diff for all three profiles):
    - contract owner-rule paragraph;
    - 2b owner recovery: classify → `--no-owner` candidate run → J4 (explicit
      local id when no candidates) → strict rerun with no `ERROR:` line;
    - 2e.4: stripping is safe only for a create-time `OWNER:`;
    - 3.3: refresh passes `--owner <stored owner verbatim>
      --allow-archived-owner`.
  - `aidocs/implementation_trail_design.md`: one sentence under the §3
    matrix.
  - Folded t1958 (foreign owner) into this task.
- **Deviations from plan:**
  - The negative control ran **in place, before the fix** (tests written
    first, then run against the unchanged module), instead of in a scratch
    worktree at HEAD. Same evidence, no worktree.
  - Two existing membership tests needed `--no-owner`, not one:
    `test_anchor_to_archived_root_still_keys_by_anchor` and
    `test_orphan_child_clusters_under_absent_parent_id`. Both topic roots exist
    nowhere.
  - Render Test 6's "verbatim" assertion was tightened to `` `owner` field
    verbatim ``: the bare word already occurred in the pre-edit refresh section
    ("surface verbatim"), so the first form passed before the edit.
  - The Change Request 1 stability-key fix (see Post-Review Changes) was not in
    the plan.
- **Issues encountered:**
  - The first mutant harness copied `lib/` alone, so `aitask_project_resolve.sh`
    (resolved relative to `lib/`'s parent) was missing. Four CrossRepo tests
    failed under every mutant. Fixed by symlinking the real siblings and adding
    an unmutated M0 baseline (0 failures).
  - The new-flag tests fail pre-fix on argparse usage (rc 2) rather than on the
    guard, so the flag-free negative-control script below is the guard-specific
    pre-fix evidence.
- **Key decisions:**
  - Create refuses archived owners by default, and refresh opts in. The
    `OWNER:` line feeds `aitask_artifact.sh create`, which resolves archived
    files too.
  - `owner_unverifiable` keeps not-read distinct from not-found.
  - The owner is not a digest input (pinned by
    `test_owner_is_not_a_digest_input`), so the candidate run and the strict
    rerun agree.
  - Other agent trees need no port task: the Codex and OpenCode stubs render
    this same `.j2`, which Test 1b (agent invariance) checks.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_artifact.sh:241 — cmd_create resolves the owner
    with resolve_task_file (lib/task_utils.sh:2324), which also returns archived
    loose files and bundle-extracted temp files, so 'ait artifact create
    <archived id>' does not refuse an archived owner and would write an
    artifacts: entry into an archived task file (by code reading; not
    reproduced)`

### Verification evidence

- `python3 -m unittest tests.test_trail_gather tests.test_roadmap_drift_contract
  tests.test_roadmap_integration tests.test_implementation_trail_design
  tests.test_trail_schema tests.test_board_bytrail_view tests.test_trail_links`
  → `Ran 579 tests … OK`
- `bash tests/test_skill_render_aitask_trail.sh` → `Tests: 59, Passed: 59, Failed: 0`.
  Test 6's five content assertions were run against the pre-edit template and
  failed there.
- `./.aitask-scripts/aitask_skill_verify.sh` → `OK (14 template(s) verified across 3 agents, 4 stub surfaces; wrapper parity clean)`
- `shellcheck .aitask-scripts/aitask_trail_gather.sh` → clean

**Negative-control script** (scratch `negctl_t1989.py`, verbatim):

```python
"""t1989 negative control: flag-free owner shapes against the CURRENT module."""
import os, sys, unittest
from pathlib import Path
sys.path.insert(0, "/home/ddt/Work/aitasks/tests")
import test_trail_gather as T

class NegCtl(T.TrailGatherCase):
    def runTest(self):
        base = Path(self._tmp.name)
        foreign = T.SyntheticRepo(base / "foreign", T.FOREIGN)
        Path(os.environ["AITASKS_PROJECTS_INDEX"]).write_text(
            f"projects:\n  - name: {T.FOREIGN}\n    path: {foreign.root}\n")
        foreign.write_task("12", "foreign_task")
        self.repo.write_task("100", "root")
        self.repo.write_task("12", "unrelated_local")
        self.repo.archive_task("500", "landed_owner")
        self.repo.archive_task("200", "archived_root")
        self.repo.write_task("104", "late", anchor=200)
        self.repo.write_task("105", "late2", anchor=300)  # no t300 anywhere
        cases = [
            ("explicit archived owner", ["--scope", "topic", "--owner", "500", "100"]),
            ("implicit archived topic root", ["--scope", "topic", "200"]),
            ("implicit missing topic root", ["--scope", "topic", "300"]),
            ("explicit foreign owner", ["--scope", "task", "--owner", f"{T.FOREIGN}#12", "100"]),
            ("implicit foreign single scope", ["--scope", "task", f"{T.FOREIGN}#12"]),
        ]
        for label, argv in cases:
            out, rc = self.run_cli("snapshot", *argv)
            head = [l for l in out.splitlines() if l.startswith(("OWNER:", "ERROR:"))]
            print(f"{label:32} rc={rc} {head}")

unittest.TextTestRunner(verbosity=0).run(NegCtl())
```

Output against the **pre-fix** module:
```
explicit archived owner          rc=0 ['ERROR:unknown_task:mainproj#500']
implicit archived topic root     rc=0 ['OWNER:mainproj#200']
implicit missing topic root      rc=0 ['OWNER:mainproj#300']
explicit foreign owner           rc=0 ['OWNER:trailtest-zz9#12']
implicit foreign single scope    rc=0 ['OWNER:trailtest-zz9#12']
```
Output after the fix:
```
explicit archived owner          rc=0 ['ERROR:archived_owner:mainproj#500']
implicit archived topic root     rc=0 ['ERROR:archived_owner:mainproj#200']
implicit missing topic root      rc=0 ['ERROR:unknown_task:mainproj#300']
explicit foreign owner           rc=0 ['ERROR:foreign_owner:trailtest-zz9#12']
implicit foreign single scope    rc=0 ['ERROR:foreign_owner:trailtest-zz9#12']
```
Change Request 1 pre-fix evidence: `test_owner_archived_between_scans_is_refused`
→ `AssertionError: Lists differ: [] != ['archived_owner:mainproj#700']`.

**Mutant harness** (scratch `mutants_t1989.py`, verbatim):

```python
"""t1989 mutants: each guard must have a test that fails when it is removed."""
import shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path("/home/ddt/Work/aitasks")
SRC = REPO / ".aitask-scripts/lib/trail_gather.py"
MUTANTS = {
    "M0 baseline (no mutation)": ("def _owner_error(", "def _owner_error("),
    "M1 archive lookup ignored": ("if find_archived_markdown_by_id(bare, tree.archived_dir,",
                                  "if False and find_archived_markdown_by_id(bare, tree.archived_dir,"),
    "M2 allow flag ignored": ("return None if allow_archived else f\"archived_owner:{ref}\"",
                              "return f\"archived_owner:{ref}\""),
    "M3 implicit owner unvalidated": ("    if owner_candidate is not None:\n        owner_err",
                                      "    if owner_parsed is not None:\n        owner_err"),
    "M4 explicit foreign accepted up front": ("        elif owner_parsed[0] != local_name:",
                                             "        elif False:"),
    "M6 helper foreign branch removed": ("    if proj != local_name:\n        return f\"foreign_owner:{ref}\"",
                                         "    if False:\n        return f\"foreign_owner:{ref}\""),
    "M7 owner presence not in stability key": ("result = stable_records(scan, state_fn=owner_presence)",
                                               "result = stable_records(scan)"),
    "M5 lookup errors dropped": ("errors=lookup_errors) is not None:", ") is not None:"),
}
RUNNER = """
import sys, unittest
sys.path.insert(0, {lib!r})
import trail_gather
assert trail_gather.__file__.startswith({lib!r}), trail_gather.__file__
sys.path.insert(0, {tests!r})
import test_trail_gather as T
suite = unittest.TestSuite()
for cls in (T.OwnerRuleTests, T.CrossRepoTests, T.OwnerHandoffTests, T.TopicScopeTests):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
r = unittest.TextTestRunner(stream=open('/dev/null', 'w')).run(suite)
bad = sorted(t.id().rsplit('.', 1)[1] for t, _ in r.failures + r.errors)
print(len(bad), bad)
"""
text = SRC.read_text()
for label, (old, new) in MUTANTS.items():
    assert text.count(old) == 1, (label, text.count(old))
    with tempfile.TemporaryDirectory() as tmp:
        # A scripts dir whose siblings (aitask_project_resolve.sh, ...) are the
        # real ones: trail_gather resolves them relative to its own lib/.
        scripts = Path(tmp) / "scripts"
        scripts.mkdir()
        for entry in SRC.parent.parent.iterdir():
            if entry.name != "lib":
                (scripts / entry.name).symlink_to(entry)
        lib = scripts / "lib"
        shutil.copytree(SRC.parent, lib)
        (lib / "trail_gather.py").write_text(text.replace(old, new))
        out = subprocess.run([sys.executable, "-c", RUNNER.format(lib=str(lib), tests=str(REPO / "tests"))],
                             capture_output=True, text=True, cwd=REPO)
        print(f"{label}: {out.stdout.strip() or out.stderr.strip()[-300:]}")
```

Output (final code):
```
M0 baseline (no mutation): 0 []
M1 archive lookup ignored: 9 ['test_archived_explicit_owner_accepted_with_flag', 'test_archived_explicit_owner_refused_without_flag', 'test_implicit_archived_topic_root', 'test_owner_archived_between_scans_accepted_with_flag', 'test_owner_archived_between_scans_is_refused', 'test_owner_is_not_a_digest_input', 'test_owner_only_in_legacy_bundle_accepted', 'test_qualified_stored_owner_ref_accepted', 'test_unreadable_bundle_is_unverifiable_not_unknown']
M2 allow flag ignored: 6 ['test_archived_explicit_owner_accepted_with_flag', 'test_implicit_archived_topic_root', 'test_owner_archived_between_scans_accepted_with_flag', 'test_owner_is_not_a_digest_input', 'test_owner_only_in_legacy_bundle_accepted', 'test_qualified_stored_owner_ref_accepted']
M3 implicit owner unvalidated: 3 ['test_implicit_archived_topic_root', 'test_implicit_foreign_single_scope_owner', 'test_implicit_owner_missing_root_is_an_error']
M4 explicit foreign accepted up front: 1 ['test_foreign_owner_of_unregistered_project']
M6 helper foreign branch removed: 1 ['test_implicit_foreign_single_scope_owner']
M7 owner presence not in stability key: 1 ['test_owner_archived_between_scans_is_refused']
M5 lookup errors dropped: 1 ['test_unreadable_bundle_is_unverifiable_not_unknown']
```
M4 trips only the unregistered-project test. That is expected: the helper's
own foreign branch still catches a registered foreign owner (M6 removes that
second layer).

**Post-phase [live_archived_owner_smoke]** (real repo, before Change Request 1):
```
$ snapshot --scope topic --owner aitasks#1852 --allow-archived-owner 1852
SCOPE:topic|aitasks#1852
OWNER:aitasks#1852
DIGEST:b74356d6e02f2d9a
$ snapshot --scope topic --owner aitasks#1852 1852
ERROR:archived_owner:aitasks#1852
$ snapshot --scope topic 1852
ERROR:archived_owner:aitasks#1852
$ snapshot --scope topic --no-owner 1852
SCOPE:topic|aitasks#1852
OWNER:none
DIGEST:b74356d6e02f2d9a
MEMBER lines: 29
$ snapshot --scope topic --owner aitasks#50 --allow-archived-owner 1852   # t50: only in _b0/old0.tar.zst
OWNER:aitasks#50
DIGEST:b74356d6e02f2d9a
$ snapshot --scope topic --owner aitasks#50 1852
ERROR:archived_owner:aitasks#50
```
Re-run after Change Request 1: `OWNER:aitasks#1852` / `ERROR:archived_owner:aitasks#1852`
unchanged. The digest had moved to `abae5320891e328e` because topic 1852's
members changed on disk between the runs; the owner is not a digest input.
