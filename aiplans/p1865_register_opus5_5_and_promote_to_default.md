---
Task: t1865_register_opus5_5_and_promote_to_default.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1865 — Register `claudecode/opus5_5` and promote it to default

## Context

Claude Opus 5.5 shipped on 2026-09-22 (model ID `claude-opus-5-5`, 1M context,
128K output, adaptive thinking always on, ~40% cheaper than Opus 5). The
framework's model registry does not know about it, and every heavy operation —
task picking, exploration, skill learning, trail building, and the five
brainstorm crew roles — still resolves to `claudecode/opus5`.

This task registers the model and moves those operations, plus the hardcoded
`DEFAULT_AGENT_STRING` fallback, onto it. `opus5` stays registered, so anything
that pins it explicitly keeps working.

### Findings that change the task as written

A full-repo sweep of `opus5` / `claude-opus-5` corrected three points in the
task body:

1. **`tests/test_brainstorm_crew.py` does *not* go red.** Its `FULL_DEFAULTS`
   (lines 300–311) is written into a tmpdir by `_write_full_config`, and all 12
   `get_agent_types` calls pass `config_root=Path(self.tmpdir)`. The assertions
   read back what the test itself wrote. **Leave it alone** — converting it
   would be churn with no signal gained.
2. **`tests/test_codeagent.sh` *is* the red file.** Its fixture copies
   `seed/codeagent_config.json` as the live config, so promoting seed's `pick`
   breaks five literal assertions (lines 115, 117, 118, 167, 175).
3. **`.aitask-scripts/lib/roadmap_run.py` holds a second hardcoded default**
   (lines 280, 562) that `promote-default-agent-string` does not patch. The
   backlog-roadmap skill never passes `--agent-string`, so a published roadmap
   artifact would record `claudecode/opus5` as its generator after the promote.

**No `opus5_5_1m` entry.** Confirmed against the vendor's published model page:
`claude-opus-5-5` is a single model ID with a 1M context window and no `[1m]`
variant. (`opus5_1m` exists because Opus 5 exposed a bracketed 1M suffix; 5.5
does not.)

## Decisions taken

| Question | Decision |
|---|---|
| `opus5_5_1m` variant | Not added — vendor docs show no `[1m]` model ID |
| Ops to move | The 9 currently on `claudecode/opus5` in live metadata |
| Seed `shadow` / `discuss` | **Left on `claudecode/opus5`** — not named in `--ops` |
| `explore-relay` | Doc-only; it has no config key and rides the hardcoded fallback, so it moves for free. No new task |
| Red test fix | Convert to the t1318 derive idiom, not re-pinned literals |

## Implementation

### Phase 1 — Registry and config, via the canonical helper

Drive every automated site through `.aitask-scripts/aitask_add_model.sh`
(atomic tempfile + `jq` validation + `mv`). **Run each with `--dry-run` first
and review the diff.** Do not hand-edit the registry JSON.

```bash
# 1. Register the model (patches aitasks/metadata/ AND seed/ in one call)
./.aitask-scripts/aitask_add_model.sh add-json \
  --agent claudecode --name opus5_5 --cli-id claude-opus-5-5 \
  --notes "Most capable model for long-running agentic coding, 1M context, 128K output, adaptive thinking always on"

# 2. Promote the 9 heavy ops
./.aitask-scripts/aitask_add_model.sh promote-config \
  --agent claudecode --name opus5_5 \
  --ops pick,explore,learn,trail,brainstorm-explorer,brainstorm-synthesizer,brainstorm-module_decomposer,brainstorm-module_merger,brainstorm-module_syncer

# 3. DEFAULT_AGENT_STRING + the resolution-chain help note
./.aitask-scripts/aitask_add_model.sh promote-default-agent-string \
  --agent claudecode --name opus5_5
```

Step 2 patches only keys that already exist per file, so `seed/` receives
`pick`, `explore`, `learn`, `trail` and silently skips the five `brainstorm-*`
keys it does not carry. `shadow` / `discuss` are deliberately unnamed: the live
copy has them on `codex/gpt5_6_terra` and naming them would clobber that.

