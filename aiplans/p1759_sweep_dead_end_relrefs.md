---
Task: t1759_sweep_dead_end_relrefs.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1759 — Sweep dead-end relrefs (mis-targeted internal links)

## Context

t1707 removed two internal links whose target page **exists** but contains none
of the subject the link text named:

- `docs/skills/aitask-trail.md:85` — `` `ait artifact` `` → `/docs/commands/task-management`
- `docs/development/task-format.md:98` — `` `ait artifact` `` → `/docs/workflows/implementation-trails`

Both were found by hand. Nothing established they were the only two — that is
goal-achievement risk 2 of t1707's plan, and this task is its risk-mitigation
follow-up.

**No check in the repo can see this class.** `hugo build` fails a `relref` only
when the target does not *resolve*; `website/check_links.py` resolves hrefs and
anchors against the built HTML, so a link to a real page with a real anchor
passes regardless of what the page *says*. The defect is a semantic mismatch
between link text and target content, and needs a different detector.

Outcome: a source-side relevance detector that reports mis-targeted links for
human triage (a report, not a gate), plus the actual sweep of the live corpus.

## Prototype evidence (already measured on the live corpus)

> **Superseded — read the Final Implementation Notes for the real figures.**
> The prototype's link regex matched **zero** `relref` links, so every row below
> that counts *link text* or *relevance verdicts* covers hand-written paths only:
> the checked set is ~360, not 236, and the hit/miss rows are correspondingly
> partial. The relref-resolution and anchor rows were measured with a separate,
> correct pattern and stand. Kept as the historical record of what the plan was
> approved on.

A throwaway prototype was run against `website/content/` before planning:

| measure | value |
|---|---|
| pages | 199 |
| internal links extracted | 502 |
| links with backtick-quoted text (the checked set) | 236 |
| `relref` links | 477 — of which **19 are page-relative** (`{{< relref "terminal-setup" >}}`) |
| anchors written **inside** the relref string (`"…/settings#shortcuts-s"`) | 27 |
| anchors appended **outside** the shortcode (`>}}#frag`) | 44 |
| links using **both** anchor forms | 0 |
| relref targets resolved by the rule below | **477 / 477, 0 unresolved** |
| anchors resolved to a heading | **76 / 76** (after removing hyphen-collapsing from the slugifier — Hugo keeps `minimal--non-tmux-workflow`) |
| relevance hits / misses (whole-token match) | 231 / 6 |
| relevance hits / misses (stem normalization + anchor scoping) | **235 / 2** |

The 4 misses that stem normalization removed were all false positives of the
same shape — flags and placeholders inside the ticked token
(`ait pr-import --list`, `ait gate pass <task-id> <name>`) whose target page does
document the command. The 2 survivors are triage candidates, not confirmed
defects.

**Correction to an earlier reading of this evidence.** A first pass reported "0
unresolved targets" while handling relref arguments as plain site-root paths.
That number was measured *after* filtering to backticked link text, and all 19
page-relative relrefs and 26 of the 27 inside-string anchors happen to carry
prose link text — so the resolver's two real gaps were never exercised and the
zero was partly vacuous. Both gaps are closed by the resolution rule below, which
now resolves 477/477 with both anchor forms exercised.

**Positive control confirmed:** both t1707 target pages still contain zero
occurrences of `ait artifact`, so reinstating either link reproduces the class
and the detector must report it. This becomes a fixture assertion, not a
corpus statistic.

## Design decisions

**1. Source-side, not build-side — deliberately diverging from `check_links.py`.**
`check_links.py` walks generated HTML on purpose (its module docstring records
why: `_index.md` → `<section>/index.html`, minified attributes, base paths). This
detector cannot: the deliverable is `(source_file, line)` for human triage, which
the built HTML has thrown away. The two are different input domains, not a
duplicated seam, and the new script's docstring must say so explicitly and point
at `check_links.py` as the owner of *existence* checking.

Source-side URL mapping is safe **today** because no content file declares
`slug:` or `url:` (verified: 0 of 199). That is an assumption, so the script
guards it: if any content file declares `slug:`/`url:`, emit a warning that the
filename→URL mapping may be wrong rather than silently mis-resolving.

