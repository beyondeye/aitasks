# aitasks Website

This directory contains the Hugo/Docsy website for aitasks.

**Live site:** https://aitasks.io/

## Required Tools

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| [Hugo](https://gohugo.io/) extended edition | 0.155.3 | Static site generator |
| [Go](https://go.dev/) | 1.23 | Required for Hugo Modules |
| [Dart Sass](https://sass-lang.com/dart-sass/) | 1.97 | SCSS compilation (required by Docsy theme) |
| [Node.js](https://nodejs.org/) | 18+ | Required for PostCSS (used by Docsy theme) |

Hugo **extended edition** is required because the Docsy theme uses SCSS for styling. Node.js is required because Docsy uses PostCSS for CSS processing.

## Installation

### Arch Linux

```bash
sudo pacman -S hugo go dart-sass nodejs npm
```

The Arch `hugo` package includes the extended edition by default.

After installing system packages, install the Node.js dependencies:

```bash
cd website
npm install
```

### macOS (Homebrew)

```bash
brew install hugo go sass/sass/sass node
```

Then install Node.js dependencies:
```bash
cd website && npm install
```

### Ubuntu / Debian

```bash
# Hugo extended - use the official .deb from GitHub releases
# (the apt package may be outdated or missing the extended edition)
# See: https://gohugo.io/installation/linux/#debian

# Go
sudo apt install golang-go

# Dart Sass
sudo snap install dart-sass

# Node.js
sudo apt install nodejs npm
```

For Hugo on Ubuntu, it's recommended to download the latest extended `.deb` package from the [Hugo releases page](https://github.com/gohugoio/hugo/releases) to ensure you get the extended edition.

After installing system packages, install the Node.js dependencies:
```bash
cd website && npm install
```

### Windows (via WSL)

Follow the Ubuntu/Debian instructions inside your WSL distribution.

## Verify Installation

Run these commands to verify everything is installed correctly:

```bash
hugo version    # Should show "extended" in the output
go version      # Should show >= 1.23
sass --version  # Should show >= 1.97
node --version  # Should show >= 18
```

## Local Development

First, ensure Node.js dependencies are installed:
```bash
cd website
npm install
```

Then start the development server:
```bash
hugo server
```

The site will be available at `http://localhost:1313/aitasks/`.

Hugo watches for file changes and automatically rebuilds, so you can edit content and see changes in real time.

### First Run

On the first run, Hugo will download the Docsy theme module automatically. This may take a minute. Subsequent runs use the cached module.

If you see module errors, try:

```bash
cd website
hugo mod tidy
hugo mod get -u
```

## Adding Content

- Documentation pages go in `content/docs/`
- Each page needs Docsy frontmatter (`title`, `linkTitle`, `weight`, `description`)
- Pages in subdirectories use `_index.md` as the section landing page
- `weight` controls ordering in the sidebar navigation (lower = higher)
- See existing pages for examples

### Internal links

Use `{{< relref "/docs/..." >}}` rather than a hand-written relative path. A
relref fails the build when the target page is moved or renamed; a relative
path is just text and silently rots. Append an anchor outside the shortcode:
`[Text]({{< relref "/docs/tuis/monitor/reference" >}}#pane-classification)`.

## Checking Internal Links

`hugo build` validates `{{< relref >}}` targets and nothing else. A
hand-written relative path that resolves one directory level wrong, and a
`#fragment` pointing at a heading that does not exist, both build **green** —
so the whole class is invisible to the build and to CI.

`check_links.py` closes that gap. It resolves every same-site link in the
*generated* HTML against the file that renders it, checks fragments against the
target page's `id` attributes, and exits non-zero on any broken link:

```bash
cd website
python3 check_links.py --build     # builds its own copy, then sweeps
```

- Python 3 stdlib only — no dependencies beyond Hugo itself.
- `--build` renders into a private temporary directory. It deliberately does
  **not** use `public/`, which is gitignored and may contain whatever was last
  built (a `hugo server` run, a non-minified build). Sweeping a stale or
  differently-flagged tree gives an unreliable answer.
- Pass `--base-url` when checking a site built with a non-default base URL; CI
  passes the same GitHub Pages URL the build step used. Without it the base
  path is auto-detected from the built RSS feed's `<channel><link>`.
- `-v` prints the derived base path and where it came from, and lists the
  base-agnostic links described below.

### The `base-agnostic` count

Hugo rewrites site-root links it owns (`relref`, `relURL`), but a path written
by hand inside a shortcode parameter or raw HTML — `url="/docs/..."` on a Docsy
`blocks/feature`, `href="/blog/"` in an `<a>` — passes through verbatim. Under
the site's own base path (`/`) that is simply correct. Under a base URL with a
path prefix it renders without that prefix, so the checker reports it under a
separate **`base-agnostic`** count rather than as broken.

They are still fully resolved: the target must exist and any `#fragment` must be
present, so a genuinely dead one is still reported (as `outside-base` or
`missing-anchor`). The count is printed on every run and `-v` lists each link,
because an exception nobody can see is indistinguishable from a checker that
stopped looking. A count that suddenly matches the total link count means the
base path is wrong — which the `base path is the one the site was built with`
control fails on independently.

Run it after editing any page under `content/`. CI runs it right after the
release build (`.github/workflows/hugo.yml`), so a dead link fails the job and
the site does not deploy.

## Checking Link *Relevance*

`check_links.py` answers "does the target exist". It cannot answer "is the target
*about* what the link text says". A link to a real page with a real anchor passes
every check the repo runs, however unrelated that page's content is — which is
how two `` `ait artifact` `` links pointing at pages documenting neither
artifacts nor that command survived until someone read them by hand.

`check_link_relevance.py` reports that class:

```bash
cd website
python3 check_link_relevance.py
```

It reads the **markdown sources** rather than the built HTML — deliberately, and
unlike `check_links.py`. The output is `source_file:line`, so a human can go
straight to the link; the generated HTML has thrown that away. The two scripts
divide the work and neither should grow into the other's job:

| | `check_links.py` | `check_link_relevance.py` |
|---|---|---|
| input | built HTML | markdown sources |
| question | does the target resolve, does the anchor exist | does the target mention the subject the link text names |
| output | broken links | candidates for human triage |
| CI | **gates the deploy** | not wired to CI |

**It is a report, not a gate.** Reported links do not change the exit status —
relevance is a heuristic and some hits are expected to be false positives (link
text that is a page title, a prose paraphrase, a script name standing in for the
command a page documents). The script exits non-zero only when one of its own
self-controls fails, i.e. when it can no longer prove it is still looking; it
prints every control on every run.

### What it does not check

Stated explicitly, because a coverage gap nobody can see is indistinguishable
from a clean result:

- **Only backtick-quoted link text** — roughly seven internal links in ten. The
  exact split moves with every docs commit, so read the `links checked` line of a
  run rather than a number quoted here. Prose link text carries no distinctive
  token to match on, and matching it would bury the real signal under false
  positives.
- **Only links written in the markdown source.** Links emitted by shortcodes,
  layouts or Docsy templates are invisible to a source-side scanner —
  `check_links.py` sees those and this does not.
- **Hugo's default filename→URL layout is assumed.** No content file overrides it
  with `slug:` or `url:` today; if one starts to, the script warns rather than
  silently mis-resolving.

Links whose target does not resolve are counted under `unresolved` and are
deliberately scored as **neither** a hit nor a miss — folding them into either
would let a broken resolver read as a clean sweep. A non-zero `unresolved` or
`anchor n/f` count therefore means the resolver regressed, and should be read as
a fault in the checker before any reported link is triaged.

## Deployment

Automatic on push of version tags (`v*`) via GitHub Actions. See `.github/workflows/hugo.yml`.

The site is deployed to https://aitasks.io/

## Common Issues

### SCSS compilation errors

If you see SCSS-related errors, verify that:
1. You have the **extended** edition of Hugo (`hugo version` should include "extended")
2. Dart Sass is installed and accessible (`sass --version`)
3. The placeholder files exist:
   - `website/assets/scss/_variables_project.scss`
   - `website/assets/scss/_styles_project.scss`

### PostCSS not found

If you see an error like `binary with name "postcss" not found`:
1. Ensure Node.js is installed: `node --version`
2. Run `cd website && npm install` to install PostCSS and autoprefixer
3. Verify `website/node_modules/.bin/postcss` exists

### Module download failures

If `hugo mod get` fails:
1. Check your internet connection
2. Verify Go is installed: `go version`
3. Try clearing the module cache: `hugo mod clean`
4. Re-download: `hugo mod get -u`

### Port already in use

If port 1313 is busy, use a different port:

```bash
hugo server --port 1314
```
