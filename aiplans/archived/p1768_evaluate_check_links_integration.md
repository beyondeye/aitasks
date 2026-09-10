---
Task: t1768_evaluate_check_links_integration.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1768 — Decide the two deferred `check_link_relevance.py` questions

## Context

t1759 shipped `website/check_link_relevance.py`: a source-side report that flags
internal doc links whose target page *exists* but never mentions the subject the
link text names — the class `hugo build` and `check_links.py` both build green on.
It deliberately left two questions open, because it had produced exactly **one**
sweep and answering either from that sweep would have been tuning the heuristic
against its own output:

1. Is any part of the heuristic precise enough to fold into `check_links.py` as a
   **non-blocking warning**?
2. Should coverage widen past backtick-quoted link text?

This task answers both **with measurements**, and leaves behind the harness that
made the measurement possible — so the next precision question does not start
from one sweep again.

### Evidence gathered during planning

The detector's `scan(content_dir)` is a pure function of a content tree and runs
**no** self-controls; one sweep is ~63 ms. Replaying it over **every commit
touching `website/content` up to `9cb61927c`** (352 at the time of the sweep; 353
by the end of this planning session) yields **11 distinct records over that
range** — 6 of which the corpus itself later resolved, for reasons entirely
independent of a detector that did not exist until the day before. That
independence is what makes them usable as ground truth:

| record | fate |
|---|---|
| `aitask_lock.sh` → `/docs/commands/lock/` | live today |
| `ait board` → `/docs/tuis/board/reference/#task-metadata-fields` | live today |
| `ait minimonitor` → `/docs/tuis/minimonitor/how-to/#…` | live today |
| `/aitask-pick` → `/docs/skills/aitask-pick/parallel-admission/` | live today |
| `/aitask-pickweb` → `/docs/skills/aitask-pickweb/#execution-profiles` | gone — anchor dropped from the link |
| `ait artifact` → `/docs/commands/task-management/` | **fixed by t1707** — true positive |
| `ait artifact` → `/docs/workflows/implementation-trails/` | **fixed by t1707** — true positive |
| `ait git` → `/docs/commands/sync/` | gone — the *target page* later documented `ait git` |
| `ait codebrowser` → `/docs/commands/board-stats/` | gone — target later documented it |
| `cli_help` → `/docs/commands/codeagent/` | gone — passage deleted (agy migration) |
| `ait ide` → `/docs/installation/terminal-setup/` | gone |

**Three of these exist only in trees that fail today's corpus self-controls**
(`ait codebrowser`, `ait ide`, `/aitask-pickweb`: 1, 1 and 48 sweeps, with the
corpus controls passing in none of them). The three control pages were added
between 2026-02-19 and 2026-05-13, so roughly half of the swept history predates
them. That fact decides how replay must work — see step 2.

Coverage-widening prototypes over the **620** internal links whose text carries
no backticked token (602 have ≥1 content word after stopwording):

- "any content word appears in the target body" → **1** record. Vacuous.
- "every content word must appear" → **20**, or 16 after excusing words present
  in the target's URL path or title — and those 16 are almost all generic-noun
  false positives (`Board documentation`, `Gates CLI reference`, `Workflows
  index`, `installation troubleshooting notes`).

Shortcode-generated internal links in the whole corpus: **~6**, all landing-page
marketing titles (3 `blocks/feature url="…"`, 3 `tour-tile`).

## Decisions this task records

**Q1 — do not fold anything into `check_links.py`.** Its input is built HTML,
which has thrown away the `source_file:line` that is the only thing making a
relevance record triageable; it gates the deploy, and a heuristic with a known
false-positive rate must never be able to block it. The division-of-labour
contract already forbids either script growing into the other's job, and nothing
measured here argues for breaking it.

**Q2 — do not widen coverage.** Prose link text has no formulation between
vacuous (1 record) and noise (16 records, ~15 false positives), and the shortcode
gap is six marketing titles. Both boundaries move from "deferred, not yet
evaluated" to "evaluated and declined", with the harness recorded so either can
be re-opened against evidence rather than intuition.

**Precision instead: classify, never suppress.** The refinement t1759 measured but
refused to apply does generalize — but not in the form t1759 sketched. "The
stemmed token appears in the target's URL path" is too loose: matching *sub-words*
of a path segment labels `ait board` → `/docs/commands/board-stats/` and
`ait setup` → `/docs/installation/terminal-setup/`, which are two different
commands and a grouped page — the t1707 shape itself. Matching **whole path
segments** reproduces the identical 5-classify / 6-survive split over all 11
historical records, needs no length floor, and refuses both.

