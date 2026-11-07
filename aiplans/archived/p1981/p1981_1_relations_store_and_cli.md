---
Task: t1981_1_relations_store_and_cli.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-06 07:46
---

# t1981_1 — Relations store and CLI

## Context

First child of t1981. It builds the orphan-branch store for task relations
(`aidocs/framework/task_relations.md` D1, D2, D3, D11). It does no analysis and
adds no triggers or skill changes. Every later child reads or writes through
this module: t1981_3 adds `stamp` / `plan-digest` / `analysis-state` / `analyze`
and the spool, and t1981_5 adds `notify-candidates`.

## Verification findings (2026-11-05, against HEAD 9b6cb2761)

The plan holds in shape. These points correct or sharpen it. Points 12–16 come
from the user's review of the first verified draft; each was checked against
the code and confirmed.

1. **Bounded fetch: reuse `lib/bounded_run.py`.** Use `run_bounded()` with
   `noninteractive_env()` (no controlling terminal, empty `GIT_ASKPASS`,
   `SSH_ASKPASS_REQUIRE=never`, process-group kill). Drop the old "SSH
   `BatchMode` unless there is a custom `core.sshCommand`" idea: `bounded_run`
   deliberately leaves configured SSH commands alone.
2. **`STORE:empty` needs a probe.** A `git fetch` of an absent remote ref
   *fails*, so use the `aitask_claim_id.sh` `remote_branch_state` precedent:
   `ls-remote --heads origin aitask-relations` (PRESENT, ABSENT or ERROR), then
   fetch only when PRESENT. Both calls are bounded, and together they are the
   one refresh of the invocation.
3. **Body digest: reuse `plan_paths.task_body_text()`.** It strips the
   frontmatter and cuts the framework sections.
