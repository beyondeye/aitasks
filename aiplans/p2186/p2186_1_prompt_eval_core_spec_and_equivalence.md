---
Task: t2186_1_prompt_eval_core_spec_and_equivalence.md
Parent Task: aitasks/t2186_generic_agent_prompt_eval_harness.md
Sibling Tasks: aitasks/t2186/t2186_2_*.md, aitasks/t2186/t2186_3_*.md, aitasks/t2186/t2186_4_*.md, aitasks/t2186/t2186_5_*.md, aitasks/t2186/t2186_6_*.md, aitasks/t2186/t2186_7_*.md
Archived Sibling Plans: aiplans/archived/p2186/p2186_*_*.md
Base branch: main
Output branch: main
---

# t2186_1: Core trace, rules and spec format, the shadow_q spec, and the byte-identical proof

Child 1 of t2186. The parent plan is `aiplans/p2186_generic_agent_prompt_eval_harness.md`; the task file carries the shared
constraints, the facts established during exploration and the target layout. Read both. Treat any deviation recorded in an archived sibling plan's Final Implementation Notes as authoritative over this plan.

## Context

Child 1 of t2186, the generic agent-prompt eval harness. It builds the **offline half** of
the new core under `aidocs/benchmarks/prompt_eval/`: the spec format, the trace parsers, the
rule engine, outcomes, sinks, the leak check and offline re-classification. It also ports the
t2179 shadow `>q` experiment as the first spec, and proves the port does not change the pilot's
classification: `classify` and `summary` must be byte-identical, with no CLI calls. Every later
child builds on this code, and t2186_7 re-runs this proof at the end.

## Implementation

### `prompt_eval_core_spec_and_equivalence` (no spend)

The offline half of the core, the spec format, the shadow_q spec, and the byte-identical proof.

1. **`pecore/spec.py`** — load and validate `spec.json` (`spec_version: 1`; unknown keys
   refused; every path required to exist). **Path base, explicit:** a path is either relative to
   the spec file's own directory, or `@<root>/<rel>` against a **named root** declared in the
   spec's `roots` map (each root itself relative to the spec directory). The CLI's
   `--root <name>=<dir>` overrides a named root for one invocation; the override is recorded in
   every output that depends on it, and is what lets the equivalence proof point the shadow_q
   spec at an archived snapshot (step 9). `digest()` =
   sha256 over the canonical spec JSON plus every referenced public file (frozen renders,
   variants, rubric, judge prompt, limits, matrix, stub bodies). The digest is what approvals
   (child 2) and pre-registration (children 5-6) bind to. Sections: `name`, `store`
   (`project`, `subdir`, `env_override`, `manifest`, `manifest_dirs`), `public_runs`, `limits`,
   `matrix`, `seed`, `agents.<name>` (layout: `skills_dir`, `stub`, `render`, `frozen`,
   `dispatch_suffix`, `skill_names`; `resolve`; `invoke_args` — `resolve` is used in child 2),
   `prompt` (`render_file`, `span`, `variants_dir`, `variants`, `baseline`, `freeze`),
   `conditions` (per condition: `instructions` on/off, `excerpt` keep-list or full render),
   `scenarios`, `replay` (helper declarations), `turns`, `vars`, `rules`, `judging`.
2. **`pecore/span.py`** — generic selectors with the occurs-once and only-span-changed proofs
   (port of `qspan.py`, difflib check intact): `bullet` (`start_prefix`; ends before the next
   `- ` / `**` / `#` line; trailing blank lines excluded) and `heading` (`heading` line; ends
   before the next heading of the same or higher level — used by child 4). `excerpt(text,
   keep)` builds the minimal-context render declaratively: shadow_q's keep-list is
   `[{"until_heading":"## Step 0"}, {"section":"## Step 1"}, {"heading_line":"## Step 3"},
   {"span":true}, {"section":"## Guardrail"}]` joined by a blank line plus a trailing newline
   (= `harness.build_minimal`).
