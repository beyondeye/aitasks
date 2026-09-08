---
priority: medium
effort: low
depends: []
issue_type: performance
status: Ready
labels: [bash_scripts, performance, macos, framework]
gates: [risk_evaluated]
anchor: 1681
followup_kind: upstream_defect
created_at: 2026-09-08 22:28
updated_at: 2026-09-08 22:28
---

## Origin

Spawned from t1746 during Step 8b review. t1746 routed test drivers through the
launching interpreter so a `/bin/bash` run genuinely tests bash 3.2. That made
this pre-existing performance defect visible: `tests/test_yaml_utils.sh` had to
be **excluded from its own 3.2 lane** because the run does not terminate in any
practical time.

## Problem

`_join_yaml_flow_lists_impl` (`.aitask-scripts/lib/yaml_utils.sh:136`) counts
bracket depth with two full pattern substitutions over the accumulated buffer,
once per input line:

```bash
opens="${buffer//[^\[]/}"
closes="${buffer//[^\]]/}"
depth=$(( ${#opens} - ${#closes} ))
```

A YAML inline flow list is a **single line**, so for an N-byte value this is two
`${var//pat/}` passes over an N-byte string. Under bash 3.2 that operation is
catastrophically slower than under 5.x.

Measured (macOS 15, one `read_yaml_list` over an inline flow list):

| fixture | bash 5.3.9 | bash 3.2.57 | ratio |
|---------|-----------|-------------|-------|
| 2 KB    | 0.03s     | 1.14s       | 38x   |
| 4 KB    | 0.04s     | 7.99s       | 200x  |
| 8 KB    | 0.10s     | 61.5s       | 615x  |
| 16 KB   | 0.30s     | 494.8s      | 1650x |

Each doubling multiplies bash 3.2's time by ~8 — the scan is **cubic** there,
not quadratic. Extrapolated to `test_yaml_utils.sh`'s 77KB inline fixture:
`(77/16)^3 x 495s` ~ **15 hours per call**. A real attempt was killed after
3h10m at 99% CPU.

Note this is not only a 3.2 problem: `tests/test_yaml_utils.sh` already carries a
comment recording the same scan as quadratic under 5.x ("2.1s at 70KB, 8.3s at
140KB, 34.5s at 324KB"), and sizes its fixture down to limit the cost.

## Impact

- `tests/test_yaml_utils.sh` cannot be run under bash 3.2 at all (documented in
  its header and in `aidocs/framework/sed_macos_issues.md`), so the framework has
  no 3.2 coverage for the YAML readers, SIGPIPE guards or trap-leak pins.
- Any production caller reading a large inline flow list pays the quadratic cost
  even on bash 5.x.

## Proposed fix

Replace the two pattern substitutions with an O(n) count. `tr -dc` is portable
and does one pass per bracket class:

```bash
opens=$(printf '%s' "$buffer" | tr -dc '[')
closes=$(printf '%s' "$buffer" | tr -dc ']')
depth=$(( ${#opens} - ${#closes} ))
```

That costs two forks per line, which may be worse for the common many-short-lines
case — so **measure both shapes** (few huge lines vs many tiny lines) before
committing to it. A fork-free alternative worth benchmarking: track depth
incrementally per line instead of re-scanning the whole accumulated buffer,
which removes the re-scan that makes this quadratic in the first place.

## Constraints

`.aitask-scripts/lib/yaml_utils.sh` is sourced by ~40 scripts and has a carefully
documented write-contract (SIGPIPE guard, `_yaml_emit`, regular-file write
guard). Do not disturb those; this change is confined to the depth arithmetic.

## Verification

- Re-run the scaling curve above under both shells; 77KB must complete in well
  under a second on 5.x and in seconds (not hours) on 3.2.
- `bash tests/test_yaml_utils.sh` → 148/148 under 5.x, unchanged.
- Then **re-enable the 3.2 lane**: `/bin/bash tests/test_yaml_utils.sh` must pass,
  and the "DO NOT run this file under bash 3.2" header warning plus the
  corresponding paragraph in `aidocs/framework/sed_macos_issues.md` must both be
  removed in the same change.
- Pin the fix with a test: a large inline flow list must read correctly and the
  bracket depth must still be right for nested/multi-line flow lists.
