---
Task: t635_1_gate_ledger_substrate.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_10_monitor_gate_status_column.md, aitasks/t635/t635_11_orchestrator_verifier_contract.md, aitasks/t635/t635_12_build_test_machine_gates.md, aitasks/t635/t635_13_risk_evaluation_gate_integration.md, aitasks/t635/t635_14_profile_gate_declaration_unification.md, aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_20_stats_multistage_completion.md, aitasks/t635/t635_2_task_workflow_checkpoint_recording.md, aitasks/t635/t635_3_dependency_unblock_semantics.md, aitasks/t635/t635_4_gate_guarded_archival.md, aitasks/t635/t635_5_ledger_driven_reentry.md, aitasks/t635/t635_6_aitask_resume_skill.md, aitasks/t635/t635_7_gate_aware_aitask_pick.md, aitasks/t635/t635_8_python_gate_ledger_parser.md, aitasks/t635/t635_9_board_inflight_action_view.md
Base branch: main
plan_verified: []
---

# t635_1 — Gate Ledger Substrate (Phase 1)

## Context

This is **Phase 1** of the gate-framework integration roadmap
(`aidocs/gates/integration-roadmap.md`, locked decision **D1: ledger-first**).
The gate framework makes task execution stateful and multi-pass via named
verification checkpoints logged as append-only blockquotes in the task body.
Phase 1 lands only the **durable-state layer** — the marker format, the
`ait gate`/`ait gates` CLI to append and derive state, the `gates:` frontmatter
field, a minimal registry, and the sidecar-log convention — with **zero behavior
change** anywhere else. No orchestrator, no verifiers, no task-workflow change
(those are t635_2/t635_11+). Everything here is the substrate that later phases
build on, so the bar is "correct, durable, and not silently lost".

The contract is fully specified by `aidocs/gates/aitask-gate-framework.md`
(§Data model, §"Gate run marker format", §Tooling) — this plan implements that
contract narrowed to the Phase-1 surface.

## Scope

**In scope (t635_1):**
1. Marker-first Gate Runs block format + back-to-front state derivation (bash+awk
   primary, Python-stdlib fallback).
2. `ait gate append`, `ait gates status`, `ait gates list` — and **only** these.
3. Register the `gates:` frontmatter field so it survives `ait update`/`ait create`/fold.
4. Minimal `aitasks/metadata/gates.yaml` registry (name, type, description only).
5. Sidecar log dir convention `.aitask-gates/<task-id>/` + gitignore default.
6. Self-contained bash tests.

**Out of scope (later children):** orchestrator + verifier contract (t635_11),
`ait gate pass/fail/run/unlocked/log` subcommands (t635_11/_15), checkpoint
recording in task-workflow (t635_2), gate-guarded archival (t635_4), TUI gate
columns / board In-Flight view (t635_9/_10), the shared TUI parser API (t635_8),
remote projection (t635_16), comprehensive website docs (t635_18).

---

## Key design decisions (rationale + rejected alternative)

These are the scope boundaries worth your sign-off — each is a deliberate call,
not an oversight.

1. **Single Python module, positioned for t635_8 (no fork).**
   The Phase-1 "stdlib fallback" lives in `.aitask-scripts/lib/gate_ledger.py`
   as an **importable module + CLI**, not an inline throwaway. The bash path is
   primary; it delegates to this module when `AIT_GATES_BACKEND=python` or when
   awk parsing fails (the framework doc's escape-hatch rule). t635_8 (shared TUI
   parser) then **extends** this same module instead of forking the derivation
   logic — honoring the roadmap's "TUIs must not fork the logic" rule.
   *Rejected:* a one-off fallback that t635_8 would have to replace/duplicate.
   *Constraint:* stdlib only (no PyYAML) — the registry/markers are parsed with
   `re`, not a YAML lib, so the fallback works even where PyYAML is absent.

