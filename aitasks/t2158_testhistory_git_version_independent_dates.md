---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [go_engine, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-26 17:46
updated_at: 2026-10-26 17:58
---

## Origin

Spawned from t2154 during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/fixture/fixture_test.go:49 — TestHistory requires git to print a UTC %cI date as "Z"; git 2.43 (Ubuntu 24.04's stock git) prints "+00:00", so the test fails on stock-distro git even though the fixture dates are correct`

## Diagnostic context

While building t2154's dash-parity container (`goengines/ci/dashcheck.sh`), the first prototype
image used Ubuntu 24.04's stock git 2.43. The whole Go suite passed under dash except:

```
--- FAIL: TestHistory (0.11s)
    fixture_test.go:50: dates "2026-01-01T00:00:00+00:00\n2026-01-01T00:01:00+00:00\n2026-01-01T00:02:00+00:00\n"
```

Newer git (2.56 on the dev box; the hosted runners install git from ppa:git-core/ppa) prints the
same instant as `2026-01-01T00:00:00Z`. The fixture's commit dates are correct — only the
assertion depends on git's strict-ISO rendering of a zero UTC offset. t2154 worked around it by
installing the PPA git in the image (matching the runners), so nothing currently fails; but the
test fails on any stock-distro git older than the "Z" rendering change.

## Suggested fix

Compare instants rather than strings: parse each `%cI` line with `time.Parse(time.RFC3339, …)`
and check against `fixture.Epoch` (+1 min per commit), or use `--format=%ct` (Unix seconds),
which is version-independent. Verify under both renderings, e.g. with
`goengines/ci/dashcheck.sh -run TestHistory ./internal/testmap/fixture/` and a scratch image on
stock git 2.43.
