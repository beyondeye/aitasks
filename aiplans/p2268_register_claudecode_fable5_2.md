---
Task: t2268_register_claudecode_fable5_2.md
Base branch: main
Output branch: main
---

# Plan: Register claudecode/fable5_2 (+ fable5_2_1m), t2268

## Context

Fable 5.2 (`claude-fable-5-2`) is not in `models_claudecode.json`. As a result a
Fable 5.2 session self-detects as `claudecode/unregistered_*`, gets the
coauthor name `Claude Code/fable5_2` instead of `Claude Code/Fable 5.2`
(verified: `aitask_codeagent.sh coauthor claudecode/fable5_2` prints the raw
name), and cannot be configured for any op. Precedents: Fable 5.1 (t1680,
1a120ec73) and Haiku 5.5 (t1916, af5bc8645).

Profile `fast`: current-branch mode (`main`), no worktree.

## `[1m]` variant check: register `fable5_2_1m` (for one narrow route)

**Session records: none.** I scanned every `~/.claude/projects/**/*.jsonl` except
this session's. No transcript has a `message.model` of `claude-fable-*`, so no
Fable session ran on this machine. The only `aitask_resolve_detected_agent.sh
--cli-id claude-fable-5-2` call came from the Opus 5.5 session that created this
task. Every `claude-fable-5-2[1m]` string in transcripts is prose, not a
self-detection.

**Static trace, Claude Code 2.1.322**
(`~/.local/share/mise/installs/claude/2.1.322/claude`, read-only byte scan):

1. *Entry point.* `Wt(e) = BI(uY(q$(e)))`, and `BI` is the identity function.
   In the model chunk, `q$` (the alias and id resolver) has exactly one caller:
   `Wt`. Every other `q$(` in the binary is a different function in another chunk.
   So any resolved model passes through the outer `uY`.
2. *Inner `q$`.* `s = rg(r)` (the input carries `[1m]` and
   `CLAUDE_CODE_DISABLE_1M_CONTEXT` is unset); `h = Ht(r)` (suffix stripped).
   - `case "fable": { let y = exe(); return BI(y + (s && !ls() && !rg(y) ? "[1m]" : "")) }`,
     where `ls() = ve()==="firstParty" && ki()`. So the inner suffix is added only
     off the first-party API. `exe()` = `ANTHROPIC_DEFAULT_FABLE_MODEL` ?? the
     catalog default `claude-fable-5-2`.
   - `case "opus"`, `"sonnet"`, `"haiku"`: `s ? fY(<default>) : <default>`, where
     `fY` appends `[1m]` unconditionally.
   - Non-alias ids: `if (s) return BI(n.replace(/(\[1m\])+$/i, "").trim() + "[1m]")`.
     The suffix survives `q$` for an explicit `claude-fable-5-2[1m]`.
3. *Outer `uY` normalises it away.*
   `uY(e) { let n = I0(e); return n !== e && PA(n, {byItsOwnName: true}) ? n : e }`, where:
   - `I0(e)` = `e.replace(/\[1m\]/gi, "")`
   - `PA(n)` = `Km(n) !== undefined`, and `Km(n)` = `YR() ? undefined : Jr(_1(n))?.window ?? mT(...)`
   - `_1(n)` canonicalises via `it(Ht(n))` and accepts it when `fT(h)`, with
     `fT(h)` = `Jr(h)?.native_1m === true || mT(h) !== undefined`
   - the catalog entry for `claude-fable-5-2` is `context: {window: 1e6, native_1m: true, supports_1m_beta: true}`

   So `PA("claude-fable-5-2")` is true and `uY("claude-fable-5-2[1m]")` returns
   `"claude-fable-5-2"`. Neither `uY` nor `Jr` checks the provider, so this
   holds on first party, Bedrock, Vertex and gateways alike. Opus 5.5, Sonnet 5.5
   and Haiku 5.5 are `native_1m` too, so in 2.1.322 their `[1m]` ids normalise
   the same way. The `claude-opus-5-5[1m]` cli-id an earlier Opus session passed
   to the resolver was on 2.1.280 (2026-09-23).
4. *The one survivor.* With `CLAUDE_CODE_DISABLE_1M_CONTEXT` set, `rg()` is
   false and `Km()` returns undefined. An explicitly typed `claude-fable-5-2[1m]`
   then passes through `q$` verbatim, and `uY` keeps it.
5. *Migration.* A Fable 5.1 user setting (`claude-fable-5-1` or `claude-fable-5-1[1m]`)
   is rewritten to the alias `fable` or `fable[1m]`, which then resolves through
   steps 1-3 to the bare id.
6. *System message.* `jLo(KDt(mainLoopModel))` emits `"The exact model ID is ${modelId}"`.
   `mainLoopModel` is `mu(e)` = override ?? `options.mainLoopModel`. Its
   env-info cache compares ids through `uY`, and `UDt` strips a
   `" (1M context)"` marketing suffix when `uY` changes the id. That means a
   `[1m]` modelId is expected only for models `uY` does not normalise. Empirical
   check: this session's setting `model: "opus"` reaches its system message as
   the resolved `claude-opus-5-5`.

   **Not fully traced:** I did not follow every minified assignment to
   `options.mainLoopModel`. The claim that explicit ids also go through `Wt`
   rests on `q$` having a dedicated non-alias branch, which exists only to serve
   explicit ids, plus `Wt` being its sole caller.

