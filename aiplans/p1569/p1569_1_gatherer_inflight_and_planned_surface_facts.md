---
Task: t1569_1_gatherer_inflight_and_planned_surface_facts.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_2_*.md, aitasks/t1569/t1569_3_*.md, aitasks/t1569/t1569_4_*.md, aitasks/t1569/t1569_5_*.md, aitasks/t1569/t1569_6_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-27 15:31
---

# t1569_1 — In-flight / planned-surface facts in the shared gatherer

Frontloaded risk of the t1569 tree: blast radius over every existing trail.

## Context

The implementation-trail RFC lists "in-flight/lock state" as an intended gather
output; `lib/trail_gather.py` has no such probe. t1569's roadmap needs it, and so
does the shared parallel-admission checker (t1569_3). This slice adds **generic
facts only** — scoring, freshness, follow-up semantics and lane policy stay in
the consuming skill.

### Verification pass (2026-08-27) — findings that change the plan

| claim | status |
|---|---|
| `aitask_remote_drift_check.sh:225-230` holds the only extraction | ✅ confirmed |
| `trail_gather.py` `input_line()` L511-520, `member_line()` L523-537, `cmd_snapshot()` L558 | ✅ confirmed |
| `trail_schema._normalize_input_record()` L615 hard-errors on unknown keys (L628-631) | ✅ confirmed — digest exclusion is structural |
| `aitask_query_files.sh` `cmd_inflight` L504-558 | ✅ confirmed |
| `aitask_lock.sh` `list_locks()` fetches at L414-421; `_lock_field()` awk helper already exists at L405-412 | ✅ confirmed — **reuse it**, do not re-author |
| `aiplans/p259_batch_reviews.md` is all-phantom | ✅ **exactly** 45 paths, 0 tracked |
| determinism claim is at docstring "L57-61" | ⚠️ actually **L44**; LINE PROTOCOL block is L22-32 |
| existing tests "will break" | ❌ **false.** `parse_snapshot` (L169-188) silently ignores unknown prefixes; the other suites read parsed keys. Nothing breaks — which also means a silently-absent new line goes unnoticed |
| test isolation is at risk | ✅ **worse**: `SyntheticRepo.__init__` (L58-65) **never runs `git init`**, so `git ls-files` walks UP out of the fixture |
| `.agents/` + `.opencode/` hold stale standalone copies | ❌ **false.** Both are profile-aware **stubs**; `aitask_skill_render.sh:7` renders **every** agent from `.claude/skills/<skill>/SKILL.md.j2`. Editing the `.j2` propagates to codex/opencode automatically — no stale contract, no porting task |

### Measured facts that drive design decisions below

