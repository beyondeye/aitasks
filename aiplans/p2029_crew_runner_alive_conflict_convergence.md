---
Task: t2029_crew_runner_alive_conflict_convergence.md
Base branch: main
Output branch: main
---

# t2029 — Converge a conflicted runner pull on `_runner_alive.yaml`

## Context

After t2018 (ab2cf4b37), `git_pull` in `.aitask-scripts/agentcrew/agentcrew_utils.py`
merges a diverged crew branch only when `git merge-tree --write-tree` proves the
merge clean in memory (`_merge_diverged`, line ~433). When merge-tree exits 1, the
pull is deferred as `merge_conflict: <paths>` and nothing is written.

When the runner's own `_runner_alive.yaml` has edits on adjacent lines on both
sides since the merge base, git reports a conflict. For example, a runner restarted
with `interval: 60` (line 7) while a peer set `requested_action: stop` (line 8). The
pull then defers on every iteration, so the remote stop is never seen. The runner
owns this file and knows how its fields combine, so it can resolve the conflict
itself. The resolution is built entirely in memory and is never written to the
live worktree.

Constraints carried over from t2018: no merge opened and no conflict markers
written in the live crew worktree; no stash, rewrite or revert of another
process's file; `--no-autostash` stays; `_advance()` stays the only step that
writes the worktree.

Advisory notes (acknowledged): the test harness's `wrapped_git_cmd` must keep
forwarding `**kw`, and only `r.time` may be patched, never the global `time`.

## Implementation

### 1. `agentcrew_utils.py` — `git_cmd` gains `input=`

- Signature: `git_cmd(worktree, *args, check=True, timeout=None, input: str | None = None)`.
- In the unbounded branch, pass it on: `subprocess.run(cmd, capture_output=True, text=True, check=check, input=input)`.
- `input` together with `timeout` → `raise ValueError(...)`. Bounded calls are network operations and never need stdin, so this mix is rejected rather than silently dropped.
- Docstring: one line saying `input` feeds stdin to local plumbing (`hash-object`, `mktree`).

### 2. `agentcrew_utils.py` — field-wise resolution (new, beside `_merge_diverged`)

Constants:
```python
RUNNER_ALIVE_FILE = "_runner_alive.yaml"
# Fields the runner rewrites every iteration: on a two-sided change its own side wins.
_RUNNER_OWNED_FIELDS = frozenset({"status", "pid", "hostname", "started_at",
                                  "last_heartbeat", "next_check_at", "interval"})
_ABSENT = object()
```

**`_merge_runner_alive_fields(base, ours, theirs) -> dict | None`** is a pure function over the union of keys. A missing key is `_ABSENT`, and a result of `_ABSENT` drops the key. The per-key policies are checked **in this order, and the field policies come before any generic three-way shortcut**:

1. **Runner-owned field** (`_RUNNER_OWNED_FIELDS`) → **ours, unconditionally**, including ours' absence. This holds even when only theirs changed it: base `running`, ours `running`, theirs `stopped` → `running`. These fields describe the live runner doing this merge. The runner rewrites them right after the pull anyway, and a peer's value for them is stale or belongs to another runner. The competing-runner case is caught earlier, by `runner_identity_guard` in the post-phase.
2. **`requested_action`**. Let a side "introduce" a stop when its value is `"stop"` and base's is not.
   - Either side introduced a stop → `"stop"`. A stop requested since the merge base is never lost on either side.
   - Otherwise, git's three-way rule: `ours == theirs` → that value; `ours == base` → theirs; `theirs == base` → ours. If both sides changed it to different values → theirs (the incoming value wins).
   - **Intentional exception, specified and tested:** base `stop`, ours `null`, theirs `stop` → `null`. A stop already in the merge base is history that this side has seen. A restarted runner clears it on purpose (`write_runner_alive` writes `requested_action: None` at start-up), and a *clean* merge of the same edits already gives `null`. Taking `stop` would make a conflicted pull undo the user's restart, so the conflicted and clean paths would disagree.
   - **Known limit, not recovered automatically.** A repeat stop written over an identical historical `stop` (the controller had not yet synced to the cleared `null`) makes no textual change. It cannot be told apart from history, so it resolves to `null`. Nothing brings it back later. The resolved merge already contains the peer's commit, so a later pull from that unchanged peer imports nothing, and pushing the merge spreads `null`. The repeat request is lost, and the operator must reissue it after the controller has synced to the cleared state. The docstring of `_merge_runner_alive_fields` and the doc paragraph (step 6) say this. Durable request identifiers would remove the ambiguity, but they are out of scope for this task.
