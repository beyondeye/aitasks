# Task premise staleness — the generalized advisory mechanism

Decision record for t1561 ("generalize task staleness detection"). It selects
and fixes the design that the implementation task tree (see "Implementation
tree" at the bottom) lands; the tree's children treat this file as their
durable context anchor. The generalization is **accepted**, not rejected: the
framework already committed to it twice — `lib/roadmap_premise.py`'s docstring
declares itself a temporary stand-in for this mechanism, and t1655 is filed to
delete that module once this lands.

Read together with:

- `aidocs/framework/manual_verification_staleness.md` — the deliberately
  narrow manual-verification seam (t1555) whose conventions this generalizes
  without widening. Its field (`verification_baseline:`) is **not** reused.
- `aidocs/framework/plan_path_reference_extraction_findings.md` — six verified
  defects in the framework's only heuristic "which files does this text
  reference?" implementation; the reason the heuristic tier is deferred.
- `aidocs/framework/background_work_roadmap.md` — the roadmap's premise-drift
  signal (t1569_5), this mechanism's second consumer via t1655.

## The problem

A task can sit `Ready` for months while the codebase, the surrounding task
graph, and the product direction move under it. The task stays syntactically
valid — its dependencies resolve, its status is honest — but its **premise**
(the state of the world it was written against) may no longer hold. The
framework had three isolated freshness checks (plan-review age in
`planning.md` §6.0, the t1555 manual-verification pre-check, the roadmap's
premise signal) and no way to surface premise drift when an ordinary backlog
task is picked.

## What "staleness" means here — three classes, two of them out of scope

1. **Detectable evidence** — commits landed on files the task's premise
   depends on, after the point the premise was last known valid. This is what
   the mechanism measures, and the only thing it claims.
2. **Heuristic signals** — age, broad architectural change, path-shaped
   tokens scraped from task prose. Excluded from v1. Time is rejected as a
   verdict outright (t1555's measurement: at a 20-day median backlog age, any
   hours-scale threshold marks everything stale — zero information). Prose
   path-extraction is rejected until the six defects in
   `plan_path_reference_extraction_findings.md` are paid down: the current
   grammar silently truncates real paths and skips most languages, and a
   wrong scope silently becomes a false all-clear.
3. **Human / product judgment** — "is this still worth doing?" The mechanism
   never claims this. A `FRESH` verdict means "the watched files did not
   change", not "the task is still a good idea".

Weak evidence is never presented as an all-clear: an uncheckable scope entry
drives the verdict toward `ASK_STALE` (never `FRESH`), and a task the
mechanism cannot evaluate reads `SKIP` — silent, and distinct from `FRESH` in
every consumer.

## Selected design

### Field — `premise_baseline: <sha> @ <YYYY-MM-DD HH:MM>`

The commit at which the task's premise was last known valid, in the exact
grammar of `verification_baseline:`. A **new** field, because reusing
`verification_baseline:` would widen a deliberately issue-type-scoped seam:
on a `manual_verification` task that field means "the checklist matches this
commit", which is a different statement with a different review transaction.
t1561's own constraints forbid the widening.

Written in three places. Creation-time seeding (see "Seeding") stamps it. A
carry-over task inherits it through `aitask_create.sh`'s internal
`--premise-baseline` creation flag. That flag requires `--commit`, overrides the
seed, and treats `""` as "none". It accepts only the stored grammar
`<40|64-hex> @ <YYYY-MM-DD HH:MM>`, lowercased, and it **does not** look the
commit up, because an inherited value may name a commit that a history rewrite
removed. The reader reports that state as `history_rewritten`, and the
carry-over must inherit it rather than abort archival. A person or the workflow
sets or clears it with `aitask_update.sh --premise-baseline` (empty string
clears). That update writer accepts
`<oid> @ <YYYY-MM-DD HH:MM>` or a bare `<oid>`, which it stamps with the current
time. `<oid>` must be a full 40- or 64-hex id that names a commit in the
repository (`git cat-file -e <oid>^{commit}`), and it is stored lowercase. A
symbolic revision is rejected rather than resolved, so callers pass the
`CHECKED:` sha. A rejected value leaves the task file untouched. Merge rule:
`_BASE_AWARE_FIELDS` in `board/aitask_merge.py` with `deletion_aware=True` —
the same two documented failure modes apply verbatim (a presence-based merge
resurrects a dismissed baseline after sync; an `updated_at`-newer merge lets
an unrelated `--status` edit win a field it never touched), and divergent
advances on both sides resolve to PARTIAL. It compares through
`lib/opaque_scalar.py:normalize_opaque_scalar`, the helper it shares with
`verification_baseline` and `plan_approved_at`.

### Scope and baseline are orthogonal axes

**Scope** (which files the premise depends on) resolves in tiers:

- **Tier A — curated:** `file_references:` when present (range suffixes
  stripped, as in the t1555 helper). Any issue type.
- **Tier B — derived:** for **any task carrying an `exact` origin**, resolve it
  with `lib/followup_origin.py` (quality `exact` only — `topic` and `unknown`
  refuse to claim causation); scope = the files the origin's landing commits
  touched outside the task-data prefixes (`aitasks/`, `aiplans/`,
  `.aitask-gates/`).

  **Eligibility is having an exact origin, not being a follow-up.**
  `followup_origin.py` "deliberately never reads `followup_kind`" — origin is a
  separate concern from classification — so it resolves any task's metadata,
  follow-up or not. The two sets differ in practice:
  `aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md` is
  `issue_type: test` with a `verifies:` list of eight siblings and neither
  `followup_kind` nor `anchor`, and the resolver returns `exact` for it.

  **`exact` requires `verifies:` — `--followup-of` can never satisfy it.**
  `resolve_anchor()` in `aitask_create.sh` turns `--followup-of` into an
  `anchor:` field and writes nothing else, and the resolver's rule 1 holds that
  `anchor` is *never* an exact origin ("Reporting it as `exact` would claim
  direct causation the data does not support"). This is a contract, not a corpus
  property: no amount of data makes a `--followup-of` task Tier-B-resolvable.
  See "Tier B reachability" below.
- Neither → silent `SKIP`.

**Baseline** (since when) resolves separately:

- A stored `premise_baseline:` always wins.
- Without one, v1 reads `SKIP`. The **computed** origin-landing baseline
  (`roadmap_premise.baseline_for` semantics: the newest commit that names an
  origin id AND touches a path outside the task-data prefixes) is **deferred
  behind a profile key** — a no-go outcome of the measured pre-phase below,
  not a guess. When enabled it gives legacy follow-ups a first-pick prompt
  against their origin's landing point.

The landing-commit qualifier is load-bearing and must not be re-derived:
measured 2026-08-31, 61 of 1714 `(tNN)`-tagged commits touch no code path,
and 35 of 1615 tagged ids have a metadata-only *newest* tagged commit — an
unqualified "newest tagged commit" baseline silently masks real drift as
`FRESH`.

Manual-verification tasks never reach this mechanism: task-workflow Step 3
Check 3 routes them to their own procedure before the premise check runs, so
the t1555 seam and this one cannot double-prompt.

### Verdict engine — protocol

One impure producer, `aitask_premise_stale.sh check <task_file>`, emitting
the fixed line protocol (modeled on `aitask_verification_stale.sh`, with two
additions):

```
BASELINE:<sha>|<YYYY-MM-DD HH:MM>   or  BASELINE:NONE
CHECKED:<sha>
FINGERPRINT:<digest>
FILES:<n>
CHANGED:<path>|<n_commits>|<task_ids>
DELETED:<path>|<culprit_task>|<subject>
UNKNOWN:<path>|<reason>
DISPLAY:<one-line human summary>
DECISION:<FRESH|ASK_STALE|SKIP>
```

- Always exit 0 for every content state; `die` on CLI misuse (a typo'd path
  must not read as `SKIP`).
- **`UNKNOWN` drives the verdict**: uncheckable entries share one evidence
  list with `CHANGED`/`DELETED`, and the verdict is an emptiness test over
  that list, so the two cannot drift apart.
- **Empty scope → `SKIP`, never `FRESH`** — a resolved baseline over nothing
  checked nothing.
- History rewrite: a stored baseline not an ancestor of the checked revision
  (`git merge-base --is-ancestor`, treating exit 1 and exit 128 alike) →
  `SKIP`.
- Probes run against **committed trees, never the worktree** (`git cat-file
  -e "<rev>:<path>"` + `git log <sha>..<rev> -- ":(literal)<path>"`), so a
  dirty worktree is invisible by construction. `:(literal)` pathspec guard on
  every history query.
- **`FRESH` is a positive claim, never the absence of a failure.** It requires
  every non-retired scope path to be present at both ends and to carry a
  *successful* history query, with the commit count attested from the producer
  to the core, and at least one such positively checked path. A failed `git log`
  is `UNKNOWN:<path>|history_unavailable`, never an empty history, and a
  malformed or missing evidence row can only add evidence or turn the verdict
  into `SKIP`.
- **A path absent at the baseline** is classified by the checked revision and
  two more history queries, each with an explicit status (a failure is
  `history_unavailable`):
  - present at the checked revision, or touched inside the window →
    `UNKNOWN:<path>|absent_at_baseline` (evidence: the file was added or
    churned since the baseline);
  - absent at both ends, no commit in the window, and history reachable from
    the baseline proves it once existed → **`retired`**: deleted at or before
    the baseline. This is exactly the state a confirmed `DELETED` leaves behind
    once the baseline advances past the deletion, so it is **not evidence** and
    **not positively checked** — it can neither re-prompt nor carry a `FRESH`. A
    scope whose every path is retired reads `SKIP`/`all_retired`;
  - absent at both ends with no history at all →
    `UNKNOWN:<path>|never_existed` (evidence: an intended future file or a typo,
    which the prompt cannot tell apart).
- **The baseline must be an immutable commit id.** The reader accepts only a
  full 40- or 64-hex object id and checks it before any git probe; a symbolic
  or abbreviated value (`HEAD`, a branch name, `abc1234`) reads
  `SKIP`/`invalid_baseline`. `HEAD` is an ancestor of every checked revision, so
  `HEAD..<rev>` is empty — comparing it would read `FRESH` over a real change.
  Task files are hand-editable, so the writer's validation is not the only
  guard.
- Encoding of every variable path field: `%` → `%25` first, then `|` → `%7C`,
  LF → `%0A`, CR → `%0D` (decode in reverse, `%25` last), so a filename holding
  `|` or a newline stays one field on one line. The Tier-B origin surface is
  read through `aitask_revert_analyze.sh --batch-map --encode-paths` for the
  same reason — the default batch-map output writes paths raw into
  newline-framed records.
- **Scope is read as YAML and its completeness is attested.** `premise_baseline:`
  and `file_references:` are read through the framework's YAML reader
  (`task_yaml.parse_frontmatter`), never by splitting the flow list on commas,
  so a quoted entry such as `"a,b.py"` stays one path; frontmatter that does not
  parse reads `SKIP`/`invalid_frontmatter`. Only a string entry is a path: YAML
  turns unquoted `null`, `on` and `010` into `None`, `True` and `8`, so every
  non-string entry — and any value holding a NUL byte, which bash would silently
  drop — is an `invalid_reference` (counted, uncheckable, `ASK_STALE`), never
  skipped or coerced. A non-string or NUL-bearing `premise_baseline:` reads
  `SKIP`/`invalid_baseline`. Every scope source states its own
  size — the fields reader's `FIELD_END` count, and in `--encode-paths` mode the
  batch map's per-id `TASKFILES_COUNT` rows, its final `END` record count, and
  exactly one `STATUS` per requested origin — and a source that fails its own
  count reads `SKIP`/`scope_error`. A dropped row can therefore never shrink the
  scope into a `FRESH`.
- `CHECKED:NONE` when no revision was pinned (the SKIPs reached before it:
  no Python, not a repository, unreadable fields, no or invalid stored
  baseline). The closed SKIP and `UNKNOWN` reason vocabularies live in
  `lib/task_premise.py`; a failed Tier-B subprocess reads `SKIP`/`scope_error`.
- `FINGERPRINT:` digests a structured (JSON) serialization of its tuple, so list
  boundaries are unambiguous — the scope `["a,b"]` never collides with
  `["a", "b"]`.

**`CHECKED:<sha>`** records the revision the evidence was evaluated against
(HEAD at check time). Every later baseline advance writes **that** sha, never
write-time HEAD: the check and the write are separated by the ownership claim
(task-workflow Step 4), HEAD can move in between, and advancing to write-time
HEAD would silently mark commits the user never saw as reviewed. Commits
after the checked revision stay uncovered and surface at the next pick.

**`FINGERPRINT:<digest>`** binds the *metadata* inputs the verdict depended
on — a digest over the canonicalized tuple (baseline source + sha, scope
tier, sorted scope path list, resolved origin ids). `CHECKED:` alone cannot
detect a concurrent mutation of `file_references:`, the origin fields, or the
stored baseline itself between prompt and write (another session, a sync
merge). After the lock is acquired and before any baseline write, the
producer is re-run and the fingerprints compared: equal → write proceeds;
different → the prompted confirmation is void, the fresh evidence is shown,
and a fresh decision is required. (The claim-time `active_gates_digest` is
the in-repo precedent for digesting a decision's inputs.)

### Architecture — the pure/impure split (the t1655 contract)

- `lib/task_premise.py` — **pure** core (no `os`/`time`/`subprocess`/I/O;
  listed in `PURE_MODULES` in `tests/test_parallel_admission_purity.py`),
  generalizing `roadmap_premise.baseline_for` + `check` over already-
  materialized text rows. Keeps `metadata_only` distinct from
  `unknown_history` (the remedies differ), keeps `SKIP` fail-open and silent,
  keeps `UNKNOWN`-drives-verdict.
- `aitask_premise_stale.sh` — the git-facing producer. Because it runs git,
  it restores the two narrowings `roadmap_premise` accepted: a `DELETED:`
  record (via `cat-file -e` probes at both ends — history alone misses
  deletions) and the `:(literal)` pathspec guard.

t1655 swaps the roadmap onto this core and deletes `roadmap_premise.py`. The
four properties its tests pin — landing-commit baseline, `UNKNOWN` drives the
verdict, silent `SKIP` with distinct reasons, purity — must survive the swap
unchanged.

### Interaction — task-workflow Step 3 Check 7

The check is **Check 7** of task-workflow Step 3 — after the `## Inbox` notes
check (Check 6) — so it runs on every entry path (pick, board agent launch,
explore), for `Ready` tasks only: the archival checks and the resume path route
away first, and a `manual_verification` task is skipped because its own
staleness pre-check (Check 3, t1555) owns it, which keeps the two from
double-prompting. `FRESH` and `SKIP` are silent. `ASK_STALE` presents one
NON-SKIPPABLE `AskUserQuestion` with the evidence inside the widget text and
four options. The procedure is `.claude/skills/task-workflow/premise-staleness.md`.

| Option | Effect on the baseline | Route |
|---|---|---|
| Proceed — premise still valid | advance to the `CHECKED:` sha (post-lock, fingerprint-gated) | continue to Step 4 |
| Review & replan with this evidence | **unchanged** at dismissal; advances to the `CHECKED:` sha once the renewed plan is approved — at the Step 7 post-approval writes, or in planning's "Approve and stop here" before the lock is released | continue, evidence threaded into planning; an existing plan is force-verified (§6.0b: the plan preference is bypassed, since `use_current` would drop the explicit choice) |
| Postpone task | unchanged | status → `Postponed` (post-lock), end with the `postponed` banner outcome |
| Pick a different task | unchanged | back to selection, nothing written |

**Ask before the lock, write after it.** The prompt runs before ownership
exists, and a `Ready` task can be claimed by another session while it is open;
local `aitask_update.sh` does not check locks. So the prompt section writes
nothing — not even "Postpone" — and records the answer as `premise_decision`.
Step 4 then claims the task with `aitask_pick_own.sh --expect-status Ready`: the
claim re-syncs the task data and re-reads the status **under the lock**, before
any write, and refuses with `STATUS_CHANGED:<actual>|Ready` when another session
changed the status and released the task meanwhile. A task-data sync that fails
under the lock refuses with `STATUS_UNVERIFIED:<reason>` instead of trusting the
local file — task_sync returns 0 on failure, so the outcome is read from
`TASK_SYNC_STATUS`. The pre-claim `previous_status` cannot serve here: it is the
same snapshot the prompt saw. The status is read as YAML through the framework's
reader (`"Ready"` and `Ready  # note` are `Ready`); a status that cannot be read
is `STATUS_UNVERIFIED:unreadable_status`, never a state change. The guarded claim
also needs a real lock: `acquire_lock` takes none when no email resolves, so
without one the claim refuses with `LOCK_REQUIRED:no_email` before writing
anything. Only after a successful claim does the post-lock section apply the
answer. A consequence: in a checkout whose task data cannot
sync, a premise-pending claim refuses until `ait syncer` reconciles it.

**The write is one transaction, in source.** `aitask_premise_stale.sh advance
<task_file> --checked <sha> --fingerprint <fp> [--remove-ref <path>]...` is the
mechanism's only write path: **re-check fingerprint → decide → write everything
→ advance the baseline last → commit.** A fingerprint that changed since the
prompt voids the answer (`MISMATCH:`, followed by the fresh protocol; a fresh
`ASK_STALE` is asked again). The checked file must **be** the task the writer
resolves by id — the single active `t<id>_*.md`, compared by device and inode so
the data-branch symlink alias passes — or `advance` refuses: a copy would be
checked while the real task's baseline moved. And it must run **under the
task's lock**: `--owner <email>` is required, and the lock record must name that
email on this host **and** name this session: email and host are shared by every
session of the same user, so the lock's recorded session anchor (pid, start-time
token and its kind) must pass `lock_anchor_is_self`, the test the lock's own
acquire gate uses. Otherwise `ADVANCE_REFUSED:not_owner`; when either anchor
cannot be named, `ADVANCE_REFUSED:owner_unverifiable` — never a pass. Checked
last before the write. The same proof, exposed as `aitask_premise_stale.sh owner`,
runs before the procedure's other post-lock writes (a postpone, a revert to
Ready). **`not_owner` is terminal** wherever it appears: the procedure's
`## Ownership lost` exit writes nothing more and undoes nothing — no status
revert, no lock release (it is the new holder's), no gate materialization, no
stop sequence — and ends the run with a state-derived banner.
`owner_unverifiable` is not proof of loss: an advance refuses on it (the
baseline write is optional), while a postpone or revert the user explicitly
chose proceeds with a warning, like every other step after this session's
claim. The workflow never continues past a lock error while an answer is
pending ("Continue without lock" is withheld), and the "Approve and stop here"
advance, which runs before Step 7's ownership guard, relies on this proof rather
than assuming the lock. Approved reference removals and the baseline go to
**one** `aitask_update.sh` invocation, which validates the baseline (grammar and
commit existence) and reads the list before its single write, so a rejected
value leaves the task byte-identical. Advancing on dismissal is load-bearing
(the same evidence must never re-prompt), but advancement always requires an
explicit premise confirmation — a dismissal or an approved replan — never a mere
workflow transit.

**Every evidence class has a defined resolution.** Advancing the baseline
resolves drift; the other classes are named in the question so the user knows
what "Proceed" does with them:

| Evidence | Resolution |
|---|---|
| `CHANGED` | covered by the advance |
| `DELETED` | covered; the re-check reads the path `retired` |
| `absent_at_baseline` (file added) | covered; the re-check reads it normally |
| `never_existed` | **kept** by default — it may be an intended future file; removed from `file_references:` only on a separate explicit approval (`--remove-ref`, which refuses any path that is not a `never_existed` row of the fresh check); a kept reference keeps being reported until the file exists or is removed |
| `invalid_reference` | not drift, and not removable here: the writer refuses to rewrite a list holding a non-string entry, so it is reported until fixed by hand |
| `history_unavailable`, `malformed_row`, origin `unknown_history` | **no advance at all** (`ADVANCE_REFUSED:unverifiable`): the commits behind them were never shown, so advancing would mark them reviewed |

**The replan reviews the complete evidence.** The question caps its evidence
rows for presentation; the complete check output is kept as
`premise_decision.protocol`, and planning reviews every row of it **first, on
every planning path** (before the verify path's terminal step), recording a
`## Premise review` section whose `Evidence rows reviewed: <n>` equals the
protocol's row count. A guard after Save Plan checks it, and the replan advance
refuses without it — an advance past evidence nobody reviewed is the one outcome
this mechanism must never produce.

**Headless profiles only report.** A non-interactive profile displays the
evidence and continues: it never prompts, never advances, never postpones —
each of those needs an explicit human confirmation.

No profile key gates the check in v1: it costs milliseconds, and
advance-on-dismissal already bounds prompt frequency to once per actual
change window. (The deferred computed-baseline tier is where a profile key
enters — see below.)

### Seeding

`aitask_create.sh` stamps `premise_baseline` = HEAD **at the task's commit
point when the new task has a derivable scope** — a `file_references:` list
(Tier A) or a `verifies:` list (Tier B; the only input that yields an `exact`
origin). **`--followup-of` alone does not seed**: it writes only `anchor:`,
which Tier B refuses by contract, so a baseline stamped on that trigger could
never resolve a scope and would read `SKIP` forever. A task with no derivable
scope is not seeded; the field would be dead weight.

There are two commit points, and both seed:

- **`--batch --commit`** (parent and `--parent` child): seeded when the
  invocation carries `--file-ref` or `--verifies` — exactly the inputs whose
  lines the serializer writes. The value is written by the creation serializer
  (`create_task_file` / `create_child_task_file`), so it lands in the
  task-creation commit.
- **`finalize_draft`** (`--finalize`, `--finalize-all`, and the interactive
  "Finalize" menu): the finalized file is read through the YAML parser
  (`read_premise_seed_fields` in `lib/task_utils.sh`), so a hand-edited
  block-style list counts as well as a flow one, and the line is inserted
  before the commit. A draft that already carries the key — even with an empty
  value — is left as it is. This path matters in practice: codebrowser's
  create-task action, the live Tier-A producer, runs the *interactive*
  `aitask_create.sh --file-ref`, which writes a draft and commits it here.

Drafts themselves are never seeded; the commit point is what anchors the value.
HEAD is resolved in the working directory (the repository root), the same
repository the reader checks. When there is no HEAD commit (an unborn branch),
the task is still created, unseeded, with a warning; absent reads `SKIP`, which
is the designed legacy behaviour. Carry-over tasks (`create_carryover_task` in
`aitask_archive.sh`) **inherit** the origin task's baseline rather than
re-stamping — the carried-over premise is as old as its source, exactly the
t1555 carryover rule. The origin's value is read through YAML, so a quoted
scalar is inherited without its quotes. It is passed to the creation call
(`--premise-baseline <value>`, or `""` when the origin has none, which
suppresses the `--verifies` seed). A malformed origin value is not inherited:
the carry-over is created without it, with a warning, because malformed and
absent both read `SKIP` and an advisory field must not block archival.

Seeding at creation is premise-correct even for "before"-timed
risk-mitigation follow-ups (created before their origin lands) **that carry a
seeding trigger**: the creator's knowledge of the world *is* HEAD at creation,
and the origin landing afterwards is genuine premise-relevant news for such a
task. (Contrast the roadmap's rejection of `created_at`-anchored baselines for
its *origin-drift* question, which this mechanism does not re-ask.) The
risk-mitigation seam creates with `--followup-of` and no `--file-ref`, so in
practice such tasks are **not** seeded — the timing argument stands, but has no
live subject in v1.

### Tier B reachability

Tier B is reachable only through `verifies:`, and that constrains the seeding
rule above far more than the tier definition suggests. Three facts, all
re-checkable in the source:

1. **`--followup-of` produces `anchor:`, and `anchor` is never `exact`.**
   `resolve_anchor()` writes `anchor:` and nothing else; `followup_origin.py`
   rule 1 refuses to promote it. So `--followup-of` cannot seed a resolvable
   scope — a contract-level impossibility, not a property of today's data.
2. **`--verifies` is type-agnostic in the CLI; the manual-verification
   restriction lives in the callers.** `aitask_create.sh` parses and serializes
   the field without consulting `issue_type`. Only two in-framework callers pass
   it to creation, and both also pass `--type manual_verification`:

   | Caller | Route | Type it passes |
   |---|---|---|
   | `aitask_create_manual_verification.sh` | calls `aitask_create.sh` | `manual_verification` |
   | `aitask_archive.sh` (`create_carryover_task`) | calls `aitask_create.sh` | `manual_verification` |
   | `aitask_fold_mark.sh` (verifies union) | calls `aitask_update.sh` — an **update** path, not creation | n/a |

3. **Manual-verification tasks never reach the check** (Step 3 Check 3 routes
   them away), so the `--verifies` seeding half currently seeds a population the
   premise check never evaluates.

**Consequence, stated plainly:** the Tier-B seeding path is **live by contract
but unexercised by framework callers** — reachable through a direct
`ait create --verifies` invocation and by any future caller, but producing no
checkable tasks today. The only seeding path framework callers exercise is
Tier A / `--file-ref` (whose live producer is codebrowser's
create-task-from-selected-files flow). The organic-coverage story in v1 is
therefore narrower than "every new follow-up is checkable".

**`--verifies` on a non-`manual_verification` task is supported, and
type-gating it would silently dormant Tier B.** The help text on
`aitask_create.sh`, `aitask_update.sh` and the website command reference
describes the common use, not an exclusivity constraint. t1663_3 owns a
non-MV, non-follow-up creation fixture pinning that such a task **is** seeded,
so a future type-gate — or a re-added follow-up gate on Tier B eligibility —
fails a test rather than quietly removing the tier.

**Why Tier B is not widened to accept `anchor`.** It would re-import the failure
mode the no-go below already rejected: a topic-root scope spans a whole topic's
afterlife, which is the same undifferentiated-churn shape that scored 0 of 5 on
the actionability bar. And the coarsening is not merely coarser — measured
2026-08-27 over 229 active follow-ups (exact 86, topic 130, unknown 13), the 37
tasks carrying both signals have differing exact and topic file sets in 21
cases, and at least one is fully disjoint (t1497: exact 3 files, topic 13,
overlap 0). Rule 1 is load-bearing for the resolver's other consumers.

**Dated observation, 2026-09-01 — a statistic, not an invariant, and not a
pass/fail criterion.** Over 495 active task files: 91 carry `verifies:` (89 of
them `manual_verification`, the other two a `chore` and a `test`), 0 carry
`file_references:`, and 309 carry `anchor:`. Recorded to show the scale of what
seeding on `--followup-of` would have stamped, not as a property anything
asserts.

## The measured pre-phase and the no-go decision

Measured 2026-09-01 on this repository (the plan's
`sample_live_backlog_prompt_rate` pre-phase; script recomputable from
`aitask_backlog_origin_facts.sh` + `aitask_revert_analyze.sh --batch-map` +
`roadmap_premise.check` over Ready follow-ups):

- Active corpus: 481 tasks, 228 of them `Ready` follow-ups; **87** carried an
  `exact`-quality resolvable origin (the computed-baseline candidates).
- First-pick verdicts: **`ASK_STALE` 78/87 = 89.7 %**, `SKIP` 9
  (`unknown_history`).
- Actionability audit, deterministic sample (pool = the 78 `ASK_STALE` ids
  sorted ascending; stride indices 0, 15, 31, 46, 62): **t623_7, t1113,
  t1291, t1391, t1541** — **0 of 5 actionable** under the pre-registered bar
  ("names ≤10 concrete drift tasks/commits the user can realistically
  inspect"). Every sample aggregated far more than 10 distinct drift tasks;
  hot-file churn dominates (`aitask_setup.sh`: 44 commits by ~40 tasks inside
  t623_7's scope; `minimonitor_app.py`: 32–49 commits in t1113/t1391).

The pre-registered go bar (≥3/5 actionable) was missed, so the **computed
origin-landing baseline for legacy follow-ups is a no-go for v1**. It is
deferred behind a profile key (below) rather than deleted: the mechanism is
sound, but against year-scale windows over hot framework files its evidence
is undifferentiated churn, and 78 unactionable prompts would train users to
click through — destroying the signal for the cases that matter.

The narrowing is precise: **only the computed-baseline source is removed.**
Derived origin *scope* (Tier B) and creation-time seeding stay in v1 — a
seeded task carries a stored baseline and resolves its scope from
`file_references:` (Tier A) or an `exact` origin (Tier B), so every **seeded**
task is checkable from day one, over windows bounded by its own review history
rather than its origin's entire afterlife. That population is materially
narrower than "every new follow-up": see "Tier B reachability" above.
Legacy tasks without a stored baseline read `SKIP`, silently — the phased
rollout t1561's constraints asked for.

## Baseline lifecycle

| Event | `premise_baseline` |
|---|---|
| task created with `--file-ref` or `--verifies` (`--batch --commit`) | seeded to HEAD at creation |
| draft finalized with a `file_references:` or `verifies:` list | seeded to HEAD at finalize (a value already in the draft is kept) |
| draft written (no commit) | not written |
| task created with `--followup-of` only | **not written** — no Tier-A/B-resolvable scope |
| task created without derivable scope | not written |
| scope acquired after creation (`aitask_update.sh --file-ref`/`--verifies`, fold union) | not written — the task resolves a scope but has no baseline, so it reads `SKIP` |
| carry-over task created at archival | **inherited** from the origin task, in the creation commit; absent stays absent; a malformed origin value is dropped with a warning |
| "Proceed — premise still valid" | advance to the `CHECKED:` sha (post-lock, fingerprint-gated) |
| "Proceed" with unverifiable evidence (`history_unavailable`, `malformed_row`, origin `unknown_history`) | unchanged — the check runs again next pick |
| "Proceed" with `never_existed` references, removal approved | the references leave `file_references:` in the same write as the advance |
| "Proceed" with `never_existed` references, kept (the default) | advanced; the references keep being reported |
| "Review & replan" chosen, plan later approved (Step 7, or "Approve and stop here") | advance to the `CHECKED:` sha, while the lock is still held |
| "Review & replan" chosen, plan not approved (abort, drift stop, resource park) | unchanged |
| "Postpone task" | unchanged; status → `Postponed`, written only after the claim succeeded |
| pick-another / session abort | unchanged |
| the claim finds the status changed (`STATUS_CHANGED:`) or unverifiable (`STATUS_UNVERIFIED:`) | unchanged; nothing claimed |
| fingerprint mismatch at write time | no write; fresh evidence, fresh decision |
| any writer refusal (`ADVANCE_FAILED:`) | unchanged; the task file is byte-identical |

## Why this is not a gate

Unchanged from t1555's analysis, which generalizes: gates are per-task
declarations whose purpose is *blocking* (`archive-ready` requires every
declared gate to pass), they run during/after implementation, and their runs
feed the re-entry ledger. An advisory pre-selection check that must never
block, runs before ownership exists, and must stay silent for most tasks is
the wrong shape for that substrate. The "reviewed" memory is a frontmatter
baseline field, exactly as t1555 chose; the check itself is a procedure step,
exactly as plan-review freshness chose.

## Deferred, each with its disposition

- **Computed origin-landing baseline for legacy follow-ups** — behind a new
  profile key, off by default; promoted only if the retrospective child finds
  seeded-task evidence quality holds and users ask for backlog-wide coverage.
  The evidence-bounding work (e.g. capping displayed drift sources, windowing)
  belongs to that follow-up.
- **Heuristic prose path-extraction (Tier C)** — blocked on the six defects
  in `plan_path_reference_extraction_findings.md`; any future attempt starts
  from `lib/plan_paths.py`, not a new grammar.
- **Task-graph evidence axis** (dependencies landed, statuses changed, plan
  content hash) — `lib/trail_gather.py` already digests exactly these inputs
  for trails; a premise version is a separate evidence class with its own
  noise profile, so it needs its own measured case before joining.
- **Read-surface markers** (`ait ls -v` flag, board card badge) — owned by
  the implementation tree's retrospective child; the precedent is the
  `plan_approved_at` visibility contract (verbose-only marker + dedicated
  filter flags, never the plain listing).
- **Topic-quality origins, cross-repo scopes** — refuse-to-claim in v1
  (`SKIP`); revisit only with a concrete consumer **and** evidence that the
  coarsening is not simply wrong. Measured 2026-08-27 over 229 active
  follow-ups, the 37 tasks carrying both an exact and a topic signal have
  differing file sets in 21 cases and can be disjoint (t1497: exact 3 files,
  topic 13, overlap 0) — so a topic fallback is not a lower-resolution version
  of the exact answer, it can be a different answer.
- **Persisted exact-origin field for `--followup-of`** — the only way to make
  Tier B reachable for ordinary follow-ups without overturning the resolver's
  rule 1. Its shape is the t1468_1 / t1468_2 field-foundation + creation-seams
  pair (a new frontmatter field with its own merge, sync and board surface), so
  it is a separately justified task rather than a widening of this tree.
  Disposition owner: the retrospective child, gated on whether the seeded
  population proves the mechanism worth extending.
- **Seeding on post-creation scope acquisition** — `aitask_update.sh
  --file-ref` / `--verifies` and `aitask_fold_mark.sh`'s unions can give an
  existing task a resolvable scope with no baseline, which reads `SKIP` forever.
  Not seeded in v1: the write would claim a premise review that never happened,
  and "since when" is genuinely unknown at that point. Disposition owner: the
  retrospective child.

## Known limits

- **The check measures change, not behavior.** A behavior-preserving refactor
  reads as drift; a distant default change that invalidates the premise reads
  as fresh. Both directions persist at any scope quality.
- **Product/purpose drift is out of scope.** `FRESH` never means "still worth
  doing".
- **A draft is stamped when it is finalized, not when it was written.** A draft
  left in `aitasks/new/` for days is seeded with HEAD at finalization, so a
  change that landed between writing and finalizing is not reported.
- **A silent-skip precondition can mask a broken implementation.** Only the
  end-to-end exercise (seed → change a scope file → prompt fires → dismiss →
  advance → no re-fire) distinguishes "correctly quiet" from "never runs";
  the implementation tree carries it as a required test, not a nicety.
- **An invalid reference recurs until it is fixed by hand.** A non-string or
  NUL-bearing `file_references:` entry is uncheckable and the writer refuses to
  rewrite such a list, so no confirmation can clear it. That is deliberate: the
  scope itself is broken, and only a person knows what the entry meant.
- **A session that cannot name itself cannot advance.** Outside the agent's tmux
  pane and without `AIT_AGENT_PID`, a session has no resolvable anchor, so its
  locks record none and every advance reads `owner_unverifiable`: the prompt
  then recurs until the task is picked from a session that can prove it holds
  the lock. Proving ownership by email and host would let another session of
  the same user write.
- **A kept never-existing reference keeps being reported** until the file is
  created or the reference is removed. The prompt cannot tell an intended
  future file from a typo, so removal always needs an explicit approval.

## Implementation tree

The mechanism lands under parent **t1663** with strictly sequential children:
t1663_1 (core engine + producer) → t1663_2 (`premise_baseline` field
end-to-end) → t1663_3 (creation-time seeding + carryover inheritance) →
t1663_4 (task-workflow Step 3 Check 7 + procedure file) → t1663_5 (website
docs) → t1663_6 (retrospective evaluation, which owns the deferred
dispositions above). t1655 (roadmap adoption) depends on t1663. The tree's
task files name their own contracts; this record is their shared design
context.