4. **The normalization lives in the schema module** (D2: "one function of the
   schema module"). The store re-exports it.
5. **`gc` existence: two independent negatives before any delete.**
   1. The complete `TaskIndex` scan (finding 15) with `errors=`. Any error
      refuses the gc.
   2. Per missing id, `aitask_query_files.sh` `task-file` / `child-file` /
      `archived-task`. `archived-task` resolves loose, numbered and legacy
      bundles (`ARCHIVED_TASK_ARCHIVE:`).

   Only `NOT_FOUND` from every applicable lookup makes an id deletable.
6. **The fold map** is the union of live files' `folded_into` and every active
   and archived primary's `folded_tasks:`, all taken from the same scan. A
   folded file is deleted when its primary is archived, so `folded_into` alone
   loses mappings. `gc` treats a folded id as existing.
7. **`write()` takes `flush=` (default True).** t1981_3's `stamp` writes the
   outbox synchronously and detaches the publish.
8. **Whitelist through `aitask_audit_wrappers.sh apply-helper-whitelist
   aitask_relations.sh`** (the 5 live touchpoints). Doing it ahead of any skill
   reference is safe: `test_helper_whitelist_coverage.sh` checks only
   referenced → whitelisted.
9. **The wrapper resolves Python** through `lib/python_resolve.sh`
   `resolve_python`, as `aitask_sitrep_todo.sh` does.
10. **One state directory per clone.** `aitasks/` and `aiplans/` are symlinks
    into `.aitask-data/`, and `git rev-parse --git-common-dir` is `.git` from
    both checkouts, so `<git-common-dir>/aitask-relations/` is shared by every
    worktree of the clone.
11. **Nothing to adopt or collide with.** No orphan-ref helper has landed since
    2026-11-04. The touchpoints, `ait` and `CLAUDE.md` are clean in the working
    tree. The uncommitted sitrep work in the tree belongs to another session
    and is not touched.
12. **Identity before ordering (review, high).** Newest-wins by `(stage, at)`
    alone lets a deleted child's stage-2 record outrank its reused number's
    stage-1 record forever, until gc. Every comparison, in `write`, in the
    flush merge and in the outbox overlay, first separates incarnations by
    `task_created_at` against the live task: a record of the live incarnation
    always beats one of a dead incarnation, whatever its stage or time.
    - This needs `task_created_at` on **all four kinds**. D2 lists it on the
      relations record only, so the approval stamp, the obsolescence record and
      the dismissal gain it too.
    - `gc`'s identity rule (D1) already presumes the field on every kind.
    - The schema change is recorded in the post-phase doc step.
13. **Revalidation on every gc retry (review, high).** A selection made before a
    CAS conflict can be stale: a producer may meanwhile publish the valid
    replacement under the same path. Eligibility is therefore re-evaluated on
    **every attempt**, against the blob in that attempt's freshly fetched base
    tree and a re-resolved live identity for the selected ids. Any path that no
    longer qualifies is preserved.
14. **The ref model (reviews, rounds 1–4).** It replaces every earlier ref rule.
    Four review findings shaped it:
    - a delayed post-push `update-ref` or a forced fetch into a shared ref
      rewinds a newer publish;
    - a single-parent upgrade commit never converges;
    - a stale pinned base plus a plain push resurrects deletions;
    - an ancestry *skip* rule rejects genuine local work, and a *frozen* local
      branch loses data when the clone goes back to local-only.

    The model:
    - **M1. One durable local ref.** `refs/heads/aitask-relations` (L) is the
      clone's **latest-known store** in both modes. It survives `git remote
      remove`, which deletes `refs/remotes/origin/*`. The tracking ref
      `refs/remotes/origin/aitask-relations` is never read or written, because
      default `git fetch` refspecs and `remote remove` both touch it. Fetches go
      into a per-operation temporary ref (`refs/aitask-relations/tmp/<pid>-<rand>`,
      deleted in a `finally`). Each operation resolves its commits once and
      reads only those immutable shas.
    - **M2. L only moves forward.** Every update is a `cas_local` from the
      observed value to a descendant of it. That happens in two cases:
      - **in local-only mode,** through each local commit, which is built on L;
      - **in remote mode,** only through `integrate()` below, which either
        fast-forwards or makes an absorb merge whose parents include the
        current L.

      **`integrate(C)` (rounds 5 and 6)** is the **only** way L takes in a
      commit C that came from the remote, either a pinned fetch R or a commit P
      this clone just pushed. It is a loop, bounded to 8 attempts:
      1. Resolve the current L as `cur`.
      2. If C is an ancestor of `cur`, it is done (`INTEGRATED`).
      3. If `cur` is None or an ancestor of C, `cas_local(L, C, cur)`, a
         fast-forward.
      4. Otherwise **absorb**: build a local merge `A = (C, cur)` whose tree is
         the M4 `merge_path` result over `merge-base --all(cur, C)`, then
         `cas_local(L, A, cur)`.
      5. On a CAS conflict, go back to step 1.

      It returns `INTEGRATED` only once C is an ancestor of L. Exhausted
      attempts return `INTEGRATE_FAILED`, which is never treated as success.

      Callers:
      - `read()` after every successful fetch (C = R);
      - `flush()` after every successful fetch (C = R, **explicitly**, before
        building the publish);
      - `flush()` and `gc()` after every successful push (C = the pushed P).

      A sibling-merge race is just another absorb. A reader's absorb `A=(R,L)`
      and a writer's published `P=(R,L)+X` are merged into L, and X is kept.

      An absorb commit is unpublished, and every remote commit it absorbed is
      an ancestor of it. So the next publish's `merge-base` with the remote
      excludes everything already observed, and M4 replays only the genuine
      local changes. L therefore **always** holds every observed and
      every published record, plus the unpublished local changes. That holds
      across failed fetches, `no_fetch`, `git remote remove`, and concurrent
      readers and writers in one clone.
    - **The outbox clearing invariant (round 6).** A published or superseded
      outbox entry is removed only **after** `integrate()` returned
      `INTEGRATED` for the commit that carries it (the pushed P) or the record
      that superseded it (the fetched R). On `INTEGRATE_FAILED`, the entries
      are **kept**. The next flush finds them identical to the remote blob or
      superseded by it, so it builds no new commit, integrates the remote tip,
      and only then clears them. An intent is never dropped while the local
      store lacks its result.
    - **Observed ref.** `refs/aitask-relations/observed` (O) is advanced
      fast-forward-only to each successfully pinned or pushed remote tip. It
      survives `remote remove`. It is used only to mark `pending_push`, as the
      paths in `diff(merge-base(L, O), L)`, and is never authoritative data.
    - **M3. Unpublished local work is a fact, not a guess.** "Local work
      pending" means L is not an ancestor of the pinned remote tip R. **L is
      resolved before R is pinned**, on the first attempt and on every retry.
      In remote mode, L only ever advances to commits that are already on the
      remote, and every push is leased, so the remote only moves forward. A
      remote-derived L resolved before the fetch is therefore always an ancestor
      of R, which kills the round-3 false positive. A genuine local commit is
      never on the remote, so it is always detected, whether L descends from R,
      is unrelated to R, or diverged from it.

      There is no skip rule. A local descendant of R is published even with an
      empty outbox.
    - **M4. Publishing local work is a three-way replay** against the merge
      bases `merge-base --all(L, R)`, or none when the histories are
      unrelated. Every path that differs among the bases, l and r goes through one total
      function, **`merge_path(kind, bases, l, r, index)`**. Here `bases` is the
      list of that path's versions in **every** merge base from `merge-base
      --all`. **Zero merge bases (unrelated histories) is normalized to one
      synthetic empty-tree base, `bases = [None]`, before the table applies**
      (round 7). Otherwise "equal to every base" is vacuously true, and every
      path reads as untouched on both sides. `merge_path` asserts that `bases`
      is non-empty. Absorb merges
      can produce criss-cross histories with several bases (round 6). l and r
      are the local and remote records, and `None` means absent or deleted.
      `wins()` never sees `None`.

      "Untouched" means equal to the path's version in **every** base. With a
      single base, b below is that base. The cases:

      | Case | Result |
      |---|---|
      | `l == r` (both sides agree, including both deleted) | `l` |
      | `l` untouched | `r` (a remote deletion after the bases stays deleted, so it is never resurrected) |
      | `r` untouched, `l` present | `l` |
      | `r` untouched, `l is None` (local deletion) | `None` only if `r` (equal to the bases' version) is **still deletion-eligible** under the current index; otherwise `r` |
      | both present, both changed | `wins(kind, l, r, live)` |
      | `l` present, `r is None` (remote deletion vs local modification) | `l` only if it matches the live task's identity; otherwise `None` |
      | `l is None`, `r` present (**local deletion vs remote modification**, round 5) | `None` only if `r` is itself deletion-eligible under the current index; otherwise **`r`**, so a valid remote replacement, such as a reused child's new record, survives an offline gc |

      **Deletion-eligible** is exactly gc's rule (D1, D11): the id exists
      nowhere (the two negatives of finding 5), or the record's
      `task_created_at` differs from the live task's. `gc` itself, absorb,
      publish and reads all use `merge_path`, so the conflict rules agree
      everywhere.

      The commit:
      - **R is the single merge base**, so R is an ancestor of L and the remote
        has not moved since L's base: push **L
        itself**, leased on R. That is a fast-forward.
      - **R absent**: push L, with the lease requiring the branch to be absent.
      - **Otherwise**: a two-parent merge `(R, L)` with the replayed tree,
        leased on R.

      Then `integrate(pushed)`. This is a fast-forward, unless a concurrent
      absorb moved L meanwhile, in which case it is an absorb.
      - Report `UPGRADED:<|Δ|>` only when `integrate` returned `INTEGRATED`.
      - Otherwise report `UPGRADE_INCOMPLETE:integrate_failed`, keep the outbox
        entries, and let the next flush converge.
      - After success, the pushed commit is an ancestor of L and of every later
        remote tip. So no `merge-base --all(L, R')` ever predates the local work
        again, and nothing is replayed twice.
    - **M5. Every push is leased on the exact base it built on**:
      `--force-with-lease=refs/heads/aitask-relations:<R or empty>`. A remote
      that moved since the pin is a `CONFLICT`, whatever the new commit's other
      parents contain. On `CONFLICT`: re-resolve L, re-pin R, recompute M3 and
      M4, and rebuild.
    - **M6. Reads are uniform.** After a successful fetch has been
      fast-forwarded or absorbed (M2), every read in every mode reads **L plus
      the outbox**. The outbox overlays through `wins()`, and an outbox
      deletion is not a thing: gc writes commits, not outbox entries.
      `pending_push` marks outbox paths and `diff(merge-base(L, O), L)`.
15. **Legacy archives are not in `iter_all_archived_markdown` (review, medium).**
    Finding 5's first draft was wrong: `iter_all_archived_markdown` and
    `archived_markdown_sources` both document that they do not scan the legacy
    `old.tar.*`. So `TaskIndex` scans, with `errors=`:
    - loose and numbered archives through `iter_all_archived_markdown`;
    - plus `iter_legacy_archive`;
    - with duplicates resolved in the shell resolver's precedence: loose, then
      numbered, then legacy, first seen wins. A duplicate whose `created_at`
      differs from the winner's is reported (`INDEX_DUPLICATE:`).
16. **Bundled tasks get real baselines (review, medium).** The archive iterators
    yield full text, so the scan keeps each archived task's normalized body
    digest. Archived plans are bundled the same way
    (`aiplans/archived/_bN/oldM.tar.zst`), so a parallel plan scan keeps plan
    digests: loose `p*_*.md` and `p*/p*_*_*.md`, plus `iter_numbered_archives`
    and `iter_legacy_archive` over `aiplans/archived/`.
    - A baseline that cannot be read never reads as fresh. It yields
      `unverified:source_baseline|target_baseline`. That marker is new, added
      beside D11's `stale:*`, and recorded in the doc step.

## Steps

### Pre-phase (risk mitigations)

0a. **probe_git_ref_states.** In a scratch repo with a bare remote, record the
    real exit codes and stderr on this host's git for:
    - `fetch` of an absent remote ref;
    - `ls-remote` to an unreachable remote (a missing path and a `file://`
      URL);
    - `push --porcelain` rejected as non-fast-forward;
    - `update-ref <ref> <new> <old>` with a stale `<old>`;
    - `merge-base --is-ancestor` exit codes, and `merge-base` on unrelated
      histories (M3, M4);
    - `push --force-with-lease=<ref>:<sha>` against a moved remote, and
      `<ref>:` (empty) against an existing branch (M5);
    - which refs `git remote remove origin` deletes (M1).
    Classify on exit status first and on porcelain or stderr only where git
    gives no distinct status. Pin the observations as a table in the
    `orphan_ref_store.py` docstring.

