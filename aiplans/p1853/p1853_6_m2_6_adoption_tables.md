---
Task: t1853_6_m2_6_adoption_tables.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-19 10:12
---

# Plan: t1853_6 — M2.6 Adoption tables (verified 2026-10-18)

## Context

M2 (t1853) builds the test-map registry. M2.6 adds the **adoption ledger's data
half**:
- the `seeds` table (`registry/seeded.yaml`, machine-proposed edges that select but
  claim nothing);
- the `adopted` table (`registry/adopted.yaml`, provenance of machine-adopted
  stamped edges, with `by:`);
- the four read tables of `aitestmap/onboard.yaml`;
- the load rules `SEED_SHADOWED`, `ADOPTED_ORPHAN` and absent-`by:`-is-human;
- the **write routing** every later verb uses to touch the three files;
- `SEEDED:` / `ADOPTED:` on `check`;
- the fill of M2.2's post-re-stamp hook. An automated re-stamp refreshes the
  matching provenance row and keeps its `by:`. Only an explicit human actor deletes
  it.

Wave B. Providers M2.1 and M2.2 have landed. The work runs on the current branch
with no worktree (profile `fast`).

**Automation-first:** `by: human:<email>` is recorded data, never a gate. No path
here waits on a person.

## Step 0 — Reality check (EXECUTED 2026-10-18, HEAD 6f6d1ed79)

**Providers on main:**

| provider | landed | what the repository has |
|---|---|---|
| M2.1 registry core | t1853_1 `0d04347ab` | **Loader:**<br>• `registry.Load` dispatches `registry/*.yaml` in file-name order through `fileLoaders` (registration wins over the reserved list).<br>• `seeded.yaml` / `adopted.yaml` stay refused until registered.<br>• Every file passes `contractCheck` before its loader runs.<br>• Loaded data is kept in `Registry.Ext`.<br>• There is **no post-load phase**: shadow/orphan rules need every edge, and a hand file sorting after `seeded.yaml` loads later.<br>• Load returns early when `registry/` is absent.<br>**Check:**<br>• `RegisterRule` runs in registration order, which is Go file-name init order.<br>• Rule findings are counted into `CHECK:<status>\|<findings>\|<failing>`.<br>• There is no summary-line mechanism.<br>**Writers:** `Render` / `WriteFile` give deterministic writes, only on change. |
| M2.2 grammar + hook | t1853_2 `f096db065` | **Hook API:**<br>• `annot.RegisterRestampHook(func(ctx, root, Actor, []Restamp) error)`.<br>• It runs once, after every file was written, from `AnnotateWith` and `Verify`. It does not run after an earlier error.<br>• A hook error is `*HookError` → `RESTAMP_HOOK_ERROR`, exit 3.<br>**Actor** is Unspecified\|Human\|Agent\|Auto. `actorFlag` (in `cmd/.../annotate.go`) resolves `--by`, else `agent:$AIT_AGENT_STRING`, else Unspecified.<br>**`Restamp{Test, Source, File, Line, Before, After, State}`**: State is added\|restamped\|current. A `current` edge is still passed to the hook.<br>**`registry` cannot import `annot`.** |
| M2.3 deps | t1853_3 `2c04a9639` | `Restamp.Origin` (`scanner:from-body`); `--from-body` actor is `--by`, else agent, else **auto** (writes stamps today) |
| M2.5 scoped | t1853_5 `6f6d1ed79` | Pattern to follow: `ScopedOf(reg)` in `Ext`, loaders from `init()`, a per-run memo on `CheckContext`, `*InputError` passthrough. Its characterization test pins `check` output byte-exact |
| downstream writers (M4.2, M4.4, M6.x, M7.x, M8.2) | — | t1855 / t1857 / t1858 / t1859 are **not decomposed**, so no plan defines a routing need. The API is built from the proposal's routing list |
| parent anchors (`2fe3f8cb7`) | — | Re-verified: module, `internal/lineproto` exits (0/1/2/3/64/75), `testmap.Contract = 1`, the guards tripwire. `aitestmap/` is still absent in this repo |

**Differences** (*proposal / coarse plan / repository → decision*):

