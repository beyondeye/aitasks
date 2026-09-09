#!/usr/bin/env python3
"""Report internal links whose target page exists but is not *about* what the
link text names.

`hugo build` fails a `{{< relref >}}` only when the target does not resolve, and
`check_links.py` resolves every href and `#fragment` against the built HTML. A
link to a real page with a real anchor therefore passes both -- regardless of
what that page actually says. t1707 removed two links of exactly that shape by
hand (`ait artifact` pointing at pages documenting neither artifacts nor that
command); nothing established they were the only two. This closes that gap.

**Division of labour with `check_links.py` -- read this before extending either.**
That checker walks the *generated HTML* on purpose, and its docstring records
why. This one cannot: the deliverable here is `source_file:line`, so a human can
triage a report, and the built HTML has thrown that away. The two operate on
different inputs and answer different questions, and neither should grow into the
other's job:

* `check_links.py` owns **existence**: does the target resolve, does the anchor
  exist. It gates CI.
* this script owns **relevance**: given that the target exists, does it mention
  the subject the link text names. It is a report for human triage and never
  gates anything.

Design notes, each of which exists because the naive alternative was measured
against the live corpus and got it wrong (t1759):

* **A relref argument is a page lookup, not a URL path.** 19 of the corpus's 477
  relrefs are page-relative (`{{< relref "terminal-setup" >}}`). Treating the
  argument as a site-root path turns every one of them into an unresolved record.
  `resolve_relref` implements Hugo's order: directory-relative first, then a
  site-wide unique-name lookup -- whose index must key section pages by their
  *directory* name, since `{{< relref "development" >}}` reaches
  `development/_index.md` and every section page's stem is the useless `_index`.
* **The anchor can live inside the quoted argument.** 27 links write
  `{{< relref "/docs/tuis/settings#shortcuts-s" >}}` and 44 append `>}}#frag`
  outside it. A pattern that knows only the appended form silently mis-resolves
  the other 27.
* **Never collapse repeated hyphens when slugifying a heading.** Hugo does not:
  "Minimal / non-tmux workflow" is `#minimal--non-tmux-workflow`. Collapsing them
  loses the anchor and silently widens the check to the whole page.
* **An ambiguous name is reported, not guessed.** `reference` matches 6 pages and
  `how-to` 7, so the site-wide fallback needs a real conflict path.
* **Anything that does not resolve is counted, never scored.** An unresolved
  target is neither a hit nor a miss -- folding it into either would let a broken
  resolver read as a clean sweep.

**What this does NOT check** -- stated here because a coverage gap nobody can see
is indistinguishable from a clean result:

* Only links whose text contains a **backtick-quoted token** -- roughly seven in
  ten of the internal links, though the exact split moves with every docs commit,
  so read the `links checked` line of a run rather than any number written here.
  Prose link text has no distinctive token to match on, and matching it would
  invert the false-positive rate that makes this report usable.
* Only links written in the **markdown source**. Links emitted by shortcodes,
  layouts or Docsy templates are invisible to a source-side scanner;
  `check_links.py` sees those and this does not.
* Source-side URL mapping assumes Hugo's default filename->URL layout. No content
  file overrides it today, and `scan()` warns if one starts to.

Exit status is **0 even when links are reported** -- the misses are for a human to
triage, and several are expected to be false positives (link text that is a page
title, a prose paraphrase). The script exits non-zero only when one of its own
self-controls fails, i.e. when it can no longer prove it is still looking.

Usage:
    python3 check_link_relevance.py                 # sweep ./content
    python3 check_link_relevance.py --content path  # sweep another tree
    python3 check_link_relevance.py -v              # also list hits
    python3 check_link_relevance.py --report        # records only, no summary
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import urljoin, urlsplit

HERE = Path(__file__).resolve().parent

# --- Controls -------------------------------------------------------------
# Keyed on pre-existing site content, never on anything a repair edits. Each
# names a capability whose silent loss would make this script report a clean
# sweep of an empty set.
CTL_LINK_SOURCE = "docs/installation/updating-model-lists.md"
CTL_LINK_URL = "/docs/commands/codeagent/"
CTL_LINK_TOKEN = "ait codeagent"                  # present on the target page
CTL_STEM_SOURCE = "docs/skills/aitask-pr-import.md"
CTL_STEM_TOKEN = "ait pr-import"                  # from `ait pr-import --list`
CTL_RELATIVE_SOURCE = "docs/installation/_index.md"
CTL_RELATIVE_URL = "/docs/installation/terminal-setup/"   # from a bare relref

# --- Patterns -------------------------------------------------------------
# The target alternation must try the shortcode form FIRST. A relref contains
# spaces (`{{< relref "x" >}}`), so a plain "no whitespace, no paren" pattern
# matches none of the corpus's 477 relref links and silently reduces this script
# to a checker of hand-written paths only -- a clean-looking run over a third of
# the real link set.
LINK_RE = re.compile(
    r'\[([^\]\n]+)\]\((\{\{<.*?>\}\}[^)\s]*|[^)\s]+?)(?:\s+"[^"]*")?\)'
)
RELREF_RE = re.compile(r'\{\{<\s*relref\s+"([^"]+)"\s*>\}\}(#[^\s)]+)?$')
TICK_RE = re.compile(r"`([^`]+)`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
SLUG_STRIP_RE = re.compile(r"[^a-z0-9\s-]")
PLACEHOLDER_RE = re.compile(r"<[^>]*>|\[[^\]]*\]|\{[^}]*\}")
FLAG_RE = re.compile(r"\s--?\S+")
FRONTMATTER_OVERRIDE_RE = re.compile(r"^(slug|url):", re.M)
SKIP_SCHEMES = ("http://", "https://", "mailto:", "#")


class Record(NamedTuple):
    """One internal link, resolved (or not) to a target page."""

    source: str      # content-relative posix path of the page holding the link
    line: int        # 1-indexed
    text: str        # raw link text, backticks included
    url: str         # resolved site URL, or the raw target when unresolved
    anchor: str      # fragment without '#', '' when absent
    kind: str        # 'relref' | 'path'
    status: str      # 'ok' | 'ambiguous' | 'missing'


class Miss(NamedTuple):
    """A backticked token that the resolved target does not mention."""

    source: str
    line: int
    token: str
    url: str
    scope: str       # 'page' or '#<anchor>' -- what the token was searched in


class Result(NamedTuple):
    records: List[Record]
    hits: int
    misses: List[Miss]
    counters: Dict[str, int]
    warnings: List[str]


# --- URL mapping ----------------------------------------------------------
def page_url(rel: Path) -> str:
    """Hugo's default output URL for a content-relative markdown path."""
    if rel.name == "_index.md":
        parent = rel.parent.as_posix()
        return "/" if parent == "." else "/" + parent + "/"
    return "/" + rel.with_suffix("").as_posix() + "/"


