---
Task: t635_36_taskworkflown_rendered_set_migration.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_23_port_gate_skills_codex_opencode.md, aitasks/t635/t635_24_remove_legacy_verify_build_path.md, aitasks/t635/t635_26_stats_gate_outcome_analytics.md, aitasks/t635/t635_27_docs_updated_live_verify.md, aitasks/t635/t635_28_docs_updated_activation.md, aitasks/t635/t635_29_procedure_gate_generalization.md, aitasks/t635/t635_30_task_gate_editing_surface.md, aitasks/t635/t635_31_per_gate_agent_model_selection.md, aitasks/t635/t635_32_procedure_gate_remote_signal.md, aitasks/t635/t635_34_reconcile_installed_gate_registry.md, aitasks/t635/t635_35_remote_web_lane_active_gates_materialization.md, aitasks/t635/t635_37_settings_registry_gate_picker.md
Archived Sibling Plans: aiplans/archived/p635/p635_10_monitor_gate_status_column.md, aiplans/archived/p635/p635_11_orchestrator_verifier_contract.md, aiplans/archived/p635/p635_12_build_test_machine_gates.md, aiplans/archived/p635/p635_13_risk_evaluation_gate_integration.md, aiplans/archived/p635/p635_14_profile_gate_declaration_unification.md, aiplans/archived/p635/p635_15_async_human_gates.md, aiplans/archived/p635/p635_19_docs_updated_gate.md, aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_20_stats_multistage_completion.md, aiplans/archived/p635/p635_21_gate_ledger_merge_safety.md, aiplans/archived/p635/p635_22_polish_board_inflight_empty_gate_state.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_33_gate_activation_render_time.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md, aiplans/archived/p635/p635_4_gate_guarded_archival.md, aiplans/archived/p635/p635_5_ledger_driven_reentry.md, aiplans/archived/p635/p635_6_aitask_resume_skill.md, aiplans/archived/p635/p635_7_gate_aware_aitask_pick.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md, aiplans/archived/p635/p635_9_board_inflight_action_view.md
Base branch: main
plan_verified: []
---

# t635_36 — Retire the pickn / task-workflown staging experiment

## Context

**This task has been re-scoped.** It was filed as "migrate `task-workflown`'s 8
stale `{% if profile.risk_evaluation %}` blocks to the `rendered_set` model" (the
carve-out from t635_33). Exploration showed extending the fork is the wrong move,
and the user redirected it to **retire the experiment**. The task file's Scope /
Verification are rewritten as implementation step 0 — no silent AC deviation.

### What the fork is

`aitask-pickn` + `task-workflown` are the t928 "hardening sandbox": parallel
copies of `aitask-pick` / `task-workflow` created to test stricter fail-closed
gates without touching production.

### Why retire rather than migrate

1. **No production callers.** `grep -rn 'pickn\|workflown'` over
   `.aitask-scripts/`, `ait`, `install.sh`, `seed/`, `website/` → **zero hits**.
   Board and minimonitor agent launchers emit `/aitask-pick`
   (`aitask_board.py:5596`, `minimonitor_app.py:1027`).
2. **Silently rotted.** t635_14 removed the `profile.risk_evaluation` key; the
   fork still keys 8 blocks on it, so it has rendered **no** risk machinery under
   any profile ever since. `tests/test_skill_render_task_workflown.sh` fails
   **7 asserts at HEAD**, undetected. t635_33 had to copy `gate-cli.md` into the
   fork purely to keep its file-parity assert green.
3. **Extending it makes it worse.** The fork has *no* gate machinery (zero
   `aitask_gate.sh` references; Step 9 still runs the legacy inline
   `verify_build`). Adding the `materialize-active` the original task asked for
   would persist `active_gates: [risk_evaluated]` on every `fast` pickn task with
   nothing able to record a pass — `aitask_archive.sh`'s `gate_guard` (:667)
   would emit `GATE_PENDING` forever.

### Salvage audit (all 35 fork files classified — not just the overview doc)

Method: normalise the `pickn`→`pick` / `workflown`→`workflow` rename noise, then
diff each fork file against its production counterpart at HEAD and inspect the
**fork-only** lines. (Cross-checked against the fork's creation base
`1a8dcce6a^` to separate "fork is behind" from "fork diverged".)