Step 3 must preserve the `DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-…}"`
parameter-expansion shape — the helper asserts this and dies if its anchor
misses. (This is the one helper step whose success *is* evidence: it greps for
its own anchor after patching and dies when it misses.)

**Run `t1865_readback.sh` (Verification) immediately after this phase, and gate
on its exit status.** Steps 1 and 2 both accept bad input silently — a non-empty
but wrong `--cli-id`, or an op name that matches no key — and report success
either way. A nonzero readback means the promotion is wrong: fix it and re-run;
do not proceed to Phase 2 and do not commit.

### Phase 2 — Manual tail (not covered by the helper)

- **`.aitask-scripts/lib/roadmap_run.py:280, 562`** — swap both
  `claudecode/opus5` literals (the `run()` keyword default and the
  `--agent-string` argparse default) to `claudecode/opus5_5`.
- **`.aitask-scripts/lib/agent_string.sh:9`** — the header comment claims the
  default is `claudecode/opus4_7_1m`, already wrong before this task. Correct it
  to name `claudecode/opus5_5`; it documents the constant rewritten 17 lines
  below.
- **`aidocs/codeagents/claudecode_tools.md:5`** — `**Model:** Claude Opus 5.5
  (`claude-opus-5-5`)`. This file tracks the current `pick` model.
- **`website/content/docs/commands/codeagent.md`** — defaults-table rows for
  `pick` (53), `explore` (55), `explore-relay` (56), `trail` (58), `learn` (63);
  the sample `resolve` output (111, 113, 114 → `claudecode/opus5_5` / `opus5_5`
  / `claude-opus-5-5`); the hardcoded-default line (176); the example config
  (185). Leave the `opus4_6` examples at 17/29/95/124/217 alone — they are
  format illustrations, not default claims.
- **`website/content/docs/tuis/syncer/_index.md:218–220`** — the three legend
  cells, one of which labels `claudecode/opus5 (default)` as "the built-in
  fallback".

Leave alone: `website/content/docs/tuis/frozenagent/_index.md:58` (illustrative
sample row), `tests/test_cross_repo_settings.py` and the other ~20 fixture
suites, `tests/test_shadow_spawn_learner.sh:46` (intentional explicit override),
`verifiedstats` blocks, changelogs, archived tasks/plans.

### Phase 3 — Convert `tests/test_codeagent.sh` to the derive idiom

Mirror `tests/test_codeagent_trail.sh` (the t1318 reference conversion) rather
than re-pinning literals. Source the shared helper after `asserts.sh`:

```bash
. "$PROJECT_DIR/tests/lib/codeagent_defaults.sh"
```

Then, for the three affected tests:

- **Test 5 (`resolve pick`, lines 112–118)** — derive the expectation with
  `codeagent_config_default pick "$PROJECT_DIR/seed/codeagent_config.json"`
  (the fixture copies that file), inject a `DEFAULT_AGENT_STRING` sentinel from
  `codeagent_sentinel_excluding`, and assert with `assert_eq` +
  `codeagent_resolve_field` — **not** `assert_contains_ci`, whose prefix
  matching lets `opus5` match `opus5_1m` / `opus5_5`. Derive the `MODEL:` and
  `CLI_ID:` expectations from the same resolution.
- **Test 11 (line 167)** — cross-check the composed command against `resolve
  pick`'s `CLI_ID` instead of the `claude-opus-5` literal, exactly as
  `test_codeagent_trail.sh:94–98` does.
- **Test 11a (line 175)** — build the expected `DRY_RUN: env
  AITASK_AGENT_STRING=… claude --model …` string from the derived agent string
  and cli_id.

**Do not touch Test 11a-2 (lines 180–208).** It writes its own
`codeagent_config.local.json` pinning `claudecode/opus5` and asserts the same
value on both sides; it stays green because `opus5` remains registered, and its
jq shim is the negative control for a different property.

Update the file's header comment to record the derive contract, as the three
t1318-converted suites do.