**2. `relref` resolution follows Hugo's rule, not a URL-path assumption.** A
relref argument is a *page lookup*, not a path — 19 of the 477 in the corpus are
page-relative. Resolution, in order:

1. **Split the argument on `#` first.** Hugo accepts the anchor inside the quoted
   argument (`{{< relref "/docs/tuis/settings#shortcuts-s" >}}`, 27 occurrences).
   An anchor appended after `>}}` (44 occurrences) is ordinary markdown and
   applies too. No link in the corpus uses both; if one ever does, the record is
   **reported as ambiguous rather than resolved under an invented precedence.**
2. **Leading `/`** → site-root; direct URL-map lookup.
3. **Otherwise page-relative**, resolved against the *source page's own
   directory*: try `<dir>/<name>.md`, then `<dir>/<name>/_index.md`. A bare
   `_index` means that directory's own section index.
4. **Site-wide unique-name fallback** — Hugo resolves a name that is unique
   across the site even when it is not directory-relative (`{{< relref
   "getting-started" >}}` from `docs/installation/_index.md` reaches
   `docs/getting-started.md`). The index keys **section pages by their directory
   name**, not by the stem `_index`; without that, `{{< relref "development" >}}`
   from `docs/commands/_index.md` fails.
5. **Ambiguous** (>1 candidate) → reported as its own status, never guessed. This
   guard is load-bearing, not hypothetical: `reference` matches 6 pages and
   `how-to` 7.

Anything not `ok` is counted under `unresolved_target` and is **excluded from the
relevance verdict** — never silently scored as a hit or a miss.

**3. Anchors narrow the scope; they never decide correctness.** `check_links.py`
owns anchor *validity* against built ids. Here an `#anchor` only narrows the
relevance check from the whole page to that heading's section. If the anchor
cannot be matched to a heading, the check **widens to page scope and increments a
reported counter** — the fail-safe direction (fewer false positives), and
visible rather than silent.

**4. Report, never gate.** Exit 0 regardless of misses. No CI wiring. The task
defers the "is any part precise enough for `check_links.py`" decision to after
the report is read.

**5. Scope: backtick-quoted link text only.** ~360 of ~500 links (the `236 of
502` figure written here at planning time was an artefact of the broken prototype
regex — see the Final Implementation Notes). This is the
highest-signal, cheapest case the task names. **What it does not buy:** the
remaining ~140 links with prose link text are unchecked, and links emitted by
shortcodes or templates are invisible to a source-side scanner. Both stated in
the script docstring and in `website/README.md`, so the coverage boundary is
readable without running anything.

## Files

### New: `website/check_link_relevance.py`

Python 3 stdlib only, matching `check_links.py`. Structured for import so tests
drive functions directly rather than only shelling out.

- `build_url_map(content_dir)` → `{url: Path}` using Hugo defaults
  (`_index.md` → `/<dir>/`, `foo.md` → `/foo/`).
- `build_name_index(content_dir)` → `{name: [Path, …]}` for the site-wide relref
  fallback, keying section pages by their **directory** name and leaf pages by
  their stem. The list-valued shape is what makes ambiguity detectable.
- `resolve_relref(source_file, argument)` → `(url, anchor, status)` implementing
  design decision 2, `status ∈ {ok, ambiguous, missing}`.
- `extract_links(content_dir)` → records of
  `(source_file, line, link_text, target_url, anchor, kind, status)`. Relref
  targets go through `resolve_relref`; hand-written relative paths are `urljoin`ed
  against the source page's own URL. Skips external and bare-`#` hrefs.
- `stem(token)` — strips `<placeholders>`/`[...]`/`{...}` and `--flag` /
  `-f` words, collapses whitespace. This is what turns
  `ait gate pass <task-id> <name>` into `ait gate pass`.
- `heading_slug(text)` / `anchor_section(body, anchor)` — Hugo-compatible
  slugification. **Must not collapse repeated hyphens** (proven by
  `minimal--non-tmux-workflow` and `debian--ubuntu--wsl-deb`).
