---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [sitrep, tests, monitor]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2217
followup_kind: upstream_defect
created_at: 2026-11-06 00:14
updated_at: 2026-11-06 00:21
---

## Origin
Spawned from t2217 during Step 8b review.

## Upstream defect
- tests/test_sitrep_window.py:169 — `test_booting_companion_without_a_marker_does_not_match` classifies a just-`Popen`ed process by its cmdline and fails intermittently under a loaded parallel suite (cmdline not yet exec'd); observed once in this session's full run, passes in isolation.

## Diagnostic context
During t2217 (minimonitor shift+arrow keys), `bash tests/run_all_python_tests.sh` ended `PYTHON SUITE: FAILED (runner=pytest, exit=1)` on exactly this test. It does not import minimonitor code; `pytest tests/test_sitrep_window.py` passed 42/42 both on the working tree and on a clean `git archive HEAD` export, so the failure is load-dependent, not caused by t2217.

The test spawns `python -c "import time; time.sleep(30)" minimonitor` and immediately asks the shared companion classifier (cmdline fallback, no `@aitask_monitor_kind` marker) whether that pid is a minimonitor companion. Right after `Popen` returns, `/proc/<pid>/cmdline` can still show the pre-exec image or be briefly unreadable, so the cmdline-based rule can read the wrong argv under a loaded box.

## Suggested fix
Wait until the child's `/proc/<pid>/cmdline` actually contains `minimonitor` (bounded poll) before classifying — or inject the cmdline through the classifier's seam rather than racing a real process.