def build_url_map(content_dir: Path) -> Dict[str, Path]:
    return {
        page_url(f.relative_to(content_dir)): f
        for f in sorted(content_dir.rglob("*.md"))
    }


def build_name_index(content_dir: Path) -> Dict[str, List[Path]]:
    """Name -> pages, for Hugo's site-wide relref fallback.

    Section pages are keyed by their **directory** name, not by the stem
    `_index`: `{{< relref "development" >}}` must reach `development/_index.md`.
    The value is a list so an ambiguous name is detectable rather than
    silently resolving to whichever page was walked first.
    """
    index: Dict[str, List[Path]] = {}
    for f in sorted(content_dir.rglob("*.md")):
        key = f.parent.name if f.name == "_index.md" else f.stem
        index.setdefault(key, []).append(f)
    return index


# --- relref resolution ----------------------------------------------------
def resolve_relref(
    source: Path,
    argument: str,
    content_dir: Path,
    url_map: Dict[str, Path],
    name_index: Dict[str, List[Path]],
    outer_anchor: str = "",
) -> Tuple[str, str, str]:
    """Resolve a relref argument to `(url, anchor, status)`.

    `outer_anchor` is a fragment appended after `>}}`. Hugo also accepts one
    inside the quoted argument; a link carrying **both** is reported
    `ambiguous` rather than resolved under an invented precedence (no link in
    the corpus does this, so there is no established behaviour to copy).
    """
    target = argument.strip()
    inner_anchor = ""
    if "#" in target:
        target, inner_anchor = target.split("#", 1)
        target = target.strip()

    if inner_anchor and outer_anchor:
        return (argument, "", "ambiguous")
    anchor = outer_anchor or inner_anchor

    if target.startswith("/"):
        url = target if target.endswith("/") else target + "/"
        return (url, anchor, "ok" if url in url_map else "missing")

    base = source.parent
    if target in ("", "_index", "_index.md"):
        candidate = base / "_index.md"
        if candidate.exists():
            return (page_url(candidate.relative_to(content_dir)), anchor, "ok")
        return (argument, anchor, "missing")

    name = target[:-3] if target.endswith(".md") else target
    for candidate in (base / f"{name}.md", base / name / "_index.md"):
        if candidate.exists():
            return (page_url(candidate.relative_to(content_dir)), anchor, "ok")

    matches = name_index.get(name, [])
    if len(matches) == 1:
        return (page_url(matches[0].relative_to(content_dir)), anchor, "ok")
    if len(matches) > 1:
        return (argument, anchor, "ambiguous")
    return (argument, anchor, "missing")