- `check(records, url_map)` → `(hits, misses, counters)` where `counters` carries
  `unresolved_target` and `anchor_not_found` as first-class reported numbers, never
  defaulted to zero on failure.
- Self-controls in the `CTL_*` idiom of `check_links.py` (module constants keyed
  on pre-existing content, never on anything a repair edits), evaluated by
  `evaluate_controls(records, counters, controls=CONTROLS)` and printed on every
  run, one `control : <name>: <True|False>` line each:
  - `extractor captured the control link` — a known backticked relref is in the
    extracted set.
  - `relevance check reports a hit` — a known good link resolves to a hit.
  - `stem normalization strips a flag` — `ait pr-import --list` stems to
    `ait pr-import` and hits.
  - `anchor scoping narrowed the check` — at least one anchored link was checked
    against a section rather than the whole page.
  - `page-relative relref resolved` — a known page-relative relref
    (`{{< relref "terminal-setup" >}}` from `docs/installation/_index.md`)
    resolved to its page. Without this the resolution rule can silently regress
    to path-handling and every relative relref becomes an `unresolved_target`
    that nobody reads.

  **The CLI exits non-zero if _any_ control is `False`**, and names every failed
  control on stderr. Not "all of them" — a run in which the extractor collapsed
  but the stem control still passes is exactly the silently-stopped-looking case
  these controls exist to catch, and it must fail. This is the only condition
  under which the script exits non-zero; misses never do.

  `CONTROLS` is a module-level list of `(name, predicate)` so tests can pass a
  fixture-specific set instead of the live-corpus one.
- Output: one `path:line  \`token\`  ->  target [scope]` record per miss, then a
  summary line with hits, misses, unresolved and anchor-not-found counts.
- Flags: `--content <dir>` (default `content`), `-v` (list hits and the
  base-agnostic-style exception counts), `--report` (records only).

### Modified: `website/README.md`

New subsection under "Checking Internal Links": what the relevance report is,
why `check_links.py` cannot see the class, how to run it, and the explicit
coverage boundary (backticked text only; source-side only; report, not gate).

### Modified: `CLAUDE.md`

One line in the Website block next to the existing `check_links.py` entry. It is
a report, so it is *offered*, not mandated — the existing "Run `check_links.py`
after editing any page" rule stays the only mandatory one.

### New: `tests/test_check_link_relevance.py`

Python unittest, matching the repo's convention (`sys.path.insert` the `website/`
dir, run by `bash tests/run_all_python_tests.sh`). Every assertion runs against a
**synthetic fixture content tree** built in a `tempfile` dir — never against
`website/content/`, whose numbers move with every docs commit.

Fixture pages and the cases they pin:

1. **Positive control — the t1707 class.** A page linking
   `` [`ait artifact`]({{< relref "/docs/commands/task-management" >}}) `` to a
   target page that documents only `ait create`/`ait ls`. Asserted **reported**,
   with the exact source file, line and token. Reproduces the real defect this
   detector exists for.
2. **Negative control — the same link, target fixed.** The identical link text
   pointing at a page that *does* contain `ait artifact`. Asserted **not**
   reported. Without this, case 1 passes for a detector that reports everything.
3. **Stem normalization.** `` `ait pr-import --list` `` → a page containing
   `ait pr-import`. Asserted not reported. And its mutant: the same link to a page
   containing neither → asserted reported. Pins that the normalization narrows
   the claim without blinding the check.
4. **Anchor scoping, both directions.** A link with `#anchor` whose named section
   lacks the token but where a *different* section on the page has it → asserted
   reported (proves scoping actually narrowed). The same link where the named
   section does contain it → asserted not reported.
5. **Hyphen-preserving slug.** A heading rendering as `foo--bar` linked as
   `#foo--bar`. Asserted the anchor resolves and `anchor_not_found` is 0 — the
   regression that the prototype actually hit.
6. **Unresolvable target is counted, not swallowed.** A link to a page that does
   not exist → asserted `counters["unresolved_target"] == 1` and asserted **not**
   silently counted as a hit or a miss.
7. **Hand-written relative path.** `](../other/#frag)` from a nested page →
   asserted it resolves to the same target the equivalent relref would.
