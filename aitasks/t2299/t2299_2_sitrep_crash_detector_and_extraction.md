---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t2299_1]
issue_type: feature
status: Implementing
labels: [sitrep, crash_recovery]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2299
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 12:54
updated_at: 2026-11-15 18:13
---

## Context

This is the second of four children of t2299. It builds the deterministic **crash detector**:
- it finds tasks whose agent is gone;
- it records the evidence about each one;
- it maintains **one recovery item per task** (`kind=task`, `ref=recover:t<N>`) through the atomic writer verb `recovery-apply` added by t2299_1.

t2299_3 wires it into refresh, the monitor tick and the TUI. The design record is the parent plan in `aiplans/p2299/`; read t2299_1's archived plan first.

Advisory only. The detector never reclaims, unlocks, edits task status or types into a pane. Helpers report evidence and the agent judges.

## The ONE ordered decision table: `recovery_verdict`

The detector and refresh share it. The first matching row wins, and lock evidence comes before task completion.

| # | Facts | Category | New item? | Existing item → |
|---|---|---|---|---|
| 1 | any input for the task is unreadable | — | no | `unknown` "unreadable: \<what\>" (title, context and key untouched) |
| 2 | the lock is on another host, or its host is `unknown` | `other_host` (skip) | no | `unknown` "held on \<host\>: not verifiable here" |
| 3 | the lock holder is `alive` | `alive` (skip) | no | `done` "held by a live session" |
| 4 | the lock holder is `unknown` (numeric pid) | `unknown` (skip) | no | `unknown` "liveness unknown" |
| 5 | the lock has no PID anchor (any status) | `stale_lock` | yes | open |
| 6 | the lock holder is `dead` and the task is Implementing | `crashed` | yes | open |
| 7 | the lock holder is `dead` and the task is not Implementing, or is archived, Done, folded or missing | `stale_lock` | yes | open |
| 8 | there is no lock and the task is Implementing | `orphan` | yes | open |
| 9 | there is no lock and the task is Ready, Postponed, Done, archived, folded or missing | none | no | `done` "recovered: \<status\>" |

- `unknown` is never rounded up to `crashed`.
- The host guard always runs before any `dead` verdict.
- The outcome is `<category> · <short evidence>` and is at most 200 characters. Only `format_outcome` / `parse_outcome` touch its leading token, and it is used for display only.

## Episode key

The episode key is recorded as the context origin `incarnation=<12 hex>`, and only `recovery-apply` writes it. A new key is minted only when a lock that represents a claim is observed:
- **Anchored lock:** sha256 of `task_id, hostname, pid, pid_starttime, pid_starttime_kind`. `locked_at` is excluded, so a session refreshing its own lock gets the same key.
- **Unanchored lock:** sha256 of `task_id, locked_by, hostname, locked_at`.
- **No lock:** carry the item's recorded key forward. A brand-new item with no lock gets sha256 of `nolock\n<task_id>`.

Task metadata never enters the key. The writer then:
- keeps a dismissed item when the key is unchanged;
- reopens it only on a different key, which means a new claim that crashed again;
- always reopens a `done` item that again falls into a stored category.

## Strict inputs

The existing probes are NOT strict enough to be reused as they are:
- `parallel_admission_collect.probe_lock_source` stores `{}` for a failed `git show` and still reports `ok`;
- `_read_frontmatter` swallows `OSError`.

Write strict readers in `lib/sitrep_crash.py`:

- **Locks**
  - Resolve `refs/remotes/origin/aitask-locks`, else the local `aitask-locks`. Never fetch.
  - Use `git ls-tree -z <ref>` to get object ids and names (`t<id>_lock.yaml`).
  - Read the blobs with one `git cat-file --batch`.
  - A blob that fails or is malformed (no `task_id` or `hostname`) is an **error** record.
  - A file that is absent from the tree means "no lock"; this is the only route to that answer.
  - The lock YAML keys are `task_id, locked_by, locked_at, hostname, pid, pid_starttime, pid_starttime_kind` (`aitask_lock.sh:296-302`).
- **Tasks**
  - Walk the active `aitasks/t*.md` and `aitasks/t<P>/t<P>_<C>_*.md`.
  - For a locked id with no active file, use `lib/archive_iter.py` `find_archived_markdown_by_id` (loose files and bundles; the same as `sitrep_refresh.TaskIndex._lookup` :291-327).
  - Each of these is an **error**: `OSError`, unparseable frontmatter (`lib/task_yaml.parse_frontmatter`), a missing `status:` or an invalid one.
  - `folded_into` means folded.
