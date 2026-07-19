---
Task: t635_33_gate_activation_render_time.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_24_*, t635_28_*, t635_30_*, t635_31_*, t635_34_*
Archived Sibling Plans: aiplans/archived/p635/p635_14_profile_gate_declaration_unification.md
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-19 08:25
---

# t635_33 — Gate activation at render time (+ folded t635_25)

## Context

Gate integration into task-workflow is too rigid. t635_14 retired the
render-time `{% if %}` risk toggle in favour of a `default_gates` profile key +
**runtime checks present in every rendered profile** — so `default`'s rendered
`SKILL.md` grew ~717→766 lines for machinery it previously rendered nothing for.
This task recovers render-time leanness **without** regressing t635_14's
single-source resolution, and closes the correctness hole that render-time
omission would otherwise open (t1147 via profile filtering).

**Model 1 (user-confirmed): the profile renders the ceiling; the task selects
within it at runtime.** A profile declares a render-time gate set; lean profiles
render no gate machinery. The task `gates:` narrows within it at runtime.

**Central risk (user: "be very careful"):** a task's `gates:` may declare a gate
the profile did NOT render. Today's enforcers read the task's literal `gates:`
directly, so a declared-but-unrendered gate would block archival with no machinery
to satisfy it. The fix: persist a profile-filtered **`active_gates`** set that
**every** enforcer consumes, so a filtered gate is invisible everywhere (render
AND enforcement) in lockstep.

**Resolved decisions (this planning session):**
- Ceiling = new `rendered_gates` profile key, defaulting to `default_gates` when
  unset (existing profiles need no new key).
- Absorbed t1147 reconcile scope split out to sibling **t635_34** (`depends: [t635_33]`).
- **t635_25 folded in** — call-shape verbs (`active`, encapsulated materialize,
  pure-bash decision verbs) land here since the `active_gates` rewrite touches the
  same call sites.
- Carve-out follow-ups (from the design stress-test): **remote/web lane
  materialization** and **the divergent `task-workflown`/pickn tree** — created
  as separate t635 siblings during implementation (separate render trees +
  goldens; folding them in balloons blast radius).

**Verification pass (2026-07-19, pre-implementation re-pick):** all source
anchors re-checked against main — zero drift (no commits touched any anchor file
since 2026-07-16). Three anchor corrections folded in below: the merge script is
`.aitask-scripts/board/aitask_merge.py` (not `.aitask-scripts/aitask_merge.py`);
the t1156 creation sink is `filter_gates_for_issue_type` at
`aitask_create.sh:1962-1965`; minor gate_ledger.py line drift in the site table.
Confirmed unimplemented: no `active_gates` code, no `rendered_gates` key
anywhere, no `active`/`materialize-active`/`active-gates-status` verbs;
`tests/test_gate_active_gates.sh` absent; t635_35/36 not yet created (highest
child t635_34); task-workflow authoring sources are plain `.md` with embedded
Jinja (`planning.md`, `SKILL.md`), not `.md.j2`.

## Design

### The single definition (rendered vs active)
- `rendered_set(profile)` = `profile.rendered_gates` **if the key is present**
  (even `[]` — an explicit render-nothing override), else `profile.default_gates`
  if present, else `[]`. **Key-presence, NOT truthiness** — an `or`-chain would
  make an explicit `rendered_gates: []` fall back to a nonempty `default_gates`
  and render machinery the profile disabled. Same semantics in ALL three compute
  paths (render context, Python `compute_active_gates`, bash `active` verb), with
  a dedicated test: `rendered_gates: []` + `default_gates: [risk_evaluated]` →
  renders nothing, active set empty. Drives **render-time** omission.
- `resolve(task.gates, profile.default_gates)` = task's literal `gates:` if the
  key is present (even `[]`, an opt-out), else `profile.default_gates`.
- `active_gates(task, profile)` = `resolve(...) ∩ rendered_set(profile)`. Drives
  **runtime** enforcement. Persisted on the task at claim.

### New per-task frontmatter (derived state — a mandatory atomic tuple)
- `active_gates: [..]` — profile-filtered effective set (list; may be `[]`).
- `active_gates_filtered: [..]` — the gates the profile ceiling REMOVED:
  `resolve(task.gates, default_gates) − active_gates` (usually `[]`). Persisted so
  no-profile readers can distinguish "declared-but-filtered" from "independent"
  gates (consumed by dependency-unblock below) and so the optional
  "skipped: execution profile" notice has an audit source.
- `active_gates_profile: <name>` — provenance stamp (producing profile).
- `active_gates_digest: <gates_hash>.<profile_hash>.<outputs_hash>` —
  **mandatory, not optional**: a three-part digest covering ALL resolve inputs
  AND the stored outputs. The `gates`-half covers the raw `gates:` field state
  (present/absent + content) — verifiable by a reader WITHOUT a profile (detects
  a same-profile manual `gates:` edit). The `profile`-half covers **both**
  profile inputs, `default_gates` ⊕ `rendered_set` — `default_gates` is a
  resolve input for any task without an explicit `gates:` field, so a
  `default_gates` edit under an unchanged `rendered_gates` must still change the
  digest; verified wherever a profile is in scope (Step 4 / materialize /
  `active-gates-status`). The `outputs`-half hashes the stored
  `active_gates` ⊕ `active_gates_filtered` values themselves — also verifiable
  WITHOUT a profile — so a hand-edited or partially-updated active set is
  detected as corrupt rather than trusted (input-only authentication would let a
  corrupted output pass while `gates:` is unchanged, silently under-enforcing).

**Governance model (explicit): claim-time snapshot.** Profile configuration is
snapshot into the tuple at materialization; enforcement between picks follows
the snapshot. A profile edit takes effect at the next materialization (any
pick/re-pick), and is *detectable* earlier wherever a profile is in scope
(`active-gates-status` → STALE). This is deliberate: enforcement paths with no
live profile (dependency-unblock, board, `ait gates run`) must never guess at
"live" profile state they cannot see.

**Manual-verification carve-out (t1156 — landed, must not regress).** t1156
strips unreachable gates at the *creation* sink (via
`filter_gates_for_issue_type`, `aitask_create.sh:1962-1965`), leaving `gates:`
absent on `manual_verification` tasks — and those tasks DO reach Step 4 (Check 3
runs ownership before dispatch), so an unguarded materialize would resolve
profile `default_gates` and stamp `risk_evaluated` right back.
`materialize-active` therefore applies the same issue-type rule at the
materialize sink: for `issue_type: manual_verification`, intersect the resolved
set with the shared allowlist `MANUAL_VERIFICATION_REACHABLE_GATES`
(`lib/task_utils.sh:262` — single source, same constant t1156's creation sink
uses). ONE compute path (`cmd_compute_active`) is shared by `materialize-active`
and `active-gates-status` so freshness comparison applies the identical rule.
Test: an MV task under `fast` materializes WITHOUT `risk_evaluated` and stays
archivable.

