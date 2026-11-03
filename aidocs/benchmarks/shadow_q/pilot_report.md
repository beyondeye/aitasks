# Shadow `>q` pilot report (t2179_1, freeze point)

**Status:** harness validation only, **never evidence**. The pilot ran
n = 1 per cell on cells chosen to exercise the machinery. Nothing below says
which `>q` wording is better. The main run (t2179_2) starts with an explicit
user approval of `matrix.json`'s matrix, budget and limits.

Raw answers, judge rationales and representative excerpts are private. They
are in the aitasks_go store `aidocs/shadow_q_store/` (`runs/pilot/`,
`judging/pilot/`, `pilot_notes.md`), because aitasks is public and the
fixtures quote private aitasks_go content. This report holds numbers and
mechanics only.

## Configuration (as run)

| item | value |
|---|---|
| baseline freeze | aitasks `d46b2bb6` (`frozen/FREEZE.json`). The `>q` bullet is lines 281-300 of both fast renders |
| profile | `fast` (`aitask_skill_resolve_profile.sh shadow`) |
| Claude | Claude Code 2.1.317. Configured `claudecode/opus5_5` (`lib/agent_string.sh` `DEFAULT_AGENT_STRING`). Reported model `claude-opus-5-5` (stream-json `system/init`) |
| Claude reasoning (raw, unresolved) | `effortLevel: high`, `env.ANTHROPIC_REASONING_EFFORT: high`, `modelSettings."claude-opus-5-5".effortLevel: xhigh` |
| Codex | codex-cli 0.166.0. Configured `codex/gpt6_1_sol` (`aitask_codeagent.sh resolve shadow`). Reported model `gpt-6.1-sol` (rollout `turn_context`) |
| Codex reasoning | `model_reasoning_effort = "high"`, `plan_mode_reasoning_effort = "high"`, `personality = "pragmatic"`, rollout `effort: high`. `memories` feature off. No trust override needed |
| store (pilot run) | aitasks_go `9eb52dd3`. Fixtures were pinned by `fixtures/MANIFEST.json` at that commit |
| store (freeze point) | aitasks_go `90c419b7` and later: adds the doc the instruction files point at (see harness issues) |
| launch | `claude -p … --output-format stream-json --verbose --permission-mode dontAsk --permission-prompts none --allowedTools …` / `codex exec --json -s read-only -C <sandbox>`, then `exec resume … -c sandbox_mode="read-only"` |

## Budget and invocations

The cap is a strict ceiling, checked before every launch. The cost and token
values are stop-launch thresholds.

| item | planned | actual |
|---|---|---|
| stub preflight (model-free) | 0 | 0 (34/34 checks ok, incl. under `codex sandbox` read-only; the write negative control was refused) |
| startup smoke | 2 | 3 (+1 Claude re-smoke after the allowlist fix, taken from headroom) |
| fresh sessions | 16 | 16 |
| repeated sessions | 8 | 8 |
| minimal-context sessions | 4 | 4 |
| calibration controls | 12 | 12 |
| answer judging | 32 | 32 |
| judge-fix check (re-judge 2 answers × 2 judges) | 0 | 4 (headroom) |
| **total** | **74** | **79 of 80** |

| threshold | value | final total | overrun |
|---|---|---|---|
| Claude reported cost | $15.00 | $10.17 | none (never reached) |
| Codex non-cached input+output tokens | 2,000,000 | 744,563 | none (never reached) |

There was no retry of a launched session, no limit hit (max 8 tool calls per
turn, max 81 s per subject turn) and no circuit-breaker trip on a launched
session. One circuit-breaker trip came from harness setup failures (see
below).

## Outcome classes

The final records for the 12 cells give **16 of 16 `>q` slots `valid`**.
- Each was verified to have the intended variant loaded (read coverage of the
  `>q` span; sha unchanged).
- Each had a fresh capture plus `--phase` within the `>q` turn, with traced
  output matching the served bytes ("full" match in every call).
- Each had a CLI-reported model.

**Re-validated offline under the hardened validator** (review fixes below;
`harness.py classify`, `runs/pilot/trials_reclassified.jsonl`): **16 / 16 still
`valid`, 0 changed**, and all 3 startup smokes still `loaded`.
- Every variant read succeeded and returned every line of the `>q` bullet.
- Every `>q` turn's screen and phase captures were full matches.

