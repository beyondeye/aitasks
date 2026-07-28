#!/usr/bin/env python3
"""import_isolated.py — import ONE test module in a fresh interpreter (t1236).

Driver for `tests/test_python_bootstrap_isolation.sh`. It exists because both
`pytest` and `unittest discover` import every `tests/test_*.py` into a **single**
interpreter, sharing one `sys.path`: the first module that inserts
`.aitask-scripts/lib` silently fixes the path for all the modules imported after
it. A test whose own bootstrap names the wrong directory therefore still passes
under the suite runner and breaks only at TUI runtime — the exact masking t1236
set out to remove. Dropping the runner's `PYTHONPATH` export removes the
runner-level half; this driver removes the intra-process half by giving each
file its own interpreter.

Importing is the whole check: a test file's `sys.path` bootstrap and its
top-level `from <module> import …` both run at module-exec time, so a wrong
bootstrap surfaces as a non-zero exit here. No test bodies are executed.

PARITY ASSUMPTION — `tests/` is a FLAT, NON-PACKAGE directory.
This driver loads each file as a top-level module named after its file stem
(`tests/test_tmux_exec.py` -> `test_tmux_exec`), because that is exactly what
`unittest discover` does when the start directory has no `__init__.py`, and
what pytest's prepend import mode does for the same layout. Verified: there is
no `__init__.py` anywhere under `tests/`, and no test file uses a relative
import.

If `tests/` ever becomes package-based (an `__init__.py` appears, or a test
starts using `from . import …` / package-level fixtures), that equivalence
breaks: such a module needs a dotted package name and its parent on `sys.path`,
and loading it under a bare stem here would report a failure the real runner
does not have. `tests/test_python_bootstrap_isolation.sh` carries a tripwire
that fails with instructions the moment that happens — evolve this driver to
derive the dotted module name from the package root rather than relaxing the
tripwire.

Usage: python3 tests/lib/import_isolated.py <path-to-test-file>
Exit:  0 = imported cleanly, non-zero = bootstrap (or import) failure.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <path-to-test-file>", file=sys.stderr)
        return 2

    path = pathlib.Path(argv[1]).resolve()
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 2

    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        print(f"cannot build import spec for: {path}", file=sys.stderr)
        return 2

    module = importlib.util.module_from_spec(spec)
    # Register before exec so a module that imports itself (or is referenced by
    # a decorator) resolves. The name is the file stem, never "__main__", so
    # `if __name__ == "__main__": unittest.main()` footers stay dormant.
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