# --- extraction -----------------------------------------------------------
def extract_links(content_dir: Path) -> List[Record]:
    url_map = build_url_map(content_dir)
    name_index = build_name_index(content_dir)
    records: List[Record] = []

    for path in sorted(content_dir.rglob("*.md")):
        rel = path.relative_to(content_dir)
        own_url = page_url(rel)
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            for match in LINK_RE.finditer(line):
                text, target = match.group(1), match.group(2)
                relref = RELREF_RE.match(target)
                if relref:
                    outer = (relref.group(2) or "")[1:]
                    url, anchor, status = resolve_relref(
                        path, relref.group(1), content_dir, url_map,
                        name_index, outer,
                    )
                    kind = "relref"
                else:
                    if target.startswith(SKIP_SCHEMES):
                        continue
                    split = urlsplit(target)
                    if not split.path:
                        continue
                    url = urljoin(own_url, split.path)
                    if not url.endswith("/") and "." not in Path(url).name:
                        url += "/"
                    anchor, kind = split.fragment, "path"
                    status = "ok" if url in url_map else "missing"
                records.append(
                    Record(rel.as_posix(), lineno, text, url, anchor, kind, status)
                )
    return records


# --- relevance ------------------------------------------------------------
def stem(token: str) -> str:
    """Reduce a backticked token to its distinctive command words.

    `ait gate pass <task-id> <name>` -> `ait gate pass`. Without this, every
    documented command written with an argument or a flag reports as a miss
    against the page that documents it.
    """
    text = PLACEHOLDER_RE.sub(" ", token)
    text = FLAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def heading_slug(text: str) -> str:
    """Hugo's heading anchor. Repeated hyphens are preserved, not collapsed."""
    slug = SLUG_STRIP_RE.sub("", text.replace("`", "").lower()).strip()
    return slug.replace(" ", "-")


def anchor_section(body: str, anchor: str) -> Optional[str]:
    """The section named by `anchor`, **heading line included**, or None.

    The heading is part of the section, not a label outside it. A link to
    `#ait-gates-run` whose target section is literally `## ait gates run` names
    its subject in the one line a body-only slice would throw away -- and would
    then be reported as a miss for saying exactly the right thing.
    """
    lines = body.splitlines()
    for index, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if not heading or heading_slug(heading.group(2)) != anchor:
            continue
        level = len(heading.group(1))
        section: List[str] = [line]
        for following in lines[index + 1:]:
            nested = HEADING_RE.match(following)
            if nested and len(nested.group(1)) <= level:
                break
            section.append(following)
        return "\n".join(section)
    return None


