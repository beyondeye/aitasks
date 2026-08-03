---
Task: t1378_fix_list_locks_pipefail_abort_on_empty_branch.md
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# t1378 — Fix `list_locks()` pipefail aborts

## Context

`.aitask-scripts/aitask_lock.sh` runs under `set -euo pipefail`. Inside
`list_locks()` two pipelines route through `grep`, which exits 1 when it matches
nothing. Under `pipefail` that exit status propagates out of the command
substitution and `set -e` kills the script — **before** the guard on the next
line can handle the empty case. `--list` then exits 1 having printed nothing.

Both instances were reproduced live during planning:

1. **Empty lock branch** (`aitask_lock.sh:362`) — the defect t1378 was filed for.
   ```bash
   lock_files=$(git ls-tree "$current_tree_hash" | grep '_lock\.yaml' | awk '{print $4}')
   ```
   On a lock branch holding no locks `git ls-tree` prints nothing → `grep` exits
   1 → abort. The `if [[ -z "$lock_files" ]]` guard on line 364 that would print
   "No active locks" and `return 0` is never reached. Verified: the old form
   exits 1 without reaching the guard; the `awk` form exits 0 and prints the
   message. This is the ordinary state of any project where nothing is locked.

2. **Malformed / stray lock file** (`aitask_lock.sh:372-375`) — the same class,
   ten lines below, found while scoping instance 1 and confirmed with the user.
   ```bash
   tid=$(echo "$content" | grep '^task_id:' | sed 's/task_id: *//')   # ×4: task_id, locked_by, locked_at, hostname
   ```
   One lock file missing any of those four keys exits 1 → aborts the **whole**
   listing, so every other lock disappears too. `tests/test_task_lock.sh` Test
   12i already constructs exactly this fixture (a stray `notalock_lock.yaml`) for
   the `--cleanup` path.

**Why it matters beyond the CLI:** `aitask_board.py:1160` `refresh_lock_map()`
gates on `result.returncode == 0`. A nonzero `--list` makes the board silently
drop its entire lock map — no error, locks just stop showing.

t1370 fixed this exact class in `cleanup_locks()` in the same file (both its
instances), structurally rather than with `|| true`. This task mirrors that fix
in `list_locks()`. The repo-wide sweep of other scripts stays with the `after`
audit task t1370 confirmed.

## Incomplete-record policy (decided)

Removing the abort raises a question the abort used to mask: what should `--list`
print for a lock file that parses but is **missing a field**? Measured against
the board's real parser
(`^t(\S+): locked by (.+?) on (.+?) since (.+)$`, `aitask_board.py:1160`):

| emitted line | board |
|---|---|
| `t5: locked by alice@test.com on myhost since 2026-08-03 10:59` | MATCH |
| `t5: locked by alice@test.com on ␣ since 2026-08-03 10:59` (hostname empty) | **NO MATCH — lock silently dropped** |
| `t5: locked by ␣ on myhost since …` (locked_by empty) | **NO MATCH** |
| `t5: locked by alice@test.com on myhost since ␣` (locked_at empty) | **NO MATCH** |
| `t5: locked by alice@test.com on unknown since unknown` | MATCH |

The `(.+?)` groups are non-empty, so naively emitting empty fields would trade a
loud whole-listing abort for a **silent per-lock omission** — the same failure
class this task exists to remove, just narrower. Policy:

- **`task_id` is required.** Without it there is no lock to report: `debug`-log
  and skip the record (mirrors `cleanup_locks()`:462-467, same wording).
- **`locked_by` / `locked_at` / `hostname` default to `unknown`.** The lock stays
  visible to both the human and the board, and the missing data is legible.
  This is not a new convention — `lock_task()` already does exactly this at
  `aitask_lock.sh:166` (`[[ -z "$locked_hostname" ]] && locked_hostname="unknown"`).

Rationale: `lock_task()` writes all four fields unconditionally
(`aitask_lock.sh:210-215`), so a missing secondary field means a corrupt or
truncated lock file. For an **advisory** lock the safe failure mode is to *show*
it — hiding a lock that is actually held is what causes two agents to collide.

## Implementation

### 1. `.aitask-scripts/aitask_lock.sh` — add a field-extraction helper

Add above `list_locks()`:

```bash
# Extract a `key: value` field from lock-file YAML. Prints the value (empty when
# the key is absent) and always exits 0. A `grep '^key:'` pipeline would exit 1
# on a missing key and, under `set -euo pipefail`, abort the whole listing — the
# same class t1370 removed from cleanup_locks().
#   $1 = key, $2 = lock file content
_lock_field() {
    printf '%s\n' "$2" | awk -v k="^$1:" '$0 ~ k { sub(/^[^:]*: */, ""); print; exit }'
}
```

