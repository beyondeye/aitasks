---
Task: t1041_brainstorm_crew_status_rollup_stale.md
Base branch: main
plan_verified: []
---

# t1041 — Fix stale crew-aggregate `_crew_status.yaml` roll-up

## Context

The crew-aggregate `_crew_status.yaml` (status + progress) lags reality: it reads
`Running` / `80` while the only member agent is `Completed` / `100`. Observed live
in `crew-brainstorm-1017` while diagnosing t1020, which scoped this out (t1020 AC
#4) as an upstream defect in a **separate subsystem** — the agentcrew crew
lifecycle, not the brainstorm operation lifecycle t1020 fixed. Affects all
operation types.

**Root cause.** `_crew_status.yaml` is a *separately persisted* aggregate, and the
only thing that recomputes it is the **runner loop** (per iteration + once on
all-terminal). Once the runner exits (it breaks the moment all currently-known
agents are terminal) or is killed, nothing rolls the aggregate forward when a
member later settles. The brainstorm finalize path (`brainstorm_cli.py:cmd_archive`)
only force-sets `status=Completed` and never touches `progress`. So every reader
of the persisted file can show stale data.

**Fix shape.** Make the aggregate **derived on-read** from member `*_status.yaml`
files at every display/query/lifecycle surface, so staleness is impossible
regardless of runner lifecycle (the task's suggested option 2; structural fix, not
a fragile invariant). In-module precedent: `get_group_status`
(`agentcrew_utils.py:436`) already derives group status from members. Collapse the
three duplicated aggregation implementations onto one canonical Python helper.

## Reviewer concerns — all four confirmed valid, addressed below

1. **Cleanup blocked by stale file (HIGH).** Confirmed: `aitask_crew_cleanup.sh`
   reads `_crew_status.yaml:status` directly (line 96) and emits
   `NOT_TERMINAL:<id>:Running` (99–106) even when members are all `Completed`.
   A fifth reader — and the worst, because it blocks the whole worktree-cleanup
   lifecycle. **→ Addressed (§Bash).**
2. **Killing preservation becomes permanently stale (MED).** Confirmed: naïve
   unconditional preservation of persisted `Killing` would never roll forward if
   the runner dies mid-shutdown. **→ Addressed: gate Killing-preservation on
   runner liveness (`_runner_alive.yaml` status + heartbeat freshness); derive
   once the runner is no longer live.**
3. **All-Aborted incompatible with terminal semantics (MED).** Confirmed:
   `compute_crew_status(["Aborted"])` → `Running`, but cleanup's terminal set is
   `{Completed, Error, Aborted}`. Deriving on-read would otherwise show a settled,
   all-aborted crew as `Running`. **→ Addressed: teach `compute_crew_status` the
   all-terminal case; cleanup uses a direct member-terminal predicate.**
4. **Tests don't prove every stale surface fixed (MED).** **→ Addressed: add a
   Python unit test for the helpers + `list_crews`, and a cleanup regression test
   (`ait crew cleanup --batch` against stale `Running`/80 with completed members,
   and an all-aborted crew).**

### Second review round — all three confirmed, addressed

5. **Wrong timestamp helper name (HIGH).** Confirmed: this module exports
   `_parse_timestamp` (utils:310); `parse_timestamp` is runner-only. `runner_is_live`
   now uses `_parse_timestamp`. **→ §A.3.**
6. **All-aborted as `Completed` is awkward (MED).** Adopted the reviewer's
   preferred option: introduce a real crew-level `Aborted` (already supported by
   `STATUS_COLORS`, the dashboard cleanup gate, and cleanup's terminal set). All
   members aborted → `Aborted`; any Completed in the mix → `Completed`. **→ §A.2.**
7. **Cleanup third field underspecified (LOW).** The predicate is boolean; cleanup
   now emits a **stable** `NOT_TERMINAL:<id>:members_not_terminal` and the test
   asserts it. Existing consumers only prefix-/cid-match, so no contract break.
   **→ §E + Tests.** *(Also caught while addressing this: a member-only predicate
   would regress empty-crew cleanup — fixed with a no-members fallback to persisted
   status, §E.)*
8. **`CREW_STATUSES`/`CREW_TRANSITIONS` drift (LOW footgun).** Adding `Aborted` to
   the state list without updating the transition table would leave them
   inconsistent. Both updated together; no active `validate_crew_transition`
   callers, so not a live bug. **→ §A.2.**

## Current state (verified by reading source)

- Writers of status+progress: `agentcrew_runner.py:recompute_crew_status`
  (645–666, runner-only); `agentcrew_status.py:_recompute_crew_status` (233–256,
  duplicate, fired by `ait crew status set`); `brainstorm_cli.py:cmd_archive`
  (status only); `aitask_crew_init.sh` (initial `Initializing`/0).
- Aggregation triplicated: `compute_crew_status` (utils:97, status only,
  canonical); progress arithmetic duplicated in runner:655 and status:254.
- Readers trusting persisted (stale-able) values: `list_crews` (utils:396–397),
  `agentcrew_dashboard.py:load_crew` (112), `agentcrew_report.py:cmd_summary`
  (80–81), `agentcrew_status.py:cmd_get` (83–85), **and `aitask_crew_cleanup.sh`
  (96, bash)**.
- Already derive-from-members (no change): brainstorm TUI
  (`brainstorm_app.py:_compute_group_progress`) and `get_group_status`. So the
  brainstorm screen was never the stale surface — the agentcrew dashboard/report/
  CLI/cleanup are.
- `_runner_alive.yaml`: `status: running|stopped`, `last_heartbeat`; runner writes
  `stopped` on shutdown (runner.py:791, 954) and heartbeats each iteration (640).

## Implementation

### A. `agentcrew_utils.py` — one canonical rollup helper (+ terminal handling)

1. **Progress + member readers:**
```python
def compute_crew_progress(agent_statuses: list[str]) -> int:
    """Percent of member agents that reached Completed (0 if none)."""
    total = len(agent_statuses)
    if total == 0:
        return 0
    return int(sum(1 for s in agent_statuses if s == "Completed") * 100 / total)


def read_member_statuses(crew_dir: str) -> list[str]:
    """Status of every member agent (skips members with no status)."""
    out = []
    for sf in list_agent_files(crew_dir, "_status.yaml"):
        s = read_yaml(sf).get("status")
        if s:
            out.append(s)
    return out
```

2. **Teach `compute_crew_status` the all-terminal case** (concern 3). Insert
   after the `if status_set & active: return "Running"` branch:
```python
    # All members terminal, no active work. Error already returned above, so
    # the remaining set ⊆ {Completed, Aborted}. A run where every agent was
    # user-aborted is reported "Aborted" (honest); any real Completed output
    # makes it "Completed". Both are terminal → cleanup-eligible, and existing
    # consumers already treat crew-level "Aborted" as terminal (STATUS_COLORS,
    # the dashboard cleanup gate, cleanup's is_terminal_state).
    TERMINAL = {"Completed", "Aborted", "Error"}
    if status_set <= TERMINAL:
        return "Completed" if "Completed" in status_set else "Aborted"
```
   Only changes the previously-undefined all-terminal-non-Completed case (was
   `Running`); all existing branches unchanged. **Add `"Aborted"` to the
   `CREW_STATUSES` list** (utils:22) and a `CREW_STATUS_ABORTED="Aborted"`
   constant to `lib/agentcrew_utils.sh` for symmetry — crew-level `Aborted` is
   now a real (terminal) state. This is the reviewer's preferred resolution over
   mislabelling an all-aborted crew `Completed`; consumers already support it,
   so scope stays contained.

   **Keep `CREW_TRANSITIONS` in sync** (utils:42) — leaving the state list and
   the transition table divergent is a footgun even though
   `validate_crew_transition` has no active callers today. Add `Aborted` as a
   reachable terminal target:
```python
CREW_TRANSITIONS: dict[str, list[str]] = {
    "Initializing": ["Running"],
    "Running": ["Killing", "Paused", "Completed", "Error", "Aborted"],
    "Killing": ["Completed", "Error", "Aborted"],
    "Paused": ["Running", "Killing", "Aborted"],
    # Terminal states
    "Completed": [],
    "Error": [],
    "Aborted": [],
}
```

3. **Runner-liveness gate for Killing** (concern 2):
```python
RUNNER_LIVE_STALE_SECONDS = 180  # ~ a few runner iterations

def runner_is_live(crew_dir: str) -> bool:
    """True iff a runner is actively heartbeating for this crew."""
    p = os.path.join(crew_dir, "_runner_alive.yaml")
    if not os.path.isfile(p):
        return False
    d = read_yaml(p)
    if d.get("status") != "running":
        return False
    hb = _parse_timestamp(str(d.get("last_heartbeat", "")))
    if hb is None:
        return False
    return (datetime.now(timezone.utc) - hb).total_seconds() <= RUNNER_LIVE_STALE_SECONDS
```
   **Note (concern 1):** the timestamp helper in *this* module is
   `_parse_timestamp` (utils:310) — the un-underscored `parse_timestamp` exists
   only in `agentcrew_runner.py`. `datetime`/`timezone` are already imported
   (utils:10). Using the wrong name would `NameError` on the first read of a
   persisted `Killing` crew.

4. **The canonical reader helper:**
```python
def effective_crew_rollup(
    crew_dir: str, persisted_status: str = "", persisted_progress: int = 0
) -> tuple[str, int]:
    """Live (status, progress) for a crew, derived from member status files.

    Fixes a stale persisted `_crew_status.yaml`: with no live runner to
    recompute it, the persisted aggregate lags member state. Readers call this
    instead of trusting persisted fields.

    'Killing' has no member-derivable equivalent (members stay Running during a
    graceful shutdown), so it is preserved ONLY while a runner is actively
    heartbeating; once the runner is gone it is derived from members so it never
    sticks permanently.
    """
    if persisted_status == "Killing" and runner_is_live(crew_dir):
        return persisted_status, persisted_progress
    statuses = read_member_statuses(crew_dir)
    if not statuses:
        return persisted_status or "Initializing", persisted_progress
    return compute_crew_status(statuses), compute_crew_progress(statuses)
```

5. **`list_crews`** (396–397): replace the two literals with
   `effective_crew_rollup(entry_path, status_data.get("status","Unknown"),
   status_data.get("progress",0))`.

### B. Route the Python readers through `effective_crew_rollup`

- `agentcrew_dashboard.py:load_crew` (~112): after building `status_data`,
  override its `status`/`progress` from `effective_crew_rollup(wt, …)` (add the
  import).
- `agentcrew_report.py:cmd_summary` (80–81): derive `crew_status`/`crew_progress`.
- `agentcrew_status.py:cmd_get` (crew-level branch, 78–85): derive before printing
  `CREW_STATUS`/`CREW_PROGRESS`.

### C. Dedupe writers onto `compute_crew_progress` (no behavior change)

- `agentcrew_runner.py:recompute_crew_status` (654–656) and
  `agentcrew_status.py:_recompute_crew_status` (250–254): replace inline progress
  arithmetic with `compute_crew_progress(...)`. (Both already use
  `compute_crew_status` for status; the all-terminal rule from §A.2 now flows to
  the persisted file too, keeping it self-consistent.)

### D. `brainstorm_cli.py:cmd_archive`

When force-setting `status=Completed`, also set `progress=100` (one line) so the
persisted file is never left `Completed`/80.

### E. Bash — cleanup derives terminal from members (concerns 1 + 3)

- **`lib/agentcrew_utils.sh`** — add a member-derived predicate (home of the
  existing bash member-enumeration loop and the `AGENT_STATUS_*` constants):
```bash
# crew_is_terminal <worktree> — true iff the crew has finished. With ≥1 member
# agent: every member must be in a terminal agent state. With NO members: fall
# back to the persisted crew status (mirrors the no-members branch of the Python
# effective_crew_rollup). Mirrors the Python all-terminal rule in
# agentcrew_utils.compute_crew_status (TERMINAL = Completed/Aborted/Error) — keep
# the two terminal sets in sync.
crew_is_terminal() {
    local wt="$1" sf st found=false
    for sf in "$wt"/*_status.yaml; do
        [[ -f "$sf" ]] || continue
        [[ "$(basename "$sf")" == _* ]] && continue   # skip _crew_status.yaml etc.
        found=true
        st="$(read_yaml_field "$sf" "status")"
        case "$st" in
            "$AGENT_STATUS_COMPLETED"|"$AGENT_STATUS_ABORTED"|"$AGENT_STATUS_ERROR") ;;
            *) return 1 ;;
        esac
    done
    if $found; then
        return 0
    fi
    # No member agents — fall back to the persisted crew status (preserves the
    # existing empty-crew cleanup behaviour, e.g. a Completed crew with no agents).
    st="$(read_yaml_field "$wt/_crew_status.yaml" "status" 2>/dev/null)"
    is_terminal_state "$st"
}
```
  **Regression guarded:** `tests/test_crew_report.sh` Test 9 cleans a crew with
  persisted `Completed` but **no member files**. A member-only predicate would
  wrongly refuse it; the no-members fallback to persisted status keeps Test 8
  (Initializing/empty → refuse) and Test 9 (Completed/empty → clean) green while
  fixing the stale-with-members case.
- **`aitask_crew_cleanup.sh:cleanup_crew`** (92–106): replace the
  `read_yaml_field _crew_status.yaml status` + `is_terminal_state "$crew_status"`
  check with `if ! crew_is_terminal "$wt_path"; then …`. Emit a **stable reason**
  in the third field — `NOT_TERMINAL:$cid:members_not_terminal` (concern 3) — and
  update the doc-comment contract at the top of the file. `is_terminal_state` is
  retained (used by the no-members fallback). Consumers are unaffected:
  `aitask_brainstorm_delete.sh:101` prefix-matches `NOT_TERMINAL:*`, and the
  existing report tests assert only the `<cid>` field, not the third.

## Tests (concern 4)

- **NEW `tests/test_agentcrew_rollup.py`** — unit-test the helpers directly:
  `compute_crew_progress`; `compute_crew_status(["Aborted"])` → `Aborted` and
  `compute_crew_status(["Completed","Aborted"])` → `Completed` (all-terminal
  rule); `effective_crew_rollup` over a temp crew dir for
  (a) stale persisted `Running`/80 + member `Completed`/100 → `Completed`/100,
  (b) persisted `Killing` + live `_runner_alive.yaml` → `Killing` preserved,
  (c) persisted `Killing` + stopped/old runner → derived from members,
  (d) no members → persisted preserved; and `list_crews` reflecting the derived
  value for a stale crew.
- **`tests/test_crew_status.sh`** — `ait crew status get` derives `Completed`/100
  from a stale file. **`tests/test_crew_report.sh`** — `ait crew report --batch`
  prints `CREW_STATUS:Completed`/`CREW_PROGRESS:100` for the stale crew.
- **NEW `tests/test_crew_cleanup.sh`** (mirrors `setup_test_repo` from
  `test_crew_status.sh`) — `ait crew cleanup --crew <id> --batch` returns
  `CLEANED` when persisted is stale `Running`/80 but members are all `Completed`;
  `CLEANED` for an all-`Aborted` crew; still `NOT_TERMINAL:<id>:members_not_terminal`
  (assert the full third field) when a member is `Running`; and `CLEANED` for the
  no-member persisted-`Completed` crew (the fallback path, ≈ Test 9). The
  existing Test 8/Test 9 in `test_crew_report.sh` must remain green.

## Verification

- `bash tests/test_crew_status.sh`, `bash tests/test_crew_report.sh`,
  `bash tests/test_crew_cleanup.sh`, and the venv python on
  `tests/test_agentcrew_rollup.py` — all pass.
- Re-run the existing suite touching this code (`test_crew_init.sh`,
  `test_agentcrew_error_recovery.sh`, `test_brainstorm_cli*.{sh,py}`) to confirm
  the `compute_crew_status` all-terminal rule broke nothing.
- Manual: in a live `crew-brainstorm-*` worktree with a `Completed` member and a
  stale `_crew_status.yaml`, `ait crew report` and `ait crew cleanup --crew … `
  both now treat it as `Completed`/cleanable.

## Scope note

The reviewer concerns expanded this from the original CLI-display-only fix into
the cleanup lifecycle path and the `compute_crew_status` terminal semantics —
effort is now **medium**, not low. This is the correct scope: cleanup is the
highest-impact stale reader, and the all-terminal rule is required for derive-on-
read to be coherent. No `compute_crew_status` consumer regresses (the only changed
output is the previously-undefined all-terminal-non-Completed case).

## Post-Implementation

Single parent task on the current branch (profile `fast`) — no worktree merge;
archive via `./.aitask-scripts/aitask_archive.sh 1041` after review/commit
(task-workflow Step 9).

## Risk

### Code-health risk: medium
- The fix touches a shared lifecycle field across six surfaces in two languages
  (Python display/CLI/report + bash cleanup) and changes `compute_crew_status`
  semantics for the all-terminal case, which also flows to the persisted write
  path. Blast radius is bounded (one Python helper, a mirrored bash predicate,
  ~1-line call-site edits) and covered by a unit + two shell regression tests, but
  a missed reader or a member-state combo not exercised by tests could surface a
  surprising aggregate. · severity: medium · → mitigation: TBD
- A second "terminal" definition now lives in bash (`crew_is_terminal`) mirroring
  the Python `TERMINAL` set — an inherent cross-language duplication (the bash lib
  already mirrors `AGENT_STATUS_*`). Guarded with an inline sync comment, but the
  two sets could drift. · severity: low · → mitigation: TBD
- The Killing runner-liveness gate adds a time-based heuristic
  (`RUNNER_LIVE_STALE_SECONDS`); too short briefly hides `Killing` during an
  active kill, too long briefly shows stale `Killing` after a runner death — a
  display-only transient, self-correcting. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Targets the exact observed failure (stale persisted aggregate vs. live members)
  at every display, query, and lifecycle surface, and resolves all four reviewer
  concerns with member-derived sources of truth. Verified by a stale-terminal
  regression test on the previously-failing reads, including cleanup.
  · severity: low · → mitigation: TBD