| # | proposal | coarse plan | repository | decision |
|---|---|---|---|---|
| A1 | a seed sharing `(test, covers)` with a stamped edge is "dropped at load" | same | `Load` has no post-load phase; file-name order puts hand files after `seeded.yaml` | **Adapt (named extension of M2.1):** add `registry.RegisterPostLoad(func(reg, root) error)`, run once after every file on both return paths. M2.6 computes shadow and orphan there |
| A2 | `onboard.yaml` is read "for status and readiness" | reader in `registry` | `Load` only reads `config.yaml` and `registry/` | **Adapt:** the post-load hook reads `aitestmap/onboard.yaml` when present (contract checked; only the four tables decoded; every other key is M6.1's and is ignored) |
| A3 | `SEEDED:` / `ADOPTED:` "informational" on `check` | — | findings count into `CHECK:` | **User decision:** always printed, as **summary lines** after the findings and before `CHECK:`. Not counted, never failing. `--json` gains `summary` |
| A4 | no severity for `SEED_SHADOWED` / `ADOPTED_ORPHAN` | — | — | **User decision:** both `Info` |
| A5 | "an automated re-stamp refreshes the matching row" | same | the adopted row schema has no field a re-stamp changes | **Revise proposal:** additive row field `stamp: <date>/<blob10>`. A refresh sets it. `by`, `origin`, `adopted_at` are kept |
| A6 | "a machine claim is never turned into a reviewed edge" | — | `--from-body` and agent `annotate` write **first stamps** with no provenance row, so they read as reviewed. There are two shapes, both with a zero `Before`: an inserted line (`InsertAfter` → `added`), and an existing **unstamped** covers line (`PlanCovers` returns `Replace` → `restamped`; `Verify` too) | **User decision + proposal revision:** an agent or `auto` actor's **first stamp** (`Before.IsZero()`, whatever the state) gets an adopted row `{origin: [<Restamp.Origin> or annotate], by, adopted_at, stamp}`, creating `adopted.yaml` if absent. Human and unspecified actors create no row. An edge that already carried a stamp never gains a row, so a reviewed edge is never relabelled |
| A7 | the stamping verbs print `WROTE:` per written file | — | the hook returns only `error`; an `adopted.yaml` write would be invisible to path-scoped commits | **Adapt (named extension of M2.2):** hooks return `([]string, error)`. The written paths are appended to `Result.Wrote` in write order (provenance before the test file when the intent phase wrote it) |
| A10 | M2.2's single post-write hook | — | the post-write hook alone cannot attribute first stamps safely: a provenance write that fails leaves the stamp, and the retry sees a non-zero `Before` (review finding) | **Adapt (named extension of M2.2): two phases.**<br>• `RegisterStampIntentHook` runs after planning and **before any `Apply`**, with the edges about to be written. An error there is `RESTAMP_HOOK_ERROR` with no test file touched.<br>• The post-write hook keeps its timing.<br>• M2.6 writes **creations in the intent phase** (provenance first) and **refreshes / deletions in the post phase**. Each failure point is retry-safe (step 5) |
| A12 | an unrelated adopted row stays byte-identical | same (task Verification) | a sorted whole-table re-render rewrites any noncanonical row (review finding) | **Adapt + user decision (narrower guarantee, 2026-10-19):** existing files are edited by text splicing.<br>• **Block-style:** untouched rows are byte-identical.<br>• **Flow-style or empty:** a touched table may be normalised. Unrelated row values, unknown fields included, are kept; other tables stay byte-identical; in-table formatting and comment loss is documented.<br>• The task's Verification text is aligned (step 6) |
| A13 | — | — | a partial reject leaves a queued seed for a rejected pair; a memo written first would hide an unfinished review (review finding) | **Adapt + proposal revision:** a per-route write order (completion memo last, replacing record first). A seed whose pair is rejected is excluded at classification and reported `SEED_REJECTED` (Info). `Adoption.Reviewed` is the memo lookup |
| A14 | `reviews[]` is "the verdict memo so a pair is read once per test blob per reader"; the packet selector starts from seeded candidates | — | a memo write that fails after a `verifies` adoption or a park cannot be recovered from `reviews[]` alone: the seed is gone or shadowed. A later human `verify` (or any route) that deletes or replaces the carrier would then erase the derived record too (review findings) | **Adapt + proposal revision:**<br>• The review record is derivable from the effect rows (replay data is required on them).<br>• `Reviews()` / `NeedsReview()` read memo ∪ derived.<br>• Review-route commits reconcile the memo.<br>• **Every** route's commit first preserves the unrecorded records whose carrier it destroys, writing `onboard.yaml` before anything else and refusing the destructive change if that fails.<br>• `REVIEW_UNRECORDED` (Info).<br>• M7.1 / M7.2 must use `RecordVerdict` and `NeedsReview` |
| A11 | — | — | `WriteFile` is an unconditional rename; nothing in the engine uses `platform.Lock` yet; a multi-file transition can stop part-way (review finding) | **Adapt:**<br>• Cooperating writers serialise on one `platform.Lock` in the git dir.<br>• The whole write set is validated and snapshot-checked before the first write.<br>• Files are written in a fixed fail-safe order.<br>• A failure after a write is `ADOPTION_PARTIAL`, and every op is idempotent, so re-running the verb converges.<br>• Hand edits are *detected* only, with no transactional promise (step 3) |
| A8 | adopted `confidence` is listed without `?` | — | a hook-created machine row has no measured confidence | **Adapt:** `confidence` is optional (absent means not measured) and range-checked when present |
| A9 | `by` is human/agent/auto | — | `annot.Actor` lives in `annot` | **Adapt:** a registry-side `By{Kind, Value}` with `ParseBy`. A rejection with absent `by` → `{Human, ""}` with `Recorded=false` |

**Ownership (step 6):** new files are all M2.6's:
- `registry/adoption.go`
- `registry/adoption_write.go`
- `registry/adoption_splice.go`
- `registry/rules_seeded_adopted.go`
- `annot/adoption_hook.go`
- their tests and testdata

Named extensions:
- M2.1's `load.go` (`RegisterPostLoad`)
- M2.1's `check.go` (`CheckRule.Summary`, `CheckResult.Summary`)
- M2.1's `cmd/.../scancheck.go` (summary printing)
- M2.2's `annot/hook.go` + `stampverbs.go` (intent phase, returned paths,
  completed writes surviving an error)
- M2.2's `cmd/.../annotate.go` `printStamps` (reporting completed writes on error)
- M2.2's test-only recording hook in `cmd/.../annotate_test.go`

No sibling is in flight on these files (t1853_4 is Ready; t1853_7 is a later repair task). The data worktree has another session's unstaged changes, so commits name only this task's paths.

## Implementation

### Pre-phase (risk mitigations)

1. [characterize_stamp_verbs_without_provenance] Before editing `annot/hook.go` /
   `stampverbs.go`, add `cmd/ait-testmap/stampverbs_characterize_test.go`:
   - Fixture: a repo with no `adopted.yaml`.
   - Pin byte-exact stdout, stderr and the exit code of:
     - `annotate --by human:x@example.invalid` (an add and a re-stamp);
     - `annotate` with an unspecified actor;
     - `verify --by human:…`, including a `current` edge;
     - `verify` unspecified;
     - `--json` variants of one annotate and one verify.
   - Also pin the resulting test-file bytes and the recording hook's calls (actor +
     edge states).
   - Run it green on the unmodified tree first. It must stay green **unchanged**
     after steps 2–5: none of these actors creates a row, so no
     `WROTE:…adopted.yaml` may appear.

1. **Post-load phase** (`registry/load.go`, extension):
   - `type PostLoader func(reg *Registry, root string) error`;
     `RegisterPostLoad(PostLoader)`.
   - `Load` runs every post-loader after the file loop, and also on the
     `registry/`-absent early return. Errors propagate unchanged (an
     `*InvalidError` / `*ContractMismatchError`).
   - Delete the `seeded.yaml` / `adopted.yaml` "refused until registered" cases
     from `load_test.go`, with a pointer to `adoption_test.go`.

