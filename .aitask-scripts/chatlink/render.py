"""render — relay questions → ``chat`` components, and answer assembly.

Gateway-side only (imports ``chat``; the agent side never imports this).
Normative spec: ``aidocs/chat/qa_relay_protocol.md`` — capability gating is
fail-closed (``RenderRejected``), degradation branches only on
``Capabilities`` fields, never platform name.
"""
from __future__ import annotations

from dataclasses import dataclass

from chat.capabilities import Capabilities
from chat.interactions import (
    ActionRow,
    Button,
    FormField,
    Interaction,
    InteractionType,
    Modal,
    SelectMenu,
    SelectOption,
)

from .relay import (
    Answer,
    Question,
    RelayError,
    build_custom_id,
    parse_custom_id,
)

__all__ = [
    "COMPONENT_FREETEXT",
    "COMPONENT_MODAL",
    "COMPONENT_MODAL_FIELD",
    "COMPONENT_SELECT",
    "AnswerMismatch",
    "RenderRejected",
    "RenderedQuestion",
    "assemble_answer",
    "build_modal",
    "is_free_text_trigger",
    "is_page_nav",
    "page_count",
    "render_question",
]

# Reserved component tags (aidocs/chat/qa_relay_protocol.md, contract 4).
COMPONENT_SELECT = "select"
COMPONENT_FREETEXT = "freetext"
COMPONENT_MODAL = "modal"
COMPONENT_MODAL_FIELD = "ftfield"
_PAGE_PREFIX = "pg"

# A select menu holds at most 25 options on both platforms; paginated pages
# hold 24 (one slot of headroom keeps the page math obvious and symmetric).
SELECT_MAX_OPTIONS = 25
PAGE_SIZE = 24


class RenderRejected(RelayError):
    """A question cannot be rendered for this adapter's capabilities.

    Fail-closed: raised instead of silently emitting unsupported components
    or silently dropping a requested affordance."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class AnswerMismatch(RelayError):
    """The interaction does not belong to the given question (stale or
    foreign) — the daemon treats this as a stale interaction."""


@dataclass
class RenderedQuestion:
    """One page of a rendered question.

    ``text_chunks``: message text split to ``max_message_length`` — the
    daemon sends them in order and attaches ``rows`` to the LAST chunk.
    ``page``/``page_count``: pagination state (stateless — the nav buttons
    carry the target page in their custom_id).
    """

    text_chunks: list[str]
    rows: list[ActionRow]
    page: int = 0
    page_count: int = 1


def _require(cond: bool, reason: str) -> None:
    if not cond:
        raise RenderRejected(reason)


def _chunk_text(text: str, limit: int) -> list[str]:
    """Split text into ≤ limit chunks, preferring newline boundaries."""
    if limit <= 0 or len(text) <= limit:
        return [text]
    chunks = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind("\n", 1, limit)
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    if rest:
        chunks.append(rest)
    return chunks


def page_count(q: Question) -> int:
    """Number of select pages for a question's options (≥ 1)."""
    n = len(q.options)
    if n <= SELECT_MAX_OPTIONS:
        return 1
    return (n + PAGE_SIZE - 1) // PAGE_SIZE


