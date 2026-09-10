---
priority: low
effort: low
depends: [1782]
issue_type: test
status: Ready
labels: [documentation, web_site]
gates: [risk_evaluated]
anchor: 1657
followup_kind: review_finding
created_at: 2026-09-10 15:40
updated_at: 2026-09-10 15:40
---

## Origin

Deferred from t1782's plan review (concern disposition: follow-up). t1782 added
`tests/test_docs_readme_links.sh`, whose `check_readme()` extracts inline
Markdown links (`[text](target)`) only.

## Gap

- **Silent bypasses:** a reference-style definition (`[x]: ../path.md`) or an
  HTML `<a href="...">` in `docs/README.md` is never extracted, so a stale one
  passes while the table's inline links keep `LINKS:` non-zero.
- **Loud false findings:** an inline destination with a title (`](p "t")`) or in
  angle brackets (`](<p>)`) is reported as `DEAD:` even when the target exists.

## Goal

Pick one approach:
- **restrict and enforce** — emit an `UNSUPPORTED:<line>` finding (non-zero
  exit) for each disallowed form. Cheapest, and matches the "enforce the
  convention, don't parse for intent" rule; or
- **extend extraction** to cover the forms.

Either way:
- add one negative control per form, using the file's fresh-fixture pattern
  (`make_fixture` + `write_readme`, then mutate);
- update the test header's "What it does NOT check" list, and the two pointer
  lines that say "inline links": the closing line of `docs/README.md` and the
  `docs/README.md` paragraph under "Checking Internal Links" in
  `website/README.md`.

The hook point is the single `check_readme()` function.
