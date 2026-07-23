---
Task: t1210_2_trail_gatherer_and_drift_helper.md
Parent Task: aitasks/t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Sibling Tasks: aitasks/t1210/t1210_3_*.md … t1210_7_*.md (pending)
Archived Sibling Plans: aiplans/archived/p1210/p1210_1_trail_schema_library_and_validator.md
Worktree: (none — profile 'fast', current branch)
Branch: main (current branch)
Base branch: main
---

# Plan: t1210_2 — Trail gatherer and drift helper

## Context

**T2** of the Implementation Trails decomposition (RFC §14,
`aidocs/implementation_trail_design.md`; parent t1210). Builds the
deterministic, read-only **gatherer** (`snapshot` verb: scope/owner
resolution → normalized §8.1 input records → `input_digest`) and the
**drift checker** (`drift` verb: recompute the digest against a stored
trail and name the drift reasons). This is the riskiest spike of the
feature — digest normalization fidelity and named drift reasons — landed
before any skill (T3) or board (T4) work. t1210_1 landed the consuming
contract: `lib/trail_schema.py` owns the per-(kind, exists) input-record
table, `canonical_input_snapshot` / `input_digest`, and validation.

## Key design decisions

1. **Topic resolution: extract the board's topic seam, don't fork it.**
   The board's `_bare_topic_id` / `task_own_id` / `task_anchor_id` /
   `topic_key` (`.aitask-scripts/board/aitask_board.py:301-341`) plus the
   filename parser `TaskCard._parse_filename` (`:1239-1253`) move
   **verbatim** to a new stdlib-only module
   `.aitask-scripts/lib/topic_semantics.py` (`parse_task_filename` + the
   four functions, same names/signatures, duck-typed over objects with
   `.filename`/`.metadata`). `aitask_board.py` imports them from there
   (`TaskCard._parse_filename = staticmethod(parse_task_filename)`), so
   the existing `tests/test_board_topic_group.py` (which imports
   `topic_key` *from aitask_board*) keeps passing unchanged and
   divergence becomes structurally impossible — parity is the same
   function object, not a behavioral promise. The board file is not
   otherwise touched (no bindings/`check_action` surface, so no t1162_4
   collision).

   **Pinned topic-membership semantics (mirrors the board exactly):**
   - **Universe** = all active local tasks: parents (`<task_dir>/t*.md`)
     **plus children** (`<task_dir>/t<N>/t<N>_*_*.md`), phantom stubs
     dropped via `BOARD_KEYS` — verified identical to the board's
     By-Topic universe (`task_datas + child_task_datas`,
     `aitask_board.py:4895-4899`). `tasks_by_id` is built over that same
     universe, exactly as `_build_topic_lanes` does.
   - **Anchor normalization**: the gatherer parses frontmatter with the
     same `task_yaml.parse_frontmatter` the board uses, so scalar-anchor
     normalization (`t500` / `500` / int) is inherited, and
     `_bare_topic_id` strips the `t` identically.
   - **Inherited edge semantics** (same code path): child without anchor →
     parent's topic key when the parent is loaded; child whose parent is
     absent/archived (not in the universe) → clusters under the bare
     parent id; anchored task → the anchor's bare id even when the root
     task is archived (the key is an id, not a loaded object).
   - **Cross-project**: `topic_key` is a single-repo rule; topic-scope ids
     are local-only (decision 2 rejects cross-repo topic roots).
   - Parity fixtures for each of these states are in test matrix A, and a
     structural drift-guard test (matrix I) pins the extraction.

2. **Canonical refs everywhere.** All task refs are emitted in cross-repo
   canonical form `<project>#<id>` (bare id, no `t` —
   `aidocs/framework/cross_repo_references.md`). The local project name
   comes from `aitasks/metadata/project_config.yaml` `project.name`
   (missing → infra error, exit 3; the framework seeds it). An anchored
   `parse_ref()` is added to `lib/cross_repo_notation.py` (fullmatch twin
   of the existing unanchored `parse`), reused instead of a new regex.
   Cross-repo refs (`other#12`) resolve through
   `aitask_project_resolve.sh <name>` (subprocess, cached per project):
   `RESOLVED:<path>` → read that repo's `aitasks/` tree; `NOT_FOUND`/
   `STALE` → staged `ERROR:unresolved_project:<name>` (exit 0, no partial
   snapshot — the work_report staged-fail-closed pattern). Cross-repo
   **topic** roots are rejected (`ERROR:cross_repo_topic_unsupported:<ref>`)
   — v1 resolves topics locally only (scope-honest; membership scans of a
   foreign board are T3+ work if ever needed).