- **The union is incomplete by construction.** Live right now: 4 tasks are
  `Implementing` (t887, t1576, t1555_2, t1569_1); the gate source returns
  `NO_INFLIGHT` (**0 of 4**); the lock tree holds t1555_2, t1569_1, t1576, **t259**.
  So the union **misses t887** (the plan's own "Implementing but unlocked" example)
  and **reports t259**, which is `Ready` and locked since February. *Both probes
  succeed.* This is the single most important constraint on the status vocabulary.
- **Extraction recall is bounded by an extension allowlist.** A plan naming
  `internal/pkg/server.go`, `src/main.rs`, `app/index.ts` yields **zero** tokens —
  the known narrowing recorded at `aitask_remote_drift_check.sh:211-224`. In any
  Go/Rust/JS consumer project the path evidence is empty *by construction*.
- **Argument injection.** The charset `[A-Za-z0-9_./-]` admits a **leading hyphen**;
  the live corpus yields 3 (`-claude.md`, `-agy-/SKILL.md`, `-codex-/SKILL.md`, split
  out of golden filenames). `dirname -claude.md` errored during this verification.
- **`sort -u` is locale-collated; Python `sorted()` is codepoint order.** Under this
  box's ambient `LANG=en_US.UTF-8`: `sort -u` → `a-b.md a_b.md ab.md aB.md`, Python →
  `a-b.md aB.md a_b.md ab.md`. `LC_ALL=C` matches Python.
- **Classification over the live corpus** (1059 distinct paths from all active
  plans): tracked **282** / planned_new **75** / phantom **702**.

## Design decision — extractor is Python-canonical with a shell bridge

Confirmed with the user. Consumers are split: `trail_gather.py` is Python and
t1569_3 specifies "a shell entry point over a **pure Python lib**". A
shell-canonical helper would force both to shell out per plan file or fork the
regex — the exact divergence this extraction exists to prevent.

Mirror the established `followup_kinds` pair exactly:

```
.aitask-scripts/lib/plan_paths.py       <- canonical (extract + classify)
.aitask-scripts/lib/plan_paths_sh.sh    <- lazy, memoised bridge; FAILS CLOSED
```

`plan_paths_sh.sh` follows `lib/followup_kinds_sh.sh` verbatim: `_AIT_..._LOADED`
guard, lazy resolve on first use, memoise, `${_AIT_RESOLVED_PYTHON:-python3}`, and
an `AIT_PLAN_PATHS_DIR` test hook.

### Pre-phase (risk mitigations)

Both run **before** Step 1 touches the extraction.

- **`characterize_extraction_byte_equivalence`** — in `tests/test_remote_drift_check.sh`,
  pin the **current inline** extraction's exact output before moving it. Fixtures:
  an all-phantom plan (the `p259` shape), a leading-hyphen token
  (`SKILL-fast-claude.md` → `-claude.md`), a `./`-prefixed path, duplicate tokens
  requiring dedupe, **and — mandatory — a collation-discriminating pair**
  (`ab.md`, `aB.md`, `a_b.md`, `a-b.md` in one fixture). Without that last pair the
  mitigation passes green while the move silently reorders live output, which would
  make the one test that exists to prove "a move, not a fix" unable to detect the
  change. See the collation decision in Step 1.
- **`gitinit_synthetic_repo_fixture`** — add `git init` plus one commit to
  `SyntheticRepo.__init__` (`tests/test_trail_gather.py:58-65`) and assert
  `git ls-files` resolves **inside** the fixture (a fixture file is found; the real
  repository's files are not). Do this before any classification work.

## Step 1 — Extract the plan-path extractor (independent; do this first)

1. **`lib/plan_paths.py`** — pure, no writes, no network:
   ```python
   _TOKEN = re.compile(r'[A-Za-z0-9_./-]+\.(?:sh|py|md|yaml|yml|json|toml)')
   ```
   Strip a leading `./`, dedupe, sort.

2. **Collation is an explicit decision, not an accident.** The canonical order is
   **codepoint order** (Python `sorted()`). The shell bridge and the rewritten drift
   check therefore sort under **`LC_ALL=C`**, so both sides agree byte-for-byte on
   every locale. This *does* change the drift check's emitted path order versus
   today's ambient-locale `sort -u`. That is safe and deliberate: the intersect at
   `aitask_remote_drift_check.sh:249` is `grep -Fxf`, which is order-independent, so
   no verdict changes — but the reorder is real, is pinned by the collation fixture
   above, and must be stated in the commit message rather than discovered later.

3. **`--validate-tracked` mode**, classifying each path in this order:

   | class | rule |
   |---|---|
   | `malformed` | the token is extraction garbage rather than a path the plan meant — currently a **leading `-`**. Checked **first** |
   | `tracked` | present in `git ls-files` |
   | `planned_new` | parent directory is **non-empty** and is a tracked directory; file is not tracked |
   | `phantom` | anything else, including a root-level untracked file |

   **Why the class is named `malformed`, not `unsafe`.** Step 1 mandates `--`
   before every path and `:(literal)` for every git pathspec, under which a leading
   hyphen *is* safe — so naming the class for danger would state something untrue
   and invite t1569_3 to read a `malformed` tally as a security signal. What these three
   tokens actually are is **extraction garbage**: fragments split out of golden
   filenames like `SKILL-fast-claude.md`. A provenance name says the true thing and
   leaves the word "unsafe" available for a token that genuinely is. The class is
   deliberately open to grow, but **only within what the grammar can produce**:
   `[A-Za-z0-9_./-]+\.(?:sh|py|md|…)` matches neither a colon nor a newline, so
   `:(glob)a.md` extracts as `a.md` and `a\nb.md` as `b.md` — verified. Naming
   those as future cases would mislead whoever tries to add them. The **reachable**
   candidates are absolute paths and parent traversal, which the charset does admit:
   `/etc/passwd.sh`, `../../up.sh`, `..md` all extract cleanly today and are
   defensible additions. Anything outside the charset requires **widening the token
   regex first**.

   **Why it is checked first.** `-claude.md` has `dirname == ''` — the repo root,
   which is trivially tracked — so without this the junk lands in `planned_new`, the
   most actionable class and the exact count t1569_3 reads as new-file collision
   evidence. Garbage must not reach a gating decision.

   **Why `planned_new` requires a non-empty parent, and what that costs.** Measured
   over the live corpus: **428** of 1059 tokens are bare filenames with no directory
   component — prose mentions like `adapter.py`, `adding_a_new_codeagent.md`.
   Without the requirement, the repo root counts as a tracked parent and
   `planned_new` balloons from **75 to 503**, flooding the gating class with prose.
   The requirement is therefore right on balance — but it introduces a **false
   negative that must be recorded beside the moved-file one**: a *genuine* planned
   new top-level file is now unrepresentable. Two tasks both planning to create
   `pyproject.toml` or `CHANGELOG.md` at the repo root is precisely the new-file
   collision t1569_3's coordination lane exists to catch, and under this rule it
   classifies `phantom`. Stated, not discovered by a consumer.

   Pass `--` before any path; use `:(literal)` for git pathspecs (leading-hyphen
   tokens above, plus the fnmatch-globbing hazard `aitask_verification_stale.sh`
   records).

4. **`lib/plan_paths_sh.sh`** — the bridge. Rewrite `aitask_remote_drift_check.sh`
   to source it. Keep the comment block at `:211-224` (it records why there is no
   root allowlist — t1275) with the file reference updated.

5. `bash tests/test_remote_drift_check.sh` must pass **unchanged**.

### `planned_new` — ship the rule, record what it does not buy

The state is load-bearing: without it, 75 of 1059 live paths collapse into
`phantom`, under-reporting exactly the new-file collisions t1569_3's coordination
lane exists to catch.

**Limitation, stated in the contract and pinned by a test:** the rule cannot
distinguish "will be created here" from "used to be here". A *moved* file lands in
`planned_new` (e.g. `aidocs/adding_a_new_codeagent.md`, now under
`aidocs/framework/`). `planned_new` means **"a plausibly-createable location"**,
never "confirmed new work" — t1569_3 must not treat it as authoritative evidence.
A git-history disambiguation pass was considered and deliberately deferred.

**Second limitation, in the opposite direction** (from the non-empty-parent rule in
Step 1): a *genuine* planned new **top-level** file is unrepresentable — two tasks
both planning to create `pyproject.toml` or `CHANGELOG.md` at the repo root
classify `phantom`, and that is exactly the new-file collision t1569_3's
coordination lane exists to catch. Accepted because the alternative floods the
gating class with 428 bare-filename prose mentions (planned_new 75 → 503), but
recorded here so a consumer reads it rather than discovers it.

## Step 2 — `MEMBER_EXT:` (cheapest new line, no probe)

Beside `member_line()` (L523-537):

```
MEMBER_EXT:<ref>|<created_at>|<anchor>|<verifies csv>|<risk_code_health>|<risk_goal_achievement>
```

- A **new line**, never extra fields on `MEMBER:` —
  `DeterminismTests.test_member_record_field_positions` (L1052) pins all 8
  positions specifically to make insertion loud.
- One per member, sorted by ref, emitted immediately after the `MEMBER:` block.
- **Every field is sanitized, and every field has a sentinel.** t1569_3 parses this
  positionally, so a stray `|` breaks the record and an empty field is ambiguous:
  - `created_at` and `anchor` are **free-form hand-editable YAML** and sit at
    positions 2 and 3 — *not* last. Run both through `has_record_breaking()` /
    `sanitize_middle_field()` (`record_protocol.py:98,117`), which the module
    already imports for exactly this hazard.
  - `verifies` → the module-local `_csv_entry()` (L202).
  - `risk_code_health` / `risk_goal_achievement` → `enum_field()`.
  - An absent value renders as the established sentinel (`-` / `INVALID_ENUM`
    semantics) in **all five** fields, never as an empty field.
- These are **display facts** and never enter an INPUT record.

### The compatibility boundary (state it once, test it exactly)

`MEMBER_EXT:` is emitted **unconditionally** — no probe, no network, no git; the
metadata is already read to build `MEMBER:`. It is **non-volatile**: its fields
change only when a task file changes.

That means the default snapshot **does change**, and the claim "output is
byte-identical to the pre-change gatherer" is **false and must not be written**.
The boundary that actually holds, and the one the tests assert:

| property | without `--with-inflight` | with `--with-inflight` |
|---|---|---|
| `DIGEST:` line | **byte-identical** to the pre-change gatherer | byte-identical (same value) |
| `INFLIGHT*`-prefixed lines | **zero** | present |
| `MEMBER_EXT:` lines | present (one per member) | present |
| two runs over unchanged state | **byte-identical to each other** | `INFLIGHT*` may differ; rest identical |

**Only the volatile `INFLIGHT`-prefixed lines are opt-in.** The invariant
protecting existing trails is *digest* identity, not whole-output identity.

## Step 3 — The in-flight probe, behind an opt-in flag

Add `--with-inflight` to the `snapshot` subparser (L1142-1146) and `cmd_snapshot()`.
Without it **no `INFLIGHT*` line is emitted, no lock ref is read, no plan file is
scanned** — that is what keeps every ordinary trail off the network.

**Source union**, tagged by which produced it:

| source | how | why neither suffices |
|---|---|---|
| gated | `aitask_query_files.sh inflight` | needs `Implementing` **and** a `## Gate Runs` heading — today surfaces **0 of 4** |
| locks | local `origin/aitask-locks`, **no fetch** | holds t259 (`Ready`), misses t887 (`Implementing`) |

**Read locks without fetching.** Do **not** shell out to `ait lock --list`: it
performs a network `git fetch` (`aitask_lock.sh:414-421`) and prints ANSI-coloured
human text to **stdout** via `info()`. Resolve locally:

```bash
git rev-parse --verify --quiet origin/aitask-locks^{tree}
git ls-tree <tree>          # -> t<id>_lock.yaml blobs
```

Parse blob keys with the **existing** `_lock_field()` awk idiom
(`aitask_lock.sh:405-412`) — not `grep`, which exits 1 on a missing key and aborts
the listing under `set -euo pipefail` (the t1370 lesson).

Emit:

```
INFLIGHT_SOURCE:<gate|lock>|<ok|degraded|unavailable>|<age_seconds|->|<reason|->
INFLIGHT:<ref>|<gate|lock|both>|<PLAN|IMPLEMENT|POSTIMPL|->|<gate_state>
INFLIGHT_PATH:<ref>|<tracked|planned_new|phantom|malformed|no_tokens|unreadable|no_plan|unclassified>|<path|->
INFLIGHT_SCAN:<n_tasks>|<extractable|partial_extractable|no_extractable_paths|unread|truncated>|<both_sources_ok|one_source_ok|no_source>
```

The summary line carries **three independent axes** — path counts, corpus
extractability, probe health — precisely so a consumer cannot collapse one into
another.

### The status vocabulary claims probe health, never evidence completeness

The earlier `full | partial | uncheckable` naming asserted something the mechanism
**cannot deliver**, and t1569_3 gates parallel admission on it. Live proof: both
probes succeed, yet the union misses t887 and reports the `Ready` t259 — so a
`full` verdict would be a false all-clear arriving through the *vocabulary*, not
through a bug. The parent task forbids exactly this.

So the field reports **only which probes ran cleanly**:

| status | meaning |
|---|---|
| `both_sources_ok` | both probes healthy. **Says nothing about completeness** |
| `one_source_ok` | exactly one probe healthy |
| `no_source` | neither — total evidence loss |

The PINNED contract must carry this sentence verbatim: *a healthy probe is not a
complete one; the gated source requires a `## Gate Runs` ledger and the lock source
tracks locks rather than execution, so neither, nor their union, enumerates every
running task.* t1569_3 derives `UNCHECKABLE` from this line plus its own policy —
this line never pre-empts that decision.

### Sources degrade independently

The lock tree resolves through a *separate* command from the gated scan
(`git rev-parse` exiting 1 has no bearing on `aitask_query_files.sh inflight`,
verified), so a clone with no cached `origin/aitask-locks` — a fresh clone, a
remote-less repo, the test fixture — must still yield **every gated record**.
Discarding them would manufacture the false no-conflict the parent forbids. Each
source is probed, hard-timed-out and reported on **its own line**; `no_source` is
reserved for total loss. `<reason>` is a **closed vocabulary**:

`no_local_ref`, `no_reflog`, `clock_skew`, `timeout`, `unreadable_tree`,
`no_remote`, `scan_error`. **`no_extractable_paths` is deliberately absent** — it
is a corpus property, not a probe failure, and lives on `INFLIGHT_SCAN:` instead.

### Corpus emptiness is a *separate axis* from probe health

Because extraction is capped by the extension allowlist, a Go/Rust/JS project
yields zero tokens for every plan. Without its own code that is indistinguishable
from "scanned, nothing to worry about".

But this is a property of the **plan corpus**, not of either probe: both sources
would report it at once, and a perfectly healthy lock read would get stamped
`degraded` because someone else's plan happens to be written in Go. Putting it on
`INFLIGHT_SOURCE:` would conflate the two axes on the very line that exists to
report probe health only, and would make `degraded` stop implying that anything
went wrong with the probe.

So it lives on `INFLIGHT_SCAN:` as its **own field**, leaving the two axes
independently readable by t1569_3:

| corpus status | meaning |
|---|---|
| `extractable` | every in-flight plan **that was read** yielded ≥1 token |
| `partial_extractable` | among plans that were read, some yielded tokens and some yielded none |
| `no_extractable_paths` | **at least one** plan was read, and none of the plans read yielded a single token |
| `unread` | **no** plan was successfully read at all — nothing to judge |
| `truncated` | the scan did not finish (classification or block budget expired) — corpus extractability is **unknown**, not measured |

`unread` completes the vocabulary. Once the other rows require a successful read,
"nothing was read at all" — every plan unreadable, or no in-flight task has one —
has no value left to carry: `no_extractable_paths` no longer applies, `truncated` is
wrong because nothing expired, and the remaining rows are vacuous. It is the same
unmeasured-versus-measured gap `truncated` fills for expiry, and it must not fall
back to a measured-looking value.

**Unreadable plans are excluded from the corpus judgement, not counted as empty.**
A plan that could not be opened was never read, so counting it as "yielded none"
would let one permissions error or broken symlink force `partial_extractable` and
file an **I/O failure as a durable corpus fact** — exactly what the task-level
`unreadable` sentinel exists to prevent, reappearing one level up. Likewise a task
with **no plan at all** contributes nothing to this axis. The corpus axis judges
*plans actually read*, and nothing else.

`truncated` exists so a timing outcome never masquerades as a corpus fact.
Reusing `partial_extractable` for an expiry would make it stop implying anything
about the corpus — the same conflation this section rejected for
`no_extractable_paths` on `INFLIGHT_SOURCE:`. The distinction is actionable: a
half-Go project is a **permanent scope limit**, an expiry is **retryable**.

`no_extractable_paths` is **not** removed from the `<reason>` vocabulary by
accident — it is removed deliberately, because no probe failure produces it.

The contract states the scope limit explicitly: **path evidence covers only
`.sh .py .md .yaml .yml .json .toml`; a plan in any other language contributes no
paths, and its absence of overlap is not evidence of safety.**

### `INFLIGHT_SOURCE:` age — measure the cache, not the commit

t1569_3's `--lock-freshness` needs **how stale this clone's cache is**, which is
*not* when the last lock was committed on some peer. The two diverge both ways: a
quiet branch fetched a second ago reports days of age, and a peer with a
forward-skewed clock on a branch whose whole purpose is multi-host coordination
yields a **negative** age that reads as maximally fresh.

Use the ref's actual update time:

```bash
git reflog show --date=raw origin/aitask-locks   # -> ...@{<unixtime> +0300}: update by push
```

(Verified here: reflog `1787827607` vs commit `%ct` `1787827605` — same machine, so
they nearly coincide; across hosts they do not. `stat` on
`.git/refs/remotes/origin/aitask-locks` also works but breaks once the ref is
packed, so reflog is the robust choice.)

- **Unit: integer seconds**, `now − <reflog update time>`.
- **No reflog entry** (a fresh clone, or reflogs disabled) ⇒ age `-` with reason
  `no_reflog`, source `degraded`. **Never fall back to commit time** — a plausible
  wrong number is worse than an honest absent one.
- **A negative computed age is a defined case, not an assumption to test against** —
  and it emits `-` with reason `clock_skew`, source `degraded`. **Never clamp it to
  `0`.** Clamping is fail-open and contradicts the `no_reflog` rule directly above:
  `0` is the most plausible-and-wrong value this field can carry — it means "this
  cache was updated this instant", and the field exists precisely so t1569_3 can
  threshold on it. A peer with a forward-skewed clock, on a branch whose whole
  purpose is multi-host coordination, would otherwise yield a maximally-fresh
  reading over an arbitrarily stale cache: the parent's forbidden false all-clear,
  reintroduced through the *value* after the detection got it right. The detection
  is correct; the emission must be honest-absent for the same reason `no_reflog` is.
- Consequently **`-` is the only sentinel** for an unusable age, and no test may
  assert "age is a non-negative integer" as if skew were impossible.
- The `gate` source always reports age `-`: a live filesystem scan has no cache to
  age. Never `0` — absent is not fresh.

### Timeouts — every phase budgeted, including the dominant one

The block has **three** cost phases, not two. Source probing is cheap; the
dominant cost is `INFLIGHT_PATH:` classification — resolving each in-flight task's
plan **via `plan_path_for()`** (never a `p<N>*.md` glob — see the resolver section),
reading it, extracting, and classifying every path (p259 alone contributes 45). Budgeting only the probes would leave the expensive phase unbounded.

| phase | budget | constant |
|---|---|---|
| each source probe | 5 s | `_PROBE_TIMEOUT_S` |
| plan read + classification, total | 10 s | `_CLASSIFY_TIMEOUT_S` |
| whole `--with-inflight` block | **30 s** | `_INFLIGHT_TIMEOUT_S` |

All three are module-level named constants, never literals at the call site.

**The block budget must exceed the sum of its phases, or it is not a backstop.**
5 + 5 + 10 = 20, so a 20 s block budget has **zero** headroom for the only work
that can actually cause it to fire: the single `git ls-files` call, the reflog
read, the plan-file reads, and interpreter overhead — none of which sits in any
phase. 30 s leaves that headroom explicit.

- **`git ls-files` is invoked exactly once**, into an in-memory set reused for every
  path, plus one derived set of tracked directory prefixes. Never once per path and
  never per task — that would be N×M subprocesses over a corpus where a single plan
  contributes 45 paths.
- `subprocess.run(timeout=…)` kills only the **direct child**. The gate probe shells
  out to `aitask_query_files.sh`, which spawns its own `git` children, so a plain
  timeout orphans the grandchildren. Start every probe in its **own process group**
  (`start_new_session=True`) and kill the **group** on timeout, per the framework's
  subprocess-hygiene convention.
- **Defined output state for each expiry** — an expired budget must never silently
  truncate the scan:
  - *source probe* → that source reports `unavailable` / `timeout`; the other source
    is unaffected.
  - *classification* → classification stops, every already-classified path is still
    emitted, every task the classifier never reached emits one `unclassified`
    sentinel, and the corpus axis reports **`truncated`** — never
    `partial_extractable`, which is a durable corpus fact and must not be produced
    by a timing outcome. The counts describe what was actually classified, so the
    accounting invariants still hold.
  - *block* → whatever has been emitted stands, no further `INFLIGHT*` line is
    written, and the corpus axis reports `truncated`. **There is no "un-probed
    source" branch**: under the probe-both-then-classify order both sources have
    already completed or timed out before the block budget can fire, so such a
    branch would be dead code. The block budget is a backstop for the un-budgeted
    work listed above, and it can only fire during or after classification.
- Never fail the snapshot: every degradation is a content state on stdout, exit 0.

### `INFLIGHT_SCAN:` accounting must reconcile

`INFLIGHT_PATH:` carries **eight** class values in two units — four **path**
classes (`tracked` `planned_new` `phantom` `malformed`, one line per extracted
path) and four **task sentinels** (`no_tokens` `unreadable` `no_plan`
`unclassified`, one line per task, path field `-`). Every in-flight task therefore
produces **at least one** `INFLIGHT_PATH:` line.

### Why the summary carries no counts

`INFLIGHT_SCAN:` changed arity in **every** review round — 4 → 5 → 6 → 7 → 8 → 10 →
12 fields — and every change was a newly discovered per-case count. The record's
*shape* was generating the churn, not any individual omission: audited, **10 of
those 12 fields were derivable by a consumer from lines already emitted** (n_tasks
by counting `INFLIGHT:` lines, every path and sentinel count by tallying
`INFLIGHT_PATH:` by class, the no-plan count by differencing the two ref sets).
Only the two enum statuses carried information the detail lines lack. Meanwhile
each addition was a **breaking positional change** to the contract this plan's own
risk section names as most likely to need revision — now guarded by a pin test that
fails on every one. Six rounds of evidence say a seventh case will surface.

So the counts are gone. The summary keeps only what is not derivable, plus
`n_tasks` as the cross-pipeline anchor:

```
INFLIGHT_SCAN:<n_tasks>|<corpus_status>|<source_status>
```

A newly discovered per-case state is now a **new class value inside an existing
field** — additive, non-positional, no schema break, no pin-test failure.

**Standing check before commit:** re-read **every passage that restates the emit
block's behaviour** — not only its counts — against the emit block above. Scoping
this to arity figures would fit the most recent symptom rather than the pattern:
across review, four restatements went stale, and only two were counts.

| stale restatement | kind |
|---|---|
| "four classes, four counts" | count |
| "6 → 7 → 9 fields" | count |
| classification expiry emitting `partial_extractable` in one section, `truncated` in the other | value |
| the Timeouts section still naming `aiplans/p<N>*.md` after the resolver was mandated | reference |
| "no plan ⇒ zero `INFLIGHT_PATH:` lines" surviving the sentinel redesign | behaviour |

The last one would have falsified the headline invariant. A restatement of behaviour
carries the same drift risk as a number, and costs more when it drifts. Verify
against the emit block; do not trust the prose.

### The one invariant that matters, and it spans two pipelines

```
set(refs on INFLIGHT: lines) == set(refs on INFLIGHT_PATH: lines)
n_tasks == |set(refs on INFLIGHT: lines)|
```

`INFLIGHT:` refs come from the **source union**; `INFLIGHT_PATH:` refs come from
the **classification stage**. They are independent pipelines, so a task the
classifier drops — silently skipped, lost to an expiry, mis-keyed — fails this
immediately. That is what the earlier `n_tasks` invariant was reaching for.

The earlier invariants 1 and 2 are deliberately **not** restated: both compared
counts against `INFLIGHT_PATH:` lines produced by the *same loop*, so implemented
the obvious way — increment the counter as you emit the line — they could not fail
for any input. This plan already rejected one such test (verification test 1); it
must not ship two more. **Where a test does tally by class, it must re-derive the
tallies by parsing emitted stdout, never by reading an internal counter.**

**Resolve each in-flight task's plan with the canonical resolver — never a fresh
glob.** `plan_path_for(row, tree)` (`trail_gather.py:358`, "mirrors
`aitask_query_files.sh cmd_plan_file`") already handles both shapes, and
`plan_glob_regex()` (L375) carries both t1532 lessons in its comments:

- **children do not live flat.** `aiplans/p1569_1*.md` resolves **nothing** —
  verified live; the file is at `aiplans/p1569/p1569_1_*.md`. A naive `p<N>*.md`
  glob makes the *dominant* shape of in-flight work resolve no plan: two of the
  four locked entries on this repo right now (t1555_2, t1569_1) are children, and
  t1569 is a six-child family. It would fail in the **safe** direction — sentinel
  or zero lines — which is exactly why it would ship unnoticed while the feature is
  dead for children.
- **a recursive glob is wrong for parents.** Any `**` form sweeps up all six
  children's plans and attributes them to the parent — the t1532 bug that
  `plan_glob_regex()`'s `(?<!p{own_id}/)` lookbehind exists to prevent.

`INFLIGHT_PATH:` then runs Step 1's module over whatever that resolver returns.
When the resolver returns **nothing**, the task emits the `no_plan` sentinel — that
state is the signal t1569_3 turns into its own `UNCHECKABLE`, so it must be
representable, never smoothed away. It is **not** represented as zero
`INFLIGHT_PATH:` lines: every in-flight task emits at least one, which is what makes
the set-equality invariant able to catch a task the classifier dropped.

### `unclassified` — keep "no plan" and "ran out of clock" separable per task

*(Rationale — this describes the design **before** the sentinels, not the emitted
behaviour.)* Without a per-task marker those two causes would be **observationally
identical**: both would yield an `INFLIGHT:` line with zero `INFLIGHT_PATH:` lines. After a classification
expiry every task the classifier never reached would therefore read as "no plan",
and t1569_3 — whose verdict is **per task** — would emit `UNCHECKABLE` for the
wrong reason, or worse, treat a merely-unscanned task as one it has fully seen.
`truncated` on the summary line cannot fix this: it is **global**, and the decision
is per task.

**The same argument covers a third cause.** A plan that exists but references only
`.go`/`.rs`/`.ts` would likewise have emitted nothing, discriminated only by the
**global** corpus field — and in a mixed repo where some in-flight plans are Go and
some are shell, `partial_extractable` tells the consumer nothing about *which* task
it is looking at, so a Go task's plan would read as absent. It gets a sentinel too.

So each zero-path cause is distinguishable **per task**:

| cause | emitted | |
|---|---|---|
| no plan file at all | `INFLIGHT_PATH:<ref>\|no_plan\|-` | — |
| plan exists, yields no extractable token | `INFLIGHT_PATH:<ref>\|no_tokens\|-` | — |
| plan exists but **cannot be read** | `INFLIGHT_PATH:<ref>\|unreadable\|-` | — |
| not reached before a budget expired | `INFLIGHT_PATH:<ref>\|unclassified\|-` | — |

All sentinels carry `-` in the path field, since no path was examined, and all are
counted as **tasks**, not paths — see the accounting section.

**`unreadable` is its own state** (permissions, a broken symlink, a decode error).
Folding it into `no_tokens` would file an **I/O failure as a durable corpus fact** —
the same defect shape this plan already removed twice: a timing outcome on the
corpus axis, and a corpus property on the probe-health axis. The probe axis has
`scan_error` for exactly this; the task axis needs its own. "We could not read it"
must stay separable from "we read it and it had nothing".

**The per-task class is `no_tokens`, not `no_extractable`** — deliberately unlike
the global corpus status `no_extractable_paths`. Three rounds went into keeping the
per-task and global axes separately readable by t1569_3; near-identical names would
re-invite the conflation in logs and in a consumer's field names alike.

**"No plan" gets a sentinel rather than a zero-line asymmetry.** It is the signal
t1569_3 turns into `UNCHECKABLE`, and an explicit `no_plan` line represents it
*more* plainly than an absence does — an absence was detectable only by differencing
two ref sets, and was indistinguishable from a task the classifier dropped. With a
sentinel, **every** in-flight task emits at least one `INFLIGHT_PATH:` line, which
is exactly what makes the set-equality invariant below able to catch a dropped
task.

### Pin the new records' field positions, for the same reason `MEMBER:` is pinned

This plan refuses to add fields to `MEMBER:` precisely because
`DeterminismTests.test_member_record_field_positions` (L1052) pins all 8 positions
and makes insertion loud. The four new records deserve the same guard, and more
urgently: `INFLIGHT_SCAN:` has changed arity at **every** review round
(4 → 5 → 6 → 7 → 8 → 10 → 12, now collapsed to **3**), it ends in **two adjacent enum fields** that a
positional parser reads by index, and this plan's own risk section names the field
set as the part most likely to need revision. Pinning only the record nobody intends to change is
backwards.

Add a characterization test mirroring L1052 for **each** of `MEMBER_EXT:`,
`INFLIGHT_SOURCE:`, `INFLIGHT_PATH:` and `INFLIGHT_SCAN:`: assert the field **count**
and each field's **meaning by index**, with a docstring naming t1569_3 as the
positional consumer. An insertion anywhere but the end must fail loudly rather than
shifting the remaining fields silently.

## Step 4 — Prove the digest exclusion, and fix the determinism claim

The exclusion is **structural**: `_normalize_input_record()` (L615) rejects any key
outside `_RECORD_BASE_FIELDS` + `_ALL_STATE_FIELDS` (L628-631). The rule is simply
*never put these facts in an INPUT record*. Adding a field there would force
`NORMALIZATION_VERSION` → `schema_version` → every stored digest incomparable.

**Amend the module docstring at L44.** "Two runs over unchanged state are
byte-identical" is stated for the **whole output**; volatile lines break it as
written. Scope the claim to digest-relevant lines and name the volatile set
explicitly — exactly the four `INFLIGHT*` prefixes; `MEMBER_EXT:` is non-volatile
and stays inside the determinism guarantee. Also extend the LINE PROTOCOL block
(L22-32) with the five new prefixes.

## Step 5 — Skill contract + goldens, same commit

1. Update the **PINNED** gatherer output contract at
   `.claude/skills/aitask-trail/SKILL.md.j2` (block at L46-78) with the **five**
   new prefixes, stating that all five are digest-excluded but split on
   availability (`MEMBER_EXT:` always; the four `INFLIGHT*` only under
   `--with-inflight`); the Step-2 compatibility boundary verbatim; the
   probe-health-not-completeness sentence; the extension scope limit; and the age
   unit plus closed `<reason>` vocabulary.
   **No porting task is needed** — `aitask_skill_render.sh:7` renders codex and
   opencode from this same `.j2`, and their `.agents/` / `.opencode/` files are
   stubs, not copies.
2. Regenerate the three goldens (this directory holds claude-only variants):
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for p in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       ".claude/skills/aitask-trail/SKILL.md.j2" "aitasks/metadata/profiles/$p.yaml" claude \
       > "tests/golden/skills/aitask-trail/SKILL-${p}-claude.md"
   done
   ```
3. `tests/test_trail_skill_contract.sh` does **not** pin the line set — it asserts
   *prose markers* across all three goldens via `assert_contains`. Add markers for
   the digest-exclusion sentence, the **verbatim** probe-health-not-completeness
   sentence (this is where verification test 5's second half is realized — a
   contract claim is testable as contract text, not as gatherer output), the
   extension scope limit, and both `planned_new` limitations. Match that file's
   existing style.

### Post-phase (risk mitigations)

- **`guard_single_extractor_source`** — the no-fork guard. **Do not match on the
  source literal**: a fork written as `[A-Za-z0-9./_-]` (same class, different
  member order) would pass, while documenting the grammar in `plan_paths.py`'s own
  docstring would make two occurrences and fail it for a documentation reason — a
  guard that fails for innocent reasons trains people to weaken it. Instead assert
  on the **importable symbol**: every consumer resolves the grammar through
  `plan_paths` (import in Python, the bridge in shell), and no other file under
  `.aitask-scripts/` constructs its own `re.compile` / `grep -oE` over a path-token
  class. Model it on the existing seam guards (`tests/test_no_raw_tmux.sh`,
  `BoardSeamGuardTests`).
- **`drift_check_fails_closed_without_python`** — drive
  `aitask_remote_drift_check.sh` with the bridge's Python unresolvable (via the
  `AIT_PLAN_PATHS_DIR` hook / a poisoned `_AIT_RESOLVED_PYTHON`) and assert it
  **fails closed**: a named error, and **never** a silent `NO_OVERLAP`. A false
  all-clear here is indistinguishable from a real one, on the pick hot path.

## Verification

```bash
python3 -m unittest tests.test_trail_gather tests.test_trail_schema -v
bash tests/test_trail_skill_contract.sh
bash tests/test_skill_render_aitask_trail.sh
bash tests/test_remote_drift_check.sh
./.aitask-scripts/aitask_skill_verify.sh          # CLAUDE.md: mandatory before committing any .j2 change
shellcheck .aitask-scripts/aitask_remote_drift_check.sh .aitask-scripts/lib/plan_paths_sh.sh
./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task 1569
./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task 1569 --with-inflight
```

New tests in `tests/test_trail_gather.py`:

1. **The digest hazard, pinned by a test that can actually fail.** The obvious
   version — snapshot, acquire a lock, snapshot again, assert `DIGEST:` identical —
   **cannot fail**: `DIGEST:` is `trail_schema.input_digest(records)` at
   `trail_gather.py:664`, computed over INPUT records only, while the new lines come
   from a wholly separate code path. It would pass on day one and forever regardless
   of the implementation, retiring the concern without testing it. Pin the **real**
   hazard instead — a maintainer moving one of these facts into an INPUT record —
   by constructing a record carrying an in-flight key and asserting
   `_normalize_input_record()` raises its unknown-key error. Keep the
   lock-acquisition scenario as a *complementary* assertion that the `INFLIGHT:`
   lines do change while the digest does not.
2. **The compatibility boundary, asserted as it actually is**:
   - without `--with-inflight`, **zero** lines match `^INFLIGHT`;
   - without `--with-inflight`, `DIGEST:` equals the pre-change gatherer's digest
     for the same state (pin the value);
   - two default-mode runs are byte-identical **to each other**, with `MEMBER_EXT:`
     present in both.
3. **Freshness field** — four cases, since the value gates a downstream decision:
   reflog present ⇒ integer age from the **ref update** time; no reflog ⇒ `-` +
   `no_reflog` + `degraded`; a **skewed (future) ref time** ⇒ `-` + `clock_skew` +
   `degraded`, asserting specifically that the age is **not** `0` (the fail-open
   value); the `gate` source always `-`, never `0`. No case asserts a non-negative
   integer as if skew were impossible.
4. **Independent source degradation** — with the lock ref removed but gated
   in-flight tasks present, the gated `INFLIGHT:` records are **still emitted** and
   the status is `one_source_ok`, with the loss named on the `lock` line. `no_source`
   **only** when both fail, emitting zero `INFLIGHT:` lines and all-zero counts.
5. **Status claims probe health only** — a fixture where both probes succeed while
   a known-running task is absent from the union still reports `both_sources_ok`.
   This is the t887 case, made deterministic. The companion claim — that no line
   asserts completeness — has **no executable form here** and must not be written as
   a pseudo-assertion that would be silently skipped or weakened; it is realized
   where the claim actually lives, as an `assert_contains` marker for the verbatim
   probe-health-not-completeness sentence in `tests/test_trail_skill_contract.sh`
   (Step 5.3).
6. **Corpus axis is independent of probe health** — an in-flight task whose plan
   references only `.go`/`.rs`/`.ts` files yields exactly one
   `INFLIGHT_PATH:<ref>|no_tokens|-` sentinel (not zero lines) and
   `no_extractable_paths` **on `INFLIGHT_SCAN:`**, while both `INFLIGHT_SOURCE:`
   lines still report `ok`. Assert all three: the emptiness is surfaced per task,
   the global axis agrees, *and* a healthy probe is not stamped `degraded` for a
   corpus property.
7. **The cross-pipeline invariant** — over a fixture mixing all eight class values:
   `set(refs on INFLIGHT:) == set(refs on INFLIGHT_PATH:)`, and
   `n_tasks == |set(refs on INFLIGHT:)|`. Then inject a **dropped task** (a task the
   classifier skips) and assert the test **fails** — a positive control, because the
   whole point is that the two sides come from independent pipelines. Any tally the
   test computes must be re-derived by **parsing emitted stdout**, never by reading
   an internal counter: a counter incremented on the same line it counts cannot
   disagree with itself, which is the un-failable shape this plan rejected for
   verification test 1.
7b. **Parent/child plan resolution** — the fixture must carry a **parent with
   children**, since `test_trail_gather.py`'s existing plan fixtures are flat and
   would not catch this. Assert: a child in-flight task resolves
   `aiplans/p<P>/p<P>_<C>_*.md` and emits real `INFLIGHT_PATH:` lines (a naive
   `p<N>*.md` glob resolves **nothing** and would emit a sentinel instead — failing
   safe and therefore silently); and a **parent** in-flight task resolves only its
   own plan, never its children's (the t1532 lookbehind). Drive it through
   `plan_path_for()`, not a locally-written glob.
7c. **`unreadable` stays separable from `no_tokens`, on both axes, in both the mixed
   and the total case** — a plan file made unreadable (chmod / broken symlink /
   undecodable bytes) emits the `unreadable` sentinel, **never** `no_tokens`. Two
   corpus assertions, because the earlier single one left the total case open:
   - *mixed* — one unreadable plan among healthy ones: the axis still reads
     `extractable`, not `partial_extractable`;
   - *all unreadable* — the axis reads **`unread`**, not `no_extractable_paths`;
     a total I/O failure must not be filed as a measured corpus fact.
8. **Classification**, including: an all-phantom plan (the `p259` shape, 45 paths /
   0 tracked); a leading-hyphen token classified `malformed`, **never** `planned_new`;
   a root-level untracked file classified `phantom`, not `planned_new`.
9. **`planned_new` is not "new work"** — a path whose file was moved away classifies
   `planned_new`; pin it so the limitation is executable, not prose.
10. **Collation** — the extractor's output order matches `LC_ALL=C sort -u` and
    differs from ambient-locale `sort -u`, over the `ab/aB/a_b/a-b` fixture.
11. **Extend, do not "fix", the existing suites.** `parse_snapshot` ignores unknown
    prefixes, so a silently-absent new line would go unnoticed. Teach it the new
    prefixes and add explicit presence/absence assertions.
12. **Test isolation** — the probe needs an injectable seam **plus** an env
    kill-switch. `run_cli` calls `trail_gather.main()` **in-process** (L149-153), so
    an `os.environ` kill-switch works and monkeypatching is viable.
13. **Every budget has its own test** — the earlier list covered probe timeout
    only, tested classification expiry for accounting alone, and left block expiry
    untested:
    - *probe* → `unavailable`/`timeout` for that source only, and **no orphaned
      grandchild process** (assert the process group is gone);
    - *classification* → already-classified paths still emitted, unreached tasks
      each emit one `unclassified` sentinel, corpus axis `truncated`, accounting
      invariant still holds;
    - *block* → fires with the un-budgeted work stretched past the headroom;
      asserts corpus `truncated` and that **no** `INFLIGHT_SOURCE:` line claims an
      un-probed source (the branch that would be dead code).
13b. **All four zero-path causes are separable per task** — one fixture carrying an
    in-flight task with no plan, one whose plan is Go-only, one whose plan is
    unreadable, and one skipped by an expiry: one `no_plan`, one `no_tokens`, one
    `unreadable`, one `unclassified` sentinel respectively. Assert per-task
    distinguishability, not merely that a global axis changed — the global field
    cannot answer a per-task question in a mixed repo.
13c. **Field positions and units pinned** — for each of the four new records, assert
    the field **count** and per-index meaning, mirroring
    `test_member_record_field_positions` (L1052). `INFLIGHT_SCAN:` has **3** fields;
    the docstring must name t1569_3 as the positional consumer **and** record that
    `INFLIGHT_PATH:`'s eight class values span **two units** — four
    path classes and four task sentinels — so a later reader cannot re-merge them.
14. An in-flight task with **no** plan file ⇒ `INFLIGHT:` present, zero
    `INFLIGHT_PATH:`.

Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Risk

Levels are the **reassessment against the augmented plan** (the four inline phases
included), per `risk-evaluation.md`'s reassessment note.

### Code-health risk: medium
- `aitask_remote_drift_check.sh` is **pure shell today** and gains a Python
  dependency via the bridge; it runs on every pick's pre-implementation path and on
  merge-target sync · severity: high ·
  → mitigation: inline post-phase drift_check_fails_closed_without_python
- The extraction is a "move, not a fix", and `sort -u` vs `sorted()` collation means
  the moved implementation **does** reorder output unless the collation is pinned ·
  severity: medium · → mitigation: inline pre-phase characterize_extraction_byte_equivalence
- The "do not fork this regex" contract is prose only; three more consumers are
  coming · severity: medium · → mitigation: inline post-phase guard_single_extractor_source
- Blast radius spans the shared gatherer (every trail), the drift check, a PINNED
  contract, 3 goldens and 3 test suites · severity: medium · → mitigation: None
  (accepted residual — the default-off flag and the structural digest exclusion
  bound it; the digest-identity test pins it)

### Goal-achievement risk: medium
- **The union cannot enumerate every running task, and no amount of implementation
  quality fixes it** — measured live: t887 invisible, t259 falsely present. The plan
  answers this by making the status claim probe health only and pushing the
  completeness judgement to t1569_3, but a consumer that misreads `both_sources_ok`
  as "safe" still gets a false all-clear · severity: high ·
  → mitigation: None (accepted residual — the contract states the caveat verbatim
  and test 5 pins it; genuinely fixing recall needs t1343's declared-claims backend,
  which the parent already tracks as an adoption follow-up)
- Path evidence is capped by the extension allowlist, so in a Go/Rust/JS project it
  is empty by construction · severity: medium ·
  → mitigation: None (accepted residual — surfaced as `no_extractable_paths` and
  stated as a scope limit, rather than silently reading as clean)
- `SyntheticRepo` has no git repo, so classification is untestable and the suite is
  machine-dependent · severity: medium ·
  → mitigation: inline pre-phase gitinit_synthetic_repo_fixture
- The five lines are a **forward contract** for siblings not yet written. Three
  review rounds caught schema defects here — a missing freshness field, a missing
  `planned_new` count, one dead source discarding the other, a completeness claim
  the mechanism cannot honour, a fail-open skew clamp, a corpus property on the
  probe-health axis, and two causes collapsing to one observable — and
  `INFLIGHT_SCAN:` changed arity at every round before being collapsed to 3 derivation-free fields. The field set remains the
  part most likely to need revision · severity: medium · → mitigation: None
  (accepted residual, now bounded two ways — all five lines are digest-excluded and
  purely additive, so a later field costs a goldens regeneration rather than a
  migration; and the new per-record positional pins make any future insertion fail
  loudly instead of silently shifting a consumer's indices)

### Planned mitigations
- timing: pre-phase | name: characterize_extraction_byte_equivalence | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — moved extractor not proven byte-equivalent, incl. locale collation | desc: Pin the current inline extraction's exact output over all-phantom, leading-hyphen, ./-prefix, duplicate and collation-discriminating fixtures before moving it
- timing: pre-phase | name: gitinit_synthetic_repo_fixture | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — classification untestable, suite machine-dependent | desc: git init + one commit in SyntheticRepo, asserting git ls-files resolves inside the fixture
- timing: post-phase | name: guard_single_extractor_source | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — no-fork contract is prose only | desc: Guard asserting every consumer resolves the grammar through the plan_paths symbol, not a source-literal match
- timing: post-phase | name: drift_check_fails_closed_without_python | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — new Python dependency on the pick hot path | desc: Assert the drift check fails closed with a named error, never a silent NO_OVERLAP, when Python is unresolvable
