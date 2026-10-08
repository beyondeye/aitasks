---
Task: t1910_superseded_default_model_upgrade_prompt.md
Base branch: main
Output branch: main
---

# t1910 — Offer newer models for superseded code-agent defaults on upgrade

## Context

`ait upgrade` runs the target version's `install.sh --force`, whose
`merge_seed json` keeps every existing `.defaults[op]` value (dest wins). A user
who installed when the default was `claudecode/opus5` keeps `opus5` forever, even
after the framework promotes `opus5_5`. Nothing records *which* model a promotion
replaced, so the framework cannot tell a stale default from a deliberate choice.

Goal: record "model A is superseded by model B" per agent, and at upgrade time
(tty) ask **one confirm per superseded model per config layer** to switch the ops
that use it. Ops set to a non-superseded model are never touched. A declined
switch is remembered and not re-asked until the offered target changes.

## Design decisions

1. **Supersession data is framework-owned code**, not user metadata:
   `.aitask-scripts/lib/model_supersessions.json`. JSON rather than a `.py` dict
   because `aitask_add_model.sh` machine-writes it; precedent for JSON data in
   `lib/`: `implementation_trail.schema.json`. It ships in the release tarball's
   `.aitask-scripts/` and is replaced by extraction on every upgrade — no merge
   change, no seed→metadata step, available to on-demand runs downstream (where
   `seed/` is deleted). Same ownership model as `DEFAULT_AGENT_STRING`.
   ```json
   {
     "version": 1,
     "agents": {
       "claudecode": { "opus5": {"by": "opus5_5", "source": "t1865 ff667f89e"} },
       "codex":      { "gpt6_sol": {"by": "gpt6_1_sol", "source": "t1886 95f0394cb"} }
     }
   }
   ```
   Canonical format = `json.dumps(indent=2, ensure_ascii=False)` + `\n`, keys in
   insertion order; hand-written and machine-written forms must match (tested).
   One successor per model → deterministic chains. Same-agent only: cross-agent
   supersession is out of scope (users on `shadow: claudecode/opus5` are offered
   `opus5_5`, not the framework's current `codex/gpt6_1_sol`).
2. **Chain resolution**: follow `by` links; a revisited node raises
   `SupersessionCycle` (that model is skipped with a warning). The offered target
   is the **furthest node in the chain registered and not `status: unavailable`**
   in the project's `aitasks/metadata/models_<agent>.json`; none → no offer.
3. **Supersession is a global declaration, and the seed never contradicts it.**
   An edge `A → B` means "every op using A, in every layer, is offered B".
   **Seed invariant:** no default in `seed/codeagent_config.json` names a model
   that has a successor (so the framework never ships a default it declares
   obsolete, and a fresh config yields no offers). Every table write re-checks
   it against the post-write seed, and a contract test checks the shipped table.
4. **Promotion policy** (`promote-config`, unless `--no-supersession`):
   predecessors = the old seed values of the ops whose seed value changes
   (same agent, ≠ new). Per predecessor A:
   - A still named by another seed op after the patch →
     `BLOCKED:partial:<a>/<A>|<remaining ops>` — a partial promotion cannot
     declare a global supersession without breaking the invariant;
   - A already has a successor X ≠ B → `BLOCKED:conflict:<a>/<A>-><a>/<X>`
     (existing edges are **never** overwritten);
   - the edge would close a cycle → `BLOCKED:cycle:…`;
   - B is not registered in `aitasks/metadata/models_<agent>.json` →
     `BLOCKED:unregistered:<a>/<B>` (an edge must point at a model the check can
     offer);
   - `A → B` already recorded → `SKIPPED:exists` (idempotent);
   - otherwise `RECORDED:<a>/<A>-><a>/<B>` (+ `WARN:family` when the leading
     `[a-z]+` of the names differ).
   Cross-agent old values → `SKIPPED:cross_agent:<value>` (not lineage, never
   blocking). **Any `BLOCKED` refuses the apply before any file is written**,
   naming the resolutions: add the remaining ops to `--ops`, or re-run with
   `--no-supersession` (promote without declaring lineage — partial promotions
   stay fully supported) and later declare it with the new explicit
   `record-supersession` subcommand once A is retired. `--dry-run` prints the
   diffs and the `BLOCKED` lines and exits 0 (it is a preview).
   **Previewing a not-yet-registered target.** The skill previews
   `add-json --dry-run` and then `promote-config --dry-run` for the *same new*
   model, and the first preview writes nothing, so the registration guard would
   reject every add-and-promote preview. `promote-config --dry-run
   --assume-registered` validates against the registry **plus the target**
   and prints `NOTE:assumes_registration:<a>/<B>`. The flag is accepted **only
   with `--dry-run`** (usage error otherwise): an apply, and
   `record-supersession` (preview or apply), always validate against the real
   registry — on apply `add-json` has already run, in the skill's fixed order.
   `record-supersession --agent a --old A --new B` applies the same guards
   (seed invariant, conflict, cycle, B registered) and writes only the table.
5. **`_1m` sibling rule** (derived, applied only when a base→base edge `A → B`
   is recorded): also record `A_1m → B_1m` when it is **eligible** — both
   siblings registered, `A_1m` not named by any seed default, `A_1m` has no
   successor yet, and the edge closes no cycle. An ineligible sibling never
   blocks; it is reported (`SKIPPED:sibling_unregistered|sibling_in_seed|
   sibling_conflict|sibling_cycle`) and not written. One function,
   `sibling_eligibility()`, decides this for both the recorder and the
   completeness contract, so an intentional skip is never reported as missing.
   A sibling that becomes eligible later (e.g. `B_1m` registered after the
   promotion, or `A_1m` retired from the seed) is added with
   `record-supersession`; the contract flags it until then. A variant↔base edge
   the framework actually promoted is recorded as promoted.
6. **Backfill** = the net lineage, each edge verified in
   `git log -p -- seed/codeagent_config.json`; it satisfies the invariant
   against today's seed. (t1865 was partial when it landed — shadow/discuss left
   `opus5` for codex in t1866 — so under the new policy it would have been
   recorded via `record-supersession` after t1866.)
   | agent | old → new | source |
   |---|---|---|
   | claudecode | opus4_6 → opus4_7_1m | t579_3 dd9a2efe6 |
   | claudecode | opus4_7_1m → opus4_8 | t853 80ba0e137 |
   | claudecode | opus4_8 → opus5 | t1241 1dd5b32ae |
   | claudecode | opus4_8_1m → opus5_1m | `_1m` sibling of t1241 |
   | claudecode | sonnet4_6 → sonnet5 | t1242 c76b0bb94 |
   | claudecode | opus5 → opus5_5 | t1865 ff667f89e (net of t1866 131707d06) |
   | claudecode | opus5_1m → opus5_5_1m | `_1m` sibling of t1865 |
   | claudecode | sonnet5 → sonnet5_5 | t1886 95f0394cb |
   | codex | gpt6_sol → gpt6_1_sol | t1886 95f0394cb |
   Not recorded: t1866 `claudecode/opus5 → codex/gpt6_sol` (cross-agent); models
   never a framework default (opus4_5, haiku, fable, gpt5_x, all opencode).