3. **Any other key** → git's three-way rule. If both sides changed it to different values → `None`, which means unresolvable and keeps the deferral.

Key order is ours' keys, then any keys only theirs has. The output is dumped with `yaml.safe_dump(default_flow_style=False, sort_keys=False)`, the same dumper `write_yaml` uses.

**`_runner_alive_at(worktree, rev) -> dict | None`**:
- `git cat-file blob <rev>:_runner_alive.yaml`, then `yaml.safe_load`.
- Returns `None` on a git failure, a `yaml.YAMLError`, or content that is not a mapping.

**`_resolve_runner_alive(worktree, head, upstream, tree, conflicted) -> tuple[str, str]`** returns `(resolved_tree, "")` or `("", reason)`:
1. `conflicted != [RUNNER_ALIVE_FILE]` → `("", "")`. This is today's deferral, with the detail string unchanged.
2. Read ours (`head`) and theirs (`upstream`). Either is `None` → `("", "runner file unreadable on one side")`.
3. Base: `git merge-base head upstream`. If it fails, or the base has no file, use `{}`. A base file that exists but does not parse → unreadable reason.
4. Merge the fields. A `None` result → `("", "runner file fields conflict")`.
5. `hash-object -w --stdin` the dumped YAML, and validate the oid with `_OBJECT_ID`.
6. `ls-tree -z <tree>`, the tree merge-tree wrote with markers. Replace the single root entry `\t_runner_alive.yaml` with the same mode and `blob <new oid>`. If the entry is missing, appears more than once, or is not a blob, return a reason. Then `mktree -z` and validate the oid.

### 3. `_merge_diverged` — use it

```python
if proof.returncode == 1:
    conflicted = [p for p in lines[1:] if p]
    tree, why = _resolve_runner_alive(worktree, head, upstream,
                                      lines[0].strip() if lines else "", conflicted)
    if not tree:
        return PULL_DEFERRED, ("merge_conflict: " + ", ".join(conflicted)
                               + (f" ({why})" if why else ""))
    resolved = f" (resolved {RUNNER_ALIVE_FILE})"
elif proof.returncode == 129: ...unchanged...
else: ...existing tree validation..., resolved = ""
```
- Signing (`_sign_args`), `commit-tree -p head -p upstream`, and `_advance()` are unchanged.
- The commit message and the outcome detail gain the `resolved` suffix.
- Update the docstrings of `_merge_diverged` and `git_pull` (the conflict paragraph): a conflict confined to `_runner_alive.yaml` is resolved field-wise in memory; any other conflict, or an unresolvable runner file, still defers.

### 4. Test harness (`tests/test_crew_pull_no_autostash.sh`)

- Add `ap.add_argument("--interval", type=int, default=30)` and pass `args.interval` to `r.run_loop(...)` (the value is currently hard-coded to 30). Update the harness usage docstring.
- Fixture: new `peer_change` value `runner_stop_and_agent`. One peer commit applies both the `runner_stop` and the `agent_conflict` edits.
- Fixture: new `peer_change` value `runner_stop_wide`. One peer commit applies the `runner_stop` edit and also adds `peer_only.txt`, an unrelated incoming change.
- Fixture: an optional second argument `nested` to `setup_crew_remote_fixture`. It commits `nested/dir/keep.txt` in the worktree before the `runner: started` commit, so the file sits in the merge base as a subtree. It is opt-in, so no other cell's fixture changes.
- Header comment: mention cells 16–17 (t2029).