| Classification | Count | Detail |
|---|---|---|
| Byte-identical to production | 27 | nothing to review |
| Fork **behind** production only | 5 | `task-creation-batch.md`, `gate-recording.md`, `crash-recovery.md`, `risk-mitigation-followup.md`, and SKILL.md's legacy inline `verify_build` + Step-3 notes — production moved on |
| Fork-only, **already shipped** elsewhere | 2 | see below |
| Fork-only, **deliberately discarded** | 2 | see below |
| Fork-only, **not shipped → salvaged** | 1 | see below |

**Already shipped (discard):**
- Pre-implementation + Archive-time Risk Gates — the `grep '^## Risk'` +
  `^### Code-health risk: (high|medium|low)` + `^### Goal-achievement risk:` +
  `^risk_code_health:` + `^risk_goal_achievement:` checks are *exactly*
  `.aitask-scripts/aitask_gate_risk.sh:55-72` (the `risk_evaluated` verifier,
  t635_13 / t1181), enforced at archival by `aitask_archive.sh gate_guard`.
- The fail-closed risk-field write ("is an error, not a skip") — same verifier
  fails when the levels are absent.

**Deliberately discarded:** the 5 stale `{% if profile.risk_evaluation %}` Jinja
conditions (dead key), and `profiles.md`'s row documenting that dead key.

**Not shipped → salvaged:** the Step-9b **final-response gate**
(`satisfaction_feedback_status` = `rated` | `skipped` + a
`satisfaction_skip_reason` from `profile_disabled` | `preprovided_rating` |
`agent_detection_failed` | `question_skipped` | `verified_update_failed`;
"silent omission is not a valid skip reason") plus the matching
`satisfaction-feedback.md` return contract that sets a status on **every** exit
path. Production `task-workflow` has no equivalent — confirmed by
`grep -n 'satisfaction_feedback_status\|Final-response gate'` over the
production tree → zero hits.

## Implementation

Three git commits on two branches, in this order. `aitasks/` and `aiplans/` are
symlinks into the `.aitask-data` worktree (branch `aitask-data`), so task/plan
changes and source changes **cannot** be atomic — the ordering below makes the
salvage survive an interruption at any point.

### Commit 1 (`./ait git`, data branch) — preserve before destroying

1. **Create the salvage task** via the **Batch Task Creation Procedure**
   (`task-creation-batch.md`): independent (not a t635 child), `depends: []`,
   `issue_type: enhancement`, priority low, effort low —
   *"Satisfaction-feedback completion gate for task-workflow"*.
   It must be **self-contained and independently actionable**: quote the retired
   Step-9b gate text and all 5 skip-reason values **verbatim** in the body (the
   source is deleted in commit 2, so a reference would dangle), name the two
   target files (`.claude/skills/task-workflow/{SKILL.md,satisfaction-feedback.md}`),
   and carry its own acceptance criteria + verification. `aitask_create.sh
   --batch` commits it itself.
2. **Re-scope this task** — rewrite `t635_36_taskworkflown_rendered_set_migration.md`'s
   Context / Scope / Key files / Verification to the retirement AC; change
   `issue_type: refactor` → `chore`. Keep the filename (renaming mid-flight
   breaks the lock/plan pairing) and note the name/content mismatch in the body.
3. **`aitasks/metadata/project_config.yaml:19`** — drop `  pickn: fast` from
   `default_profiles`. (Also fixes a latent inconsistency: `pickn` was never in
   `VALID_PROFILE_SKILLS`, `settings_app.py:233-236`, and `save_project_settings`
   rebuilds the block from rendered rows — the settings TUI would have silently
   dropped the key on any save.)
4. **`aitasks/t1215_skill_render_entry_skill_error_message.md:35`** — drop the
   now-dangling "hand-maintained forks like `task-workflown`" parenthetical
   (keep the rule it illustrates); add a reverse coordination note to t635_36.

### Commit 2 (plain `git`, main) — the retirement itself

**2a. Delete the fork — 40 tracked files** (`git rm -r`):

```
.claude/skills/aitask-pickn/            SKILL.md + SKILL.md.j2
.claude/skills/task-workflown/          35 files (the whole closure)
.agents/skills/aitask-pickn/SKILL.md    codex / agy shared-root stub
.opencode/skills/aitask-pickn/SKILL.md
.opencode/commands/aitask-pickn.md
tests/test_skill_render_aitask_pickn.sh
tests/test_skill_render_task_workflown.sh
aidocs/framework/pickn_workflown_experiment.md
```