**Atomicity — enforced at the CLI, not by convention:** the four fields are
written together in ONE `aitask_update.sh` call (single frontmatter rewrite,
single `updated_at` bump). `aitask_update.sh` **hard-rejects** any invocation
passing a strict subset of the four tuple flags (all four or none — nonzero
exit, file untouched), so a partial update cannot produce a mixed tuple in the
first place; the outputs-hash then catches any corruption that bypasses the CLI
(direct file edit). Tests: partial-flag invocation → rejected, zero diff;
hand-edited `active_gates` value → outputs-half mismatch → readers fall back
conservatively. **Fail-closed staleness rule:** every reader validates the
`gates:`-half of the digest against the task's current raw `gates:`; on mismatch
(the field was edited after materialization) the tuple is treated as **absent** —
raw-`gates:` fallback governs. That is conservative in the enforcement direction
(the newly declared intent is enforced; a filtered gate may over-block until the
next pick re-materializes — and the archival-guard message says so: "stale
active_gates — re-pick or run materialize-active"). It can never silently
under-enforce or keep enforcing a set computed from inputs that no longer exist.
Profile-content drift under the same name is caught at every claim (materialize
recomputes the full digest) and by `active-gates-status` wherever a profile is
in scope. **Merge rule — grouped presence/deletion semantics:** the tuple moves
as a UNIT — `board/aitask_merge.py` resolves the four fields as one group, taking
the newer-`updated_at` side's tuple STATE wholesale, **including absence**: if the
newer side legitimately has no tuple and the older side has one, the merged
result has NO tuple (generic per-field one-sided preservation would resurrect
the obsolete snapshot). Never mixes sides. Tests cover: both-present with
different materializations → winner's tuple intact; **newer-absent vs
older-present in BOTH local/remote orientations → merged output has no tuple**.

Raw `gates:` stays **declared intent**; `active_gates` is the enforced set.

### Materialization (claim-time, profile-aware)
`aitask_pick_own.sh` has no profile in scope, so materialization lives in the
skill's **Step 4** (which knows `active_profile_filename`), via a new helper:

```
aitask_gate.sh materialize-active <task_id> [--profile <file>]
  → writes the four-field tuple (active_gates, active_gates_filtered,
    active_gates_profile, active_gates_digest); prints ONE line
    MATERIALIZED:<csv>  (or MATERIALIZED:(empty) / NOOP:unchanged)
```
- **Always runs** (even for lean profiles): writing `active_gates: []` is the
  safety valve that neutralizes a declared-but-unrendered gate — this is what makes
  a filtered gate invisible to enforcers. **Never Jinja-omitted.**
- Re-materialized on every re-pick (Step 4 runs on re-entry too → "re-derive under
  the CURRENT profile" is free).
- **Replaces** the Step-7 `gates:` backfill (folded t635_25's "move backfill to
  Step 4"): with `active_gates` materialized before planning, every downstream site
  is a plain task-state read (no `--profile` fallback).
- **Error path (no resolvable profile): fail clearly, write nothing.** If
  `--profile` is missing or the file is unreadable, exit nonzero with a clear
  message and leave the derived tuple **absent** — the read-only raw-`gates:`
  fallback governs. Never persist raw gates as an authoritative active set without
  knowing what machinery was rendered (that would recreate the unsatisfiable-gate
  bug this task exists to prevent). In the skill, Step 4 only calls it when
  `active_profile_filename` is set; a manual/resume invocation without a profile
  skips the call (staleness notice still applies).
- **Idempotent + serialized.** Read-compare-write: when the computed tuple equals
  the persisted one, print `NOOP:unchanged` and do NOT rewrite the file, bump
  `updated_at`, or create a commit (a re-pick under the same profile is a no-op).
  The whole read-compute-write transaction runs under the existing per-task gate
  mutex `acquire_gate_lock` (`aitask_gate.sh:71`, mkdir-based — the same lock
  the ledger appenders take), so a whole-file rewrite can never interleave with a
  concurrent `append`. Tests: unchanged re-pick → `NOOP:unchanged`, zero diff;
  materialize racing a concurrent append → both effects land.

### Enforcement seam — ONE validated tuple reader, swapped at EVERY enforcer
`lib/gate_ledger.py` — a single reader returns BOTH tuple fields plus validity,
so no consumer can read `active_gates` and `active_gates_filtered` under
different validity conclusions:

```python
def read_active_tuple_from_text(text) -> tuple[list[str], list[str], bool]:
    """(active, filtered, tuple_valid). ALL consumers go through this."""
    if _frontmatter_has_key(text, "active_gates"):
        if _digest_profileless_halves_match(text):   # gates-half AND outputs-half
            return (_read_frontmatter_list_from_text(text, "active_gates"),
                    _read_frontmatter_list_from_text(text, "active_gates_filtered"),
                    True)                             # authoritative, even []
        # stale (gates: edited) or corrupt (outputs edited) → tuple treated as absent
    return (read_declared_gates_from_text(text), [], False)  # backward-compat fallback

def read_active_gates_from_text(text):               # convenience for set-only sites
    return read_active_tuple_from_text(text)[0]
```

An invalid tuple yields `filtered = []`, so the `also_blocks_dependents`
subtraction below degrades to "unfiltered" (today's behavior) in the SAME
decision that falls `active_gates` back to raw intent — the two fields can never
disagree about staleness (a stale filtered list must not keep removing a
newly-declared blocker after `active_gates` already fell back).

**`also_blocks_dependents`: remove filtered duplicates, keep independent
blockers.** `required_unblock_gates()` (gate_ledger.py:640-651) appends every raw
`also_blocks_dependents` entry unconditionally — a profile-filtered gate listed
there would stay BLOCKED and break "filtered gates are invisible everywhere".
But a blanket intersection with `active_gates` would ALSO drop legitimate
**independent** blockers — `also` may name gates NOT in the declared set (e.g. a
checkpoint gate like `merge_approved`, recorded by `record_gates` machinery and
intentionally holding dependents). Correct semantics in `dependents_status`:

```python
active, filtered, _valid = read_active_tuple_from_text(text)   # ONE validated read
also_effective = [g for g in also if g not in filtered]
```

i.e. drop exactly the **declared-but-filtered** gates (the persisted
`active_gates_filtered` field, obtained through the validated tuple reader — no
profile needed at read time); keep every independent addition (today's
semantics). Tuple absent OR invalid → `filtered = []` → `also` unfiltered
(today's behavior, in lockstep with the `active_gates` fallback). Negative-control gains BOTH cases: (i)
`also_blocks_dependents: [risk_evaluated]` on a task whose profile filtered
`risk_evaluated` → dependents unblock; (ii) `also_blocks_dependents:
[merge_approved]` (not declared, not filtered) → dependents still BLOCKED until
it passes.
Swap raw-`gates:` reads → `read_active_gates_from_text` at ALL enforce/schedule/
record sites (the stress-test found 9, not 4; line anchors re-verified
2026-07-19):

| Site | File:line | Role |
|---|---|---|
| `should_self_record` | gate_ledger.py:445 | **P0** Step-7 self-record decision (else double-record returns) |
| `dependents_status` | gate_ledger.py:665 | dependency-unblock |
| `unmet_procedure_gates` | gate_ledger.py:695 | procedure-gate dispatch |
| `archive_status_from_text` | gate_ledger.py:735 | archival guard (via `archive-ready`→`aitask_archive.sh gate_guard`) |
| `read_task_gate_state` | gate_ledger.py:785 | board + monitor archive/deps decisions — **including the decision summaries**: `_has_failed_gate` (aitask_board.py:819-822) and the compact status/human-pending summaries scan ALL `state.current` ledger entries, so a failed historical run of a now-filtered gate would still classify "failed gate" / show pending. Filter every *decision* surface to the active set; historical runs of inactive gates stay visible **audit-only** (status text), never drive a classification. Board/monitor tests included. |
| `unlocked()` | gate_orchestrator.py:537 | `ait gates unlocked` engine scheduling |
| `_read_state` | gate_orchestrator.py:367 | `ait gates run` |
| `format_list` | gate_ledger.py:619 | `aitask_gate.sh list` — **decided: stays on the DECLARED set** (it is the declared-intent introspection verb, per t635_14). The enforced set is displayed by `active-gates-status` (prints the full tuple + freshness). The gate-CLI contract doc states the distinction explicitly: `list` = declared intent, `active-gates-status` = enforced active set. |
| decision verbs | aitask_gate.sh | `active` / `should-self-record` read active set |

Fallback: task with `active_gates` present → authoritative (filtered gate
invisible); task without it (pre-migration / never claimed) → reads raw `gates:` =
today's behavior. **Document the pre-claim invariant** (P1-2): before Step 4 the
fallback to raw `gates:` is intentionally conservative — an unclaimed dependency
has no passing gates either way, so `deps-unblock` at `aitask_ls.sh:192` never
wrongly satisfies. No fix needed there beyond the grep below.

### `aitask_ls.sh` candidate grep (P0-4)
`build_dep_satisfied_set` (aitask_ls.sh:172; grep at :177) greps
`^(gates|also_blocks_dependents):` to pick candidates. Since gates now come via
`active_gates` (no `gates:` backfill), add it:
`^(gates|active_gates|also_blocks_dependents):` — else a profile-default
gate task is never evaluated and the `dependents_status` swap is moot.

### CLI verbs (folded t635_25, retargeted to active_gates)
`aitask_gate.sh`:
- `active <id> <gate>` → exit 0 if gate ∈ active set. **Pure-bash** (reuse
  `cmd_list`'s `read_yaml_list`/awk path — no python-availability ambiguity), and
  replicate the `active_gates`-present-else-`gates:` fallback so it agrees with the
  Python enforcers on unclaimed tasks. Used by the planning producer trigger +
  risk-section guard, replacing `effective-gates | grep`.
- `materialize-active <id> [--profile <f>]` — the action verb above (compute+write
  +path-scoped commit; honors the encapsulate-bash convention; unit-tested).
- `active-gates-status <id> [--profile <f>]` → `FRESH` / `STALE:<stamped>→<current>`
  — provenance/staleness checker; surfaced as a Step-4 pick-time notice (cheap: the
  profile is already in scope) and optionally a board badge.
- Keep `effective-gates` / `list` for introspection/debug.
- Document the gate-CLI contract once (decision verbs → exit codes; action verbs →
  do-and-print-one-line): extend `gate-recording.md` or a new `gate-cli.md`.

### Render-time omission (minijinja, strict undefined)
**P0-2 — inject `rendered_set` into the render context**, do NOT rely on `{% set %}`
(it does not cross `{% include %}`, which planning.md uses). In
`skill_template.py` `render_skill` (def :110, render call :122), compute and pass:
```python
# Key-presence, not truthiness: an explicit rendered_gates: [] must NOT fall
# back to default_gates (it is the profile's render-nothing override).
if "rendered_gates" in profile:
    rendered_set = profile["rendered_gates"] or []
else:
    rendered_set = profile.get("default_gates") or []
env.render_str(template_source, profile=profile, agent=agent_name, rendered_set=rendered_set)
```
Then gate the RISK PRODUCER machinery in `.claude/skills/task-workflow/{planning.md,
SKILL.md}` with `{% if 'risk_evaluated' in rendered_set %} … {% endif %}`:
- planning.md §6.1 risk-gate check + risk sub-steps + risk-section guard;
- SKILL.md Step-7 risk self-record + Step-7 risk-mitigation "before" + Step 8d "after".

**Always rendered** (never gated): the Step-4 `materialize-active` call. The existing
`{% if profile.record_gates %}` blocks stay as-is (orthogonal — human/integration
checkpoint recording).

### Profile YAML + editor registration
No YAML change for current behavior (`rendered_gates` defaults to `default_gates`):
`fast` renders `[risk_evaluated]`; `default`/`remote` render none. Document
`rendered_gates` in `profiles.md`. (Explicit `rendered_gates: []` on `remote.yaml`
lands with the remote-lane follow-up.) **Register `rendered_gates` in
`profile_editor.py`** (the t635_14 `default_gates` pattern): `PROFILE_SCHEMA`
entry (`list` type), `PROFILE_FIELD_INFO` help text (short: "Render ceiling —
gate machinery rendered into this profile's task-workflow"; long: key-presence
semantics incl. the explicit-`[]` override and the `default_gates` fallback),
"Gates" `PROFILE_FIELD_GROUPS` entry, and a round-trip test (set/serialize/load,
including `rendered_gates: []` surviving the editor round-trip).

## Implementation steps

0. **Create the two follow-up siblings FIRST** (t635_35 remote/web lane
   materialization, t635_36 task-workflown/pickn migration — see Follow-up
   tasks below), both `depends: [635_33]`, via the Batch Task Creation
   Procedure. The Step-8 review checklist verifies they exist.
1. **`lib/gate_ledger.py`** — add `read_active_tuple_from_text` (the single
   validated reader: gates-half + outputs-half digest checks, returns
   `(active, filtered, valid)`) with the `read_active_gates_from_text`
   convenience wrapper, `_digest_profileless_halves_match`,
   `_read_profile_rendered_gates` (key-presence fallback to `default_gates`),
   `compute_active_gates(task_text, profile_file)` (key-presence semantics), a
   staleness comparator; swap the 6 gate_ledger sites
   (445/619[doc-only — stays declared]/665/695/735/785); in `dependents_status`,
   drop declared-but-filtered entries from `also_blocks_dependents` via the
   tuple reader's `filtered` (keep independent blockers).
2. **`lib/gate_orchestrator.py`** — swap `_read_state:367` and `unlocked():537`.
3. **`lib/skill_template.py`** — inject `rendered_set` into the render context (P0-2).
4. **`aitask_gate.sh`** — new `active` / `materialize-active` / `active-gates-status`;
   pure-bash decision path for `active`/`has-gates-field`/`should-self-record`;
   dispatch + help. `materialize-active`: atomic-tuple write, hard-fail on
   unresolvable profile (no write), `NOOP:unchanged` read-compare-write, entire
   transaction under `acquire_gate_lock` (`:71`), t1156 issue-type allowlist
   applied via the shared `MANUAL_VERIFICATION_REACHABLE_GATES`
   (`lib/task_utils.sh:262`) in the single `cmd_compute_active` path shared with
   `active-gates-status`.
4b. **`lib/profile_editor.py`** — register `rendered_gates` (schema `list`, help
   text, "Gates" group) + editor round-trip test incl. explicit `[]`.
5. **`aitask_ls.sh:177`** — add `active_gates` to the candidate grep.
6. **Frontmatter field plumbing (the four-field `active_gates*` tuple)** per
   `aidocs/framework/aitasks_extension_points.md`:
   - `aitask_update.sh` — `--active-gates` / `--active-gates-filtered` /
     `--active-gates-profile` / `--active-gates-digest` writers, with a
     **hard-enforced all-or-nothing rule**: passing a strict subset of the four
     tuple flags is a usage error (nonzero exit, file untouched) — atomicity is
     CLI-enforced, not a caller convention + `write_task_file`
     field set. **CRITICAL —
     presence-tracked emission, NOT the `gates:` pattern:** `write_task_file`
     emits `gates:` only when non-empty (`aitask_update.sh:620-626` — "never emit
     `[]`"), so reusing that plumbing would silently DROP the load-bearing
     `active_gates: []` on any unrelated rewrite → field absent → raw-`gates:`
     fallback → a filtered task converts back into a gated task. Track field
     presence with a separate flag (mirror `BATCH_*_SET`) and always emit
     `active_gates: []` when the tuple is present. **Round-trip tests:** explicit
     empty tuple survives an unrelated `ait update` (e.g. `--priority`), a rename,
     a merge, and a fold.
   - `board/aitask_merge.py` `merge_frontmatter()` (def :156) — **grouped
     presence/deletion semantics**: the four tuple fields resolve as ONE group
     to the newer-`updated_at` side's state, including absence
     (newer-side-no-tuple deletes; generic one-sided preservation would
     resurrect an obsolete snapshot); never mix sides (a mixed tuple has
     inconsistent provenance); keep `active_gates` OUT of `_LIST_UNION_FIELDS`
     (:129 — computed replace-all, like `gates`); add to the key-order emit
     (~:434/:437). Tests: both-present different → winner tuple; newer-absent
     vs older-present in both local/remote orientations → no tuple.
   - `aitask_fold_mark.sh` — no-op; **must NOT union `active_gates`** (recomputed at
     next claim; unioning would corrupt it). Fold must also preserve an explicit
     empty tuple (round-trip test above).
   - `aitask_board.py` — read-only display of `active_gates` (low priority; ensure
     not dropped). Extend `TaskGateState` (gate_ledger.py:115) if the board should
     show the active set.
   - Docs: `task-format.md`, `CLAUDE.md`, seed instructions + AGENTS.md mirror,
     `task-creation-batch.md` — mark both as framework-derived, not user-authored.
7. **Skill closures** (`.claude/skills/task-workflow/` — plain `.md` sources with
   embedded Jinja):
   - `SKILL.md` Step 4 — always-rendered `materialize-active` call after ownership +
     optional `active-gates-status` staleness notice.
   - `planning.md` §6.1 — producer trigger + risk-section guard use `active <id>
     risk_evaluated`, wrapped in `{% if 'risk_evaluated' in rendered_set %}`.
   - `SKILL.md` Step 7 — remove the inline backfill bash (→ Step-4 materialize);
     Jinja-gate the risk self-record + risk-mitigation "before"; Step 8d "after".
   - `gate-recording.md` / new `gate-cli.md` — CLI contract reference.
8. **Rerender + goldens** — `aitask_skill_rerender.sh` all profiles × 3 agent trees;
   regenerate `tests/golden/procs/task-workflow/` + `tests/golden/skills/` and the 9
   caller skills' per-profile goldens; run `aitask_skill_verify.sh`.

## Tests

- **New `tests/test_gate_active_gates.sh`** (real `aitask_gate.sh`, fixture cwd +
  `TASK_DIR`):
  - `materialize-active`: `gates:[risk_evaluated]` under fast (rendered
    `[risk_evaluated]`) → `active_gates:[risk_evaluated]` + profile stamp + digest
    (one atomic write); SAME task under default (rendered `[]`) → `active_gates:[]`;
    opt-out `gates:[]` → `[]`; no `gates:` + default → `[]`; **no-profile /
    unreadable profile → nonzero exit, clear message, NOTHING written** (tuple
    stays absent; raw fallback governs reads); **`rendered_gates: []` +
    `default_gates: [risk_evaluated]` → active `[]`** (key-presence, no
    truthiness fallback); **unchanged re-pick → `NOOP:unchanged`**, zero file
    diff, no commit; **concurrent `append` during materialize → both effects
    land** (shared `acquire_gate_lock`); **manual_verification task under fast →
    active set has NO `risk_evaluated`** (t1156 allowlist applied at the
    materialize sink) and `archive-ready` stays satisfiable; **profile
    `default_gates` edit (unchanged `rendered_gates`, task without `gates:`) →
    digest profile-half mismatch → STALE** (concern-3 case).
  - `active`: exit 0/1 over active set; pre-claim fallback to raw `gates:`;
    agrees with the Python reader on the digest-mismatch (stale) case.
  - `active-gates-status`: FRESH when stamp+digest match; STALE after a profile
    switch; STALE after a manual `gates:` edit under the SAME profile name
    (gates-half digest mismatch) — and the enforcers then fall back to raw
    `gates:` (fail-closed), verified via `archive-ready` **AND via
    `deps-unblock`: after the raw `gates:` edit adds a blocker also named in
    `also_blocks_dependents`, the STALE tuple's `active_gates_filtered` is
    ignored — the newly declared blocker still blocks** (single validated
    tuple reader; the two fields cannot disagree about staleness).
  - **Tuple integrity**: `aitask_update.sh` with a strict subset of the four
    tuple flags → rejected (nonzero exit, zero diff); a direct hand-edit of the
    `active_gates` value (bypassing the CLI) → outputs-half digest mismatch →
    readers fall back to raw `gates:` conservatively (verified via
    `archive-ready`), never trusting the corrupted set.
  - **Tuple durability round-trip**: explicit `active_gates: []` tuple survives an
    unrelated `ait update --priority`, a rename, a merge, and a fold — never
    silently dropped back to the raw-gates fallback.
  - **Merge group semantics**: both-present different materializations → winner's
    tuple intact; newer-absent vs older-present (both local/remote orientations)
    → merged output has NO tuple (no resurrection).
- **Negative-control (must-have)** — task `gates:[risk_evaluated]` materialized under
  **default** (empty rendered set → `active_gates:[]`): assert (a) the
  default-rendered planning.md/SKILL.md contain NO risk producer machinery, (b)
  `archive-ready` → NO_GATES (archives), (c) `deps-unblock` → NO_GATES (dependents
  unblock), (d) **`also_blocks_dependents: [risk_evaluated]` on the same task
  still unblocks dependents** (declared-but-filtered entries dropped via
  `active_gates_filtered`) **while `also_blocks_dependents: [merge_approved]`
  (independent, not declared) still BLOCKS** until it passes, (e)
  **board/monitor decision surfaces**: a failed historical
  `risk_evaluated` run on the filtered task does NOT classify it "failed gate"
  (audit-only in status text). SAME task under **fast** → enforced
  (`archive-ready` BLOCKED until `risk_evaluated` pass). Proves the filter is
  load-bearing at render AND every enforcer.
- **Double-record regression** (P0-1) — fast task, `## Risk` plan: assert `ait gates
  run` records **exactly one** `risk_evaluated`; negative control (self-record NOT
  swapped to `active_gates`) yields the mask/double. Adapt existing
  `test_gate_no_double_record.sh`.
- **Render-content assertions** — invert `test_skill_render_task_workflow.sh` **Test 5**
  (currently asserts the risk producer text is profile-INvariant across all 3 —
  lines ~212-256): make it profile-conditional (present for fast, absent for
  default/remote); transform the "backfill always rendered" asserts (~242-247) into
  "`materialize-active` always rendered"; keep the `profile.risk_evaluation`
  absent-asserts (~249-252). Assert `default` shrinks materially vs the post-t635_14
  baseline. Keep Test 1b invariance (the new gate is profile-dimension, not
  `{% if agent %}`).
- **Regression** — `test_gate_effective_gates.sh`,
  `test_gate_declaration_backfill.sh` (adapt to Step-4 materialize replacing Step-7
  backfill), `test_gate_orchestrator.sh`, `test_gate_guarded_archival.sh`,
  `test_dependency_unblock.sh`, `test_gates_reference_drift.sh`; `shellcheck`;
  `aitask_skill_verify.sh`.

## Follow-up tasks — created as the FIRST implementation step (not deferred)

Creating these two siblings is **implementation step 0** (immediately
post-approval, before any code change), and the Step-8 review checklist verifies
they exist — t635_33 must not finalize while these lanes silently retain the
known mismatch:

- **Remote/web lane materialization** (new t635 sibling, `depends: [635_33]`):
  add `materialize-active` to `aitask-pickrem`/`aitask-pickweb` ownership steps
  (their own `.md.j2` + rendered trees), set `remote.yaml rendered_gates: []`,
  regen their goldens. Interim risk is narrow (only a LITERAL `gates:`
  declaration under `remote`, which has no `default_gates`); the refactor does
  not worsen today's behavior — documented in the task body.
- **`task-workflown` (pickn) migration** (new t635 sibling, `depends: [635_33]`):
  migrate its 8 stale `{% if profile.risk_evaluation %}` blocks to the
  `rendered_set` model. Latent t1147 today, safe only because no one runs
  pickn+`fast` — documented in the task body.

**t1156 (landed):** its manual-verification carve-out is honored IN-TASK at the
materialize sink (shared allowlist — see Design); no follow-up needed, but add a
reverse coordination note referencing t1156's archived plan.

## Verification (end-to-end)

1. `shellcheck` edited scripts; `bash tests/test_gate_active_gates.sh` + the
   negative-control + double-record tests pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens regenerated &
   committed in the same change; `default` rendered planning.md/SKILL.md is visibly
   leaner (risk producer omitted).
3. Regression suite green (orchestrator, verifiers, effective-gates, dependency
   unblock, guarded archival, reference drift).
4. **Live smoke:** pick a fast child → `active_gates:[risk_evaluated]` stamped,
   producer runs, `ait gates run` records one `risk_evaluated`, archives. Set a
   throwaway task `gates:[risk_evaluated]`, materialize under `default` →
   `active_gates:[]`, `archive-ready` → NO_GATES → archives with no manual append
   (the negative control, live).
5. **Step 9 (Post-Implementation)** — cleanup / archival / merge.

## Risk

### Code-health risk: high
- **Wide blast radius across load-bearing enforcement.** The change swaps the
  gate-reading seam at 9 enforce/schedule/record sites (gate_ledger.py
  445/619/665/695/735/785, gate_orchestrator.py 367/537), injects a render-context
  var (skill_template.py), edits the `aitask_ls.sh` candidate grep, and adds a
  frontmatter field with 5-layer registration — the archival guard, orchestrator,
  and dependency-unblock all change what they read at once · severity: high · →
  mitigation: in-task structural guards (single reader seam, negative-control +
  durability + concurrency tests) + gate_activation_live_verify (after)
- **Subtle mis-enforcement failure modes.** A single missed read-site silently
  reintroduces t1147 (wrongful block) or under-enforces (skips a real gate); the
  stress-test already caught 5 sites the first design missed · severity: high · →
  mitigation: gate_activation_live_verify (after)
- **Goldens/render blast radius.** All 3 profiles × 3 agent trees × 9 caller skills
  regenerate; Test 5 inverts · severity: medium · → mitigation: single reader
  function (one seam); `aitask_skill_verify.sh` + committed goldens guard drift.

### Goal-achievement risk: medium
- **Correctness invariant spans many sites + the render layer.** "A filtered gate
  is invisible everywhere" is only true if every enforcer + the render omission +
  the materialize safety-valve all agree; partly encoded in markdown/Jinja ·
  severity: medium · → mitigation: gate_activation_live_verify (after)
- **Scope carve-outs could leave latent t1147 in sibling lanes.** Remote/web and
  `task-workflown` are deferred to follow-ups; if not tracked, a `fast`-run pickn
  task reproduces the bug · severity: low · → mitigation: explicit follow-up tasks
  created post-approval; interim risk documented as narrow.

### In-task structural guards (not separate tasks)
- Single `read_active_gates_from_text` seam (one place to reason about the swap).
- **Negative-control test** (filtered gate: renders without machinery, archives,
  unblocks dependents) + **double-record regression** (P0-1) with a negative control.
- **Render-content assertions** keep the Jinja omission wired to `rendered_set`.
- Full goldens regen + `aitask_skill_verify.sh`.

### Planned mitigations
- timing: after | name: gate_activation_live_verify | type: manual_verification | created: t1163 | priority: medium | effort: medium | addresses: code-health mis-enforcement + goal-achievement whole-flow correctness | desc: Live cross-profile verification — a task declaring a profile-filtered gate archives cleanly under a lean profile (no manual gate append), is enforced under fast, and shows the correct active set in board/monitor; exercises the real pick→archive flow, not just unit fixtures.

## Post-Review Changes

### Change Request 1 (2026-07-19 09:10)
- **Requested by user:** Six review concerns: (1, high) a failed
  `materialize-active` re-derivation left a previous profile's tuple
  authoritative (profileless digest halves still validate) — over-blocking on
  fast→default switches, under-enforcing on the reverse; (2, medium)
  `materialize-active` leaked `task_git` commit output onto stdout before the
  status line and swallowed persist failures silently; (3, medium)
  profile-read errors degraded to an empty render ceiling, so a directory
  path / vanished file / garbage profile could silently persist
  `active_gates: []`; (4, low) the AGENTS.md mirror was not updated alongside
  CLAUDE.md and the seed; (5, low) the promised profile-editor round-trip test
  for `rendered_gates: []` was missing; (6, low) working-tree hygiene — the
  `task-workflown/gate-cli.md` copy, the untracked `.aitask-data` symlink, and
  over-claiming a green suite.
- **Changes made:** (1) `materialize-active` hard-fail paths now CLEAR any
  persisted tuple (new `aitask_update.sh --clear-active-gates` grouped-deletion
  flag, mutually exclusive with the tuple flags) before exiting nonzero, so the
  raw-`gates:` fallback truly governs after a failed re-derivation; SKILL.md
  Step 4 documents both the clear-on-failure semantics and the no-profile
  claim-time-snapshot semantics explicitly. A bare no-`--profile` invocation
  stays a plain usage error (the skill skips the call by design — the snapshot
  keeps governing). (2) git persist output fully quieted (stdout = exactly one
  status line, asserted by test) and a persist failure now emits a WARN on
  stderr instead of being swallowed; the verb still exits 0 there because the
  tuple is already durable in the task file and fixtures/legacy no-git setups
  make commit failure a normal condition. (3) `compute_active_gates` now reads
  the profile strictly via `_read_profile_text_strict` (regular readable file
  + top-level `name:` key required) and raises `ProfileReadError` (CLI exit 3)
  instead of degrading to `[]`; the bash caller adds `-f` and converts the
  failure into the clear-stale-tuple path. (4) AGENTS.md mirrors the
  CLAUDE.md/seed gates + tuple documentation. (5) new
  `tests/test_profile_editor_rendered_gates.py` (5 tests): collect → serialize
  → load round-trip keeps an explicit `rendered_gates: []` present, blank text
  clears the key, and the real `render_skill` seam distinguishes `[]` (renders
  nothing) from unset (falls back to `default_gates`). (6) verified with
  evidence that the `task-workflown/gate-cli.md` copy FIXES the source-parity
  assertion (removing it re-breaks it), so it is kept — required by the
  workflown mirror contract and consumed when t635_36 migrates the tree; the
  `.aitask-data` symlink is worktree scaffolding and is excluded via
  path-scoped staging; the 7 remaining `test_skill_render_task_workflown.sh`
  failures are pre-existing at HEAD (stale `profile.risk_evaluation` blocks —
  the documented latent defect t635_36 owns) and are disclosed, not claimed
  green.
- **Files affected:** `.aitask-scripts/aitask_gate.sh`,
  `.aitask-scripts/aitask_update.sh`, `.aitask-scripts/lib/gate_ledger.py`,
  `.claude/skills/task-workflow/SKILL.md` (+ regenerated goldens and committed
  remote prerenders), `AGENTS.md`, `tests/test_gate_active_gates.sh` (72
  asserts now), new `tests/test_profile_editor_rendered_gates.py`.

### Change Request 2 (2026-07-19 09:55)
- **Requested by user:** Three further review concerns: (A, high) the tuple
  write itself destroyed an explicit `gates: []` opt-out — write_task_file's
  never-emit-[] rule dropped the key, so the fresh tuple's gates-half digest
  ("present empty") immediately mismatched the rewritten file ("absent"),
  going STALE and letting the next fast pick resolve `default_gates` and
  revoke the opt-out (reproduced live: STALE:fast->fast right after
  materialize); (B, high) continuing the workflow after a profiled
  materialization failure under-enforces — the raw-`gates:` fallback lacks the
  current profile's `default_gates` (a gates-absent task under fast should
  inherit risk_evaluated) — and `_materialize_fail` claimed "cleared" even
  when the clear itself failed; (C, medium) name:-only profile validation
  still let a malformed gate list (`default_gates: [unclosed`, scalar values)
  read as an empty ceiling and persist `active_gates: []`.
- **Changes made:** (A) raw `gates:` is now presence-tracked in
  aitask_update.sh exactly like the tuple (CURRENT_GATES_PRESENT through
  parse / batch-apply / parent-write save-restore / write_task_file): a
  non-empty set emits as before, an explicit empty key emits `gates: []`, and
  only a truly absent key emits nothing; `--gates ""` keeps its documented
  clear-the-key contract. This also fixes the PRE-EXISTING bug where any
  unrelated `ait update` silently dropped a `gates: []` opt-out. Tests: the
  opt-out survives the tuple write, is immediately FRESH, re-picks are NOOP,
  and survives an unrelated `--priority` update with no default_gates
  resurrection. (B) SKILL.md Step 4 now ABORTS the pick on a nonzero
  materialize exit (Task Abort Procedure) instead of warning-and-continuing —
  clearing the stale tuple remains cleanup, not a justification to proceed;
  `_materialize_fail` reports honestly ("stale tuple cleared" only on a
  successful clear, "could NOT be cleared" warning otherwise, "no prior tuple
  present" when none existed), asserted by tests. The CLI-level NO_GATES
  assertion after clear-on-fail is kept with a comment naming it the transient
  state the workflow abort exists to avoid. (C)
  `_validate_profile_gate_list_syntax` rejects a PRESENT `default_gates` /
  `rendered_gates` whose value is not list-shaped (inline `[...]` or bare-key
  block form) with ProfileReadError; tests cover an unclosed inline list and a
  scalar value (nonzero exit, nothing written).
- **Files affected:** `.aitask-scripts/aitask_update.sh`,
  `.aitask-scripts/aitask_gate.sh`, `.aitask-scripts/lib/gate_ledger.py`,
  `.claude/skills/task-workflow/SKILL.md` (+ regenerated goldens and remote
  prerenders), `tests/test_gate_active_gates.sh` (82 asserts now).

### Change Request 3 (2026-07-19 10:25)
- **Requested by user:** (D, medium) the gate-list validator was not
  syntax-safe: `\s*` after the key consumed newlines, so a valid BLOCK list
  (`default_gates:` + `- item` lines) was mis-read as the scalar
  `- risk_evaluated` and rejected (a regression against the readers'
  supported form), while malformed inline YAML like `[a,,b]` passed the broad
  `\[.*\]` check and was silently normalized; (E, medium) a failed
  path-scoped `task_git add`/`commit` still printed plain `MATERIALIZED:*`
  with exit 0, telling Step 4 the tuple was durable when other checkouts of
  the task-data branch could not see it; (F, low) `_materialize_fail`
  unconditionally appended "raw gates: fallback governs" even when its own
  cleanup report said the stale tuple could NOT be cleared — in that branch
  the old tuple stays authoritative, making the report self-contradictory.
- **Changes made:** (D) validator rewritten: the value match is anchored to
  the key's OWN line (horizontal whitespace only); a present inline list must
  be a complete `[...]` whose every comma-separated item is a (possibly
  quoted) gate-name token (`[a,,b]`, scalars, unterminated lists rejected); a
  bare `key:` must be followed only by `- item` block lines until dedent
  (mis-dashed block lines rejected; empty block = empty list). Exercised
  against a 10-case matrix (valid/empty/malformed × inline/block/absent) plus
  new bash regressions incl. the block-form profile now ACCEPTED end-to-end.
  (E) persistence is now status-typed: a `task_git rev-parse` probe is the
  non-git seam (fixtures skip persistence silently); in a real repo a failed
  add/commit yields the structured single-line
  `MATERIALIZED_UNCOMMITTED:<csv>` (locally enforced, not yet committed) plus
  a stderr WARN; SKILL.md Step 4 parses the new status (warn + continue —
  local enforcement is correct; a later `./ait git` commit of aitasks/ picks
  it up). Test simulates a real-repo failure via a held `.git/index.lock`:
  UNCOMMITTED under the lock, NOOP/plain MATERIALIZED after release. (F)
  `_materialize_fail`'s governing-state suffix is now conditional: "raw
  gates: fallback governs" only when the tuple was cleared or never existed;
  a failed clear instead warns that the outdated tuple may still govern and
  names the manual clear command.
- **Files affected:** `.aitask-scripts/lib/gate_ledger.py`,
  `.aitask-scripts/aitask_gate.sh`, `.claude/skills/task-workflow/SKILL.md`
  (+ regenerated goldens and remote prerenders),
  `tests/test_gate_active_gates.sh` (87 asserts now).

### Change Request 4 (2026-07-19 10:50)
- **Requested by user:** (G, medium) the validator still missed forms its
  readers accept: an unindented dash line was treated as a dedent, so
  `default_gates:\n-\n` passed validation while the reader returned []
  (silent empty ceiling), and the item regex's independent optional quotes
  accepted mismatched pairs like `['risk_evaluated"]`; (H, medium) after a
  transient commit failure, an unchanged re-pick exited through the
  tuple-equality NOOP branch BEFORE persistence, so the pending commit was
  never healed nor re-warned — and the test codified that non-healing.
- **Changes made:** (G) block walk rewritten: a dash line at ANY indentation
  (including none — matching both readers' `[ \t]*-` patterns) is validated
  as a sequence item and a bare `-` is rejected; an indented non-dash line
  inside the block is rejected; only a dedented non-item line ends the block.
  The item regex now requires MATCHED quote pairs
  (`name | 'name' | "name"`). Regressions added: indentless block accepted
  end-to-end, bare-dash rejected, mismatched quotes rejected (verified
  against the reader's parse of each case). (H) persistence extracted into
  `_persist_task_file` (rev-parse non-git seam + porcelain dirty check +
  quiet add/commit) and now runs on BOTH paths: the identical-tuple branch
  verifies/repairs a pending commit before reporting `NOOP:unchanged`, and
  reports the new `NOOP_UNCOMMITTED:pending-persist` (with stderr WARN) when
  the repair is still refused. SKILL.md Step 4 and the CLI help document both
  NOOP statuses. Tests: unchanged retry under a held index lock →
  NOOP_UNCOMMITTED; after lock release → NOOP:unchanged AND `git status
  --porcelain` proves the file was actually committed by the heal.
- **Files affected:** `.aitask-scripts/lib/gate_ledger.py`,
  `.aitask-scripts/aitask_gate.sh`, `.claude/skills/task-workflow/SKILL.md`
  (+ regenerated goldens and remote prerenders),
  `tests/test_gate_active_gates.sh` (92 asserts now).

### Change Request 5 (2026-07-19 11:10)
- **Requested by user:** (I, medium) the validator skipped blank lines inside
  block lists while both regex readers stop consuming at the first blank —
  `default_gates:\n  - a\n\n  - b` validated cleanly but parsed as only [a],
  silently dropping the second gate; (J, medium) `_persist_task_file`
  conflated diagnostics with success: any nonzero rev-parse (including a
  BROKEN real task-data repo) was treated as the fixture seam, and a failing
  `status --porcelain` with empty stdout read as "clean".
- **Changes made:** (I) the validator now REJECTS a dash item that follows a
  blank line inside the block ("a blank line splits the block list — the
  readers stop at blank lines and would drop the items after it"); trailing
  blanks before the next key remain fine. Deliberate scope decision, stated
  explicitly: rather than teaching BOTH canonical readers (python fenced +
  bash whole-file) to consume interior blanks — a framework-wide parsing
  semantics change that would also risk the bash reader swallowing markdown
  `- ` bullets from a task BODY after a blank line — validation is aligned to
  the readers' real contract, so no gate can be silently dropped (loud error
  instead of survival-by-reader-change). Regression: the blank-split profile
  is rejected with nothing written. (J) `_persist_task_file` now
  discriminates: rev-parse failure with NO git markers (`.git` /
  `.aitask-data` absent) = the expected non-git fixture seam (skip silently);
  rev-parse failure WITH markers present = broken repo → unverified →
  UNCOMMITTED status; the porcelain status command's own exit is captured
  separately and a failure reads as "unverified", never "clean". Regressions:
  a fixture with a corrupt `.git` file yields MATERIALIZED_UNCOMMITTED and
  NOOP_UNCOMMITTED on the unchanged retry.
- **Files affected:** `.aitask-scripts/lib/gate_ledger.py`,
  `.aitask-scripts/aitask_gate.sh`, `tests/test_gate_active_gates.sh` (95
  asserts now).

### Change Request 6 (2026-07-19 11:25)
- **Requested by user:** (K, medium) the blank-split safeguard also rejected
  blanks BEFORE the first block item (`default_gates:\n\n  - risk_evaluated`),
  a valid form the authoritative python reader consumes whole — an
  unnecessary fail-closed regression.
- **Changes made:** the block walk now tracks `item_seen`: a blank line only
  triggers the split rejection when a dash item follows a blank in an
  already-started list; leading blanks between the key line and the first
  item are accepted. Regressions: leading-blank profile materializes
  end-to-end (`MATERIALIZED:risk_evaluated`); the interior blank-split case
  stays rejected.
- **Files affected:** `.aitask-scripts/lib/gate_ledger.py`,
  `tests/test_gate_active_gates.sh` (96 asserts now).

## Final Implementation Notes

- **Actual work done:** Landed the full Model-1 design as planned: the
  `rendered_set` render-context injection with `{% if 'risk_evaluated' in
  rendered_set %}` gating of all risk machinery (planning §6.1 producer +
  guard, Step-7 self-record + mitigation-before, Step 8d) plus Step-8c
  routing; the four-field `active_gates*` tuple materialized at Step 4 via
  the new `aitask_gate.sh materialize-active` (replacing the Step-7 backfill,
  which was removed); the single validated tuple reader
  `read_active_tuple_from_text` swapped at all 9 enforce/schedule/record
  sites (gate_ledger ×5 + orchestrator ×2 + bash decision verbs + board
  decision surfaces), with `also_blocks_dependents` filtered-subtraction;
  pure-bash `active`/`has-gates-field`/`should-self-record`;
  `active-gates-status` freshness introspection; `rendered_gates` profile key
  (schema/editor/docs); CLI-atomic tuple plumbing in `aitask_update.sh` (+
  `--clear-active-gates` grouped deletion); grouped newer-side-wholesale
  tuple merge in `board/aitask_merge.py`; `aitask_ls.sh` candidate grep;
  docs (task-format.md, CLAUDE.md, AGENTS.md, seed instructions,
  profiles.md, task-creation-batch.md, new `gate-cli.md`); goldens + remote
  prerenders regenerated. Follow-up siblings t635_35 (remote/web lane) and
  t635_36 (task-workflown migration) created as implementation step 0, both
  `depends: [635_33]`. `default`'s rendered SKILL.md shrank 766→~750 lines
  and its planning.md lost the entire risk block (the restored leanness).
- **Deviations from plan:** (1) Implementation moved into an isolated git
  worktree (`aiwork/t635_33_gate_activation_render_time`, branch
  `aitask/t635_33_gate_activation_render_time`) after a concurrent session's
  `git stash` + reset wiped the first round of edits in the shared checkout —
  the fast profile's current-branch mode was abandoned mid-task for safety;
  all wiped edits were later byte-verified recovered against stash@{0}. The
  concurrent session's own stashed files (chatlink_app.py,
  test_chatlink_tui.sh, settings.local.json) remain untouched in stash@{0}.
  (2) Six review rounds hardened the initial implementation (see Post-Review
  Changes 1–6): clear-on-failure semantics + workflow abort, presence-tracked
  raw `gates:` (opt-out preservation), strict profile validation
  (line-anchored, block/inline/quote/blank-split rules), structured
  MATERIALIZED_UNCOMMITTED / NOOP_UNCOMMITTED persistence statuses with a
  three-way non-git/broken-repo seam, AGENTS.md mirror, and the
  profile-editor round-trip test. (3) `gate-cli.md` was also copied into
  `task-workflown/` to keep its source-parity contract green (consumed when
  t635_36 migrates that tree).
- **Issues encountered:** the concurrent-writer wipe (above);
  `tests/test_skill_render_task_workflown.sh` fails 7 asserts at HEAD
  (pre-existing: its stale `{% if profile.risk_evaluation %}` blocks — the
  documented latent defect t635_36 owns); the initial `assert_contains`
  argument order in the new test file; profile-editor list rows could not
  express present-but-empty (fixed with the literal `[]` affordance).
- **Key decisions:** key-presence (not truthiness) semantics for
  `rendered_gates` in all three compute paths; full compute lives ONLY in
  python (`compute_active_gates`) with the MV allowlist passed in from
  task_utils.sh (single source) while decision verbs are pure bash validating
  the profileless digest halves (implicit cross-language hash agreement);
  `list` stays declared-intent, `active-gates-status` is the enforced-set
  display; blank-split block lists are rejected rather than teaching both
  canonical readers new semantics (documented trade-off, CR5); persistence
  failures are status-typed rather than fatal (the tuple is locally durable;
  Step 4 aborts only on materialization failure proper).
- **Upstream defects identified:**
  - tests/golden/procs/task-workflow/gate-recording-default.md:21 — golden was
    stale since t635_15 (dual-transport paragraph missing); fixed in this task
    by the golden regeneration, no follow-up needed.
  - .aitask-scripts/aitask_update.sh:620 — pre-existing: any `ait update`
    rewrite silently dropped an explicit `gates: []` opt-out (never-emit-[]
    writer); fixed in this task via presence-tracking (CR2), no follow-up
    needed.
  - .claude/skills/task-workflown/SKILL.md:1 — pre-existing latent t1147: 8
    stale `{% if profile.risk_evaluation %}` blocks render no risk producer
    under gate-declaring profiles; already tracked as t635_36 (created by
    this task), no new follow-up needed.
- **Notes for sibling tasks:** t635_35/t635_36 should reuse the Step-4
  materialize call shape from `.claude/skills/task-workflow/SKILL.md` Step 4
  verbatim (incl. the MATERIALIZED_UNCOMMITTED / NOOP_UNCOMMITTED handling
  and the abort-on-failure rule) and the `rendered_set` Jinja pattern from
  planning.md; `remote.yaml` gets its explicit `rendered_gates: []` in
  t635_35. The gate-CLI contract reference is `gate-cli.md` (already copied
  into task-workflown). t635_34 reconciles installed registries against this
  model. The after-mitigation `gate_activation_live_verify` manual task is
  created at Step 8c/8d of this session.