**Where the literal `claude-opus-5-5` does and does not belong.** The test
derives, so a future promotion cannot rot it — but a derived expectation agrees
with a typo'd registry ID by construction, since both sides read the same
registry. The exact-ID pin therefore lives in Readback 1, a one-time promotion
check, and **not** in the test file. Do not "strengthen" the test by pinning the
ID there; that would reintroduce exactly what t1318 removed.

### Post-phase (risk mitigations)

Both confirmed inline; they run after Phases 1–3 land.

**P1 — `derive_conversion_negative_control`.** Adopt `codeagent_fixture_metadata`
(from `tests/lib/codeagent_defaults.sh`) inside `test_codeagent.sh`'s
`setup_test_env`, replacing the five hand-written metadata `cp` lines. Trace
before substituting: the helper copies `models_*.json` + `project_config.yaml`
from `aitasks/metadata/` and installs the `config_src` argument as
`codeagent_config.json` — pass `"$PROJECT_DIR/seed/codeagent_config.json"` to
reproduce the current layout exactly. The remaining setup
(`setup_fake_aitask_repo`, script copies, `git init`) is unaffected.

Adopting it brings the `AIT_CODEAGENT_FIXTURE_OMIT_OPS` seam, so the control is
then a single command:

```bash
AIT_CODEAGENT_FIXTURE_OMIT_OPS=pick bash tests/test_codeagent.sh   # MUST fail
```

Record the control command in the file's header comment, as the t1318 suites do.

**P2 — `audit_doc_staleness_note`.** Phase 4 below.

### Phase 4 — Note to t1341

t1341 owns refreshing `aidocs/framework/model_reference_locations.md`. Send it
the sweep findings rather than editing the audit doc here:

```bash
./ait note 1341 --from 1865 --file - <<'EOF'
…roadmap_run.py:280,562 omitted from §3; ~20 unlisted test suites; the
test_brainstorm_crew.py `needed_for_promote` tag is wrong (hermetic fixture);
aitask_brainstorm_init.sh §4 entry no longer has any opus5 reference;
agent_string.sh:9 comment is not grep-findable by model name.
EOF
```

Hedge it as written against this task's SHA. Prefer the `/aitask-note` skill.

## Commit strategy

**Gate: `bash $SCRATCH/t1865_readback.sh` must exit 0 before any commit below.**

Three path-scoped commits (per `aidocs` audit + CLAUDE.md). Never a bare
`./ait git commit` — it takes the whole shared `.aitask-data` index.

1. **Task-data branch** — `./.aitask-scripts/aitask_task_commit.sh -m "ait:
   Register claudecode/opus5_5 and promote to default (t1865)"
   aitasks/metadata/models_claudecode.json
   aitasks/metadata/codeagent_config.json`
2. **main, seed** — `git commit -m "ait: Sync claudecode/opus5_5 to seed
   (t1865)" -- seed/models_claudecode.json seed/codeagent_config.json`
3. **main, code + docs + tests** — `git commit -m "feature: Promote
   claudecode/opus5_5 as the default code agent (t1865)" --
   .aitask-scripts/lib/agent_string.sh .aitask-scripts/aitask_codeagent.sh
   .aitask-scripts/lib/roadmap_run.py aidocs/codeagents/claudecode_tools.md
   website/content/docs/commands/codeagent.md
   website/content/docs/tuis/syncer/_index.md tests/test_codeagent.sh`

Name every path; parse each result per the outcome contract in
`.claude/skills/ait-git-fast-/SKILL.md`, and `git show --stat <sha>` using the
sha from the commit's own `[branch sha]` line, not `HEAD`.

## Verification

**Neither helper's success line is evidence.** `promote-config`'s jq is
`if (.defaults // {}) | has($op) then … else . end`, so a mistyped or absent op
key is skipped *silently* while the command exits 0 and prints
`Promoted … for ops: <the csv I typed>`. And `validate_cli_id()`
(`aitask_add_model.sh:55-58`) checks only that `--cli-id` is non-empty, so a
typo'd ID is stored, resolved, and — because Phase 3 derives its expectation
from that same resolution — agreed with by the test. Both are caught by
re-reading the files, never by the exit status.

