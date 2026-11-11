---
priority: medium
effort: low
depends: []
xdeps: [114]
xdeprepo: aitasks_go
issue_type: chore
status: Ready
labels: [go_engine]
created_at: 2026-11-11 19:30
updated_at: 2026-11-11 19:30
---

## Goal

Accept aitasks_go's new YAML module in the public goengines integrity check.
aitasks_go t114 (commit `da80ee4`) moved its YAML dependency from the archived
`gopkg.in/yaml.v3 v3.0.1` to the YAML organization's maintained v3 line,
`go.yaml.in/yaml/v3 v3.0.6`. The change was an import-only rewrite with zero
behaviour change. The next goengines export from aitasks_go that includes t114
will require `go.yaml.in/yaml/v3`, and the current public script refuses it.

## Changes

1. `.github/scripts/goengines_integrity.sh` `CLOSURE_ALLOWED_MODULES` (line 94): swap
   `gopkg.in/yaml.v3` for `go.yaml.in/yaml/v3`. Swap it, do not add it next to the old
   one: aitasks_go's own allowlists (`goengines/guards_test.go` `allowedDeps`,
   `promote/checks.go` `closureAllowlist`) already name only the new module.
2. `tests/test_goengines_export_integrity.sh:483`: the `assert_contains "guards_test.go
   allowedDeps parsed" "gopkg.in/yaml.v3"` expectation becomes `go.yaml.in/yaml/v3`.
3. Check, and change only if needed: lines 406/410 use `gopkg.in/yaml.v3` as an
   arbitrary module in the absolute-`replace` private-deps fixture. Confirm the fixture
   still exercises the refusal once the exported go.mod no longer requires that module.
   Switching it to `go.yaml.in/yaml/v3` keeps it aligned.

## Ordering (important)

Ship this in the **same public commit or PR as the first goengines export whose
source includes aitasks_go t114**, not before and not after. The swap is
mutually exclusive with the old tree:

- the current script rejects a t114 tree;
- the swapped script rejects the current (pre-t114) tree.

So landing the script alone breaks public CI on the current export, and landing
the export alone breaks it on the new one. `promote/export.sh` stages only
`goengines/` and never commits, so commit the script and test edits together with
the staged export.

## Evidence (aitasks_go t114, scratch copies of this repo at `47212a7f`)

`goengines_integrity.sh check --dir <tree>`:
- the current script on the current tree: `INTEGRITY_OK` (control);
- the current script on the tree transformed the t114 way (import rewrite + go.mod
  swap + tidy): `INTEGRITY_FAIL:closure:<target>:ait-testmap:go.yaml.in/yaml/v3 is
  from go.yaml.in/yaml/v3, not on the allowlist` on all four targets (linux/darwin ×
  amd64/arm64). That is the only failure: gofmt, private-deps and independent-build
  pass;
- the script with the swapped allowlist on the t114 tree: `INTEGRITY_OK`;
- the script with the swapped allowlist on the current tree: `INTEGRITY_FAIL:closure`
  on `gopkg.in/yaml.v3`.

## Verification

- `tests/test_goengines_export_integrity.sh` passes.
- On the export PR, `goengines_integrity.sh check` reports `INTEGRITY_OK`.

## Context

This task was split out of t2192 (task-query framework integration), which had
held the public half of t114 as an advisory note. It is self-contained so that it
can land with the next export without waiting on t2192.