2. **Tables + loaders** (`registry/adoption.go`, `init()` registers `seeded.yaml`,
   `adopted.yaml` and the post-loader):
   - `By{Kind ByKind; Value string}`, `ByHuman|ByAgent|ByAuto`, `ParseBy(s)`
     (`human:<v>` / `agent:<v>` / `auto`, same validity as `annot.ParseActor`),
     `String()`.
   - `SeedRow{Test, Covers string; Origin []string; Confidence float64; Evidence
     SeedEvidence; ProposedAt, Verdict string; Extra map[string]any \`yaml:",inline"\`}`.
     - `SeedEvidence{Static, Convention string; Cochange []string; Plan, Prose,
       Coverage, Observed string; AgentReview *AgentReview}`.
     - `AgentReview{Verdict string; AssertLine int; Rationale, By, Run, PacketSHA,
       TestBlob string; Unsure int; At string}`.
     - All yaml tags are snake_case per *Where state lives*; `omitempty` on every
       optional field.
   - `AdoptedRow{Test, Source string; Origin []string; Confidence *float64;
     AdoptedAt, Task, By, Run, Rationale string; AssertLine int; PacketSHA, TestBlob,
     SourceBlob, Stamp string; Evidence map[string]string; Extra map[string]any
     inline}`.
   - Onboard rows:
     - `Rejection{Test, Source, Reason, By, Run}`
     - `Review{Test, Source, Verdict, TestBlob, PacketSHA, Run, By}`
     - `KindProposal{Test, Kind, Reason, At}`
     - `Calibration{Run string; Agree, Disagree int; Ratio float64; GroundTruth,
       At string}`
   - **Validation** (one function per row type, `validateSeed` / `validateAdopted` /
     …, reused by the writer so a written file always loads; a failure is
     `REGISTRY_INVALID:<path>|<table>[<n>]: <reason>`):
     - `test` is `ParseID` with no `@variant`; `covers` / `source` are `checkPath`;
     - `origin` is non-empty; `confidence` is in [0,1];
     - dates are `YYYY-MM-DD`; `verdict` ∈ {"", verifies, drives, unsure};
     - adopted `by` is required and must pass `ParseBy`; `stamp` matches
       `<date>/<hex10>`;
     - a review verdict ∈ {verifies, drives, unsure}; a kind proposal's `kind` is
       `ValidKind`;
     - a duplicate `(test, covers)` within `seeded.yaml` or `adopted.yaml` is
       refused;
     - unknown top-level keys in `seeded.yaml` / `adopted.yaml` are refused; unknown
       row fields are kept in `Extra` and re-rendered (the additive contract).
   - **`onboard.yaml` reader:**
     - Path: `aitestmap/onboard.yaml`.
     - `testmap.CheckContract` runs first.
     - It decodes only `contract`, `rejections`, `reviews`, `kind_proposals` and
       `calibration`, and ignores every other key (`task`, `level` and `phases`
       are M6.1's).
     - A rejection with no `by` → `By{Human, ""}` with `Recorded: false`
       (absent-`by:`-is-human).
   - **`Adoption`** (in `Ext["adoption"]`, `AdoptionOf(reg)` never nil):
     - `Seeds`, `Shadowed` and `RejectedSeeds`; `Adopted` and `Orphans`;
     - `Onboard OnboardTables`;
     - `Classify(stamped map[[2]string]bool)`, which splits raw rows with the
       shadow, rejected-seed (A13) and orphan rules.
     - The post-loader classifies against `reg.Edges` that are `Stamped()` (the
       persisted map). `check` re-classifies against live edges.
   - **Lookups for consumers:**
     - `AdoptedFor(test ID, source) (AdoptedRow, bool)`
     - `SeedsCovering(source) []SeedRow`
     - `Rejected(test, source) (Rejection, bool)`
     - `Reviews() []Review`: the `reviews[]` memo ∪ records derived from effect rows
       (A14)
     - `Reviewed(test, source, testBlob, by) bool` and
       `NeedsReview(test, covers, testBlob, reader) bool` (the packet selector's
       eligibility predicate), both over `Reviews()`
     - `Counts() (seeded int, c AdoptedCounts{Total, Human, Agent, Auto int})`

3. **Write routing** (`registry/adoption_write.go`):
   - `type Route string`, one per verb row of *Registry loader → write routing*:

     | route | allowed ops |
     |---|---|
     | `RouteOnboardSeed` | seedPut |
     | `RouteAttributePropose` | seedPut |
     | `RouteAdoptAgentVerdicts` | recordVerdict only (it performs seedRemove / seedReview / adoptedPut / reviewAdd itself, with replay data required, and reconciles missing memo rows) |
     | `RouteCalibrate` | calibrationAdd |
     | `RouteAdoptClass` (incl. `--auto`) | seedRemove, adoptedPut |
     | `RouteAdoptRow` (per-row / `--area --batch` / in-gate person row) | seedRemove, adoptedDelete |
     | `RouteAnnotateAuthor` | adoptedPut |
     | `RouteOnboardReject` | seedRemove, rejectionAdd |
     | `RouteClassifyPropose` | kindProposalAdd |
     | `RouteRestamp` (`verify`, `annotate`, `--from-body`, `stale --confirm-source`) | adoptedPut, adoptedRefresh, adoptedDelete |

   - **Coordination: `OpenAdoption(ctx, root string, r Route) (*AdoptionTx, error)`**
     - First it takes an exclusive `platform.Lock` on
       `<git-dir>/ait-testmap/adoption.lock`. The git dir comes from
       `git rev-parse --absolute-git-dir` through `gitx.Repo.Run`. The lock is per
       worktree and never in the work tree, so nothing new appears in
       `git status`.
     - The lock is held until `Commit` or `Close` (always deferred by callers;
       `Close` is idempotent). flock is released if the process dies.
     - **Only after holding the lock** does it read the three files raw, keeping a
       snapshot of their bytes. Every engine writer of the three files goes through
       this API, so cooperating writers are serialised and read each other's
       committed state: no lost update.
     - It refuses a newer `contract:` with `*ContractMismatchError`, so a newer file
       is never overwritten.
     - It refuses an invalid file with `*InvalidError`.
   - **Ops.** Each refuses outside its route with `*RouteError{Route, Op}` →
     `ADOPTION_ROUTE:<route>|<op>`, exit 3. Every op is **idempotent by key**, so
     re-running a verb after a partial failure converges:
     - `PutSeed`: replace by `(test, covers)`.
     - `SetSeedReview(test, covers, AgentReview, origin)`: sets `verdict` and
       `evidence.agent_review`; the origin is added once.
     - `RemoveSeed` and `DeleteAdopted`: absent is a no-op.
     - `PutAdopted`: replace by `(test, source)`.
     - `RefreshAdopted(test, source, stamp)`.
     - `AddRejection`: replace by `(test, source)`.
     - `AddReview`: replace by `(test, source, test_blob, by)`, which is the memo key
       "once per test blob per reader".
     - `AddKindProposal`: replace by `test`.
     - `AddCalibration`: replace by `run`.
     - `ApplyRestamps(phase, by By, known bool, edges []RestampEdge{Test, Source,
       Before, After string; Origin string})` holds the provenance rule (step 5).
   - **`Commit() (wrote []string, err error)`, all under the lock:**
     1. **Prepare the whole write set before any mutation.** Validate every row of
        every changed table with the step-2 validators, render each changed file,
        and re-read every file to be written. Any snapshot mismatch (a
        non-cooperating hand edit since open) is `*AdoptionConflictError` →
        `ADOPTION_CONFLICT:<path>`, exit 75, **with nothing written**.
     2. **Write in a per-route order.** The order is chosen per route, not one
        global order, by two principles:
        - a **completion record** (the `reviews[]` memo) is written **after** the
          effects it certifies;
        - a **record that replaces a queue entry** (a rejection, a provenance row)
          is written **before** the queue removal.

        | route | file order | why |
        |---|---|---|
        | `RouteOnboardReject` | `onboard.yaml` (rejection) → `seeded.yaml` | the decision is durable before the seed leaves the queue |
        | `RouteAdoptAgentVerdicts` | `adopted.yaml` → `seeded.yaml` → `onboard.yaml` (`reviews[]` memo **last**) | the memo makes the selector skip the pair, so it may exist only after the verdict, park or adoption it records |
        | `RouteAdoptClass`, `RouteAdoptRow` | `adopted.yaml` → `seeded.yaml` | the provenance change comes before the queue removal |
        | single-file routes | that file | — |

        On every route, a non-empty carrier-preservation set P (A14) prepends an
        `onboard.yaml` write to this order. A route test pins each order, with and
        without P. Each file is written atomically
        (`WriteFile`: temp file + rename), only when changed. A file whose table
        is empty is never created.
     3. **Partial failure + bounded recovery.** A failure after ≥1 file was written
        is `*AdoptionPartialError{Wrote, Failed, Err}` →
        `ADOPTION_PARTIAL:<failed>|<wrote,…>`, exit 3. Each reachable intermediate
        state is made **equivalent to completion for every reader**, or is
        **re-selected by normal re-entry**. Idempotent ops alone are not relied
        on:
        - **`reject`** (rejection written, seed removal failed): classification
          **excludes a seed whose pair is in `rejections[]`**. It neither selects
          nor counts, and `check` reports it as `SEED_REJECTED:<test>|<covers>`
          (Info). `PutSeed` (seed / propose routes) skips a rejected pair. So the
          stranded seed behaves as rejected everywhere, and the next reject, or
          any seed route's commit, removes it.
        - **`--agent-verdicts`: the review record is recoverable from its
          effects** (A14):
          - **Replay data lives on every effect row.** A parked or below-threshold
            seed carries `evidence.agent_review {verdict, by, run, packet_sha,
            test_blob, at}`. A `verifies`-adopted row carries
            `{by, run, packet_sha, test_blob}` and implies verdict `verifies`.
          - **Caller contract.** On this route the low-level ops are not callable.
            The route exposes one op, `RecordVerdict(VerdictRecord{Test, Covers,
            Verdict, Review AgentReview, Adopt *AdoptedRow})`. It refuses missing
            replay data with `ADOPTION_ROUTE:…|replay-data`: `by`, `run`,
            `packet_sha` and `test_blob` are required, and an `Adopt` row must carry
            the same four. It then applies the effects itself:
            - adopt → `PutAdopted` + `RemoveSeed`;
            - `verifies` below `accept_min` → seed review;
            - `drives` / `unsure` → park;
            - plus the memo row.
          - **Reads take the union.** `Adoption.Reviews()` = `reviews[]` ∪ the
            records derived from effect rows (deduplicated by
            `(test, source, test_blob, by)`). `Reviewed(…)` and the selector's
            eligibility predicate `NeedsReview(test, covers, testBlob, reader)` read
            that union. `NeedsReview` is true exactly when the pair is a live seed
            (not shadowed or rejected) and no review exists for those test bytes by
            that reader. M7.1's packet selector must use it, never `reviews[]`
            directly (note to t1858).
          - **Reconcile.** Every commit on this route back-fills `reviews[]` rows
            for derived records missing from it. `check` reports each missing row
            as `REVIEW_UNRECORDED:<test>|<source>|<test_blob>|<by>` (Info) until
            then.
          - **Carrier preservation, on every route — the lifetime rule.** A derived
            record lives only as long as its carrier row. So every `Commit`, on
            **any** route including `RouteRestamp`, preserves it in the prepare
            step. It computes **P** = the records derivable from the
            **pre-mutation** state that have no `reviews[]` row **and** whose
            carrier this commit destroys or changes. A carrier is destroyed or
            changed when:
            - `RemoveSeed` / `DeleteAdopted` removes it;
            - `PutSeed` / `SetSeedReview` replaces a seed whose
              `evidence.agent_review` differs or is dropped;
            - `PutAdopted` replaces a row whose review fields
              (`by`, `run`, `packet_sha`, `test_blob`) differ.

            `RefreshAdopted` changes only `stamp`, so it never destroys a carrier.
            When P is non-empty:
            - the memo rows for P are added to `onboard.yaml` and **written first,
              before any other file of the commit**;
            - if that write fails, nothing destructive has happened. The commit
              returns the error with **no other file written**: the destructive
              change is refused, and a retry converges;
            - this is an implicit op on every route, `reviewPreserve` (not
              callable), so `RouteRestamp` and the seed routes may write
              `onboard.yaml` for this purpose only;
            - on `RouteAdoptAgentVerdicts`, when the preservation write and the
              new verdict's memo both touch `onboard.yaml`, both renders are
              prepared up front. The preservation render is written first, then
              the effects, then the render that adds the new memo (memo last
              still holds).

            An empty P writes nothing extra, so `onboard.yaml` stays
            byte-identical.
          - **Resulting partial states:**
            - **memo write fails after a `verifies` adoption** (seed removed):
              derived from the adopted row, so the pair is not re-read and the
              record is not lost;
            - **seed removal fails** (seed shadowed): `NeedsReview` is false and
              the record is derived;
            - **memo write fails after a park**: derived from the seed, so the pair
              is not re-read for the same test bytes. Changed test bytes make it
              eligible again, as the proposal intends.

            In every case the next commit on the route restores the memo.
        - **per-row adopt:** the provenance row is deleted and the seed is still
          queued. It is shadowed by the person's stamp.
     4. **What is promised.** Cooperating engine writers are serialised. A
        non-cooperating hand edit is *detected* when it lands before step 1's
        re-read. One that lands between that re-read and the rename is not
        detected. The doc comment and README say so: there is no cross-file
        atomicity and no transaction claim.
   - **Rendering — untouched rows are preserved byte-for-byte (text splicing, not
     re-rendering):**
     - **A new file** renders canonically, sorted by (test, covers/source):
       `{contract: 1, seeds|adopted|<onboard key>: [...]}` behind a
       `# Written by ait-testmap. Change it through the onboard / annotate verbs.`
       header (no header for `onboard.yaml`).
     - **An existing file** is edited by `registry/adoption_splice.go`:
       1. Parse it to `yaml.Node` only to locate each row of the touched block
          sequence. A row's byte range runs from its first head-comment line (or
          its `- ` line) up to the next row's range, or the end of the sequence.
       2. A deleted row's range is cut. A touched row's range is replaced by that
          row alone, rendered canonically at the sequence's own indentation. A new
          row is inserted before the first row whose key sorts after it, else
          after the last row.
       3. **Every other byte is copied verbatim:** untouched rows with their
          quoting, field order and comments, other top-level keys (M6.1's
          `phases`), and the header.
       4. A key absent from `onboard.yaml` is appended as a new block at the end.
     - **Guarantee, by layout (user decision, A12):**
       - **Block-style table:** every untouched row is **byte-identical**, and so
         is every byte outside the touched rows.
       - **Flow-style table, or an empty one:** that key's sequence **may be
         normalised** to a canonical block sequence when it is edited.
         - Every unrelated row keeps **all its values**: known fields, the unknown
           fields carried in `Extra`, and their order of keys.
         - Its quoting, flow layout and comments inside that table are **lost**.
         - Other top-level keys and tables in the file stay byte-identical.
         - The doc comment, the README write-routing row and the proposal state
           this loss.
       - A **touched row's** own representation is always canonicalised (its
         values are kept, and unknown fields are kept).
     - **Prepare step:** the spliced bytes are re-parsed and run through the
       step-2 validators before any write, so a splice that would produce an
       invalid or differently-meaning file is refused with nothing written.
   - **Test seams** (package vars): `afterLock func()` and
     `writeFile = WriteFile`.

