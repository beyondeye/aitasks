---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testmap, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2304
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 23:14
updated_at: 2026-11-16 11:40
---

## Origin

Spawned from t2304 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/shadow_scope.py:224-225` — `dirty_channels()` reads staged/unstaged with porcelain `git diff [--cached] --name-only -z` (rename detection on by default), so a staged rename's old path is missing from the shadow's own dirty channels; same blind spot as t2304, outside `aitask_change_surface.sh`.
- `.aitask-scripts/aitask_change_surface.sh:132,295` — git C-quotes non-ASCII/special paths under the default `core.quotePath` (e.g. `"d\303\251 j\303\240.md"`), so such a path can never equal a plan token or a baseline line and is never attributed `TASK` — even when the plan names it in either form (reported by aitasks_go#t61_1's note on t2304).
- `.aitask-scripts/aitask_change_surface.sh:249` — the plan-token class `[A-Za-z0-9_./-]` excludes `|` (and other legal path bytes), so a plan naming `docs/a|b.md` splits it and the path stays `UNKNOWN` (reported by aitasks_go#t61_1's note on t2304).

## Diagnostic context

t2304 added `--no-renames` to both git reads in `aitask_change_surface.sh` (the
dirty set and pass A's `git show`), so a rename's old path reaches the testmap
intake (`list` → `ait testmap select --changes -`). Reviewing consumers for the
one-extra-path-per-rename effect showed `shadow_scope.claim_baseline` consumes
only `baseline` (now correct), but `shadow_scope.dirty_channels()` does its own
porcelain diff reads with renames on — the same old-path loss. The quoting and
`|` findings came from aitasks_go#t61_1 running the real script on a scratch
repository (its note was advisory; not re-verified in t2304).

Constraint carried from t2304: no new line prefixes — consumers (shadow scope,
docs_updated gate, the testmap engine M4.1 intake) parse `COMMITTED:/TASK:/
OTHER:/UNKNOWN:` and `DIRTY_AT_CLAIM:` as `PREFIX:<path>`. A path containing a
newline cannot be represented in that line grammar at all; decide explicitly
whether to refuse/escape it rather than leave it C-quoted.

## Suggested fix

- shadow_scope: add `--no-renames` to the two `diff` sources in `dirty_channels()`, with a staged-rename test in `tests/test_shadow_scope.sh`.
- change_surface: read with `-z` (or `-c core.quotePath=false`) so paths arrive raw, and widen the plan-token class (or tokenize plans by backtick-delimited spans) so `|` and non-ASCII names can match; test through the real script with a pre-fix control, as t2304 §10 does.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T09:40:21Z status=pass attempt=1 type=human
