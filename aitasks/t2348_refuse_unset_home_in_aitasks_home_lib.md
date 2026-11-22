---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [brainstorm]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
created_at: 2026-11-22 18:45
updated_at: 2026-11-22 19:16
---

## Origin

Spawned from t2347 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/aitasks_home.sh:19 — AITASKS_HOME default expands $HOME at source time, so aitask_engine.sh / aitask_testmap.sh abort with a raw "HOME: unbound variable" when HOME is unset (an empty HOME instead yields a root-level /.aitasks); it should refuse clearly, as aitask_setup.sh now does, rather than default to empty`

## Diagnostic context

t2347 made `lib/python_resolve.sh`, `lib/aitask_path.sh` and `ait`'s update
check tolerate an unset/empty HOME under `set -u`, and made `aitask_setup.sh`
refuse one (an empty HOME let setup derive root-level / empty install paths,
e.g. `rm -f /bin/python` in its PyPy fallback cleanup). An isolated sweep
(`env -i PATH=/usr/bin:/bin AIT_PYTHON=… bash <script> --help` over a scratch
copy outside any git repo) then left one library-level crash:
`lib/aitasks_home.sh:19`, `export AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"`,
reached by `aitask_engine.sh` and `aitask_testmap.sh`.

It was deliberately NOT given the `${HOME:+…}` treatment: AITASKS_HOME is the
engine's install / prune / migrate root, so an empty value would turn
`$AITASKS_HOME/engine/...` into `/engine/...`. An explicit `AITASKS_HOME`
already works without HOME.

## Suggested fix

When `AITASKS_HOME` is unset and HOME is unset or empty, fail with a clear
message naming both variables (the caller can set `AITASKS_HOME`), instead of an
unbound-variable abort or a root-level default. Check every sourcer (testmap
shim, install_engine_binary / aitask_engine.sh, gate verifiers, aitask_test.sh,
aitask_setup.sh) for how a sourcing-time refusal propagates. `aitask_setup.sh`
already refuses earlier. Gate verifiers may need a structured status rather than
an exit. Cover it with an `env -i` test like
`tests/test_python_resolve_unset_home.sh`.