3. **`pecore/trace.py`** — `Event`, `Turn`, `parse_claude`, `parse_codex` (verbatim ports,
   in a `PARSERS` registry by agent family that child 2's adapters use), `unwrap_shell`,
   `match_output`, `read_coverage(event, dispatch_suffix, skill_names, nlines)`, `covers`, and
   a generic `helper_calls(command, helper_table)`. The table is built from the spec's `replay`
   declarations: per helper an invocation regex (default
   `(?:[^\s'";|&()]*/)?<dir>/(<name>)`), an off-path pattern (shadow_q:
   `\.aitask-scripts/(aitask_[A-Za-z0-9_]+\.sh)`) and an ordered `form_rules` list, first match
   wins. shadow_q's capture forms: `[["phase",{"has":"--phase"}], ["stdin",{"has":"-"}],
   ["deep",{"has":"--deep"}], ["any_pane",{"has":"--any-pane"}],
   ["explicit_id",{"positional":true}], ["noarg",{}]]`; other helpers → `default`. Keep the
   segment splitting, `piped` detection and the redirect filter exactly.
4. **`pecore/rules.py`** — `classify_session(turns, session_spec, rules)`. The core runs the
   infra checks first (setup, earlier turn dead, sha changed, model unverified, this turn dead,
   cumulative helper infra), always records `web_tools`, then applies the spec's **ordered**
   `q_turn` list. Rule types needed by shadow_q only (child 4 adds the rest):
   - `command_flag` (`flag`, `outcome`): fail when a command-flag fired in this turn;
   - `limits`: `limit_tool_calls` then `limit_timeout`;
   - `variant_load` (turn-1 coverage of the span + delivered bullet lines; `uncertain_load` /
     `subject_noncompliance:variant_not_loaded`);
   - `helper_forms` (`helper`, `require_any`, `require_all`, `outcome`, `flag_on_fail`);
   - `delivery` (`helper`, `groups`, `transformed_outcome`, `else_outcome`, `flag_on_fail`;
     delivered = `full` | `head_tail`);
   - `answer_nonempty`.
   Session-level flags: `command_flags` (`regex` with `unwrap`, or `substring`), `greeting`
   (distinct regex matches ≥ n in a text/final event), `helper_before` (named helpers called
   before the greeting index), `off_path_helpers`, `helper_infra`, `match_kinds`,
   `denied_off_path`. Expected outputs per turn come from the session spec, built from the
   replay map (`expected: {form: "replay:screen" | literal}`).
5. **`pecore/outcomes.py`** — outcome vocabulary, `summarise` (same keys and denominators), and
   `adequate(judgments, rule)` with the rule from the spec (shadow_q: every calibrated judgment
   flag-free and mean `could_choose` ≥ 2; unknown counted as not adequate and reported).
6. **`pecore/store.py`** and **`pecore/leakcheck.py`** — ports of `store.py` (sinks, manifest,
   `resolve_store(project, subdir, env_override)`; core `PUBLIC_FIELDS` kinds plus per-spec
   additions; `MAX_PUBLIC_STR` 160) and `check_public.py` (public paths default to
   `aidocs/benchmarks/prompt_eval/**`, the spec's `public_runs`, and
   `tests/test_prompt_eval_*.py`; HEAD-committed exemptions only; leak terms from the store).
   CLI: `prompt_eval.py --spec <s> check-public [--staged]`.
7. **`pecore/classify.py`** — generic `reclassify_batch(spec, batch, store, runs_public)` (port
   of `harness.py:1594-1663`: rebuild each launched session's dispatched text from the spec,
   refuse on a dispatched-sha or fixture-hash mismatch, rebuild expected outputs from the
   replay map, q-turns from the condition, smoke rows) and `summary(spec, batch)` (port of
   `cmd_summary`, identical output). CLI: `classify --batch B [--write | --out PATH]` (prints by
   default, writes only on request) and `summary --batch B`.
8. **`specs/shadow_q/spec.json`** (+ `README.md`) — declares `"roots": {"shadow_q":
   "../../../shadow_q"}` (from `aidocs/benchmarks/prompt_eval/specs/shadow_q/` that resolves to
   `aidocs/benchmarks/shadow_q/`; `../../shadow_q` would wrongly land in
   `aidocs/benchmarks/prompt_eval/shadow_q/`), and references
   `@shadow_q/{frozen,variants,rubric.md,judge_prompt.md,fixtures/MANIFEST.json,limits.json,
   matrix.json}` and `public_runs: @shadow_q/runs`. Store `aitasks_go` / `aidocs/shadow_q_store`, env override
   `AIT_SHADOW_Q_STORE`, seed 2179, the q-turn rule list in the precedence above, the
   `minimal` excerpt keep-list, the replay map and its expected outputs.
9. **`tools/equiv_shadow_q.py`** — the byte-identical proof. **Both implementations read the
   same pinned, archived inputs**, so the verdict never depends on what later happens to the live
   shadow_q files (t2179_2 edits `matrix.json`'s status field, for example):
   - extract `git archive 6930f54e2 aidocs/benchmarks/shadow_q` and
     `git -C <aitasks_go> archive 3fcf4bd aidocs/shadow_q_store` into a fresh scratch dir outside
     every repository (`check_ancestors`), record both tree ids;
   - **before**: a subprocess running the pinned `harness.py --store <scratch store> classify
     --batch pilot` (it writes only inside the scratch copy) and `summary --batch pilot`;
   - **after**: a subprocess running the live `prompt_eval.py --spec specs/shadow_q
     --root shadow_q=<scratch>/aidocs/benchmarks/shadow_q --store <scratch store>` with
     `classify --out <scratch file>` and `summary` — the new code over the archived inputs;
   - compare bytes; print `EQUIV:historical:classify|IDENTICAL|<sha256>` and
     `EQUIV:historical:summary|IDENTICAL|<sha256>` (or `DIFFERENT` plus the first differing
     record); exit 0 only when both are identical. This is the verdict.
   - **Current-input compatibility, reported separately and never gating:** list each live file
     the spec references as `same` / `changed` against its pinned copy, then run the after side
     once more on the live inputs and report whether its classify/summary still equal the
     historical output (`EQUIV:current:…|SAME|DIFFERS`, with the changed files named). A
     changed `matrix.json` status field therefore shows up as a reported input change, not a
     failed proof.
   - Also report, as information only, whether the committed
     `runs/pilot/trials_reclassified.jsonl` equals the pinned "before" output.
   - The script and its output go verbatim into the child plan's Final Implementation Notes
     (durable closure evidence).
10. **Tests `tests/test_prompt_eval_core.py`** (offline):
    - differential validator: every synthetic turn set from `TestValidator` in
      `tests/test_shadow_q_harness.py` classified by the live `validate.classify_session` and by
      `pecore.rules` → identical;
    - synthetic-run equivalence: a batch produced by the **old** harness under the fake CLIs
      (modes `good`, `no_read`, `no_capture`, `deny`, `mismatch`, `no_answer`, `capture_first`,
      `no_model`, both agents, fresh/minimal/repeated) → old vs new `reclassify_batch` and
      `summary` identical;
    - **mutation control**: a temp copy of the shadow_q spec with two rules swapped (delivery
      before helper_forms) or the tmux rule dropped makes the differential fail on the cases
      built to hit them;
    - span/excerpt: every variant × agent substitution and minimal excerpt equals
      `qspan`/`build_variant`/`build_minimal` over the frozen public renders;
    - spec loader: unknown key, missing path, digest changes when a referenced file changes;
      **the shipped `specs/shadow_q/spec.json` loads from the documented layout** and every
      `@shadow_q/...` path resolves under `aidocs/benchmarks/shadow_q/` (asserted by absolute
      path, so a `../../` slip fails); a `--root shadow_q=<dir>` override redirects every one of
      them and nothing else;
    - equivalence tool on synthetic archives: two scratch "commits" whose referenced inputs
      differ only in `matrix.json`'s `status` give a historical `IDENTICAL` and a current-input
      report naming `matrix.json` as `changed`; a planted classifier difference gives
      `DIFFERENT` and a non-zero exit;
    - leak check: ported planted-line, leak-term, identifier-only, self-certification and
      decoded-stream cases.

## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2186 auto-archives with its last child.

## Verification

- `python3 aidocs/benchmarks/prompt_eval/tools/equiv_shadow_q.py` prints
  `EQUIV:historical:classify|IDENTICAL|…` and `EQUIV:historical:summary|IDENTICAL|…` and exits 0.
  The current-input report is printed separately. The script and its full output go verbatim
  into this plan's Final Implementation Notes.
- `python3 tests/test_prompt_eval_core.py` passes; the mutation controls go red on the mutated
  spec.
- `bash tests/run_all_python_tests.sh --test-dir <scratch dir holding only the new module>` is
  green (set `-o pipefail`, read the last line).
- `python3 aidocs/benchmarks/prompt_eval/prompt_eval.py --spec aidocs/benchmarks/prompt_eval/specs/shadow_q check-public --staged`
  passes before the public commit.
- `git diff --stat` shows nothing under `.claude/skills/`, `.agents/`, `.opencode/` or
  `aidocs/benchmarks/shadow_q/`.

## Risk

### Code-health risk: low
- New code only, under `aidocs/benchmarks/prompt_eval/` plus one test module; shadow_q is
  untouched. · severity: low · → mitigation: none (contained by design)

### Goal-achievement risk: medium
- Byte-identical equivalence may be out of reach if a shadow_q rule is subtler than the rule
  types (the tmux-before-limits order, delivery kinds, smoke rows). · severity: medium
  · → mitigation: none (addressed in design: the recorded precedence, an ordered rule list that
  can place `limits`, the per-case differential test and mutation controls; a difference is
  explained, never accepted silently)
- The spec format could fit shadow_q only. · severity: medium · → mitigation: none (addressed
  by t2186_4's second spec)
