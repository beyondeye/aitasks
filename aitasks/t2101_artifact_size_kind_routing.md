---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-10-21 14:51
updated_at: 2026-10-21 14:51
---

## Context

Decided in t1890 (`aidocs/artifact_storage_lifecycle.md`, D2 and §4): route by
size and kind so that small text artifacts (trails, HTML plans) stay on the data
branch, where they belong to the audit history, while binary or large content
goes to a configured large-data backend. **Today** `create` uses
`artifacts.default_backend` or `--backend` for everything
(`aitask_artifact.sh`, `create` ~L400-460). The manifest records a **single
`backend` for all versions** (`lib/artifact_manifest.py` schema, `set-backend`),
and `update` resolves that backend (~L520-565). `move` copies every version
(~L570-692).

## Scope

1. New keys in `project_config.yaml`: `artifacts.large_backend` (unset by
   default; must name a registered backend) and `artifacts.large_threshold_mb`
   (default `1`), validated in `lib/artifact_registry.py`. Add commented
   examples to `seed/project_config.yaml`.
2. **Routing happens at creation only**, with one precedence contract (design
   doc §4), highest first:
   1. an explicit `--backend`;
   2. `large_backend`, when it is set and the content is over the threshold or
      binary (a NUL byte in the first 8 KiB, git's heuristic);
   3. `default_backend` (unset means `local`, the data branch) for everything
      else. Large content also goes there when `large_backend` is unset, with a
      warning once per command.

   "Small text stays on the data branch" is the outcome under the shipped
   default, not a separate rule. A configured non-local `default_backend` keeps
   receiving small content; routing never overrides it.
3. **`update` always keeps the artifact's existing backend.** A manifest has one
   backend for all versions, so routing only the new bytes would break the model.
   When the update's content crosses the threshold, or is binary, on a non-large
   backend, it warns and names `ait artifact move <handle> --to <large_backend>`.
   Nothing moves automatically.
4. Keep the existing size cap (`artifact_max_size_mb`, default 25) unchanged and
   independent.

## Acceptance criteria / verification (tests in `tests/`)

- Routing: a small text file goes to the default backend; an over-threshold file
  and a binary file go to `large_backend`.
- Override precedence: `--backend local` beats routing.
- The warning when `large_backend` is unset.
- **Threshold-crossing update**:
  1. Create a small artifact on `local`, then update it with over-threshold
     content.
  2. Assert the backend is unchanged and the warning names the `move` command.
  3. Assert both the current and the historical version are retrievable with
     `get`.
  4. Run `move --to <large_backend>` and assert both versions are still
     retrievable, now from the new backend.
- **Non-local default**: with `default_backend: dir` and `large_backend:
  gitbranch`, small text goes to `dir` and large or binary content to
  `gitbranch`. With `large_backend` unset, large content goes to `dir` with the
  warning.
- An invalid `large_backend` (unregistered) is refused at activation.

## Docs

- `website/content/docs/commands/artifact.md` configuration table: both keys and
  the routing rule (creation only, update keeps the backend).
- `concepts/artifacts.md`: one paragraph.
- Run `check_links.py`.

Attachments get the same routing through t1258; do not change `ait attach` here.