No rendered variants exist on disk or in git for this tree (only `*-remote-`
prerenders are tracked, and only for `task-workflow`/`pickrem`/`pickweb`), so
there are no goldens to regenerate.

**2b. Upgrade migration — new `.aitask-scripts/aitask_prune_retired_skills.sh`.**

Deleting the sources upstream is not enough. `install_skills` (`install.sh:316-334`),
`setup_codex` (`aitask_setup.sh:2141-2158`) and `setup_opencode` are **additive**
`mkdir -p` + `cp` loops — none removes a destination that disappeared upstream.
`ait upgrade` just re-runs `install.sh --force` (`aitask_upgrade.sh:152`), and
the release tarball fans the fork out through `skills/`, `codex_skills/`,
`opencode_skills/`, `opencode_commands/` (`.github/workflows/release.yml:42-96`).
So an already-installed project keeps a discoverable `/aitask-pickn` after
upgrade, in **eight** locations plus rendered closures:

```
.claude/skills/aitask-pickn/            .claude/skills/task-workflown/
.agents/skills/aitask-pickn/            .opencode/skills/aitask-pickn/
.opencode/commands/aitask-pickn.md
aitasks/metadata/codex_skills/aitask-pickn/
aitasks/metadata/opencode_skills/aitask-pickn/
aitasks/metadata/opencode_commands/aitask-pickn.md
+ rendered: {.claude,.agents,.opencode}/skills/{aitask-pickn,task-workflown}-<profile>[-<agent>]-/
```

The helper is **table-driven and reusable** (this will not be the last
retirement). Two independent safety rules govern it:

**Rule 1 — exact-name matching, never prefix-glob.** `aitask-pickn*` would eat
`aitask-pick`, and `task-workflown-*-` sits one character from
`task-workflow-*-`.

**Rule 2 — prune only *framework-owned, unmodified* copies. Never delete a file
the framework did not ship.** Exact-name matching protects `aitask-pick`, but it
does **not** protect a user who customized `.claude/skills/aitask-pickn/`, kept
their own unrelated skill at that name, or hand-edited an untracked Codex /
OpenCode staging wrapper. An upgrade that silently deletes those is unacceptable.

Identity is decided by **content hash**, not by path or by git-tracked status:

- `.aitask-scripts/retired_skills_manifest.txt` — a committed flat set of every
  git blob SHA any retired file ever had in this repo's history (**98 distinct
  blobs across 37 paths** — measured, so the manifest is small and complete for
  every release the fork shipped in), plus the retired path/stem tables.
  Generated reproducibly; the generating command is documented in the file
  header and re-runnable to regenerate it.
- Per file: `git hash-object <file>` ∈ the manifest → **prune**; otherwise
  → **preserve** and emit `KEPT:<path>:unrecognized-content`.
- This works because release tarballs `cp` files verbatim and the repo has **no
  `.gitattributes`** (verified — no `text=auto` / CRLF filter), so an installed
  copy hashes identically to the blob it came from. Spot-checked on three files:
  on-disk `git hash-object` == `git rev-parse HEAD:<path>`.
- A flat SHA *set* (not per-path) is deliberate: it also covers the staging
  copies under `aitasks/metadata/{codex,opencode}_skills/`, which are byte-for-byte
  `cp`s of the agent-tree wrappers.

**Directories are all-or-nothing.** A retired dir is removed only when *every*
file inside it is manifest-matched **and** it contains no extra files. One
modified or unknown file preserves the **whole directory** — never a partial
delete that leaves a broken half-skill.

**Rendered closures are never deleted by an upgrade.**
(`{.claude,.agents,.opencode}/skills/<stem>-<profile>[-<agent>]-/`.) A shape
check — "only `.md` files, including a `SKILL.md`" — is **not** ownership-aware:
a hand-edited `SKILL.md` keeps that exact shape, so a shape-gated delete would
destroy it silently, which is the very thing Rule 2 exists to prevent. And
ownership *cannot* be proven here: closure content is a function of the user's
own `aitasks/metadata/profiles/*.yaml` (local profiles, edited `fast.yaml`), so
no shipped hash manifest can cover it, and the authoring template needed to
re-render for comparison is exactly what this task deletes.