And it lands as a **label plus a counter**, never a suppression: suppressing would
take today's report to zero records, which is precisely the "make its own output
look clean" hazard t1759 named.

## Implementation

### Pre-phase (risk mitigations)

1. `[freeze_history_baseline]` Build **step 2** (the history harness) first, run
   it, and paste its aggregated output — the 11 distinct
   `(source, token, url, scope)` records with sweep counts — into this plan under
   a `### Frozen baseline` heading, together with the expected classification for
   each. The `scope` column is what makes an expected classification checkable at
   all, since the classifier labels page-scoped misses only. Only then write the
   classifier of step 1. Writing the rule first and measuring after is how a
   heuristic gets tuned to its own output, which is the thing t1759 refused to do.

   **Stamp the table with its terminal SHA and rev-range** (`git rev-parse HEAD`
   and the range swept), and phrase every count as scoped to that range — never
   "all history". The counts in this plan were taken at `9cb61927c`; the
   content-commit count moved from 352 to 353 *during this planning session*, so
   an unstamped table is unreproducible within a day and a reader cannot re-derive
   the 5/6 split the whole precision claim rests on. The same stamp goes on the
   docstring's copy of the table.

### Frozen baseline

Taken **before** `subject_of_page` existed (pre-phase `freeze_history_baseline`),
by `website/check_link_relevance_history.py` over `--range HEAD` with tip
**`97f238c3c`** — **358** content commits swept, 0 skipped; ENGINE control
passed; CORPUS controls reported not applicable. (The range grew from 352 → 358
between planning and this freeze: main advanced mid-session.)

| sweeps | source | token → target | scope | expected label |
|---:|---|---|---|---|
| 1 | `docs/commands/_index.md` | `ait codebrowser` → `/docs/commands/board-stats/` | page | no — `codebrowser` is not a segment |
| 164 | `docs/commands/_index.md` | `ait git` → `/docs/commands/sync/` | page | no |
| 1 | `docs/commands/_index.md` | `ait ide` → `/docs/installation/terminal-setup/` | page | no — `ide` ≠ `terminal-setup` |
| 20 | `docs/development/task-format.md` | `ait artifact` → `/docs/workflows/implementation-trails/` | page | **no — t1707 true positive** |
| 117 | `docs/installation/known-issues.md` | `cli_help` → `/docs/commands/codeagent/` | page | no |
| 27 | `docs/skills/aitask-trail.md` | `ait artifact` → `/docs/commands/task-management/` | page | **no — t1707 true positive** |
| 76 | `docs/tuis/monitor/how-to.md` | `ait minimonitor` → `/docs/tuis/minimonitor/how-to/` | `#how-to-mark-an-agent-as-prioritized` | no — anchored, never labelled |
| 48 | `docs/workflows/claude-web.md` | `/aitask-pickweb` → `/docs/skills/aitask-pickweb/` | `#execution-profiles` | no — anchored |
| 192 | `docs/workflows/crash-recovery.md` | `aitask_lock.sh` → `/docs/commands/lock/` | page | **yes** — key `lock` |
| 15 | `docs/workflows/parallel-development.md` | `/aitask-pick` → `/docs/skills/aitask-pick/parallel-admission/` | page | **yes** — key `aitask-pick` |
| 148 | `docs/workflows/risk-evaluation.md` | `ait board` → `/docs/tuis/board/reference/` | `#task-metadata-fields` | no — anchored |

**Expected: 2 labelled, 9 unlabelled.** The plan's "5 classify / 6 survive" is the
URL-matching rule alone; the page-scope restriction then withholds the label from
the three anchored ones (`ait minimonitor`, `/aitask-pickweb`, `ait board`). Both
t1707 records stay unlabelled either way. Implementation must reproduce exactly
this column; any divergence is a defect in the rule, not a reason to edit the
table.

**Deviation recorded (step 1c):** `CORPUS_CONTROLS` is derived as the complement
of a named `ENGINE_CONTROL_NAMES` set rather than kept as a second hand-maintained
list. "A control in neither list" is then impossible by construction, and a new
control defaults to CORPUS — the fail-safe direction for replay. The planned
partition test becomes a test that every `ENGINE_CONTROL_NAMES` entry names a real
control, which is the hazard the derivation leaves open: renaming a probe would
otherwise drop it silently into CORPUS.

### 1. `website/check_link_relevance.py` — the classifier, and an engine/corpus control split

**1a. `subject_of_page(token, url) -> bool`**, a module-level pure function next to
`stem()` / `heading_slug()`:

