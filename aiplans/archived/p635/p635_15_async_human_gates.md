---
Task: t635_15_async_human_gates.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_16_*.md, aitasks/t635/t635_17_*.md, aitasks/t635/t635_18_*.md
Archived Sibling Plans: aiplans/archived/p635/p635_11_orchestrator_verifier_contract.md, aiplans/archived/p635/p635_21_gate_ledger_merge_safety.md
Branch: (current branch — profile 'fast')
Base branch: main
---

# t635_15 — Async human gates: `ait gate pass` + hybrid switch (Phase 5)

## Context

The gate framework (t635_1…t635_14) shipped the **read side** of human gates:
the orchestrator (`lib/gate_orchestrator.py` `_handle_human`) appends `pass`
when a gate's `signal_target` file exists and `pending` when it does not, and
**never self-signals**. `ait gate fail` exists; the non-negotiable autonomy rule
is documented verbatim in the registry and `aitask-gate-template`.

What is still missing (Phase 5 / roadmap decision **D2**, hybrid-by-mode):

1. **Signal CREATION** — a sanctioned way for a *human* to sign a gate:
   `ait gate pass <task-id> <gate>`. The CLI reference lists it but no script
   exists (t635_11 deliberately deferred it and told the dispatcher "Do NOT add
   `gate pass`").
2. **The hybrid switch** — attended sessions keep interactive approvals (the
   `AskUserQuestion` answer *is* the signal, recorded directly by the Gate
   Recording Procedure); the headless/remote lane treats the *same* gate as an
   async human gate — it **runs the orchestrator** and **stops cleanly at
   pending-human** instead of auto-committing past it. One gate definition, two
   signal transports.

**Two facts discovered during planning that shape the design:**

- **`.aitask-gates/` is gitignored** (`.gitignore:19`). The `.signed` file is a
  *local witness only*; the durable, cross-PC record of a sign-off is the `pass`
  block in the task file's `## Gate Runs` ledger, which **t635_21** made
  union-merge-safe. So `ait gate pass` creates the witness, then lets the
  existing orchestrator read-side record the ledger `pass` (no second pass-writer).
- **pickrem never runs the orchestrator today.** Its Step 8 does only legacy
  `verify_build`; it never calls `ait gates run`, so a headless task reaches
  archive with no machine-gate runs and no pending human-gate block. Merely
  handling the archive guard's `GATE_PENDING` would be *archive-blocking*, not
  "resolve approvals as async human gates". This task therefore adds a **real
  `ait gates run` step** to the headless lane (see Deliverable B).

Out of scope (later children): remote comment/label signals + projection
(t635_16); autonomous-lane **auto-completion policy** — whether the autonomous
lane may auto-resume/auto-complete past a pending human gate (t635_17). This
task only makes the headless lane **run the gates and stop cleanly**.

## Design decisions (confirmed with user)

- **`ait gate pass` = signal-creation + delegate recording.** Creates the
  `.signed` witness (signer, UTC timestamp, hostname, **and the code digest** —
  see freshness below), then delegates the ledger `pass` recording to the
  existing wrapper `aitask_run_gates.sh run <id> --gate <gate>` — reusing the
  orchestrator's read-side `_handle_human` (the single writer of observed pass
  blocks). No duplicated append logic; one-command UX; matches the framework
  doc's "signal CREATION" wording.
- **Hybrid switch = real `ait gates run` in the headless lane + stop-clean.**
  Give `review_approved`/`merge_approved` an async `signal: file-touch` +
  `signal_target`; port the attended Step 9 orchestrator dispatch into the
  pickrem flow so declared gates actually run, human gates pend, and the lane
  stops cleanly at pending-human (never self-signalling). **Dormant by default**
  (remote.yaml declares no `default_gates`) — zero blast radius for existing
  remote runs until a policy child opts in. Auto-completion policy stays t635_17.
- **Approval freshness (raised in review): witnesses are code-bound.** A
  persistent witness must not be silently consumed as a `pass` for a *different*
  code state than the human reviewed. The witness records the `code_digest` at
  signing time; the orchestrator's read-side **validates it against the current
  digest** and re-pends a stale signature instead of passing it.

## Deliverable A — `ait gate pass` (signal creation, code-bound)

### New file `.aitask-scripts/aitask_gate_pass.sh` (whitelisted helper)
Model on `aitask_gate_fail.sh` (thin wrapper, `set -euo pipefail`, sources
`terminal_compat.sh`; add `task_utils.sh`/`python_resolve.sh` as needed).