So the rule is conservative: **name-match retired closures, report them, delete
none.** They are inert once the stub is pruned (nothing dispatches into them),
gitignored (`.gitignore:36-38`), and regenerated on demand, so leaving them costs
a stale directory and nothing else. Emit
`KEPT:<path>:rendered-closure-not-verifiable` for each and name them in the
closing warning with the one-line cleanup command.

An explicit **`--prune-rendered`** flag deletes name-matched closures without a
content check, documented as "removes generated closures unconditionally — do
not use if you have hand-edited them". It is opt-in and never invoked by
`install.sh` / `ait setup`: a user-initiated destructive action is acceptable, a
silent upgrade side effect is not. Roots are resolved through the canonical
`lib/agent_skills_paths.sh` seam in both modes; the name match stays exact
(Rule 1) so `task-workflown-fast-` can never catch `task-workflow-fast-`.

**Output contract:** `PRUNED:<path>` per removal, `KEPT:<path>:<reason>` per
preserved path, exit 0 either way.

**Idempotence means no additional removals, not silence.** `PRUNED:` lines are
one-shot *events* — a second run emits none, because the paths are gone.
`KEPT:` lines and the closing warning are a *standing report of current state*
and therefore **repeat on every run** for as long as the preserved paths exist —
that is required, not a defect: in the default mode every rendered closure is
preserved, so a project with closures would otherwise lose its cleanup
instruction on the very next upgrade. The contract to implement and test is:
**a re-run removes nothing further and exits 0; its `KEPT:` set is identical to
the previous run's.**
When anything was kept, print a closing warning naming the paths, why they were
kept, and the explicit manual cleanup command, e.g.:

```
WARNING: 1 retired skill path was KEPT because its contents differ from every
version the framework shipped (local modification, or your own skill at that
name). The pickn/task-workflown staging experiment was retired in v<X>.
  .claude/skills/aitask-pickn/   (modified)
If you do not need it:  rm -rf .claude/skills/aitask-pickn
```

`install.sh` and `ait setup` must surface this warning in their final summary —
a kept path is a user-visible outcome, not a debug line.

Wiring:
- `install.sh` main() — call after `install_opencode_staging` and before
  `rm -rf seed` (so freshly-restored staging is pruned too), guarded on the
  helper existing (it is extracted from the tarball at :1214, before
  `install_skills` at :1223). Feed the `PRUNED:` lines into the existing commit
  pathspec exactly as the `cached_pycache` one-time-cleanup block already does
  (`install.sh:~1024-1050`) — `commit_framework_files` stages only
  untracked+modified, never deletions, so the removals must be added explicitly.
- `.aitask-scripts/aitask_setup.sh` — call after `setup_codex` / `setup_opencode`
  so `ait setup` (repair) prunes as well.
- `aitasks/metadata/**` paths are on the data branch; route their staged deletion
  through the installer's existing `commit_installed_data_files()` path, not the
  main-branch pathspec.

**2c. `tests/test_prune_retired_skills.sh` — an upgrade fixture, not a fresh
checkout.** Build a temp project populated as a *pre-upgrade install*: all eight
retired locations, rendered closures under all three agent roots, a mix of
git-tracked and untracked, **plus the live neighbours** `.claude/skills/aitask-pick/`,
`.claude/skills/task-workflow/`, `.claude/skills/aitask-pick-fast-/`,
`.claude/skills/task-workflow-remote-/`. Cases:

*Pruned (framework-owned, unmodified):*
- shipped bytes, git-tracked → removed **and** staged as a deletion;
- shipped bytes, untracked (a Codex/OpenCode wrapper the project never
  committed) → removed;
- shipped bytes from an **older** release version (a second manifest SHA for the
  same path) → removed — proves the manifest covers every shipped version, not
  just HEAD.

*Preserved (the Rule-2 guards — each asserts the file is byte-identical
afterwards, `KEPT:` is emitted, the warning names it, and exit is still 0):*
- **modified tracked** retired file (one byte changed) → kept;
- **custom untracked** file at a retired path — a user's own
  `.claude/skills/aitask-pickn/SKILL.md` with unrelated content → kept;
- **modified untracked staging wrapper**
  (`aitasks/metadata/opencode_skills/aitask-pickn/SKILL.md`) → kept;
- retired **directory with one modified file among shipped ones** → the *whole
  directory* survives intact, including the unmodified files (no partial delete);
