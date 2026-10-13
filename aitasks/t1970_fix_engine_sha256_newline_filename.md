---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bug]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: upstream_defect
created_at: 2026-10-13 13:05
updated_at: 2026-10-13 13:26
---

## Origin

Spawned from t1967 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/engine_install.sh:79-90` — `engine_sha256` passes the path as an argument to `sha256sum` / `shasum -a 256` and takes `${out%% *}`; a name with a newline or backslash makes the tool escape it with a leading `\`, so the hash fails the `^[0-9a-f]{64}$` validation (fail-closed, returns 1). Same fix as t1967: hash from stdin.

## Diagnostic context

t1967 fixed the identical argument-passing shape in `artifact_sha256` (`.aitask-scripts/lib/artifact_utils.sh`): every hashing tool echoes a name argument back (openssl splits its line on a newline; sha256sum/shasum escape such names as `\<hex>  <escaped-name>`), and option-parses a bare leading `-`. Feeding the file on stdin removes the name from both argv and output. `engine_sha256`'s inputs are framework-managed engine-slot paths under `$AITASKS_HOME`, so this is reachable only through an unusual `AITASKS_HOME` / file name — low priority, but it fails closed and so would block engine verification.

## Suggested fix

`out="$(sha256sum < "$1" 2>/dev/null)"` / `out="$(shasum -a 256 < "$1" 2>/dev/null)"` (output is `<hex>  -`, so `${out%% *}` still works). Add a regression test hashing a newline-named file through each backend — `tests/test_attach_scaffold.sh` Test 1b shows the restricted-PATH per-backend pattern.
