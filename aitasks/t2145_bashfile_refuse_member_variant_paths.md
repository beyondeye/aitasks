---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-26 10:05
updated_at: 2026-10-26 12:25
---

## Origin

Spawned from t1854_9 (M3.2f pytest adapter) during Step 8b review.

## Upstream defect

- goengines/internal/testmap/runner/builtin/bashfile.go:93 — bash-file accepts a script path that `registry.ParseID` reads as a member/variant (`#`, `@`). It is checked only for a parse error, not that `id.String() == rel`. Reproduced: a committed `tests/test_a#b.sh` is listed, then always ends `UNIT …|error` with `PROTOCOL_ERROR missing_start` (fail-closed, but it can never pass). The pytest adapter refuses such paths at list time with an explicit message.

## Diagnostic context

- `bashFileList` writes `<rel>\tfile\t<p>` whenever `registry.ParseID(rel)` succeeds. `ParseID` cuts `@` (variant) and `#` (member) off the path, so `tests/test_a#b.sh` parses as path `tests/test_a` + member `b.sh`. The listed id then is not a plain file id, and the run's start row does not match it (`missing_start`).
- Repro (2026-10-26, engine at `0c2f693c9`): a scratch repo with `aitestmap/runners.yaml` holding one `builtin: bash-file` entry, committed `tests/test_a#b.sh` (`exit 0`) and `tests/test_ok.sh`. `ait-testmap run --all` gives:
  - `UNIT:tests/test_a#b.sh|error`;
  - `CAUSE:1|reconciliation|exit_mismatch`;
  - `PROTOCOL_ERROR:1|missing_start:tests/test_a#b.sh`.
- t1854_9's pytest adapter guards the same spot with `id, err := registry.ParseID(rel); err != nil || id.String() != rel || …` → a list error naming the path (`pytest.go` `pytestList`).

## Suggested fix

Apply the same check in `bashFileList`: refuse (list error, naming the path) when `id.String() != rel` or the id has a member/variant. Add a regression with a committed `tests/test_a#b.sh` asserting the Load error, plus an isolated red proof. Consider whether the shared `gitInventory` caller should own the check for both adapters.