### 5. New test cells (each gated by `need_merge_tree`, like 6/8/9)

**16a — the pull converges a runner-file conflict (pull level) and preserves the rest of the tree**
- Fixture `runner_stop_wide nested`.
- Local side, in one commit: `interval: 60` in `_runner_alive.yaml`, plus a new `local_only.txt`.
- Control: `git merge-tree --write-tree --name-only HEAD $PEER_SHA` exits 1 and names only `_runner_alive.yaml`. This proves it is a real conflict, so the cell is not vacuous. Keep its tree oid as `conflicted_tree`.
- **Tree preservation**, checked after the pull:
  - `git ls-tree -r HEAD`, with the `_runner_alive.yaml` line removed, must equal `git ls-tree -r $conflicted_tree` with the same line removed. Every other path, mode and blob must match git's own merge exactly.
  - `HEAD:nested/dir/keep.txt` must equal the merge base's blob.
  - `HEAD:peer_only.txt` (incoming) and `HEAD:local_only.txt` (local) must both exist.
- `run_pull`:
  - The output contains `PULL_RESULT:ok|merged` and `resolved _runner_alive.yaml`.
  - HEAD is a two-parent merge: `HEAD^1` is the commit before the pull, and `HEAD^2` is `PEER_SHA`.
  - `HEAD:_runner_alive.yaml` contains `interval: 60` and `requested_action: stop`, and no `<<<<<<<`.
  - The worktree file matches HEAD.
  - No MERGE_HEAD, no `ls-files -u` entries, and an empty stash list.

**16b — the running runner honours the stop through the conflict (end to end)**
- Fixture `runner_stop`, a dirty agent heartbeat, and `run_runner --once --interval 60`. Its own "runner: started" commit writes `interval: 60` next to the peer's line.
- Assertions:
  - rc 0, `SHUTDOWN:complete`, and no `LAUNCH_STUB:`.
  - `PEER_SHA` is an ancestor of HEAD, and the remote head equals HEAD (the push converged).
  - The merge commit `m=$(git rev-list --merges -n1 HEAD)`:
    - its `_runner_alive.yaml` carries `interval: 60` and `requested_action: stop`;
    - `merge-tree --write-tree $m^1 $m^2` exits 1, so it really was a conflict;
    - its subject contains `resolved _runner_alive.yaml`.
  - HEAD's runner file says `status: stopped`.
  - No MERGE_HEAD, and the stash is empty.
  - The agent's file bytes and identity are unchanged.

**16c — anything else still defers, touching nothing**
- **(i) A second conflicted path.** Fixture `runner_stop_and_agent`. One local commit sets `interval: 60` and w1's `last_heartbeat`. Expect `PULL_RESULT:deferred|merge_conflict:` naming both files with no "resolved" text, an unchanged HEAD, no MERGE_HEAD, and no unmerged entries.
- **(ii) An unparseable local side.** Fixture `runner_stop`. A local commit puts `interval: [60` on line 7. Expect `deferred|merge_conflict: _runner_alive.yaml (runner file unreadable on one side)`, an unchanged HEAD, no MERGE_HEAD, and worktree file bytes unchanged.

**17 — the field-merge table (pure function)**
An inline `"$AITASK_PYTHON" -c` imports `agentcrew.agentcrew_utils` and prints one `case|result` line per case. The expected table is asserted in full.

Precedence rows (each checks that a field policy runs before the generic shortcut):
- `status`: base `running`, ours `running`, theirs `stopped` → `running` (only theirs changed; ours still wins).
- `hostname` changed only on theirs → ours' value.
- An owned field absent on ours and present on theirs → dropped (ours verbatim).
- `interval`: both changed → ours.

`requested_action` rows:
- base `null`, ours `null`, theirs `stop` → `stop`.
- base `null`, ours `stop`, theirs `null` → `stop`.
- add/add (no base), ours `stop`, theirs `null` → `stop`.
- **Exception:** base `stop`, ours `null`, theirs `stop` → `null` (a historical stop cleared by a restart).
- base `stop`, ours `stop`, theirs `null` → `null` (theirs cleared it).
- base `null`, ours `hold`, theirs `wait` → `wait` (no new stop; incoming wins).