3. **Input records (what feeds the digest) — exactly the t1210_1 contract.**
   Per member task:
   - `task_file` record: `ref`, `exists: true`, `status` (frontmatter),
     `depends` (each entry normalized to canonical ref in the owning
     project's namespace when parseable; kept verbatim otherwise —
     deterministic either way), `gates_pending` = the `BLOCKED` list from
     `gate_ledger.archive_status_from_text` (enforced active set minus
     terminal-satisfied; `NO_GATES`/`ALL_PASS` → `[]`). One validated
     reader — no parallel gate parsing.
   - `plan_file` record **only when the plan exists**: `ref` =
     `<project>:<relpath>` (cross-repo file notation), `content_hash` =
     `sha256(bytes).hexdigest()[:16]`.
   - **Pinned plan resolver (mirrors `aitask_query_files.sh
     cmd_plan_file`, the canonical rule):** parent task `t<N>_*.md` →
     sorted glob `$PLAN_DIR/p<N>_*.md`; child task `t<P>/t<P>_<C>_*.md` →
     sorted glob `$PLAN_DIR/p<P>/p<P>_<C>_*.md`. First match wins;
     multiple matches → first + a stderr warning (deterministic either
     way). No match → **no record** (absent plan is not an input).
     Archived plans (`aiplans/archived/`) are **never** consulted: when a
     member archives, its plan moves there, so at drift time the stored
     plan input goes `input_missing` alongside the task-level
     `task_completed` — both honest. `PLAN_DIR` env honored (default
     `aiplans`); `TASK_DIR` via the existing `config_utils.task_dir()`.
   - **Generation invariant (documented in the module docstring): snapshot
     records only inputs that exist** (`exists: true` always at
     generation). `exists: false` appears only in drift recomputation,
     which is exactly what makes a deleted input change the digest.
     `boardidx`/timestamps are unrepresentable by the t1210_1 contract
     (unknown key = hard error) — the "boardidx change → no drift"
     guarantee.
   - No `board_state`/`gate_ledger` records are generated in v1 (board
     order is deliberately not semantic drift; gate state already rides in
     `gates_pending`). Drift still *accepts* stored trails carrying them
     (content-kind handling below).
   - Digest = `trail_schema.input_digest(records)` — the lib, never a
     reimplementation.

