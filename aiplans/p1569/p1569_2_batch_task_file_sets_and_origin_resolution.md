---
Task: t1569_2_batch_task_file_sets_and_origin_resolution.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_3_shared_parallel_admission_checker.md, aitasks/t1569/t1569_4_task_workflow_parallel_admission_preflight.md, aitasks/t1569/t1569_5_roadmap_scoring_freshness_and_lanes.md, aitasks/t1569/t1569_6_backlog_roadmap_skill_and_trail_authoring.md, aitasks/t1569/t1569_7_manual_verification_background_work_roadmap.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_1_gatherer_inflight_and_planned_surface_facts.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-28 16:45
---

# t1569_2 — Batch task→file-set derivation, history index, origin resolution

Parallel with t1569_1 (landed: `lib/plan_paths.py` + `trail_gather.py` — disjoint, confirmed).

## Context

t1569 needs, for ~260 backlog candidates, "which files did this task's origin
touch". The canonical seam is `aitask_revert_analyze.sh --task-files`, which costs
one `git log` grep **per id** plus a per-parent `aitask_query_files.sh all-children`
shell-out. Measured now: 0.098 s for a childless id, **3.03 s for t635**. One
`git log --all` pass builds the entire map in **0.61 s**.

This slice delivers that batch pass, a commit index carrying `%ct`, a three-state
history status, and a pure origin resolver — the inputs t1569_3 (admission
checker) and t1569_5 (premise drift) consume.

**This plan was re-verified against the live repo on 2026-08-27**; six of its
original assumptions were wrong, and the acceptance oracle's id enumeration was
undefined. Corrections are marked **[V]** below, each with the evidence that
established it.

### Pre-phase (risk mitigations)

**`pin_path_framing`** — before wiring any bucketing logic, write the framing tests
first (Verification items 11 and 12): the adversarial fixture whose path *and*
commit message contain `\x1e`/`\x1f`, the negative control proving the rejected
framing mis-parses it, the fail-closed `FRAMING_ERROR:` case, and the leading-newline
strip with a control that fails when `.strip("\n")` is removed. This runs first
because a framing fault makes the Step 4 oracle pass *falsely*, which would render
every later check vacuous.

## Step 1 — `--batch-map` on `aitask_revert_analyze.sh`

Add a subcommand alongside `--task-files`, which **stays** as the oracle.

### [V] Correction 1 — `--no-renames` is mandatory

`cmd_task_files()` uses `git diff-tree --numstat` (**plumbing** — rename detection
off, a rename appears as delete + add). `git log --name-only` is **porcelain** —
`diff.renames` defaults true, so a rename collapses to the new path only.

Proof (t1217, `board/task_yaml.py` → `lib/task_yaml.py`):

| source | paths |
|---|---|
| `--task-files 1217` (oracle) | `board/task_yaml.py` **and** `lib/task_yaml.py` |
| `log --name-only` | `lib/task_yaml.py` only |
| `log --no-renames --name-only` | both — **matches** |

**32 task-tagged commits contain renames.** Without `--no-renames` the oracle test
fails on every one.

### [V] Correction 2 — match the literal `(t<id>)` in the FULL message

`--task-files` greps with `--fixed-strings --grep="(t<id>)"`, which searches the
**whole commit message**, not the subject. Use `%B`, not `%s`. Today 0 commits
carry a body-only id, so `%s` would pass by luck — it is not equivalent.

The literal form also means `(t1529, mitigation not required)` and `(t1410, t1411)`
match **neither** id (8 such commits). The batch must not "helpfully" match them.

### [V] Correction 3 — record framing must be NUL-only and fail closed

A `\x1e`/`\x1f`-delimited framing is **not** collision-safe. A git path may contain
any byte except NUL and `/`, and a commit message may contain arbitrary control
bytes — so a future filename or message carrying a separator would split a record
or field and **silently corrupt the map**. Today's "0 malformed" measurement proves
only that the current corpus lacks that input; it is not a safety argument. Reject
that framing.

Use **NUL as the only delimiter**, which rests on git invariants rather than corpus
facts: a path can never contain NUL and is never empty, and git will not produce a
commit message containing NUL.

```
git log --all --no-renames -z --name-only --format='%x00%H%x00%ct%x00%B'
```

Under `-z` git NUL-terminates the format output and every path. Split the whole
stream on `\x00`; a **`\x00\x00` pair (an empty token) is the record marker**,
unambiguous because git never emits an empty path. At each marker consume exactly
**three positional tokens** — hash, `%ct`, message — then every token up to the next
empty token is a path. Positional consumption keeps an empty commit message from
being mistaken for a record marker.

**Fail closed, do not guess.** Immediately validate `^[0-9a-f]{40}$` on the hash and
`^[0-9]+$` on the timestamp. Any violation means the framing assumption broke: emit
`FRAMING_ERROR:<token_index>` and **exit non-zero without emitting a map**. A
corrupt map that looks plausible is the failure mode this guards; a loud abort is
always preferable to a silently wrong file set.

Verified on the live repo: **21192 records, 0 framing violations, 46441
(commit,path) pairs, 0.546 s** — byte-identical products to the rejected framing.