def check(records: List[Record], url_map: Dict[str, Path]) -> Result:
    hits = 0
    misses: List[Miss] = []
    counters = {
        "checked": 0,
        "unresolved_target": 0,
        "anchor_not_found": 0,
        # Misses that exist *because* an anchor narrowed the search: the token is
        # somewhere on the target page, just not in the named section. This is
        # the only quantity that distinguishes "scoping is wired into scoring"
        # from "scoping is computed and then ignored" -- if the full page were
        # searched, none of these could be a miss at all. The
        # `anchor scoping narrowed the check` control asserts it is non-zero.
        "scope_narrowed_verdict": 0,
    }

    for record in records:
        tokens = [t for t in (stem(t) for t in TICK_RE.findall(record.text)) if t]
        if not tokens:
            continue
        counters["checked"] += 1
        if record.status != "ok":
            # Neither a hit nor a miss: we never read the page, so we know
            # nothing about relevance. Scoring it either way would let a broken
            # resolver read as a clean sweep.
            counters["unresolved_target"] += 1
            continue
        body = url_map[record.url].read_text()
        scope, label = body, "page"
        if record.anchor:
            section = anchor_section(body, record.anchor)
            if section is None:
                counters["anchor_not_found"] += 1
            else:
                scope, label = section, "#" + record.anchor
        for token in tokens:
            if token in scope:
                hits += 1
            else:
                if label != "page" and token in body:
                    counters["scope_narrowed_verdict"] += 1
                misses.append(
                    Miss(record.source, record.line, token, record.url, label)
                )
    return Result(records, hits, misses, counters, [])


def scan(content_dir: Path) -> Result:
    content_dir = Path(content_dir)
    url_map = build_url_map(content_dir)
    result = check(extract_links(content_dir), url_map)

    warnings: List[str] = []
    for path in sorted(content_dir.rglob("*.md")):
        head = path.read_text()[:2000]
        if FRONTMATTER_OVERRIDE_RE.search(head):
            warnings.append(
                f"{path.relative_to(content_dir).as_posix()} declares slug:/url: "
                "-- the filename->URL mapping this script assumes may be wrong"
            )
    return result._replace(warnings=warnings)