`$0 ~ "^task_id:"` keeps the original `grep` anchoring exactly (a leading-space
line does not match, as before); `sub(/^[^:]*: */, "")` reproduces
`sed 's/task_id: *//'` — `[^:]*` cannot cross the first colon, so a value
containing colons or spaces (`locked_at: 2026-08-03 10:59:00`) survives intact.

### 2. `.aitask-scripts/aitask_lock.sh:362` — drop `grep` from the listing

```bash
    local lock_files
    # awk, not grep: an empty lock branch makes `grep` exit 1, which under
    # `set -euo pipefail` kills --list before the emptiness guard below.
    lock_files=$(git ls-tree "$current_tree_hash" | awk '$4 ~ /_lock\.yaml$/ {print $4}')
```

Identical in form to the already-landed `cleanup_locks()` fix at line 452.

### 3. `.aitask-scripts/aitask_lock.sh:369-377` — rewrite the loop body

```bash
    while IFS= read -r lf; do
        local content tid lby lat lhost
        content=$(git show "origin/$BRANCH:$lf" 2>/dev/null)

        # task_id identifies the record — without it there is no lock to report.
        tid=$(_lock_field task_id "$content")
        if [[ -z "$tid" ]]; then
            debug "Skipping unrecognized lock file: $lf"
            continue
        fi

        # A corrupt lock file must still be REPORTED, not silently dropped: the
        # board's parser (aitask_board.py refresh_lock_map) requires non-empty
        # fields, so an empty value would make it discard this lock entirely.
        # "unknown" matches the placeholder lock_task() already uses (line 166).
        lby=$(_lock_field locked_by "$content");  lby="${lby:-unknown}"
        lat=$(_lock_field locked_at "$content");  lat="${lat:-unknown}"
        lhost=$(_lock_field hostname "$content"); lhost="${lhost:-unknown}"

        echo "t${tid}: locked by $lby on $lhost since $lat"
    done <<< "$lock_files"
```

Output format is unchanged for well-formed locks, so the board regex still
matches; the placeholders keep it matching for malformed ones too.

**Deliberate behavior change:** a lock file with no `task_id:` is now dropped
from the listing instead of aborting it. Strictly better than the status quo —
the abort dropped that entry *and every other lock* — but it is a choice, not a
no-op, so it is named here, in the Risk section, and pinned by Test 13c.

### 4. `tests/test_task_lock.sh` — three regression tests

Insert after Test 13, numbered 13b/13c/13d so existing numbering is untouched.
All reuse `setup_paired_repos`; 13c/13d reuse Test 12i's tree-surgery pattern
(`git hash-object -w` → `git mktree` → `git commit-tree` → push) to plant a
hand-built lock blob. Add a shared comment block above them in the style of the
Test 12b-12h header, recording that these pin the same `set -euo pipefail` class
as 12b/12i but on the `--list` path.

Shared helper for 13c/13d — plant a lock blob with arbitrary content:

```bash
# Push $3 as lock file $2 onto the lock branch in repo $1 (tree surgery, as 12i).
plant_lock_blob() {
    local dir="$1" name="$2" body="$3"
    (
        cd "$dir"
        git fetch origin aitask-locks --quiet 2>/dev/null
        blob=$(printf '%s\n' "$body" | git hash-object -w --stdin)
        tree=$( { git ls-tree "$(git rev-parse origin/aitask-locks^{tree})"
                  printf '100644 blob %s\t%s\n' "$blob" "$name"; } | git mktree )
        commit=$(echo "plant $name" | git commit-tree "$tree" -p "$(git rev-parse origin/aitask-locks)")
        git push --quiet origin "$commit:refs/heads/aitask-locks" 2>/dev/null
    )
}
```

- **Test 13b — empty lock branch.** Fixture: `setup_paired_repos` + `--init`, no
  locks. Assert `--list` exits 0 (`assert_exit_zero`) and stdout contains
  `No active locks` (`info` writes to stdout). This is the case Test 13 never
  covered — it always locks two tasks first. **Pins mutation NC1.**
- **Test 13c — stray file with no `task_id`.** Fixture: `--init`, lock task 1,
  then `plant_lock_blob … notalock_lock.yaml 'junk'`. Assert exit 0 and that the
  listing still contains `t1:`. **Pins mutation NC2** (the `task_id` extraction).
