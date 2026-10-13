---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bug]
gates: [risk_evaluated]
anchor: 1065
followup_kind: upstream_defect
created_at: 2026-10-13 11:36
updated_at: 2026-10-13 11:36
---

## Origin

Spawned from t1960 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/artifact_utils.sh:36` — `artifact_sha256` dies ("unexpected hash output") on a file whose name contains a newline: `openssl dgst` echoes the file name in its `ALGO(<name>)= <hex>` line, so a newline splits the output and `awk '{print $NF}'` returns a non-hash field. The `sha256sum` / `shasum` fallbacks escape such names (a leading `\` plus `\n`) and parse unreliably as well. It fails closed, never mis-hashes: e.g. `ait artifact create` / attach of such a file dies.

## Diagnostic context

t1960 added regression tests for caller paths ending in a newline to the dir artifact backend (`tests/test_artifact_dir_backend.sh` section G). `artifact_sha256 "nl.dst"$'\n'` returned nothing (it died inside the command substitution), so the test compares bytes with `cmp` instead. The backend's own put/get handle such names correctly. Only the hashing helper does not.

## Suggested fix

Hash from stdin so no tool ever sees the file name: `openssl dgst -sha256 < "$file"` / `sha256sum < "$file"` / `shasum -a 256 < "$file"`. All three print just the hex plus a `-`/`(stdin)` marker, which the existing awk parse handles. Add a regression test that hashes a newline-named file and a file whose name contains spaces.