# --- self-controls --------------------------------------------------------
class _ProbePage:
    """Stands in for a content file so a control can drive `check()` directly."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read_text(self) -> str:
        return self._text


def _probe_scope_narrowing() -> bool:
    """Drive the real scoring path over a link whose token is in another section.

    `ait probe` appears on the probe page, but under `## Beta` while the link
    names `#alpha`. A page-scoped implementation finds it and reports no miss;
    only section-scoped scoring produces the miss this asserts. It also pins the
    scope label, so a correct verdict reached with a wrong label is caught too.
    """
    body = (
        "# Probe\n\n"
        "## Alpha\n\nNothing relevant here.\n\n"
        "## Beta\n\nRun `ait probe` in this section.\n"
    )
    url = "/__control_probe__/"
    records = [Record("__control_probe__.md", 1, "`ait probe`", url,
                      "alpha", "relref", "ok")]
    result = check(records, {url: _ProbePage(body)})
    return (
        len(result.misses) == 1
        and result.misses[0].scope == "#alpha"
        and result.misses[0].token == "ait probe"
        and result.counters["scope_narrowed_verdict"] == 1
    )


def _has_record(result: Result, source: str, url: str) -> bool:
    return any(r.source == source and r.url == url for r in result.records)


def _is_hit(result: Result, source: str, token: str) -> bool:
    """True when `token` was actually scored from `source` and did not miss.

    "No miss was reported" is not enough on its own: a control link that stopped
    resolving, lost its backticks, or vanished from the page produces no miss
    either, and a control that passes when its subject disappeared proves
    nothing. So require a **resolved** record from `source` whose stemmed tokens
    include `token`, and only then check that it did not miss.
    """
    scored = any(
        r.source == source
        and r.status == "ok"
        and token in [stem(t) for t in TICK_RE.findall(r.text)]
        for r in result.records
    )
    if not scored:
        return False
    return not any(
        m.source == source and m.token == token for m in result.misses
    )


CONTROLS = [
    (
        "extractor captured the control link",
        lambda r: _has_record(r, CTL_LINK_SOURCE, CTL_LINK_URL),
    ),
    (
        "relevance check reports a hit",
        lambda r: _is_hit(r, CTL_LINK_SOURCE, CTL_LINK_TOKEN),
    ),
    (
        "stem normalization strips a flag",
        lambda r: _is_hit(r, CTL_STEM_SOURCE, CTL_STEM_TOKEN),
    ),
    (
        # NOT "an anchored link was extracted" -- that passes for an
        # implementation that computes the scope and then searches the whole
        # page anyway. This drives the real `check()` path over a probe whose
        # token sits in a *different* section of the same page: it can only come
        # back a miss if scoring is section-scoped.
        #
        # A probe rather than a corpus link on purpose. Keying it to the one
        # live link that currently narrows a verdict would make the script exit
        # non-zero for everyone the day somebody legitimately repoints that
        # link -- a control that fails when the content is *fixed*. The corpus
        # side of the same evidence is reported as `scope-narrowed`.
        "anchor scoping narrowed the check",
        lambda r: _probe_scope_narrowing(),
    ),
    (
        "page-relative relref resolved",
        lambda r: _has_record(r, CTL_RELATIVE_SOURCE, CTL_RELATIVE_URL),
    ),
]


def evaluate_controls(result: Result, controls=None) -> Dict[str, bool]:
    return {name: bool(fn(result)) for name, fn in (controls or CONTROLS)}


# --- CLI ------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--content", default=str(HERE / "content"),
                        help="content directory to sweep (default: ./content)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="also list resolved hits")
    parser.add_argument("--report", action="store_true",
                        help="print records only, no summary or controls")
    args = parser.parse_args()

    content_dir = Path(args.content)
    if not content_dir.is_dir():
        print(f"error: no such content directory: {content_dir}", file=sys.stderr)
        return 2

    result = scan(content_dir)

    for miss in result.misses:
        print(f"{miss.source}:{miss.line}  `{miss.token}`  ->  "
              f"{miss.url} [{miss.scope}]")
    if args.report:
        return 0

    for warning in result.warnings:
        print(f"warning     : {warning}", file=sys.stderr)
    if args.verbose:
        # Every link that carried a token and resolved -- NOT "every hit". The
        # ones that missed are the records printed above; labelling this list
        # "hits" would overstate by exactly the misses.
        for record in result.records:
            if record.status == "ok" and TICK_RE.search(record.text):
                scope = f"#{record.anchor}" if record.anchor else "page"
                print(f"checked     : {record.source}:{record.line} -> "
                      f"{record.url} [{scope}]")

    counters = result.counters
    print(f"\nlinks checked : {counters['checked']}")
    print(f"hits          : {result.hits}")
    print(f"reported      : {len(result.misses)}")
    print(f"unresolved    : {counters['unresolved_target']}")
    print(f"anchor n/f    : {counters['anchor_not_found']}")
    # Reported links that are a miss only because an anchor narrowed the search:
    # the token IS on the target page, just not in the named section. A common
    # false-positive shape, so it is worth seeing separately when triaging.
    print(f"scope-narrowed: {counters['scope_narrowed_verdict']}")

    controls = evaluate_controls(result)
    for name, ok in controls.items():
        print(f"control       : {name}: {ok}")

    failed = [name for name, ok in controls.items() if not ok]
    if failed:
        # ANY failed control, not all of them: a run whose extractor collapsed
        # while the stem control still passes is exactly the silently-stopped-
        # looking case these exist to catch.
        print("\nFAILED CONTROL(S) -- this run proves nothing about the content:",
              file=sys.stderr)
        for name in failed:
            print(f"  - {name}", file=sys.stderr)
        return 1

    print("\nRelevance is a heuristic: reported links need human triage, and "
          "some are expected to be false positives.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