- **Errors**
  - An unreadable ref or tree, or an unwalkable task dir → `CRASH_FAILED:<reason>`, with no writes.
  - A per-task failure → `CRASH_WARN:t<N>|unreadable:<what>`, and nothing is written for that task.
- **Reuse only the pure liveness helpers:**
  - `parallel_admission_collect.classify_liveness`, the host guard (:247-274);
  - `lock_holder_liveness` (:229-244), which wraps `lib/pid_anchor.sh::lock_holder_liveness <pid> <starttime> <kind>` → `alive|dead|unknown`.

## Evidence per stored task (source-tagged)

**lock**
- host, pid, `locked_at`, `lock_age` (clock seam `AITASK_SITREP_NOW`), and the key.

**phase** (from `lib/gate_ledger.py`)
- `has_gate_markers` and `resume_point_from_text` give: PLAN → `planning`, IMPLEMENT → `implementing`, POSTIMPL → `post_impl`.
- No ledger → `unknown`.
- Unreadable ledger → `error`.
- Also record `phase_provenance` (`ledger` / `unknown` / `error`).
- For post_impl, add the `archive_pending` gate names from `read_task_gate_state(task_file, registry_file="aitasks/metadata/gates.yaml", current_digest=<per-run memo>)`. Call it directly, never through an alias; that is a syntactic guard, see `tests/test_gate_ledger_only_surfaces.py`.
- Do NOT import `board/board_workflow_phase.py`: lib must not import board (`tests/test_no_lib_to_tui_import.sh`).

**plan**
- `plan`: `none | draft | approved`.
  - Find the file with `parallel_admission_collect.plan_path_for` (or `trail_gather.plan_path_for`).
  - `approved` means ledger `plan_approved` is `pass`, or the frontmatter has `plan_approved_at`.
- `plan_signature`: `valid | stale | none`. It is `stale` when `plan_approved` is in that same state's `stale_signed`; `plan_approved` is a `type: human` gate in `aitasks/metadata/gates.yaml`.
- `plan_fresh`: `fresh | stale:<reasons> | unknown:<why>`, where the reasons are a comma-joined list of `signature_stale`, `<n>_commits` and `dirty_referenced:<k>`.
  - Referenced files are the `file_references:` frontmatter plus tracked paths (`git ls-files`) named in the plan or task text.
  - The baseline is `premise_baseline` (`<sha> @ <ts>`), else the commit at approval time (`git rev-list -1 --before=<ts> HEAD`).
  - Commits are counted with `git log <base>..HEAD -- <files>`.
  - No file list, or no baseline → `unknown`, never `fresh`.
- **Authorship rule:**
  - In a dedicated worktree, dirty files are this task's own surviving work and do not make the plan stale.
  - In the SHARED tree, a dirty referenced file sets `stale:dirty_referenced:<k>` (re-verify the plan against the surviving edits).

**surviving work**
- `aitask_task_worktree.sh resolve <task_name>` prints `NONE | USABLE <p> | STALE | LOCKED | MAIN | UNSAFE`:
  - `USABLE` → `git -C <p> status --porcelain -z`, all of it attributed (source `worktree`);
  - `NONE` → the shared tree;
  - any other state → report it, never guess.
- **Shared tree:** run `git status --porcelain -z` ONCE per pass. A path is attributed to a task only when that task's plan or task text names it (source `plan` or `task`). Everything else goes in an `unattributed` bucket.
- `overlaps`: paths named by two or more Implementing tasks (live or crashed), each tagged with its owner.
- Commits referencing `(t<N>)` since `locked_at`, excluding `ait:` subjects.
- The last commit on `aitask/<task_name>`, if that branch exists.
- When any work survives, print a loud "do not `git restore` / `git stash` / checkout the tree".

**pane**
- Look up an `lib/agent_sessions.py` `load_safe()` record with `task_id == N` and `root ==` the canonical root. A matching `pane_pid` is strong evidence.
- If `capture_txt` is readable, retain its last ~200 lines as a `capture:` source.
- `agent_string` and `pane_id` go into the origin keys.

## Writes (through `aitask_sitrep_todo.sh` only)

Per task: 0+ `retain` calls (content-addressed, so an interruption is harmless), then EXACTLY ONE `recovery-apply` with the rev from this pass's `list` read (`absent` for a new item).