2. **Register `gates:` in the write path = mandatory, not gold-plating.**
   `aitask_update.sh` **reconstructs** frontmatter from a hardcoded positional
   field list (`write_task_file`, ~24 params) and **silently drops any
   unregistered field**. A gated task routinely passes through `ait update`
   (status/assignment changes during the normal workflow, board edits). Without
   registration, `gates:` would be wiped on the next update. So parse+serialize
   of `gates:` in `aitask_update.sh` and `aitask_create.sh` is required for
   durability. (The board's PyYAML `serialize_frontmatter` already round-trips
   unknown keys — but update.sh does not, and that's the live hazard.)

3. **Defer the board edit *widget* to t635_9.**
   The board preserves `gates:` on round-trip already (verified: `task_yaml.py`
   `serialize_frontmatter` keeps all keys). A per-field **edit** widget
   (`GatesField` in `TaskDetailScreen`) is only needed to hand-edit gates in the
   TUI — which Phase 1 never does (gates are populated programmatically later).
   The natural home for gate UI is the action-grouped In-Flight view (t635_9).
   *Rejected:* adding the widget now — dead UI in Phase 1, and it would belong to
   t635_9's design anyway. (Field durability is fully covered by decision #2.)

4. **Seed the registry with the 5 Phase-1 checkpoint gates.**
   The roadmap Phase-1 bullet names exactly the checkpoints task-workflow will
   record in t635_2: `plan_approved`, `review_approved`, `merge_approved`,
   `build_verified`, `risk_evaluated`. Seed these with `type` + `description`
   only (verifier/retries/unlocks come with t635_11). This gives `ait gates list`
   real content to enrich and hands t635_2 a ready registry.
   *Rejected:* an empty/example-only registry — leaves `ait gates list`
   untestable and forces t635_2 to invent names already fixed by the roadmap.

5. **Whitelist `aitask_gate.sh` now (forward-looking).**
   Strictly, no SKILL.md references it *in t635_1*. But the script's entire
   purpose is skill/verifier invocation, and the immediate dependent t635_2
   invokes it from task-workflow. Whitelisting now avoids a permission-prompt
   regression the moment t635_2 lands. *Rejected:* deferring to t635_2 (scope-pure
   but guarantees a prompt-regression window). I'll add a reverse coordination
   note to t635_2's definition either way.

6. **No `ait gate`/`ait gates` dispatcher entry in Phase 1 — full-path helper.**
   Per `aitasks_extension_points.md` ("the `ait` dispatcher is user-facing only…
   default to no entry; adding later is trivial, removing it is breaking"):
   `append` is purely programmatic (verifiers + t635_2 checkpoint recording); a
   human never hand-appends a gate-run block. `status`/`list` are conceivable
   human commands but have **no human workflow** until the TUI columns / board
   In-Flight view / `aitask-resume` land (t635_9/_10, t635_6/_7). So
   `aitask_gate.sh` is invoked **by full path** (`./.aitask-scripts/aitask_gate.sh
   <append|status|list>`) from skills/verifiers/tests. The user-facing dispatcher
   surface arrives later **with its first real human command** (most naturally
   `ait gate pass`, t635_15). *Rejected:* adding `ait gate`/`ait gates` now —
   speculative user-facing surface with no human consumer in Phase 1.

---

## Deliverables (file by file)

### 1. Core ledger engine

**`.aitask-scripts/lib/gate_ledger.py`** (new) — importable + CLI, stdlib only:
- `parse_gate_runs(text) -> list[dict]` — scan the `## Gate Runs` section, parse
  each marker line `> **<icon> gate:<name>** key=val …` into `{name,status,attempt,run,...}`.
- `derive_status(text) -> dict[name -> state]` — last marker per gate wins
  (= first when scanning back-to-front).
- `append_block(text, gate, status, fields) -> text` — ensure `## Gate Runs`
  exists at EOF, compute `attempt` (last+1 for that gate) and `run` (ISO-8601-Z)
  if absent, append a marker-first blockquote.
- `__main__` CLI: `append <file> <gate> <status> [k=v…]` | `status <file>` |
  `list <file> [registry]`.

**`.aitask-scripts/aitask_gate.sh`** (new) — bash+awk primary path, invoked **by
full path** (no `ait` dispatcher entry — decision #6). Sources `terminal_compat.sh`
+ `task_utils.sh` (no new sourced lib → no test-scaffold change). Flat
subcommands `append` / `status` / `list`:
- `append <task-id> <gate> <status> [attempt=N] [run=ISO] [duration=Ns] [verifier=…] [type=human] [log=path] [k=v…]`
  - Resolve file via `resolve_task_file` (task_utils).
  - **Lock:** mkdir lock (portable; mirror `acquire_child_lock`/`release_child_lock`
    in `aitask_create.sh:237-267`) on `/tmp/aitask_gate_lock_<sanitized-task-id>`,
    with stale-lock reclaim.
  - Read-modify-write via awk to a tempfile, then write back **symlink-safely**
    (task files are symlinks into `.aitask-data/`; match the write-back mechanism
    `aitask_update.sh` uses so the symlink is preserved, not replaced by `mv`).
    Do **not** use `readlink -f` (GNU-only); canonicalize via
    `cd "$(dirname "$f")" && pwd -P` or write through the symlink.
  - Marker format per framework doc §"Gate run marker format": first line
    `> **<icon> gate:<name>** run=… status=… [attempt=…] [duration=…] [type=…]`,
    blank `>` separator, body lines (`Verifier:`/`Result:`/`Log:`), block
    terminated by next `> **` / next `##` / EOF. Icon derived from status
    (✅ pass, ❌ fail, ⏸ pending, 🔄 running, ⏭ skip, ⚠ error).
- `status <task-id>` — print derived per-gate state (awk scan; delegates to
  `gate_ledger.py` on `AIT_GATES_BACKEND=python` or awk failure).
- `list <task-id>` — read declared gates from frontmatter (`read_yaml_list`
  from `yaml_utils.sh`), enrich each with `type`/`description` from the registry
  (small awk reader of the 2-level `gates.yaml`).
- `--help` for the script; unknown subcommands error clearly (so later phases’
  `pass/fail/run/unlocked/log` slot in without surprising callers today).

**`ait` dispatcher — no change** (decision #6). `aitask_gate.sh` is a full-path
helper in Phase 1; the user-facing `ait gate`/`ait gates` surface is added later
with its first real human command (e.g. `ait gate pass`, t635_15).

### 2. `gates:` frontmatter registration (durability)

- **`aitask_update.sh`**: add `gates)` parse case (`CURRENT_GATES=$(parse_yaml_list …)`,
  ~line 432 alongside `labels`); add a `--gates "a,b,c"` batch flag (replace
  semantics, mirror `--labels`); thread `CURRENT_GATES` through `write_task_file`
  as a new param + emit the `gates:` serialization line. **The parse+serialize is
  the load-bearing part** (preserves the field even when `--gates` isn't passed).
- **`aitask_create.sh`**: add `--gates` batch flag + emit `gates:` in
  `create_task_file` serialization (parity; lets default_gates be applied later).
- **`aitask_fold_mark.sh`**: union `gates:` across folded tasks into the primary
  (list-field union, per extension-points "Fold machinery").

### 3. Minimal registry

- **`aitasks/metadata/gates.yaml`** (new) + **`seed/gates.yaml`** (new): documented
  2-level schema; the 5 checkpoint gates (decision #4) with `type` + `description`
  only; comment noting verifier/retries/unlocks arrive with t635_11.
- **`install.sh`**: add `install_seed_gates_registry()` (model on
  `install_seed_project_config`, `merge_seed yaml`) + call it in `main()` near the
  other metadata seeds (~line 968).
- **`aitask_setup.sh`**: add `seed/gates.yaml` to the data-branch metadata copy
  list (~line 1272) so it lands in `.aitask-data/aitasks/metadata/`.

### 4. Sidecar logs + gitignore

- Root **`.gitignore`**: add `.aitask-gates/` (this repo, dogfooding).
- **`aitask_setup.sh`**: add `setup_gate_logs_gitignore()` (clone of
  `setup_python_cache_gitignore`, line ~1547) appending `.aitask-gates/` to the
  user's root `.gitignore` for fresh installs; wire into the setup flow.
- `ait gate append` records a `log=` field when given; it does **not** itself
  write log files in Phase 1 (verifiers do, in t635_11). Provide a path-convention
  helper only.

### 5. Whitelist (decision #5)

Add `aitask_gate.sh` to every allowlist touchpoint per the extension-points table
(`aidocs/framework/aitasks_extension_points.md` §"Adding a new helper script"):
runtime `.claude/settings.local.json` + `.codex/rules/default.rules`, and seed
mirrors `seed/claude_settings.local.json` + `seed/codex_rules.default.rules` +
`seed/opencode_config.seed.json` (+ runtime opencode config if present). Verify
the exact set against the table during implementation.

### 6. Tests (`tests/*.sh`, self-contained, asserts.sh helpers)

- **`test_gate_ledger.sh`** — append creates section; second append for same gate
  → latest wins; multi-gate derivation; pending/fail/pass states; attempt
  auto-increment; **awk vs `gate_ledger.py` parity** on the same fixtures;
  symlink-preserving write.
- **`test_gate_cli.sh`** — `ait gate append` / `gates status` / `gates list`
  end-to-end on a fixture task (incl. registry enrichment); unknown-subcommand
  error.
- **`test_gate_frontmatter_roundtrip.sh`** — regression for decision #2:
  `ait update <task> --status X` on a task carrying `gates:` **preserves** it;
  `--gates` flag write; fold union of `gates:`.
- Confirm existing `tests/test_update_*.sh`, `test_yaml_utils.sh`,
  `test_parallel_child_create.sh` still pass.

### Docs

Defer the comprehensive website sweep to **t635_18** (current-state-only rule).
In t635_1: `ait help` + `aitask_gate.sh --help` only. No new website page (so no
`_index.md` bullet needed). No edits to the `aidocs/gates/` design docs (they are
the contract).

---

## macOS portability (the awk path is the live concern)

macOS ships BSD/`nawk`, not GNU `gawk`; gawk-only constructs are **hard syntax
errors** under BSD awk (script fails to parse), not silent no-ops — and this is
exactly the class that broke `aitask_skill_resolve_profile.sh` in t931. The
marker parser in `aitask_gate.sh` must stay **POSIX-awk only**
(`aidocs/framework/sed_macos_issues.md` §"awk macOS Incompatibilities"):

- **Allowed:** `~`, `sub()`, `gsub()`, `split()`, `substr()`, **2-arg** `match($0, /re/)`
  with `RSTART`/`RLENGTH`, `index()`, char classes `[[:space:]]`.
- **Forbidden:** **3-arg** `match(str, re, arr)` capture form, `gensub()`,
  `\<`/`\>` word boundaries.
- **Marker parse pattern** (POSIX-safe): extract gate name via
  `match($0, /gate:[A-Za-z0-9_]+/)` → `substr($0, RSTART+5, RLENGTH-5)`; extract
  `status=…`/`attempt=…`/`run=…` the same way (2-arg match + substr, or `split()`
  on whitespace tokens then `split(tok, kv, "=")`). No capture arrays anywhere.
  Follow the t931 rewrite of `aitask_skill_resolve_profile.sh` as the precedent.

Other BSD-vs-GNU primitives used by this task:
- `mktemp` — template form only: `mktemp "${TMPDIR:-/tmp}/aitask_gate_XXXXXX"` (no `--suffix`).
- `date` — `date -u +%Y-%m-%dT%H:%M:%SZ` is portable (no `-d` → no `portable_date` needed).
- `stat` — mkdir-lock stale check uses `stat -c %Y … || stat -f %m …` (both forms), per `acquire_child_lock`.
- `wc -l` — trim padding (`tr -d ' '`/`xargs`) before any string compare in tests.
- `sed` — use `sed_inplace` and `sed -E` for any `?`/`+`/`|`; never `grep -P`.

**Dev box is Linux** (BSD awk not locally runnable), so macOS safety is enforced
**by construction** (POSIX-only) plus the static sweep in Verification. If the
parser grows complex, the Python fallback (`gate_ledger.py`) is the escape hatch;
a macOS smoke can be named as a manual-verification follow-up.

---

## Risk

### Code-health risk: medium
- Editing `aitask_update.sh` `write_task_file` (positional reconstruction on a
  load-bearing path) risks corrupting frontmatter on **all** task updates, not
  just gated ones · severity: medium · → mitigation: in-task — `test_gate_frontmatter_roundtrip.sh`
  + full existing `test_update_*` suite must stay green.
- Symlink-safe write-back to `.aitask-data` task files (naive `mv` would replace
  the symlink with a regular file) · severity: medium · → mitigation: in-task —
  match update.sh's write mechanism; explicit symlink test.
- Wide-but-shallow blast radius (dispatcher, install/setup, whitelist 5+ files) ·
  severity: low · → mitigation: each change mirrors an established pattern.

### Goal-achievement risk: medium
- awk marker-parsing correctness across edge cases (multiline body with `>`,
  back-to-front derivation, block boundaries) **and BSD-awk portability** (3-arg
  `match()` would be a hard syntax error on macOS) · severity: medium ·
  → mitigation: in-task — POSIX-awk-only by construction + static sweep (see
  macOS section); bash↔python parity tests; Python fallback escape hatch.
- 2-level `gates.yaml` parsing in bash (nested map) is fiddly · severity: low ·
  → mitigation: strict documented schema; minimal (type/description lookup only).

### Planned mitigations
None — the identified risks are bounded and fully mitigated **in-task** by the
test deliverables above; no separate before/after mitigation tasks are warranted.

---

## Verification

1. `shellcheck .aitask-scripts/aitask_gate.sh` (and edited `aitask_*.sh`).
2. New tests: `bash tests/test_gate_ledger.sh && bash tests/test_gate_cli.sh && bash tests/test_gate_frontmatter_roundtrip.sh`.
3. Regression: `bash tests/test_update_landing.sh tests/test_update_risk.sh tests/test_yaml_utils.sh tests/test_parallel_child_create.sh` (run each).
4. Manual smoke on a scratch task (full-path helper):
   `./.aitask-scripts/aitask_gate.sh append <id> tests_pass pass` →
   `./.aitask-scripts/aitask_gate.sh status <id>` shows `tests_pass: pass`; append
   `fail` then `pass` → latest wins; `… list <id>` shows declared gates + registry
   descriptions.
5. Durability: add `gates: [tests_pass]` to a task, run `ait update <id> --status Editing`,
   confirm `gates:` survives.
6. Fresh-install flow (per extension-points "Test the full install flow"):
   `bash install.sh --dir /tmp/scratchgate` then confirm `aitasks/metadata/gates.yaml`
   and the `.aitask-gates/` gitignore entry are present.
7. Skill-surface guard: `./.aitask-scripts/aitask_skill_verify.sh` is unaffected
   (no skill files changed); whitelist entries present in all touchpoints.
8. macOS static sweep (must return **no hits** in the new/edited scripts):
   `grep -rnE "match\([^,]+,[^,]+,[^)]+\)" .aitask-scripts --include='*.sh'` (3-arg
   match), plus the `sed \?`/`grep -P`/`mktemp --suffix` checks from
   `sed_macos_issues.md` §"After fixing one portability bug, sweep…".

## Coordination
- Add a reverse pointer in **t635_2** noting `aitask_gate.sh append` (full path)
  and the registry are available, that the whitelist already landed here, and that
  the user-facing `ait gate`/`ait gates` dispatcher surface is intentionally
  deferred to a phase with a real human command (bidirectional-link convention).
- Note for **t635_8**: extend `lib/gate_ledger.py` (do not fork).

## References
- `aidocs/gates/aitask-gate-framework.md` — §Data model, §"Gate run marker format", §Tooling
- `aidocs/gates/integration-roadmap.md` — Phase 1, D1/D6, child table
- `aidocs/framework/aitasks_extension_points.md` — new field / new helper / install flow
- `aidocs/framework/sed_macos_issues.md` — awk/sed/mktemp/date BSD-vs-GNU rules
- `aidocs/framework/shell_conventions.md` — shebang, `set -euo pipefail`, sed_inplace, test-scaffold rule
- Reuse: `resolve_task_file`, `read_yaml_list` (task_utils/yaml_utils);
  `acquire_child_lock`/`release_child_lock` (aitask_create.sh:237);
  `merge_seed` + `install_seed_*` (install.sh); `setup_python_cache_gitignore`
  (aitask_setup.sh:1547).

## Final Implementation Notes

- **Actual work done:** Built the ledger engine (`lib/gate_ledger.py` importable
  + CLI; `aitask_gate.sh` bash+POSIX-awk primary path with mkdir-lock and atomic
  same-dir write); registered `gates:` in the write path (`aitask_update.sh`
  parse+serialize+`--gates`, `aitask_create.sh` `--gates` on all 3 creation
  paths, `aitask_fold_mark.sh` union); seeded `gates.yaml` (5 checkpoint gates)
  via `install_seed_gates_registry` + setup data-branch copy; sidecar gitignore
  (`.aitask-gates/`, root + `setup_gate_logs_gitignore`); whitelisted
  `aitask_gate.sh` across all 5 allowlist touchpoints; two test suites
  (`test_gate_ledger.sh` 27/27, `test_gate_frontmatter_roundtrip.sh` 9/9).

- **Deviations from plan:**
  - **create `--gates` also added to `create_draft_file`** (not just
    `create_task_file`). Discovered the batch-create flow is draft→finalize, and
    `finalize_draft` `sed`-copies the draft (it never calls `create_task_file`),
    so `--gates` would have been silently lost on the common path otherwise.
  - **Board edit widget deferred** (decision #3 confirmed): the board's PyYAML
    `serialize_frontmatter` already round-trips `gates:`; the gate UI belongs to
    t635_9.
  - **Tests consolidated 3→2 files** (engine+CLI merged into `test_gate_ledger.sh`)
    to avoid redundant coverage; durability/registration in the roundtrip file.
  - **No `ait` dispatcher entry** (decision #6, from plan review): full-path
    helper only; the user-facing `ait gate`/`ait gates` surface lands later with
    its first real human command (e.g. `ait gate pass`, t635_15).

- **Issues encountered:**
  - My own portability guard false-positived: a 2-arg `match()` and a `substr()`
    on the *same awk line* matched the (loose, documented) 3-arg-match sweep
    regex. Fixed by splitting match/substr onto separate lines — keeps the
    documented sweep clean and is no real 3-arg match.
  - update.sh resolves task files relative to cwd/data-worktree; tests must run
    from inside the temp dir with a relative `TASK_DIR` (how `ait` invokes it),
    not an absolute `TASK_DIR` from another repo root.
  - Full `install.sh` end-to-end run isn't feasible in-sandbox (dies early in
    pre-existing `confirm_install`/download machinery, before extraction).
    Verified the gate seed via `install.sh --source-only` + direct
    `install_seed_gates_registry` call instead (gates.yaml installs correctly).

- **Key decisions:** marker/derivation format is byte-identical between the awk
  and python paths (parity-tested) so the fallback is a true drop-in; `gates:`
  is omitted (never `[]`) when empty to keep Phase-1 "no behavior change"; the
  registry is a strict 2-level YAML parsed with POSIX awk / stdlib `re` (no
  PyYAML, so the fallback works without it).

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t635_2** (checkpoint recording): call `./.aitask-scripts/aitask_gate.sh
    append <id> <gate> <status> [k=v...]` (full path — no `ait gate` dispatcher
    entry yet; it whitelisted across all 5 touchpoints here). Supported keys:
    marker = run/attempt/duration/type, body = verifier/result/log/note. The 5
    seeded checkpoint gates (`plan_approved`, `risk_evaluated`, `build_verified`,
    `review_approved`, `merge_approved`) are ready to record against.
  - **t635_8** (shared TUI parser): extend `lib/gate_ledger.py`
    (`parse_gate_runs`/`derive_status`) — do NOT fork the derivation logic.
  - Derivation = last marker per gate wins; markers matched anywhere (not only
    inside `## Gate Runs`), so a missing section header never loses runs.
  - awk must stay POSIX (2-arg `match`+`substr` on *separate lines*; no 3-arg
    `match`, no `gensub`). A static guard test enforces this.