Other-key rows:
- only theirs changed an unknown key → theirs;
- both changed an unknown key differently → `None`;
- an unknown key deleted on one side and unchanged on the other → dropped.

### 6. Doc

`aidocs/agentcrew/agentcrew_architecture.md`, in the paragraph at ~line 236, add after "proves the merge clean in memory": a conflict confined to `_runner_alive.yaml` is resolved in memory, field by field. The runner's own identity and heartbeat fields are always kept. A stop that either side requested since the last common commit wins. A stop already in that commit can be cleared by a restarted runner, exactly as a clean merge would clear it. A repeat stop sent before the controller saw that clearing cannot be told apart from the old one and is lost, so it must be reissued after the controller syncs. Otherwise, the incoming `requested_action` wins. The result is committed and advanced the same way. A conflict where the peer side names a different runner (`hostname`/`pid`) still defers, and so does any other conflict.

### Post-phase (risk mitigations)

1. [runner_identity_guard] **Defer when the two sides name competing runners.**
   - Add a pure `_competing_runner_identity(base, ours, theirs) -> bool` in `agentcrew_utils.py`. The identity is the pair `(hostname, pid)`; a missing key counts as `_ABSENT`.
   - It returns True when **theirs' identity differs from base's and from ours'**. That means the peer side rewrote the runner identity to some runner other than this one: a takeover, or a second runner. It covers both cases, whether or not ours also changed its own identity. Without the guard, policy 1 would silently overwrite the other runner's claim with ours.
   - In `_resolve_runner_alive`, check this after reading the three sides and before merging the fields. On True, return `("", "competing runner identities: <theirs host>/<theirs pid> vs <ours host>/<ours pid>")`. The pull defers exactly as it does today, so this task makes no takeover decision of its own.
   - Ordinary conflicts still converge: a heartbeat/interval rewrite against a remote stop changes only `requested_action` on the peer side, and the peer's identity equals base. Cells 16a and 16b keep proving that.
   - **Regression tests:**
     - **16d.** New fixture `peer_change` value `runner_takeover`: the peer rewrites `pid: 9999`, `hostname: otherhost`, `last_heartbeat` and `next_check_at` (lines 2–6). Locally, `local_commit ... interval: 60` (line 7, next to line 6, so it is a real conflict, proven by the same merge-tree control as 16a). `run_pull` must give `deferred|merge_conflict: _runner_alive.yaml (competing runner identities: otherhost/9999 vs crewhost/4242)`, with HEAD unchanged, no MERGE_HEAD, and worktree bytes unchanged.
     - **Cell 17's table** gains these rows: takeover → True; both identities unchanged → False; ours restarted (new pid) with theirs equal to base → False; add/add with equal identities → False.

### Post-implementation
Step 9 of the task workflow: commit the code, then archive the task and plan.
Step 8d creates the spawned "after" mitigation.

## Verification

1. `bash tests/test_crew_pull_no_autostash.sh` passes everything, including cells 16a–17.
2. **Red proof in an isolated copy, without stash or restore:**
   - Extract the tree with `git archive HEAD | tar -x -C <scratchpad>/red`.
   - Copy in only the new test file.
   - Run it there. Cells 16a and 16b must fail (deferred / no `SHUTDOWN:complete`), and 17 must fail on import. The other cells must still pass.
3. Run the other tests that use the crew git helpers: `bash tests/test_crew_*.sh` (those matching `git_cmd`/`git_pull` via grep), and `bash tests/run_all_python_tests.sh --test-dir` on any Python crew tests. Check the verdict on the last line.
4. **Guard mutant**, in the scratch copy only: make `_competing_runner_identity` return False. Cell 16d must then fail, because the pull converges, while 16a and 16b still pass. This shows that 16d is a signal specific to the guard.
5. **Precedence mutant**, in the scratch copy only: move the generic three-way shortcut ahead of policies 1 and 2. The `status`/`hostname` precedence rows in cell 17 must then fail.
6. **Tree-rebuild mutant**, in the scratch copy only: drop the first non-runner `ls-tree` entry before `mktree`. The 16a tree-preservation assertion must then fail.
7. `shellcheck tests/test_crew_pull_no_autostash.sh` reports nothing new compared with HEAD.