8. **Non-backticked prose link text is skipped** — asserted not reported, pinning
   the documented coverage boundary rather than leaving it implicit.
9. **Page-relative relref from a section index.** `{{< relref "terminal-setup" >}}`
   inside `installation/_index.md` → asserted it resolves to
   `installation/terminal-setup.md` **and** that its backticked token is
   relevance-checked (`unresolved_target == 0`). Asserting resolution alone would
   pass for an implementation that resolves and then drops the record.
10. **Page-relative relref from a leaf page.** `{{< relref "known-issues" >}}`
    inside `installation/pypy.md` → same two assertions. Both directions of
    design decision 2 step 3 (`<dir>/<name>.md` and `<dir>/<name>/_index.md`) get
    one fixture each.
11. **Site-wide unique-name fallback.** `{{< relref "getting-started" >}}` from
    `installation/_index.md` where the target lives at `docs/getting-started.md` —
    not directory-relative. Plus a section-name case (`{{< relref "development" >}}`
    reaching `development/_index.md`), which fails outright if the name index keys
    section pages by the stem `_index`.
12. **Ambiguous name is reported, never guessed.** Two `reference.md` pages under
    different sections, and a relref `"reference"` from a third directory that has
    none → asserted `status == "ambiguous"`, counted under `unresolved_target`,
    and asserted **not** scored as either a hit or a miss.
13. **Bare `_index` relref** → resolves to the source page's own section index.
14. **Anchor inside the relref string.** `{{< relref "/docs/x#some-heading" >}}` →
    asserted the anchor is parsed out and the check is section-scoped, identically
    to the appended `>}}#some-heading` form; and asserted the two forms yield the
    same verdict for the same content.
15. **Both anchor forms on one link** → asserted reported as ambiguous rather than
    silently resolved under an invented precedence.
16. **Each control failing individually fails the CLI.** One sub-test per control:
    monkeypatch that control's `CTL_*` constant to an unmatchable value, run the
    CLI, and assert exit status is non-zero **and** that control's name appears in
    the failure output. Five sub-tests, so no single control can be the only one
    load-bearing — and the `all()` vs `any()` inversion cannot pass.

Assertions are on identity (which file/line/token) plus count, never on
"some misses were found".

## Steps

### Pre-phase (risk mitigations)

1. `[known_class_control_first]` Before the detector is written, add fixture
   cases 1 and 2 (the reconstructed t1707 links — broken target **and** the
   fixed-target negative control) to `tests/test_check_link_relevance.py`, and
   confirm the file fails for the right reason (no module yet). This makes the
   detector's ability to catch the class it was commissioned for a precondition
   rather than a claim made afterwards.

### Main steps

1. Write `website/check_link_relevance.py` per the design above — URL map, name
   index, `resolve_relref`, extraction, stem, anchor scoping, counters, `CTL_*`
   self-controls with the any-false exit rule, CLI.
2. Complete `tests/test_check_link_relevance.py` with fixture cases 3–16.
3. Run `bash tests/run_all_python_tests.sh --test-dir tests` narrowed to the new
   module; then the relevant slice of the suite. Read only the last line for the
   verdict (`PYTHON SUITE: PASSED|FAILED`), and use `set -o pipefail` if piping.
4. Document in `website/README.md` and `CLAUDE.md`.

### Post-phase (risk mitigations)

1. `[sweep_and_triage]` Run the finished detector against the live
   `website/content/` and **triage every reported record**, deciding per record:
   genuine mis-target (fix the link), or false positive (leave, and name which
   class it belongs to). Record the dispositions in the plan's Final
   Implementation Notes. The task's goal is a *sweep*, not only a tool — without
   this step the deliverable is half-done. Any link actually fixed here is a
   content change, so `check_links.py --build` runs after it per CLAUDE.md.
2. `[document_coverage_boundary]` State the coverage limits explicitly in both
   the script docstring and `website/README.md`: backticked link text only
   (~360 of ~500 internal links — stated proportionally in the delivered docs,
   since the exact split moves with every docs commit), source-side only
   (shortcode- and template-generated
   links are invisible), report not gate. Folds into main step 4; listed
   separately here because it is what stops the report being mistaken for a
   clean sweep.