- **Test 13d — incomplete-record matrix.** The policy applies **independently** to
  `locked_by`, `locked_at` and `hostname`, so all three must be covered: pinning
  only one would let the other two `:-unknown` defaults be deleted with the suite
  still green, silently dropping those locks at the board. Fixture: `--init`, then
  `plant_lock_blob` four hand-built lock files onto one branch, each omitting a
  different field (plus one omitting all three), and a fifth complete lock as the
  positive control. **One** `--list` call, then assert every row.

  Rows are asserted by **exact full-line equality** — the timestamps are authored
  by the fixture, not generated, so the expected output is deterministic. Exact
  equality (not `contains`) is what pins the placeholder to the *correct slot*:
  a default applied to the wrong variable would still contain `unknown`.

  ```bash
  board_re=$(sed -n "s/^ *r'\(\^t(.*\)',\$/\1/p" "$PROJECT_DIR/.aitask-scripts/board/aitask_board.py")
  assert_exit_zero "board lock regex located in aitask_board.py" test -n "$board_re"

  while IFS='|' read -r id expected; do
      [[ -z "$id" ]] && continue
      line=$(printf '%s\n' "$list_out_13d" | grep "^${id}:")
      assert_eq "13d $id renders its missing field(s) as unknown" "$expected" "$line"
      assert_exit_zero "13d $id still matches the board parser" \
          python3 -c 'import re,sys; sys.exit(0 if re.match(sys.argv[1], sys.argv[2].strip()) else 1)' \
          "$board_re" "$line"
  done <<'ROWS'
  t7|t7: locked by alice@test.com on unknown since 2026-08-03 10:59
  t8|t8: locked by unknown on box8 since 2026-08-03 10:59
  t9|t9: locked by carol@test.com on box9 since unknown
  t10|t10: locked by unknown on unknown since unknown
  t11|t11: locked by dave@test.com on box11 since 2026-08-03 11:00
  ROWS
  ```

  | lock file | omits | expected line |
  |---|---|---|
  | `t7_lock.yaml`  | `hostname`  | `t7: locked by alice@test.com on unknown since 2026-08-03 10:59` |
  | `t8_lock.yaml`  | `locked_by` | `t8: locked by unknown on box8 since 2026-08-03 10:59` |
  | `t9_lock.yaml`  | `locked_at` | `t9: locked by carol@test.com on box9 since unknown` |
  | `t10_lock.yaml` | all three   | `t10: locked by unknown on unknown since unknown` |
  | `t11_lock.yaml` | nothing (control, incl. `pid`/`pid_starttime`) | `t11: locked by dave@test.com on box11 since 2026-08-03 11:00` |

  Also assert `--list` exits 0 for the whole call. All five rows were rendered
  through the proposed `_lock_field` + defaults during planning and checked
  against the extracted board regex: every one MATCHes, and the space-containing
  `locked_at` value survives `awk` intact. **Pins mutations NC3-NC6.**

  Reading the regex from `aitask_board.py` makes this an assertion about the real
  consumer contract rather than a string invented by the test, and the non-empty
  guard fails loudly if the board source moves. (Helpers verified present in
  `tests/lib/asserts.sh`: `assert_exit_zero` takes `desc` then a varargs command;
  there is no `assert_not_eq`, hence `test -n`. `python3 -c` is already used by
  several bash tests, e.g. `tests/test_python_resolve.sh`. The test file runs
  under `set +e` from line 86, so the in-loop `grep` needs no `|| true`.)

## Verification

```bash
bash tests/test_task_lock.sh                       # full lock suite, expect 0 FAIL
shellcheck .aitask-scripts/aitask_lock.sh          # clean
bash -n .aitask-scripts/aitask_lock.sh             # also pinned by Test 14
./ait lock --list; echo "exit=$?"                  # live repo: exits 0
```

### Negative controls — one mutation per test, each naming its expected failure

Restore by **inverse edit**, never `git checkout` (which would revert concurrent
work in this shared checkout). After each: re-run the suite, confirm it exits 1,
and confirm **the named assertion** is the one that failed — a failure elsewhere
means the control proved nothing.