- **a normal-shaped rendered closure with a hand-edited `SKILL.md`** (only `.md`
  files, `SKILL.md` present — i.e. it passes any shape check) → kept
  byte-identical in the default mode. This is the case a shape-gated delete
  would have destroyed;
- a pristine rendered closure → **also** kept in the default mode (no closure is
  deleted on upgrade), with `KEPT:…:rendered-closure-not-verifiable` emitted;
- rendered closures removed only under the explicit `--prune-rendered` flag, and
  even then a `task-workflow-fast-` neighbour is untouched.

*Negative control (Rule 1):* every live neighbour byte-identical afterwards.
The test must be written to **fail** against a prefix-globbing implementation
(it deletes `aitask-pick`) and against a hash-less implementation (it deletes the
modified/custom files) — run both deliberately-broken variants once to prove the
harness catches them, per the prove-the-harness-can-fail rule.

*Idempotence:* a second run exits 0, emits **no** `PRUNED:` line, leaves the tree
byte-identical, and emits **the same** `KEPT:` set as the first run (assert
equality of the two runs' `KEPT:` output — the repeat is the contract, so a
"prints nothing" assertion would be wrong and would fail against a correct
implementation).

**2d. `aidocs/framework/skill_authoring_conventions.md:~132`** — *keep* the
`<skill>n` parallel-name staging convention (it is sound and still in use), but
add the missing half of the rule: **a staging copy is short-lived — swap it in or
delete it within the same effort, and retiring it means pruning installed
projects, not just deleting the source.** Cite this retirement as the evidence.

**2e. `CHANGELOG.md`** — retirement entry naming the three superseded hypotheses,
the salvaged fourth, and the upgrade-prune migration.

**No change** (verified, documentation_conventions: history stays in the
changelog): `CHANGELOG.md:391/545/582`, `tests/fixtures/skills/README.md:11`
(a quoted commit subject), `aidocs/framework/stub-skill-pattern.md:199` (the
accurate t777 history where `aitask-pickn` *was* renamed into `aitask-pick`).

### Commit 3 (`./ait git`, data branch) — the workflow's own plan commit

### Memory hygiene

`project_rerender_misses_task_workflown` becomes half-wrong once the fork is
gone. Fold its still-true half (the rerender script takes a profile arg; only
`remote` variants are tracked) into the surviving note and drop the
task-workflown half — do not leave a memory naming a deleted path.

## Verification

1. **Baseline first — prove the harness can fail.** Before deleting, record
   `tests/test_skill_render_task_workflown.sh` = 7 failed / 21, and confirm
   `tests/test_prune_retired_skills.sh` fails against **both** deliberately
   broken helper variants: a prefix-globbing one (must delete `aitask-pick` and
   be caught) and a hash-less path-only one (must delete the modified/custom
   files and be caught).
2. **Reference sweep — the structural guard.** After deletion:
   ```bash
   grep -rn 'pickn\|workflown' . --exclude-dir=.git --exclude-dir=aiwork
   ```
   Expected survivors and nothing else: `CHANGELOG.md` (history + the new entry),
   `tests/fixtures/skills/README.md:11`, `aidocs/framework/skill_authoring_conventions.md`,
   `aidocs/framework/stub-skill-pattern.md:199`, the prune helper's retired-paths
   table, `retired_skills_manifest.txt`, the helper's test, the salvage task, and
   this task's own files. Any other hit is a dangling reference.
3. `./.aitask-scripts/aitask_skill_verify.sh` → passes; its `.j2` discovery loses
   exactly one entry (confirm the count drops by 1).
4. `shellcheck` the new helper, `install.sh`, `aitask_setup.sh`.
5. `bash tests/test_prune_retired_skills.sh` green — all prune cases, all five
   preserve-and-warn cases, the live-neighbour negative control, and the
   idempotent re-run.
6. Surviving skill-render suite green: `test_skill_render_task_workflow.sh`
   (production untouched; its `profile.risk_evaluation` absent-asserts at
   :275-278 still pass), `..._aitask_pick.sh`, `..._fold.sh`, `..._pickweb.sh`,
   `test_skill_parity_runtime_vs_rendered.sh`; plus the install/setup suite
   (`test_install_merge.sh`, `test_t644_branch_mode_upgrade.sh`,
   `test_opencode_setup.sh`).
7. `./.aitask-scripts/aitask_skill_resolve_profile.sh pick` → still `fast`,
   proving the `default_profiles` edit did not disturb live keys.
