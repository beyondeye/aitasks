---
priority: high
effort: high
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-09-07 16:38
updated_at: 2026-09-07 16:38
---

## Context

Parent t1725, findings 1 (shell side), 2, 3, 4 / acceptance criteria 1 (wire) and 2.
Independent of t1725_1 and t1725_2 (`--no-sibling-dep`). t1725_4 (pane + prompt
state) and t1725_5 (TUI screen) build on the record this task defines.

Today `aitask_sync.sh`'s sweep resolves each dirty file to its owning task, checks
the lock holder's liveness and appends a prescriptive line per file to
`SKIP_REPORT` — then prints it on **stderr** (`report_skipped`) and emits only
`DEFERRED:protected_dirty:N file(s) held by other sessions` on stdout. Four
sub-reasons (`live_lock`, `unknown_liveness`, `ownerless`, `ambiguous_rename`, …)
collapse into that one token; "held by other sessions" is wrong when the holder is
the user's own pane; and an **untracked** file needlessly defers the whole rebase
(git rebase ignores an untracked path unless an incoming commit creates it).

**Related in-flight task — t1696** (holder dead, lock stale): fixes the recovery
*hint wording* that sends users to `./ait sync` for a recovery `ait sync` cannot
perform on a dirty shared worktree, and suggests "have `ait sync` run the converge
seam on its `protected_dirty` path". **This task implements that sync-side half**
(3c: fast-forward when `local_ahead == 0` and the dirty files are untouched by
incoming commits); t1696 keeps the hint-wording half. The parent session sent t1696
an `ait note` saying so.

## Key files

- `.aitask-scripts/aitask_sync.sh` — `batch_out` (~166), `_protect` (~279),
  `_pct_encode`/`_pct_decode` (~307/320), `_lock_snapshot` (~394, currently discards
  `lemail`), `_holder_verdict` (~424), `_sweep_dirty` (~599), `_commit_group` (~753),
  `report_skipped` (~856), `count_local_ahead`/`count_remote_ahead` (~888),
  `do_pull_rebase` (~998), `do_push` (~1152, the retry branch ~1190-1205), `main`
  (~1221, the gate at ~1269-1280), `show_help` (~66), the test seams
  `_sync_test_seam` (~246-277)
- `.aitask-scripts/lib/sync_action_runner.py` — `DEFERRED_REASONS`, `SyncResult`,
  `parse_sync_output`, `sync_batch_command` / `run_sync_batch`
- `.aitask-scripts/lib/task_utils.sh` — `get_user_email` (~1533),
  `task_data_converge` (~943, the ff-only rule this task mirrors)
- `tests/test_sync_deferral_and_quarantine.sh`, `tests/lib/sync_fixture.sh`
  (`setup_repo`, `plant_lock`, `lock_yaml_live <tid> [host] [pid]`, `lock_yaml_dead`,
  the `bin/hostname` shim driven by `TEST_HOSTNAME`), `tests/test_sync.sh`,
  `tests/test_sync_action_runner.py` (`_emitted_tokens` scan,
  `test_every_emitted_deferred_reason_is_declared`)
- `website/content/docs/commands/sync.md` is **not** this task's (t1725_6); only the
  inline `show_help` is updated here.

## Implementation plan

### Pre-phase (risk mitigation `characterize_sync_paths_never_empty_stdout`) — before any restructure

1. [characterize_sync_paths_never_empty_stdout] Add a forced-path harness
   (`tests/test_sync_protect_paths.sh`, or a section of the deferral test) that drives
   **every** `_protect "<reason>"` literal — scanned from the script source so a new
   reason cannot be missed — through `aitask_sync.sh --batch` under `set -u` (planted
   live lock / unreadable lock branch via an unreachable origin / a staged path /
   an ownerless file / a content change via the existing `pre_group_commit` seam /
   a lock acquired via the `pre_commit_phase` seam) and asserts the run's stdout is
   **non-empty and starts with a recognised token** every time. Commit it green
   against the current script, then restructure.

### 3a. Per-file record

2. Replace `PROTECTED_DIRTY=()` (reasons only) with parallel arrays
   `PROT_REASON PROT_TASK PROT_PATH PROT_STATE PROT_HOLDER PROT_EMAIL PROT_HOST
   PROT_PID PROT_PANE PROT_PANE_STATE PROT_ACTION` (`PROT_PANE` / `PROT_PANE_STATE`
   stay empty here; t1725_4 fills them). `_protect` takes
   `<reason> <task> <path> <tree_state> <human line>`; per-task protections
   (`live_lock`, `unknown_liveness`, `locks_unavailable`, `staged_elsewhere`,
   `content_changed`, `commit_failed`, `unverifiable`, `lock_acquired_during_scan`)
   call it once per path of that task; path-less ones (`scan_failed`,
   `lock_contended`) record an empty path with `tree_state=unknown`. `tree_state`
   comes from the porcelain `XY` already parsed in `_sweep_dirty`: `??` → `untracked`,
   anything else → `tracked`. `_lock_snapshot` keeps `LOCK_EMAIL[$tid]`.