## Risk

### Code-health risk: low
- `git_cmd` is shared by every crew helper. The new `input=` keyword is additive and defaults to the old behaviour, and the harness forwards `**kw` · severity: low · → mitigation: none
- A new write path (a synthesized merge commit) can now advance the worktree after a conflict. It is limited to one root-level file, built with plumbing only, and goes through the same `_advance()` and signing gates · severity: low · → mitigation: none

### Goal-achievement risk: low
- Takeover duel: the runner's own identity fields win a two-sided change. If a peer runner on another host took over (rewrote `hostname`/`pid`), this runner would overwrite that claim, and both might keep running. This rule is specified by the task, and the situation already exists today on clean merges · severity: low (residual — the automatic resolution now defers on competing identities via inline post-phase runner_identity_guard; detecting and yielding on a duel that a *clean* merge produces is left to crew_runner_takeover_duel_detection) · → mitigation: inline post-phase runner_identity_guard; crew_runner_takeover_duel_detection
- The convergence needs `_runner_alive.yaml` to be clean at the pull, as with t2018's ordering. When it is dirty (cell 7), `_advance` still refuses, as intended · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: runner_identity_guard | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: takeover duel (goal-achievement) | desc: Defer the field-wise resolution when the peer side carries a runner identity (hostname/pid) that differs from both the base and ours; regression cell 16d plus rows in table 17
- timing: after | name: crew_runner_takeover_duel_detection | type: enhancement | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: takeover duel (goal-achievement) | desc: Full takeover detection and a safe yield: when a pull (clean or conflicted) shows another live runner owns _runner_alive.yaml, log it and yield or hold rather than overwrite, and report the deferred competing-identity case to the operator | created: t2115

## Post-Review Changes

### Change Request 1 (2026-10-21 12:40)
- **Requested by user:** (1) the tree rebuild read `ls-tree -z` and fed `mktree` through text-mode `git_cmd`, so a root name containing a CR was rewritten with a LF, and a non-UTF-8 name raised `UnicodeDecodeError`; (2) `_runner_alive_at` let an incoming blob's invalid UTF-8 (`UnicodeDecodeError`) or unconstructible timestamp (`ValueError`, e.g. `2026-99-99 10:00:00`) escape and end the runner instead of deferring.
- **Changes made:** `git_cmd` gains `text=` (default True; `text=False` exchanges raw bytes and, like `input=`, is refused with `timeout`). The `ls-tree -z` → `mktree -z` surgery is bytes end to end. `_runner_alive_at` reads the blob as bytes, decodes it inside the `try`, and treats `yaml.YAMLError` / `ValueError` (which includes `UnicodeDecodeError`) / `RecursionError` as an unreadable side. Tests: 16a's local commit adds `$'cr\rname.txt'` and `$'latin\xe9.txt'`, with byte-exact presence checks, a no-LF-twin check, and controls showing that git's own merge carries both names. New peer fixtures `runner_stop_bad_utf8` / `runner_stop_bad_timestamp` drive 16c(bad_utf8) and 16c(bad_timestamp), which must defer with HEAD, the worktree bytes and the merge state all unchanged.
- **Red proof:** the pre-fix resolver, built in an isolated `git archive` copy, fails 16a with a traceback and both new 16c cells. A variant without the non-UTF-8 name isolates the CR defect: the CR name goes missing and an LF twin appears.
- **Files affected:** `.aitask-scripts/agentcrew/agentcrew_utils.py`, `tests/test_crew_pull_no_autostash.sh`