Usage: `aitask_gate_pass.sh <task-id> <gate>`

1. Resolve the task file (`resolve_task_file`).
2. Read the gate's `type` + `signal_target` from `aitasks/metadata/gates.yaml`
   by reusing `gate_ledger.read_registry` via a `python_resolve.sh`-guarded
   one-liner — do NOT hand-parse YAML.
3. **Refuse machine gates:** `type != human` → `die "gate pass refuses machine
   gate '<gate>' …"`, non-zero exit. (Framework: "refuses for machine".)
4. **Refuse gates with no file-touch signal:** empty `signal_target` → `die`
   (attended-only checkpoint, e.g. `plan_approved`), non-zero exit.
5. Substitute `<task-id>`→`t<id>`, `<gate>` in `signal_target`; `mkdir -p` the
   parent; write the witness with `signer=`, `signed_at=<UTC>`, `hostname=`, and
   **`code_digest=<hash>`** (the current code digest — reuse
   `gate_orchestrator.code_digest()` via a new `code-digest` CLI verb on
   `gate_orchestrator.py`, or a tiny shared call). Idempotent: if it exists,
   report "already signed" and re-stamp the digest (a re-sign after code change
   refreshes the binding). Absent git / no digest → omit the field.
6. **Delegate recording:** run `"$SCRIPT_DIR/aitask_run_gates.sh" run "$task_id"
   --gate "$gate"` and surface its report (records `pass` if fresh + predecessors
   satisfied; otherwise reports why and records nothing — the witness persists).
7. Header comment carries the verbatim autonomy rule: this is the **human's**
   tool; agents must never invoke it to self-sign.