```python
# Section directories are not subjects: every URL starts with one, so matching
# them would classify a link whose text happens to say `docs` or `commands`.
SECTION_SEGMENTS = frozenset({
    "docs", "commands", "skills", "tuis", "workflows",
    "concepts", "installation", "development", "blog",
})

# Stripped only when it follows a literal '.' in the RAW token. A bare trailing
# word is never an extension: `ait gate pass` must keep `pass`, and a rule that
# drops any final word matching an extension list silently shortens the key of
# every command whose last word happens to collide.
TOKEN_EXTENSIONS = frozenset({"sh", "py", "md", "json", "yaml", "yml", "txt"})
```

Keys, derived in this exact order:

1. from the **raw** stemmed token, strip a leading `/` and a trailing `.<ext>`
   suffix when `<ext>` is in `TOKEN_EXTENSIONS`;
2. slugify what remains: `re.sub(r'[^a-z0-9]+', '-', raw.lower()).strip('-')`;
3. split on `-`, drop leading `ait` / `aitask` words, rejoin.

Both the full slug and the prefix-stripped form are keys: `aitask_lock.sh` →
`{aitask-lock, lock}`, `/aitask-pick` → `{aitask-pick, pick}`, `ait gate pass` →
`{ait-gate-pass, gate-pass}`. Classify iff those intersect the target's **whole**
path segments minus `SECTION_SEGMENTS` — never the segments' `-`/`_` sub-words.

**Only page-scoped misses are labelled.** A path describes a *page*; an anchored
miss is a verdict about a *section*, which the path cannot vouch for — and the
anchored case already has its own lever in `scope_narrowed_verdict`. This also
keeps the report visibly incomplete: labelling anchored records would tag 4 of
today's 4 and reach t1759's optics hazard by another route. Today the split is
2 labelled / 2 residual.

In `check()`: add a `subject_of_page` counter and a sixth `Miss` field
(`subject: bool = False` — a `NamedTuple` default keeps `_probe_scope_narrowing`
and every positional construction working; there is exactly one construction site).

In `main()`:
- tag the record line (`… [page] [subject-of-page]`) — a counter alone says *how
  many* but not *which*, and `grep -v` is then the filter, so no record-hiding
  flag is needed;
- print residual records **first**, labelled ones after, so the top of the output
  is the part that needs reading;
- print `subject-of-page: N` beside `scope-narrowed: N`, **with its live base
  rate** (`label matches M of K resolved token links`). The label is true of
  roughly four in five internal token links, so it is informative only
  conditional on already being a miss; printing the rate every run beats
  documenting a number that goes stale with the next docs commit;
- **exit status unchanged**: still 0 with records reported, non-zero only on a
  failed self-control.

**1b. A new engine control, `_probe_subject_classification()`**, mirroring
`_probe_scope_narrowing()`: synthetic input asserting **both** directions
(`ait probe` → `/probe/` classifies; `ait artifact` → `/task-management/` does
not), driven through the real `check()` path. The classifier's failure-*closed*
mode (classifies everything) makes the report look fully explained, and at a ~77%
base rate that is invisible on the summary line.

**1c. Split `CONTROLS` into two named lists**, keeping `CONTROLS` as their
concatenation in today's order plus the new probe last, so every existing control
name is unchanged:

- `ENGINE_CONTROLS` — prove the *machinery* works, on synthetic input:
  `anchor scoping narrowed the check` and the new subject-classification probe.
  Valid against **any** tree, past or present.
- `CORPUS_CONTROLS` — prove the extractor and resolver work *on this corpus*,
  keyed on specific live pages: `extractor captured the control link`,
  `relevance check reports a hit`, `stem normalization strips a flag`,
  `page-relative relref resolved`. Meaningless on a tree that predates those
  pages.

This split is what makes historical replay possible without weakening anything:
the live CLI keeps running all of `CONTROLS`, exactly as today.

**1d. Docstring**: record both decisions; the 11-record table **stamped with its
terminal SHA and rev-range**; and the **historical-replay contract** — replay goes
through `scan()` plus `ENGINE_CONTROLS`, never through `main()` or `--report`,
because `CORPUS_CONTROLS` key on pages a past tree does not contain. The table is
what stops the next task re-litigating this; the contract is what stops the next
change to `main()` from silently breaking the replay.

### 2. `website/check_link_relevance_history.py` — the multi-sweep harness

**Python, importing the module — not a shell loop over the CLI.** The CLI is the
wrong interface for replay, and it is about to change: `--report` today returns
before `evaluate_controls()` (so it always exits 0), and **t1770**
(`harden_check_link_relevance_self_verification`, `Ready`) will make it evaluate
its controls and fail closed. After that, replaying any tree older than the
corpus control pages exits non-zero. Treating such a sweep as "unavailable" would
discard `ait codebrowser`, `ait ide` and `/aitask-pickweb` entirely — shrinking
the evidence from 11 records to 8 and the split from 5/6 to 4/4 depending only on
which task landed first. Calling `scan()` directly makes the harness independent
of that ordering by construction.