### Main steps

1. **Reality check.** Done at verification (the findings above).

2. **`.aitask-scripts/lib/orphan_ref_store.py`** (new, stdlib only). Git
   plumbing with no policy. Every call takes `repo` and passes `cwd=`, and
   nothing calls `os.chdir`.
   - `git(*args, input=None)`: local plumbing, with the status checked and no
     shell pipelines.
   - `remote_url()` → str | None.
   - `probe_remote_branch(ref, timeout)` → `PRESENT|ABSENT|ERROR:<reason>`
     (`run_bounded(..., env=noninteractive_env())`).
   - `fetch_pinned(ref, timeout)` → `(sha|None, error|None)`. It fetches
     `+refs/heads/<ref>:<tmp ref>`, resolves the tmp ref to a sha, and deletes
     the tmp ref in a `finally`. It never writes a shared ref.
   - `resolve(refname)` → sha | None, and `is_ancestor(a, b)` → bool, from the
     `merge-base --is-ancestor` exit status (0 / 1; anything else raises).
   - `merge_bases(a, b)` → `list[sha]`, from `merge-base --all`. It is empty
     for unrelated histories (per 0a) and has several entries for
     criss-crosses.
     `diff_trees(old_tree|None, new_tree)` → `{path: new_blob|None}`, from
     `diff-tree -r -z --no-renames`, with the empty tree when `old` is None.
   - `advance_ref(refname, new)` → `ADVANCED|ALREADY_NEWER|DIVERGED`. Loop:
     `cur = resolve`.
     - `cur` is None, or `cur` is an ancestor of `new` → `update-ref <ref>
       <new> <cur|zero-oid>`; on a CAS failure, loop again (at most 8 times).
     - `new` is an ancestor of `cur` → `ALREADY_NEWER`, and nothing changes.
     - Otherwise → `DIVERGED`, and nothing changes. The caller reports it, and
       the next pinned fetch is authoritative.
   - `read_tree(commit)` → `{path: blob_sha}` (`ls-tree -r -z`).
     `cat_blobs(shas)` runs one `cat-file --batch`, with its binary output
     parsed by header length.
   - `build_commit(base|None, changes{path: bytes|None}, message,
     extra_parents=())`. `extra_parents` is used only by the M4 merge. It uses a
     temporary `GIT_INDEX_FILE`, `read-tree <base>` or `--empty`, `hash-object
     -w --stdin`, `update-index --add --cacheinfo 100644,<sha>,<path>` or
     `--force-remove`, `write-tree`, and `commit-tree [-p base]`. The committer
     identity falls back to environment values when none is configured.
   - `cas_push(commit, ref, base|None, timeout)` → `OK|CONFLICT|ERROR:<reason>`.
     It runs `push --porcelain --force-with-lease=refs/heads/<ref>:<base or
     empty> origin <c>:refs/heads/<ref>`, bounded and classified per 0a. A
     stale lease and a non-fast-forward are both `CONFLICT` (M5).
   - `cas_local(ref, new, old|None)` → `OK|CONFLICT` (`update-ref`).

3. **`.aitask-scripts/lib/relations_schema.py`** (new).
   - `SCHEMA = "aitask-relations/1"` and `LAYOUT_VERSION = "1"`. The kinds are
     `records`, `obsolescence`, `dismissals` and `approvals`.
   - The `TYPES` direction table (`affects`, `advisory_precedes`, `supersedes`
     and `informs` directed; `coordinates_with` and `duplicates` symmetric).
     `IMPACT_BASES = {path, symbol, token}`, `CONNECTIVITY_BASES =
     {task_ref}`, and `NEEDS_IMPACT = {affects, coordinates_with, supersedes}`.
   - `parse_ref()`, the canonical `<project>#<id>` with the t1635 id shapes.
   - Validators for the four kinds, and `validate(kind, path, obj)`, which also
     checks that the path matches the task. **`task_created_at` is required on
     every kind** (finding 12). They raise `SchemaError` on:
     - an unknown key or type;
     - an unknown relation type or basis kind;
     - a missing impact basis;
     - a description over 600 characters;
     - an absolute basis path, one with a `..` segment, or a bare basename;
     - a relation with no end equal to the record's task;
     - a relation end with no `inputs.candidates[]` entry.
   - `normalize_body(raw)` = `plan_paths.task_body_text(raw)`. `normalize_plan(raw)`
     strips the leading `---` block and drops the `## Final Implementation
     Notes` and `## Post-Review Changes` sections. `sha256_text` hashes UTF-8
     with LF line endings. `digests(task_text, plan_text|None)`. This is the
     single normalization function.
   - `order_key(kind, obj)`: `(run.stage, run.at)` for `records` and
     `obsolescence`; `(0, approved_at)` for approvals and `(0, at)` for
     dismissals.
   - **`wins(kind, new, old, live_created_at)`**, the one comparison used
     everywhere:
     1. When `live_created_at` is known and exactly one side's
        `task_created_at` equals it, that side wins.
     2. Otherwise, `order_key(new) >= order_key(old)`.

     Callers pass the live identity from `TaskIndex`. Unknown (the id exists
     nowhere) falls through to rule 2.