### 3b. Holder classification

3. `_holder_class <tid>` → `self | other | remote | unverified | none`. `self`
   **only** when every identity is present and verified: `LOCK_EMAIL[$tid]`
   non-empty, `get_user_email` non-empty, the two equal, `LOCK_HOST[$tid]` non-empty
   and not `unknown`, `hostname` resolvable and equal to it. Any missing or malformed
   identity → `unverified` (never `self`, never eligible for `--commit-for-task`) — an
   empty local email must not equal an empty lock email. `other` = same verified
   host, different non-empty email; `remote` = a different host; `none` = unlocked.
   Human line / `PROT_ACTION` per class:
   - self: "t<id>: <path> — held by YOUR OWN live session on this host (pid <pid>[,
     pane <pane>]) — finish or answer that session; or commit on its behalf:
     ./ait sync --commit-for-task <id>"
   - other: "held by <email>'s live session on <host> (pid <pid>) — left for that session"
   - remote: "held on <host> (liveness cannot be verified from here) — left for that host"
   - unverified: "held by a session whose identity could not be verified (lock email /
     local userconfig email missing) — left as is"
   - ownerless / ambiguous_rename / staged_elsewhere / … keep their existing
     prescriptive text. "held by other sessions" disappears everywhere.

### 3c. Rebase gate

4. `_rebase_blocked` replaces both `(( ${#PROTECTED_DIRTY[@]} )) && remote_ahead > 0`
   sites (`main` ~1279, `do_push` ~1186). Inputs: `local_ahead`, `remote_ahead`,
   `incoming=$(task_git diff --name-only HEAD..@{u})` computed once after `do_fetch`.
   Blocked when any record has `tree_state=unknown`; or `tracked` **and**
   `local_ahead > 0` (a rebase needs a clean tree); or (`tracked` or `untracked`)
   **and** its path is in `incoming` (checkout would overwrite it). Otherwise not
   blocked. Rewrite the comment at ~1269 to state this three-way rule. In `main`:
   not blocked and `local_ahead == 0` → `task_git merge --ff-only --quiet @{u}`
   (a fast-forward never conflicts; `did_pull=true` on success — the
   `task_data_converge` rule from t1658_1); not blocked and `local_ahead > 0` →
   `do_pull_rebase` as today.
5. **Push-retry path re-gates on fresh inputs.** In `do_push`'s rejection branch:
   after the retry fetch recompute `local_ahead`, `remote_ahead`, `incoming`; re-run
   `_rebase_blocked`; if blocked emit the same `protected_dirty` deferral (status line
   + records) and return 2; otherwise route the rebase through `do_pull_rebase`
   (abort-safe; reports `CONFLICT:` / `ERROR:` itself) — the bare
   `task_git pull --rebase --quiet` at ~1198 is removed. Add a marker-gated
   `pre_push` seam (`_sync_test_seam pre_push`, same mechanism as `pre_commit_phase`)
   immediately before the first push so a test can advance the remote in between.

### 3d. Wire

6. First line keeps its shape and the closed reason set (`DEFERRED_REASONS`
   unchanged, three reasons):
   `DEFERRED:protected_dirty:<N> file(s) block the rebase: live_lock=<k> ownerless=<m> …`
   (sub-reason counts). Then, **after** the status line, one continuation line per
   record via a new `batch_detail()` (stdout, batch mode only — deliberately **not**
   `batch_out`, so `_emitted_tokens` in `test_sync_action_runner.py` does not read
   it as a status):
   `DEFERRED_FILE:<sub_reason>|<task>|<path>|<tree_state>|<holder>|<email>|<host>|<pid>|<pane>|<pane_state>|<action>`
   The record is the **complete per-file snapshot** — everything any consumer
   renders is on the wire, so no TUI re-derives locks, pane state or files. **Every
   textual field is `_pct_encode`d** (`|`, `%`, newline): `path`, `action`, `email`,
   `host`, `pane` (a tmux session name may contain `|` and a newline; `hostname` and
   `locked_by` are user-controlled). Closed/numeric fields stay bare: `sub_reason`
   (closed set), `task` (`^[0-9]+(_[0-9]+)?$`), `tree_state`
   (`tracked|untracked|unknown`), `holder` (`self|other|remote|unverified|none`),
   `pid` (`^[0-9]*$`), `pane_state` (`^(waiting_[a-z0-9_]+|active|)$`). Both
   emission sites (`main` and `do_push`) go through one `_emit_protected_deferral`.
   `report_skipped` (stderr) stays.

### 3e. Parser