The harness:

- enumerates commits touching `website/content` over a rev-range (default: all),
  extracts each with `git archive <sha> website/content` into a temporary
  directory, and calls `clr.scan()` on it. Commits with no `website/content` are
  skipped and counted, never fatal;
- runs **`ENGINE_CONTROLS` once** against the current module and **fails closed**
  if any fails — the replay is only as sound as the machinery it runs;
- reports **`CORPUS_CONTROLS` as not applicable to historical trees**, visibly and
  by name, on every run. Skipped is not passed, and must never print as success;
- aggregates `Miss` records by **`(source, token, url, scope)`**, read straight
  from the `NamedTuple` fields — no parsing of printed output. `scope` is part of
  the key because a link that moves between page-scoped and anchored
  (`/aitask-pickweb` did exactly that) is a different case under the classifier —
  one labelled, one not. The line number is **not** in the key: it drifts with
  every edit above it. Emits the table with per-record sweep counts and the
  subject-of-page label;
- prints the terminal SHA, the rev-range, the commit count, the skipped count and
  the elapsed time, so the output is its own provenance stamp;
- has a **HEAD self-control, guarded on a clean tree**: `scan()` of the archived
  `HEAD` must yield the same record set as `scan()` of the working tree's
  `website/content`. Both sides go through the same `scan()`, so this checks the
  replay-specific pipeline — archive path, extraction, content-root discovery —
  which is exactly what rots. It runs only when
  **`git status --porcelain -- website/content` is empty**: not
  `git diff --quiet HEAD`, which does not see untracked files, so a brand-new page
  would make the control fail while the tree reported as clean (confirmed during
  planning). Local edits there are normal — one exists right now,
  `docs/commands/setup-install.md` — so otherwise it **skips loudly**, naming the
  differing paths;
- accepts **`--repo <path>`**, defaulting to its own repo root, so the test can
  drive a throwaway repo instead of this repository's permanent history. All git
  calls pass `cwd=` — the process never `chdir`s;
- is **never wired to CI**, and exits 0 with records reported.

### 3. `website/check_links.py` — record the Q1 decision where it would be broken

Its docstring carries no division-of-labour note today; the prohibition lives only
in `check_link_relevance.py` and the README. Add the Q1 = NO decision to its "Two
deliberate policies" region — this is the file a future contributor opens to add
the warning, so it is where the answer has to be. Docstring only; no behaviour
change.

### 4. `tests/test_check_link_relevance.py`

Reuse `SiteTestCase` / `FixtureSite` / `assertReported` / `assertNotReported`;
synthetic trees only, never the real corpus.

- new `SubjectOfPageTests`, modelled on `ScopeNarrowedVerdictCounterTests`
  (including its fourth test's shape: a fixture where nothing classifies must
  still pass the control):
  - a page-scoped subject-of-page link is **still reported**, tagged, counter fires;
  - **negative control**: the t1707 shape does **not** classify;
  - **the refinement itself**: `ait board` → `/docs/commands/board-stats/` must
    NOT classify — a live corpus shape, and the whole reason for whole-segment
    matching;
  - `ait ls` → `/docs/tools/` does not classify (vacuous under segment matching —
    say so: it can only fail if matching regresses to substrings);
  - **positive key-order test**: `subject_of_page("aitask_lock.sh",
    "/docs/commands/lock/")` classifies — the one live shape whose key depends on
    stripping `.sh` before slugging;
  - **negative extension test**: `subject_of_page("ait gate pass",
    "/docs/commands/gates/")` does not, and `gate-pass` survives in its key set —
    an ordinary final command word is never mistaken for an extension;
  - anchored vs. page-scoped: same token and target, differing only in the label;
  - the counter does not fire for a genuinely unrelated target.
- `ControlFailureTests.CONTROL_NAMES` is an **exact-equality tripwire** — extend it
  for the new control, which then gets "each control failing alone fails the CLI"
  coverage for free.
- **a partition test**: `ENGINE_CONTROLS` and `CORPUS_CONTROLS` are disjoint and
  together equal `CONTROLS`, so a future control cannot be added to neither list
  and silently escape both the live CLI and the replay.
- `ScopeProbeControlTests`-style tests that `_probe_subject_classification` fails
  when the classifier is patched to `lambda *_: True` **and** to `lambda *_: False`.