## Verification

- `cd website && python3 check_link_relevance.py` exits 0 and prints all five
  controls as `True`. A control printing `False` is a failure of the checker, not
  of the content.
- The live run reports `unresolved_target: 0` and `anchor_not_found: 0` — the
  numbers the corrected resolution rule was verified against (477/477 relrefs,
  76/76 anchors). A non-zero either way means the resolver regressed, and is read
  as a checker fault before any content record is triaged.
- `bash tests/run_all_python_tests.sh --test-dir tests` — new module passes;
  verdict read from the final `PYTHON SUITE:` line.
- **Mutation checks that the fixtures can fail** (each applied, observed, then
  reverted — a suite that stays green under these is not evidence):
  - invert the miss condition in `check()` → fixture cases 1 and 3-mutant must flip
    to failing;
  - change the control exit rule from `any(... is False)` to `all(...)` → the five
    case-16 sub-tests must fail;
  - drop the site-wide name-index fallback → cases 11 and 12 must fail;
  - key the name index by `Path.stem` instead of the directory name for section
    pages → case 11's section-name half must fail.
- `cd website && python3 check_links.py --build` after P2, if any link was
  edited.
- Triage table for every live-corpus record present in the Final Implementation
  Notes.

## Risk

Reassessed once against the augmented plan (three inline mitigations added). The
inline control and the inline sweep materially reduce the two largest
goal-achievement concerns, but the "does the heuristic generalize to unknown
instances" question is not falsifiable by any test — so that dimension stays
`medium` rather than being talked down.

### Code-health risk: low
- A second link-extraction implementation lives beside `check_links.py` and could
  drift from it · severity: low · → mitigation: inline post-phase
  `document_coverage_boundary` — the docstring states the domain split (source
  markdown vs built HTML) and names `check_links.py` as the owner of existence
  and anchor-validity checking, so neither script grows into the other's job.
- Source-side URL mapping assumes Hugo defaults, which no content file overrides
  today · severity: low · → mitigation: inline — the script warns when any
  content file declares `slug:`/`url:` instead of silently mis-resolving (design
  decision 1; no separate phase step).

### Goal-achievement risk: medium
- The heuristic may be tuned to the two known instances and generalize to nothing
  — the exact "only two were found" doubt this task inherits · severity: medium ·
  → mitigation: inline pre-phase `known_class_control_first`
- Building the detector without running the sweep would leave the task's stated
  goal undelivered · severity: medium · → mitigation: inline post-phase
  `sweep_and_triage`
- Coverage is limited to backtick-quoted link text (~360 of ~500 internal links;
  the planning-time `236 of 502` was an artefact of the prototype regex defect);
  prose link text and shortcode-generated links stay invisible · severity: medium
  · → mitigation: inline post-phase `document_coverage_boundary`, and
  t1768. Deliberately **not** widened in this task:
  prose link text has no distinctive token to match on and would invert the
  false-positive rate that makes this report usable.

### Planned mitigations
- timing: pre-phase | name: known_class_control_first | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — heuristic may not generalize past the two known instances | desc: Write the reconstructed t1707 broken-link fixture and its fixed-target negative control before the detector exists, and confirm they fail for the right reason.
- timing: post-phase | name: sweep_and_triage | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — detector built but sweep never run | desc: Run the finished detector on live website/content and triage every reported record as genuine mis-target or named false-positive class, recording dispositions in the Final Implementation Notes.
- timing: post-phase | name: document_coverage_boundary | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — coverage gap mistaken for a clean sweep; code-health — drift against check_links.py | desc: State the coverage limits (backticked text only, source-side only, report not gate) and the domain split against check_links.py in the script docstring and website/README.md.
- timing: after | name: evaluate_check_links_integration | type: enhancement | priority: low | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — coverage limited to backticked link text | desc: Once the triage report has been read, decide whether any part of the relevance heuristic is precise enough to fold into check_links.py as a non-blocking warning, and whether to widen coverage past backtick-quoted link text. | created: t1768

---

## Final Implementation Notes