4. **`.aitask-scripts/lib/relations_store.py`** (new).
   - **Paths:** `<git-common-dir>/aitask-relations/`, with
     `outbox/<kind>/t<id>.json[.err]`, `outbox.lock` and `fetched_at`.
     `BRANCH = "aitask-relations"`, and the timeout is
     `AIT_RELATIONS_FETCH_TIMEOUT` (default 20 s).
   - **Mode:** `remote` when `origin` exists, else `local_only`.
   - **`TaskIndex`** (built once per process, plus `refresh(ids)` for targeted
     re-resolution). The scan sources, all with `errors=`:
     - the active tasks under `TASK_DIR`;
     - `iter_all_archived_markdown` plus `iter_legacy_archive`, with
       duplicate precedence (finding 15);
     - the plan scan over `aiplans/` and `aiplans/archived/` (finding 16).
     Per id it keeps `created_at`, status, `folded_into`, `folded_tasks`, the
     normalized body digest, the normalized plan digest (or None for no plan,
     or `UNREADABLE`), and where the task lives. The fold map is
     canonicalized transitively, with a cycle guard. `index.errors` is exposed,
     so callers that need completeness (`gc`) can refuse.
   - **Hooks for the interleaving tests:** the module-level no-op
     `_test_hook(point)` is called at `after_snapshot`, `after_resolve_local`,
     `after_pin`, `after_push`, `before_bookkeeping`, `gc_after_select` and
     `before_removal`. Tests
     replace it with a barrier, so the interleavings are deterministic, not
     timing-based.
   - **`write(path, record, *, flush=True)`:**
     1. Validate. On a failure nothing is written.
     2. Under `flock`: compare with the visible version (the M6 view: L plus
        the outbox) through `wins()`, with the live identity. A loss →
        `STALE_RUN:<path>`. A record whose own `task_created_at` does not match
        a known live task → `IDENTITY_MISMATCH:<path>`, and it is not written.
     3. tmp + fsync + `os.replace`, then a directory fsync. Release the lock.
     4. Optionally `flush()`.
   - **`flush()`**, one operation per attempt, up to 8 attempts with jitter:
     1. Snapshot the outbox under the lock: `{path: (bytes, sha256)}`.
     2. Resolve L (`after_resolve_local`).
     3. **Local-only mode:**
        1. Apply the outbox onto `tree(L)` through `wins()`. Losers are
           `SUPERSEDED`.
        2. `build_commit(L, ...)`, then `cas_local(L_ref, new, L)`.
        3. `CONFLICT` → the next attempt.
     4. **Remote mode:**
        1. Probe. ERROR → retain.
        2. PRESENT → `fetch_pinned` (`after_pin`), and that sha is R. ABSENT →
           R = None.
        3. **`integrate(R)` explicitly** (round 6), then re-resolve L, which now
           contains R. `INTEGRATE_FAILED` → retain, with no publish built on a
           store that lacks R.
        4. If local work is pending (M3: L is not an ancestor of R), compute the
           M4 replay tree through `merge_path` over `merge-base --all(L, R)`,
           and the commit shape. Otherwise the base tree is `tree(R)`.
        5. Apply the outbox on top through `wins()`. Losers are `SUPERSEDED`.
           An entry byte-identical to R's blob is already published and needs
           no commit.
        6. Build the commit:
           - with no changed paths and no Δ, push nothing;
           - with Δ only, a single merge base B, and R == B, the commit is L
             itself;
           - otherwise a new commit, whose parents are R, plus L when Δ is
             non-empty.
        7. `cas_push(commit, base=R)`, leased. `CONFLICT` → the next attempt,
           which re-resolves L and re-pins R. `ERROR` → retain.
        8. On `OK`: `advance_ref` O, then **`integrate(pushed)`**
           (`before_bookkeeping`). This merges with any concurrent reader's
           absorb.
     5. A run that exhausts its attempts, or hits an `ERROR`, writes
        content-conditional `.err` sidecars and reports `RETAINED:<n>|<reason>`.
        Any R it did fetch was already integrated in step 4.3, so the observed
        records are kept. The local work stays pending for the next flush.
     6. **Clearing (the round-6 invariant):**
        - published entries are removed only when `integrate(pushed)` returned
          `INTEGRATED`;
        - superseded and already-published entries only when `integrate(R)`
          did.
        Each removal happens under the lock, only if the entry's sha256 still
        equals the snapshot's (`before_removal`); a rewritten entry survives.
        On `INTEGRATE_FAILED`, everything is kept, and the run reports
        `RETAINED:<n>|integrate_failed`.

     The report lines are `PUBLISHED:<n>`, `SUPERSEDED:`, `RETAINED:`,
     `UPGRADED:<n>`, `UPGRADE_INCOMPLETE:` and `NOTHING_TO_FLUSH`.
     - `UPGRADED:<n>` is printed when a run published a non-empty Δ, following
       the D1 vocabulary.
     - A divergence of L is never terminal: `integrate()` absorbs it. Only O,
       which is advisory, can report `OBSERVED_DIVERGED:` after an outside
       rewrite of the remote. It is then reset to the pinned tip, which is safe
       because O is not data.
   - **`read(no_fetch=False)`** → `Snapshot(store_state, base_sha, files,
     pending_paths)`. The refresh runs at most once per process.
     - On a successful pinned fetch: `advance_ref` O, then `integrate(R)`
       (M2). The snapshot reads the L sha that `integrate` left, plus the outbox
       (M6), never a re-resolved ref. `INTEGRATE_FAILED` →
       `stale:integrate_failed@<ts>`, reading the current L.
     - The states:
       - `local_only` reads L.
       - `fresh@<ts>`.
       - `empty`: ABSENT with no L and no outbox, recorded in `fetched_at`.
         ABSENT with an L reads as `fresh@<ts>` with every path marked
         `pending_push`.
       - `stale:<reason>@<fetched_at|never>`: a failed fetch, or `no_fetch`,
         while L exists. It reads L.
       - `unreachable:<reason>`: a failed fetch with no L, so there is no data.
         A clone that never fetched but holds local-only data therefore reads
         `stale:…@never`, because it has data.
     - The outbox overlays through identity-first `wins()`. `pending_push` is
       set per M6. A malformed blob or entry → `CORRUPT:<path>`,
       never silently skipped.
   - **`relations(task_id, snap)`** → `Rel(from, to, type, description, basis,
     evidence, record_task, direction_label, freshness, pending_push)`.
     - Forward ∪ reverse, with both ends canonicalized through the fold map. A
       self-collapsed relation is dropped.
     - Identity: a record whose `task_created_at` differs from the live task is
       dropped, and so is a relation end whose candidate `created_at` differs.
     - An end that names an id existing nowhere is filtered.
     - The result is deduplicated on `(from, to, type, record_task)`.
   - **`freshness(rel, record, snap)`** →
     `fresh|stale:source_changed|stale:target_changed|unverified:source_baseline|unverified:target_baseline`,
     source end first.
     - The body baseline is always the index's normalized body digest.
     - The plan baseline is the approval stamp's `plan_sha256` (identity-checked)
       when present, else the index's plan digest.
     - An `UNREADABLE` baseline → `unverified:*`, never `fresh` (finding 16).
   - **`analysis_line(task_id, snap, relations_state)`** →
     - `unknown(store_unreachable)`;
     - or `analysed:<n>(stage=S[,stale][,partial])`, from an identity-valid
       record;
     - or the `job_state(task_id)` hook. It returns None here; t1981_3 replaces
       it with `pending(..)` / `failed(..)`;
     - or `disabled`, or `never`.
   - **`relations_state()`** → `host_off` / `enabled` / `disabled`, from
     `relations.enabled` in `project_config.yaml` (through
     `config_utils.load_yaml_config`) and `AIT_RELATIONS`.
   - **`gc(dry_run)`:**
     1. If `index.errors` is non-empty → `GC_REFUSED:scan_incomplete`.
     2. Candidate ids: those that appear on the branch or in the outbox but in
        no `TaskIndex` entry and no fold-map entry.
     3. Confirm each through `aitask_query_files.sh`, which gives the
        two-negative existence set (finding 5).
     4. Identity candidates: paths whose `task_created_at` differs from the live
        task's.
     5. **Per CAS attempt** (findings 13 and round 8), in this order:
        1. Pin R, then `integrate(R)`, then `index.refresh(selected ids)`.
        2. Build the **effective tree E**, exactly the tree the commit will be
           built from: the M3/M4 replay result (or `tree(R)` / `tree(L)`) with
           the outbox applied. It is computed once and kept as an immutable
           `{path: blob}` map.
        3. Re-check each selected path against **E's blob at that path**, never
           R's or the outbox's alone, with the refreshed identity. A path
           stays selected only if E's record is deletion-eligible. Otherwise
           it is preserved and reported `GC_KEPT:<path>|revalidated`. That
           covers a valid replacement from the remote, from a local-only commit
           in L, or from the outbox.
     6. `build_commit` from **that same E** with the still-eligible deletions
        (no recomputation in between), then a leased CAS, then
        `integrate(pushed)`. In local-only mode, E is `tree(L)` plus the
        outbox, and the commit goes through `cas_local` on L.
     7. Outbox entries for eligible paths are removed content-conditionally,
        only after their own eligibility re-check, and only after
        `integrate(pushed)` returned `INTEGRATED`.
     The reports are `GC_REMOVED:<path>|<reason>`, `GC_KEPT:`, `GC_NONE` and
     `GC_REFUSED:`. This is the documented single-writer exception, and the
     module header says so.