4. **Check integration:**
   - `registry/check.go` (extension):
     - `CheckRule.Summary bool`. A summary rule's findings go to `CheckResult.Summary`
       (json `summary`, always an array). They are never failing and never counted.
   - `cmd/ait-testmap/scancheck.go`:
     - prints findings, then summary lines, then `CHECK:`;
     - the doc comment and the `check` README row are updated.
   - `registry/rules_seeded_adopted.go` registers, after core and scoped (file-name
     order), from one per-run memo that classifies the tables against `liveEdges()`
     `Stamped()`:
     - `SEED_SHADOWED:<test>|<covers>` (Info);
     - `SEED_REJECTED:<test>|<covers>` (Info; a queued seed whose pair is in
       `rejections[]`);
     - `REVIEW_UNRECORDED:<test>|<source>|<test_blob>|<by>` (Info; a review
       derived from an effect row with no `reviews[]` memo row);
     - `ADOPTED_ORPHAN:<test>|<source>` (Info);
     - summary `SEEDED:<n>` and `ADOPTED:<n>|human <h>|agent <a>|auto <m>` (counts
       exclude shadowed and orphaned rows);
     - an exported `AdoptionSummary(a *Adoption) [][]string` that M4.2's
       `stale --all` reuses.

5. **Hook fill — two phases, provenance first:**
   - **`annot/hook.go` + `stampverbs.go` (M2.2 extension):**
     - `RestampHook` returns `([]string, error)`.
     - New `RegisterStampIntentHook(h IntentHook)`, with the same signature. It is
       called **once per invocation, after every target was planned and before the
       first `Apply`**, with the edges that will be written (states `added` /
       `restamped`; `current` edges are not written, so they are not passed). It is
       skipped when there are none.
     - `AnnotateWith` calls it between planning and `beforeApply` / `Apply`. `Verify`
       calls it after its planning loop and before its write loop.
     - An intent error → `*HookError` (`RESTAMP_HOOK_ERROR`, exit 3) with **no test
       file touched**.
     - Paths from both phases are appended to `res.Wrote` in write order:
       intent-phase paths, then test files, then post-phase paths.
     - **Completed writes survive an error.** Today an `Apply` error returns a nil
       result, and `printStamps` prints only the error line. On a hook error the
       test file is already unreported, and the intent phase would make
       `adopted.yaml` unreported too. Change:
       - `AnnotateWith` / `Verify` track the paths actually written so far (intent
         paths, each test file whose `Apply` returned `changed`, post paths).
       - On **any** error after ≥1 write they return a non-nil
         `res = {Wrote: <completed paths>, Incomplete: true}` alongside the error,
         with **no** `STAMP` / `STAMP_SKIP` / `STAMP_REFUSED` lines, so no stamp is
         reported that did not land. `Result.Incomplete` is json
         `incomplete,omitempty`.
       - On an error with nothing written the result stays nil, so the output is
         unchanged.
       - `cmd/ait-testmap/annotate.go` `printStamps`: when `err != nil` and
         `res != nil && len(res.Wrote) > 0`:
         - line mode prints `WROTE:<path>` per completed write on stdout, with no
           `STAMPS:` summary;
         - `--json` emits the result object (`wrote`, `incomplete: true`, empty
           stamp arrays);
         - then the error line on stderr, with the error's own exit code (75
           `REWRITE_CONFLICT`, 3 otherwise).
         - The `annotate` / `verify` README rows state this.
     - The post hook keeps its timing and its "not after an earlier error" rule.
     - The recording hook in `cmd/.../annotate_test.go` returns `nil, hookFail`.
   - **`annot/adoption_hook.go`** (`init()` registers both phases). Each phase
     converts `Actor` → `registry.By` (Unspecified → `known=false`) and the edges,
     opens `RouteRestamp`, calls `ApplyRestamps(phase, …)`, then `Commit`. It opens
     nothing when the phase's rule selects no edge, so `adopted.yaml` is never
     touched needlessly. The rule, per edge matched by `(Test.String(), Source)`:
     - **Intent phase (before the test file is written):** for an **Agent / Auto**
       actor and an edge whose `Before` is zero — a **first stamp**, whether it is
       an inserted line (`added`) or an existing unstamped line (`restamped`):
       - `PutAdopted` the row `{test, source, origin: [Origin|"annotate"],
         adopted_at: After.Date, by, stamp: After}`;
       - if a row already exists (a retry), keep its `by` / `origin` /
         `adopted_at` and set only `stamp`.
       - Nothing else is written in this phase.
     - **Post phase (after every file was written):**
       - **Human** → delete the matching row (all states; `current` included,
         because a person's `verify` confirmed it).
       - **Agent / Auto / Unspecified**, row present → `stamp` = After; `by`,
         `origin` and `adopted_at` are kept. A no-op when the intent phase already
         set it.
       - **Never:** creating a row for an edge whose `Before` was non-zero. A stamp
         without a row is reviewed or pre-existing, so it is never relabelled.
         Unspecified first stamps get no row (the actor may be a person).
     - **Failure points, and why each is retry-safe:**
       - **(a) The intent commit fails:** no test file is touched and the error is
         `RESTAMP_HOOK_ERROR`. The retry re-plans the same first stamp.
       - **(b) The intent succeeds and `Apply` fails** (conflict, I/O): the row
         names a stamp that never landed. That is an `ADOPTED_ORPHAN` (Info), which
         over-attributes a machine claim that does not exist: the safe direction.
         The retry sees `Before` still zero, re-puts the same row with the new
         stamp, and writes the file. If the run is abandoned, the orphan stays
         reported.
       - **(c) The files are written and the post phase fails:**
         - a human deletion fails → the row stays on a person's stamp (still
           attributed to the machine, the conservative direction). Re-running the
           human `verify` sees the edge `current` and deletes it. When the row
           carries an unrecorded review, the deletion first preserves it in
           `onboard.yaml` (A14). A failed preservation refuses the deletion, and
           `WROTE:` then lists the onboard file only if it was written;
         - a machine refresh fails → `stamp` is stale; the retry (`current`)
           refreshes it.
     - A re-stamp of an edge with no row, by any actor, leaves `adopted.yaml`
       byte-identical.