4. **Scope semantics.**
   - `--scope task <ids...>`: each id (local bare or cross-repo ref)
     names a task; members = the task + its active children
     (`<task_dir>/t<N>/t<N>_*_*.md`) for parents, just itself for a child.
     Owner = the single id (`OWNER:<ref>`), or `OWNER:none` when several
     ids were given (the skill picks — RFC J4).
   - `--scope topic <ids...>` / `--scope multi_topic <ids...>`: ids are
     topic roots (local only, decision 2); members = every task in the
     pinned universe (decision 1) whose `topic_key(task, tasks_by_id)`
     equals the root key. Owner = the root for a single topic, `none` for
     multi_topic.
   - **Owner handoff (`--owner <id>`, RFC J4):** optional on every scope,
     canonicalized and validated like any id (must resolve to an existing
     task, else staged `ERROR:unknown_task`); when given it overrides the
     default and is echoed as `OWNER:<ref>`. A multi-topic snapshot
     without `--owner` emits `OWNER:none` — the pinned meaning is "T3
     MUST obtain an explicit user owner choice before `ait artifact
     create`" (the substrate requires a task-owned handle); with
     `--owner`, the snapshot output is directly attachable. Both paths
     tested (matrix A2).
   - Unknown/missing local task id → staged `ERROR:unknown_task:<id>`.
   - `SCOPE:<kind>|<topic csv>` reports the canonical topic roots observed
     (for task scope: the members' own topic keys) — this is what T3 puts
     in `scope.topics`.
   - **Canonicalization rules (same command → same input set, always):**
     argv ids are canonicalized first, then deduplicated preserving first
     occurrence (the `_parse_csv` discipline); the member set is
     deduplicated by canonical ref (a task reachable via two ids appears
     once); topics csv, MEMBER lines, and INPUT lines are emitted in
     sorted order (decision 5). A topic root may be any bare id (parent
     or child — `topic_key` values are ids, not just parents); membership
     is `topic_key` equality only, never transitive expansion. A child
     member whose parent is absent stands alone (its records are its
     own). The complete structured-error vocabulary is pinned in the
     module docstring: `unknown_task`, `unresolved_project`,
     `cross_repo_topic_unsupported`, `unstable_repository_state`,
     `undriftable_input`, `ref_outside_project`, `invalid_trail`,
     `trail_unreadable`, `artifact_unresolved` — and `ERROR` paths emit
     **only** error lines (never a partial SCOPE/DIGEST or partial
     verdict).

5. **Snapshot line protocol** (work_report_gather style: `PREFIX:` +
   pipe fields, at most one free-ish field per record and always LAST;
   exit 0 for validation outcomes incl. `ERROR:` lines, 2 usage, 3 infra):

   ```
   SCOPE:<kind>|<topics csv>
   OWNER:<ref | none>
   MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<path>
   INPUT:task_file|<exists>|<status>|<depends csv>|<gates csv>|<ref>
   INPUT:plan_file|<exists>|<content_hash>|<ref>
   DIGEST:<hex>
   ERROR:<kind>:<id>            (staged — emitted alone, exit 0)
   ```

   **Deterministic ordering, pinned:** `INPUT` lines in the canonical
   record order (sorted by `(kind, ref)` — the same order the digest
   hashes); `MEMBER` lines sorted by ref; topics csv sorted. Two runs over
   unchanged state are byte-identical (tested).

   `MEMBER` lines give T3 the analysis context §7 promises (status,
   priority, effort, boardcol, labels, path) without agent free-reading of
   the board. Delimiter policy is the pinned t1162 rule enforced at the
   write site: enum-ish fixed-position fields (`status`, `priority`, …) go
   through the `_enum_field` absent→`unknown` / unsafe→`invalid` policy;
   list entries that would carry `,`/`|`/CR/LF are rendered `invalid` in
   the *line* while the *digest* uses raw values (transport is lossy for
   display, hashing is exact — documented); `ref`s must match the notation
   patterns and paths are refused (infra error) if record-breaking. The
   same write-site policy covers the drift surface: `DRIFT` `<detail>` is
   the free-text LAST field (CR/LF collapsed to spaces, `|` survives via
   fixed maxsplit) and `ERROR` ids are sanitized identically.

6. **Drift verb — digest for detection, named reasons only where sound.**

   **Trail loading boundary and error contract (stdout stays protocol-
   clean; consumers can always distinguish "unavailable" from a
   verdict):**
   - The `.sh` wrapper owns handle resolution (decision 7). The Python
     verb receives only a file path.
   - Unreadable path → stdout `ERROR:trail_unreadable:<path>`, exit 0.
   - Parse/validation failure (`trail_schema.load_trail` raised) → stdout
     single line `ERROR:invalid_trail:<issue_count>`, per-issue
     `INVALID:<path>|<rule>|<message>` details on **stderr**, exit 0.
   - `CURRENT` / `STALE` are emitted **only** for a schema-valid trail.
   - **Wrong-kind artifacts need no separate check:** the manifest stores
     no kind, but a non-trail document (generic artifact resolved via a
     handle) cannot pass `load_trail` — the pinned schema's required
     root keys, `schema_version` const, and `additionalProperties: false`
     reject it deterministically → `ERROR:invalid_trail`, never a
     freshness verdict. Fixture in matrix J (wrong-kind artifact through
     the real handle path).
   - Exit codes: 0 for every validation outcome (verdicts and `ERROR:`),
     2 usage, 3 infra — matching `snapshot`.

   **Driftable-input rule (every accepted kind has a defined resolver, or
   the verdict is refused):** the stored `generation.inputs` carry only
   ref/kind, so a live record can be recomputed honestly for exactly two
   kinds — `task_file` whose ref parses as a task ref (`parse_ref`), and
   `plan_file` whose ref parses as `<project>:<relpath>` file notation
   **and stays confined**: before any read, the relpath is joined to the
   resolved project root and realpath-resolved (symlink-aware); a result
   outside the project root (e.g. `proj:../../etc/passwd`) → staged
   `ERROR:ref_outside_project:<ref>` — parsing the notation is not a
   confinement check; the resolved-path containment proof is (the one
   file-read sink for untrusted refs, fixed at the sink; tested).
   Any other stored input — `board_state`, `gate_ledger`, `other`, or a
   `task_file`/`plan_file` ref that does not parse — has **no canonical
   live resolver**, and a digest recomputed without it would be a
   fabricated verdict. Drift therefore **fails closed**: staged
   `ERROR:undriftable_input:<ref>` (one line per offending input, exit 0,
   no CURRENT/STALE emitted). A parseable ref whose project cannot be
   resolved on this machine → staged `ERROR:unresolved_project:<name>`
   (same fail-closed reasoning — CURRENT must never be asserted over
   state that could not be read). v1 snapshot only ever generates the two
   driftable kinds, so gatherer-produced trails always drift-check;
   hand-authored trails with exotic inputs are refused with a precise
   protocol outcome. Tested (matrix D2).

   For a drift-checkable trail: recompute live records for the stored
   refs (missing → `exists: false`), and compare `input_digest` to the
   stored `generation.input_digest`.

   **Bounded stable-read policy (shared by snapshot and drift):** the
   record scan reads many live files with no atomicity guarantee, and a
   concurrent archive/plan-save/gate-append could yield a digest no real
   repository state ever had — worst at generation time, where the torn
   digest gets persisted. Both verbs therefore compute the record set,
   re-scan, and accept only when two consecutive scans produce the same
   digest (max 3 scans); still unstable → staged
   `ERROR:unstable_repository_state`, exit 0. Declared residual
   approximation (module docstring): two torn reads that happen to hash
   identically are indistinguishable from a stable state — the policy is
   churn *detection*, not isolation. Tested through an injectable scan
   seam (matrix L).

   **Version-compatibility contract (version lock, not a runtime
   mapping):** the digest hashes `NORMALIZATION_VERSION` into its bytes,
   and the stored trail persists **no** normalization provenance — so no
   runtime table can prove which normalization produced a stored digest.
   The sound guarantee is a **lock**: a `NORMALIZATION_VERSION` bump MUST
   ship with a `schema_version` bump (pinned contract, enforced by a
   tripwire test — matrix M asserts the runtime pairing
   `schema const 1.0.0 ↔ NORMALIZATION_VERSION 1.0.0`; bumping one
   without the other turns the suite red). Under the lock, every trail
   that passes validation (schema const) was digested under the
   runtime's own normalization — comparable by construction — and an
   old-schema trail after a future bump fails validation →
   `ERROR:invalid_trail`, a clear "not comparable / unavailable"
   outcome, never a false STALE and never a hidden incompatibility.
   Historical-schema loading (keeping old trails drift-checkable across
   a major bump) is a T1-follow-up if ever needed — recorded in
   notes-for-siblings, not smuggled into T2.

   Output: `CURRENT` or `STALE`, then
   `DRIFT:<code>|<task_ref or ->|<detail>` lines (codes from the schema
   enum), then `DIGEST:<live hex>`.

   **Canonical reason ordering + dedup (deterministic output for
   identical state, regardless of traversal order):** reasons are
   deduplicated by `(code, task_ref)` — when multiple triggers produce
   the same key, the **lexicographically smallest sanitized detail
   survives** (pinned tie-break, so traversal/discovery order can never
   select the output text) — and emitted sorted by `(code, task_ref)`.
   Multiple simultaneous changes all appear (aggregation never drops a
   code); two runs over identical state are byte-identical, tested with
   the multi-change fixture AND a duplicate-key fixture fed in reversed
   discovery order (matrix G).

   **Trigger matrix (evidence → exact trigger, one row per emittable
   code; "input" = a stored `task_file` input unless noted):**

   | Code | Evidence read | Trigger |
   |---|---|---|
   | `task_folded` | live/archived frontmatter | `folded_into` present or status `Folded` (checked **first**) |
   | `task_completed` | live/archived frontmatter | else: active with status `Done`, or archived with status `Done` |
   | `task_archived` | archive lookup | else: found only in archive, status ≠ `Done` |
   | `task_deleted` | active + archive lookup | else: in neither tree |
   | `status_changed` | live frontmatter vs entry `snapshot.status` | inequality (active, non-terminal inputs with a matching entry) |
   | `dependency_changed` | live `depends` vs `snapshot.depends` | set inequality (canonical refs) |
   | `gate_state_changed` | live pending set vs `snapshot.gates_pending` | set inequality |
   | `plan_changed` | per-member plan-identity compare (stored ref belonging to the member vs current resolver result); residual attribution | appeared (none→some), renamed/moved (path differs), **or** sole content-kind candidate under residual attribution |
   | `input_missing` | filesystem | non-task stored input unreadable/absent |
   | `new_related_task` | scoped-universe scan vs baseline | unreferenced universe task matching topic or depends trigger |
   | `other` | residual attribution | substitution digest proves an unattributed change with ≥2 candidates, or reconstruction incomplete (detail names them) |

   The four existence-class rows are mutually exclusive per input (first
   match in table order wins); the three snapshot-comparison rows fire
   only for **active, non-terminal** inputs (so a task now `Done` yields
   `task_completed` alone, never also `status_changed`); `task_deleted`
   vs `input_missing` never overlap (disjoint by input kind: task_file
   vs non-task). Scans are independent of both. Newly discovered related
   tasks participate as **reasons only** — the digest recompute uses the
   stored refs exclusively, and new tasks join `generation.inputs` when
   the refresh (T3) regenerates the trail, never during a drift check.
   This matrix is reproduced in the module docstring as the pinned
   contract.

   **Emittable-code contract:** a pinned module constant
   `GATHERER_DRIFT_CODES` = {`task_completed`, `task_archived`,
   `task_deleted`, `task_folded`, `status_changed`, `dependency_changed`,
   `gate_state_changed`, `plan_changed`, `new_related_task`,
   `input_missing`, `other`} — a strict subset of the schema enum.
   `premise_invalidated` is **excluded from the gatherer contract**: it is
   a reasoning/evidence judgment the refresh agent (T3) authors, not a
   comparison this helper can honestly compute — a deterministic premise
   verdict would violate the RFC's own §7.5 anti-fabrication rule, and
   the alternative (a machine-readable premise record with a checkable
   predicate) would require a schema change, which T1 pinned and T2 must
   not reopen (rejected alternative). Documented in the module docstring;
   tested (matrix D: every member of `GATHERER_DRIFT_CODES` is producible,
   the set is ⊆ the schema enum read from the schema file, and
   `premise_invalidated` ∉ the set).

   **This is an explicit scope amendment, not a silent narrowing — and
   not a schema change.** The schema's `drift_reasons` enum is untouched:
   a trail may still carry `premise_invalidated`, written by the T3
   refresh agent, and every downstream consumer (board badge, refresh
   summaries) keeps reading the full enum. Only the *deterministic
   helper's emission set* is narrower — which the RFC itself demands
   (§7.5 anti-fabrication: the helper must not assert judgments it
   cannot evidence). Sign-off chain: the parent task t1210 (which
   authored the RFC) and this task are owned in this repository, so the
   user approving this plan **is** the parent/RFC-owner sign-off; the
   decision is then durably recorded by (1) implementation **step 0**
   amending the task file's AC wording (committed via `./ait git`)
   *before* coding, (2) the plan's notes-for-siblings flagging the RFC
   §8.2 wording for T6's doc-sync, and (3) an explicit note to T3 that
   `premise_invalidated` authorship is a refresh-skill responsibility.
   If the user instead wants a deterministic producer, that requires a
   machine-checkable premise record — a schema change owned by a
   T1-follow-up task, not silently smuggled into T2 (rejected here).

   Reason derivation:
   - **Existence-class (task_file inputs; sound under the generation
     invariant of decision 3):** live file gone everywhere →
     `task_deleted`; found archived (via `archive_iter.
     find_archived_markdown_by_id`) with status Done → `task_completed`,
     archived otherwise → `task_archived`; `folded_into`/status Folded
     (active or archived) → `task_folded`; active with status Done →
     `task_completed`. Non-task inputs live-missing → `input_missing`.
   - **Snapshot-anchored (per RFC "drift anchor"):** for a task_file input
     whose ref matches a wave entry, compare live vs `entry.snapshot`:
     `status_changed`, `dependency_changed` (set compare of canonical
     refs), `gate_state_changed` (set compare of `gates_pending`).
   - **Digest-independent scans (run on every drift check, even when the
     digest matches — this is what catches work created *after*
     generation, which stored inputs by construction cannot see):**
     - **Pinned discovery universe — all scoped project roots, not just
       local:** the scanned projects are the distinct namespaces
       appearing in `scope.topics` ∪ entry task refs ∪ stored `task_file`
       input refs. For each, the universe is that project's active tasks
       (parents + children, phantom stubs dropped — the decision-1 rule
       applied at that root). An unresolvable scoped project → staged
       `ERROR:unresolved_project` (fail-closed: freshness is never
       asserted over a tree that could not be scanned — consistent with
       the digest recompute, which needs the same root anyway). Archived
       tasks are excluded everywhere (completed work is not "new related
       work").
     - **Pinned baseline (what counts as already-known):** the trail's
       referenced set = stored input task refs ∪ entry `task`s ∪
       exclusion `task`s ∪ observation `affects`.
     - `new_related_task`: a universe task **not** in the baseline whose
       qualified topic key matches a root in `scope.topics` **or** whose
       `depends` (canonicalized) intersects the **persisted member set =
       stored `task_file` input refs ∪ entry task refs** (RFC: "depending
       on a member" — a gathered input that never became an entry is
       still a member whose new dependents matter; exclusions are
       deliberately NOT targets, the trail already rejected that work).
       Both triggers run in every scanned project. **Pinned qualified-key
       serialization:** the comparison form is
       `<scanned-project-name>#<bare topic_key>` — built per scanned
       project — string-compared against `scope.topics` entries after
       canonicalization (`t` stripped). Identical numeric ids in two
       projects can therefore never cross-match: `projA#635` ≠
       `projB#635` (fixture pins both directions — same-number foreign
       topic does NOT fire; foreign root actually listed in
       `scope.topics` does).
     - `plan_changed` (identity-by-member comparison): **plan identity is
       the member task, not the stored path.** For each member task_file
       input, the stored plan ref *belonging to that member* is the
       stored `plan_file` input whose path matches the member's
       decision-3 glob pattern (`p<N>_*` / `p<P>/p<P>_<C>_*` under that
       project's plan dir); the live side is the resolver's current
       result. Compare per member: none→some ("plan appeared") →
       `plan_changed`; some→some with a **different path** (rename/move)
       → `plan_changed` (the old stored ref *additionally* yields
       `input_missing` — distinct codes, both kept); some→none →
       `input_missing` alone (already covered by the existence rule).
       This closes the rename gap: a renamed plan always produces
       `plan_changed`, never silently only `input_missing`.
   - **Residual attribution (runs on digest mismatch — never suppressed
     by task-level reasons, so simultaneous task+content changes all
     appear):** the trail stores no per-input hashes, but old *task*
     records are reconstructible from entry snapshots. **Candidates**
     are the content-kind inputs whose transition is NOT already
     attributed — an input that produced `input_missing` (exists flip)
     or an identity-attributed `plan_changed` (rename/appeared) is
     excluded, and because its old record (hash) is unreconstructible,
     any such attributed content transition makes the remaining check
     undecidable: **the substitution-digest check runs only when zero
     content transitions were already attributed**. When it cannot run
     AND unattributed content candidates remain, they are NOT silently
     dropped — re-gather would adopt their new hashes as the next
     baseline and the change would never be named — instead drift emits
     one conservative `other` reason whose detail names the remaining
     candidates as *unverifiable* ("attributed content transition made
     residual attribution undecidable; refresh must reanalyze these
     candidates"). It flags undecidability, never asserts a change
     (declared approximation; bounded to the
     multi-content-change-with-attributed-transition corner). When it runs and **every** stored `task_file`
     input has a complete matching entry snapshot (status + depends +
     gates_pending), compute a **substitution digest** over
     (reconstructed old task records + LIVE content records): equal to
     the stored digest ⇒ content inputs proven unchanged (no content
     reasons); unequal ⇒ a content input changed even though task-level
     reasons also fired — `plan_changed` for a sole candidate, else one
     `other` naming them. Reconstruction incomplete ⇒ undecidable:
     `other` listing the unattributable inputs (declared approximation,
     module docstring). Net pinned outcomes: status+plan-content change
     ⇒ BOTH `status_changed` and `plan_changed`; removed plan ⇒
     `input_missing` ALONE (never a speculative `plan_changed`/`other`),
     with complete or incomplete snapshots alike.
   - Verdict: `STALE` iff digest differs **or** any reason was found
     (digest-independent scans can fire alone — a CURRENT digest with a
     newly created related task still yields `STALE` +
     `new_related_task`; tested).
   - **Read-only, guaranteed:** the verb opens files for reading only;
     no cache, no stamp, no rewrite (negative-control test pins
     byte-identical trees).

7. **Bash entry `.aitask-scripts/aitask_trail_gather.sh`** — thin
   whitelistable wrapper mirroring `aitask_work_report_gather.sh`
   (`set -euo pipefail`, `aitask_path.sh` + `python_resolve.sh`,
   `require_ait_python`, `exec`), with one addition — the **handle
   resolution boundary**: for `drift --trail art:<handle>` it resolves the
   handle via `"$SCRIPT_DIR/aitask_artifact.sh" get <handle> --out <tmp>`
   (**`$SCRIPT_DIR`, never `./` — the wrapper's own location must not
   depend on cwd**; mktemp + trap cleanup — no `mktemp --suffix`, macOS)
   and passes the temp file to Python; a plain path passes through
   untouched.
   **Declared cwd contract (not pretended independence):** the helper —
   like `aitask_work_report_gather.sh` and `aitask_artifact.sh` itself,
   whose registry config path is cwd-relative — must be invoked with cwd
   at the project root (the `ait` dispatcher and skill convention);
   `TASK_DIR`/`PLAN_DIR` env override for tests. Stated in the wrapper
   header + module docstring. The integration test invokes the wrapper
   by **absolute path** with cwd = the synthetic repo root, proving no
   dependence on the wrapper's location (matrix J).
   **Protocol hygiene:** `cmd_get --out` prints `Wrote <path>` to stdout
   on success (verified in source), so the wrapper redirects the get
   call's stdout to stderr (`1>&2`) — the drift protocol stream must
   contain only protocol lines; the integration test asserts the
   **complete** stdout of a successful handle-path run byte-exactly.
   - `artifact get` failure (missing handle, corrupt manifest, missing
     blob) → stdout `ERROR:artifact_unresolved:<handle>`, the artifact
     CLI's own diagnostics forwarded to **stderr**, exit 0 — so a consumer
     always gets exactly one protocol token and can distinguish
     "trail unavailable" from `STALE`/`CURRENT`/`ERROR:invalid_trail`.
   - Python never learns about the artifact substrate.

8. **Whitelisting** (five surfaces, same rows as
   `aitask_work_report_gather.sh`): `.claude/settings.local.json`,
   `seed/claude_settings.local.json`, `seed/opencode_config.seed.json`,
   `.codex/rules/default.rules`, `seed/codex_rules.default.rules`.

## Files

- **New:** `.aitask-scripts/lib/topic_semantics.py` (extracted board seam)
- **New:** `.aitask-scripts/lib/trail_gather.py` (gatherer + drift lib, CLI)
- **New:** `.aitask-scripts/aitask_trail_gather.sh` (wrapper)
- **New:** `tests/test_trail_gather.py`
- **Modified:** `.aitask-scripts/board/aitask_board.py` (delete the four
  functions + `_parse_filename` body; import from `topic_semantics`)
- **Modified:** `.aitask-scripts/lib/cross_repo_notation.py` (add anchored
  `parse_ref`)
- **Modified (whitelists):** `.claude/settings.local.json`,
  `seed/claude_settings.local.json`, `seed/opencode_config.seed.json`,
  `.codex/rules/default.rules`, `seed/codex_rules.default.rules`

## Implementation steps

### 0. AC amendment (before coding — decision 6 approval trail)

Update `aitasks/t1210/t1210_2_trail_gatherer_and_drift_helper.md`: in the
Implementation plan bullet 4 and Verification, reword "each drift code
producible" to "each gatherer-emittable drift code (`GATHERER_DRIFT_CODES`)
producible; `premise_invalidated` is authored by the refresh agent (T3),
never the deterministic helper". Commit via `./ait git commit -m "ait:
Amend t1210_2 AC — premise_invalidated is refresh-agent-authored"`.

### 1. `lib/topic_semantics.py` + board delegation

Move `parse_task_filename` (from `TaskCard._parse_filename`),
`_bare_topic_id`, `task_own_id`, `task_anchor_id`, `topic_key` verbatim
(docstrings included). Board: replace definitions with imports; keep
`group_tasks_by_topic` and lane helpers in the board (widget-adjacent,
not needed here). Run `tests/test_board_topic_group.py` to prove parity.
**Ownership note (recorded in the module docstring):** the module carries
the board's by-topic semantics — any future change must keep
`tests/test_board_topic_group.py` AND trail_gather matrix A green in the
same commit; the board remains the semantic owner, trail_gather a
consumer.

### 2. `lib/cross_repo_notation.py::parse_ref`

`parse_ref(text) -> (project, task_id) | None` — fullmatch against the
canonical anchored pattern, `t` tolerated and stripped.

### 3. `lib/trail_gather.py`

Structure (work_report_gather conventions: module docstring pins the line
protocol, the emittable drift-code set, the generation invariant, and the
elimination bound; `EXIT_USAGE=2`, `EXIT_INFRA=3`; `sys.path` bootstrap
for `board/`):

- **Ref layer:** local project name loader (yaml via `config_utils`
  patterns), `canonical_ref(raw, default_project)`,
  `ProjectRoots` resolver cache shelling to `aitask_project_resolve.sh`.
- **Task tree loader:** `load_tasks(root)` → rows (`filename`, `metadata`,
  `path`, `ref`) over the pinned universe (parents + children, phantom
  stubs dropped via `BOARD_KEYS`, board-parity parse swallow —
  mirrors `work_report_gather.scan_tasks` plus children).
- **Plan resolver:** `plan_path_for(task_row)` per decision 3 (the
  `cmd_plan_file` glob rule).
- **Record builder:** `build_input_records(members)` per decision 3;
  `member_line`, `input_line` emitters with the delimiter policy.
- **Stable-read helper:** `stable_records(scan_fn, max_scans=3)` —
  digest-compared consecutive scans per decision 6; injectable `scan_fn`
  is the test seam.
- **`cmd_snapshot(args)`:** resolve scope (decision 4) → staged errors →
  stable-read → emit SCOPE/OWNER/MEMBER/INPUT/DIGEST in pinned order.
- **`cmd_drift(args)`:** load trail (decision 6 error contract) →
  driftable-input rule (fail-closed on unsupported kinds/refs) → stored
  inputs → stable-read recompute → reasons per decision 6 (scans over
  all scoped project roots) → CURRENT/STALE + DRIFT + DIGEST.
- **CLI:** argparse subcommands `snapshot` (`--scope`, ids) and `drift`
  (`--trail <path>`), `main(argv)` returning int (testable seam).

### 4. `aitask_trail_gather.sh`

Per decision 7; shellcheck-clean; header comment states it is an internal
skill helper not wired into the `ait` dispatcher.

### 5. Whitelist rows (decision 8)

### 6. `tests/test_trail_gather.py`

`unittest`, importlib-loaded lib (test_gate_ledger_python_parser pattern);
synthetic repos built in `tempfile.TemporaryDirectory()` with
`TASK_DIR`/`PLAN_DIR` env + cwd swap; trail fixtures constructed
programmatically from a minimal valid template and checked with
`trail_schema.validate_trail` before use (fixtures must be real trails).

- **A. Topic/scope parity fixtures (decision 1 states):** anchored task
  joins root's topic; explicit `t`-prefixed anchor normalizes; child
  without anchor + parent loaded → parent's key; child without anchor +
  parent archived/absent → bare parent id; anchored task whose root is
  archived → still keyed by the anchor id; task scope pulls active
  children; multiple task ids → `OWNER:none`; unknown id →
  `ERROR:unknown_task` alone.
- **A2. Owner handoff:** multi_topic without `--owner` → `OWNER:none`;
  with `--owner <valid id>` → `OWNER:<ref>` echoed; `--owner` naming a
  nonexistent task → `ERROR:unknown_task` alone; `--owner` overrides the
  single-topic default.
- **B. Records + digest ground truth:** snapshot INPUT lines match the
  §8.1 table; `DIGEST` equals `trail_schema.input_digest` recomputed
  in-test over independently constructed expected records (independent
  path, not the gatherer's own output).
- **C. Digest stability/sensitivity (negative controls):** boardidx
  change and `updated_at` change → identical digest + drift `CURRENT`;
  status flip / depends change / gate pending change / plan byte change /
  member file deletion → digest changes.
- **D. Drift codes — the pinned emittable set:** `GATHERER_DRIFT_CODES` ⊆
  the schema enum (read from the schema file) and excludes
  `premise_invalidated`; each member producible: `task_completed` (active
  Done; archived Done), `task_archived` (archived non-Done),
  `task_deleted`, `task_folded` (`folded_into`), `status_changed`,
  `dependency_changed`, `gate_state_changed`, `plan_changed` (content
  change via single-candidate elimination; plan-appeared scan),
  `new_related_task` (new anchored task; new task depending on an entry
  member; **new task depending on a non-entry input-only member** — all
  fired with an unchanged digest, pinning the digest-independent scan
  and the persisted-member target set), `input_missing` (deleted plan
  input), `other` (residual attribution with ≥2 content-kind candidates;
  reconstruction-incomplete case).
- **D2. Driftable-input rule:** a schema-valid trail carrying a
  `board_state` / `gate_ledger` / `other` input → staged
  `ERROR:undriftable_input:<ref>`, no CURRENT/STALE, exit 0; same for a
  `plan_file` ref that is not `<project>:<relpath>` notation; a
  `task_file` ref in an unregistered project → `ERROR:unresolved_project`
  (never a CURRENT verdict over an unreadable tree).
- **E. Plan-identity fixtures (decision 3 resolver + per-member
  compare):** parent plan resolves; child plan resolves
  (`p<P>/p<P>_<C>_*`); absent plan → no record; **removed plan →
  `input_missing` ALONE — asserted under BOTH complete and incomplete
  entry snapshots (pins the attributed-transition exclusion: no
  speculative `plan_changed`/`other`)**; renamed plan (the exact
  some→some transition) → `plan_changed` (identity-by-member path
  compare) AND `input_missing` (old stored ref), both present in one
  run; plan-appeared (none→some) → `plan_changed`; **two-plan
  remove-plus-edit (plan A removed, plan B content-edited)** →
  `input_missing` for A AND one `other` naming B as unverifiable (pins
  the conservative flag — B is never silently dropped); traversal ref
  `proj:../../…` → `ERROR:ref_outside_project` alone (containment
  negative control).
- **F. Presence tracking:** deleted stored input → recomputed record
  `exists: false` → digest differs (pins the §8.1 presence contract).
- **G. Protocol determinism + delimiter safety:** two snapshot runs over
  unchanged state byte-identical; INPUT lines in `(kind, ref)` order;
  status containing `|` → `invalid` in MEMBER/INPUT lines while the
  digest hashes the raw value (assert digest matches an
  independently-built record with the raw status); **multi-change drift
  determinism**: one fixture with 3 simultaneous changes (status flip +
  plan content edit + new related task) → ALL of `status_changed`,
  `plan_changed` (via the substitution digest — task reasons must not
  suppress it), and `new_related_task` in one run, exact expected DRIFT
  sequence, two runs byte-identical; **duplicate-key tie-break**: the
  same `(code, task_ref)` from two triggers fed in reversed discovery
  order → identical surviving detail (lexicographically smallest); DRIFT
  detail containing CR/LF → collapsed to spaces.
- **H. Read-only negative control:** sha256 the whole synthetic tree
  (trail file included) before/after a `drift` run — byte-identical.
- **I. Cross-repo:** second synthetic project registered via
  `AITASKS_PROJECTS_INDEX` temp registry; task-scope member resolves and
  gathers; unregistered project → `ERROR:unresolved_project`; cross-repo
  topic root at snapshot → `ERROR:cross_repo_topic_unsupported`;
  **foreign-project freshness**: a new task in the registered foreign
  project depending on a scoped member → `new_related_task` (pins the
  all-scoped-roots scan; digest unchanged); **qualified-key collision
  control**: both projects carry topic id `635`, a new task anchored in
  the foreign `635` does NOT fire when `scope.topics` holds only the
  local `635`, and DOES fire when the foreign root is listed (pins
  `projA#635` ≠ `projB#635`).
- **J. Trail loading / real entry point:** subprocess the real
  `./.aitask-scripts/aitask_trail_gather.sh`: `snapshot --scope task <id>`
  (exit 0, DIGEST line); `drift --trail <path>` (CURRENT); mutated
  fixture → STALE + expected code (proves the suite can fail); malformed
  trail JSON → stdout exactly `ERROR:invalid_trail:<n>` (details on
  stderr only); unreadable path → `ERROR:trail_unreadable`; handle form
  `--trail art:no-such-handle` → `ERROR:artifact_unresolved` on stdout,
  exit 0. **Positive handle resolution is mandatory** (the advertised
  happy path must be proven): the synthetic repo is `git init`-ed with a
  seeded `aitasks/metadata/project_config.yaml`, a real artifact is
  created via the real `aitask_artifact.sh create … --kind
  implementation_trail --handle art:trail-test` (local backend stores
  under the repo's data root in legacy mode), and the wrapper's
  `drift --trail art:trail-test` must produce a **byte-exact complete
  stdout** (`CURRENT` + `DIGEST:` lines only — pins the `Wrote <path>`
  redirection; artifact diagnostics allowed on stderr only). Any
  scaffolding failure here is an integration defect to fix in-task, not
  a skip. A
  second artifact holding a non-trail JSON document, resolved through
  the same handle path → `ERROR:invalid_trail` (wrong-kind fixture).
- **K. Board seam intact:** `aitask_board.py` contains
  `from topic_semantics import` and no local `def topic_key` (drift guard
  for the extraction).
- **L. Stable-read policy (injectable seam):** `stable_records` with a
  scan_fn returning (changed, then stable) sequences → converges, one
  output; permanently churning scan_fn → `ERROR:unstable_repository_state`
  after the 3-scan bound (at-bound and over-bound cases pinned).
- **M. Version-lock tripwire:** assert the runtime pairing — the lib
  schema's `schema_version` const is `1.0.0` AND
  `trail_schema.NORMALIZATION_VERSION == "1.0.0"` — with a comment
  pinning the contract (bump both or the suite goes red); plus an
  old-schema fixture (`schema_version: 0.9.0`) → `ERROR:invalid_trail`,
  never a CURRENT/STALE verdict (no false STALE across versions).

## Verification

- `python3 -m unittest tests.test_trail_gather -v` green.
- `python3 -m unittest tests.test_trail_schema tests.test_board_topic_group -v`
  still green (consumed contract + extraction parity).
- `bash tests/run_all_python_tests.sh` picks the new file up automatically.
- `shellcheck .aitask-scripts/aitask_trail_gather.sh` clean.
- Live smoke: `./.aitask-scripts/aitask_trail_gather.sh snapshot --scope
  topic 635` on this repo emits members + digest; run twice → identical
  bytes.
- Commit: `feature: Add trail gatherer and drift helper (t1210_2)`; then
  Step 9 (post-implementation): `./ait gates run 1210_2` (risk_evaluated
  via orchestrator), archive via `aitask_archive.sh 1210_2`.

## Out of scope (owned by siblings)

Skill flows and the single confirmed artifact write (T3); board By-Trail
view and refresh launch (T4/T5); docs (T6). In-flight/lock state and
archived-sibling landscape lines (RFC §7's richer context) are additive
protocol extensions T3 can request — v1 pins the records+digest+drift
core (additive-extension contract, no breaking re-shape).
`premise_invalidated` stays an agent-authored refresh code (decision 6).

## Risk

### Code-health risk: low
- Extracting `topic_key`/`_parse_filename` out of `aitask_board.py` touches a load-bearing board path; bounded by verbatim moves, re-export via import, and the existing `test_board_topic_group.py` running unchanged · severity: low · → mitigation: TBD
- New line protocol is a second delimiter-encoded surface; bounded by reusing the pinned t1162 write-site policy and tests for each field class · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- Drift attribution fidelity is the spike: the pinned schema stores no per-input state, so content-change attribution rests on the documented elimination bound and could under-name reasons on multi-input drift; bounded by the digest always detecting staleness, the digest-independent scans covering post-generation work, and the declared approximation in the docstring · severity: medium · → mitigation: TBD
- T3 consumes this protocol next; a shape T3 can't drive would force rework — bounded by pinning the protocol in the module docstring and additive-extension room (MEMBER context lines already included) · severity: low · → mitigation: TBD
