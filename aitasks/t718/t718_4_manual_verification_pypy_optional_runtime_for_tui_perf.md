---
priority: medium
effort: medium
depends: [t718_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [718_1, 718_2, 718_3]
created_at: 2026-04-30 10:36
updated_at: 2026-04-30 10:36
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t718_1] shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/lib/python_resolve.sh — clean
- [ ] [t718_1] bash tests/test_python_resolve_pypy.sh — passes (precedence table covered)
- [ ] [t718_1] Fresh install: bash install.sh --dir /tmp/aitt718_v --force && cd /tmp/aitt718_v && ./ait setup --with-pypy completes; ~/.aitask/pypy_venv/bin/python -c "import sys, textual; assert sys.implementation.name == 'pypy'" succeeds
- [ ] [t718_1] Fresh install without --with-pypy: ~/.aitask/pypy_venv does NOT get created
- [ ] [t718_1] git diff --stat shows changes ONLY in lib/python_resolve.sh, aitask_setup.sh, and tests/test_python_resolve_pypy.sh — no TUI launcher modified in t718_1
- [ ] [t718_2] Without PyPy installed: ./ait board, ./ait codebrowser, ./ait settings, ./ait stats-tui, ./ait brainstorm <id> all launch under CPython exactly as before
- [ ] [t718_2] With PyPy installed: each of the 5 fast-path TUIs auto-launches under PyPy (verify via sys.implementation.name from launcher venv)
- [ ] [t718_2] AIT_USE_PYPY=0 ./ait board (with PyPy installed) launches under CPython (override works)
- [ ] [t718_2] AIT_USE_PYPY=1 ./ait board (without PyPy installed) errors with "Run 'ait setup --with-pypy' first" message
- [ ] [t718_2] AIT_USE_PYPY=1 ./ait monitor and AIT_USE_PYPY=1 ./ait minimonitor still use CPython (monitor/minimonitor never call require_ait_python_fast)
- [ ] [t718_2] Visual smoke test: each of the 5 modified TUIs renders, scrolls, accepts input correctly under PyPy (no missing-deps errors, no widget-render breakage)
- [ ] [t718_2] shellcheck clean on all 5 modified TUI launcher scripts
- [ ] [t718_3] cd website && hugo build --gc --minify succeeds with no broken-cross-link warnings on the new content
- [ ] [t718_3] grep -n "AIT_USE_PYPY\|--with-pypy" CLAUDE.md website/content/docs/ -r shows both env var and flag documented in user-facing places
- [ ] [t718_3] git diff --stat shows ONLY .md files (and possibly website/...) — no .aitask-scripts/* edits in t718_3
- [ ] [t718_3] Local website preview (cd website && ./serve.sh): new PyPy page renders, links resolve, AIT_USE_PYPY precedence table is formatted correctly
- [ ] [Aggregate] git revert <t718 commits> on a clean checkout cleanly removes PyPy support without touching CPython behavior (parent acceptance criterion)
- [ ] [Aggregate] After full t718 implementation: AIT_USE_PYPY semantics match the documented precedence table end-to-end (1/0/unset cases × installed/not-installed cases)