The readbacks are **one fail-closed script**, not a sequence of eyeball checks.
Write it to `$SCRATCH/t1865_readback.sh` and run it; its **exit status is the
gate**. A per-line `|| echo "FAIL …"` would not do — `echo` succeeds, so the
block would print `FAIL` and still return 0, and the promotion would sail into
the commits. Every mismatch therefore sets `rc=1` and the script's last
statement is the verdict. Re-run it after any fix; do not pipe it to `tail`
(that discards the status — check `${PIPESTATUS[0]}` if you must).

```bash
#!/usr/bin/env bash
# t1865_readback.sh — exit 0 = promotion verified, nonzero = DO NOT COMMIT.
# No `set -e`: every check must run so one failure does not mask the rest.
rc=0
fail() { printf 'FAIL: %s\n' "$*" >&2; rc=1; }
eq() {  # eq <label> <expected> <actual>
    [ "$2" = "$3" ] || fail "$1: expected '$2', got '${3:-<empty>}'"
}

# JSON validity on every file written
for f in aitasks/metadata/models_claudecode.json aitasks/metadata/codeagent_config.json \
         seed/models_claudecode.json seed/codeagent_config.json; do
    jq . "$f" >/dev/null 2>&1 || fail "invalid JSON: $f"
done

# --- Readback 1: the cli_id is the ID the task requires -------------------
# Pinned to the literal ON PURPOSE, and only here. The TEST derives (so a future
# promotion cannot rot it); this one-time promotion check pins, so a typo cannot
# pass by agreeing with itself.
for f in aitasks/metadata/models_claudecode.json seed/models_claudecode.json; do
    eq "cli_id in $f" "claude-opus-5-5" \
       "$(jq -r '.models[] | select(.name == "opus5_5") | .cli_id' "$f")"
done
eq "resolve pick CLI_ID" "claude-opus-5-5" \
   "$(./.aitask-scripts/aitask_codeagent.sh resolve pick 2>/dev/null | sed -n 's/^CLI_ID://p')"
eq "resolve pick AGENT_STRING" "claudecode/opus5_5" \
   "$(./.aitask-scripts/aitask_codeagent.sh resolve pick 2>/dev/null | sed -n 's/^AGENT_STRING://p')"

# --- Readback 2: every promoted op actually moved -------------------------
for op in pick explore learn trail brainstorm-explorer brainstorm-synthesizer \
          brainstorm-module_decomposer brainstorm-module_merger brainstorm-module_syncer; do
    eq "metadata defaults.$op" "claudecode/opus5_5" \
       "$(jq -r --arg op "$op" '.defaults[$op] // "ABSENT"' aitasks/metadata/codeagent_config.json)"
done
for op in pick explore learn trail; do
    eq "seed defaults.$op" "claudecode/opus5_5" \
       "$(jq -r --arg op "$op" '.defaults[$op] // "ABSENT"' seed/codeagent_config.json)"
done

# --- Readback 3: residuals and deliberate non-moves -----------------------
# Readback 2 only proves the ops I NAMED moved; this catches one omitted entirely.
eq "metadata residual claudecode/opus5 defaults" "0" \
   "$(jq '[.defaults[] | select(. == "claudecode/opus5")] | length' aitasks/metadata/codeagent_config.json)"
# seed must retain EXACTLY two — shadow and discuss, left behind deliberately
eq "seed residual claudecode/opus5 defaults" "2" \
   "$(jq '[.defaults[] | select(. == "claudecode/opus5")] | length' seed/codeagent_config.json)"
eq "seed shadow"            "claudecode/opus5"     "$(jq -r '.defaults.shadow'  seed/codeagent_config.json)"
eq "seed discuss"           "claudecode/opus5"     "$(jq -r '.defaults.discuss' seed/codeagent_config.json)"
eq "metadata shadow"        "codex/gpt5_6_terra"   "$(jq -r '.defaults.shadow'  aitasks/metadata/codeagent_config.json)"
eq "metadata discuss"       "codex/gpt5_6_terra"   "$(jq -r '.defaults.discuss' aitasks/metadata/codeagent_config.json)"

# --- Readback 4: the fallback moved, and the old model still resolves ------
eq "explore-relay rides the new fallback" "claudecode/opus5_5" \
   "$(./.aitask-scripts/aitask_codeagent.sh resolve explore-relay 2>/dev/null | sed -n 's/^AGENT_STRING://p')"
./.aitask-scripts/aitask_codeagent.sh check claudecode/opus5_5 >/dev/null 2>&1 || fail "check claudecode/opus5_5"
./.aitask-scripts/aitask_codeagent.sh check claudecode/opus5   >/dev/null 2>&1 || fail "check claudecode/opus5 (must stay valid)"

# --- Verdict: this script's exit status is the commit gate ----------------
if [ "$rc" -eq 0 ]; then
    printf 'PROMOTION READBACK: PASSED\n'
else
    printf 'PROMOTION READBACK: FAILED — do not commit\n' >&2
fi
exit "$rc"
```