- `STALE` → `CRASH_WARN:t<N>|stale`; the next pass re-decides. Never retry blind, so a concurrent dismissal always wins.
- Dismissed items get no write other than a reopening `recovery-apply`, and the writer decides KEPT vs REOPENED.

**title** (≤200), e.g. `Recover t2284 (crashed): implementing, approved plan (stale: dirty_referenced), 13 files, overlaps t2286`. It names the task by its id and filename slug only: the list never copies task content.

**group**, by rank:
1. implementing/post_impl with an approved, valid, fresh plan and surviving work;
2. approved, but invalid, stale or unknown;
3. draft;
4. planning, or no plan.

Rank 1–2 → `now`, rank 3–4 → `next`. Orphan → `next`. Stale_lock → `waiting`. post_impl is ranked by what remains.

**context** (a map, not a summary):
- a static background line per category;
- `origin: task=t<N> incarnation=<key>` (plus `agent=` / `pane=` when known);
- sources: `task:`, `plan:`, `capture:` (the survey passage), `capture:` (the pane tail), `commit:`.

**survey passage**: deterministic `key: value` lines, starting with `SITREP_RECOVERY_SURVEY v1`. Keys: `task`, `category`, `incarnation`, `lock`, `lock_age`, `phase`, `phase_provenance`, `pending_gates`, `plan`, `plan_signature`, `plan_fresh`, `worktree`, `uncommitted_files: attributed=<a> unattributed=<u>`, `attributed: <path> [<source>]`…, `overlap: <path> <task>(<live|crashed>)`…, `commits`, `warning`.

## CLI: `aitask_sitrep_harvest.sh crashed [--root <abs>] [--dry-run]`

- Add the dispatch case in `main()` (sh:387-401) plus the header contract.
- Plan/apply split as `plan` → `WORK:<root>` (`_work` :1247) → `with_harvest_lock` (:196).
- `canonical_root` (sitrep_harvest :642).
- `--dry-run` takes no lock and writes nothing.

Output:

```
CRASH_ITEM:t<N>|c<M>|added|applied|unchanged|reopened|kept_dismissed|dry_run|<category>
CRASH_SKIP:t<N>|alive|unknown|other_host:<host>
CRASH_WARN:t<N>|<reason>
final: CRASHED:crashed=<a>|orphans=<o>|stale_locks=<s>|skipped=<k>|added=<n>|reopened=<r>|warned=<w>
     | CRASH_NONE:nothing_inflight
     | CRASH_FAILED:<reason>
```

- Exit 0 ok, 1 failed, 2 usage.
- Fault seam `AITASK_SITREP_CRASH_FAULT=<point>` (e.g. `before_apply`).
- Add the new helper or lib files to the five code-agent allow-lists only if the skill calls them; the verb lives in an existing script (see `aidocs/framework/aitasks_extension_points.md`).

## Reference patterns

- `lib/sitrep_harvest.py`: `Store.add`/`retain`/`run` (:707-796), `_context()` (:816).
- `tests/test_sitrep_refresh.sh` scratch-root helpers (:86-186): `new_root`, `task`, `archive`, `wr`, `add_item`.
- `tests/test_sitrep_refresh.py` `Tree`/`TreeCase` (:42-85).
- `lib/pid_anchor.sh` for capturing a live process's starttime token in tests.

## Verification

`tests/test_sitrep_crash.py` (units) and `tests/test_sitrep_crash.sh` (end to end with the real writer; a scratch repo whose `refs/remotes/origin/aitask-locks` holds lock blobs, real dead and live PIDs):

**Classification**
- Every decision-table row, including the unknown-liveness and other-host negative controls (never stored, never crashed).

**Precedence**
- An archived task and a Done task, each with a dead or no-anchor lock, stay open `stale_lock` across 3 detector passes with identical output.
- Release the lock → `done`, and it stays done.
- Replace it with a live claim → `done` (row 3).
- A crashed task archived under its dead lock → `stale_lock`, same key.

**Strict inputs**
- An unreadable blob, a malformed lock, an unreadable task file and a missing `status:` each give `CRASH_WARN`, and the existing item stays byte-identical.
- An unreadable ref or tree → `CRASH_FAILED` with no writes.
- Control: a lock absent from the tree means "no lock".

**Episodes**
- A metadata edit on a dismissed orphan → kept.
- A dismissed crashed item whose lock is removed → kept.
- A new live claim → item untouched; once that claim dies → reopened.
- A self-refreshed lock → same key.
- done → crashed again → reopened.

