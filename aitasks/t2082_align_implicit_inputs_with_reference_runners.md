---
priority: medium
effort: low
depends: [t1854_8, t1854_9, t1854_10, t1854_11]
issue_type: enhancement
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-10-20 15:21
updated_at: 2026-10-21 22:08
---

## Origin

Risk-mitigation ("after") follow-up for t2081, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — implicit-input rules keyed on language because M3.2 reference runners are not implemented

- **The reference runners (M3.2) are not implemented.** Rules key on the test language, not on the runner's real command line, cwd or unit kind. An implemented runner may read inputs these rules miss. · severity: medium · → mitigation: align_implicit_inputs_with_reference_runners

## Goal

Once M3.2 (`t1854_2`) lands the pytest / go-test / gradle-class / bash-file reference runners, cross-check `goengines/internal/testmap/cost/implicit.go` against what each implemented runner actually reads:
- its command line and working directory: pytest `-c`, `--rootdir`, `-p` plugins and an ini resolved from the cwd rather than the test's ancestors; go-test per-package vs per-file units and its `-run` filter;
- the unit kind and `filter_scope` it declares. A gradle-class runner with `filter_scope: whole_run` is already `opaque:whole-run`.

Add a red-proved row with an exact `anchor_reason` to `TestEligibilityImplicitInputs` for every input the rules miss. Today the rules key on `Facts(test).Lang`; if a runner's real behaviour differs (e.g. its cwd is not an ancestor of the test), key the affected rule on the runner as well. The isolated-mutant harness and the 33 mutants from t2081 are described in that task's archived plan.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_2** id=2026-10-21T19:10:52Z.e7d33849047c15862e65d879 from=t1854_2 from_verified=yes at=2026-10-21T19:10:52Z base=5582dd4f455372f5ba40a43b6d2dffe2101089b3 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_2 (the M3.2 re-decomposition, 2026-10-21). Ids are as of the commit this note records.
> | - Your body says "Once M3.2 (t1854_2) lands …". M3.2 is now split, and your `depends:` names the adapter tasks: t1854_8 bash-file, t1854_9 pytest, t1854_10 go-test / engine-test, t1854_11 gradle-class.
> | - Each adapter records **what it reads** (command line, cwd, config flags) in its Final Implementation Notes, for your cross-check.
> | - Planned shapes:
> |   - **pytest:** native `--collect-only` discovery with the same cwd, ini and rootdir as execution; no `-c` / `--rootdir` / `-p`; cwd an ancestor of every test.
> |   - **go-test:** per-file units, a `-run` filter, `-count=1`, one process per package.
> |   - **gradle-class:** native `--test-dry-run` if confirmed, possibly an adapter-owned init script for report routing.
> | - `aggregate` (suite) results never anchor (`opaque:aggregate`, t1854_2).

> **✉ note:t15** id=2026-10-25T08:54:39Z.45bd770a6e65d8fe53faae70 from=aitasks_go#t15 at=2026-10-25T08:54:39Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t1854_8** id=2026-10-25T12:30:54Z.7819538d42dff0ffb9c7f200 from=t1854_8 from_verified=yes at=2026-10-25T12:30:54Z base=c774eb540e034fdb097cf2d4d4e34a16b08a15a2 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_8 (M3.2e bash-file adapter), landed in e88923ecb: what the bash-file builtin reads, for the eligibility re-alignment. Verify against goengines/README.md ("bash-file builtin (M3.2e)").
> | 
> | - Command line: `<command: split by SplitCommand | bash> ./<cwd-relative path>`, run in the entry's cwd (default the root).
> | - Inventory: `git ls-files -z --cached --others --exclude-standard` in the cwd, with gitx.Env(). git's index and ignore rules are therefore inputs to which units exist.
> | - Config: runners.yaml `cwd`, `bind`, `command`. There are no tool config flags. Script contents and whatever they source are opaque to the engine.
> | - Accounting: unit; discovery: inventory; timeouts: per_unit.

> **✉ note:t1854_9** id=2026-10-26T08:06:14Z.9359c3614a4bf64c48b94988 from=t1854_9 from_verified=yes at=2026-10-26T08:06:14Z base=7f49dbd62e8c9ab5ae05de2935184d3bf72256d7 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_9 (M3.2f pytest adapter), as landed in 0c2f693c9 (engine) / 7f49dbd62 (CI). Verify against goengines/README.md (row "`pytest` builtin (M3.2f)") before relying on it.
> | 
> | What the pytest builtin reads (for re-aligning cost/implicit.go):
> | - Command lines: list `<command: | python3 -m pytest> -p _aitestmap_pytest_evidence --collect-only -q ./<cwd-relative file>…`; run `<command> -p _aitestmap_pytest_evidence ./<file>…`. No -c, --rootdir, -o, --junitxml.
> | - DEVIATION from the "no -p" assumption your body lists (user-authorized 2026-10-25 at t1854_9's plan review): an engine-owned, observe-only evidence plugin is loaded with -p from an engine-private directory PREPENDED to PYTHONPATH; the env also gains AIT_TESTMAP_PYTEST_EVIDENCE. The plugin source is embedded in the engine (part of the engine version), never a project file, and reads no project files.
> | - Cwd: the entry's cwd, an ancestor of every listed test (inventory = cwd-scoped `git ls-files -z --cached --others --exclude-standard`).
> | - pytest resolves the ini from the ARGS' common ancestor upward (i.e. from the tests' ancestors; possibly above the repository root), conftest.py along the tests' paths, PYTEST_ADDOPTS / PYTEST_PLUGINS, installed entry-point plugins.
> | - runners.yaml: cwd, bind, command, batch_timeout_s, zero_tests. The unit lowering is the file's path relative to the rootdir pytest reports (config.rootpath), not the cwd-relative path.

> **✉ note:t1854_12** id=2026-10-27T07:02:16Z.b3757edca6bfc35fa830abf2 from=t1854_12 from_verified=yes at=2026-10-27T07:02:16Z base=aff353fe0e81e10eb613a30540418eb91c820e45 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_12 (M3.2i suite adapter), as landed in commit ecefd276d: what the suite builtin reads.
> | - Command line: `bash -c <command:>`, the whole command: string as one argument (no SplitCommand). runnerConfig's per-whitespace-token treatment of command: still applies, but the suite never anchors (opaque:aggregate, checked before the clean-tree return), so implicit-input precision does not matter for its own results.
> | - Cwd: the entry's `cwd` (default the root).
> | - Inventory: no process. It reads runners.yaml (its own command, cwd, bind (refused), describe overrides; every other entry's bind) and config.yaml `exclude:`.
> | - Environment: inherited from the builtin (AIT_TESTMAP_ROOT / RUNNER / RUN_ID / REPORT_DIR / ACTIVE / COMMAND), stdin /dev/null. No tool config flags; what the command itself reads is opaque.

> **✉ note:t22_3** id=2026-10-29T22:23:29Z.fffe398b8362dd6ee29714fe from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:29Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
