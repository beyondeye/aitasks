#!/usr/bin/env python3
"""Sweep every same-site link on the built Hugo site and fail on any broken one.

`hugo build` cannot catch this class. It fails a broken `{{< relref >}}` (the
page must exist), but a hand-written relative markdown path is just text, and a
`#fragment` pointing at a heading that does not exist builds green. This checker
closes that gap: it resolves every same-site href against the generated HTML and
reports a resolved/broken count plus one normalized record per broken link.

Design notes, each of which exists because a naive alternative silently produced
a false pass (learned in t1603_5, extended in t1682):

* **Walk the generated HTML; never map source filenames to output paths.**
  `_index.md` builds to `<section>/index.html`, and sources carry site-root
  (`/docs/...`), page-relative (`reference/#...`) and `../../` forms whose
  resolution depends on Hugo's URL layout, not on the filename. Hugo has already
  resolved every href in the output.
* **Extract with a real HTML attribute parser, not a regex.** `--minify` strips
  attribute quotes from `href` exactly as it does from `id`: the minified
  `docs/tuis/board/how-to/index.html` holds only *two* quoted hrefs in the whole
  page, so a quote-only pattern reports a clean sweep of an empty set.
* **"Same-site" is an origin question, not a "has a netloc" question.** The site
  emits ~1600 absolute same-origin hrefs (Docsy taxonomy/blog navigation) on
  nearly every page. Skipping anything with a netloc drops them all silently.
* **The base URL is not always `/`.** CI builds with
  `--baseURL "${{ steps.pages.outputs.base_url }}/"`; a GitHub Pages project
  path renders every site-root href as `/<project>/docs/...`. The base path is
  therefore taken from `--base-url`, or auto-detected from the built RSS feed's
  `<channel><link>` -- *not* from its `<atom:link rel="self">` href, which is
  `<root>/index.xml` and would yield a base path of `/index.xml`.
* **Never trust a pre-existing `public/`.** It is gitignored and gets rewritten
  by whatever anyone last ran (`hugo server`, a non-minified build). Use
  `--build`, which renders into a private destination.

Two deliberate policies:

* A `#fragment` whose target is a Hugo *alias stub* (a `meta refresh` redirect
  page, which carries no ids) is reported broken. Link the canonical page
  instead.
* **Site-root hrefs that do not carry the base path are accepted, not broken.**
  Hugo rewrites site-root links it owns (`relref`, `relURL`), but a path written
  by hand inside a shortcode parameter or raw HTML -- `url="/docs/..."` on a
  Docsy `blocks/feature`, `href="/blog/"` in an `<a>` -- passes through verbatim.
  Under a base path of `/` that is simply correct; under a project-path base URL
  it renders as an unprefixed `/docs/...`. These are reported under their own
  `base-agnostic` count rather than as broken. They are still resolved: the
  target must exist at the output root and any fragment must be present, so a
  genuinely dead one is reported `outside-base` as before. The count is printed
  on every run and the individual links are listed under `-v`, because an
  exception nobody can see is indistinguishable from a checker that stopped
  looking.

Usage:
    python3 check_links.py --build            # hermetic: builds its own copy
    python3 check_links.py                    # sweep ./public as-is
    python3 check_links.py --base-url "https://example.org/proj/"
    python3 check_links.py --report           # normalized records only
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

HERE = Path(__file__).resolve().parent

# --- Controls -------------------------------------------------------------
# All are keyed on pre-existing site content, never on anything a repair edits.
CTL_EXTRACT_PAGE = "docs/tuis/board/index.html"
CTL_EXTRACT_HREF = "how-to/#how-to-mark-tasks"   # unquoted + relative + fragment
CTL_RESOLVE_PAGE = "docs/tuis/board/reference/index.html"
CTL_RESOLVE_FRAG = "by-trail"                    # pre-existing, known good
CTL_BASE_PAGE = "docs/index.html"
CTL_BASE_SUFFIX = "docs/"                        # matched as <base_path> + this
CTL_ABS_PAGE = "blog/index.html"
CTL_ABS_SUFFIX = "depth/advanced/"               # matched as <base_path> + this


class Hrefs(HTMLParser):
    """Collect every <a href>. A parser, not a regex: --minify writes href
    unquoted, and a quote-only pattern would capture almost nothing."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for k, v in attrs:
            if k == "href" and v is not None:
                self.hrefs.append(v)