8. **Live negative control:** `/aitask-pickn` gone from the agent skill listing;
   `/aitask-pick` still resolves and renders.
9. **Step 9 (Post-Implementation)** — cleanup / archival / merge.

## Risk

### Code-health risk: medium
- **The prune helper deletes a live skill.** `aitask-pickn` / `task-workflown`
  sit one character from `aitask-pick` / `task-workflow`; a prefix glob in the
  retired-paths table or the rendered-dir expansion destroys a working
  installation on upgrade · severity: high · → mitigation: exact-name matching
  only (Rule 1), rendered roots resolved through the canonical
  `lib/agent_skills_paths.sh` seam, and a negative-control test asserting the
  live neighbours are byte-identical after a prune — the test is written to fail
  against a deliberately globbing implementation
- **The prune helper deletes the user's own work.** An exact retired path is not
  proof of framework ownership: a user may have customized
  `.claude/skills/aitask-pickn/`, kept an unrelated local skill at that name, or
  edited an untracked Codex/OpenCode staging wrapper. Silent deletion on upgrade
  is unrecoverable for untracked files · severity: high · → mitigation: Rule 2 —
  prune only when the file's `git hash-object` is in the committed
  `retired_skills_manifest.txt` (all 98 blobs the fork ever shipped);
  all-or-nothing directory semantics; preserve-and-warn with a manual cleanup
  command otherwise; fixture cases proving modified-tracked, custom-untracked,
  modified-staging and mixed-directory paths all survive byte-identical, with a
  hash-less implementation used as the harness-fails control
- **Rendered closures cannot be proven framework-generated.** Their content is a
  function of the user's own profiles, and the template needed to re-render for
  comparison is deleted by this task — so any shape-based delete (`only .md
  files + a SKILL.md`) would silently destroy a hand-edited `SKILL.md` that keeps
  that shape · severity: medium · → mitigation: upgrades delete **no** closures
  at all (name-match, report, keep); deletion is available only behind the
  opt-in `--prune-rendered` flag; fixture pins a normal-shaped closure with a
  hand-edited `SKILL.md` surviving byte-identical. Accepted cost: upgraded
  projects keep inert, gitignored stale closure dirs until the user runs the
  printed cleanup command
- **Upgrade path leaves zombie wrappers.** A missed install location (one of
  eight, across three agent roots plus two staging dirs) leaves a discoverable
  `/aitask-pickn` in upgraded projects · severity: medium · → mitigation: the
  location list is derived from the actual fan-out
  (`release.yml:42-96` → `install.sh` / `aitask_setup.sh` copy loops), not from
  memory, and the fixture test populates all of them; pickn_retirement_reference_sweep_verify (after)
- **Staged deletions not committed on upgrade.** `commit_framework_files` stages
  only untracked+modified · severity: medium · → mitigation: reuse the existing
  `cached_pycache` one-time-cleanup pattern that already solves exactly this
  (`install.sh:~1024-1050`); data-branch paths routed through
  `commit_installed_data_files()`
- **Losing an un-shipped idea.** · severity: low · → mitigation: all 35 fork
  files audited and classified (table above), and the one un-shipped item is
  created as a self-contained task in **commit 1, before** the deletion

### Goal-achievement risk: low
- **Re-scoped mid-task.** Delivered work no longer matches the filed Scope or the
  filename · severity: low · → mitigation: task file rewritten to the retirement
  AC in commit 1; t635_33's carve-out note answered in the Final Implementation
  Notes so the gate-system thread stays coherent
- **Convention lesson lost.** Deleting the experiment doc without recording *why*
  invites the next long-lived `n` fork · severity: low · → mitigation: the
  retirement rule (including "prune installed projects, not just the source") is
  folded into `aidocs/framework/skill_authoring_conventions.md` beside the
  convention it amends — a source-level fix, not a memory

