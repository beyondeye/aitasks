---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [website, screenshots]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-16 15:30
updated_at: 2026-11-16 18:10
completed_at: 2026-11-16 18:10
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

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T13:50:52Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-16T16:00:52Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-16T16:10:33Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:6b92d901b52961cd

> **✅ gate:risk_evaluated** run=2026-11-16T16:10:33Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2316/risk_evaluated_2026-11-16T16:10:33Z-risk_evaluated-a1.log`