**Negative control for the readback itself:** before trusting a PASS, prove it
can fail — e.g. temporarily point `eq "resolve pick CLI_ID"` at
`claude-opus-5` and confirm the script exits nonzero. A verification block that
has never been seen to fail is not evidence.

# Suites
bash tests/test_codeagent.sh
bash tests/test_codeagent_trail.sh
bash tests/test_codeagent_work_report.sh
bash tests/test_shadow_spawn_learner.sh
bash tests/test_add_model.sh
bash tests/test_codeagent_op_wiring.sh
set -o pipefail; bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only

# Docs + lint
cd website && python3 check_links.py --build
shellcheck .aitask-scripts/aitask_add_model.sh   # only if touched (it should not be)
```

**Negative control for Phase 3** (proves the converted assertions are not
vacuous): `AIT_CODEAGENT_FIXTURE_OMIT_OPS=pick bash tests/test_codeagent.sh`
must fail, and temporarily pointing the derived expectation at the sentinel must
fail too. A derive conversion that silently passes both ways is worse than the
literals it replaced.

## Risk

### Code-health risk: **low**

- Wide but shallow blast radius — 11 files, of which 4 are registry/config
  written by an atomic, `jq`-validating helper and 4 are documentation prose.
  · severity: low · → mitigation: `--dry-run` review before every helper write
- `tests/test_codeagent.sh` is the one non-mechanical edit: a botched derive
  conversion can make assertions **vacuous** rather than red — the exact hazard
  `tests/lib/codeagent_defaults.sh` documents (`assert_contains` degrading to a
  prefix match, empty `$expected`). · severity: medium · → mitigation: inline
  post-phase derive_conversion_negative_control
- `promote-default-agent-string` patches by `sed` anchor and dies if the anchor
  misses, so a silent partial write is not reachable. · severity: low

### Goal-achievement risk: **low**

- The goal is precisely specified, the site inventory is now backed by a
  full-repo sweep rather than the stale audit doc, and both the model ID and the
  `[1m]` question are confirmed from the vendor's published model page.
  · severity: low
- Residual: the audit doc stays unreliable, so a *future* promotion could miss
  `roadmap_run.py` again. Out of scope here — t1341 owns that file.
  · severity: low · → mitigation: inline post-phase audit_doc_staleness_note

### Planned mitigations

- `derive_conversion_negative_control` · inline post-phase · `inline_risk: low`
  · `added_complexity: low` — adopt `codeagent_fixture_metadata` in
  `test_codeagent.sh` and prove the converted assertions fail under
  `AIT_CODEAGENT_FIXTURE_OMIT_OPS=pick`.
- `audit_doc_staleness_note` · inline post-phase · `inline_risk: low`
  · `added_complexity: low` — hand the sweep findings to t1341 by `ait note`
  rather than editing `model_reference_locations.md` here.