5. **`lib/relations_cli.py`** and **`aitask_relations.sh`** (new; the wrapper is
   a shebang, `set -euo pipefail`, `python_resolve.sh`, and `exec`).
   - Verbs: `show <id> [--json] [--no-fetch]`, `why <a> <b> [--no-fetch]`,
     `status`, `flush` and `gc [--dry-run]`. An unknown verb prints usage and
     exits 2.
   - Every reader output starts with `RELATIONS_STATE:`, then `STORE:`, then
     `ANALYSIS:` (per task; `status` prints no `ANALYSIS:`).
   - `show` prints `REL:<direction>|<type>|<other>|<freshness>[|pending_push]`
     plus an indented description and bases. `--json` gives the same as one
     object. `status` prints `OUTBOX:<path>|age=<s>|err=<..>`.
   - Exit codes: 0 ok; 1 for a usage or validation error; 3 for `RETAINED` /
     `GC_REFUSED`.
   - `ait` dispatcher: a `relations)` case next to `note)` / `artifact)`, plus
     one help line.

6. **Whitelist:** `aitask_audit_wrappers.sh apply-helper-whitelist
   aitask_relations.sh`, then `audit-helper-whitelist` reports no `MISSING:`.

7. **CLAUDE.md:** one pointer: "Read `aidocs/framework/task_relations.md` when
   editing the relations store, worker, triggers or consumers
   (`lib/relations_*.py`, `lib/orphan_ref_store.py`, `aitask_relations.sh`)."

### Post-phase (risk mitigations)

8. **store_api_contract.** Add a "Store API" subsection under D1 "Module" in
   `aidocs/framework/task_relations.md`, describing the current state only:
   - the public functions: `write(..., flush=)`, `flush()`, `read()`,
     `relations()`, `freshness()`, `wins()`, `digests()`, and the `job_state`
     hook;
   - the report vocabulary.

   Amend in the same edit:
   - D2: `task_created_at` on the approval stamp, the obsolescence record and
     the dismissal;
   - D1 newest-wins: identity first;
   - D11: the `unverified:*` freshness marker;
   - D1 modes, reader refresh and upgrade, replaced by the M1–M6 ref model:
     - the local branch as the durable latest-known store, fast-forward only;
     - the tracking ref is not used;
     - L resolved before R;
     - the three-way replay against the merge base, through the `merge_path`
       table, with deletion eligibility as gc's rule;
     - `integrate()` as the only path by which remote commits enter L, with
       absorb merges over `merge-base --all`;
     - the outbox clearing invariant;
     - the observed ref, used only for `pending_push`;
     - leased pushes;
     - `stale:…@never` for local-only data.

## Verification

