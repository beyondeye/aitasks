"""An in-memory tmux server for tests of guarded pane dispatches (t2088).

Answers the verbs `helper_panes.kill_bound_helpers` and
`monitor_core.TmuxMonitor.kill_agent_pane_smart` issue — `list-panes` (``-a``
or a window / `%N` target), `if-shell -F`, `kill-pane`, `kill-window`,
`display-message -p` — from a mutable pane model, the way the real server does:

* `if-shell -F` evaluates its condition AT DISPATCH TIME against the current
  model, and only then runs the branch through :meth:`run`, so a nested
  `kill-pane` is recorded like a bare one. It answers 0 whether or not the
  branch fired, as tmux does (measured on tmux 3.8). The supported grammar is
  the subset the guards use: `#{==:#{fmt},value}` and binary `#{&&:A,B}`,
  nested.
* `#{pid}` is SERVER-scoped: it expands from :attr:`server_pid`, for every
  pane, and for a gone one too.
* `display-message -p -t <gone pane>` answers 0 with empty pane-scoped fields
  (measured on tmux 3.8).

:attr:`before_dispatch` runs just before every `if-shell` is evaluated, so a
test can mutate the model BETWEEN a listing and the guarded kill — the window a
tmux restart, a freeze or a rebind can fall into.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable


class TmuxServerModel:
    """``panes`` maps pane id -> fields (option names keyed with their ``@``)."""

    def __init__(self, panes: dict[str, dict[str, str]],
                 server_pid: str = "9999") -> None:
        self.panes = panes
        self.server_pid = server_pid
        self.calls: list[list[str]] = []
        self.kill_ok = True
        self.list_ok = True
        self.before_dispatch: Callable[[], None] | None = None

    # -- the gateway surface --------------------------------------------------
    def __call__(self, args, *_rest, **_kw):
        return self.run(args)

    def run(self, args, timeout=None):  # noqa: ARG002 - gateway signature
        args = list(args)
        self.calls.append(args)
        verb = args[0] if args else ""
        if verb == "list-panes":
            return self._list(args)
        if verb == "if-shell":
            return self._if_shell(args)
        if verb in ("kill-pane", "kill-window"):
            return self._kill(args)
        if verb == "display-message":
            return self._display(args)
        return 0, ""

    # -- format expansion -----------------------------------------------------
    def _field(self, pane: dict[str, str] | None, key: str) -> str:
        if key == "pid":
            return self.server_pid
        if pane is None:
            return ""
        return str(pane.get(key, ""))

    def _expand(self, fmt: str, pane: dict[str, str] | None) -> str:
        return "\t".join(self._field(pane, spec.strip("#{}"))
                         for spec in fmt.split("\t"))

    @staticmethod
    def _split_top(body: str) -> list[str]:
        parts, depth, start = [], 0, 0
        for i, ch in enumerate(body):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(body[start:i])
                start = i + 1
        parts.append(body[start:])
        return parts

    def eval_condition(self, cond: str, pane: dict[str, str]) -> bool:
        assert cond.startswith("#{") and cond.endswith("}"), cond
        body = cond[2:-1]
        if body.startswith("&&:"):
            operands = self._split_top(body[3:])
            assert len(operands) == 2, f"`&&` is binary: {cond!r}"
            return all(self.eval_condition(c, pane) for c in operands)
        if body.startswith("==:"):
            lhs, rhs = self._split_top(body[3:])
            assert lhs.startswith("#{") and lhs.endswith("}"), cond
            return self._field(pane, lhs[2:-1]) == rhs
        raise AssertionError(f"unsupported condition: {cond!r}")

    # -- verbs ----------------------------------------------------------------
    @staticmethod
    def _target(args: list[str]) -> str:
        return args[args.index("-t") + 1] if "-t" in args else ""

    def _list(self, args):
        if not self.list_ok:
            return 1, ""
        fmt = args[args.index("-F") + 1]
        target = self._target(args)
        rows = []
        if "-a" in args or not target:
            selected = list(self.panes.values())
        else:
            if target.startswith("%"):
                pane = self.panes.get(target)
                if pane is None:
                    return 1, ""
                window = pane.get("window", "")
            else:
                window = target.split(":")[-1]
            selected = [p for p in self.panes.values()
                        if p.get("window", "") == window]
        for pane in selected:
            rows.append(self._expand(fmt, pane))
        return 0, "\n".join(rows) + ("\n" if rows else "")

    def _if_shell(self, args):
        if self.before_dispatch is not None:
            self.before_dispatch()
        pane = self.panes.get(self._target(args))
        if pane is None:
            return 1, ""
        if self.eval_condition(args[-2], pane):
            for piece in args[-1].split(" ; "):
                rc, _ = self.run(shlex.split(piece))
                if rc != 0:
                    break
        return 0, ""

    def _kill(self, args):
        if not self.kill_ok:
            return 1, "kill refused"
        target = self._target(args)
        if target not in self.panes:
            return 1, ""
        if args[0] == "kill-window":
            window = self.panes[target].get("window", "")
            for pid in [k for k, v in self.panes.items()
                        if v.get("window", "") == window]:
                self.panes.pop(pid)
        else:
            self.panes.pop(target)
        return 0, ""

    def _display(self, args):
        pane = self.panes.get(self._target(args))
        return 0, self._expand(args[-1], pane) + "\n"

    # -- inspection -----------------------------------------------------------
    def bare_kills(self) -> list[list[str]]:
        """`kill-pane` calls issued OUTSIDE an `if-shell` branch.

        A nested kill is recorded right after the `if-shell` that ran it.
        """
        bare = []
        for i, call in enumerate(self.calls):
            if call and call[0] == "kill-pane":
                prev = self.calls[i - 1] if i else []
                if not (prev and prev[0] == "if-shell"
                        and prev[-1] == " ".join(call)):
                    bare.append(call)
        return bare
