# Active-Gates Materialization Procedure (web-merge Step 5)

Runs at the top of Step 5, after the Step 3 code merge and Step 4 plan copy
succeeded and before attribution/archival — the implementation has landed, so
the tuple write cannot stamp gate suppression onto an unlanded task.

The completion marker's `profile` / `profile_filename` fields record which
execution profile governed the web session. Write the marker JSON (already
read in Step 1) to a temp file if needed, then run the validating helper:

```bash
./.aitask-scripts/aitask_web_merge.sh materialize <task_id> <marker_json_file>
```

Parse the single output line:

- `WEBMAT_SKIP:no-profile` — legacy marker without provenance fields; raw
  `gates:` fallback governs (never guess a profile). Continue.
- `WEBMAT_OK:<status>` — tuple materialized (or already current) under
  exactly the recorded profile file. Continue; if `<status>` is
  `MATERIALIZED_UNCOMMITTED:*` or `NOOP_UNCOMMITTED:*`, warn: "active-gates
  tuple written but not committed — a later `./ait git` commit of `aitasks/`
  picks it up."
- `WEBMAT_INVALID:<reason>` or `WEBMAT_FAIL:<rc>:<output>` — do **NOT**
  continue to archival: a failed re-derivation may leave a previous profile's
  tuple authoritative (the helper's clear is best-effort), so proceeding
  could enforce the wrong gate set. Use `AskUserQuestion`:
  - Question: "Active-gates materialization failed for t\<task_id\>
    (\<reason\>). Retry after fixing, or abort this branch?"
  - Header: "Materialize"
  - Options:
    - "Retry" (description: "Re-run this sub-step after fixing the marker/profile")
    - "Abort this branch" (description: "Code merge stays committed; task stays unarchived — re-run aitask-web-merge later (no-op merge) or repair manually via aitask_gate.sh materialize-active + ait archive")
  Never self-append a gate result to work around the failure.

When the procedure returns with a continue outcome, resume Step 5 (agent
attribution, then the archive script).