**Each path must still be `.strip("\n")`** — git emits a newline between the format
output and the name list, so the first path of every record carries a leading `\n`.
This bug was hit during verification and produced 41 *false* mismatches; written the
other way round it produces false *matches*.

### [V] Correction 4 — children come from disk, in one pass

The original plan aggregated `parent = own ∪ children` from the commit id-map.
That is **not** equivalent: `build_search_ids()` → `get_child_ids()` →
`all-children` globs only `aitasks/t<N>/` and `aitasks/archived/t<N>/` (never the
`_b0`/`_b1` tarballs).

Measured: **525 of 689 commit-referenced child ids have no file on disk**, across
**100 parents** that have no own commit either. For those the oracle returns
*empty*; an id-map expansion returns a full set.

So build the parent→children map from **the same two globs**, once, for the whole
corpus — not per parent. This keeps byte-equality *and* the speed-up (the
per-parent `all-children` shell-out is what costs 3 s on t635).

Those 100 parents correctly become `UNKNOWN_HISTORY` → `UNCHECKABLE`.

### Output protocol

Default (oracle-exact — byte-identical semantics to `--task-files`):

```
TASKFILES:<task_id>|<path>
COMMIT:<path>|<sha>|<committed_at>|<task_ids csv>
TRACKED:<path>
STATUS:<task_id>|<FILES|NO_FILES|UNKNOWN_HISTORY>
```

Opt-in, **only** under `--with-recovered`:

```
RECOVERED_TASKFILES:<task_id>|<path>
RECOVERED_STATUS:<task_id>|<FILES|NO_FILES|UNKNOWN_HISTORY>
RECOVERED_DIVERGES:<task_id>|<n_paths_only_in_recovered>
```

Recovered lines carry the **commit-derived** child expansion, recovering the 100
parents. They are off by default and separately named.

#### Recovered contract — owning consumer and decision rule

Correct-but-unowned recovery data is how a second product turns into a second
definition of truth. So the ownership is fixed here, not left to whoever reads it
first:

- **`t1569_3` (`aitask_parallel_admission.sh`) is the sole consumer** that may pass
  `--with-recovered`. t1569_4 and t1569_5 consume t1569_3's verdicts only — they
  never read this stream directly. That preserves t1569_3's own rule that "all
  collision verdicts are computed here and nowhere else."
