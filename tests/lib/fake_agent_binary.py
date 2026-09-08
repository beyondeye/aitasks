"""A real executable named after a code agent, so its `comm` IS that name (t1729).

Two live modules need the same thing: a long-running process that a name-based
resolver reads as `claude` or `codex`, so that
`agent_keys.agent_key_from_command` — which lowercases the **basename** of
whatever it is handed — resolves it.

Not a `#!` script: a script's `comm` is its interpreter's, so a `sh` wrapper
named `codex` reports `sh` and the fixture measures nothing. Not an `argv[0]`
rename either: `exec -a claude /bin/sleep` still reports `sleep`, because both
readers below name a process after the file it executed, never after `argv[0]`
(measured under tmux on macOS).

**Why this is not just `shutil.copy` of `/bin/sleep`.** That is what the
fixtures used to do, and macOS breaks it twice over — the second break only
becoming visible once the first is fixed:

1. `shutil.copy2` runs `copystat`, which calls `chflags` on the destination, and
   macOS ships `/bin/sleep` with the SIP `restricted` flag → `PermissionError:
   [Errno 1] Operation not permitted`. `shutil.copy` does not copy flags and
   gets past this.
2. The resulting copy **will not run**. `/bin/sleep` is a platform binary on the
   signed system volume; a copy of it anywhere else is SIGKILLed on exec (exit
   137). Neither clearing the flags, `codesign --remove-signature`, nor an
   ad-hoc `codesign -f -s -` rescues it — the constraint is on where the binary
   lives, not on its signature. Measured on macOS 15 / arm64.

So this module tries a ladder and **verifies each rung by running it**, rather
than branching on `sys.platform`: what matters is whether the result executes,
and that is directly testable. A future OS that fixes — or newly breaks — any of
this then needs no change here.

    1. copy the system `sleep`         — the historical fixture; what Linux uses
    2. copy a locally compiled sleeper — macOS, where rung 1 cannot run
    3. symlink to the system `sleep`   — opt-in; see `allow_symlink` below

**Rung 3 is not equivalent to the others, which is why it is opt-in.** The two
readers disagree about a symlink:

* `ps -o comm=` (used by `agent_keys._child_commands`) reports the path that was
  *invoked* — `/tmp/…/codex` on macOS, `codex` on Linux — so the basename is the
  agent name and the symlink works;
* tmux's `pane_current_command` reports the *resolved* executable, so a symlink
  named `claude` reads `sleep` and the fixture silently measures nothing.

A caller that reads panes through tmux must therefore leave `allow_symlink`
False and skip when `FakeAgentBinaryUnavailable` is raised.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile

__all__ = ["FakeAgentBinaryUnavailable", "fake_agent_binary"]

#: Sleeps for `argv[1]` seconds (default: effectively forever). Deliberately
#: argv-compatible with `sleep`, so callers can swap rungs without changing the
#: command lines they build.
_SLEEPER_C = """\
#include <stdlib.h>
#include <unistd.h>
int main(int argc, char **argv) {
    unsigned n = argc > 1 ? (unsigned)atoi(argv[1]) : 1000u;
    sleep(n);
    return 0;
}
"""

#: Unresolved sentinel — distinct from `None`, which records "we tried and there
#: is no toolchain". Compilation happens at most once per process.
_UNRESOLVED = object()
_compiled_sleeper: object = _UNRESOLVED


class FakeAgentBinaryUnavailable(RuntimeError):
    """No rung produced a usable binary — an environment limit, not a defect."""


def _sleep_binary() -> str:
    return shutil.which("sleep") or "/bin/sleep"


def _runs(path: str) -> bool:
    """Does `path` actually execute? `sleep 0` returns at once; a SIGKILL does not."""
    try:
        return subprocess.run([path, "0"], capture_output=True,
                              timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _compiled_sleeper_path() -> str | None:
    """Compile `_SLEEPER_C` once per process; None when no toolchain is usable."""
    global _compiled_sleeper
    if _compiled_sleeper is not _UNRESOLVED:
        return _compiled_sleeper  # type: ignore[return-value]

    _compiled_sleeper = None
    build = tempfile.mkdtemp(prefix="ait-fake-agent-build-")
    atexit.register(shutil.rmtree, build, True)
    source = os.path.join(build, "sleeper.c")
    with open(source, "w", encoding="utf-8") as fh:
        fh.write(_SLEEPER_C)

    for compiler in ("cc", "clang", "gcc"):
        exe = shutil.which(compiler)
        if not exe:
            continue
        out = os.path.join(build, "sleeper")
        try:
            done = subprocess.run([exe, "-o", out, source],
                                  capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            continue
        if done.returncode == 0 and _runs(out):
            _compiled_sleeper = out
            break
    return _compiled_sleeper  # type: ignore[return-value]


def fake_agent_binary(tmpdir: str, name: str, *,
                      allow_symlink: bool = False) -> str:
    """Create `<tmpdir>/<name>`, an executable that sleeps for `argv[1]` seconds.

    Returns its path. Pass `allow_symlink=True` only when the caller reads the
    process name through `ps -o comm=`; a tmux-based reader must not (see the
    module docstring). Raises `FakeAgentBinaryUnavailable` when no rung applies.
    """
    dest = os.path.join(tmpdir, name)

    for source in (_sleep_binary(), _compiled_sleeper_path()):
        if not source:
            continue
        if os.path.lexists(dest):
            os.unlink(dest)
        try:
            shutil.copy(source, dest)
            os.chmod(dest, 0o755)
        except OSError:
            continue
        if _runs(dest):
            return dest

    if allow_symlink:
        # Exec the real binary through a link that carries the name. Do NOT
        # chmod it: `os.chmod` follows the link and would try to change the mode
        # of the system binary itself.
        if os.path.lexists(dest):
            os.unlink(dest)
        os.symlink(_sleep_binary(), dest)
        return dest

    if os.path.lexists(dest):
        os.unlink(dest)
    raise FakeAgentBinaryUnavailable(
        f"cannot build a runnable executable named {name!r}: copying the system "
        "sleep produced a binary this platform refuses to execute, and no C "
        "compiler (cc/clang/gcc) is available to build one")