def render_question(q: Question, capabilities: Capabilities,
                    page: int = 0) -> RenderedQuestion:
    """Render one page of a question as text chunks + component rows.

    Capability gating (fail-closed, spec §Rendering rules): options require
    ``supports_selects``; ``allow_free_text`` requires ``supports_buttons``
    AND ``supports_modals``. Branches only on ``Capabilities`` fields.
    """
    q.validate()
    pages = page_count(q)
    if page < 0 or page >= pages:
        raise RenderRejected(f"page {page} out of range (0..{pages - 1})")

    if q.options:
        _require(capabilities.supports_selects,
                 "question has options but adapter lacks select support")
    if pages > 1:
        # Nav is button-based, and page-local selects cannot accumulate a
        # multi-selection across pages — v1 rejects that combination
        # (documented extension point in the protocol doc).
        _require(capabilities.supports_buttons,
                 "paginated options require button support (nav buttons)")
        _require(not q.multi_select,
                 "multi-select with paginated options is unsupported in v1")
    if q.allow_free_text:
        _require(capabilities.supports_buttons,
                 "free text requires button support")
        _require(capabilities.supports_modals,
                 "free text requires modal support")

    rows: list[ActionRow] = []

    if q.options:
        if pages == 1:
            page_options = q.options
        else:
            page_options = q.options[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        select = SelectMenu(
            custom_id=build_custom_id(q.session_id, q.seq, COMPONENT_SELECT),
            options=[SelectOption(value=o.value, label=o.label,
                                  description=o.description or None)
                     for o in page_options],
            placeholder=q.header or None,
            min_values=1,
            max_values=len(page_options) if q.multi_select else 1,
        )
        rows.append(ActionRow(components=[select]))

        if pages > 1:
            # Stateless nav: each button's custom_id carries the target page.
            prev_page = max(page - 1, 0)
            next_page = min(page + 1, pages - 1)
            nav = ActionRow(components=[
                Button(custom_id=build_custom_id(
                           q.session_id, q.seq, f"{_PAGE_PREFIX}{prev_page}"),
                       label="Prev", style="secondary", disabled=page == 0),
                Button(custom_id=build_custom_id(
                           q.session_id, q.seq, f"{_PAGE_PREFIX}{next_page}"),
                       label="Next", style="secondary",
                       disabled=page == pages - 1),
            ])
            rows.append(nav)

    if q.allow_free_text:
        rows.append(ActionRow(components=[
            Button(custom_id=build_custom_id(q.session_id, q.seq,
                                             COMPONENT_FREETEXT),
                   label="Answer…", style="primary"),
        ]))

    text = f"**{q.header}** — {q.text}" if q.header else q.text
    if pages > 1:
        text += f"\n(options page {page + 1}/{pages})"
    chunks = _chunk_text(text, capabilities.max_message_length)

    return RenderedQuestion(text_chunks=chunks, rows=rows, page=page,
                            page_count=pages)


def build_modal(q: Question) -> Modal:
    """The free-text modal for a question (opened by the daemon on the
    "Answer…" button interaction — contract 5)."""
    return Modal(
        custom_id=build_custom_id(q.session_id, q.seq, COMPONENT_MODAL),
        title=q.header or "Answer",
        fields=[FormField(
            custom_id=build_custom_id(q.session_id, q.seq,
                                      COMPONENT_MODAL_FIELD),
            label=q.text[:45] if len(q.text) > 45 else q.text,
            kind="multiline",
        )],
    )


def _match_question(q: Question, interaction: Interaction) -> str:
    """Validate the interaction belongs to ``q``; return its component."""
    if not interaction.custom_id:
        raise AnswerMismatch("interaction has no custom_id")
    session_id, seq, component = parse_custom_id(interaction.custom_id)
    if session_id != q.session_id or seq != q.seq:
        raise AnswerMismatch(
            f"interaction {interaction.custom_id!r} does not match "
            f"question {q.session_id}/{q.seq}")
    return component


def is_free_text_trigger(q: Question, interaction: Interaction) -> bool:
    """True if this interaction is the "Answer…" button of ``q`` (the daemon
    responds by opening ``build_modal(q)`` — never an answer by itself)."""
    try:
        return _match_question(q, interaction) == COMPONENT_FREETEXT
    except (AnswerMismatch, RelayError):
        return False


def is_page_nav(q: Question, interaction: Interaction) -> int | None:
    """If this interaction is a pagination nav button of ``q``, return the
    target page; else None."""
    try:
        component = _match_question(q, interaction)
    except (AnswerMismatch, RelayError):
        return None
    if component.startswith(_PAGE_PREFIX) and component != COMPONENT_SELECT:
        suffix = component[len(_PAGE_PREFIX):]
        if suffix.isdigit():
            return int(suffix)
    return None


def assemble_answer(q: Question, interaction: Interaction) -> Answer:
    """Assemble a validated ``answered`` Answer from an interaction.

    - SELECT: ``interaction.values["values"]`` are option **values** —
      each must belong to ``q``.
    - MODAL_SUBMIT: the modal field's text (keyed by the field custom_id)
      becomes ``free_text``.
    Raises ``AnswerMismatch`` for foreign/stale interactions and the
    free-text trigger button (which is not an answer).
    """
    component = _match_question(q, interaction)

    if interaction.type == InteractionType.SELECT:
        if component != COMPONENT_SELECT:
            raise AnswerMismatch(
                f"select interaction on unexpected component {component!r}")
        raw = interaction.values.get("values", [])
        if not isinstance(raw, list) or not raw:
            raise AnswerMismatch("select interaction carries no values")
        if not q.multi_select and len(raw) != 1:
            raise AnswerMismatch(
                f"single-select question got {len(raw)} values")
        known = {o.value for o in q.options}
        unknown = [v for v in raw if v not in known]
        if unknown:
            raise AnswerMismatch(f"unknown option values: {unknown}")
        return Answer(id=q.id, seq=q.seq, status="answered",
                      values=list(raw), free_text=None,
                      answered_by=interaction.actor.id)

    if interaction.type == InteractionType.MODAL_SUBMIT:
        if component != COMPONENT_MODAL:
            raise AnswerMismatch(
                f"modal submit on unexpected component {component!r}")
        field_id = build_custom_id(q.session_id, q.seq, COMPONENT_MODAL_FIELD)
        text = interaction.values.get(field_id)
        if not isinstance(text, str) or not text.strip():
            raise AnswerMismatch("modal submit carries no text")
        return Answer(id=q.id, seq=q.seq, status="answered", values=[],
                      free_text=text, answered_by=interaction.actor.id)

    raise AnswerMismatch(
        f"interaction type {interaction.type} is not an answer "
        f"(component {component!r})")