- **Recovered evidence is monotone toward less confidence. It may only:**
  - name an otherwise-anonymous uncheckable — emit
    `UNCHECKABLE_CAUSE:candidate|origin_history_off_disk_children` (a new member of
    t1569_3's closed reason vocabulary); and
  - downgrade `CLEAR` → `CLEAR_CAVEATED` via
    `CAVEAT:candidate|recovered_history_diverges` when `RECOVERED_DIVERGES:` is
    non-zero for that id — history exists that the oracle cannot attribute.
- **It may never** contribute an `OVERLAP:` line, produce a `CONFLICT` verdict, or
  move any verdict toward `CLEAR`. Recovery narrows confidence; it never grants it.

So recovered data is **diagnostic in phase 1**: it changes how honestly a verdict is
labelled, never which surface is judged to collide. Widening it to affect admission
is a separately justified enhancement, gated on evidence that the caveat rate is
actually costing usable parallelism.

- `TRACKED:` from one `git ls-files`.
- `%ct` is carried from the start: t1569_5's premise-drift needs commit
  timestamps; omitting them forces a re-shell per path and loses the win.
- `--ids-from <file|->` scopes `STATUS:` to the queried ids; with no ids, every
  discovered id gets one.

Implementation: `aitask_revert_analyze.sh` owns the `git` / `ls-files` / glob
calls and pipes the stream to a new pure bucketer `.aitask-scripts/lib/task_file_sets.py`
(interpreter via `lib/python_resolve.sh`). Bash cannot bucket 89k lines fast, and a
pure module is unit-testable without a repo.

## Step 2 — `STATUS:` is three-valued

`cmd_task_files()` (L324-356) warns on **stderr** and returns 0 with **empty
stdout**, so an absent entry is indistinguishable from "touched no files" — a
false no-conflict.

| value | meaning |
|---|---|
| `FILES` | id matched; paths follow |
| `NO_FILES` | id matched, commits genuinely touched nothing |
| `UNKNOWN_HISTORY` | **unrecognized by the oracle's disk-derived expansion** |

**[V] `UNKNOWN_HISTORY` does not mean "no commit exists anywhere."** The original
wording — "the id was never matched at all" — is untrue for the 100 parents of
Correction 4, whose child commits demonstrably exist but whose child task files are
off disk; `--with-recovered` can produce their file sets. The token stays (it is
oracle-exact and must not change), but its documented meaning is the narrower one:
*no commit was matched by the oracle's disk-derived expansion*. Both causes — "never
landed" and "landed under an off-disk child id" — are real and are deliberately not
distinguished in the default stream, because distinguishing them requires evidence
the oracle does not have.

A consumer that needs the distinction must pass `--with-recovered` and read
`RECOVERED_DIVERGES:<id>|<n>`, applying the decision rule fixed above: a non-zero
`n` names the cause and caveats the verdict; it never turns `UNKNOWN_HISTORY` into a
usable file set for admission. Document this on the subcommand's help output, not
only here — a consumer reading `UNKNOWN_HISTORY` as "no history" is exactly the
false-confidence failure the three-state contract exists to prevent.

`NO_FILES` is **production-reachable**, not fixture-only: t1435, t1236, and the
`refs/stash` entries carrying `(t1598)` all match with zero paths.

Emit `STATUS:` for **every queried id** so no consumer infers state from absence.

**Accepted residual:** `--all` walks `refs/stash`, and a stash subject quotes the
HEAD subject, so `WIP on main: … (t1598)` injects t1598. The oracle does exactly
the same, so equivalence holds — both are "wrong" identically. Record it; do not
silently diverge to fix it.

## Step 3 — `lib/followup_origin.py`

Pure: no writes, no git, no subprocess — the contract
`lib/followup_backfill_classify.py` states at L8-10.

**The public contract is the two-tuple the task specifies — do not widen it.**

```python
def resolve(metadata) -> tuple[list[str], str]:   # quality in exact | topic | unknown
```

1. `verifies:` present **and every entry canonicalises** → `exact`, origins = its ids.
2. else `anchor:` present and canonicalises → `topic`, origins = `[anchor]`.
   **Never `exact`** — anchor is a topic *root* that "always points at the root and
   never chains".
3. else → `unknown`, origins = `[]`.

Residue is exposed through a **separate detailed API**, never by changing `resolve()`:

```python
def resolve_detailed(metadata) -> dict:   # {"origins", "quality", "residue"}
```

which mirrors `followup_backfill_classify.classify()`'s dict return. `resolve()`
keeps the exact signature and arity the task's acceptance contract states, so the
planned consumer is unaffected.

#### [V] The CLI record layout — exactly five fields, defined before coding

"Residue gets its own field" was underspecified: a sixth field would break the
task's stated **5-field tab-separated** protocol, and packing residue into an
existing field ambiguously would make the shell consumer fragile. Pin it now.

The reference (`followup_backfill_classify.py:276-300`) emits `task_id`, then three
classification fields, then **`path` last** — the "free-ish field last" convention
`aitask_verification_stale.sh` also follows. Mirror that positionally:

| # | field | values |
|---|---|---|
| 1 | `task_id` | canonical bare id, or `-` |
| 2 | `quality` | `exact` \| `topic` \| `unknown`, or a row marker (below) |
| 3 | `origins` | comma-separated canonical ids, or `-` when empty |
| 4 | `residue` | comma-separated **encoded** raw tokens, or `-` when empty |
| 5 | `path` | the task file path — **last**, free-ish |

```
1569_2\texact\t1018_1,1018_2\t-\taitasks/t1569/t1569_2_….md
1064\ttopic\t1018\tnot-an-id\taitasks/t1064_….md
```

Malformed-input rows reuse the reference's shape verbatim, so a consumer's parser is
unchanged — id `-`, a marker in field 2, `-` in the middle fields, path last:

```
-\tNO_FRONTMATTER\t-\t-\t<path>
-\tUNPARSEABLE_ID\t-\t-\t<path>
```

**Field 4 is the only one carrying raw user text, so it is the only escaping
hazard.** Fields 1 and 3 hold canonical ids (`^\d+(_\d+)?$` — no separator can
occur); field 5 is a repo-relative path with no tab. Residue tokens come from
arbitrary YAML scalars and may contain a tab, comma, newline, or `%`.

Encode each residue token, **`%` first — that ordering is what makes it injective**,
the same rule t1569_3 states for its path encoding:

`%` → `%25`, then TAB → `%09`, LF → `%0A`, CR → `%0D`, `,` → `%2C`

No live token needs this today (verified: zero `verifies`/`anchor` tokens contain any
of those bytes). It is specified because the guarantee must come from the protocol,
not from the current corpus — the same reasoning as Correction 3.

Fixture-test the layout directly: every row is exactly 5 tab-separated fields
(assert the split length, so a sixth field is caught mechanically), both malformed
markers, an empty-residue row rendering `-`, and a residue token containing a tab, a
comma and a `%` that round-trips through decode back to the original token.

#### [V] Correction 5 — a malformed entry degrades the verdict, it is not advisory

The original contract said "`verifies:` → `exact`" and separately "an unparseable
origin → `unknown`", and never said which wins for a list holding both.

Reporting residue is **not sufficient**. If a mixed list still returned `exact` over
only the valid ids, t1569_3 would compute a verdict from a **silently incomplete
origin surface** and could issue `CLEAR` — and its line protocol has no residue field
to catch it. That is precisely the false-confidence case residue exists to expose, so
residue must move the verdict, not annotate it.

This is the framework's own established rule, stated in the parent task for
`aitask_verification_stale.sh`: **"`UNKNOWN` drives the verdict, not advisory — a
path that cannot be checked means the check covers *less* scope than it claims, so
`FRESH` would be a false all-clear."** The same reasoning applies verbatim here.

So: **any unparseable entry disqualifies `exact`.**

| `verifies:` contents | quality | origins |
|---|---|---|
| all entries canonicalise | `exact` | all of them |
| **any** entry unparseable (mixed **or** wholly) | falls through to rule 2 → `topic`, else `unknown` | per the rule reached |
| absent | rule 2/3 | per the rule reached |

An incomplete `verifies:` list is not evidence of an exact origin — we cannot know
what the malformed token pointed at, so the surface derived from it is short by an
unknown amount. Falling through to `anchor` yields `topic`, a coarser but *complete*
signal (anchor is a scalar: it parses or it does not); with no usable anchor the
result is `unknown` → `UNCHECKABLE` downstream. Both outcomes are already degraded by
t1569_3 and t1569_5 on origin quality, so **no new field, verdict, or reason-code is
needed in t1569_3's closed protocol** — the existing quality channel carries it.

The valid ids and the malformed tokens are still fully recoverable via
`resolve_detailed()` and the CLI, so nothing is silently dropped for a human or a
diagnostic path; what is withheld is only the *strongest quality claim*.

### [V] Correction 6 — canonicalize, and reuse the existing seam

The original plan says `task_yaml` normalises ids to `t`-prefixed form. **That is
false for both fields this resolver reads.** `_normalize_task_id` only prefixes a
`^\d+_\d+$` *string* and explicitly preserves int type; `verifies` is not in the
normalise list at all. Measured over the live corpus:

| field | shapes found |
|---|---|
| `anchor` | **167 × `int`** — never a string, never `t`-prefixed |
| `verifies` | 125 × `'t1018_1'`, 59 × `int`, 3 × `'1018_1'` |

The batch map is keyed on bare strings. Uncanonicalised, **every** anchor and 125
of 187 `verifies` entries miss.

**Reuse `.aitask-scripts/lib/dep_resolution.py::canonical_dep_id`** (do not write a
new canonicaliser — CLAUDE.md "Reusable Helpers"). Verified against all five live
shapes: `130`/`'t130'`→`'130'`, `'t85_2'`/`'1018_1'`→`'85_2'`/`'1018_1'`,
unparseable→`None`. A `None` origin resolves to `unknown`, never a silent drop.

Two further rules that are correctness, not style:

- **Do not consult `followup_kind`.** Classification and origin are separate
  concerns; `followup_kind` is settled and is not an input.
- Parse with `task_yaml.parse_frontmatter`, **not** `stats_data.parse_frontmatter`
  (`stats_data.py:394`). **[V]** Its real signature is
  `parse_frontmatter(raw_text) -> (metadata, body, key_order) | None` — it takes
  file *text* and returns a **3-tuple**, not a path and not a dict.

Expose a CLI in the 5-field tab-separated shape of `followup_backfill_classify.py`.

## Step 4 — Acceptance oracle

Whole-corpus byte-equality of `TASKFILES:` against `--task-files`, for **every**
id — the AC as written, unchanged.

### [V] The enumeration is part of the AC, and must be defined

"Every task id in the corpus" is not self-evident, and getting it wrong makes the
oracle pass while never testing the cases this work exists for. Measured:

| enumeration source | ids | what it alone would miss |
|---|---|---|
| (a) on-disk task files — active + archived, parents **and** children | 758 | every id whose files were archived away |
| (b) ids discovered in commit messages | 1597 | **485** ids with no commit at all — i.e. every `UNKNOWN_HISTORY` probe |
| (c) parents implied by any `P_C` id in (a) ∪ (b) | +98 | — |
| **union of all three** | **2180** | — |

**Iterating the commit map alone is the trap**, and it is worse than it looks:
**t1016 — the flagship off-disk-child divergence parent — appears in neither (a) nor
(b)**. It has no `(t1016)` commit and no file on disk; it is reachable *only* through
(c), from its child ids. An enumeration without (c) silently never tests the
divergence this task is designed around.

Enumeration, run once before comparing:

```bash
# (a) on-disk ids
{ ls aitasks/t*.md aitasks/t*/t*.md \
     aitasks/archived/t*.md aitasks/archived/t*/t*.md 2>/dev/null; } \
  | sed -E 's#.*/t([0-9]+(_[0-9]+)?)_.*#\1#'
# (b) ids in commit messages -- NO NUL in this stream (see below)
git log --all --format='%B' | grep -oE '\(t[0-9]+(_[0-9]+)?\)' | tr -d '()' | sed 's/^t//'
# (c) implied parents: for every P_C above, also P
```
sorted `-u` into one list.

**[V] The `%x00` this originally carried silently breaks source (b).** NUL bytes make
grep treat stdin as binary. Verified in this repo: `git log --all --format='%B%x00' |
grep -oE '\(t…\)'` yields **0 lines, exit 1** — not even a "binary file matches"
notice, because `grep` here is **ugrep 7.8.4**, not GNU grep. Source (b) would
collapse to empty, the union would silently narrow to on-disk ids, and the oracle
would run over a reduced set while appearing to work — the exact vacuous-coverage
failure this section exists to prevent, caused by the enumeration command itself.

Fix at the source: the enumeration only regex-scans for `(tNN)`, so it needs no
record boundary — drop `%x00`. (With it, `grep -a` recovers the 1716 matches, but
carrying a NUL that nothing needs is what invites the bug back.) The NUL-framed
parser of Correction 3 is unaffected: it reads **bytes in Python**, never through a
line-oriented text tool. Rule for this task: **NUL-framed streams are parsed
programmatically, never piped through `grep`/`sed`/`awk`.**

**Assert the enumeration before trusting it** — a coverage claim that cannot fail is
worthless (the corpus grows, and a future glob change could quietly drop a source).

**[V] Derive the probes dynamically; do not hardcode ids.** A later legitimate
`(t1016)` or `(t1)` commit would fail a hardcoded test against a perfectly correct
implementation. Compute two classes from the enumeration itself:

| class | definition | count today |
|---|---|---|
| **A — off-disk-child divergence** | no own commit, no on-disk child with a commit, **but** ≥1 commit-referenced child id | **96** |
| **B — no history at all** | no own commit and no commit-referenced child | **460** |

Assertions:

1. **class A is non-empty** and **class B is non-empty** — this is what actually
   guarantees the divergence and no-history cases are exercised;
2. probes are drawn from those classes (e.g. lowest id in each) — `1016` and `1`
   are today's members and are recorded as **diagnostic examples only**, never as
   test literals;
3. its size is ≥ each individual source, and (c) contributed a non-zero count;
4. **source (b) is non-empty** — the direct guard against the grep-binary
   regression above.

Then compare `TASKFILES:` against `--task-files` for **every id in that set**, and
additionally assert `STATUS:` is `UNKNOWN_HISTORY` for the class-A and class-B
probes — the oracle emits empty stdout for both, so path-equality alone cannot
distinguish them.

Already proven on 45 ids covering every hazard class (renames, comma-forms,
commit-only children, `NO_FILES`, 229-path parents, 25 random): **byte-equal,
zero mismatches**. The full 2180-id run is the remaining proof.

### Post-phase (risk mitigations)

**`pin_oracle_unchanged`** — add a characterization test that pins
`--task-files` output for a synthetic fixture task (paths + `FILE|` shape + the
stderr warning on the empty case). It exists so that a future byte-equality
failure is fixed by correcting the batch, never by editing the oracle to agree.

It also pins the **enumeration** (Step 4) by running the real pipeline and
asserting class A and class B are both non-empty, source (b) is non-empty, and source
(c) contributed non-zero — with a negative control showing a commit-map-only
enumeration omits every class-A id. Probes come from the classes, never from
hardcoded ids. Without this the oracle's coverage claim is unfalsifiable.

**`guard_recovered_not_substituted`** — add a test asserting (a) default
`--batch-map` output contains zero `RECOVERED_*` lines, and (b) running with
`--with-recovered` leaves every `TASKFILES:` and `STATUS:` line byte-identical to
the default run, adding only `RECOVERED_*` lines. Include a fixture in the
divergence class (a parent whose commits exist only under an off-disk child id) so
the test actually exercises a non-empty recovered set rather than passing vacuously
— this is Verification item 14's fixture, shared.

Also assert the **documentation** side of the contract, since that is what stops a
later consumer applying recovery inconsistently: `--help` must state that
`UNKNOWN_HISTORY` means "unrecognized by the oracle's disk-derived expansion", and
must name t1569_3 as the only sanctioned `--with-recovered` caller. A grep-level
assertion is enough; the point is that the constraint cannot be dropped silently.

**`pin_cli_record_layout`** — add a test asserting the `followup_origin.py` CLI
emits **exactly five** tab-separated fields on every row (split length, not a regex),
that the two malformed-input markers match `followup_backfill_classify.py`'s shape,
and that a residue token carrying a tab, a comma and a `%` survives encode→decode
unchanged. This is what stops a sixth field or an ambiguous packing from reaching the
shell consumer.

## Key files

- `.aitask-scripts/aitask_revert_analyze.sh` — add `--batch-map`, `--ids-from`,
  `--with-recovered`; update `show_help` output-format block. `--task-files`
  untouched.
- NEW `.aitask-scripts/lib/task_file_sets.py` — pure bucketer.
- NEW `.aitask-scripts/lib/followup_origin.py` — pure resolver.
- NEW `tests/test_task_file_sets.py`, `tests/test_followup_origin.py`,
  `tests/test_revert_analyze_batch.sh`.

Fixture scaffold: `tests/test_change_surface.sh` L36-44 — `FIXTURE_ROOT` is created
in the **parent** shell (`fx="$(new_repo)"` runs in a subshell, so a
`CLEANUP_DIRS+=(…)` inside would be lost). Bash tests using `( … )` subshell bodies
must use `assert_counters_init` / `assert_counters_load` (CLAUDE.md, t1207).

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read ONLY the last line
python3 -m unittest tests.test_followup_origin tests.test_task_file_sets -v
bash tests/test_revert_analyze_batch.sh
shellcheck .aitask-scripts/aitask_revert_analyze.sh
./.aitask-scripts/aitask_revert_analyze.sh --task-files 1555   # unchanged
```

Piping the runner discards its status — use `set -o pipefail` or `${PIPESTATUS[0]}`.

Required tests:

1. **Whole-corpus byte-equality oracle** (Step 4), over the **defined three-source
   enumeration** (2180 ids today). The enumeration's own assertions run *first* —
   class A non-empty, class B non-empty, source (b) non-empty, source (c) non-zero —
   so a silently narrowed enumeration fails loudly instead of passing vacuously.
   **The test must execute the real enumeration pipeline** (the actual shell
   commands, not a Python re-implementation of them): the grep-binary defect lived
   in the pipeline, so only running it can catch that class of regression.
2. `FILES` / `NO_FILES` / `UNKNOWN_HISTORY` fixture-tested in a synthetic repo —
   including a task whose commits exist **only** under a child id, and one with no
   commit at all.
3. **Rename divergence**: a fixture commit renaming a file; assert batch emits
   **both** old and new paths (fails without `--no-renames`).
4. **Comma-form negative control**: `(t100, t101)` matches neither id.
5. Resolver truth table with an explicit **`anchor`-is-never-`exact`** negative
   control, and a `verifies`+`anchor` case asserting `exact` wins.
6. **Canonicalisation across all three live shapes** (`int`, `'t1018_1'`,
   `'1018_1'`) plus an unparseable value.
7. A case proving `followup_kind` is not read (same metadata, different
   `followup_kind`, identical result).
8. **Recovered-field isolation**: default output contains **no** `RECOVERED_*`
   line; `--with-recovered` adds them and leaves `TASKFILES:`/`STATUS:` byte-identical.
9. Live-corpus coverage assertion on **shape** — exact + topic + unknown == total
   follow-ups, no double counting. **Never on frozen counts**: the plan's 86/130/13
   already drifted to **87/129/13 of 229** between writing and verification. Raw
   signals (`verifies` 87, `anchor` 167, overlap 38) must not be summed.
10. Timing regression: batch over the whole corpus stays far under the per-call form.

11. **Adversarial framing fixture** (Correction 3): a synthetic repo containing a
    tracked path with `\x1e` and `\x1f` in its name, and a commit whose message
    body contains both bytes. Assert the map is **correct**, not merely non-empty —
    and include a negative control proving the rejected `\x1e`/`\x1f` framing
    mis-parses that same fixture, so the test cannot pass vacuously.
12. **Framing fail-closed**: feed a truncated / corrupted stream and assert
    `FRAMING_ERROR:` plus a non-zero exit and **no** emitted map.
13. **Resolver contract and residue policy** (Correction 5):
    - `resolve()` returns a **two-tuple** — assert its arity directly, so the
      published contract cannot be widened by a later edit;
    - one case per table row: all-valid → `exact`; **mixed** valid+invalid → **not
      `exact`** (→ `topic` with `anchor`, → `unknown` without); wholly unparseable,
      both with and without `anchor`;
    - the mixed case is the load-bearing negative control: it must fail if an
      implementation returns `exact` over the valid subset;
    - `resolve_detailed()` surfaces the valid origins **and** the malformed raw
      tokens for that same mixed input, proving degradation loses no information;
    - **CLI record layout**: every emitted row splits into **exactly 5** tab-separated
      fields (assert the split length, so a sixth field is caught mechanically), both
      `NO_FRONTMATTER` / `UNPARSEABLE_ID` marker rows match the reference shape, an
      empty residue renders `-`, and a residue token containing a tab, a comma and a
      `%` round-trips through decode back to the original token.
14. **`UNKNOWN_HISTORY` semantics**: a fixture parent whose commits exist only
    under an off-disk child id asserts `STATUS:…|UNKNOWN_HISTORY` in the default
    stream **and** a non-zero `RECOVERED_DIVERGES:` under `--with-recovered` —
    pinning that the two causes are distinguishable exactly where documented.
Record measured perf/coverage in the Final Implementation Notes. **Re-measure — do
not restate the task's figures**: "0.53 s/call" is really 0.098 s–3.03 s depending
on child count, and "2261 commits" is really 21192 walked / 1689 tagged.

Step 9 (Post-Implementation) covers cleanup, archival, and merge.

## Risk

*Reassessed once against the augmented plan after the three inline mitigations were
confirmed and inserted as phase blocks. The framing item's residual drops to low
(it is now pinned first, with a negative control); the levels below describe the
plan as approved. Code-health stays `medium`: two new modules plus a new subcommand
carrying two output products is a real, if bounded, maintainability surface that
tests guard but do not remove.*

### Code-health risk: medium
- The batch and the oracle are two implementations of one definition; they can
  drift after this task lands. · severity: medium · → mitigation: inline post-phase `pin_oracle_unchanged`
- Framing has a silent failure mode: a separator byte in a path or message, or a
  mis-stripped path, corrupts the map *plausibly* — yielding false byte-equality
  passes, not failures. Now structurally addressed (NUL-only framing + fail-closed
  validation), not merely tested. · severity: high · → mitigation: inline pre-phase `pin_path_framing`
- Two path products (`TASKFILES:` vs `RECOVERED_TASKFILES:`) invite a consumer to
  substitute the recovered set for the oracle set, or to apply it inconsistently
  across t1569_3/_4/_5. · severity: medium · → mitigation: inline post-phase `guard_recovered_not_substituted`
- `UNKNOWN_HISTORY` conflates "never landed" with "landed under an off-disk child",
  so a default-stream consumer can read it as "no history exists". · severity: medium · → mitigation: inline post-phase `guard_recovered_not_substituted`
- `verifies:` id shapes are heterogeneous corpus-wide; every future consumer must
  re-canonicalise or silently miss 2/3 of entries. · severity: medium · → mitigation: `normalize_verifies_in_task_yaml`
- Residue is the one CLI field holding raw YAML text; an unencoded tab or newline in
  it would desynchronise the shell consumer's field split. · severity: medium · → mitigation: inline post-phase `pin_cli_record_layout`
- The byte-equality oracle can pass vacuously if the id enumeration silently narrows
  — the commit map alone omits every class-A divergence id and all no-history ids,
  and a NUL in the enumeration stream empties source (b) with exit 1 and no
  diagnostic. · severity: high · → mitigation: inline post-phase `pin_oracle_unchanged`
- Probes pinned to literal ids would fail on a correct implementation as soon as the
  corpus legitimately grows a matching commit. · severity: medium · → mitigation: inline post-phase `pin_oracle_unchanged`

### Goal-achievement risk: low
- Approach is proven end-to-end on the real corpus before implementation: 45
  hazard-class ids byte-equal, full map 0.61 s, three-state contract and the
  canonicalisation seam both validated against live data. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: pin_path_framing | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: framing silent-failure | desc: Pin the NUL-only framing first: adversarial fixture whose path and commit message both contain \x1e/\x1f, a negative control proving the rejected \x1e/\x1f framing mis-parses it, the fail-closed FRAMING_ERROR case, and the leading-newline strip with a control that fails when the strip is dropped.
- timing: post-phase | name: pin_oracle_unchanged | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: batch/oracle drift and vacuous oracle coverage | desc: Characterization test pinning `--task-files` output for a fixture task so the oracle cannot be edited to meet the batch, plus execution of the real three-source enumeration pipeline asserting class A (off-disk-child divergence) and class B (no history) are both non-empty and source (b) is non-empty, with probes drawn from those classes rather than hardcoded ids.
- timing: post-phase | name: guard_recovered_not_substituted | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: recovered-field substitution and UNKNOWN_HISTORY conflation | desc: Assert default output has no RECOVERED_* lines, that --with-recovered leaves TASKFILES:/STATUS: byte-identical over a non-empty divergence fixture, and that --help documents the narrowed UNKNOWN_HISTORY meaning and names t1569_3 as the only sanctioned --with-recovered caller.
- timing: post-phase | name: pin_cli_record_layout | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: CLI protocol drift and residue escaping | desc: Assert every followup_origin.py CLI row splits into exactly five tab-separated fields, that the NO_FRONTMATTER / UNPARSEABLE_ID marker rows match the reference shape, and that a residue token containing a tab, comma and % round-trips through the %-first encoding.
- timing: after | name: normalize_verifies_in_task_yaml | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: heterogeneous verifies id shapes | desc: Add `verifies` to task_yaml's id-normalisation list so consumers stop re-canonicalising; deferred because it changes a shared parser read by every board/ls/monitor consumer and needs its own risk evaluation.

---

## Final Implementation Notes

Landed as planned; every correction the verification pass identified held up
under implementation. Nothing was descoped.

### What shipped

| file | role |
|---|---|
| `.aitask-scripts/aitask_revert_analyze.sh` | `--batch-map` + `--ids-from` + `--with-recovered`; `--task-files` untouched |
| `.aitask-scripts/lib/task_file_sets.py` | NEW — pure bucketer (framing, matching, disk/commit child expansion, three-state status) |
| `.aitask-scripts/lib/followup_origin.py` | NEW — pure origin resolver + 5-field CLI |
| `tests/test_task_file_sets.py` | NEW — 37 tests |
| `tests/test_followup_origin.py` | NEW — 39 tests |
| `tests/test_revert_analyze_batch.sh` | NEW — 44 assertions |

### Measured (this box, 2026-08-28 — re-measured, not restated)

- Corpus walked: **21192 commits**, **1689** carrying a `(tNN)` tag, **46441**
  `(commit, path)` pairs. (The task's "2261 commits / 9680 pairs" were stale.)
- `--batch-map` over the full 2182-id enumeration: **0.575 s**.
- `--task-files` per call: **105 ms** mean over a 60-id sample (range 0.098 s for
  a childless id to **3.03 s** for t635 — the task's flat "0.53 s/call" hid a 30x
  spread; the cost is the per-parent `all-children` shell-out, not the git grep).
- Extrapolated per-call cost for the same enumeration: **229 s** → **~399x**.
- Resolver over 470 active task files: every row exactly **5** tab-separated
  fields; `exact` 88 / `topic` 249 / `unknown` 128, plus **4** `NO_FRONTMATTER`
  and **1** `UNPARSEABLE_ID` — both marker rows occur naturally in the corpus, so
  neither is fixture-only.
- Follow-ups only (the population the plan quotes): **229** → `exact` **87** /
  `topic` **129** / `unknown` **13**, a mutually exclusive partition. Already
  drifted from the task's 86/130/13, which is why the test asserts shape.
- Live residue rows: **0**. The percent-encoding is contract-driven, exercised
  only by fixtures — as intended.

### Acceptance

**Whole-corpus byte-equality oracle: 2182 ids compared, 0 mismatches.** The
enumeration came from the real three-source pipeline (`SRC_A=759`, `SRC_B=1597`,
`SRC_C=140` → `ENUM=2182`), and both probe classes are populated.

Every control was mutation-tested rather than assumed — a control that has never
failed proves nothing. Ten deliberate breakages, each caught:

| mutation | caught by |
|---|---|
| drop the first-path newline strip | 9 failures |
| blanket `.strip()` on every path token | 1 failure (the precise control) |
| drop the fail-closed hash validation | 1 failure |
| loosen the id regex (drop the literal parens) | 2 failures |
| mixed `verifies:` still returns `exact` | 3 failures |
| `anchor` reported as `exact` | 6 failures |
| skip canonicalisation | 18 failures + 1 error |
| encode `%` last (breaks injectivity) | 2 failures |
| widen `resolve()` to a 3-tuple | 9 failures + 5 errors |
| consult `followup_kind` | 1 failure |

### Two defects found by user review (both blocking, both fixed)

1. **`parse_log_stream` was not fail-closed on truncation.** An incomplete
   record header hit `break`, so a *valid prefix followed by a cut-short record*
   returned the good records and exited 0 — a short map indistinguishable from a
   complete one, contradicting Verification item 12. Now: a stream not ending on
   a NUL raises, and a marker with fewer than four following tokens raises.
   Getting this right needed one more byte of care than it first appeared: a
   well-formed record always carries the format-terminating NUL *after* the
   message, so even an empty-message, no-paths commit leaves **four** tokens
   after its marker (`\0sha\0ct\0\0`). A `< 3` guard would have accepted the
   truncated form; the guard is `< 4`. Added a CLI-level test asserting no map
   and a non-zero exit, **with a positive control** proving the same prefix,
   properly terminated, still yields a map — otherwise the assertion would pass
   against a parser that rejects everything.

2. **`resolve_detailed()` discarded the ids that *did* parse.** For
   `{"verifies": ["t42", "not-an-id"]}` it returned `origins: []`,
   `residue: ["not-an-id"]` — the canonical `42` was gone, not merely unclaimed.
   The plan's promise that "the valid ids and the malformed tokens are still
   fully recoverable" was therefore false as implemented, and my own
   `test_degradation_loses_no_information` was too weak: it asserted the residue
   only, so it passed against exactly this bug. Added a distinct
   **`degraded_origins`** field carrying the parsed-but-unclaimed ids, and the
   mixed-input test now asserts `origins`, `residue` **and** `degraded_origins`
   together. Withholding the strongest quality claim is the point; discarding
   the evidence was not.

   Scope note: `degraded_origins` is a **detailed-API field only**. The CLI
   record stays at exactly five fields — a sixth would break the protocol the
   task specifies — so the CLI surfaces residue, and a caller wanting the
   withheld ids uses `resolve_detailed()`.

Re-verified after both fixes: full oracle **2182/2182, 0 mismatches**; the
emitted map is **byte-identical** to the pre-fix map (the parser change rejects
malformed input only); suite `PYTHON SUITE: PASSED`; shellcheck clean.

Three further mutations confirm the new guards bite — reintroducing either
reported defect now fails loudly:

| mutation | caught by |
|---|---|
| restore the `break` on a short header | 2 python failures + 3 bash |
| drop the unterminated-stream check | 1 failure |
| discard the parsed-but-unclaimed ids | 3 failures |

### Two defects found in my own implementation during review

1. **`trap ... RETURN` with a `local` tmpdir.** The trap body is evaluated after
   the function's locals are gone, so under `set -u` it died on the very variable
   it was cleaning up. Replaced with a script-level `EXIT` trap.
2. **`git ls-files` is cwd-relative.** Run from a subdirectory, `TRACKED:` silently
   dropped from 1850 rows to 398 while `TASKFILES:` (repo-relative from
   `git log`) did not — a half-correct map. Both git calls and the `aitasks/`
   glob are now anchored to `git rev-parse --show-toplevel`.

Also fixed: `--ids-from` used `[[ -f ]]`, which rejects a process substitution
(`<(...)` is a fifo). Now `[[ -r ]]` + `cat`, so `<(...)`, a fifo and
`/dev/stdin` all work. Empty-array expansions use the repo's
`${arr[@]+"${arr[@]}"}` idiom (bash 3.2 / macOS `set -u`).

### Deviations from the plan

None in substance. One naming choice: the pure bucketer is
`lib/task_file_sets.py` (the plan named it without fixing the filename), and the
resolver's detailed API is `resolve_detailed()` returning a dict, mirroring
`followup_backfill_classify.classify()`.

### Carried forward

- `resolve_detailed()` returns four keys (`origins`, `quality`, `residue`,
  `degraded_origins`); `resolve()` remains the published two-tuple.
- `RECOVERED_*` ships behind `--with-recovered`, documented in `--help` as
  callable only by `aitask_parallel_admission.sh` (t1569_3), with the
  monotone-toward-less-confidence rule stated there. **t1569_3 must implement
  the two consuming rules** (`UNCHECKABLE_CAUSE:candidate|origin_history_off_disk_children`
  and `CAVEAT:candidate|recovered_history_diverges`) — this slice only produces
  the evidence.
- `normalize_verifies_in_task_yaml` is the spawned "after" mitigation (Step 8d).
