---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [website, screenshots]
gates: [risk_evaluated]
anchor: 2278
followup_kind: upstream_defect
created_at: 2026-11-16 15:30
updated_at: 2026-11-16 15:30
---

## Origin

Spawned from t2278_3 during Step 8b review.

## Upstream defect

- `website/screenshots/svg_export.py:render_png` — headless Chromium leaves
  `org.chromium.Chromium.*` / `org.chromium.Chromium.chromium_chrome_url_fetcher_*`
  scratch directories in `$TMPDIR` on every PNG preview. The Python suite's
  tmpdir guard reports them (`TMPDIR LEFTOVERS (2): org.chromium.Chromium.chromium_chrome_url_fetcher_.…`),
  warn-only. The renderer was added by t2278_2; t2278_3 added tests that
  exercise it, which is how the leftovers became visible.

## Diagnostic context

- `render_png` already runs Chromium with a private `--user-data-dir` in a
  `tempfile.TemporaryDirectory(prefix="ait_shots_chrome_")`, removed after the
  render. The url-fetcher directories are created in `$TMPDIR`, outside it.
- Tried in t2278_3 and reverted: passing `TMPDIR=<profile dir>` to the Chromium
  subprocess. Under a long scratch `TMPDIR`
  (`/tmp/claude-1000/<project>/<session>/scratchpad/...`) Chromium aborted
  with SIGABRT. The same abort happens with the unmodified code when the test
  run's `TMPDIR` itself is that long, so the cause is most likely the path
  length of a Unix socket Chromium creates under `$TMPDIR` (108-byte
  `sun_path` limit), not the env change as such. With the default `TMPDIR`
  every preview test passes.

## Suggested fix

Give the Chromium subprocess a SHORT dedicated `TMPDIR` (e.g. a
`tempfile.mkdtemp(dir="/tmp", prefix="ait_shots_chrome_tmp_")`, removed
afterwards), and add a test that runs `render_png` under a private `TMPDIR`
and asserts nothing is left in it. Also check whether a long `$TMPDIR` should
make `render_png` fall back to a short one rather than abort.