- `tests/test_relations_store.py` (unittest, no `chdir`).
  - Each case builds a scratch repo plus a bare `origin`, with
    `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, a scratch `HOME`
    and `AITASKS_HOME` unset.
  - Fixtures: `aitasks/` and `aiplans/` trees with loose archives, a numbered
    `_b0/old0.tar.zst`, and a legacy `old.tar.zst` built with `zstd` (skipped
    with a reason when `zstd` is absent).
  - Interleavings go through `_test_hook` barriers.
  - Cases:
    - local-only;
    - unreachable remote: retained with an `.err`, listed by `status`, then
      published after the URL is fixed, with the `.err` removed;
    - a two-clone CAS race;
    - newest-wins: `SUPERSEDED` at flush, and `STALE_RUN` at write;
    - **a replacement child with no gc in between** (finding 12): an old
      incarnation's stage-2 record is published, and the reused id's stage-1
      record then wins at `write` (no `STALE_RUN`), at `flush` (no
      `SUPERSEDED`), in the overlay and in `relations()`. Also: a record for a
      dead incarnation → `IDENTITY_MISMATCH`;
    - **gc retry revalidation** (finding 13): gc pauses at `gc_after_select`,
      a producer publishes the replacement and gc resumes. The replacement is
      kept (`GC_KEPT:`), and a genuinely obsolete sibling path is still
      removed;
    - **same-clone ref bookkeeping** (M2): publisher A pushes C1 and pauses at
      `before_bookkeeping`; B pushes C2 and finishes; A resumes. L is still C2,
      and a reader reports both records as `fresh`. Also: a reader whose pinned
      fetch predates C2 does not rewind L;
    - the removal interleaving on both removal paths (the `before_removal`
      hook rewrites the entry, and it survives);
    - `unreachable` vs `stale` (including `@never` with local-only data) vs
      `empty` vs `fresh`;
    - digest normalization (implementation notes and header edits leave the
      plan digest unchanged; a `## Gate Runs` entry leaves the body digest
      unchanged);
    - **the upgrade and the ref model** (M1–M6):
      - **remote absent:** L is pushed (the branch-must-be-absent lease), and
        the next flush reports no `UPGRADED`;
      - **independent histories, remote present:**
        - the merge has both parents;
        - local paths are on the remote, and remote-only paths are kept;
        - L is an ancestor of the remote tip;
        - a second flush replays nothing;
        - after a remote `gc` deletes a record that came from the local
          history, later flushes and reads do not resurrect it;
      - **a local descendant, with an empty outbox** (round 4):
        1. Both sides start at R.
        2. Remove origin.
        3. Write and flush a record locally, so L extends R and the outbox is
           empty.
        4. Restore origin, with the remote unchanged.
        5. Flush: L itself is pushed (a fast-forward, leased on R), the record
           is on the remote, and `UPGRADED:1` is printed.
        Variant: the remote moved meanwhile. Then the three-way merge is used,
        and both sides' changes survive;
      - **local → remote → local** (round 4):
        1. Start local-only, then upgrade.
        2. Publish more records in remote mode, including one written by
           another clone and fetched here.
        3. Run `git remote remove origin`, which drops the tracking ref.
        4. Read: `STORE:local_only`, and every record is present, including the
           post-migration and the fetched ones;
      - **the snapshot race** (round 3):
        1. Flusher F pauses at `after_resolve_local`, and in a second run at
           `after_pin`.
        2. A cleanup publishes descendant C, which deletes record X, and L
           advances to C.
        3. F resumes. There is no replay of stale content, X stays deleted, and
           F's push is rejected by its lease and rebuilt on C;
      - **two upgraders in one clone,** interleaved by hooks: exactly one replay
        lands, and the other finds Δ empty after re-pinning;
      - **the lease:** a commit built on R whose second parent contains the
        moved tip C is rejected (`CONFLICT`);
      - **`merge_path` table:** every row is a unit test, with `wins()` never
        called with `None`. Criss-cross rows with two bases are covered too:
        "untouched" requires equality with every base. **Zero-base cases**
        (round 7), through the real normalization from an empty
        `merge_bases()` result:
        - a local-only path (`l` present, `r=None`) keeps `l`;
        - a remote-only path keeps `r`;
        - a conflict where both are present and `l` should win (newer, or the
          live identity) resolves through `wins()` to `l`;
        - `merge_path` called directly with `bases=[]` raises;
      - **publish vs read absorb** (round 6), interleaved by hooks:
        1. Writer W pins R and L, builds P with the combined tree plus outbox
           record X, and pauses at `after_pin`, before its push.
        2. A concurrent `read()` absorbs R into L as A.
        3. W pushes P and runs `integrate(P)`: an absorb merge of A and P,
           with no error.
        4. Only then does W clear X's outbox entry.
        5. Then a failed-fetch read, then `git remote remove` and a local-only
           read: X is visible in both.
        Control: monkeypatch `integrate` to return `INTEGRATE_FAILED`. X's
        entry is kept (`RETAINED:…|integrate_failed`) and is still visible, and
        the next flush clears it without a new commit;
      - **divergent fallback continuity** (round 5):
        1. Write and flush one record locally, in local-only mode.
        2. Another clone publishes an independent remote record.
        3. Restore origin and do a successful `read()` without flushing. Both
           records are shown, L is an absorb merge, and only the local record
           is `pending_push`.
        4. Make the fetch fail: `STORE:stale`, and both records are still
           present.
        5. Run `git remote remove origin`: `STORE:local_only`, and both are
           still present.
        6. Restore origin and flush: only the local record is replayed, and the
           remote record is not duplicated or rewritten;
      - **offline gc vs a valid remote replacement** (round 5):
        1. Clone A, offline, gc-deletes an old child incarnation's record.
        2. Clone B publishes a valid record for the reused child id at the
           same path.
        3. Reconnect A, then read and flush. The replacement stays visible and
           survives on the remote, and A's deletion is not replayed. A control
           with an unchanged remote path applies the deletion;
      - **gc vs a local replacement** (round 8):
        1. R holds an obsolete incarnation's record at path p.
        2. Clone A, in local-only mode, commits a valid replacement for the
           reused child id at p into L, and its outbox drains.
        3. Reconnect A and run `gc`.
        4. The R blob qualifies for deletion, but E's does not:
           `GC_KEPT:<p>|revalidated` is printed, and the replacement survives
           both in L and on the remote after the push, with an empty outbox.
        Control: the same setup without the local replacement deletes p;
    - the outbox overlay (`pending_push`);
    - forward ∪ reverse;
    - folded canonicalization (`folded_into`, and an archived primary's
      `folded_tasks` in the legacy bundle);
    - freshness, both `stale:*` markers plus the stamp baseline;
    - **a bundled task keeps its stale marker** (finding 16): a body edit after
      analysis gives `stale:target_changed`, and the marker stays after the
      task moves into a numbered bundle and into the legacy bundle. An
      unreadable baseline gives `unverified:*`;
    - **legacy and numbered bundles tested separately** (finding 15): a task
      only in the legacy `old.tar.zst` is indexed, keeps its relations, and is
      not gc-eligible. A duplicate id across sources follows the precedence
      rule;
    - `gc` with an archived, a bundled (numbered and legacy) and a deleted
      id, the identity mismatch, and `GC_REFUSED` on a corrupt bundle;
    - schema rejections, including a missing `task_created_at` on each kind.
- `tests/test_relations_cli.sh`: the state lines for disabled / host_off /
  empty / stale / local_only, `show --json`, `status`, `flush` exit code 3 on
  retain, and an unknown verb. It uses `assert_counters_init` / `_load`
  (t1207).
- Run:
  - `bash tests/run_all_python_tests.sh --test-dir <scratch dir with the new module>`;
  - `bash tests/test_relations_cli.sh`;
  - `bash tests/test_helper_whitelist_coverage.sh`;
  - `bash tests/test_touchpoint_count_contract.sh`;
  - `shellcheck .aitask-scripts/aitask_relations.sh`.
- No test touches the real `aitask-relations` branch or `~/.aitask*`.

## Risk

