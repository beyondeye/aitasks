# Active-Gates Materialization (Step 5 ownership follow-on)

Runs immediately after task ownership is claimed in Step 5 — **ALWAYS** (never
profile-omitted): writing the tuple (even an empty one) is what makes a
declared-but-unrendered gate invisible to every enforcer. With ownership held,
derive and persist the task's enforced gate set under this profile:

```bash
./.aitask-scripts/aitask_gate.sh materialize-active <task_num> --profile aitasks/metadata/profiles/remote.yaml
```

Parse the single stdout line:

- `MATERIALIZED:<csv>` — active set persisted and committed.
  `MATERIALIZED:(empty)` means a fully profile-filtered (or ungated) task —
  that persisted empty set is what makes a declared-but-unrendered gate
  invisible to every enforcer. Continue.
- `MATERIALIZED_UNCOMMITTED:<csv>` — the tuple was written and is enforced
  locally, but the path-scoped git commit failed (e.g. an index lock). Display
  warning: "active-gates tuple written but not committed — other checkouts
  won't see it until the task data is committed." Continue; a later
  `./ait git` commit of `aitasks/` picks it up.
- `NOOP:unchanged` — re-pick under the same profile with unchanged inputs;
  nothing rewritten. Continue.
- `NOOP_UNCOMMITTED:pending-persist` — the tuple is unchanged and enforced
  locally, but the task file still carries changes git refused to commit. Warn
  as for `MATERIALIZED_UNCOMMITTED` and continue.
- Nonzero exit — the re-derivation failed (unreadable/invalid profile, compute
  backend unavailable). The helper clears any previously persisted tuple (its
  stderr says whether the clear succeeded), but the raw-`gates:` fallback is
  only the task's declared intent — it does NOT include this profile's
  `default_gates`, so continuing could silently under-enforce. Display
  "active-gates materialization failed (\<output\>) — fix the profile /
  compute backend and re-run." and trigger the **Abort Procedure**. Do NOT
  proceed to Step 6.
- **Also on stderr (advisory — not part of the stdout status line):** a
  `Warning: materialize-active: active gate '<gate>' has no verifier configured
  in <registry> — it will block archival.` line — or its `… has no registry
  entry in <registry> …` variant — means an **enforced** gate can never be
  satisfied, so the Step 10 archival guard will hold the task in-flight
  indefinitely. The exit status is still 0 and stdout still reports
  `MATERIALIZED:` / `NOOP:`, so **continue** — but **display the warning
  verbatim in the run output** and note that `ait gates sync-registry`
  reconciles the registry. Same warn-and-continue shape as
  `MATERIALIZED_UNCOMMITTED` / `NOOP_UNCOMMITTED` above; the exit-code contract
  is unchanged (a nonzero exit still aborts).

This claim-time materialization mirrors the attended workflow's Step 4: raw
`gates:` stays the task's declared intent, and the persisted `active_gates`
tuple is the enforced set that the Step 9.5 orchestrator and the Step 10
archival guard read. (Gate CLI verb shapes are documented in
`.agents/skills/task-workflow-remote-codex-/gate-cli.md`.)