### Planned mitigations
- timing: after | name: pickn_retirement_reference_sweep_verify | type: manual_verification | priority: medium | effort: low | addresses: code-health "upgrade path leaves zombie wrappers" + "prune helper deletes a live skill" + "prune helper deletes the user's own work" | desc: On a real upgraded project, run ait upgrade and confirm /aitask-pickn is absent from every agent's skill listing (Claude, Codex, OpenCode) while /aitask-pick still resolves and renders; confirm no aitask-pickn/task-workflown AUTHORING or wrapper dirs remain under .claude, .agents, .opencode or aitasks/metadata/{codex,opencode}_skills, while any rendered *-<profile>- closure dirs are reported as KEPT rather than deleted; confirm ait settings shows no pickn row under default_profiles. Then repeat on a project where a retired wrapper AND a rendered closure SKILL.md were hand-edited beforehand: confirm both survive byte-identical, the KEPT warning with its manual cleanup command appears in the upgrade summary, and the upgrade still exits 0. Finally run the helper with --prune-rendered and confirm the closures go while task-workflow-*- / aitask-pick-*- neighbours are untouched.

## Post-Review Changes

### Change Request 1 (2026-07-22 18:40)
- **Requested by user:** One review concern, raised as informational
  (`aitask_prune_retired_skills.sh:210`): default upgrades intentionally retain
  every matching rendered closure because its content cannot be proven
  framework-owned, so only the explicit `--prune-rendered` path removes it. That
  leaves inert, gitignored stale directories until a user cleans them up. The
  user verified the rationale holds — deleting a normal-shaped closure could
  destroy a hand-edited `SKILL.md` — and dispositioned it as informational.
