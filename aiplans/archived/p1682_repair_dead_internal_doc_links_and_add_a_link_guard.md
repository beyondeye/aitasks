---
Task: t1682_repair_dead_internal_doc_links_and_add_a_link_guard.md
Branch: main
Base branch: main
Output branch: main
---

# t1682 — Repair dead internal doc links and add a link guard

## Context

t1603_5 built a link sweep as an inline risk mitigation for the five pages it
edited. Run site-wide, that sweep found a pre-existing defect class it did not
own: **hand-written relative markdown paths that resolve one directory level
wrong**, plus one dead `#fragment`. They are live on the published site.

`hugo build` cannot catch any of it. It fails a broken `{{< relref >}}` (the
page must exist) — `refLinksErrorLevel` is unset, so Hugo's default `ERROR`
applies — but a hand-written relative path is just text, and a `#fragment`
pointing at a nonexistent heading builds green. Nothing in the repo builds the
site or resolves links outside `.github/workflows/hugo.yml`, which only runs
*after a Release*. The 437 relrefs under `website/content/` are unverified
until then, and relative paths are never verified at all.

The sweep that found this was never checked in. Its only surviving copy is a
session scratchpad file that will be reaped.

**Outcome:** every broken internal link repaired as `{{< relref >}}`, and the
sweep promoted to a checked-in, site-wide checker wired into the release build
so the class cannot reach the published site again.

### Ground truth (measured, not assumed)

A read-only replay of the sweep against the built site, with same-site scope
resolved by **origin** (see hazard 4):

```
216 html files
same-site hrefs : 26942 relative + 1662 absolute = 28604
skipped         : 1523 (external origin / non-web scheme / empty)
broken          : 28   (27 missing-page, 1 missing-anchor)
```

Traffic counts drift with the build (`public/` was rebuilt under me three
times during planning, with two different base URLs). **The 28-record broken
set did not** — it reproduced identically across all three builds, minified and
not, and with and without absolute same-site links in scope. That set, not the
counts, is what Appendix A pins.

The task body's page list is **incomplete** — the plan uses the measured set:

| | task body says | measured |
|---|---|---|
| pages | 10 | **11** — `installation/macos.md` is missing from the body |
| `installation/linux.md` | 2 (L229, L230) | **3** — L132 also |
| `tuis/monitor/how-to.md` | 2 (L75, L276) | **4** — L18, L37 also |

### Four hazards found while planning

These reshape the checker's design; each was observed, not inferred.

1. **`website/public/` is shared, gitignored, and concurrently rewritten.**
   Mid-planning it changed from a `--minify` build to a non-minified one under
   another session — the original sweep's unquoted-href control flipped from
   `True` to `False` on an unchanged repo. A checker that trusts whatever is in
   `public/` is not reproducible. → the checker builds its own site into a
   private destination.
2. **The release build uses a base URL this repo has never built with locally.**
   CI builds `--baseURL "${{ steps.pages.outputs.base_url }}/"`. If Pages
   resolves to a project path (`https://beyondeye.github.io/aitasks/`) rather
   than the `CNAME` custom domain, Hugo renders every site-root href as
   `/aitasks/docs/…`. **The large majority of same-site hrefs (~24.6k of 28.6k)
   are root-relative**, so a naive `lstrip('/')` → `public/…` mapping would
   false-fail almost the entire site — and *only at release time*.
   (`serve.sh`'s own comment still says `http://localhost:1313/aitasks/`, so
   this prefix has been in play here before.) → the checker takes the base URL
   explicitly and strips its path.
3. **A count is not a set.** `broken: 28` can be reached by dropping one real
   defect and adding one false positive. → the checker emits normalized records
   and compares them against a pinned inventory.
4. **"Same-site" is an origin question, not a "has a netloc" question.** The
   original sweep skipped every href carrying a scheme or netloc — which drops
   **1662 absolute same-site links on 208 of the 216 pages**, e.g.
   `https://www.aitasks.io/depth/advanced/` on `blog/index.html`. Docsy emits
   them for taxonomy and blog navigation, and a hand-written absolute link to a
   missing page or dead fragment would never be checked, while the sweep still
   printed a confident `broken : 0`. → same-site is decided by comparing the
   href's netloc against the **effective base URL's** netloc; only genuinely
   foreign origins and non-web schemes are skipped. (Bringing all 1662 into
   scope changed the broken set by **zero** records — they all resolve today —
   which is why Appendix A is unaffected.)

## Decisions taken (user-confirmed)

- **Guard placement:** checked-in `website/check_links.py` + one step in the
  existing release workflow. Rejected: a Python-suite test shelling out to
  `hugo build`; a new PR/push CI job; wiring `verify_build`.
