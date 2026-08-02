---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_settings]
anchor: 1223
created_at: 2026-07-28 01:19
updated_at: 2026-07-28 01:19
boardidx: 280
---

## Origin

Spawned from t1223_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_codeagent.sh:74-82` — a malformed `codeagent_config.json`
  is swallowed (`jq … 2>/dev/null` then `|| true`), so `resolve_agent_string`
  falls through to the next layer and exits 0 with a plausible value. A corrupt
  project config is therefore indistinguishable from an absent one at every call
  site. The same swallow applies to the local layer at `:63-71`.
- `aidocs/framework/model_reference_locations.md:67,74` — self-contradicting and
  stale line references: line 67 cites `~540` for the resolution-chain help text
  that actually lives at `aitask_codeagent.sh:645-649`, and line 74 cites `663`
  and the outdated `claudecode/opus4_6` default (now `claudecode/opus5`).

## Diagnostic context

t1223_4 needed a typed `dest_config_unreadable` outcome when pushing settings
into another repo. Reproduced end-to-end: with a destination whose
`codeagent_config.json` is `{not json` and a valid model catalog present,

    METADATA_DIR=<fixture> ./.aitask-scripts/aitask_codeagent.sh resolve pick

prints `AGENT_STRING:claudecode/opus5` and exits **0**. Nothing distinguishes
that from a repo which simply has no project config.

Consequence for t1223_4: trusting the resolver would have made `plan_push`
return `ok`/`noop` against a repo whose config is broken, and then write into
it. It was worked around **in-task** with a strict raw-layer probe in
`lib/cross_repo_settings.py` (`_read_layer`), not fixed at the source, because
changing the resolver's failure behavior affects all ~10 existing callers of
`agent_launch_utils.resolve_agent_string` and belongs in its own change.

Related lossiness found in the same pass (already handled locally, noted for
whoever fixes this): `config_utils._load_json` reports a **directory** at a
config path as `{}` — indistinguishable from absent — and returns `None` for a
file containing `null`.

## Suggested fix

Distinguish "layer absent" from "layer unreadable" in the shell resolver: let
`jq` failure on an existing file surface as a non-zero exit or a distinct
marker line (e.g. `CONFIG_INVALID:<path>`) rather than falling through, and have
`resolve_agent_string` propagate it. Audit the ~10 callers first — several
deliberately want best-effort resolution, so the strict behavior may need to be
opt-in. Fix the two stale references in `model_reference_locations.md` in the
same change.