class Ids(HTMLParser):
    """Collect every fragment target: any element `id`, plus legacy <a name>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get("id"):
            self.ids.add(d["id"])
        if tag == "a" and d.get("name"):
            self.ids.add(d["name"])


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


_ids_cache: dict[Path, set[str]] = {}


def ids_of(path: Path) -> set[str]:
    if path not in _ids_cache:
        p = Ids()
        p.feed(_read(path))
        _ids_cache[path] = p.ids
    return _ids_cache[path]


def normalize_base_path(path: str) -> str:
    """`/aitasks/index.xml` -> `/aitasks/`; `` or `/aitasks` -> `/` or `/aitasks/`.

    Stripping a terminal `index.xml` matters: the RSS atom self-link points at
    the feed file, not the site root, and using it raw would make base_path
    `/index.xml` -- under which every ordinary `/docs/...` link is `outside-base`.
    """
    path = re.sub(r"index\.xml$", "", path or "/")
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith("/"):
        path += "/"
    return path


def detect_base(public: Path, base_url: str | None) -> tuple[str, str, str]:
    """Return (base_path, base_netloc, source)."""
    if base_url:
        s = urlsplit(base_url)
        return normalize_base_path(s.path), s.netloc, "--base-url"
    feed = public / "index.xml"
    if feed.is_file():
        # The channel <link> IS the site root. The <atom:link rel="self"> href
        # is <root>/index.xml -- do not use it without stripping that segment.
        m = re.search(r"<channel>.*?<link>([^<]*)</link>", _read(feed)[:4000], re.S)
        if m:
            s = urlsplit(m.group(1).strip())
            return normalize_base_path(s.path), s.netloc, "index.xml channel link"
    return "/", "", "fallback"


def url_to_file(public: Path, base_path: str, url_path: str) -> Path | None:
    """A rendered URL path -> the file that serves it, or None if outside base."""
    if not url_path.startswith(base_path):
        return None
    rel = url_path[len(base_path):]
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    elif "." not in Path(rel).name:
        rel += "/index.html"
    return public / rel


def build_site(dest: Path, base_url: str | None) -> None:
    if shutil.which("hugo") is None:
        sys.exit("check_links: 'hugo' not found on PATH; cannot --build")
    # Exactly the flags .github/workflows/hugo.yml uses, plus a private
    # destination so a concurrent `hugo server` in ./public cannot affect us.
    cmd = ["hugo", "--gc", "--minify", "--destination", str(dest)]
    if base_url:
        cmd += ["--baseURL", base_url]
    proc = subprocess.run(cmd, cwd=HERE)
    if proc.returncode != 0:
        sys.exit(f"check_links: hugo build failed (exit {proc.returncode})")


def sweep(public: Path, base_path: str, base_netloc: str):
    """Return (records, counts, base_agnostic, controls)."""
    records: list[str] = []
    base_agnostic: list[str] = []
    resolved = skipped = abs_same_site = root_relative = 0
    ctl = {
        "extractor captured the control href": False,
        "that href resolved": False,
        "that href is unquoted in the output": False,
        "resolver found the known-good anchor": False,
        "base path is the one the site was built with": False,
        "same-origin absolute links are in scope": False,
    }
    ctl_base_seen = False
    ctl_abs_seen = False

    for f in sorted(public.rglob("*.html")):
        page = f.relative_to(public).as_posix()
        page_url = base_path + (page[: -len("index.html")]
                                if page.endswith("index.html") else page)

        for raw in Hrefs_of(f):
            href = raw.strip()
            if href in ("", "#"):
                skipped += 1
                continue
            s = urlsplit(href)
            if s.scheme and s.scheme not in ("http", "https"):
                skipped += 1                      # mailto:, tel:, javascript:...
                continue
            if s.netloc and s.netloc != base_netloc:
                skipped += 1                      # genuinely external origin
                continue

            if s.netloc:
                abs_same_site += 1
                # Same origin: keep the path+fragment, drop scheme/host. Scheme
                # is ignored on purpose, so an http:// link to an https:// site
                # is still checked.
                url_path, frag = s.path or "/", s.fragment
            else:
                if href.startswith("/"):
                    root_relative += 1
                a = urlsplit(urljoin(page_url, href))
                url_path, frag = a.path, a.fragment
            frag = unquote(frag)

            if page == CTL_EXTRACT_PAGE and href == CTL_EXTRACT_HREF:
                ctl["extractor captured the control href"] = True
            if page == CTL_BASE_PAGE and href == base_path + CTL_BASE_SUFFIX:
                ctl_base_seen = True
            if (page == CTL_ABS_PAGE and s.netloc
                    and s.path == base_path + CTL_ABS_SUFFIX):
                ctl_abs_seen = True

            is_base_agnostic = False
            target = url_to_file(public, base_path, unquote(url_path))
            if target is None:
                # A site-root path that does not carry the base path: written by
                # hand in a shortcode parameter or raw HTML, which Hugo passes
                # through verbatim. Accept it if it resolves at the output root
                # -- but keep resolving it, so a dead one is still reported.
                target = url_to_file(public, "/", unquote(url_path))
                if target is None or not target.is_file():
                    records.append(f"{page}|{href}|outside-base")
                    continue
                is_base_agnostic = True
            if not target.is_file():
                records.append(f"{page}|{href}|missing-page")
                continue
            if frag and frag not in ids_of(target):
                records.append(f"{page}|{href}|missing-anchor")
                continue

            resolved += 1
            # Counted only once the link fully resolves -- a dead one is a
            # broken record, never an accepted exception.
            if is_base_agnostic:
                base_agnostic.append(f"{page}|{href}")
            if page == CTL_EXTRACT_PAGE and href == CTL_EXTRACT_HREF:
                ctl["that href resolved"] = True
            if (page == CTL_BASE_PAGE and href == base_path + CTL_BASE_SUFFIX):
                ctl["base path is the one the site was built with"] = True
            if page == CTL_ABS_PAGE and ctl_abs_seen and s.netloc:
                ctl["same-origin absolute links are in scope"] = True
            # Keyed on the resolved TARGET, not on which page carried the link:
            # the control is "the resolver finds this known-good anchor", and
            # the reference page does not link to its own.
            if target == public / CTL_RESOLVE_PAGE and frag == CTL_RESOLVE_FRAG:
                ctl["resolver found the known-good anchor"] = True

    # The minification premise the parser exists for: prove href really is
    # written unquoted, so a quote-only pattern would have found nothing.
    ctl_page = public / CTL_EXTRACT_PAGE
    if ctl_page.is_file():
        ctl["that href is unquoted in the output"] = (
            f"href={CTL_EXTRACT_HREF}" in _read(ctl_page))

    # Keyed on a named href that CARRIES the base path (`/docs/` at root,
    # `/aitasks/docs/` under a project path), so a wrong base path fails here.
    # It cannot be keyed on "every root-relative href starts with base_path"
    # any more -- the base-agnostic class above is legitimately outside it.
    ctl["base path is the one the site was built with"] = (
        root_relative > 0 and ctl_base_seen
        and ctl["base path is the one the site was built with"])
    ctl["same-origin absolute links are in scope"] = (
        abs_same_site > 0 and ctl["same-origin absolute links are in scope"])

    records.sort()
    base_agnostic.sort()
    counts = dict(resolved=resolved, skipped=skipped,
                  absolute=abs_same_site, root_relative=root_relative)
    return records, counts, base_agnostic, ctl


def Hrefs_of(path: Path) -> list[str]:
    p = Hrefs()
    p.feed(_read(path))
    return p.hrefs


def load_expect(path: Path) -> Counter:
    out: Counter = Counter()
    for line in _read(path).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out[line] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true",
                    help="run `hugo --gc --minify` into a private destination first")
    ap.add_argument("--public", type=Path, default=None,
                    help="built site to sweep (default: ./public next to this script)")
    ap.add_argument("--base-url", default=None,
                    help="the base URL the site was BUILT with")
    ap.add_argument("--expect", type=Path, default=None,
                    help="compare the broken-record multiset against this file")
    ap.add_argument("--report", action="store_true",
                    help="print normalized broken records only, then exit 0")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="also print the derived base path and its source")
    args = ap.parse_args()

    tmp = None
    if args.build:
        if args.public is not None:
            public = args.public.resolve()
            public.mkdir(parents=True, exist_ok=True)
        else:
            tmp = tempfile.TemporaryDirectory(prefix="check_links-")
            public = Path(tmp.name)
        build_site(public, args.base_url)
    else:
        public = (args.public or (HERE / "public")).resolve()

    if not public.is_dir():
        sys.exit(f"check_links: no built site at {public} (use --build)")

    base_path, base_netloc, source = detect_base(public, args.base_url)
    records, counts, base_agnostic, ctl = sweep(public, base_path, base_netloc)

    if args.report:
        for r in records:
            print(r)
        return 0

    if args.verbose:
        print(f"site        : {public}")
        print(f"base path   : {base_path}   (source: {source}"
              + (f", host {base_netloc}" if base_netloc else "") + ")")
    print(f"resolved    : {counts['resolved']}")
    print(f"broken      : {len(records)}")
    print(f"skipped     : {counts['skipped']} "
          "(external origin / non-web scheme / empty)")
    print(f"same-site   : {counts['root_relative']} root-relative, "
          f"{counts['absolute']} absolute")
    print(f"base-agnostic: {len(base_agnostic)} "
          "(site-root hrefs written without the base path; resolved at the root)")
    if args.verbose:
        for b in base_agnostic:
            print("  BASE-AGNOSTIC:", b)
    for name, ok in ctl.items():
        print(f"control     : {name}: {ok}")
    for r in records:
        print("  BROKEN:", r)

    fail = bool(records)
    for name, ok in ctl.items():
        if not ok:
            print(f"  CONTROL FAILED: {name}")
            fail = True
    if not ctl["that href is unquoted in the output"]:
        print("  HINT: the site under --public was not built with --minify; "
              "re-run with --build, or point at a --minify build")

    if args.expect is not None:
        got, want = Counter(records), load_expect(args.expect)
        for rec, n in sorted((want - got).items()):
            print(f"  MISSING x{n}: {rec}")
            fail = True
        for rec, n in sorted((got - want).items()):
            print(f"  UNEXPECTED x{n}: {rec}")
            fail = True
        if got == want:
            print(f"expect      : set equality against {args.expect} "
                  f"({sum(want.values())} records)")

    print("SWEEP:", "FAILED" if fail else "PASSED")
    if tmp is not None:
        tmp.cleanup()
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