### Code-health risk: medium
- The CAS classification relies on git's porcelain and stderr for a
  non-fast-forward push. A misclassification retries on an auth failure or
  retains on a race. · severity: medium · → mitigation: inline pre-phase probe_git_ref_states
- New concurrency surfaces: the flock with content-conditional removal,
  fast-forward-only ref bookkeeping, and gc revalidation. They are
  load-bearing for every later child, and a defect silently loses or rewinds
  data. · severity: medium · → mitigation: covered by the hook-driven
  deterministic interleaving tests in Verification (no separate mitigation)

### Goal-achievement risk: medium
- The store API is designed before its main consumers (t1981_3, t1981_5)
  exist. · severity: medium · → mitigation: inline post-phase store_api_contract
- The schema extends D2: `task_created_at` on all four kinds, plus the
  `unverified:*` freshness marker. Siblings planned against the old D2 need to
  learn of it. · severity: low · → mitigation: inline post-phase
  store_api_contract (the doc amendment), plus a Step 8e note to t1981_3 and
  t1981_5
- The scope is wide for one child. · severity: low · → mitigation: none (the
  sequencing lands the plumbing and schema testable first)

Reassessed with the inline phases and the review fixes in place, both levels
stay medium.

### Planned mitigations
- timing: pre-phase | name: probe_git_ref_states | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: CAS outcome misclassification (code health) | desc: Record the real git exit codes and stderr for an absent-ref fetch, an unreachable ls-remote, a non-fast-forward push, a stale update-ref and merge-base --is-ancestor; pin them in the orphan_ref_store docstring
- timing: post-phase | name: store_api_contract | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: store API designed before its consumers (goal achievement) | desc: Add a "Store API" subsection under D1 Module in task_relations.md, and amend D1/D2/D11 for identity-first ordering, task_created_at on all kinds, unverified:* and pinned/FF-only refs

## Step 9

Post-implementation per task-workflow Step 9: the archival and lock release of
this child.

## Post-Review Changes

### Change Request 1 (2026-11-06 11:00)
- **Requested by user:** six review findings, verify and address. Each was
  reproduced before it was fixed.
  1. `TaskIndex._add` read missing frontmatter as empty metadata, so gc could
     delete a folded child's record as `task_gone`.
  2. `_atomic_write` ignored short `os.write` returns.
  3. `Store.read` cached the whole snapshot.
  4. Decoded records were not schema-validated (a `KeyError` in
     `analysis_line`).
  5. The CLI chose a symmetric relation's `other` from the direction prose.
  6. `visible_no_lock` read every blob while holding the outbox lock.
- **Changes made:**
  1. Unreadable, missing, malformed or non-mapping frontmatter, and an
     unreadable `folded_tasks` / `folded_into`, now append to `index.errors`.
     That makes the scan incomplete: gc refuses, and `exists()` turns
     "unknown".
  2. `_atomic_write` loops until every byte is written. A 0 return or an error
     unlinks the temp file and raises, so the prior entry survives.
  3. `read()` caches only the refresh outcome (`_refresh`). The L + outbox view
     is recomputed on every call, and `empty` vs `fresh` is decided at view
     time.
  4. One `_decode(path, data)` (JSON plus `rs.validate`) and one `_replaces()`
     are now the only way any consumer or merge reads a record. Invalid blobs
     are reported as `CORRUPT:<path>|<reason>`, are never consumed, always lose
     to a valid record, and are never deletion-eligible. A damaged outbox entry
     is neither published nor cleared.
  5. `Rel.other` is computed from the queried task's canonical id. The CLI
     prints it.
  6. `orphan_ref_store.read_file()` reads one blob (one `ls-tree` of the path
     plus one blob read).
- **Tests:**
  - `ReviewFindingTests` adds 6 cases. Each is red-proven by reverting its fix
    in a scratch copy, and each fails on its assertion, not on an error.
  - The CLI test gains a symmetric-reverse check.
  - All 11 earlier guard mutants are still killed.
  - A full `TaskIndex` scan of this repository: 3128 tasks, 0 errors, 0
    duplicates, 43 folded ids, 1.4 s. The stricter rule does not make gc refuse
    spuriously here.
- **Files affected:** `.aitask-scripts/lib/relations_store.py`,
  `.aitask-scripts/lib/orphan_ref_store.py`, `.aitask-scripts/lib/relations_cli.py`,
  `tests/test_relations_store.py`, `tests/test_relations_cli.sh`.

### Change Request 2 (2026-11-06 11:40)
- **Requested by user:** three review findings, verify and address. All three
  were confirmed.
  1. `TaskIndex._add` iterated a non-list `folded_tasks: "22"` as `["2","2"]`
     (task_yaml passes non-lists through by design), so gc removed t22 as
     `task_gone`.
  2. The CLI built `Store(os.getcwd())` with a hardcoded `aitasks` project, so
     `mobile#1 -> mobile#2` showed as `aitasks#...`.
  3. `relations_schema.parse_ref` used its own grammar, not
     `cross_repo_notation.parse_ref`. It rejected `_mobile#1` / `-mobile#1`
     and accepted dotted names.
- **Changes made:**
  1. `folded_tasks` must be a list of int/str ids, and `folded_into` a str/int
     scalar. Anything else (string, mapping, nested list, bool) appends to
     `index.errors`, so the scan is incomplete and gc refuses.
  2. `Store(repo, project=None)` resolves `project.name` through the new
     `local_project_name()` (TASK_DIR-aware; same source as
     `trail_gather.local_project_name`). A missing or invalid name raises
     `ProjectUnresolved`, which the CLI reports as `PROJECT_UNRESOLVED`, exit 1.
     Every end is now a qualified ref:
     - only local refs go through the index and the fold map;
     - foreign ends keep their project, get `unverified:target_baseline`, and
       read `unknown(other_project)` in `ANALYSIS:`;
     - a record whose own task is foreign gets `PROJECT_MISMATCH:` at write and
       `CORRUPT:...|foreign_task_project` at read;
     - `show` / `why` accept bare or qualified ids, and `--json` carries
       `project`.
  3. `rs.parse_ref` delegates to `cross_repo_notation.parse_ref`.
     `rs.canon_ref` requires the local project. `rs.qref` normalizes qualified
     refs.
  - The design doc's Store API and D12 now state the project rules.
- **Tests:**
  - `ReviewRound2Tests` adds 4 cases. The grammar case checks our parser
    against the shared one over 13 inputs.
  - The CLI test adds the `mobile` project and `PROJECT_UNRESOLVED` checks.
  - All three fixes were red-proven by reverting each in a scratch copy. R7
    reproduces the reported `GC_REMOVED:records/t22.json|task_gone`.
  - All 11 original guard mutants and the 6 round-1 red proofs still fail as
    expected.