- **Actual work done:** Built `website/check_link_relevance.py`, a source-side
  detector for internal links whose target page exists but never mentions the
  subject the link text names, plus 38 fixture-based tests, and swept the live
  corpus. Matches the approved plan.
- **Deviations from plan:** None in scope. Two additions the plan did not name,
  both from self-review: `_is_hit` was tightened so a control cannot pass when
  its subject disappears, and the `-v` listing was relabelled from `hit?` to
  `checked` because it was overstating by exactly the misses.
- **Issues encountered:** The plan's prototype link regex never matched a single
  `relref` link (whitespace-excluding target pattern vs. a shortcode containing
  spaces), so every relevance figure in the plan covered only hand-written paths
  -- about a third of the real link set. The pre-phase control caught it before
  the detector was finished. Details under "Correction to the planning evidence".
- **Key decisions:** (1) source-side rather than build-side, because the
  deliverable is `file:line` for triage; (2) unresolved targets are counted and
  excluded from scoring, never folded into hits or misses; (3) the report never
  gates -- only a failed self-control exits non-zero; (4) the URL-path
  suppression rule that would zero the report was deliberately NOT applied here
  (see below).
- **Upstream defects identified:** None.

### What landed

- **`website/check_link_relevance.py`** (new) — source-side relevance report.
- **`tests/test_check_link_relevance.py`** (new) — 48 tests over synthetic
  fixture content trees.
- **`website/README.md`** — new "Checking Link *Relevance*" section with the
  division-of-labour table against `check_links.py` and the coverage boundary.
- **`CLAUDE.md`** — Website block entry, stating it is a report and not a gate.

### Correction to the planning evidence

The plan's prototype numbers (236 links checked / 235 hits / 2 misses) were
**wrong, and wrong in a way the plan did not anticipate**. The link regex
`\[([^\]\n]+)\]\(([^)\s]+?)…\)` excludes whitespace in the target, and a relref
contains spaces (`{{< relref "x" >}}`) — so it matched **zero** relref links.
Every relevance number in the plan came from hand-written relative paths alone,
i.e. about a third of the real link set.

The pre-phase control caught it: fixture case 1 reconstructed a relref link and
failed with an empty record set. `LINK_RE` now tries a shortcode alternation
first, and carries a comment saying why.

Corrected live figures: **359 links checked, 358 hits, 4 reported, 0 unresolved,
0 anchor-not-found**, all five self-controls `True`. The relref resolution rule
itself was verified separately at 477/477.

### Triage of every reported record (`sweep_and_triage`)

All four are **false positives**. No content change was made; the two known
t1707 instances remain the only confirmed members of the class.

| # | record | verdict | class |
|---|---|---|---|
| 1 | `docs/tuis/monitor/how-to.md:236` `` `ait minimonitor` `` → `minimonitor/how-to/#how-to-mark-an-agent-as-prioritized` | false positive | subject-of-page paraphrase — target is the minimonitor's own how-to page (6 mentions elsewhere); the named section says "it" rather than repeating the command |
| 2 | `docs/workflows/crash-recovery.md:30` `` `aitask_lock.sh` `` → `/docs/commands/lock/` | false positive | implementation-name link text — the page documents `ait lock` (18×) and never names the script; the sentence is deliberately about what the *script* records |
| 3 | `docs/workflows/parallel-development.md:44` `` `/aitask-pick` `` → `/docs/skills/aitask-pick/parallel-admission/` | false positive | sub-page of the named command's own doc section — the URL path carries the relationship the body never restates |
| 4 | `docs/workflows/risk-evaluation.md:38` `` `ait board` `` → `board/reference/#task-metadata-fields` | false positive | subject-of-page paraphrase — the board reference never writes the literal `ait board`, but that section is the correct target |

### A precision refinement, deliberately NOT applied here

All four share a suppressible shape: the **stemmed token appears in the target's
own URL path** (`minimonitor`, `lock`, `aitask-pick`, `board`). Neither t1707
instance does — `ait artifact` → `/docs/commands/task-management/` and
`/docs/workflows/implementation-trails/` — so a "token in target path ⇒ hit" rule
would clear the report to zero while preserving both true positives.