`trials.jsonl` also keeps the first pass's records: 8 slots
`infra_failure:setup_failed` and 2 `not_run:circuit_open`. Those sandboxes
were refused before launch, so they cost no invocations (see harness issues).
They were re-run with `pilot --resume`, which re-runs only cells that never
launched.

The denominator is attempted slots minus `infra_failure`, `uncertain_*` and
`not_run`. Mechanics only, n = 1 per cell:

| measure | value |
|---|---|
| compliance rate (`valid` / denominator) | 16 / 16 |
| **overall success** (`valid` **and** adequate / denominator) | **14 / 16** |
| sensitivity lines (every launched-or-refused slot in the denominator) | compliance 16 / 24, overall success 14 / 24 |
| conditional quality (`valid` only) | n = 16, scores below |

**Adequate (pre-registered):**
- every calibrated judgment has `failure_flag` false, **and**
- the mean `could_choose` over the calibrated judges is ≥ 2.

A flag from either judge makes an answer inadequate. The two inadequate
answers are:
- Codex · v1 · minimal (flagged by both judges);
- Claude · v1 · repeated, `go_versions` (mean `could_choose` 1.5).

## Mechanics observed (flags, not scores)

| flag | Claude | Codex |
|---|---|---|
| Step 0 capability greeting seen at startup (non-minimal sessions) | 2 / 7 | 6 / 6 |
| capture before greeting (non-minimal sessions) | 6 / 7 | 0 / 6 |
| web-tool use in a `>q` turn | 0 / 8 (no web tools on its allowlist) | 4 / 8 (every fresh session, 2 searches each; none in repeated or minimal) |
| off-path helper calls, tmux use, replay-dir peeks, reads outside the sandbox | 0 | 0 |
| answer length, chars (not scored) | mean 3,368 (2,647-4,317) | mean 1,214 (797-2,268) |

Instruction length, the `>q` bullet only (the rest of the skill is
identical):

| variant | chars |
|---|---|
| v1 | 1,256 |
| v2 | 1,228 |
| v3 | 1,596 |
| v4 | 1,392 |

## Judging (both agents' judges, blinded)

- **Calibration** (pre-registered: composite(shallow) < composite(adequate)
  per scenario × judge): **6 / 6 ordered correctly**. The shallow controls are
  9-16% *longer* than the adequate ones and recommend the same option, so
  neither length nor the pick explains the ordering.
- **Parse failures:** 0. Judge tool use: 0. Agent self-references stripped
  from answers: 0 were present.
- **Disputed** (the judges differ by more than 1 point on some dimension):
  **8 of 16** answers.
- **Failure flag** (the failure under study): both judges set it on the same
  single answer, Codex · v1 · minimal context.

Mean composite per judge, by answering agent:

| judge \ answers by | Claude (n=8) | Codex (n=8) |
|---|---|---|
| Claude judge | 10.88 | 8.83 |
| Codex judge | 10.45 | 10.92 |

**Factual correctness differs by judge.** The Codex judge gave Claude's
answers a mean factual correctness of 0.62, against 2.38 from the Claude
judge. Its first-pass rationales called task-file citations "invented"; the
judge had seen only the screen and the reference notes.
- **Fix, applied for the main run:** the judge prompt now includes the task
  (and plan) file the subject could read.
- **Check** (2 answers re-judged by both judges, `runs/pilot/rejudge_taskctx.json`):
  the "invented citation" objection disappeared. The Codex judge still scored
  factual correctness 0, against the Claude judge's 2, now over substantive
  overclaims.
- So the judges differ in strictness on this dimension. It is the main source
  of disputes, and t2179_2's independent audit should prioritise it.

Whether the opposite-direction gaps reflect self-preference, strictness or
real quality differences cannot be told from n = 16; this is a hypothesis.

## Fidelity check (does v1 reproduce the originating terse pattern?)

Observed, **inconclusive** at n = 1 per cell:
- **Codex under v1** (fresh, minimal, repeated): 800-1,100 characters,
  recommendation first, one line per option. This is closest to the
  originating pattern. It got the only failure flag.