### Change Request 2 (2026-10-21 12:55)
- **Requested by user:** a self-referencing YAML value (`note: &n {self: *n}`) parses, but each side loads its own copy, so `_three_way`'s `==` raised `RecursionError` after parsing. The `RecursionError` handler covered parsing only.
- **Changes made:** `_runner_alive_at` now accepts only a flat mapping of `str` keys to scalars (`_RUNNER_SCALARS`: str, int, float, bool, date/datetime, None). A list, a nested mapping or a cyclic value is an unreadable side, so the pull defers. The runner never writes non-scalar fields, so nothing legitimate is refused. The check sits at the reader boundary: the pure merge function documents that its inputs are flat scalar mappings, and still recurses if given a cyclic value directly. New fixture layout `cyclic_note` appends the value to the base runner file. New cell 16c(cyclic) (interval-vs-stop conflict) asserts a deferral with HEAD, the worktree bytes and the merge state unchanged.
- **Red proof:** the pre-fix snapshot, run in an isolated copy, fails 16c(cyclic) with no `PULL_RESULT` line; a direct call confirmed the cause is `RecursionError`. The fixed code passes 299/0.
- **Files affected:** `.aitask-scripts/agentcrew/agentcrew_utils.py`, `tests/test_crew_pull_no_autostash.sh`

## Final Implementation Notes
- **Actual work done:** `git_pull` now converges a diverged crew branch whose only conflicted path is `_runner_alive.yaml`. `_resolve_runner_alive` (in `.aitask-scripts/agentcrew/agentcrew_utils.py`) reads base, ours and theirs as flat scalar mappings, checks the competing-identity guard, merges the fields by the specified precedence, writes the blob, and rebuilds merge-tree's conflicted tree in raw bytes (`ls-tree -z` → `mktree -z`). `_merge_diverged` then signs, commits (`(resolved _runner_alive.yaml)` in the message and the outcome detail) and advances through the unchanged `_advance()`. Any other conflict keeps its exact old deferral text. An unresolvable runner file defers with a parenthesised reason. `git_cmd` gained `input=` and `text=`; both are refused with `timeout=`. Tests: cells 16a–16d and 17, the harness `--interval` option, 6 new peer fixtures, and the `nested` / `cyclic_note` base layouts. Doc: one paragraph in `aidocs/agentcrew/agentcrew_architecture.md`.
- **Deviations from plan:** All three came from post-review requests (see Change Requests 1–2): the byte-exact tree rebuild (`text=False`); the blob reader catching decode and construct errors; and the reader's flat-scalar schema, which rejects cyclic or nested values. Reasons are worded as planned, plus three plumbing reasons (blob not written, merge tree unreadable, merged tree not built).
- **Issues encountered:** The harness's `--interval` was needed for 16b: with interval 30, the runner's start-up rewrite leaves line 7 equal to the base, and the merge stays clean (that is Test 6). The red proofs ran in isolated `git archive` copies, never in the shared worktree. In the first pre-fix probe the non-UTF-8 name crashed before the CR mangling could show, so a variant without it isolated the CR defect.
- **Key decisions:** Policies are ordered: runner-owned fields take ours unconditionally; then `requested_action`, where a stop introduced since the merge base wins; then git's three-way rule. The historical-stop exception (base stop, ours null, theirs stop → null) matches what a clean merge does, so a restarted runner is not undone. A repeat stop over an identical historical stop is documented as lost and must be reissued. The identity guard is placed at the reader/resolver boundary and defers rather than deciding a takeover; fuller takeover handling is the spawned "after" mitigation `crew_runner_takeover_duel_detection`. The cyclic-value guard sits at the reader, not in the pure merge function, whose docstring states the input contract.
- **Upstream defects identified:**
  - `.aitask-scripts/agentcrew/agentcrew_utils.py:623` — `_merge_diverged` runs `merge-tree --name-only` through text-mode `git_cmd`. Under `core.quotePath=false`, a conflict on a non-UTF-8 path prints raw bytes, and decoding them raises `UnicodeDecodeError` out of `git_pull`, ending the runner. Verified in a scratch repo: quotePath=true prints `"f\351.txt"`; quotePath=false prints `f\xe9.txt` and the decode fails. This dates from t2018 and was not introduced here.