**Conclusion.** In 2.1.322, a Fable 5.2 session reports `claude-fable-5-2` on
every route: `fable`, `fable[1m]`, an explicit `claude-fable-5-2[1m]`, the
migrated 5.1 setting, and any provider. The single exception is an explicit
`[1m]` id combined with `CLAUDE_CODE_DISABLE_1M_CONTEXT`. That combination does
report `claude-fable-5-2[1m]` (step 4), so the task's "if it does" branch
applies. Register `fable5_2_1m` → `claude-fable-5-2[1m]` so that route resolves
to a real entry instead of `claudecode/unregistered_claude_fable_5_2_1m`. It is
the same model under another spelling (`[1m]` entries are never distinct models),
and `format_claude_model_label` strips `[1m]`, so its coauthor label is
`Fable 5.2`. Nothing is inferred
about whether the existing `opus5_5_1m` / `sonnet5_5_1m` / `haiku5_5_1m` entries
are still needed: they serve older CLI versions and are out of scope.
This section is copied verbatim into the final plan as the durable record.

## Implementation

Every write goes through `.aitask-scripts/aitask_add_model.sh`, never by hand.
Run each step as `--dry-run` first, then apply it.

1. Add the entry:
   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode --name fable5_2 \
     --cli-id claude-fable-5-2 \
     --notes "Fable 5.2 — most capable Fable model, 1M context, 128K output, thinking always on (Fable 5.1 is now the previous generation)"
   ```
   Add the `[1m]` spelling:
   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode --name fable5_2_1m \
     --cli-id 'claude-fable-5-2[1m]' \
     --notes "Fable 5.2 — same model, explicit [1m] spelling (reported only for an explicit [1m] id with CLAUDE_CODE_DISABLE_1M_CONTEXT set), 1M context, 128K output, thinking always on"
   ```
2. Record the lineage (`fable5_1` → `fable5_2`). The `fable5 → fable5_1` edge is left as it is:
   ```bash
   ./.aitask-scripts/aitask_add_model.sh record-supersession --agent claudecode --old fable5_1 --new fable5_2
   ```
   Expect `RECORDED:claudecode/fable5_1->claudecode/fable5_2`, plus at most a
   `SKIPPED:sibling_*` line: `fable5_1` has no `_1m` sibling, so `fable5_2_1m`
   gets no edge. Any `BLOCKED:` → stop and report.
3. **No promotion.** `seed/codeagent_config.json` and `DEFAULT_AGENT_STRING`
   (`claudecode/opus5_5`) stay unchanged.
4. **`fable5_1` notes refresh is skipped.** The helper has no notes-edit
   subcommand, and the task requires every write to go through it. Reported as a
   possible follow-up.

### Commits (name paths only; another session has t2211_10 files dirty in the data worktree)
- Code: `git add seed/models_claudecode.json .aitask-scripts/lib/model_supersessions.json` and
  `git commit -m "feature: Register claudecode/fable5_2 and fable5_2_1m (Fable 5.2) (t2268)" -- <those two paths>`.
- Task data: `./.aitask-scripts/aitask_task_commit.sh -m "ait: Register claudecode/fable5_2 and fable5_2_1m" aitasks/metadata/models_claudecode.json`.

## Verification

The resolver checks below confirm the **registration** only. They cannot confirm
which id a session reports: they supply the literal themselves. For the variant
question, the evidence is the recorded trace above.

- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id claude-fable-5-2` → `AGENT_STRING:claudecode/fable5_2`
- same with `'claude-fable-5-2[1m]'` → `AGENT_STRING:claudecode/fable5_2_1m`
- `bash .aitask-scripts/aitask_codeagent.sh coauthor claudecode/fable5_2` → `AGENT_COAUTHOR_NAME:Claude Code/Fable 5.2`, and the same for `claudecode/fable5_2_1m`
- Both registry files parse as JSON, and both new entries' `name`/`cli_id`/`notes` are identical in seed and metadata (python3 compare)
- `python3 -I -c` check that `model_supersessions.json` has `claudecode.fable5_1.by == "fable5_2"` and still has `fable5.by == "fable5_1"`
- `bash tests/test_install_superseded_models.sh`, `bash tests/test_codeagent.sh`, `bash tests/test_add_model.sh`
- `python3 tests/test_model_supersession.py`, directly. Check the exit status, not a tail.

## Follow-ups (report only, not created automatically)
- opencode `opencode/claude-fable-5-2`, through `aitask-refresh-code-models`.
- Optionally refresh the `fable5_1` "most capable" notes, if a notes-edit path is wanted.

## Step 9
Post-implementation: user review (Step 8), then archival per task-workflow Step 9.
There is no branch to merge (current-branch mode).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