| # | mutation | must fail | must stay green |
|---|---|---|---|
| NC1 | restore `\| grep '_lock\.yaml' \|` at line 362 | 13b `--list on empty lock branch exits 0` | 13c, 13d |
| NC2 | restore `tid=$(echo "$content" \| grep '^task_id:' \| sed …)` | 13c `stray lock file does not abort --list` | 13b |
| NC3 | restore `lhost=$(echo "$content" \| grep '^hostname:' \| sed …)` | 13d `--list with incomplete lock records exits 0` (whole listing aborts) | 13b |
| NC4 | drop only `lhost="${lhost:-unknown}"` | 13d rows **t7** and **t10** | 13d rows t8, t9, t11 |
| NC5 | drop only `lby="${lby:-unknown}"` | 13d rows **t8** and **t10** | 13d rows t7, t9, t11 |
| NC6 | drop only `lat="${lat:-unknown}"` | 13d rows **t9** and **t10** | 13d rows t7, t8, t11 |

Notes on why each is needed:

- **NC2 must mutate the `task_id` extraction specifically.** 13c's fixture
  `continue`s before any secondary field is read, so restoring a
  `locked_by`/`locked_at`/`hostname` pipeline would leave 13c green and prove
  nothing. That is what NC3 covers.
- **NC3 vs NC4-NC6 fail for different reasons** — NC3 is the pipefail abort (the
  whole listing dies), NC4-NC6 are the silent board-side omission of one lock.
- **NC4-NC6 are three separate controls, one per default,** because the three
  defaults are independent. Each must be dropped on its own; the discriminating
  evidence is the **must stay green** column — a mutation that reddens rows it
  should not have touched means the fixture, not the fix, is doing the work. The
  compound `t10` row legitimately fails for all three (it omits all three fields).
- **`t11` (complete record) must stay green under every mutation.** If it ever
  reddens, the change broke the ordinary path.

Record all six negative-control outcomes, including the stayed-green rows, in the
plan's Final Implementation Notes.

## Upstream defect (record at Step 8b, do not fix here)

`lock_task()` has the same class at `aitask_lock.sh:162-165` — `locked_by`,
`locked_at` and `hostname` are extracted with unguarded `echo | grep | sed`
inside the "lock already exists" branch, so a corrupt lock file aborts the lock
attempt. Note the adjacent lines 172-173 already carry `|| true` guards for the
PID-anchor fields, so the omission at 162-165 looks accidental. Out of scope for
t1378 (`list_locks` only); belongs to the repo-wide audit t1370 confirmed.

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch to merge or clean up. Step 9 runs the
merge-approval gate against `main` (from the `Output branch:` header above), then
`./ait gates run 1378` for the declared `risk_evaluated` gate, then
`./.aitask-scripts/aitask_archive.sh 1378`.

## Risk

### Code-health risk: low

- Removing the abort exposes a previously-masked decision about incomplete lock
  records. Emitting empty fields would convert a loud whole-listing abort into a
  silent per-lock omission at the board (measured against the real parser, see
  the policy table). Resolved by the `unknown` placeholder — the same convention
  `lock_task()` already uses. The three defaults are **independent**, so each is
  pinned separately by a row of the Test 13d matrix and its own negative control
  (NC4/NC5/NC6); a single-field test would have left the other two deletable
  with the suite green · severity: low · → mitigation: none
- The loop-body rewrite changes behavior for a lock file missing `task_id:`, from
  "abort the entire listing" to "skip that entry and log at debug level". Strictly
  an improvement, and pinned by Test 13c, but a real semantic decision rather than
  a pure refactor · severity: low · → mitigation: none
- Blast radius is one function in one script with a single programmatic consumer
  (`aitask_board.py` `refresh_lock_map`), whose parsing regex is unaffected —
  and Test 13d now asserts that directly, reading the regex from the board source
  · severity: low · → mitigation: none

### Goal-achievement risk: low

- None identified. Both defects were reproduced live during planning, the
  replacement `awk` forms were verified to exit 0 and produce the same values, and
  the board-parser behavior for every incomplete-record shape was measured rather
  than assumed. The acceptance criteria (structural fix + empty-branch test +
  discriminating negative controls) are directly executable.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, no scope changes.
  - `.aitask-scripts/aitask_lock.sh` (+33/-5): added `_lock_field()` above
    `list_locks()`; replaced the `git ls-tree | grep | awk` listing with
    `git ls-tree | awk '$4 ~ /_lock\.yaml$/ {print $4}'`; rewrote the loop body
    to require `task_id` (skip + `debug` when absent) and default
    `locked_by`/`locked_at`/`hostname` to `unknown`.
  - `tests/test_task_lock.sh` (+121): `plant_lock_blob()` helper plus Tests
    13b (empty branch), 13c (stray non-lock file), 13d (five-row incomplete-record
    matrix). Existing test numbering untouched.