It is **not** implemented in this task on purpose. Tuning the heuristic against
the four records it just produced, to make its own output look clean, is exactly
the "tuned to the known instances" risk this task inherited. The rule needs
evidence from more than one sweep. It is handed to
t1768 `evaluate_check_links_integration` (the spawned `after` mitigation) as concrete,
measured input rather than as a hunch.

### Two defects found by self-review, fixed and pinned

1. **`_is_hit` could pass vacuously.** It asked only "was no miss reported for
   this token?" — trivially true when the control link stops resolving, loses
   its backticks, or is deleted. A control that goes green when its subject
   vanishes is worse than no control. It now requires a **resolved** record from
   that source whose stemmed tokens actually include the token, *then* checks for
   a miss. `ControlVacuityTests` pins all four ways it can now fail (deleted
   link, unresolved target, backticks removed, genuine miss) plus the passing
   case.
2. **The `-v` listing was labelled `hit?`** while printing every checked-and-
   resolved link — overstating by exactly the misses. Relabelled `checked`, with
   the scope shown.

### Three defects found in Step-8 review, all confirmed and fixed

1. **`anchor_section()` excluded the heading line** (`check_link_relevance.py`).
   It collected from the line *after* the matched heading, so a link to
   `#ait-gates-run` landing on `## ait gates run` was reported as a miss for
   naming its subject in the one line the slice threw away. The heading is part
   of the section it names; it is now included. Pinned by
   `AnchorHeadingIsPartOfTheSectionTests`, including that the section is still
   bounded by the next same-level heading (the fix must not widen to the page).
2. **The `anchor scoping narrowed the check` control was not discriminating.**
   It asserted `any(rec.anchor and rec.status == "ok")` — that an anchored link
   was *extracted and resolved*, which stays `True` for an implementation that
   computes the scope and then searches the whole page. It now drives the real
   `check()` path over a probe whose token sits in a different section of the
   same page, so only section-scoped scoring satisfies it, and it pins the scope
   label too.

   The probe is deliberate rather than corpus-keyed. Exactly one live link
   currently narrows a verdict, so keying the control to it would make the
   script exit non-zero for everyone the day somebody legitimately repointed
   that link — a control that fails when the *content* is fixed. The corpus-side
   evidence is kept as a reported counter instead, `scope-narrowed`, which is
   also a useful triage signal: it isolates the "token is on the page, just not
   in that section" false-positive shape.
3. **The module docstring carried the stale `236 of 502` coverage figure** while
   the code reported 359 and the README said ~360 — two incompatible boundaries
   in the delivered docs, in the one place the task required to be readable.
   Both now describe the split proportionally and point at a run's
   `links checked` line, since the exact number moves with every docs commit.
   The plan's own restatements above were corrected too.

### Verification performed

- 48/48 tests pass (`python3 -m unittest tests.test_check_link_relevance`).
- Live run exits 0 with all five controls `True`, `unresolved: 0`,
  `anchor n/f: 0`.
- **Four mutation checks, each confirmed to fail the intended test and then
  reverted** (the module was restored byte-identical, verified by `diff`):
  | mutation | failures | intended test hit? |
  |---|---|---|
  | invert the miss condition in `check()` | 25 | yes |
  | control exit rule `any` → `all` | 5 | `test_each_control_failing_alone_fails_the_cli` (5 subtests) |
  | drop the site-wide name-index fallback | 3 | yes |
  | name index keyed by `Path.stem` | 1 | `test_site_wide_fallback_finds_a_section_by_directory_name` |
  | remove the `_is_hit` vacuity guard | 3 | `ControlVacuityTests` |
  | drop the heading from `anchor_section` | 2 | `AnchorHeadingIsPartOfTheSectionTests` |
  | `scope_narrowed_verdict` never increments | 3 | counter + probe tests |
  | **scoping ignored — always search the whole page** | 6 | incl. `test_probe_passes_against_the_shipped_implementation` — this is the mutant the *old* control failed to catch, and the reason review item 2 was blocking |
- No `website/content/` page was edited, so `check_links.py` needed no re-run on
  account of this task (the plan's conditional post-phase step).