- assert `KnownClassControlTests`' case-1 miss is **unlabelled**, in the new class —
  leave `KnownClassControlTests` itself untouched; it is the acceptance floor.
- extend `ExitStatusTests` rather than duplicating it.
- `CoverageBoundaryTests`' docstring becomes the durable record of the Q2
  decision: the 620 non-backticked links, 20 records under all-content-words, 16
  after the URL/title excuse, overwhelmingly generic nouns.
- pin the new record-line format in a test — it is now load-bearing twice.

**Do not move the misplaced `if __name__ == "__main__": unittest.main()` block —
that is t1770's, not this task's.** It sits above six classes, so direct execution
runs 33 of the 48 tests and prints a green `OK` over the truncated set. An advisory
note from t1760 (verified sender, base `9cb61927c`) records that t1770 already owns
that fix, and t1770's body explicitly disclaims this task's scope; fixing it here
would be a guaranteed line-level conflict. **Insert the new classes immediately
above that guard**, not at the end of the file — there they are collected by both
entry points whichever task lands first — with a one-line comment naming t1770 so
nobody "tidies" them to the bottom.

### 5. `tests/test_check_link_relevance_history.py`

Python, so it runs under `tests/run_all_python_tests.sh` with everything else.
Builds **deterministic throwaway git repos** in a temporary directory (every git
call with `cwd=`, never `chdir`, never touching this repository's `.git`) and
drives the harness via `--repo`:

- **the legacy-tree case**: a commit whose content lacks every page the
  `CORPUS_CONTROLS` key on, containing a known miss, **still contributes that
  record** to the aggregation, and the run reports the corpus controls as not
  applicable rather than failed. This is the case the CLI-based design lost;
- a two-commit repo (a missing link, then the same link repointed) aggregates the
  record with the right sweep count, and asserts a record was reported at all —
  an empty aggregation reads identically to "no records in history";
- the same `(source, token, url)` under two different scopes in two commits
  yields **two** rows;
- an `ENGINE_CONTROLS` failure (patched) makes the harness exit non-zero;
- the HEAD self-control in all three tree states: clean (runs and passes),
  modified (skips, with a reason), and **an untracked page** (skips, with a
  reason — not passes, and not fails).

### 6. `website/README.md`

"Checking Link *Relevance*": document the label, the page-scope restriction and
its reason, and that the base rate is printed live. Upgrade the "Only
backtick-quoted link text" bullet from an assertion ("matching it would bury the
real signal") to the measured decision, naming the harness as the way to re-open
it. Name the residual population for what it is — the **grouped-page** family
(`ait gate pass` → `/commands/gates/`, `ait ls` → `/commands/task-management/`),
which is where t1707's two defects came from: *labelled = the URL itself names the
subject; residual = only the body can vouch, so read it.* Add a short
"Historical replay" paragraph pointing at the harness and at the replay contract
in the module docstring — point, do not restate.

`CLAUDE.md` and `aidocs/` need no change: the harness is not a routine command,
and `.github/workflows/hugo.yml` calls only `check_links.py`.

### 7. Coordination (post-approval, before any code)

Plan mode is read-only, so both of these run as the first actions after approval:

- record the read receipt for t1760's note, which the user acknowledged during
  planning: `./.aitask-scripts/aitask_note.sh read 1768 --by t1768 --ids
  2026-09-09T16:35:40Z.a9952d5c495e1a5e739c8277 --mode explicit`;
- send **t1770** a note (via the `/aitask-note` skill) stating the shared
  historical-replay contract: replay runs through `scan()` + `ENGINE_CONTROLS`,
  never through `main()` / `--report`, so t1770's fail-closed change to
  `--report` is safe for the harness — and naming the two things t1770 must not
  do to keep it that way: put a control call inside `scan()`, or reshuffle
  entries between `ENGINE_CONTROLS` and `CORPUS_CONTROLS`. Advisory, as all notes
  are; it closes the link t1760 opened from the other direction.

### Post-phase (risk mitigations)

1. `[harness_smoke_test]` Step 5 must exercise the harness end-to-end over the
   throwaway repos, including the **legacy tree lacking the modern control pages**
   — the one case whose loss would silently shrink the evidence base. Asserting
   only that the harness exits 0 does not count.
2. `[discriminator_mutation_check]` For each classifier discriminator — the
   `ait`/`aitask` prefix stripping, dot-anchored `TOKEN_EXTENSIONS` stripping,
   `SECTION_SEGMENTS`, whole-segment (not sub-word) matching, and the page-scope
   restriction — remove it locally and confirm the test that names it goes
   **red**. Do the same for the engine/corpus partition. Any discriminator whose
   removal leaves the suite green is pinned by nothing; fix the test before
   proceeding. Record the result in the task's completion notes.

## Implementation progress (t1768)

**Status: all steps implemented and verified; awaiting Step 8 review.**

- [x] Pre-phase `freeze_history_baseline` — harness built and run before the
  classifier existed; frozen table above (tip `97f238c3c`, 358 sweeps).
- [x] 1c engine/corpus split — done first, since the harness needs it.
- [x] Step 2 harness — `website/check_link_relevance_history.py`.
- [x] 1a/1b/1d classifier, probe control, output, docstring.
- [x] Step 3 `check_links.py` docstring (Q1).
- [x] Step 4 tests — new classes placed above the stranded `unittest.main()`
  guard (t1770 owns moving it); `CoverageBoundaryTests` docstring records Q2.
- [x] Step 5 `tests/test_check_link_relevance_history.py`.
- [x] Step 6 README.
- [x] Step 7 coordination — t1760 note receipt recorded; note sent to t1770
  (`2026-09-10T11:40:42Z.4e6897dc1446deb87b0fc370`, `LIVE_NONE:unlocked`).

**Results.**

- Live CLI: 4 records, 2 unlabelled first, then `aitask_lock.sh` and
  `/aitask-pick` tagged `[subject-of-page]`; 6 controls True; exit 0.
- Replay with the classifier live reproduces the frozen column exactly: 11
  records, 2 labelled, both t1707 records unlabelled; HEAD control PASSED
  (website/content clean — t1760 committed the earlier `setup-install.md` edit).
- `pytest` on both files: 81 passed. Direct execution: 55 (was 33) — the new
  classes are collected under both entry points.
- Full suite: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
- `check_links.py --build`: `SWEEP: PASSED`.

**Post-phase `discriminator_mutation_check`** — run on isolated copies of the
modules and tests, never the shared worktree; each mutant's replacement asserted
to land exactly once; unmutated copy green before and after.

| mutant | result | killed by |
|---|---|---|
| prefix stripping removed | red | `test_a_final_command_word_is_never_an_extension` (+15) |
| extension stripping removed | red | `test_extension_is_stripped_before_slugging` (+5) |
| bare-word extension stripping | red | `test_a_final_command_word_is_never_an_extension` |
| `SECTION_SEGMENTS` removed | red | `test_section_directories_are_not_subjects` |
| sub-word matching | red | `test_a_segment_sub_word_does_not_match` |
| page-scope restriction removed | red | `test_anchored_miss_is_never_labelled` |
| probe renamed out of `ENGINE_CONTROL_NAMES` | red | `test_every_engine_name_is_a_real_control` (+2) |
| residual-first ordering removed | red | `test_unlabelled_records_print_first_and_the_base_rate_is_shown` |
| harness HEAD guard uses `git diff` | red | `test_head_control_skips_on_an_untracked_page` (+1) |
| harness drops `scope` from the key | red | `test_scope_is_part_of_the_record_identity` (+3) |
| ~~harness makes archive failure fatal~~ | ~~red~~ | **Retracted** — this row recorded the *defect* being pinned, not a discriminator checked. See Change Request 1. |
| probe positive-only (both negative clauses removed) | red | `test_probe_fails_if_everything_is_labelled` |

**Equivalent mutants, recorded rather than hidden:** removing *either one* of the
probe's two negative-direction clauses (`labels == {…}` or
`counters["subject_of_page"] == 1`) survives, because each alone rejects
"label everything". They are redundant guards over one direction, not an
unguarded one — the mutant removing both is killed.

