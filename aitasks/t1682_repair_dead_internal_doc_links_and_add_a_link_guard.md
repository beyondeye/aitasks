---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [docs, web_site]
gates: [risk_evaluated]
anchor: 1595
followup_kind: upstream_defect
created_at: 2026-09-02 09:44
updated_at: 2026-09-02 09:44
---

## Origin

Spawned from t1603_5 during Step 8b review. That task built a link sweep as an
inline risk mitigation for its own five edited pages; run site-wide, the same
sweep found the defect below.

## Upstream defect

**28 broken internal links (21 distinct) across 10 pages**, all one class:
hand-written relative markdown paths that resolve one directory level wrong, plus
one dead `#fragment`. They are live on the published site.

- `website/content/docs/development/review-guide-format.md:270-274 — 5 dead relative links (../workflows/, ../skills/)`
- `website/content/docs/skills/aitask-pick/execution-profiles.md:43,44,51,118 — 3 dead relative links (../../workflows/, ../aitask-pickrem/)`
- `website/content/docs/tuis/settings/reference.md:182,183 — 2 dead relative links (../../skills/)`
- `website/content/docs/tuis/monitor/how-to.md:75,276 — 2 dead relative links (reference/#... resolves under how-to/)`
- `website/content/docs/skills/aitask-qa.md:25,75 — 2 dead relative links (aitask-pick/... resolves under aitask-qa/)`
- `website/content/docs/installation/linux.md:229,230 — 2 dead relative links (windows-wsl/, ../commands/setup-install/)`
- `website/content/docs/development/skills/aitask-audit-wrappers.md:92 — 1 dead relative link (../../skills/aitask-add-model/)`
- `website/content/docs/installation/windows-wsl.md:52 — 1 dead anchor (../#authentication-with-your-git-remote)`
- `website/content/docs/tuis/minimonitor/how-to.md:345 — 1 dead relative link (../monitor/how-to/#...)`
- `website/content/docs/tuis/settings/how-to.md:61 — 1 dead relative link (../board/)`

## Diagnostic context

**`hugo build` cannot catch any of this.** It fails a broken `{{< relref >}}`
because the page must exist, but a hand-written relative path is just text, and a
`#fragment` pointing at a heading that does not exist builds green. So the entire
class is invisible to CI and to local builds. t1603_5's three repairs
(`reference/#by-trail` twice and `../../workflows/work-report/` in
`tuis/board/how-to.md`) were found only because that task happened to build a
sweep; every other page is unswept.

Two mechanics any checker must get right, both learned in t1603_5:

1. **Resolve against the generated HTML, not source filenames.** Deriving
   `public/<section>/<page>/index.html` from a `.md` path is wrong in both
   directions: `_index.md` builds to `<section>/index.html`, and sources carry
   site-root (`/docs/...`), page-relative (`reference/#...`) and `../../` forms
   whose resolution depends on Hugo's URL layout. Hugo has already resolved every
   href in the output — read those and resolve each relative to its own rendered
   file.
2. **`--minify` writes `href` unquoted, exactly like `id`.** The built
   `tuis/board/how-to` page carries `href=reference/#by-trail` and holds only two
   quoted hrefs in total, so a quote-only regex extracts almost nothing and
   reports a clean sweep of an empty set — a false pass. Use a real HTML attribute
   parser.

## Suggested fix

Two parts:

- **Repair** all 28 links. Prefer `{{< relref >}}` over a corrected relative path:
  a relref fails the build when a page is moved or renamed, which is exactly the
  regression that produced these. Anchors still need the sweep, since relref does
  not validate fragments.
- **Add a durable guard** so the class cannot recur. t1603_5's sweep is proven and
  is the starting point — it walks the built HTML with `html.parser`, resolves
  every same-site href against its rendering file, checks the unquoted `id=` form
  for fragments and file existence otherwise, and reports a resolved/broken count.
  Promote it from that task's scratchpad to a checked-in checker over the whole
  site.

  Keep both of its controls, and note why each exists — one caught a real bug in
  t1603_5:
  - a **positive control on the extractor** (a named unquoted relative
    fragment-bearing href must be captured *and* resolve), because an extractor
    that silently captures nothing otherwise passes the whole sweep;
  - a **negative control on the resolver** (a known-good pre-existing anchor must
    resolve). In t1603_5 this control failed on first run — it had been keyed on
    the page carrying the link rather than the resolved target — and catching that
    is the only reason its "0 broken" verdict meant anything.

  The checker needs a built site, so decide deliberately where it runs: a Python
  test that shells out to `hugo build` is slow and adds a Hugo dependency to the
  suite, while a `website/`-local script is cheap but only runs when someone
  remembers. Sizing that choice is part of this task.
