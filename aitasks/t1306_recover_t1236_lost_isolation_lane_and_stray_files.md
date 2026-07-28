---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, git-integration]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1162
implemented_with: claudecode/opus5
created_at: 2026-07-28 18:26
updated_at: 2026-07-28 18:43
---

## Origin

Found by `/aitask-explore` while auditing the 8 uncommitted paths in the shared
checkout, to classify each as in-flight task work vs. leftovers of committed
tasks. Four of them turned out to be neither: they are the *only surviving copy*
of a task that is already archived as Done.

## Defect: t1236's implementation is not in main

t1236 (`aitasks/archived/t1236_pythonpath_isolated_python_test_lane.md`, status
`Done`, `completed_at: 2026-07-28 18:03`) shipped four files:

- `tests/run_all_python_tests.sh` (unset PYTHONPATH instead of seeding it)
- `tests/lib/import_isolated.py`
- `tests/test_python_bootstrap_isolation.sh`
- `tests/test_runner_python_isolation.sh`

Their content was swept into commit `e22bdc582` ("refactor: Promote
stats_data.py from stats/ to lib/ (t1235)") by a concurrent session's
index-wide commit. Commit `442dbc42c` was then landed as an empty traceability
marker whose message states the content is in `e22bdc582` and deliberately
leaves that commit unrewritten.

`e22bdc582` was subsequently rewritten anyway into `eb1a4f7ea` (same t1235
subject, currently on main) with **all four t1236 paths dropped**. Verified:

```bash
git merge-base --is-ancestor e22bdc582 HEAD   # -> not an ancestor
git show --stat eb1a4f7ea | grep -c isolation # -> 0
```

Net effect on `main`:

- `tests/run_all_python_tests.sh` still seeds `PYTHONPATH` with `board/` and
  `lib/` — the exact masking t1236 was created to make structurally impossible.
- The three new test/helper files do not exist in history at all.
- t1236 and its plan `aiplans/archived/p1236_*.md` are archived as complete, and
  the changelog / issue-update tooling will match on `(t1236)` and report it as
  shipped.

The working-tree copies are byte-identical to `e22bdc582`'s blobs (verified with
`diff <(git show e22bdc582:<path>) <path>` for all four — no output). They are
uncommitted and therefore one `git stash` or `git checkout --` away from being
lost for good; this checkout has already lost in-flight edits to a concurrent
session's stash once.

No committed file references the missing helpers (`git grep import_isolated
HEAD` is empty), so HEAD is self-consistent — the isolation lane is simply
absent, silently.

## Coordination risk (read before touching the runner)

`aitasks/t1179_python_test_runner_masks_failures.md` is status `Implementing`
and its upstream defect is `tests/run_all_python_tests.sh:22-26` — the same
file. t1179 targets the *summary/exit-code* masking (prints
"Results: 25 passed, 0 failed" while the unittest phase reports FAILED);
t1236 targets the *PYTHONPATH* masking. They are complementary, but a
concurrent session may be editing the file right now.

Before staging anything: re-read the live `tests/run_all_python_tests.sh`, check
`git diff --cached` for foreign staged hunks, and stage the four paths
explicitly (never `git add -A`). If the file has drifted, re-apply t1236's
change (`unset PYTHONPATH` + its comment) on top of the current content rather
than restoring the old blob wholesale.

## Stray uncommitted files (triage, decide disposition for each)

| Path | Finding | Suggested disposition |
|------|---------|----------------------|
| `.antigravitycli/823d4920-*.json` | Antigravity CLI workspace-state file (records the repo folder URI + write permission). Tool-generated, no owning task, **not** matched by any `.gitignore` rule. | Add `.antigravitycli/` to `.gitignore` |
| `.opencode/package-lock.json` | npm lock generated under `.opencode/`, dated 2026-07-19, no owning task. `.gitignore` currently only has `.opencode/skills/*-/` rules. | Confirm it is generated, then ignore it |
| `aidocs/slack/pros_and_cons.md` | Hand-written notes weighing "claude tag" / Slack integration. No owning task. Note `aidocs/chat/` is the established home for chat-platform docs. | Ask the author: commit (probably relocated under `aidocs/chat/`) or drop |
| `.claude/settings.local.json` | Six added permission entries (a WebFetch domain, `./ait projects *`, some `Read(//home/ddt/...)` globs). Routine local drift, no task association. | Commit as `ait:` housekeeping or leave uncommitted — author's call |

## Acceptance criteria

- [ ] The four t1236 paths are committed to `main` with a message tagged
      `(t1236)`, and the commit body records that this restores content dropped
      by the `e22bdc582` -> `eb1a4f7ea` rewrite.
- [ ] `git show HEAD --stat` lists all four paths; `git status --porcelain` no
      longer reports them.
- [ ] `bash tests/test_python_bootstrap_isolation.sh` and
      `bash tests/test_runner_python_isolation.sh` pass from a clean
      environment, and `bash tests/run_all_python_tests.sh` still passes with
      the restored `unset PYTHONPATH`.
- [ ] Negative control: with `PYTHONPATH` exported by the caller, the runner
      still scrubs it (prove the restored guard actually discriminates, rather
      than passing because something else is doing the work).
- [ ] t1179's in-flight change to the same file is not clobbered — verify the
      staged content, not just the path.
- [ ] Each stray path in the triage table has an explicit disposition applied
      (ignored, committed, relocated, or deleted); none is left silently
      untracked.
- [ ] `.gitignore` additions are verified with `git check-ignore -v <path>`.

## Out of scope

- Rewriting or reverting `eb1a4f7ea`. The history is shared and another session
  was active on it; restore forward with a new commit.
- t1179's own fix (exit-code / summary masking) — that task owns it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T15:43:29Z status=pass attempt=1 type=human