### Orchestrator read-side — freshness validation (`lib/gate_orchestrator.py`)
Edit `_signal_present` / `_handle_human` (the read-side t635_11 shipped) so a
witness is honored **only when its code binding is current**:
- Read the witness's `code_digest=`. If **absent** (hand-created / no-git witness)
  → accept as before (back-compat). If **present and == `self.digest`** → fresh →
  append `pass` with `note=signed_digest:<hash>` (auditable approved state,
  mirroring machine gates' `stuckhash:`). If **present and != `self.digest`** →
  **stale** → do NOT pass; append/keep `pending` with `note=stale signature:
  signed against <old>, code now <new> — re-sign with 'ait gate pass'`.
- If the current digest is unavailable (git missing) → cannot validate → accept
  (graceful degrade, matching `is_stuck`'s digest-unavailable behavior).
This closes the deferred-observation hole (sign while predecessors blocked → code
changes → witness later consumed for the wrong state). It does **not** invalidate
an already-recorded `pass` (a satisfied gate is never re-observed — see Test 3),
so it only governs witness *consumption*, exactly where the risk is.

### `ait` dispatcher (`ait`)
Under `gate)` add `pass) exec "$SCRIPTS_DIR/aitask_gate_pass.sh" "$@" ;;` and
extend the help block with `pass <task-id> <gate>`. (Reverses t635_11's note.)

### Registry `aitasks/metadata/gates.yaml`
Add async transport to the two post-integration approval gates:
```yaml
  review_approved:
    type: human
    signal: file-touch
    signal_target: ".aitask-gates/<task-id>/<gate>.signed"
    ...
  merge_approved:
    type: human
    signal: file-touch
    signal_target: ".aitask-gates/<task-id>/<gate>.signed"
    ...
```
Leave `plan_approved` **attended-only** (no signal_target: pre-code; headless
auto-approves the plan). Rewrite the header comment (currently "The interactive
checkpoint gates below … declare no signal_target") to document the **dual
transport** (attended direct-`pass`; headless file-touch) and the **code-bound
freshness** rule. Harmless to attended mode — the direct `pass` satisfies the
gate so the orchestrator never re-pends it.

### Whitelist
Add `aitask_gate_pass.sh` to the 4 framework touchpoints (mirror
`aitask_gate_fail.sh`): `.codex/rules/default.rules`,
`seed/codex_rules.default.rules`, `seed/claude_settings.local.json`,
`seed/opencode_config.seed.json`; and `.claude/settings.local.json` if the
self-modification guard permits (else note for the user, as in t635_11).

## Deliverable B — hybrid switch (headless runs gates + stops clean)

### `.claude/skills/aitask-pickrem/SKILL.md.j2` — new Step 9.5 "Run declared gates"
**Placement (pinned):** a new step **after Step 9 Auto-Commit** (code + plan are
already committed — the durable, reviewable artifact) and **before Step 10
Archive**. Port the attended `task-workflow` Step 9 "Verify implementation"
orchestrator dispatch:

```bash
gates_out="$(./ait gates run <task_id> 2>&1)"; gates_rc=$?
```
- `gates_rc` nonzero → **infra** failure (`ait`/wrapper/registry/python) →
  **Abort Procedure**.
- `gates_out` contains `No gates declared; nothing to do.` → no-op (the common
  case today; the legacy pre-commit `verify_build` in Step 8 already covered the
  build). Proceed to Step 10.
- else → read the per-gate report and act per status (mirroring attended Step 9,
  **not** abort-on-first-fail):
  - `pass`/`skip` → continue.
  - machine **`fail`** → inspect `./ait gate log <task_id> <gate>` + diff against
    base. **If task-caused** → fix and re-run `./ait gates run <task_id>`; repeat
    within the gate's retry budget (same fix-and-retry loop pickrem Step 8 already
    uses for `verify_build`). **If pre-existing/unrelated or unfixable after
    reasonable attempts** → `./ait gate fail <task_id> <gate> --reason "…"` and log
    it in Final Implementation Notes; **Abort only** if a *blocking* gate cannot be
    made to pass.
  - machine **`error`** (verifier infra: launch/timeout/exit-3/malformed) →
    diagnose the verifier/config; do **not** "fix the code". Abort if unresolvable.
  - **`pending` (human) → stop cleanly**: the code+plan are already committed
    (reviewable & resumable), so **skip only Step 10 (archive + push-after-
    archival)** — do NOT touch the committed code. Leave the task in-flight and
    display: "Awaiting human sign-off on gate(s) `<csv>` — a reviewer inspects the
    committed branch, runs `ait gate pass <task-id> <gate>`, then `ait gates run
    <task-id>` (or re-runs `/aitask-pickrem <task-id>`) to record the pass and
    complete archival." **Never self-signal.** This is D2's "stop cleanly at
    pending-human" for the headless lane.

Keep the archive-guard `GATE_PENDING` handling as a **backstop** in Step 10
(stop clean, same message) so a task that somehow reaches archive still can't
slip past. Dormant unless the task declares gates. **Known benign redundancy:** a
task that opts into BOTH a legacy `verify_build` (Step 8, pre-commit) and a
`build_verified` gate (Step 9.5) runs the build twice; harmless, and only
possible once a policy child opts remote tasks into machine gates — de-duplication
is left to that child (t635_17), noted here rather than silently ignored.

`aitask-pickweb` is **not** touched: it defers all ownership/merge/archival to
the local (attended) `aitask-web-merge`, so its approvals are attended, not
headless-async (explicit scope note).

### Regenerate the committed headless prerender + goldens
`aitask-pickrem` declares `prerender_for_headless: true`, so the `remote`
closure is committed. Re-render + regenerate goldens in the **same commit**;
run `./.aitask-scripts/aitask_skill_verify.sh`.

## Docs

- `aidocs/gates/aitask-gate-framework.md` — `ait gate pass` is now real; refresh
  "arrives in t635_15" future-tense notes to present tense; document the dual
  transport + the code-bound freshness rule for `review`/`merge`.
- `.claude/skills/aitask-gate-template/SKILL.md` — update the **Scope boundary**
  note (~lines 183-186): signal creation (`ait gate pass`) has **shipped**; keep
  `signal: comment` / remote polling as t635_16. (Auto-renders to Codex/OpenCode.)
- `.claude/skills/task-workflow/gate-recording.md` — one-line note that
  `review_approved`/`merge_approved` now carry an async file-touch transport used
  by the headless lane; attended recording unchanged.
- **Website:** the comprehensive sweep is **t635_18** (parent doc track); a brief
  `ait gate pass` mention is deferred there — explicit scope decision, not a
  silent drop.

## Tests

- **`tests/test_gate_pass.sh`** (new; mirror `test_gate_orchestrator.sh`
  scaffold). Cases:
  1. refuses a machine gate (`build_verified`) → non-zero, **no** witness created;
  2. refuses an unknown gate; 3. refuses a human gate with no `signal_target`
  (`plan_approved`) → non-zero; 4. creates the witness for a human gate — correct
  `t<id>` path substitution; content has signer + timestamp + `code_digest=`;
  5. idempotent second call (re-stamps digest); 6. **integration**: after `ait
  gate pass` with predecessors satisfied, the delegated `ait gates run --gate`
  appends a `pass` block carrying `note=signed_digest:`.
- **Freshness / no-self-signal (orchestrator human-gate tests** — extend
  `test_gate_orchestrator.sh`):
  7. **absent signal** → read path appends `pending` (never self-signals);
  8. **stale witness** — witness `code_digest` ≠ current digest → orchestrator
     re-pends (`note=stale signature…`), does **not** pass;
  9. **unstamped witness** (no `code_digest`) → accepted as `pass` (back-compat).
- **Concern-3 regression** (explicit): a task with an existing direct ledger
  `pass` for `review_approved` and **no** `.signed` file → `ait gates run`
  appends **no** `pending` (satisfied gate never re-observed).
- **`tests/test_gate_cli_wiring.sh`** — add `ait gate pass` dispatch assertion
  (refuse-path / `--help`, no live signing).
- **pickrem render test** (`tests/test_skill_render_aitask_pickrem*.sh` or
  equivalent) — assert the rendered `remote` closure contains the `ait gates run`
  step + the pending-human stop-clean branch; keep the golden in sync.
- If `aitask_gate_pass.sh` sources a lib absent from the fake-repo baseline, add
  it to `tests/lib/test_scaffold.sh` `setup_fake_aitask_repo()`.

## Risk

### Code-health risk: medium
- **Editing the shared read-side `_handle_human`/`_signal_present`** (t635_11's
  engine) to add freshness validation ripples to every `ait gates run` observing
  a human gate · severity: medium · → mitigation: back-compat default (unstamped
  witness still passes; git-unavailable degrades to accept); Tests 7-9 cover
  fresh/stale/unstamped; behavior is additive (a fresh or unstamped witness
  behaves exactly as today).
- Adding `signal_target` to `review_approved`/`merge_approved` changes read-side
  behavior for tasks that declare them · severity: medium · → mitigation: dormant
  by default; attended direct-`pass` satisfies the gate (Concern-3 regression
  asserts no re-pend).
- Editing the pickrem `.md.j2` regenerates a **committed headless prerender** +
  goldens · severity: medium · → mitigation: regenerate in the same commit;
  `aitask_skill_verify.sh` + render test in-plan.
- `aitask_gate_pass.sh` reuses `aitask_run_gates.sh` + `code_digest()` (no new
  orchestration logic) · severity: low.

### Goal-achievement risk: medium
- The headless run-gates + stop-clean path is dormant by default, so it is
  validated against a constructed fixture rather than a live autonomous run ·
  severity: medium · → mitigation: in-plan render/unit tests of the `ait gates
  run` + pending-human branch; live autonomous validation is t635_17's concern
  (auto-completion policy) — coordinate, don't duplicate.
- Cross-PC async correctness relies on the ledger `pass` propagating via
  t635_21's union-merge (the witness is gitignored/local) · severity: low
  (t635_21 shipped + tested) · → mitigation: Test 6 asserts the *ledger* `pass`
  (the propagating artifact) is recorded, not just a local file.

### Planned mitigations
- timing: after | task: **t1109** (async_human_gate_live_verify) | type: manual_verification | priority: low | effort: low | addresses: goal-achievement "headless run-gates + stop-clean validated only against a fixture" | desc: autonomous manual-verification of the end-to-end async human-gate flow — construct a task declaring `review_approved`, drive the headless lane to a clean pending-human stop, `ait gate pass`, re-run, confirm the ledger `pass` (+ stale-signature re-pend after a code change) and archival; coordinate with t635_17 to avoid overlap. **Created as t1109.**

## Verification (end-to-end)
1. `bash tests/test_gate_pass.sh`, `bash tests/test_gate_orchestrator.sh`,
   `bash tests/test_gate_cli_wiring.sh`, the pickrem render test — all PASS.
2. `shellcheck .aitask-scripts/aitask_gate_pass.sh`.
3. `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens regenerated + committed.
4. **Live smoke (manual):** temp task with `gates: [review_approved]`; `ait gate
   pass <id> review_approved` → witness (with `code_digest`) created and a `pass`
   block appended; change a code file, hand-create a stale witness, `ait gates
   run` → re-pends with a stale-signature note; `ait gate pass <id>
   build_verified` refuses; a headless run with the gate pending stops clean.
5. Reference **Step 9 (Post-Implementation)** for cleanup / archival / merge.

## Final Implementation Notes

- **Actual work done:** Built both deliverables exactly as planned.
  - *A — `ait gate pass`:* new `.aitask-scripts/aitask_gate_pass.sh` (refuses
    machine gates + attended-only human gates; writes a code-bound witness with
    `signer`/`signed_at`/`hostname`/`code_digest`; delegates ledger recording to
    `aitask_run_gates.sh run <id> --gate <gate>`). `lib/gate_orchestrator.py`:
    added the `code-digest` CLI verb, `_read_witness_digest()`, and a `_signal_state()`
    classifier (`absent`/`fresh`/`stale`/`unstamped`) driving a rewritten
    `_handle_human()` — a fresh witness passes with `note=signed_digest:<hash>`,
    a stale one (digest mismatch) re-pends with a `stale signature` note, an
    unstamped one is accepted (back-compat). `ait` dispatcher `gate pass` case +
    help. `gates.yaml`: `signal: file-touch` + `signal_target` on `review_approved`
    / `merge_approved` (dual transport) + rewritten header comment. Whitelisted
    `aitask_gate_pass.sh` in the 4 framework touchpoints.
  - *B — hybrid switch:* `aitask-pickrem/SKILL.md.j2` new **Step 9.5** (after the
    Step 9 auto-commit, before Step 10 archive) that runs `ait gates run`,
    mirrors the attended machine-fail fix-and-retry loop (Abort only as a last
    resort), and stops cleanly at pending-human (never self-signals); `GATE_PENDING`
    archive-guard backstop added to Step 10. Regenerated all 3 committed remote
    prerenders + the golden.
  - *Docs:* framework worked-example (code-binding/freshness), gate-template
    scope boundary (signal creation shipped), gate-recording dual-transport note.
- **Deviations from plan:** None material. `plan_approved` was left attended-only
  (no signal_target) as planned. The witness-perturbs-digest edge case (the
  witness must be gitignored so creating it does not flip the code digest between
  stamping and observing) is real and handled by `.aitask-gates/` being gitignored
  in production; the freshness tests replicate it with a `sig/` gitignore in the
  fixture.
- **Issues encountered:** (1) `aitask_gate_pass.sh` initially tripped shellcheck
  SC2034 (`file` unused, since recording is delegated) — changed to
  `resolve_task_file … >/dev/null` (validate-and-discard). Remaining SC1091 infos
  are the source-not-followed baseline shared by every helper (e.g.
  `aitask_gate_fail.sh`). (2) `gates.yaml` and the task/plan files live on the
  `aitask-data` branch (symlinked); the concurrent syncer swept my `gates.yaml`
  edit into an unrelated data-branch commit — expected concurrent-writer behavior,
  content is on-branch and correct. (3) The pickrem render test's 3 "freshness"
  failures pre-commit are the `git show HEAD:` commit-reminder; they pass once the
  regenerated remote variants are committed.
- **Key decisions:** `ait gate pass` is pure signal-creation that *delegates*
  recording to `ait gates run --gate` (user's refinement) — the orchestrator stays
  the single writer of observed pass blocks, no duplicated append path. Signatures
  are code-bound (raised in plan review) so a witness cannot be silently consumed
  as a pass for a different code state; this governs witness *consumption* only and
  never invalidates an already-recorded pass (a satisfied gate is never
  re-observed — Test 9c). The hybrid switch adds a real `ait gates run` step to the
  headless lane (not mere archive-blocking) and is dormant by default (remote.yaml
  declares no `default_gates`).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The async human-gate write side is complete —
  `ait gate pass <id> <gate>` creates the code-bound witness and records the ledger
  pass via the orchestrator; the ledger pass (not the gitignored witness) is the
  cross-PC artifact (union-merge-safe via t635_21). **t635_16** (remote projection
  / Appendix A) owns `signal: comment` and remote comment polling — the natural next
  transport. **t635_17** (autonomous-lane rigor) owns the auto-completion policy:
  t635_15 only makes the headless lane STOP cleanly at pending-human; whether the
  autonomous lane may auto-resume/auto-complete past it is t635_17's call. The
  headless run-gates + stop-clean path is validated against a fixture; the proposed
  after-mitigation MV (`t635_async_human_gate_live_verify`) drives it live —
  coordinate with t635_17 to avoid overlap.
