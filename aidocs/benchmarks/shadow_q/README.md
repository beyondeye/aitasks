# Shadow `>q` wording experiment (t2179)

This experiment measures whether a concise, intent-based definition of the
aitask-shadow `>q` command is enough, or whether more explicit wording makes
the decision help more consistent. It runs across the real Claude Code and
Codex default agents. The production `>q` definition is **not** changed here.

**Public / private split.** aitasks is public; the fixtures quote the private
aitasks_go repository.
- This directory holds code, frozen public skill text, the rubric, the judge
  prompt, and numbers-only results.
- Everything that carries or quotes aitasks_go content lives in the aitasks_go
  store `aidocs/shadow_q_store/`, resolved with
  `./ait projects resolve aitasks_go`.
- `fixtures/MANIFEST.json` pins that store by commit and per-file sha256, and
  the harness refuses to run against a store that differs.
- Run `check_public.py --staged` before every public commit.

| file | role |
|---|---|
| `freeze.py`, `qspan.py` | pin the baseline: frozen render trees, `>q` span, `variants/v1_baseline.md` |
| `variants/` | the four bullet texts and their hypotheses |
| `harness.py` | sandboxes, replay stubs, real CLI launch with limits, the durable budget journal, and the `plan` / `preflight` / `smoke` / `pilot` / `judge` / `rejudge` / `summary` / `classify` (offline re-validation) commands |
| `validate.py` | trace parsing, read coverage and outcome classes (offline, re-runnable) |
| `judge.py`, `judge_prompt.md`, `rubric.md` | blinded two-judge scoring with per-scenario calibration controls |
| `store.py`, `check_public.py` | whitelisted public sink, private sink, store manifest, leak check |
| `limits.json`, `matrix.json` | the frozen pilot limits, and the proposed (unapproved) main matrix |
| `runs/<batch>/` | numbers-only JSONL: sessions, trials, invocations, scores, preflight |
| `pilot_report.md` | the pilot's measured numbers, harness issues and open decisions |

Tests: `python3 tests/test_shadow_q_harness.py` (offline; fake CLIs and a
synthetic store).