**Atomicity**
- `AITASK_SITREP_CRASH_FAULT=before_apply` → the item is unchanged.
- A dismissal between the read and the write → `STALE`, the item stays dismissed, and the next pass reports `kept_dismissed`.

**Plan**
- One ledger fixture per phase, including a reachable post_impl.
- A stale signature (witness digest mismatch) → `stale:signature_stale`.
- A dirty referenced file in the shared tree with no new commit → `stale:dirty_referenced`.
- The same file dirty in a dedicated worktree → surviving work and `fresh`.
- No baseline → `unknown`.
- An unreadable ledger → `error`.

**Work**
- Two tasks naming one file → overlap.
- Control: an unattributed path is never attributed.

**Idempotence**
- A second pass → `unchanged`.
- `--dry-run` writes nothing.

**Live acceptance (read-only)**
- `./.aitask-scripts/aitask_sitrep_harvest.sh crashed --root "$PWD" --dry-run` on this repo. On 2026-11-15 it should list 15 crashed (1555_2, 1576, 1697, 1912_2, 2199, 2216, 2264, 2284, 2285, 2286, 2287, 2289, 2291, 2292, 2293), stale_lock 259, orphans 1699 and 887, and `CRASH_SKIP` alive 2290. Re-survey first, because this is moment-relative.

Never `git restore` / `git stash` / checkout in this repo: the shared tree holds crashed tasks' uncommitted work.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2299_1** id=2026-11-15T14:35:19Z.8064b4670be300333b50718d from=t2299_1 from_verified=yes at=2026-11-15T14:35:19Z base=172d5e4af21ce7986be7b5b555442ba8b8c57600 base_branch=main dirty=yes host=omg16
>
> | recovery-apply caller contract (t2299_1). This affects your plan's apply loop (step 6.3) and reply mapping (step 6.4).
> | 
> | As of this moment the t2299_1 change is implemented but NOT yet committed. The base SHA this note records does not contain it; it lands with the `feature: ... (t2299_1)` commit. Read `.aitask-scripts/aitask_sitrep_todo.sh`'s header `recovery-apply` entry once that commit exists.
> | 
> | 1. Two different keys. `--incarnation` names the episode the RECORDED evidence belongs to, which is not always the lock key you just observed.
> |    - WITH a context (create, evidence refresh, reopen): `--incarnation` = the context's origin `incarnation` = the observed episode key. This is the only way a recorded incarnation changes.
> |    - WITHOUT a context (a state-only `done` / `unknown` verdict, e.g. live claim B now holds the task): pass the item's RECORDED incarnation (read it from `context c<N>`), never the observed key. The item's context stays byte-identical. When B later crashes, send B's context with `--state open` and you get `REOPENED`, with the recorded incarnation now B.
> |    - The observed key with no context, on a non-dismissed item, is exit 2 and writes nothing. Your plan step 6.3 as written ("same verb with the state and outcome only, no context") would hit this if it passes the newly hashed key.
> | 2. A context's origin `incarnation` must equal `--incarnation`, else exit 2. Creating (`--expect-rev absent`) needs `--title` and a context.
> | 3. Reply lines: `ADDED:c<N>|<rev>`, `APPLIED:c<N>|<rev>`, `UNCHANGED:c<N>|<rev>`, `REOPENED:c<N>|<rev>`, `STALE:c<N>|<rev>`, `KEPT:c<N>|dismissed`, `KEPT:c<N>|dismissed_no_incarnation`, and `ABSENT:<ref>` (a numeric rev was given but no item holds the ref, e.g. after a restore; nothing written, re-read). Your step 6.4 mapping should handle ABSENT.
> | 4. Only `recovery-apply` can create a `recover:` item or move its incarnation. `add` refuses the ref; `update` cannot set, change or re-kind it; `upsert-context` must keep the recorded incarnation.
> | 
> | Pinned by `tests/test_sitrep_todo.sh` Test 17b ("episode handoff"): A open, then a state-only done with A gives APPLIED with the context unchanged. The same call with B is the exit-2 negative control. B's context with open gives REOPENED. Dismiss, then B again, gives KEPT.
> | 
> | This is advisory context for your planning, not an instruction.

> **👁 note:read** id=2026-11-15T15:45:36Z.48bdd2e29a3b49bf26b5e0a8 by=t2299_2 at=2026-11-15T15:45:36Z mode=explicit ids=2026-11-15T14:35:19Z.8064b4670be300333b50718d

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-15T16:13:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-15T17:34:36Z status=pass attempt=1 type=human