- **Claude under v1:** explained the decision and both options at length in
  all three conditions, so it did *not* reproduce the pattern.

So the main run can plausibly detect a wording effect for Codex. For Claude
the baseline may already be at ceiling.

## Measured per call (pilot means; basis of the projection)

| call | Claude | Codex |
|---|---|---|
| startup turn | $0.296, 37.5 s | 28.0k tokens, 30.5 s |
| `>q` turn | $0.661, 53.7 s | 39.7k tokens, 29.0 s |
| answer judge | $0.094, 22.7 s | 8.3k tokens, 35.0 s |
| control judge | $0.075, 15.8 s | 10.2k tokens, 22.5 s |

Codex does not report dollar cost; tokens are its usage measure. The
task-aware judge prompt adds the task file to every judge call, so judging cost
will rise above these means. Each judge's added input is roughly 6-8k tokens.

## Projected main run (`matrix.json`, PROPOSED, not approved)

| item | count |
|---|---|
| sessions | 196 (fresh 144, minimal 40, repeated 12) |
| subject invocations | 416 |
| `>q` answers | 220 |
| judge invocations | 440 answers + 16 controls |
| **planned invocations** | **872** |
| projected Claude cost | ≈ $123 (subjects ≈ $102, judging ≈ $21, before the task-file increase) |
| projected Codex tokens | ≈ 9.0M non-cached (subjects ≈ 7.1M, judging ≈ 1.9M, before the task-file increase) |
| wall clock | ≈ 2.2 h of subject runs at 2 concurrent sessions, ≈ 3.7 h of sequential judging |

**Proposed limits:**
- invocation cap 920;
- Claude cost threshold $145;
- Codex token threshold 10.5M;
- 16 invocations reserved for controls;
- per-turn limits unchanged.

The task-file judge context may push judging past these thresholds, so the
approval should re-check them.

## Harness issues found by the pilot, all fixed

1. **Allowlist not self-sufficient (startup smoke).** Claude chained
   `helper; echo "EXIT:$?"`, and `dontAsk` checks every subcommand.
   - Read-only utilities were added (`echo`, `printf`, `true`, `cat`, `head`,
     `tail`, `wc`, `ls`, `nl`, `sed -n`, `grep`).
   - The denial was classified `infra_failure:permission_denied`, as designed.
   - Cost: 1 re-smoke.
2. **Transient ancestor dirs.** Empty `/tmp/.agents` and `/tmp/.codex` appeared
   during a Codex resume turn and were gone afterwards. The likely source is
   the Codex CLI; the record does not prove it.
   - The ancestor guard refused all later sandboxes before launch. That cost 0
     invocations, but it opened the circuit breaker on 2 cells.
   - Now only ancestors that carry content are refused; empty ones are
     flagged. Cells that never launched were re-run with `pilot --resume`.
3. **Store `.gitignore`.** aitasks_go ignores every `aitasks`/`aiplans` path
   component, so the task-file fixtures were silently uncommitted.
   - They are now stored as `_aitasks`/`_aiplans` and served under their real
     names.
   - `manifest --write` now refuses files the store's git does not track.
4. **Missing pointed-to doc.** The instruction files tell the agent to read a
   project overview doc, and every Codex startup ran `cat` on it. The pilot
   sandboxes lacked it. The store carries it from the freeze point.
5. **Judge input gap:** see "Factual correctness differs by judge".
6. **The stub's ANSI-strip `sed`** needed `LC_ALL=C` (preflight).

## Review fixes (after the pilot, before the freeze)

All of these are covered by offline tests. None changed a pilot outcome (see
the re-validation above).

1. **A variant read counts only if it succeeded and delivered the bullet.**
   - A failed or unanswered read (an error, or no result) contributes nothing.
   - A covering read whose returned text lacks any line of the `>q` bullet
     (for example, CLI truncation) is `uncertain_load`, never `loaded`.
   - Skill-tool loads need the injected content to show the bullet.
   - Checked on a real trace: a failed read gives `not_loaded`, a truncated
     one gives `uncertain`.
2. **A capture counts only if its delivery is verified** (a full match, or a
   head + tail match).
   - Output the subject transformed (`| head -1`) is
     `subject_noncompliance:capture_not_delivered`.
   - An unpiped head-only match is `uncertain_delivery`, which is excluded
     from the denominator like `uncertain_load`.