7. **Layers**: `codeagent_config.json` (project, tracked) and
   `codeagent_config.local.json` (user, gitignored); **every** key under
   `.defaults` is scanned (brainstorm-* included). Same superseded model in both
   layers → one question per layer. Malformed values / missing `defaults` /
   unparseable file → skipped with a warning, never fatal.
8. **"Keep" memory lives in the git dir, not under `aitasks/`**:
   `<git-common-dir>/ait-codeagent-supersession-kept.json` (resolved with
   `git -C <root> rev-parse --path-format=absolute --git-common-dir`; precedent:
   `aitask_sync.sh` `<gitdir>/ait-sync-quarantine`). Under `aitasks/metadata/` it
   would be committed by the next legacy-mode upgrade (`*.local.json` is ignored
   only in the data branch's `.gitignore`). Shape:
   `{"project": {"claudecode/opus5": "claudecode/opus5_5"}, "local": {}}` — the
   **offered target** at decline time; suppressed while the same target is
   offered, re-asked when a different one is. Not a git repo → no memory (said so).
9. **Prompt**: `[Y/n]` (matches the installer's "Proceed with upgrade? [Y/n]").
   EOF or Ctrl-C stops asking, applies only what was already accepted, records
   nothing for unanswered offers, exits 0.
10. **When it runs**: `install.sh`, only for an existing install
    (`EXISTING_INSTALL=true`), **after** `commit_installed_files` /
    `commit_installed_data_files` so an interrupted prompt cannot strand the
    framework update and the switch gets its own commit. tty → interactive;
    non-tty (`curl | bash`, CI) → report with `</dev/null` (never reads stdin,
    which under `curl | bash` is the script) plus the re-run hint. On demand:
    `ait codeagent check-superseded [--report]`. Not wired into `ait setup`; the
    docs state that teammates' **local** layers are checked only when each user
    runs the verb.
11. **Interpreter**: `install.sh` uses `resolve_python`, which exists only after
    `main()` sources `.aitask-scripts/aitask_setup.sh --source-only` (it is
    absent after `install.sh --source-only` alone); the function guards with
    `declare -F resolve_python` and warns + skips if missing. The CLI is
    **stdlib-only** (writes via `lib/atomic_write.py`, commits via
    `lib/metadata_commit.py`; no `config_utils`, which imports yaml), Python ≥ 3.7.
12. **Commit**: project-layer switch only, and only when safe to attribute: root
    is a git work tree **and** `preflight_metadata` (before our write) reports the
    file `clean` with no `MIDOP`. Then `commit_metadata(..., expect={rel: <copy of
    our bytes>}, env=<TASK_DIR/METADATA_DIR scrubbed>, timeout=60)`. Every status
    handled (`committed`, `nochange`, `skipped`, `refused`, `raced`, `failed`);
    otherwise the file is written and reported "left uncommitted (<reason>)" with
    `cd <root> && <remedy_command>` where a remedy applies. Never raises. The
    local layer is never committed.

## Implementation steps

1. **`.aitask-scripts/lib/model_supersession.py`** (new, stdlib-only):
   - `load_table(path)` (missing → empty), `successor()`,
     `resolve_chain(table, agent, name) -> list[str]` (raises `SupersessionCycle`),
     `offer_target(table, agent, name, available) -> str | None`,
     `render_table(table) -> str` (canonical).
   - `parse_agent_string(value)` → `(agent, name)` or `None`
     (`^[a-z]+/[a-z][a-z0-9_]*$`); `load_registry(models_json) -> set[str]`.
   - `Offer(layer, agent, old, new, ops)`; `find_offers(layer, defaults, table,
     registries) -> (offers, warnings)`: ops grouped by `(agent, old)` in config
     order, offers sorted by `(agent, old)`.
   - `seed_violations(table, seed_defaults) -> list[(op, agent, name)]`
     (invariant check, Design §3).
   - `sibling_eligibility(table, agent, base_old, base_new, seed_defaults,
     available) -> (eligible: bool, reason)` and
     `missing_sibling_edges(table, seed_defaults, registries)` (eligible but
     absent; Design §5).
   - `plan_promotion(table, agent, new, seed_before, seed_after, available,
     source) -> (table, events, blocked: bool)` and
     `plan_explicit(table, agent, old, new, seed, available, source)` — both
     implement Design §4–§5 through one edge-adding core, so the guards cannot
     diverge. `available` is passed in by the caller; the preview's
     "registry + target" is built by the CLI, not by the core.
   - Keep memory: `is_kept(kept, offer)`, `with_kept(kept, offer)`.
2. **`.aitask-scripts/aitask_model_supersession.py`** (new CLI, stdlib-only;
   `sys.path` gets `lib/`; top-level `KeyboardInterrupt` → exit 0 after applying
   accepted answers):
   - `check --root DIR [--interactive] [--porcelain] [--no-commit]` — table =
     the script's own `lib/model_supersessions.json`; metadata =
     `<root>/aitasks/metadata`; project layer first, then local. Report mode never
     touches stdin; human lines plus `Run 'ait codeagent check-superseded' in a
     terminal to review them.`; `--porcelain`:
     `OFFER:<layer>|<a>/<old>|<a>/<new>|<ops csv>`, `KEPT:…`, `NONE`. Interactive:
     "Your <layer> defaults for pick, explore, learn use claudecode/opus5, which is
     superseded by claudecode/opus5_5. Switch? [Y/n]"; invalid input re-asks; per
     layer writes only the accepted ops (`atomic_write.atomic_write_text`, mode
     preserved); "n" → keep memory; project commit per Design §12 unless
     `--no-commit`. Writers are separate functions (`_write_project_layer`,
     `_write_local_layer`, `_write_kept`) so the inventory can pin them.
   - `record --table P --output P --models P --agent A --new B
     (--seed-before P --seed-after P | --old X --seed P) [--assume-registered]
     [--source TEXT]` — writes the proposed table (canonical) to `--output`,
     prints events; exit 0 when nothing is blocked, **3** when any `BLOCKED:`
     line was printed. `--assume-registered` adds `--new` to the available set
     and prints `NOTE:assumes_registration:…`.
   - Exit 1 on I/O/parse error, 2 on usage.
3. **`.aitask-scripts/lib/model_supersessions.json`** (new): Design §6 table.
4. **`install.sh`**: `check_superseded_model_defaults()` with a header comment
   (why after the commits, why `</dev/null`, why `resolve_python`):
   `[[ "$EXISTING_INSTALL" == true ]] || return 0`; helper missing → `return 0`;
   `declare -F resolve_python >/dev/null` else warn + `return 0`;
   `py="$(resolve_python)"` empty → warn + `return 0`; `trap ':' INT`; tty →
   `"$py" "$helper" check --root "$INSTALL_DIR" --interactive`, else same without
   `--interactive` and with `</dev/null`; failure → `warn` naming
   `ait codeagent check-superseded`; `trap - INT`; `return 0`. Called in `main()`
   right after `commit_installed_data_files`, after
   `info "Checking for superseded code-agent model defaults..."`.
5. **`.aitask-scripts/aitask_codeagent.sh`**: `check-superseded [--report]` verb
   (`cmd_check_superseded`; `require_ait_python` is already available via
   `lib/task_utils.sh`; root = `$SCRIPT_DIR/..`; `--interactive` when `[[ -t 0 ]]`
   and not `--report`); `show_help` Commands + Examples; dispatcher `case`.
6. **`.aitask-scripts/aitask_add_model.sh`**:
   - Source `lib/python_resolve.sh` at column 0 with the other sources.
   - Fix `print_diff` to take `<label> <current_file> <proposed>`: today it tests
     and diffs the repo-relative path against the **cwd**, so with
     `AITASK_REPO_ROOT` set the dry-run diffs the wrong file. Update all callers.
   - `promote-config`: after computing `tmp_metadata` / `tmp_seed` and **before
     any `commit_staged`**, unless `--no-supersession`: no seed →
     `SKIPPED:no_seed`, table untouched; else `require_ait_python` and run
     `record --seed-before "$seed_file" --seed-after "$tmp_seed"` into a temp
     table; echo its events. Exit 3 → apply mode `die`s with the resolution text
     (Design §4) having written nothing; dry-run continues. `--dry-run` → also
     `print_diff` the table; apply → `commit_staged` the table when it differs
     (`cmp -s`) and print `NOTE: commit .aitask-scripts/lib/model_supersessions.json`.
     New flags `--no-supersession` and `--assume-registered` (dry-run only,
     forwarded to `record`; `die` with a usage error without `--dry-run`).
   - New subcommand `record-supersession --agent a --old A --new B [--dry-run]`
     (`record --old … --seed "$seed_file"`; needs a seed; same diff/commit
     pattern; exit 3 → `die` with the blocking reason).
   - Update header comment and `usage`.
7. **`.claude/skills/aitask-add-model/SKILL.md`**: promote mode declares a
   global supersession (meaning for upgrading users); `--no-supersession`; Step 3
   — in add-and-promote mode the `promote-config --dry-run` call carries
   `--assume-registered` (the preceding `add-json --dry-run` wrote nothing; the
   Step 4 apply call never carries it); relay `RECORDED`/`WARN:family`/`SKIPPED`
   lines, and on `BLOCKED:partial`
   ask (AskUserQuestion) "Also promote <remaining ops>" (re-run the dry-run with
   the extended `--ops`) / "Promote without recording supersession"
   (`--no-supersession`) / "Abort"; on `BLOCKED:conflict|cycle` offer only the
   last two; Step 4 — promote-mode option "Apply without recording
   supersession"; Step 6 — main-branch group `git commit -m "ait: Record
   <agent>/<name> supersession" -- .aitask-scripts/lib/model_supersessions.json`
   when changed; Notes bullet on `record-supersession`.
8. **`tests/test_metadata_writer_inventory.py`**: pin
   `aitask_model_supersession.py::_write_project_layer` in `WIRED` with seam
   `"commit_metadata("`; `::_write_local_layer` in `KNOWN_UNCOMMITTED`
   ("user layer, gitignored"); pin `_write_kept` too if discovery flags it.
9. **Docs** (current-state only):
   - `website/content/docs/commands/codeagent.md`: `#### check-superseded` + a
     "Superseded model defaults" subsection under Configuration (table, chain,
     per-layer offers, keep memory, upgrade prompt, local layers are per user).
   - `website/content/docs/commands/setup-install.md` `## ait upgrade`: a
     paragraph on the end-of-upgrade offer and non-tty report (`relref` link).
   - `website/content/docs/skills/aitask-add-model.md`: global supersession,
     partial-promotion refusal and its resolutions, `--no-supersession`,
     `record-supersession`.
   - `python3 check_links.py --build` in `website/`.

### Post-phase (risk mitigations)

1. [pty_install_prompt_test] Add `tests/test_install_superseded_prompt_pty.py`
   (unittest, stdlib `pty` + `os.openpty`/`subprocess`; skipped when `pty` is
   unavailable): build a temp legacy-mode git repo with a copied
   `.aitask-scripts/` and a committed `aitasks/metadata/codeagent_config.json`
   holding `pick: claudecode/opus5` plus `models_claudecode.json` registering
   `opus5`/`opus5_5`. Run, with stdin/stdout on the pty slave, the production
   prerequisites in the order `main()` uses them:
   `bash -c '. <repo>/install.sh --source-only; INSTALL_DIR=<tmp>;
   EXISTING_INSTALL=true; source "$INSTALL_DIR/.aitask-scripts/aitask_setup.sh"
   --source-only; check_superseded_model_defaults'` — so the real
   `resolve_python` and prompt path are exercised. Wait (deadline-bounded read
   on the master) for `Switch? [Y/n]`, write `y\n`, wait for exit. Assert: exit
   0; `pick` is now `claudecode/opus5_5`; the last commit touching
   `aitasks/metadata/codeagent_config.json` carries the metadata-commit subject
   and that path is clean. Second case answers `n`: config unchanged and
   `<git-common-dir>/ait-codeagent-supersession-kept.json` records the pair.

## Verification

- `tests/test_model_supersession.py` (new, unittest):
  - lib: multi-hop chain; cycle → skipped + warning; unknown model → no offer;
    furthest-registered target when the terminal is unregistered/unavailable;
    ops grouped per old model; a non-superseded custom default is never offered;
    same model in both layers → one offer per layer; `plan_promotion` /
    `plan_explicit`: complete retirement records, partial → `BLOCKED:partial`
    with remaining ops, existing different successor → `BLOCKED:conflict` and
    table unchanged, cycle → `BLOCKED:cycle`, exists → `SKIPPED:exists`, sibling
    recorded / skipped-not-blocking, family warning, cross-agent skipped.
  - CLI report mode with a never-closed stdin pipe completes under a timeout;
    `record` exit 3 on blocked.
  - CLI interactive in temp git repos (copied `.aitask-scripts/`): `y`/`n` writes
    only the accepted ops and records the keep memory in the git dir; re-run does
    not re-ask; a different target re-asks; EOF mid-prompt exits 0 and applies
    only prior answers; **legacy** and **branch-mode** (`.aitask-data` worktree)
    commits land path-scoped; a project file dirty before the run → written, not
    committed; non-git root → no commit, no `REFUSED` noise, no keep memory;
    local layer never committed.
  - Shipped-table contract: canonical format; no cycles; every name registered in
    `seed/models_<agent>.json`; no family warnings;
    `missing_sibling_edges(table, seed, registries) == []`;
    `seed_violations(table, seed) == []` (fresh configs never get offers).
  - `_1m` completeness under the eligibility rules (synthetic tables): A→B with
    `A_1m` still a seed default → **not** reported (intentional skip accepted);
    `A_1m` already → X → not reported; sibling unregistered or cycle-closing →
    not reported; eligible sibling absent → reported. The same fixtures fed to
    `plan_promotion` produce the matching `SKIPPED:sibling_*` / recorded events,
    proving recorder and contract agree.
  - `aitask_codeagent.sh check-superseded --report` wiring in a temp root.
- `tests/test_add_model.sh`:
  - existing Test 3 and the mode-preservation group promote only `pick` while the
    seed keeps the old model on `explore` — under the new policy those are partial
    promotions, so they pass `--no-supersession` (they test op patching, not
    lineage); a new assertion shows the same call **without** the flag is refused
    with `BLOCKED:partial` and leaves every file byte-identical.
  - **two successive partial promotions from one predecessor** (seed
    pick=explore=trail=A): pick→B and then explore→C are each refused without the
    flag (`BLOCKED:partial` naming the remaining ops, nothing written) and each
    applies with `--no-supersession` leaving the table untouched; the final
    trail→C retires A and records `A→C` (shown in its dry-run first); the seed
    invariant holds after every step.
  - conflict: a pre-seeded `A→B` plus a hand-broken seed still on A → promoting
    A→C is refused with `BLOCKED:conflict`, and `--no-supersession` applies the
    config while the `A→B` edge is unchanged (never overwritten).
  - **add-and-promote preview with an initially absent target** (fixture where
    `opus4_7` is not registered): `add-json --dry-run` then `promote-config
    --dry-run --assume-registered --ops pick,explore` (retires `opus4_6` from the
    fixture seed) prints `NOTE:assumes_registration`, `RECORDED:claudecode/opus4_6->claudecode/opus4_7`
    and the `+++ b/.aitask-scripts/lib/model_supersessions.json` diff, and the
    fixture checksum is unchanged. The same preview without the flag shows
    `BLOCKED:unregistered`; an apply with the target still unregistered is
    refused with every file byte-identical; `--assume-registered` without
    `--dry-run` is a usage error; `record-supersession --dry-run` for an
    unregistered target is refused (no flag accepted there). After a real
    `add-json`, the apply records the edge.
  - complete promotion records the edge and its `_1m` sibling only when eligible;
    no-seed fixture → `SKIPPED:no_seed`; dry-run prints the
    fixture table's diff and writes nothing; cross-agent value skipped;
    `record-supersession` happy path, and refusal while A is still in seed.
- `tests/test_install_superseded_models.sh` (new):
  - function level: `install.sh --source-only` **plus**
    `aitask_setup.sh --source-only` (as `main()` does), stub helper: non-tty
    path passes `</dev/null`, returns 0 under `set -e` even when the helper
    fails, skipped for a fresh install; without the `aitask_setup.sh` source it
    warns and returns 0.
  - full `install.sh --force --local-tarball` over a legacy-mode fixture
    (`pick: claudecode/opus5`, `explain: claudecode/sonnet5`, custom
    `qa: claudecode/haiku4_5`; stdin `/dev/null`, `timeout`, isolated `HOME`,
    modeled on `tests/test_t644_branch_mode_upgrade.sh`): completes; report lists
    opus5→opus5_5 and sonnet5→sonnet5_5 with the hint; haiku4_5 absent; defaults
    unchanged; table delivered.
- Re-run `tests/test_codeagent.sh`, `tests/test_install_merge.sh`,
  `tests/test_t644_branch_mode_upgrade.sh`, `tests/test_metadata_writer_inventory.py`;
  `shellcheck` on edited scripts; `bash tests/run_all_python_tests.sh --test-dir`
  over the new modules.

## Risk

### Code-health risk: medium
- `install.sh` runs on every downstream upgrade; a hang, a `set -e` abort or stdin consumption under `curl | bash` would break upgrades everywhere · severity: medium · → mitigation: none (addressed in-plan: non-fatal wrapper, `declare -F` guard, `</dev/null`, INT trap, function-level + full-install tests)
- The tty branch of `check_superseded_model_defaults` (`[[ -t 0 ]]` → `--interactive` → prompt → commit) is exercised by no automated test; only the CLI's interactive mode with piped stdin is · severity: low (residual — addressed by inline post-phase pty_install_prompt_test) · → mitigation: inline post-phase pty_install_prompt_test
- A wrong-lineage edge recorded by `promote-config` would ship to every user and steer them toward an unrelated model · severity: low · → mitigation: none (seed-only capture, partial/conflict/cycle refusal, `WARN:family`, dry-run review, `--no-supersession`, shipped-table contract test)
- `promote-config` now refuses partial promotions unless `--no-supersession` is passed — a behaviour change for the skill, its Codex/OpenCode copies (until ported) and existing tests · severity: low · → mitigation: none (refusal names the resolution; Claude skill and tests updated in-plan; port follow-ups suggested)
- A new writer of a tracked metadata file adds commit-attribution logic (preflight + `expect=`) that must stay in step with `aitask_metadata_commit.sh` · severity: low · → mitigation: none (reuses `lib/metadata_commit.py`; pinned in the writer inventory)

### Goal-achievement risk: low
- Supersession is per-model lineage within one agent, so for ops the framework moved across agents (shadow/discuss → codex) users are offered the same-agent successor, not the current framework default · severity: low · → mitigation: none (cross-agent explicitly out of scope; documented)
- Teammates' local layers are only checked when each user runs `ait codeagent check-superseded` · severity: low · → mitigation: none (documented)

### Planned mitigations
- timing: post-phase | name: pty_install_prompt_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tty branch of check_superseded_model_defaults has no automated coverage | desc: pty-driven test of install.sh's interactive prompt path (accept → switched + committed; decline → keep memory recorded)

## Step 9 (Post-Implementation)

Current-branch workflow: commit code + plan per Step 8, then archive with
`aitask_archive.sh 1910`. Follow-ups to suggest: port the `aitask-add-model`
change to `.agents/skills/` and `.opencode/skills/` + `.opencode/commands/`;
Settings TUI surfacing of superseded defaults.
