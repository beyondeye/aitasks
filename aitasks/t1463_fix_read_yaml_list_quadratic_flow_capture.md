---
priority: medium
effort: low
depends: []
issue_type: performance
status: Ready
labels: [bash_scripts, performance]
gates: [risk_evaluated]
anchor: 1444
followup_kind: upstream_defect
created_at: 2026-08-07 17:42
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t1444 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/yaml_utils.sh:110-113 — read_yaml_list's flow-list bracket counting (${value//[^\[]/}) is quadratic in the captured value's length: 2.1s at 70KB, 8.3s at 140KB, 34.5s at 324KB. Harmless for real task frontmatter but a latent cliff, and it is what caps t1444's inline test fixture just above pipe capacity instead of at a comfortable multiple.`

## Diagnostic context

`read_yaml_list` captures a flow list by accumulating physical lines into
`$value` and re-counting unbalanced brackets on the **whole accumulated
buffer** after every line:

```bash
opens="${value//[^\[]/}"
closes="${value//[^\]]/}"
depth=$(( ${#opens} - ${#closes} ))
```

Each `${value//…/}` scans the entire buffer, so an N-byte value costs O(N)
per line and O(N^2) overall. Measured on a single-line inline list
(`depends: [...]`), unpatched and patched alike — t1444 did not touch this
loop:

| inline value size | `read_yaml_list ... | wc -l` |
|---|---|
| 70 KB  | 2.1 s |
| 140 KB | 8.3 s |
| 324 KB | 34.5 s |

Real task frontmatter never approaches these sizes, so this is latent rather
than actively breaking. It became visible because t1444's SIGPIPE regression
tests must emit **more than one pipe buffer** (64 KiB on Linux) to make EPIPE
deterministic rather than racy — which lands the inline fixture squarely in
the range where this loop starts costing seconds. t1444 therefore had to size
that one fixture at capacity + ~10% (~2.1s) instead of the 2x margin used for
the other three, and documented the reason inline in
`tests/test_yaml_utils.sh`.

## Suggested fix

Avoid rescanning the accumulated buffer: count brackets on **each incoming
line** and keep a running `depth` (`depth += opens_in_line - closes_in_line`)
rather than recomputing over `$value` every iteration. That makes the capture
linear and leaves the returned value byte-identical.
`join_yaml_flow_lists` has the same shape and should be checked at the same
time — it resets `buffer` per logical line so it is far less exposed, but the
same running-depth form applies.

Guard the change with the characterization pins t1444 added to
`tests/test_yaml_utils.sh` (25 block/inline list shapes) plus a wrapped
multi-line flow-list case, and re-measure the table above to confirm the
timings become linear.
