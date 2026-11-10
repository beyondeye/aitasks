"""sitrep_tui_requests.py - the requests the sitrep TUI types into its agent (t2211_4).

``AGENT_REQUESTS`` is the ONE table of them: the TUI's bindings are built from
it, and the sitrep skill's parity test (t2211_5) reads its templates against the
``>`` codes the skill documents. The delivery itself -- readiness, the guarded
paste, the per-Enter composer proof -- lives in
``monitor/agent_request_delivery.py``; this module only builds the line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sitrep_todo as st
from monitor import agent_request_delivery as delivery


@dataclass(frozen=True)
class AgentRequest:
    """One request key: the Textual ``action``, its default ``key``, the footer
    ``label``, and the ``template`` typed into the agent (``{cid}``,
    ``{theme}``, ``{text}`` are filled from the item / the ask dialog)."""

    action: str
    key: str
    label: str
    template: str


AGENT_REQUESTS = (
    AgentRequest("request_triage", "t", "Triage", ">t {cid}"),
    AgentRequest("request_ask", "a", "Ask agent", ">q {cid} {text}"),
    AgentRequest("request_situation", "w", "Situation text", ">w {theme}"),
    AgentRequest("request_trail_refresh", "T", "Trail refresh", ">tr {cid}"),
    AgentRequest("request_pick_advice", "n", "Pick advice", ">p"),
)
REQUESTS_BY_ACTION = {r.action: r for r in AGENT_REQUESTS}
#: The requests that act on the selected item (the rest are store-wide).
ITEM_REQUESTS = frozenset({"request_triage", "request_ask", "request_situation",
                           "request_trail_refresh"})

#: Longest question the ask dialog accepts (a 300-char line was measured to land
#: in all three agents' composers as typed text, no paste placeholder).
ASK_MAX_CHARS = 300

_ASK_REASONS = {
    "empty": "Type a question.",
    "too_long": f"Keep it to {ASK_MAX_CHARS} characters.",
    "control_character": "Use one plain line (no tabs, line breaks or control characters).",
    "trailing_mention": ("Do not end with an @mention: it opens the agent's file picker, "
                         "which would take the Enter."),
}
_SPACES_RE = re.compile(r" {2,}")


def normalize_ask_text(text: str) -> str:
    """The ask text as it will be typed: trimmed, runs of spaces collapsed
    (the composer proof needs single spaces). Other whitespace is left for
    :func:`ask_text_error` to refuse, never silently rewritten."""
    return _SPACES_RE.sub(" ", (text or "").strip(" "))


def ask_text_error(text: str) -> str:
    """Why the (normalized) ask text is refused, as a sentence, or ``""``."""
    norm = normalize_ask_text(text)
    if not norm:
        return _ASK_REASONS["empty"]
    if len(norm) > ASK_MAX_CHARS:
        return _ASK_REASONS["too_long"]
    # Content rules only: the command-prefix rule belongs to the ASSEMBLED line,
    # which starts with the request code (`build_request` checks it), so a
    # question may begin with `/`, `#`, `$` ...
    reason = delivery.request_line_error(norm, check_prefix=False)
    if reason == "spacing":
        reason = "control_character"
    return _ASK_REASONS.get(reason, "") if reason else ""


def item_theme(store: "st.TodoStore | None", item: "st.Item | None") -> str:
    """The item's context theme when it is a valid theme token, else ``""``."""
    if store is None or item is None:
        return ""
    ctx = store.contexts.get(item.num)
    theme = getattr(ctx, "theme", "") if ctx is not None else ""
    return theme if theme and st.THEME_RE.match(theme) else ""


def build_request(req: AgentRequest, item: "st.Item | None" = None,
                  store: "st.TodoStore | None" = None, text: str = "") -> str:
    """The line ``req`` types, or ``""`` when it cannot be built safely.

    Store and user text are only ever FORMAT ARGUMENTS (braces in them stay
    literal), and the finished line must pass the delivery's one-line rule.
    """
    fields = {"cid": item.cid if item is not None else "",
              "theme": item_theme(store, item), "text": normalize_ask_text(text)}
    if "{cid}" in req.template and not fields["cid"]:
        return ""
    if "{theme}" in req.template and not fields["theme"]:
        return ""
    if "{text}" in req.template and (not fields["text"] or ask_text_error(text)):
        return ""
    line = req.template.format(**fields)
    if not line.startswith(">") or delivery.request_line_error(line):
        return ""
    return line


class TmuxGateway:
    """The ``monitor`` duck type the roles probe and the delivery share: one
    ``TmuxClient`` (the gateway), sync, async and stdin calls. It holds no
    pane -- every request resolves its target afresh."""

    def __init__(self, client=None) -> None:
        if client is None:
            from tmux_exec import TmuxClient
            client = TmuxClient()
        self._client = client

    def tmux_run(self, args, timeout: float = 5.0):
        return self._client.run(args, timeout=timeout)

    async def tmux_run_async(self, args, timeout: float = 5.0):
        return await self._client.run_async(args, timeout=timeout)

    def tmux_run_input(self, args, data: str, timeout: float = 5.0):
        return self._client.run_with_input(args, data, timeout=timeout)
