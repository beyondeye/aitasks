---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-03 16:24
updated_at: 2026-06-03 16:25
---

## Problem

`ait setup` (with PyPy opted in) fails on macOS:

```
× Preparing metadata (pyproject.toml) did not run successfully.
  Python reports SOABI: pypy310-pp73
  Unsupported platform: pp73
  Checking for Rust toolchain....
  Rust not found, installing into a temporary directory
error: metadata-generation-failed
× Encountered error while generating package metadata.
╰─> minijinja
```

`minijinja` is a Rust extension; PyPI has no PyPy wheel for `pypy310-pp73`,
so pip falls back to building from source, which needs Rust.

## Root cause

`.aitask-scripts/aitask_setup.sh:573` (the **PyPy** venv install line)
includes `'minijinja>=2.0,<3'`:

```bash
"$PYPY_VENV_DIR/bin/pip" install --quiet 'textual>=8.2.7,<9' 'pyyaml==6.0.3' \
  'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3' 'minijinja>=2.0,<3' 'pexpect>=4.9,<5'
```

But `minijinja` is imported only from `.aitask-scripts/lib/skill_template.py`,
which is invoked exclusively from `aitask_skill_render.sh` and
`aitask_skill_verify.sh`. Both call `require_ait_python` (CPython venv), never
the PyPy fast path. The PyPy fast path (`require_ait_python_fast`) is used
only by `aitask_board.sh`, and `.aitask-scripts/board/` has no minijinja
reference.

So `minijinja` on the PyPy install line is dead weight that also blocks
setup on macOS.

## Fix

Remove `'minijinja>=2.0,<3'` from `aitask_setup.sh:573` (the PyPy install
line). Leave `aitask_setup.sh:654` (the CPython install line) untouched —
that's where minijinja is actually needed and where prebuilt wheels exist.

## Validation

- [ ] Re-run `ait setup` on macOS with PyPy opted in; PyPy venv installs
      cleanly with no Rust toolchain required.
- [ ] `ait skill-render <some-skill> --profile <p> --agent claude` still
      works (uses CPython venv).
- [ ] `ait board` still launches via the PyPy fast path.
- [ ] `shellcheck .aitask-scripts/aitask_setup.sh` clean.

## Notes

- No need to also gate by OS — minijinja is unused under PyPy on every
  platform; removing it unconditionally is correct.
- No corresponding change needed in `seed/` (no PyPy install line there).
- No docs reference the PyPy minijinja install; no doc updates required.