- **Deviations from plan:** None to the design. One mechanical adjustment during
  the negative-control run: NC1's mutation anchor had to include the
  `list_locks`-specific comment line, because t1370's `cleanup_locks` fix left a
  **byte-identical** `awk` line in the same file. A bare anchor matched twice and
  would have mutated both functions, confounding NC1 with the Test 12 cleanup
  assertions. Caught by an explicit uniqueness assertion in the control driver,
  not by inspection — worth keeping that assertion in any future control harness.

- **Issues encountered:**
  - While confirming the risk-gate preconditions I invoked
    `aitask_gate_risk.sh 1378 1 dryrun-check` as a read-only probe. It is not a
    dry-run verb: it appended a real `risk_evaluated pass` block to the ledger
    with the synthetic run id `dryrun-check`, pre-empting the Step-9 orchestrator
    record. Caught immediately; the entry was still uncommitted, so it was removed
    by a targeted inverse edit (not `git checkout` — a concurrent session shares
    this checkout) along with its `.aitask-gates/1378/` sidecar log, restoring
    `archive-ready` to `BLOCKED:risk_evaluated`. **Lesson: gate verifiers are
    ledger-mutating, never probes.** Use `aitask_gate.sh archive-ready` /
    `status` for inspection.
  - `Output branch:` in this plan's header reads `main` rather than being cleared
    by `--no-worktree`, because the header was hand-written into the plan before
    externalization. Harmless here: current-branch mode on `main` means base and
    output agree, which is what the planning convention prescribes anyway.

- **Key decisions:**
  - **Scope widened by one instance, with user confirmation.** t1378 named only
    line 362; `list_locks` held a second instance of the same class ten lines
    below (the four `echo | grep | sed` field extractions). Both were reproduced
    before asking. The repo-wide sweep of *other* scripts stays with t1370's audit.
  - **Incomplete records get `unknown` placeholders, not empty fields.** Measured
    against the board's real regex: every empty-field shape fails to match, so the
    naive fix would have converted a loud whole-listing abort into a *silent
    per-lock omission* — the same failure class, narrower. `unknown` reuses the
    convention `lock_task()` already applies at line 166.
  - **`task_id` is the only required field.** Without it there is no record to
    report; mirrors `cleanup_locks()`:462-467 including the `debug` wording.
  - **Test 13d reads the board's regex out of `aitask_board.py`** rather than
    copying it, so it pins the real consumer contract and fails loudly (via a
    `test -n` guard) if the board source moves.
  - **Rows asserted by exact full-line equality, not `contains`** — a default
    wired to the wrong variable would still contain the substring `unknown`.

- **Verification results:**
  - `bash tests/test_task_lock.sh` → 79 passed, 0 failed.
  - `shellcheck .aitask-scripts/aitask_lock.sh` → no new findings (pre-existing
    `SC1091` source-following and `SC2086` at line 493 in `cleanup_locks` remain).
  - `./ait lock --list` on the live repo → exit 0, all 9 locks rendered.
  - Negative controls (one mutation each, restored by inverse edit, suite back to
    79/79 afterwards). The "stayed green" column is the discrimination evidence:

    | # | mutation | failed | stayed green |
    |---|---|---|---|
    | NC1 | restore `grep` in the `ls-tree` listing | 13b (2 asserts) | 13c, 13d |
    | NC2 | restore `grep` for `task_id` | 13c (2 asserts) | 13b, 13d |
    | NC3 | restore `grep` for `hostname` | all of 13d (11 asserts — listing aborts) | 13b, 13c |
    | NC4 | drop `lhost="${lhost:-unknown}"` | 13d t7, t10 | 13d t8, t9, **t11** |
    | NC5 | drop `lby="${lby:-unknown}"` | 13d t8, t10 | 13d t7, t9, **t11** |
    | NC6 | drop `lat="${lat:-unknown}"` | 13d t9, t10 | 13d t7, t8, **t11** |

    NC4-NC6 each redden only their own row plus the compound `t10` row (which
    omits all three fields), confirming the three defaults are pinned
    independently. `t11` (complete record) stayed green under NC4-NC6 and failed
    only under NC3, which kills the entire listing — exactly as predicted.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_lock.sh:162-165` — `lock_task()` extracts `locked_by`,
    `locked_at` and `hostname` with unguarded `echo | grep | sed` inside its
    "lock already exists" branch, so a corrupt or truncated lock file aborts the
    lock attempt under `set -euo pipefail`. Same class as the two fixed here; the
    omission looks accidental because the adjacent lines 172-173 already carry
    `|| true` guards for the PID-anchor fields. Out of scope for t1378, which is
    scoped to `list_locks`.