6. **Docs and contract:**
   - `goengines/README.md` `## Interfaces`:
     - an M2.6 tables row (schemas, `AdoptionOf`, lookups, load rules);
     - a write-routing row (route × op table, `OpenAdoption` / `Commit`, conflict
       and route errors);
     - the `check` row (summary lines);
     - the `annotate` / `verify` rows (hook paths in `WROTE:`).
   - Proposal (`aidocs/testing_engine/n014_explorer_006_proposal.md`, path-scoped
     `documentation:` commit):
     - *Where state lives*: the adopted `stamp` field and optional `confidence`
       (A5, A8);
     - *Registry loader*: the post-load rule, the summary lines and Info severities
       (A1, A3, A4), and machine adds getting provenance rows (A6);
     - the line-protocol index: `ADOPTION_ROUTE:`, `ADOPTION_CONFLICT:`,
       `ADOPTION_PARTIAL:`, `SEED_REJECTED` and `REVIEW_UNRECORDED`;
     - *Where state lives* and *Agent Review Pass*: review replay data required on
       effect rows; the memo as memo ∪ derived; `NeedsReview` as the selector's
       eligibility (A14);
     - the per-route write order and the rejected-seed read rule (A13);
     - untouched-row preservation (A12);
     - `annotate` / `verify` reporting completed writes on error;
     - the write routing: the lock, prepare-then-write, the fail-safe file order and
       the explicit "no cross-file atomicity" statement (A11);
     - the M2.2 hook paragraph: the intent phase before `Apply`, creations first,
       and paths returned (A7, A10).

   - **Task text alignment (A12):** update the Verification bullet of
     `aitasks/t1853/t1853_6_m2_6_adoption_tables.md`. It currently reads "in both
     the unrelated row is byte-identical". It becomes: "byte-identical when
     `adopted.yaml` is block style (the engine's form); value-identical, unknown
     fields included, when a hand-written flow-style table is normalised". Committed
     with `./.aitask-scripts/aitask_task_commit.sh` naming only that path.

7. **Notes** (`/aitask-note`, hedged, citing the landed SHA):
   - **t1855** (M4): `AdoptionOf`/`AdoptedFor` for `adopted(…)`; `AdoptionSummary`
     for `stale --all`; `RouteAttributePropose`; `stale --confirm-source` calls
     `OpenAdoption(RouteRestamp)` + `ApplyRestamps`.
   - **t1857** (M6): the routes for seed / adopt / reject / classify / calibrate.
     `onboard.yaml` is shared with M6.1, so M6.1 must keep the four keys (node-level
     edits). Person-only rejection is **not** enforced by the routing.
   - **t1858** (M7): `RouteAdoptAgentVerdicts` exposes only `RecordVerdict`, with
     replay data (`by`, `run`, `packet_sha`, `test_blob`) required. The packet
     selector (M7.1) must use `NeedsReview` / `Reviews()` (memo ∪ derived), never
     `reviews[]` alone. The `AgentReview` schema (`assert_line` int). `--author` through `AnnotateWith` with
     `Origin: "agent:author"` gets its row from the intent phase (first stamps only;
     an already-stamped pair needs an explicit `PutAdopted`); enrich it with
     `PutAdopted` on `RouteAnnotateAuthor`. Any machine adoption that rewrites a test
     file should go through `AnnotateWith` (provenance first) rather than writing the
     row after the file.
   - **t1859** (M8.2): the two lines are always present, as summary lines outside
     the `CHECK:` counts.
   - **t1853_7**: `ADOPTED_ORPHAN` has no repair verb; a repair route is needed.

### Post-phase (risk mitigations)

1. [e2e_adoption_lifecycle] Add `cmd/ait-testmap/adoption_e2e_test.go`. Drive the real
   verb table (`call`) with the real `annot.Source` and `runner.Lister` on a
   `fixture.New` repo whose `runners.yaml` binding lists the test and which has a
   `registry/seeded.yaml` seed `{tests/t.sh, src/a.sh}`. Steps:
   1. `scan --apply` + `check` → `SEEDED:1` and
      `ADOPTED:0|human 0|agent 0|auto 0`.
   2. `AIT_AGENT_STRING=x annotate tests/t.sh src/a.sh` →
      `WROTE:aitestmap/registry/adopted.yaml`, then `WROTE:tests/t.sh`.
   3. `check` without a re-scan → `SEED_SHADOWED:tests/t.sh|src/a.sh`, `SEEDED:0`,
      `ADOPTED:1|human 0|agent 1|auto 0`.
   4. Edit `src/a.sh`; `verify --by auto` → the row's `stamp` changes and `by` stays
      `agent:x`.
   5. `verify --by human:p@example.invalid` → the row is gone and `ADOPTED:0`.
   6. A second agent-adopted edge whose covers line is then removed by hand →
      `ADOPTED_ORPHAN:<test>|<source>`, and `check` still exits 0.

## Verification

- `registry/adoption_test.go`:
  - **load golden** (`testdata/adoption/`): a JSON dump of `AdoptionOf` for a fixture
    with `_scanned.yaml` + a hand file sorting after `seeded.yaml` + `seeded.yaml` +
    `adopted.yaml` + `onboard.yaml` covers both table merges, the shadow rule (a
    seed shadowed by a hand-file-independent stamped edge; an unstamped edge does
    **not** shadow), orphans, and absent-`by:` on a rejection;
  - every validator refusal;
  - per-file `contract: 2` refusal for all three files;
  - unknown row fields round-trip through a write;
  - `onboard.yaml` other keys/comments survive a write.
- **`by:` merge golden** (`testdata/adoption/by_merge.golden`): every cell of
  phase (intent / post) × existing row? (none / `by` human / `by` agent / `by` auto)
  × actor (Human / Agent / Auto / Unspecified) × state (added / restamped / current)
  × `Before` (zero / stamped) → the resulting row or no row. Impossible combinations
  (`added` with a stamped `Before`; `current` in the intent phase) are omitted.
- `registry/adoption_write_test.go`:
  - table-driven over every route × every op: allowed ops succeed, every other op is
    `ADOPTION_ROUTE`;
  - each op applied twice equals once (idempotence);
  - goldens for the rendered `seeded.yaml` / `adopted.yaml`;
  - no file is created for an empty table.
  - **Controlled concurrent interleaving:** tx A opens on `RouteOnboardSeed`. A
    goroutine opens tx B. The `afterLock` seam signals over a channel, so the test
    proves B has *not* acquired the lock while A is open, with no sleeps.
    1. A puts seed X and commits.
    2. B then acquires the lock, reads, puts seed Y and commits.
    3. The final `seeded.yaml` holds both X and Y.
    - **Negative control:** the same interleaving with the lock replaced by a no-op
      through a seam loses X. This proves the test detects a lost update.
  - **Hand edit:** a hand edit between open and commit → `ADOPTION_CONFLICT`, and
    **no file written** (all three byte-identical), even when only the last file in
    the order changed.
  - **Per-route write order:** pinned for every multi-file route by recording the
    `writeFile` seam's call order.
  - **Failure on a later file, `RouteOnboardReject`:**
    1. The `writeFile` seam fails on `seeded.yaml` →
       `ADOPTION_PARTIAL:aitestmap/registry/seeded.yaml|aitestmap/onboard.yaml`.
    2. The rejection is recorded and the seed is still in the file.
    3. `AdoptionOf` on reload: the seed is not in `Seeds`, it is not counted, and
       `check` prints `SEED_REJECTED:…`.
    4. Re-run with the seam cleared → the seed is removed and there is exactly one
       rejection row.
  - **`RouteAdoptAgentVerdicts` memo recovery.** Each case goes through
    `RecordVerdict` with the `writeFile` seam, then reloads with `Load` and judges
    **real candidate eligibility** through `AdoptionOf(reg).NeedsReview` /
    `Reviews()`, never by replaying low-level ops:
    1. **`verifies` + adopt, the memo write fails:**
       - `ADOPTION_PARTIAL`; the seed is gone and the provenance row is present;
       - `NeedsReview == false`; `Reviews()` holds the derived `verifies` record;
       - `check` prints `REVIEW_UNRECORDED:…`;
       - a later `RecordVerdict` for a different pair (normal re-entry) back-fills
         the memo row, and `REVIEW_UNRECORDED` is gone.
    2. **`verifies` + adopt, seed removal fails:** the seed is shadowed (the test is
       stamped), `NeedsReview == false`, and the record is derived.
    3. **`drives`, the memo write fails:**
       - parked seed, no memo;
       - `NeedsReview` with the same test blob and reader is false (derived from
         `agent_review`);
       - with a **new** test blob it is true;
       - re-entry reconciles the memo.
    4. **`drives`, failing on `seeded.yaml`** → nothing written, and
       `NeedsReview == true` (nothing happened, so the pair stays a candidate).
    - **Negative control:** a live seed with no review anywhere →
      `NeedsReview == true`.
  - **Carrier lifetime (A14):**
    1. **Failed memo, then human `verify`, then reload.** Case 1's state, then the
       real `verify --by human:x` (through `call`, so the hook runs on
       `RouteRestamp`):
       - output: `WROTE:aitestmap/onboard.yaml` before
         `WROTE:aitestmap/registry/adopted.yaml`;
       - the adopted row is deleted;
       - after reload, `Reviews()` still holds the `verifies` record, now as a
         `reviews[]` row;
       - there is no `REVIEW_UNRECORDED`.
    2. **Preservation write fails.** The same, with the `writeFile` seam failing on
       `onboard.yaml`:
       - `RESTAMP_HOOK_ERROR`, exit 3;
       - the adopted row is **not** deleted and `onboard.yaml` is unchanged;
       - the retry converges as in (1).
    3. **Replacing a seed that carries an unsaved review.** Case 3's parked seed
       (memo failed), then `RouteOnboardSeed` `PutSeed` of the same pair without a
       review:
       - `onboard.yaml` is written first with the record, then `seeded.yaml`;
       - after reload, the review is in `Reviews()` and the new seed has no
         `agent_review`.
    4. **A newer review replacing an older unsaved one.** `SetSeedReview` (via
       `RecordVerdict` with a newer test blob) over a seed whose older review was
       never memoized: the older record is preserved, and both are in
       `Reviews()`.
    5. **Remove / delete on the other routes.** `RemoveSeed` through reject and
       `DeleteAdopted` through per-row adopt, each over an unsaved review: the
       review is preserved first.
    6. **Negative control.** Deleting a carrier whose review **is** already in
       `reviews[]` leaves `onboard.yaml` byte-identical, with no extra write.
    - **Refused before anything is written:** `RecordVerdict` with missing
      `run` / `packet_sha` / `test_blob` / `by` → `ADOPTION_ROUTE:…|replay-data`.
    - **Refused:** a low-level op called on this route → `ADOPTION_ROUTE`.
- `registry/adoption_splice_test.go`:
  - **Fixture:** `adopted.yaml` holds a **noncanonical unrelated row**: a head
    comment, an inline comment, double-quoted values, fields in non-schema order,
    and an extra unknown field.
  - Refreshing another row and then deleting it leaves that row's byte range, and
    every byte outside the touched row, identical.
  - Inserting a row places it in sorted position without touching its neighbours.
  - An `onboard.yaml` with M6.1 `phases` and comments gains a rejection with
    `phases` byte-identical.
  - **Flow-style `adopted.yaml`:** a file with a top-level comment, the target row
    and an unrelated row carrying quoted values and an unknown field, in flow
    style. Refresh, then deletion, of the target →
    - the unrelated row **decodes value-identically**, unknown field included, in
      the normalised block table;
    - the `contract:` line and header comment outside the table are
      byte-identical;
    - the loss of in-table formatting is the documented behaviour.
  - **Flow-style `onboard.yaml` `rejections:`:** gaining a row normalises only that
    key. `phases` and the other three tables stay byte-identical.
  - A splice producing an invalid file is refused with nothing written.
- `registry/rules_seeded_adopted_test.go`:
  - `SEED_SHADOWED` and `ADOPTED_ORPHAN` (Info, never failing);
  - live vs persisted (a stamp added by an annotation but not yet scanned still
    shadows on `check`);
  - summary counts per `by` kind.
- **Command-level re-stamp cases** (`cmd/ait-testmap/adoption_restamp_test.go`, real
  `annotate` / `verify` through `call`). The fixture's `adopted.yaml` holds the
  re-stamped row and an **unrelated noncanonical row** (head comment, quoted
  values, reordered fields), and that row's bytes are compared:
  - agent `verify` → stamp refreshed, `by` kept, `WROTE:…adopted.yaml`;
  - `annotate --by auto` → refreshed;
  - `verify --by human:x` and `annotate --by human:x` → row deleted;
  - human `verify` on a `current` edge → deleted;
  - in every case the unrelated row is byte-identical;
  - re-stamping an edge with no row → `adopted.yaml` byte-identical and no
    `WROTE:` for it;
  - **first stamps:**
    - agent `annotate` **inserting** a covers line → row created;
    - agent `annotate` stamping an **existing unstamped** covers line (`restamped`
      with a zero `Before`) → row created;
    - `verify --by auto` on an unstamped covers line → row created;
    - unspecified actor → no row in any of these;
    - an agent re-stamp of an already-stamped edge with no row → no row (never
      relabelled);
    - `WROTE:aitestmap/registry/adopted.yaml` precedes `WROTE:<test file>`.
  - **failure / fix / retry, (a) intent fails:**
    1. With `adopted.yaml` at `contract: 2`, agent `annotate` (insert) →
       `RESTAMP_HOOK_ERROR`, exit 3; the test file and `adopted.yaml` are
       byte-identical.
    2. Fix the contract and retry → row + stamped line, consistent.
  - **failure / fix / retry, (c) human deletion fails:**
    1. With `adopted.yaml` at `contract: 2`, `verify --by human:x` on a stale
       adopted edge → test file re-stamped, `RESTAMP_HOOK_ERROR`, row kept.
    2. Fix and retry the human `verify` (now `current`) → row deleted.
  - **(c) machine refresh fails:** the same, with `--by auto` → stale `stamp`. The
    retry refreshes it.
  - **Completed writes reported on failure, through the real command:**
    - Agent `annotate` inserting a covers line into a test whose directory is made
      read-only (`chmod 0555`; skipped when `os.Geteuid() == 0`): the intent phase
      writes `adopted.yaml`, then `Apply` fails.
    - Assert together: a **non-zero exit**, stdout exactly
      `WROTE:aitestmap/registry/adopted.yaml\n` (no `STAMP:` / `STAMPS:`), the
      error line on stderr, and `adopted.yaml` holding the row.
    - The `--json` variant: `wrote` = `[adopted.yaml]`, `incomplete: true`,
      `stamps: []`.
    - Restoring the mode and retrying converges (row `stamp` = the landed stamp).
  - **The post-hook error now reports the test file:** a `RESTAMP_HOOK_ERROR` case
    prints `WROTE:<test file>` and exit 3. The pre-existing M2.2 pin in
    `annotate_test.go` (empty stdout on a hook error) is updated deliberately.
- `annot/adoption_hook_test.go` — **(b) `Apply` fails after the intent phase:** use
  the in-package `beforeApply` seam to change the test file → `REWRITE_CONFLICT`.
  The row is present and the edge unstamped, so `AdoptionOf` lists it under
  `Orphans`. Then retry `Annotate` with the seam cleared → the stamp lands, the row's
  `stamp` equals it, and it is no longer an orphan. Covered for both the insert and
  the existing-unstamped-line shapes.
- Updated byte-exact pins (`scancheck_test.go`, `scancheck_characterize_test.go`,
  `run_test.go`, `scoped_e2e_test.go`, any `annotate_deps_test.go` `WROTE` pins) each
  gain exactly the two summary lines / the hook's `WROTE:`, and nothing else.
- `ait engine test` (`go vet` + `go test` over `goengines/`) passes, including
  `guards_test.go` (no new module, no `aitasks/` literal).
- No path requires a human action.

## Risk

### Code-health risk: medium
- **Risk:** the hooks now write `adopted.yaml` from the shared `annotate` / `verify`
  paths (M2.2), which gain an intent phase before `Apply`, and the return signature
  changes. A bug could change stamping-verb output or silently rewrite provenance.
  - severity: low (residual — addressed by inline pre-phase
    characterize_stamp_verbs_without_provenance)
  - → mitigation: inline pre-phase characterize_stamp_verbs_without_provenance
- **Risk:** `check` output changes on every repository (two summary lines), and `Load`
  gains a post-load phase that every verb goes through. This is intentional, pinned
  by the updated byte-exact tests.
  - severity: low
  - → mitigation: none

- **Risk:** the multi-file adoption writes depend on a new cross-process lock (the
  first `platform.Lock` user in the engine) and on a fixed fail-safe order. A wrong
  lock path or a missed `Close` would serialise or block writers. Bounded by the
  controlled-interleaving test with its negative control, the partial-failure /
  re-run tests, and deferred `Close` on every path.
  - severity: low
  - → mitigation: none

- **Risk:** text splicing of YAML row ranges could misjudge a row boundary (head /
  trailing comments, blank lines) and cut or duplicate bytes. Bounded by:
  re-parsing and validating the spliced bytes before any write (refused, nothing
  written), the noncanonical-row splice fixtures, and a canonical fallback for flow
  tables.
  - severity: medium
  - → mitigation: none

### Goal-achievement risk: medium
- **Risk:** the write-routing API and parts of the schemas (`stamp`, optional
  `confidence`, `assert_line` int) are designed without any consumer plan
  (M4 / M6 / M7 / M8 are not decomposed), so consumers may need a different shape.
  This is bounded by recording the decisions in the proposal and by notes to each
  consumer parent (step 7).
  - severity: medium
  - → mitigation: none (proposal edit + notes)
- **Risk:** unit-level tests of the tx, the rules and the hook could miss a mismatch
  between load-time classification, `check`'s live classification and the hook
  across a real lifecycle.
  - severity: low (residual — addressed by inline post-phase e2e_adoption_lifecycle)
  - → mitigation: inline post-phase e2e_adoption_lifecycle

### Planned mitigations
- timing: pre-phase | name: characterize_stamp_verbs_without_provenance | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared stamping paths / hook signature change | desc: pin byte-exact annotate/verify output, test-file bytes and hook calls for actors that create no provenance row, before editing hook.go / stampverbs.go
- timing: post-phase | name: e2e_adoption_lifecycle | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal — load/check/hook classification mismatch across a lifecycle | desc: drive seed → agent annotate → check → auto verify → human verify → orphan through the real verb table

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