3. **Durable budget.** A `reserve` record is fsynced to
   `runs/<batch>/budget_journal.jsonl` before every launch, and a `usage`
   record after it.
   - Recovery takes the maximum over the journal, `invocations.jsonl` and the
     snapshot, so an interruption cannot reset the cap or the spend.
   - A reservation without recorded usage, and a finished call that reported
     none, are charged a conservative bound: Claude $2.00 (the per-call
     `--max-budget-usd` ceiling), Codex 200k tokens (`limits.json`).
   - The pilot predates the journal; its totals above come from
     `invocations.jsonl`.
4. **Bounded runner.** The wall-clock deadline now covers the process's whole
   lifetime, not only its stdout, so a child that closes stdout and keeps
   running is still timed out.
   - Every wait is bounded by the deadline plus the grace period.
   - Processes left in the group after the leader exits are killed.
5. **The leak check cannot be self-certified.**
   - Exemptions come only from HEAD-committed public sources (the seed
     instructions and the tracked skill sources), read from git objects.
   - Files being checked (`frozen/`, `variants/`, …) never exempt text.
   - Raw streams are decoded fail-safe: every string counts except the text the
     subject received from skill-file reads, per the store's own trace.
   - A private line planted in a new `frozen/` file is now caught.

**Second review round:**

6. **Budget migration and reconciliation by identity.**
   - The journal starts with a `baseline` record. For a batch that predates
     it, the baseline holds the historical totals.
   - Each `reserve` carries the next global `seq`, and its `usage` carries the
     same `seq`.
   - Recovery gives `used` = max(baseline, highest seq), and spend = baseline +
     matched usage + the bound for each unmatched reservation. History and
     pending reservations therefore add up, and completed calls are never
     counted twice.
   - Example: 79 historical calls plus 1 interrupted reservation recovers as
     80, so the 81st launch is refused.
7. **Overall success is the approved, quality-aware measure** (above). The
   valid-only rate is now named `compliance_rate`.
8. **The live tool counter covers every tool kind.** It counts Codex
   `web_search`, `mcp_tool_call` and `file_change` items, as well as
   `command_execution`, once per item id. Recounted over the pilot streams,
   the maximum per turn is still 8.
9. **Any threshold stops every new launch**, of either agent, subject or
   judge. During the pilot each agent's threshold gated only its own launches,
   but no threshold was reached, so no outcome changed.
10. **Every option score must be finite and in 0-3.** An out-of-range judgment
    goes through the one re-ask, then `parse_failed`. All 48 saved pilot
    judgments (44, plus 4 re-judges) pass the strict check.

## Open decisions for the t2179_2 approval gate

1. **Web access asymmetry.** Codex web-searched in every fresh `>q` turn;
   Claude has no web tools under the allowlist. The fixtures were written to be
   answerable without browsing. Disable web access for both (recommended:
   uncontrolled evidence, varies per run), or allow it for both.
2. **Audit budget.** With about half the answers disputed, the independent
   audit should be sized accordingly.
3. **Claude startup behaviour.** Claude skipped the Step 0 greeting in most
   sessions and gave a proactive explanation before `>q`. The `>q` answer can
   lean on that. Keep it as part of the real behaviour (as now), or report it
   as a covariate.

No optional extra variant (such as a worked example) was tested; see
`variants/README.md`.

## Reproduce

```bash
python3 aidocs/benchmarks/shadow_q/freeze.py                 # re-freeze (refuses dirty sources)
python3 aidocs/benchmarks/shadow_q/harness.py plan           # enumerated pilot cells and totals
python3 aidocs/benchmarks/shadow_q/harness.py preflight      # model-free stub checks
python3 aidocs/benchmarks/shadow_q/harness.py smoke          # 2 paid startup turns
python3 aidocs/benchmarks/shadow_q/harness.py pilot          # 12 sessions (bounded by limits.json)
python3 aidocs/benchmarks/shadow_q/harness.py judge          # controls first, then answers
python3 aidocs/benchmarks/shadow_q/harness.py summary        # numbers-only aggregate
python3 aidocs/benchmarks/shadow_q/check_public.py --staged  # leak check before any public commit
```