- **Repair scope:** exactly the 28 broken links. Relative links that resolve
  correctly today are left alone — the checker makes them self-policing.
- **Mitigations:** `prove_checker_discriminates` and
  `full_site_sweep_with_controls` inline; the authorship-time-guard follow-up
  dropped.

## Implementation

### Pre-phase (risk mitigations)

**1. [prove_checker_discriminates]** Write `website/check_links.py` **first**,
before touching a single doc page, and run it against the *unrepaired* site:

```bash
cd website && python3 check_links.py --build --expect ../aidocs/…/  # see below
```

Requirements — all three, not just the count:

- exit **1**;
- `broken : 28`;
- **`--expect` reports set equality** against the 28-record inventory in
  [Appendix A](#appendix-a--expected-pre-repair-broken-set) — zero *missing*
  and zero *unexpected* records. Records are `<rendered page>|<raw href>|<reason>`,
  sorted, compared as a **multiset** so both identity and multiplicity are pinned.

A checker landed alongside its own repairs can only ever be observed passing;
this is the only point at which its non-zero verdict is demonstrable on real
input, and the set comparison is what stops a coincidental count from passing.
The expected-set file is a **temporary planning artifact** (write it to the
scratchpad from Appendix A) — it is not checked in, because after the repair
the expected set is empty and a checked-in copy would immediately be a lie.
Record the run's output in the plan's post-phase results.

### 2. Write `website/check_links.py`

Promote the scratchpad sweep from
`…/39c39373-…/scratchpad/sweep_links.py`, changing the page set from a
hard-coded five-entry `PAGES` list to a site-wide walk, and adding the four
hazard fixes above. Stdlib only (`html.parser`, `pathlib`, `urllib.parse`,
`argparse`, `subprocess`, `tempfile`). No new dependency anywhere.

```
usage: check_links.py [--build] [--public DIR] [--base-url URL]
                      [--expect FILE] [--report] [-v]
```

| flag | behaviour |
|---|---|
| `--build` | run `hugo --gc --minify --destination <dir>` (adding `--baseURL <url>` when `--base-url` is given) in the script's own directory, then sweep `<dir>`. `<dir>` is `--public` when given, else a `tempfile.TemporaryDirectory()` that is cleaned up. **Never writes to `website/public/`** unless explicitly asked — hazard 1. |
| `--public DIR` | sweep an already-built site. Defaults to `Path(__file__).resolve().parent / "public"`, so cwd is irrelevant. |
| `--base-url URL` | the base URL the site was **built with**. `base_path = urlsplit(URL).path`. Defaults to auto-detect (below). |
| `--expect FILE` | compare the normalized broken-record multiset against `FILE`; print `MISSING:` / `UNEXPECTED:` lines and exit 1 on any difference. |
| `--report` | print only the normalized records (for regenerating an expectation file). |
| `-v` | also print the **derived `base_path` and its source** (`--base-url` / `index.xml channel link` / `fallback`), so auto-detect is verifiable directly rather than only through its consequences. |

Exit **1** on any broken link, any failed control, or any `--expect`
divergence; **0** otherwise.

**Base-path handling (hazard 2).** `--base-url` is authoritative; CI passes the
same value the build step used, so there is no way for the two to drift.

Resolution order, then one normalization applied to whichever source won:

1. `--base-url URL` → `urlsplit(URL).path`.
2. Auto-detect from the built home RSS feed, `public/index.xml`
   (`[outputs] home = ["HTML","RSS"]` guarantees it exists): take the
   **`<channel><link>`**, which is the site root verbatim.
3. Fallback `/`.

**Use the channel link, *not* the `<atom:link rel="self">` href.** Measured on
this site: `channel/<link>` is `https://www.aitasks.io/` → path `/`, while the
atom self href is `https://www.aitasks.io/index.xml` → path `/index.xml`.
Deriving from the self-link would set `base_path=/index.xml`, and then every
ordinary `/docs/…` link would be classified `outside-base` — a total false-fail
on the *default* invocation. A project-path deployment fails the same way
(`/aitasks/index.xml` instead of `/aitasks/`). If the atom self-link is ever
used as a secondary source, its terminal `index.xml` segment MUST be stripped
first.

**Normalize**: strip any trailing `index.xml`, then ensure exactly one trailing
`/`, so `base_path` is `/` or `/aitasks/` and never `/index.xml` or `/aitasks`.

A root-relative href has `base_path` stripped before mapping to the output dir;
one that does **not** start with `base_path` is reported with reason
`outside-base`. The base-path control below is the tripwire for exactly this
class of mistake — a `/index.xml` base path would have made it fail on the
first run rather than shipping.

**Carried-over mechanics**, each with the reason kept as a code comment:

- **Walk the generated HTML; never map source filenames to output paths.**
  `_index.md` builds to `<section>/index.html`, and sources carry site-root,
  page-relative (`reference/#…`) and `../../` forms whose resolution depends on
  Hugo's URL layout, not the filename. Hugo has already resolved every href.
- **Extract with a real HTML attribute parser** (`HTMLParser` subclasses
  `Hrefs` / `Ids`), not a regex. `--minify` strips attribute quotes from `href`
  exactly as it does from `id`: the minified `docs/tuis/board/how-to/index.html`
  holds only **2** quoted hrefs in the whole page, so a quote-only pattern
  reports a clean sweep of an empty set.
- **One uniform resolution rule.** A bare `#frag` targets the containing file;
  anything else is `urljoin`ed against the containing file's own directory URL,
  then `…/` → `…/index.html` and an extension-less final segment →
  `…/index.html`.
- **Same-site scope is by origin, not by "has a netloc" (hazard 4).** Skip only
  empty / `#` hrefs (Docsy's toggle anchors), non-web schemes (`mailto:`,
  `tel:`, `javascript:`, `data:`, …), and `http(s)` hrefs whose **netloc differs
  from the effective base URL's netloc**. An `http(s)` href whose netloc
  *matches* is a same-site link and goes through the **same** path,
  `base_path`-stripping and fragment rules as a relative one. Netloc match
  ignores scheme, so a hand-written `http://` link to the `https://` site is
  still checked.
- **Assert** target-file existence always; for a fragment-bearing href,
  additionally that the slug is present as an `id` (or `a@name`) in the target.
- **Report** `resolved / broken / skipped` counts, then one normalized record
  per broken link: `<page>|<href>|<reason>` with reason ∈ `missing-page` |
  `missing-anchor` | `outside-base`.

**Controls — the four carried over, plus two for the new base-path and same-origin code.**
Each keeps a comment saying what it proves. All are keyed on **pre-existing**
content this task does not touch.

| control | assertion | why it exists |
|---|---|---|
| positive (extractor) | `href=how-to/#how-to-mark-tasks` on `docs/tuis/board/index.html` is **in the extracted set** | an extractor that silently captures nothing otherwise passes the whole sweep |
| positive (extractor) | …and that href **resolves** | capture without resolution proves only that parsing ran |
| positive (premise) | that href is present **unquoted** as a raw substring of the built page | pins the minification premise the parser exists for |
| negative (resolver) | the known-good pre-existing anchor `#by-trail` resolves on `docs/tuis/board/reference/index.html` | **in t1603_5 this failed on first run** — keyed on the page *carrying* the link rather than the resolved *target*. Catching that is the only reason its "0 broken" verdict meant anything. Keep the in-code comment recording the re-keying. |
| **positive (base path)** — new | ≥1 root-relative href exists; every one starts with the derived `base_path`; and `<base_path>docs/` captured from `docs/index.html` resolves | 93% of all hrefs are root-relative, so silent base-path mishandling is the single largest false-fail surface, and it is reachable **only** under a prefixed release baseURL. A `/index.xml` base path fails here on the first run instead of shipping. |
| **positive (same-origin absolute)** — new | on `blog/index.html`, the href `<base_url>depth/advanced/` is captured, **classified same-site**, and resolves; and the count of same-site *absolute* hrefs is > 0 | 1662 absolute same-site hrefs sit on 208 of 216 pages. A scope rule that skips "anything with a netloc" drops all of them silently and still prints a confident `broken : 0` — the same false-pass shape as the quote-only extractor. Expressed against `<base_url>` so it holds under any `--base-url`. |

**The minification-premise control fails closed with an actionable message.**
It legitimately fires when someone points `--public` at a `hugo server` tree —
observed during planning. On failure print: *"the site under `--public` was not
built with `--minify`; re-run with `--build`, or point at a `--minify` build"*,
and exit 1. Refusing to vouch for the extractor is correct; a silent pass is not.

Document one deliberate policy in the module docstring: a `#fragment` whose
target is a Hugo **alias stub** (`/docs/board/` is one — a `meta refresh`
redirect carrying no ids) is reported broken; link the canonical page instead.
No such link exists today.

### 3. Repair all 28 links

Convert each to `{{< relref >}}` — the house style (437 uses across 91 files)
and the form that *fails the build* when a page is moved or renamed, which is
the regression that produced these. Anchors are appended outside the shortcode,
matching the existing pattern at `execution-profiles.md:41`.

Every target below was verified to exist as both a source file and a built
page. Shortcodes expand inside tables and blockquotes (already relied on in
these same files); none of the 28 sits in a code fence.

| # | File | Lines | Current href | Replacement |
|---|---|---|---|---|
| 1 | `docs/development/review-guide-format.md` | 270 | `../workflows/code-review/` | `{{< relref "/docs/workflows/code-review" >}}` |
| | | 271 | `../skills/aitask-review/` | `{{< relref "/docs/skills/aitask-review" >}}` |
| | | 272 | `../skills/aitask-reviewguide-classify/` | `{{< relref "/docs/skills/aitask-reviewguide-classify" >}}` |
| | | 273 | `../skills/aitask-reviewguide-merge/` | `{{< relref "/docs/skills/aitask-reviewguide-merge" >}}` |
| | | 274 | `../skills/aitask-reviewguide-import/` | `{{< relref "/docs/skills/aitask-reviewguide-import" >}}` |
| 2 | `docs/development/skills/aitask-audit-wrappers.md` | 10, 92 | `../../skills/aitask-add-model/` | `{{< relref "/docs/skills/aitask-add-model" >}}` |
| 3 | `docs/installation/linux.md` | 132, 230 | `windows-wsl/` | `{{< relref "/docs/installation/windows-wsl" >}}` |
| | | 229 | `../commands/setup-install/` | `{{< relref "/docs/commands/setup-install" >}}` |
| 4 | `docs/installation/macos.md` | 112 | `../commands/setup-install/` | `{{< relref "/docs/commands/setup-install" >}}` |
| 5 | `docs/installation/windows-wsl.md` | 52 | `../#authentication-with-your-git-remote` | `{{< relref "/docs/installation/git-remotes" >}}#authentication-with-your-git-remote` |
| 6 | `docs/skills/aitask-pick/execution-profiles.md` | 43 | `../../workflows/manual-verification/#autonomous-verification` | `{{< relref "/docs/workflows/manual-verification" >}}#autonomous-verification` |
| | | 44 | `../../workflows/risk-evaluation/` | `{{< relref "/docs/workflows/risk-evaluation" >}}` |
| | | 51 | `../aitask-pickrem/#remote-specific-profile-fields` | `{{< relref "/docs/skills/aitask-pickrem" >}}#remote-specific-profile-fields` |
| | | 118 | `../aitask-pickrem/` | `{{< relref "/docs/skills/aitask-pickrem" >}}` |
| 7 | `docs/skills/aitask-qa.md` | 25 | `aitask-pick/execution-profiles/` | `{{< relref "/docs/skills/aitask-pick/execution-profiles" >}}` |
| | | 75 | `aitask-pick/build-verification/` | `{{< relref "/docs/skills/aitask-pick/build-verification" >}}` |
| 8 | `docs/tuis/minimonitor/how-to.md` | 345 | `../monitor/how-to/#how-to-switch-tmux-to-the-focused-pane` | `{{< relref "/docs/tuis/monitor/how-to" >}}#how-to-switch-tmux-to-the-focused-pane` |
| 9 | `docs/tuis/monitor/how-to.md` | 18, 276 | `reference/#session-name-fallback-dialog` | `{{< relref "/docs/tuis/monitor/reference" >}}#session-name-fallback-dialog` |
| | | 37, 75 | `reference/#pane-classification` | `{{< relref "/docs/tuis/monitor/reference" >}}#pane-classification` |
| 10 | `docs/tuis/settings/how-to.md` | 61 | `../board/` | `{{< relref "/docs/tuis/board" >}}` |
| 11 | `docs/tuis/settings/reference.md` | 134 | `../../skills/aitask-explore/` | `{{< relref "/docs/skills/aitask-explore" >}}` |
| | | 140, 182, 183 | `../../skills/aitask-qa/` | `{{< relref "/docs/skills/aitask-qa" >}}` |

Paths are relative to `website/content/`. **28 occurrences.** Line numbers are
the pre-edit positions; every edit is same-line, so they do not shift.

None of these files is pinned by an existing content guard —
`test_website_doc_lists.sh` (`commands/codeagent.md`, `skills/_index.md`),
`docs_vocabulary_scan.py` (`development/task-format.md`,
`commands/task-management.md`, `tuis/board/*`, `workflows/issue-tracker.md`),
`test_board_reference_doc_literals.py` (`tuis/board/reference.md`) and
`test_shadow_disposition_surfaces.py` (`workflows/shadow-agent.md`) all target
other pages. In particular `test_website_doc_lists.sh` pins the *relative*
`]($slug/)` form in `skills/_index.md`, which this task does not touch.

### 4. Wire the checker into the release build

`.github/workflows/hugo.yml`, immediately after `Build with Hugo` and before
`Upload artifact`. It reuses that step's output (no second build, ~1s) and is
handed **the same base URL the build was given**, from the same expression —
so the two cannot drift:

```yaml
      - name: Check internal links
        run: python3 check_links.py --base-url "${{ steps.pages.outputs.base_url }}/"
        working-directory: website
```

`ubuntu-latest` ships `python3`; the script is stdlib-only. A dead link now
fails the job and the site does not deploy.

### 5. Make it discoverable

- **`CLAUDE.md`** — in the *Website (Hugo/Docsy)* block, add
  `cd website && python3 check_links.py --build`, noting it builds its own copy
  and does not touch `website/public/`.
- **`website/README.md`** — a short section: what it checks, why `hugo build`
  cannot, how to run it, and that CI runs it after the release build.
- **`aidocs/framework/documentation_conventions.md`** — a short rule (this file
  currently has no link guidance at all): prefer `{{< relref >}}` for internal
  links because a hand-written relative path is invisible to the build; run
  `check_links.py` after editing website pages.

### Post-phase (risk mitigations)

**6. [full_site_sweep_with_controls]** Rebuild and re-run the checker
site-wide. Require `broken : 0`, **6/6 controls True**, and exit **0**. Record
the counts paired with the pre-phase run, so the plan shows the verdict changed
from FAILED to PASSED on the same instrument.

## Verification

1. `cd website && hugo --gc --minify` succeeds — this is what validates the 28
   new relrefs (a typo'd relref is a build error).
2. `python3 website/check_links.py --build` → `broken : 0`, six controls
   `True`, `SWEEP: PASSED`, exit `0`.
3. **Discrimination** is proven by the pre-phase/post-phase pair on the same
   script: 28 broken / exit 1 / expected-set equality **before** the repairs,
   0 broken / exit 0 **after**.
4. **Base-URL parity — reproduces the release-only failure mode locally.**
   Four cases, covering both the explicit flag *and* the auto-detect path at
   both root and project path. Each must report `broken : 0`, exit 0, and show
   the base-path control `True`, except the last:

   | # | command (from `website/`) | expected `base_path` |
   |---|---|---|
   | a | `python3 check_links.py --build --base-url "https://www.aitasks.io/"` | `/` |
   | b | `python3 check_links.py --build --base-url "https://beyondeye.github.io/aitasks/"` | `/aitasks/` |
   | c | `python3 check_links.py --build` (auto-detect, default baseURL) | `/` |
   | d | build once with `hugo --gc --minify --baseURL "https://beyondeye.github.io/aitasks/" -d <tmp>`, then `python3 check_links.py --public <tmp>` (auto-detect, project path) | `/aitasks/` |

   Print the derived `base_path` under `-v` so cases (c) and (d) are checked
   against the value, not merely against a passing exit code — an auto-detect
   bug that yields `/index.xml` must be visible directly, not only through its
   consequences.

   Then one **forced failure**: run with a deliberately wrong base path
   (`--base-url "https://x/nope/"` against a site built for `/`) and confirm it
   fails loudly with `outside-base` records and exit 1 — proving the base-path
   code is load-bearing rather than inert.

5. **Same-origin absolute scope is load-bearing (hazard 4).** All 1662 absolute
   same-site links resolve today, so a passing run proves nothing about whether
   they are actually *in scope*. Force the discrimination in the checker's own
   disposable build directory — never in `website/content/`:
   ```bash
   cd website
   python3 check_links.py --build --public /tmp/…/site   # keep the build
   # inject one broken absolute same-site link into one built page
   # e.g. <a href=https://www.aitasks.io/docs/nope/> appended to blog/index.html
   python3 check_links.py --public /tmp/…/site
   ```
   Must report that injected href as `missing-page` and exit 1. Re-run with the
   injection removed → 0. Also confirm a genuinely **external** broken-looking
   href (`https://example.invalid/nope/`) in the same file is *not* reported —
   the scope rule must discriminate on origin, not merely widen to everything.
   Both directions are required: the pre-fix sweep would have passed the first
   half of this by silently skipping the injected link.
6. **The CI change itself.** `act` is **not installed** on this machine, so the
   workflow cannot be executed locally — the verification is therefore two
   parts, and the plan claims nothing more:
   - **Command fidelity:** run the step's exact `run:` string with its
     `working-directory`, i.e. `cd website && python3 check_links.py
     --base-url "<url>/"`, under both base-URL shapes from step 4.
   - **Structural fidelity:** parse `.github/workflows/hugo.yml` with PyYAML
     (6.0.3 is installed) and assert the new step exists, carries
     `working-directory: website`, has a `run` matching the command executed
     above modulo the `${{ }}` expression, and sits at an index strictly
     between the `Build with Hugo` and `Upload artifact` steps. A parse, not a
     grep — a grep would pass on a step in the wrong job or the wrong order.
7. Spot-check two rendered pages for the *correct* resolved hrefs, not just the
   absence of the old ones — `docs/tuis/settings/how-to/index.html` must now
   carry `/docs/tuis/board/`, and `docs/installation/windows-wsl/index.html`
   `/docs/installation/git-remotes/#authentication-with-your-git-remote`.
8. Existing content guards still pass:
   `bash tests/test_website_doc_lists.sh`,
   `bash tests/test_docs_vocabulary_coverage.sh`,
   `python3 -m pytest tests/test_board_reference_doc_literals.py tests/test_shadow_disposition_surfaces.py`.
9. `python3 -m py_compile website/check_links.py`. No shell added, so no
   `shellcheck` target.

Notes for anyone re-running this by hand: `website/public/` is **gitignored and
concurrently written by other sessions** — always use `--build`, never trust
what is there. And this shell's `grep` is a ugrep wrapper with `--ignore-files`
that silently skips gitignored paths; use `command grep` on the built site.

## Risk

### Code-health risk: medium
- The new CI step gates the **release deploy**: a false positive from the
  checker would block the site from publishing — and the largest false-positive
  surface (base-path handling over 93% of hrefs) is reachable *only* under the
  release base URL. · severity: medium · → mitigation: inline pre-phase
  prove_checker_discriminates, plus the base-URL parity verification (step 4)
  which exercises that path locally before it can ever run in CI
- 28 same-line edits across 11 doc pages, no production code touched; the build
  itself validates every new relref. · severity: low · → none needed

### Goal-achievement risk: medium
- The chosen enforcement fires **only at release time**, so a dead link can
  still land on `main` and sit there until the next release. · severity: medium ·
  → mitigation: none — accepted. A follow-up to narrow the guard to authorship
  time was proposed and deliberately dropped; release-time enforcement is the
  chosen posture, and it does stop the class reaching the published site.
- The task body's page list is incomplete (10 pages / partial line lists vs 11
  pages / 28 measured occurrences), so working from it would leave links broken.
  · severity: medium · → mitigation: inline pre-phase
  prove_checker_discriminates (set equality against Appendix A, not a count)
- `website/public/` is rewritten by concurrent sessions with different Hugo
  flags, so a measurement taken from it is not reproducible. · severity: medium
  · → mitigation: inline pre-phase prove_checker_discriminates (the checker
  builds its own hermetic copy; the premise control fails closed on a
  non-`--minify` tree)

### Planned mitigations
- timing: pre-phase | name: prove_checker_discriminates | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: checker false-positive/false-pass risk; incomplete task-body list; non-reproducible shared build dir | desc: write the checker first and run it against the unrepaired site built hermetically by the checker itself, requiring exit 1, broken=28, and --expect set equality against the Appendix A inventory (multiset of page|href|reason records), before any source edit
- timing: post-phase | name: full_site_sweep_with_controls | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: verifying the repair is complete on the same instrument | desc: rebuild and re-run the checker site-wide, requiring broken=0, 6/6 controls True and exit 0, recorded alongside the pre-phase counts

## Appendix A — expected pre-repair broken set

28 records, `<rendered page>|<raw href>|<reason>`, sorted; compared as a
multiset (note the intentional duplicates). Measured against the built site
during planning; write to a scratchpad file and pass via `--expect`.

```
docs/development/review-guide-format/index.html|../skills/aitask-review/|missing-page
docs/development/review-guide-format/index.html|../skills/aitask-reviewguide-classify/|missing-page
docs/development/review-guide-format/index.html|../skills/aitask-reviewguide-import/|missing-page
docs/development/review-guide-format/index.html|../skills/aitask-reviewguide-merge/|missing-page
docs/development/review-guide-format/index.html|../workflows/code-review/|missing-page
docs/development/skills/aitask-audit-wrappers/index.html|../../skills/aitask-add-model/|missing-page
docs/development/skills/aitask-audit-wrappers/index.html|../../skills/aitask-add-model/|missing-page
docs/installation/linux/index.html|../commands/setup-install/|missing-page
docs/installation/linux/index.html|windows-wsl/|missing-page
docs/installation/linux/index.html|windows-wsl/|missing-page
docs/installation/macos/index.html|../commands/setup-install/|missing-page
docs/installation/windows-wsl/index.html|../#authentication-with-your-git-remote|missing-anchor
docs/skills/aitask-pick/execution-profiles/index.html|../../workflows/manual-verification/#autonomous-verification|missing-page
docs/skills/aitask-pick/execution-profiles/index.html|../../workflows/risk-evaluation/|missing-page
docs/skills/aitask-pick/execution-profiles/index.html|../aitask-pickrem/#remote-specific-profile-fields|missing-page
docs/skills/aitask-pick/execution-profiles/index.html|../aitask-pickrem/|missing-page
docs/skills/aitask-qa/index.html|aitask-pick/build-verification/|missing-page
docs/skills/aitask-qa/index.html|aitask-pick/execution-profiles/|missing-page
docs/tuis/minimonitor/how-to/index.html|../monitor/how-to/#how-to-switch-tmux-to-the-focused-pane|missing-page
docs/tuis/monitor/how-to/index.html|reference/#pane-classification|missing-page
docs/tuis/monitor/how-to/index.html|reference/#pane-classification|missing-page
docs/tuis/monitor/how-to/index.html|reference/#session-name-fallback-dialog|missing-page
docs/tuis/monitor/how-to/index.html|reference/#session-name-fallback-dialog|missing-page
docs/tuis/settings/how-to/index.html|../board/|missing-page
docs/tuis/settings/reference/index.html|../../skills/aitask-explore/|missing-page
docs/tuis/settings/reference/index.html|../../skills/aitask-qa/|missing-page
docs/tuis/settings/reference/index.html|../../skills/aitask-qa/|missing-page
docs/tuis/settings/reference/index.html|../../skills/aitask-qa/|missing-page
```

If the pre-phase run diverges from this set, **stop and investigate** — a
divergence means either the checker is wrong or `website/content/` changed
since planning. Do not adjust the expectation to match the output.

## Step 9 (Post-Implementation)

Standard: commit the doc repairs, the checker and the CI step together;
current-branch mode, so nothing to merge. Archive t1682 and its plan once the
`risk_evaluated` gate is recorded.

## Post-Review Changes

### Change Request 1 (2026-09-02 11:05)

- **Requested by user:** The site-wide sweep surfaced 8 further links that
  resolve only under a base path of `/` (7 in `content/_index.md` as Docsy
  `blocks/feature url=` / `tour-tile href=` parameters and one raw `<a href>`,
  1 in `docs/workflows/releases.md` as `](/blog/)`). The user's decision: those
  links are **correct as written**, so `check_links.py` must carry an exception
  for that link *type* rather than the content being changed — and the exception
  must make the stated base-URL parity case pass instead of failing.

- **Changes made:**
  1. `check_links.py` — a same-site path that does not carry the configured
     base path is re-resolved **at the output root**. If it resolves there it is
     accepted and counted under a new **`base-agnostic`** total; if it does not,
     it is still reported `outside-base`. Excepted links keep their full
     resolution: the target file must exist and any `#fragment` must be present,
     so a dead anchor on an excepted link is still `missing-anchor`.
  2. The count is printed on **every** run and each link is listed under `-v`.
     An exception nobody can see is indistinguishable from a checker that
     stopped looking, which is the exact false-pass shape the other controls
     exist to prevent.
  3. A link is added to the `base-agnostic` list **only after it fully
     resolves** — a first cut counted a dead excepted link both as accepted and
     as broken (9 vs 8).
  4. **Control 5 was re-keyed.** It previously asserted "every root-relative
     href starts with `base_path`", which the accepted class now legitimately
     violates. It is now keyed on a *named* href that carries the base path
     (`/docs/` at root, `/aitasks/docs/` under a project path) captured from
     `docs/index.html`, renamed `base path is the one the site was built with`.
  5. `website/README.md` gained a "The `base-agnostic` count" subsection.

- **Deviation from the plan's Verification step 4 (recorded deliberately):**
  the wrong-base forced failure no longer discriminates by broken count — with
  the exception in place, a bogus base path (`https://x/nope/`) sends every
  root-relative href down the accept path, so `broken` is 0. **The load-bearing
  assertion moved to the control**, which is exactly why control 5 was re-keyed
  rather than dropped. Measured: base path `/nope/` → `broken: 0`,
  `base-agnostic: 25108`, control 5 **False**, exit **1**. The 25108 count is
  itself the loud signal. Verification step 4's forced-failure assertion should
  be read as "control 5 fails and the run exits 1", not "`outside-base` records
  appear".

- **Re-verified after the change (all with the final checker):**
  | case | result |
  |---|---|
  | pre-repair build, `--expect` | `broken: 28`, set equality, 6/6 controls, exit 1 |
  | committed state (isolated build) | `broken: 0`, `base-agnostic: 0`, 6/6, exit 0 |
  | (a) explicit root | `broken: 0`, `base-agnostic: 0`, 6/6, exit 0 |
  | (b) explicit project path | `broken: 0`, `base-agnostic: 8` (all 8 named), 6/6, exit 0 |
  | (c) auto-detect root | base path `/`, `broken: 0`, exit 0 |
  | (d) auto-detect project path | base path `/aitasks/`, `broken: 0`, exit 0 |
  | forced: wrong base `/nope/` | control 5 False, exit 1 |
  | forced: `/docs/nope/` under project path | `outside-base` — the exception is not a blanket pass |
  | forced: `/docs/tuis/#no-such-anchor` | `missing-anchor` — excepted links keep fragment checking |
  | forced: `/aitasks/docs/nope/` | `missing-page` |
  | control: `https://example.invalid/nope/` | not reported — scope still discriminates on origin |

## Final Implementation Notes

- **Actual work done:** `website/check_links.py` (new, stdlib-only, site-wide,
  6 controls) checked in and wired into `.github/workflows/hugo.yml` as a
  `Check internal links` step between `Build with Hugo` and `Upload artifact`,
  sharing the build step's `${{ steps.pages.outputs.base_url }}/` expression so
  the two cannot drift. All 28 broken links across 11 pages converted to
  `{{< relref >}}`. Discoverability added to `CLAUDE.md`, `website/README.md`
  and `aidocs/framework/documentation_conventions.md` (which previously carried
  no link guidance at all).

- **Deviations from plan:**
  1. The task body listed 10 pages; the measured set is **11** —
     `installation/macos.md` was missing from it, `linux.md` had 3 occurrences
     (not 2) and `monitor/how-to.md` had 4 (not 2). The plan was built from the
     measured set, which is why the count still reconciles to 28.
  2. Verification step 1 (`cd website && hugo --gc --minify` writing to
     `website/public/`) was folded into the `--build` runs, which execute the
     identical command into a private destination. `website/public/` is shared
     with concurrent sessions; the relref validation is what step 1 was for and
     it is fully covered. The exact CI command *was* run against `public/` once,
     for command-fidelity (verification step 6).
  3. Verification step 4's wrong-base forced failure changed assertion — see
     Change Request 1. The tripwire moved from the broken count to control 5.

- **Issues encountered:**
  - `website/public/` was rewritten by concurrent sessions **three times**
    during this task, once switching from a `--minify` to a non-minified build,
    which flipped the inherited unquoted-href control from `True` to `False` on
    an unchanged repo. This is why the checker builds into a private
    `tempfile.TemporaryDirectory()` and why the premise control fails closed
    with an actionable message instead of vouching for an unverifiable tree.
  - The shared worktree carried a large amount of unrelated in-flight work from
    other sessions, including a `parallel_admission` row added to
    `execution-profiles.md` — one of the 11 files this task edits. Only this
    task's own hunks were committed: the file was staged as an explicit blob
    (HEAD + this task's 4 edits) via `git hash-object` + `git update-index`,
    leaving the other session's row untouched in the working tree. The
    resulting committed state was then built **in isolation** (a content copy
    with every foreign change reverted, via `hugo --contentDir`) and swept
    clean — 0 broken, 6/6 controls — so the commit's claim does not depend on
    anyone else's uncommitted work.

- **Key decisions:**
  - Base path is taken from `--base-url`, else auto-detected from the built RSS
    feed's **`<channel><link>`**. The `<atom:link rel="self">` href was
    explicitly rejected: it is `<root>/index.xml`, which would yield a base path
    of `/index.xml` and mark every ordinary `/docs/...` link `outside-base` on
    the *default* invocation.
  - Same-site scope is decided by **origin**, not by "has a netloc". The
    original sweep's rule dropped 1662 absolute same-origin links on 208 of the
    216 pages while still printing a confident `broken : 0`.
  - Site-root hrefs that do not carry the base path are an **accepted class**
    (`base-agnostic`), per the user's decision that those 8 links are correct as
    written. They are still fully resolved and are counted and listed, never
    silently dropped.
  - The pre-repair expectation was compared as a **multiset of
    `page|href|reason` records**, not a count: `broken: 28` is reachable by
    dropping one real defect and adding one false positive.

- **Upstream defects identified:** None. (The 8 base-path-sensitive site-root
  links found under a project-path base URL were adjudicated by the user as
  correct as written and are handled by the checker's `base-agnostic` class —
  they are a deliberate authoring convention here, not a defect.)

### Commit split caused by a concurrent session (recorded, not a deviation in scope)

Between this task's Step-8 review and its commit, a concurrent session committed
`2384e4a64 feature: Add the advisory parallel-admission preflight to
task-workflow (t1569_4)`, which **swept this task's four repairs to
`website/content/docs/skills/aitask-pick/execution-profiles.md` into its own
commit** along with its `parallel_admission` row.

Consequence: of the 28 repairs, **24 are in `1a42aa71b` (t1682) and 4 already
landed in `2384e4a64` (t1569_4)**. The staged-blob approach prepared before that
commit would, once HEAD moved, have *deleted* the other session's row — it was
discarded after `git diff --cached --stat` showed a single deletion instead of
the expected 4 insertions / 4 deletions. That `--stat` check is the only reason
this was caught before committing.

Both site states were swept clean, so the split changes nothing about the
result: 0 broken with the concurrent work present (the `public/` CI-fidelity
run) and 0 broken with every foreign change reverted (the isolated
`--contentDir` build).