7. `sync_action_runner.py`: `DeferredFile` dataclass with one field per column;
   `SyncResult.deferred_files: list[DeferredFile]`; `DEFERRED_FILE_REASONS` closed
   set (the `_protect "<reason>"` literals; a scan test mirrors
   `test_every_emitted_deferred_reason_is_declared` over `_protect\s+"([a-z_]+)"`);
   `parse_sync_output` collects `DEFERRED_FILE:` lines only when the first line
   parsed as `DEFERRED`; an unknown sub-reason, a bad closed-field value or a
   malformed line fails closed to `STATUS_ERROR`; a `DEFERRED_FILE:` line **as the
   first line** is `unknown status`. Percent-decoding mirrors `_pct_decode` order
   (`%25` last) on every encoded field.

### 3f. `--commit-for-task`, `--expect-path`, `--require-waiting`

8. `--commit-for-task <id>[,<id>…]`: evaluated **inside `_holder_verdict`** at both
   lock snapshots (pre-scan and the 5a.2 CAS): a listed task gets `free` only if its
   class is `self` *at that evaluation*; a lock that changes hands between the two
   snapshots yields differing verdicts → `lock_acquired_during_scan`. Any other class
   (incl. `unverified`) is refused with a stderr line naming who holds it. The
   override bypasses **neither** 5a.3 (state re-check) nor 5a.4 (publication guard).
   When it commits on behalf, print: "t<id>'s session is live — its uncommitted
   edits were committed as they stand now".
9. `--expect-path <pct-encoded path>` (repeatable, one argument per path — never a
   CSV: a comma is a legal path character): with `--commit-for-task`, if the task's
   dirty group at commit time is not exactly that set (any extra or missing path),
   skip the group as `_protect "commit_scope_changed"` with the delta in the action
   text.
10. `--require-waiting` (with `--commit-for-task`; the TUI always passes it): in
    `_commit_group`, after 5a.3 and before the commit, re-probe the holder's pane via
    `ait_tmux_pane_for_pid` + `lib/pane_state_probe.py` (both from t1725_4); unless the
    result is `waiting_<kind>` skip the group as `_protect "holder_not_waiting"` with
    the observed state (`active` / `unresolvable`) in the action text. **Fail closed
    when the probe is unavailable** (this task lands before t1725_4: no probe → not
    waiting → refused). The bare CLI flag without `--require-waiting` stays the
    explicit operator escape.
11. `show_help`: document the three flags and the `DEFERRED_FILE:` lines.
12. `shellcheck .aitask-scripts/aitask_sync.sh`.

## Verification

`tests/test_sync_deferral_and_quarantine.sh` (existing Tests 1–17 keep passing —
Test 3's asymmetry included):
- AC2 both directions: (i) untracked `aiplans/p10_x.md` + live lock on t10 + remote
  ahead, no incoming touch → no `DEFERRED`, remote commit pulled, local pushed;
  (ii) tracked modified `t10_alpha.md` in the same position → `DEFERRED:protected_dirty`;
  (iii) untracked, but an incoming commit creates the same path → deferred;
  (iv) `local_ahead == 0` + tracked dirty untouched by incoming → fast-forwarded, no
  deferral (t1696's scenario).
- wire: `DEFERRED_FILE:live_lock|10|…|tracked|self|other%40x.com|testhost|<pid>|||…`
  with `TEST_HOSTNAME` + a userconfig email matching the planted lock; `other`,
  `remote`, `unverified` rows via `lock_yaml_live … otherhost` / a different email /
  no userconfig email; a lock blob with no `locked_by:` → `unverified`.
- `--commit-for-task 10`: class `self` → group committed
  (`ait: Auto-commit t10 …`), run pushes, stderr carries the live-session warning;
  `other` → refused, still deferred; `unverified` → refused; under the
  `pre_group_commit` seam rewriting the file → skipped / quarantined exactly as
  without the flag.
- `--expect-path`: identical set → committed; group grown by one file → skipped
  (`commit_scope_changed`), nothing committed; a path containing a comma
  (`aiplans/p10_a,b.md`) round-trips and matches.
- `--require-waiting` with no probe available → `holder_not_waiting`, nothing
  committed (the fail-closed pin; the positive case is t1725_4's).
- push-retry race via the `pre_push` seam: the hook advances the remote from `pc2`
  creating the protected untracked path → push rejected → retry gate blocks →
  `DEFERRED:protected_dirty`, no `ERROR:push_rebase_failed`, local bytes unchanged;
  negative control: an unrelated advance → retry rebases → `PUSHED`.
`tests/test_sync_action_runner.py`: continuation parsing; pct-decoding of `|` in a
path, of `|` in an email, of a pane target from a session named `a|b`, of a host
containing literal `%7C` (no double-decode); unknown sub-reason / bad `pane_state`
grammar fails closed; first-line `DEFERRED_FILE:` is an error; the closed-set scan;
`_emitted_tokens` still passes.
Run: `bash tests/test_sync_deferral_and_quarantine.sh`, `bash tests/test_sync.sh`,
`bash tests/test_sync_auto_commit_scoping.sh`, `bash tests/test_sync_protect_paths.sh`,
`bash tests/run_all_python_tests.sh --test-dir tests` (verdict on the last line).