**Deviations from the plan.**

- `CORPUS_CONTROLS` is derived as the complement of `ENGINE_CONTROL_NAMES`
  instead of a second hand-kept list (see the frozen-baseline note). The planned
  partition test is kept and joined by a test that every engine name is a real
  control — the hazard the derivation leaves open.
- Base rate is **299 of 329 page-scoped token links (~91%)**, not the ~77%
  planning estimate, which counted anchored links too. The docs say "most" and
  the CLI prints the live figure, so nothing quotes the stale number.
- **Pre-existing error corrected:** README and the module docstring both said
  "roughly seven internal links in ten" carry a backticked token. Measured: 388 of
  1034 (37%). Both now point at the run's `links checked` line instead of a ratio.
- The harness is Python and not wired to CI, as planned; the two probe clauses
  are kept (see equivalent mutants above).

## Post-Review Changes

### Change Request 1 (2026-09-10 15:28)
- **Requested by user:** `_extract` treated every non-zero `git archive` as "this
  commit has no `website/content`", so a real archive failure on a commit whose
  directory exists was counted as a skip and the run still exited 0 — silently
  truncating the aggregation the frozen baseline rests on. Distinguish absence
  from failure, and prove a failure fails the run.
- **Changes made:** absence is now decided by `git ls-tree <rev> -- website/content`
  *before* archiving: non-zero → `ReplayError`; empty → skip; present → the
  archive and extraction must succeed, else `ReplayError`. `main()` reports
  `REPLAY FAILED` and exits 1; `head_control` reports `failed` instead of
  crashing. Two tests use a deleted loose object — what a partial or corrupt clone
  produces — each asserting the fixture's shape first (directory still listed,
  `git archive` genuinely failing).