- **Files affected:** `.aitask-scripts/lib/relations_store.py`,
  `.aitask-scripts/lib/relations_schema.py`, `.aitask-scripts/lib/relations_cli.py`,
  `tests/test_relations_store.py`, `tests/test_relations_cli.sh`,
  `aidocs/framework/task_relations.md`.

### Change Request 3 (2026-11-06 11:55)
- **Requested by user:** an optional cleanup, confirmed:
  `orphan_ref_store.commit_tree_from_files` duplicated `build_commit`'s
  temporary-index and commit sequence.
- **Changes made:** it now delegates to `build_commit(repo, None, files,
  message, extra_parents=parents)`. With `base=None`, the only parents are
  `extra_parents`, in order. The interface is unchanged, and a value of `None`
  (a deletion, which has no meaning here) is refused.
- **Verification:** all store tests pass. A direct check confirms a two-parent
  merge keeps its parent order and exact tree.
- **Files affected:** `.aitask-scripts/lib/orphan_ref_store.py`.

## Final Implementation Notes
- **Actual work done:** everything in the approved plan landed. It covers the
  pre-phase probe, steps 2–7 and the post-phase doc step, plus the three review
  rounds above.
  - New modules:
    - `lib/orphan_ref_store.py`: plumbing. Leased push, `cas_local`,
      `advance_ref`, `fetch_pinned` into a temp ref, `merge_bases`, a
      temp-index `build_commit`, and the single-blob `read_file`.
    - `lib/relations_schema.py`: four kinds, each carrying
      `task_created_at`; the closed vocabulary; the impact-basis rule; the
      digest normalization; identity-first `wins()`; ref parsing through
      `cross_repo_notation`.
    - `lib/relations_store.py`: `Store` and `TaskIndex`.
    - `lib/relations_cli.py` and `aitask_relations.sh`: show / why / status /
      flush / gc.
  - Changed files:
    - `ait`: routing, a help line, and `relations` added to the update-check
      skip list.
    - The five helper-whitelist touchpoints, via `aitask_audit_wrappers.sh`.
    - `CLAUDE.md`: a pointer.
    - `aidocs/framework/task_relations.md`: a "Store API" section, a "Refs"
      section with the merge table, and amendments to D1, D2, D11 and D12.
    - `tests/test_metadata_writer_inventory.py`: `relations_store.py` pinned,
      with its reason.
  - Tests:
    - `tests/test_relations_store.py`: 47 cases, all deterministic, with
      interleavings driven by hook barriers.
    - `tests/test_relations_cli.sh`: 34 assertions.
- **Deviations from plan:**
  - Probe results (git 2.56.0):
    - a CAS miss in `update-ref` exits 128, like any other failure, so
      `cas_local` classifies it by re-reading the ref;
    - push conflicts show up as `!` porcelain lines reading `(stale info)` or
      `(non-fast-forward)`.
  - The flush always runs `integrate(R)` **before** building the publish. So
    the "two-parent merge on R" shape of M4 happens inside `integrate`'s
    absorb commit, never as a separate publish commit, and the pushed commit
    is always L or a child of L (a fast-forward of R).
  - Body digests strip edge blank lines. Cutting a framework section leaves
    its separating blank line behind.
  - `ait relations` skips the update check: every output must *start* with
    the state lines.
  - Review rounds 1–3 (see Post-Review Changes) added:
    - `_decode`-gated reads;
    - a refresh cache instead of a snapshot cache;
    - a full-write loop in `_atomic_write`;
    - incomplete-scan errors for unreadable or malformed metadata;
    - project identity from `project.name` (`ProjectUnresolved` /
      `PROJECT_MISMATCH`);
    - the shared ref grammar;
    - `Rel.other`;
    - one-blob reads under the outbox lock;
    - `commit_tree_from_files` delegating to `build_commit`.
- **Issues encountered:**
  - The full Python suite flagged `relations_store.py` in the metadata-writer
    tripwire. It is a read-only config reader whose writes are runtime state
    under `<git-common-dir>/aitask-relations/`, so it was pinned with that
    reason; the regex was not evaded. The config read now honours `TASK_DIR`.
  - The first R1 red proof produced a syntax error, not a failure, and was
    redone with a `pass` body.
  - After every fix the full Python suite passes.
- **Key decisions:**
  - `refs/heads/aitask-relations` is the durable latest-known store in both
    modes. The tracking ref is unused, because `git remote remove` deletes it.
  - Every outbox clear waits for `integrate()` to return INTEGRATED.
  - gc requires two negatives (a complete index scan with zero errors, plus
    `aitask_query_files.sh` NOT_FOUND) and decides on the effective tree.
  - An unreadable baseline is `unverified:*`, never `fresh`.
  - On this repository: a full index scan finds 3128 tasks, 0 errors and 43
    folded ids in 1.4 s, and `ait relations show <id> --no-fetch` takes about
    1.2 s.
- **Upstream defects identified:**
  - `tests/test_codeagent.sh:372` — `$(cd … && … || true)`, an unconfined
    and-chain cd that `tests/test_cd_guard_lint.sh` flags.
  - `tests/test_file_references.sh:372` — unconfined and-chain cd, flagged by
    the cd-guard lint.
  - `tests/test_premise_baseline_field.sh:24` — unguarded `cd /`, and no
    `enter_scratch_cwd` call.
  - `tests/test_premise_baseline_seeding.sh:32` — unguarded `cd /`, and no
    `enter_scratch_cwd` call.
  - `tests/test_label_yaml_words.sh:138` — changes cwd without calling
    `enter_scratch_cwd` first.

  These five make `test_cd_guard_lint.sh` fail at HEAD, independently of this
  task.
- **Notes for sibling tasks:**
  - Build only on the Store API (design doc D1 "Store API"):
    - `write(path, record, flush=False)` is the synchronous stamp write for
      t1981_3;
    - replace `relations_store.job_state` to report `pending(..)` /
      `failed(..)`;
    - read records only through `Store.read()` / `relations()`. Snapshot files
      are already schema-validated.
  - Every record needs `task_created_at` from the live task's `created_at`.
    Candidate `created_at` values must match too, or the end is dropped.
  - Build records with refs from `Store.ref()`. Never hardcode `aitasks#`:
    the project comes from `project.name`.
  - Use `relations_schema.digests()` for every digest. The plan digest
    ignores the YAML header and the Final Implementation Notes / Post-Review
    Changes sections.
  - `ANALYSIS:` can now also read `unknown(other_project)`, and freshness can
    read `unverified:*`. Consumers (t1981_5) must render both.
  - Tests:
    - use the `Env` / `record()` / `HookPlan` helpers in
      `tests/test_relations_store.py`;
    - every scratch repo needs `project.name` in its `project_config.yaml`;
    - never chdir.
