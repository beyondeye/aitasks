---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-13 11:55
updated_at: 2026-10-13 15:50
completed_at: 2026-10-13 15:50
---

## Origin

Spawned from t1954_1 during Step 8b review. The defect was found by the t1954 parser-research baseline matrix (`aidocs/testing_engine/t1954_parser_research/results/matrix_baseline.md`, fixture `corpus/python/bom_doc.py`) and reproduced by hand.

## Upstream defect

- `goengines/internal/testmap/annot/lexctx.go:555 — classifyPython does not skip a leading UTF-8 BOM, so a BOM-prefixed module's docstring (and its testmap: records) is not detected (CPython's ast.get_docstring sees it)`
- `goengines/internal/testmap/annot/rewrite.go:420-432 — fixedPosition then places a fresh file-level line at 0, above the BOM; Apply writes it and the module stops running (SyntaxError U+FEFF). Reproduced in corpus/python/bom_doc.py; exposure today nil (0 BOM files in 5,723 sources across the six surveyed repos)`

(Line numbers are at the t1954 pinned baseline `f096db065`; M2.3 / t1853_3 is editing `annot`, so re-locate them before fixing.)

## Diagnostic context

- **Fixture:** a UTF-8 BOM, then `"""Doc after a BOM.\n\ntestmap:covers src/bom_doc.py\n"""`, then `print("bom")`.
  - CPython reads the docstring, including the `testmap:` line.
  - The landed lexer does not: line 1 starts with the BOM bytes.
  - So the docstring record is missing (`read: missing … origin=docstring`).
- **Resulting write:** `annotate member= source=src/bom_doc.py` then becomes a fresh file-level insertion.
  - `fixedPosition` falls to `leading(0)` = 0, so the new comment is written ABOVE the BOM, moving the BOM to the start of line 2.
  - `python3` then fails with `SyntaxError: invalid non-printable character U+FEFF` (exit 0 → 1), verified independently of the harness.
  - `Apply`'s own checks pass: every other line keeps its bytes and class.
- **Not affected:**
  - Bash files with a BOM (bash gives the BOM no meaning; correctly not special-cased).
  - Go files with a BOM (fine in the matrix).

## Suggested fix

Treat a leading UTF-8 BOM as part of line 1's prefix for the lexers that honour it (Python; also check Kotlin/Go behaviour): classify after the BOM, and never insert at line 0 above a BOM (insert after it, or refuse). Add the t1954 `bom_doc.py` case (docstring read, refused docstring write, placement after DocEnd, BOM preserved) to annot's own tests. The t1954 harness re-runs it (`go run ./cmd/t1954 matrix --provider baseline --lang python`, after moving `baseline/PIN`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-13T10:34:44Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-13T12:45:57Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-13T12:50:07Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:032440b23357ca69

> **✅ gate:risk_evaluated** run=2026-10-13T12:50:07Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1969/risk_evaluated_2026-10-13T12:50:07Z-risk_evaluated-a1.log`