- **Correction to the progress notes above:** the mutation row "harness makes
  archive failure fatal | red" recorded the *old* defect being pinned, not a
  discriminator being checked: `test_a_commit_without_website_content_is_skipped_not_fatal`
  killed that mutant because it enforced the conflation. That test stays — genuine
  absence must still skip — but it is no longer the only thing constraining the
  branch; see the re-run below.
- **Files affected:** `website/check_link_relevance_history.py`,
  `tests/test_check_link_relevance_history.py`.
- **Verification:**
  - both relevance test files: **83 passed** (81 + the two new tests);
  - mutants on isolated copies, each killed by the test named for it, with an
    unmutated control green before and after:

    | mutant | result | killed by |
    |---|---|---|
    | archive failure treated as absence (the original defect) | red | `test_an_archive_failure_fails_the_run_instead_of_counting_a_skip` |
    | `ls-tree` failure treated as absence | red | `test_an_unreadable_tree_is_an_error_not_an_absence` |
    | genuine absence made fatal | red | `test_a_commit_without_website_content_is_skipped_not_fatal` |

  - replay over the real history is unchanged: 358 swept, 0 skipped, 11
    distinct, exit 0, HEAD control PASSED — no real commit tripped the new
    failure path, and no record was lost.

## Verification

```bash
cd website
python3 check_link_relevance.py          # 4 records: 2 residual first, then
                                         # 2 [subject-of-page]; base rate printed;
                                         # 6 controls all True; exit 0
python3 check_link_relevance_history.py | tail -25
                                         # 11 (source,token,url,scope) rows, stamped;
                                         # both `ait artifact` rows unlabelled;
                                         # ait codebrowser / ait ide / pickweb present;
                                         # corpus controls "not applicable";
                                         # website/content is dirty today, so the HEAD
                                         # self-control must SKIP and say so
cd ..
python3 -m pytest tests/test_check_link_relevance.py tests/test_check_link_relevance_history.py -q
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
```

Acceptance:

- the replay reproduces **all 11** records, including the three found only in
  trees that fail today's corpus controls — and reproduces them identically
  whether or not t1770 has landed, since it never calls the CLI;
- both t1707 records remain **unlabelled** — the refinement never explains away
  the class the detector was commissioned for;
- `KnownClassControlTests` passes untouched;
- the harness's HEAD self-control passes on a clean `website/content`, and
  visibly **skips with a reason** on a modified or untracked one — verify both
  directions, since a control that silently passes when it could not run is worse
  than none;
- `check_links.py` behaviour is unchanged (docstring only) and still gates:
  `python3 website/check_links.py --build`;
- no file under `website/content/` changes, so the "run `check_links.py` after
  editing content" rule is not triggered (README is not content).

Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Risk

Reassessed against the augmented plan (both mitigations inlined, whole-segment
rule adopted, replay moved onto `scan()` + an engine/corpus control split).

### Code-health risk: low
- The classifier is still a heuristic surface (`SECTION_SEGMENTS`,
  `TOKEN_EXTENSIONS`, prefix stripping) that a later reader may widen ad hoc ·
  severity: low · → mitigation: inline post-phase discriminator_mutation_check
- The harness runs in no CI path, so it can bit-rot silently and be useless
  exactly when the next precision question needs it · severity: medium ·
  → mitigation: inline post-phase harness_smoke_test
- The HEAD self-control can only run on a clean `website/content`, which is not
  the normal state of a working repo — so day to day it will usually skip, and the
  replay pipeline's correctness rests on step 5's tests rather than on the
  control · severity: low · → mitigation: inline post-phase harness_smoke_test
- **t1770 edits the same two files** (`main()` and the control wiring in
  `website/check_link_relevance.py`; `tests/test_check_link_relevance.py`) and is
  `Ready` but unclaimed, so both may be in flight at once and whichever lands
  second rebases. The replay is order-independent by construction — it never
  touches `main()` or `--report` — and step 7's note tells t1770 the two
  invariants that keep it so. The residual is an ordinary textual conflict on
  `CONTROLS` and `main()` · severity: medium · → mitigation: none needed (design
  is order-independent; coordination note in step 7)