- **Changes made:** **None — no code change required.** Verified the behavior is
  already the documented, tested contract rather than an oversight:
  (a) the rationale is stated in full at the exact cited location and in the
  manifest header; (b) `tests/test_prune_retired_skills.sh` pins it with a
  normal-shaped closure carrying a hand-edited `SKILL.md` surviving
  byte-identical, plus a `--prune-rendered` case; (c) the accepted cost is
  already recorded as a code-health risk bullet in this plan ("Accepted cost:
  upgraded projects keep inert, gitignored stale closure dirs until the user
  runs the printed cleanup command"); and (d) the residual cleanup burden is
  bounded by the closing warning, which emits a named `rm -rf <path>` line for
  every kept closure — confirmed live:

  ```
  Warning: 1 retired skill path(s) were KEPT, not deleted:
      .claude/skills/aitask-pickn-fast-  (rendered-closure-not-verifiable)
    These are safe to leave in place. If you do not need them:
      rm -rf .claude/skills/aitask-pickn-fast-
  ```

  Recorded here so the archived plan carries the review trail for the
  deliberate trade-off.
- **Files affected:** none (documentation of the disposition only).

## Final Implementation Notes

- **Actual work done:** Retired the pickn / task-workflown staging experiment
  end-to-end. Deleted 40 tracked files (the 35-file `task-workflown` closure,
  the `aitask-pickn` stubs in all three agent trees, the OpenCode command, both
  fork tests, and `aidocs/framework/pickn_workflown_experiment.md`). Added the
  upgrade migration the deletion requires: `aitask_prune_retired_skills.sh` +
  `retired_skills_manifest.txt` (8 retired paths, 2 rendered stems, 64 shipped
  blob hashes), wired into `install.sh` and `aitask_setup.sh`, with a 62-assert
  upgrade fixture. Removed `default_profiles.pickn` from `project_config.yaml`,
  redirected the t1215 cross-reference, and extended the `<skill>n` staging
  convention in `skill_authoring_conventions.md` with its missing half (retire
  the copy; retiring means pruning installed projects, not just the source).
  The one unshipped experiment hypothesis was salvaged as **t1218** and
  committed *before* any deletion.

- **Deviations from plan:**
  1. **CHANGELOG entry skipped.** v0.28.0 is already shipped and the file has no
     `Unreleased` section — entries are generated per release by
     `/aitask-changelog` from commits and archived plans. A manual entry would
     have misattributed this change to a released version.
  2. **Staging wiring is simpler than planned.** The plan mirrored the
     `cached_pycache` one-time-cleanup pattern to stage the deletions. Verified
     unnecessary: `git ls-files --modified` already reports deleted files and
     `git add` stages them, and that is exactly how `commit_framework_files()`
     and `commit_installed_data_files()` discover changes. The helper therefore
     never touches the git index at all — a cleaner seam — and the fixture
     asserts the assumption directly.
  3. **Manifest is 64 blobs, not the planned 98.** The 98 figure counted
     per-path duplicates; 64 is the deduped set. Verified complete: every blob
     the retired paths had at HEAD is present.
  4. **Rule 1's hazard was mis-stated in the plan, and the negative control
     caught it.** The plan claimed `aitask-pickn*` could eat `aitask-pick`; it
     cannot — a longer prefix can never swallow a shorter name. The control
     failed for exactly that reason. The real hazard is a retired stem that is a
     **prefix of a live one** (retiring `aitask-pick` while `aitask-pickn`
     lives), which the next retirement can easily hit. The control was rebuilt
     around an inverted-stem manifest and now proves both directions: the real
     helper spares the live longer-named render, the globbing mutation destroys
     it. Helper and manifest comments were corrected to state the rule
     accurately.
  5. Review disposition — see Post-Review Changes 1 (informational, no code
     change).

- **Issues encountered:**
  - The first negative controls silently died on startup: the broken helper
    copies lived in a bare temp dir, so `source "$SCRIPT_DIR/lib/..."` failed
    under `set -e` and they did nothing. The test *reported* failure (correctly)
    but for the wrong reason. Fixed by staging the controls in a dir with
    symlinked `lib/` and manifest, **and** asserting each control exits 0 — a
    control that crashes proves nothing.
  - Diffing the fork against production HEAD was misleading on its own (the fork
    is mostly *behind*, not diverged). The audit needed a second axis — diffing
    against the fork's creation base `1a8dcce6a^` — to separate "production
    moved on" from "the experiment changed something".

- **Key decisions:**
  - **Ownership by content hash, not by path.** An exact retired path is not
    proof the framework owns the file; a user may have customized the skill or
    parked their own at that name. Deleting those on upgrade is unrecoverable
    for untracked files. Directories are all-or-nothing so a partial delete
    cannot leave a broken half-skill.
  - **Rendered closures are never auto-deleted.** Their content is a function of
    the user's own profiles and the template needed to re-render for comparison
    is exactly what this task deletes, so ownership is unprovable. A shape check
    ("only .md, SKILL.md present") is *not* ownership-aware — a hand-edited
    SKILL.md keeps that shape. Deletion is opt-in via `--prune-rendered`;
    upgrades report and keep. Accepted cost: inert gitignored stale dirs, each
    named with an `rm -rf` line in the warning.
  - **Idempotence means no additional removals, not silence.** `PRUNED:` lines
    are one-shot events; `KEPT:` lines are a standing report and must repeat, or
    a project would lose its cleanup instruction on the next upgrade.
  - **A flat SHA set rather than per-path** — it also covers the
    `aitasks/metadata/{codex,opencode}_skills/` staging copies, which are
    byte-for-byte `cp`s of the agent-tree wrappers.
  - **Salvage before deletion, in a separate commit on the data branch.** Task
    files and source live on different branches, so the two cannot be atomic;
    creating t1218 first means the idea survives an interruption at any point.

- **Upstream defects identified:**
  - `.aitask-scripts/settings/settings_app.py:233-236,2517-2527` — `default_profiles`
    keys absent from `VALID_PROFILE_SKILLS` are **silently dropped** whenever
    project settings are saved: `save_project_settings()` rebuilds the whole
    block from the rendered `ConfigRow`s, which are generated only from that
    allow-list. `pickn` sat in `project_config.yaml` in exactly that state (this
    task removed it), but the silent-drop behavior is generic and still present
    for any key the schema does not know — a user hand-adding a
    `default_profiles` entry loses it on the next settings save, with no warning.

- **Notes for sibling tasks:**
  - `aitask_prune_retired_skills.sh` + `retired_skills_manifest.txt` are the
    reusable mechanism for **any** future skill retirement: append `DIR` / `FILE`
    / `STEM` records and regenerate the SHA set with the command in the manifest
    header. Do not hand-roll a second pruner.
  - The additive-copy blind spot is general: `install_skills()`,
    `setup_codex()` and `setup_opencode()` never remove anything. Any t635
    sibling that deletes or renames a shipped skill/wrapper must add a manifest
    entry, or upgraded projects keep the old surface.
  - `install.sh` and `aitask_setup.sh` intentionally duplicate the framework
    path list (`install.sh` runs stand-alone via `curl|bash` and cannot source a
    shared helper) — the prune call is wired into both for the same reason.
  - t635_33's carve-out is now answered: the `task-workflown` lane it deferred
    no longer exists, so there is no second tree to keep in sync with the
    `rendered_set` model. Only t635_35 (remote/web lane) remains from that pair.