- Blast radius is otherwise small and non-gating: two scripts, two test files, one
  README section; `check_links.py` gains only a docstring note and everything
  under `website/content/` is untouched · severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- The swept range produces only **11 distinct records**. The rule is validated
  against a genuinely independent ground truth — the six the corpus resolved on
  its own — but eleven is a small sample: "generalizes" here means "never
  explained away a record the corpus later fixed", not a measured precision rate ·
  severity: medium · → mitigation: inline pre-phase freeze_history_baseline
- The label is true of ~77% of all resolved token links, so it discriminates only
  conditional on already being a miss. Mitigated by printing the base rate live
  rather than documenting it, but a reader who ignores that line will over-read
  the label · severity: medium · → mitigation: inline pre-phase freeze_history_baseline
- The task asks whether to fold into `check_links.py`; this plan answers *no* and
  delivers a different artifact instead. If the intent behind Q1 was "find a way
  to make it fold", the plan meets the letter and not the spirit — the
  ExitPlanMode approval is the checkpoint for that · severity: low ·
  → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: freeze_history_baseline | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — small record sample / rule tuned to its own output | desc: Build and run the history harness first and freeze its SHA-stamped 11-record (source,token,url,scope) aggregation plus expected classifications into the plan before writing the classifier
- timing: post-phase | name: harness_smoke_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — harness in no CI path can bit-rot silently | desc: Python test driving the harness over throwaway repos, including a legacy tree lacking the modern control pages, asserting its known record is still aggregated
- timing: post-phase | name: discriminator_mutation_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — hand-tuned constant set pinned only by possibly-vacuous tests | desc: Remove each classifier discriminator and the engine/corpus partition in turn and confirm the test naming it goes red

## Final Implementation Notes
- **Actual work done:** Both deferred questions answered with measurements, and
  recorded where the next contributor would look: Q1 (fold into `check_links.py`)
  = no, recorded in both scripts' docstrings and the README; Q2 (widen past
  backtick-quoted text) = no, recorded in the module docstring, the README and
  `CoverageBoundaryTests`. Added the `subject-of-page` label (whole-segment URL
  match, page-scoped only, labelled never suppressed, live base rate), a new
  engine probe, an ENGINE/CORPUS control split, and a history replay harness
  (`website/check_link_relevance_history.py`) with its own tests.
- **Deviations from plan:** `CORPUS_CONTROLS` derived as the complement of
  `ENGINE_CONTROL_NAMES` rather than a second list; base rate measured at ~91%
  (299/329 page-scoped), not the ~77% planning estimate; the harness is Python
  and replays through `scan()`, per the pre-approval revision. See the progress
  notes and Change Request 1.
- **Issues encountered:** (1) The first harness `_extract` conflated "no
  website/content" with "git archive failed", and my own mutation check pinned
  that conflation as a success — caught in review, fixed with an `ls-tree`
  presence probe and `ReplayError`, and the stale mutation row retracted. (2)
  `main` advanced repeatedly mid-session (content-commit count 352 → 358), which
  is why every count in the plan and docstring is stamped with its tip SHA.
  (3) Several commands initially ran from the wrong directory after the shell's
  cwd moved; all verification was re-run by absolute path.
- **Key decisions:** label, never suppress (suppression would take today's report
  to zero — the optics hazard t1759 named); restrict the label to page-scoped
  misses; derive CORPUS so a new control fails safe for replay; replay through
  `scan()` so the evidence does not depend on whether t1770 lands first; leave
  the stranded `unittest.main()` guard to t1770 and place new tests above it.
- **Upstream defects identified:**
  - `website/check_link_relevance.py:642-643` — `--report` returns before
    `evaluate_controls()` (`:671`), so report mode never evaluates or prints a
    self-control and exits 0 even when one would fail. **Already owned by t1770**
    (verified against the tree; t1768 sent it a coordination note).
  - `tests/test_check_link_relevance.py:865` — `if __name__ == "__main__":
    unittest.main()` sits above later test classes, so direct execution silently
    runs a subset (55 of the module's 70 tests).
    **Already owned by t1770.**
  - `website/README.md` / `website/check_link_relevance.py` docstring — both
    claimed "roughly seven internal links in ten" carry a backticked token;
    measured 388 of 1034 (37%). **Fixed in this task** (both now point at the
    run's `links checked` line), since the rewritten bullets were in scope.

