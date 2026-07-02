"""interactions — platform-agnostic interaction surface.

Slice of the layer: the verbs users click instead of type. Normalizes
Discord components/modals/slash commands and Slack Block Kit
elements/views/slash commands into generic outbound primitives, and every
click/select/submit/command into one inbound ``Interaction`` type
("abstract concepts, not APIs").

Purpose: higher layers compose native-feeling UX (approval buttons, pickers,
forms) and consume the results without leaking SDK payloads upward or
falling back to text-parsing. These are deliberately *generic* primitives —
no aitasks-specific components live here.

Contract: stdlib-only; list/dict defaults via ``field(default_factory=...)``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .model import Actor, ConversationRef, MessageRef

__all__ = [
    "Button",
    "SelectMenu",
    "SelectOption",
    "ActionRow",
    "FormField",
    "Modal",
    "Form",
    "SlashCommand",
    "CommandOption",
    "InteractionType",
    "Interaction",
]


@dataclass
class Button:
    """A clickable button attached to a message.

    What it abstracts: a Discord button component / a Slack Block Kit
    ``button`` element.

    Purpose: the primary one-tap signal primitive (approve/reject/etc.).
    Contract: ``custom_id`` round-trips into the resulting
    ``Interaction.custom_id`` so consumers can route clicks; ``style`` is a
    generic hint (``"primary"``/``"secondary"``/``"danger"``) each adapter
    maps to its closest native style.
    """

    custom_id: str
    label: str
    style: str = "primary"
    disabled: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class SelectOption:
    """One choice inside a :class:`SelectMenu`.

    What it abstracts: a Discord select option / a Slack ``option`` object.

    Purpose: value/label separation — ``value`` is what the consumer
    receives, ``label`` what the user reads.
    """

    value: str
    label: str
    description: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SelectMenu:
    """A dropdown select attached to a message.

    What it abstracts: a Discord string-select component / a Slack
    ``static_select`` (or multi-select) element.

    Purpose: the pick-one-of-N primitive. Contract: selections arrive as an
    ``Interaction`` of type SELECT with the chosen values under
    ``Interaction.values["values"]``; ``min_values``/``max_values`` express
    multi-select where the platform supports it.
    """

    custom_id: str
    options: list[SelectOption]
    placeholder: str | None = None
    min_values: int = 1
    max_values: int = 1
    metadata: dict = field(default_factory=dict)


@dataclass
class ActionRow:
    """A horizontal grouping of components on a message.

    What it abstracts: a Discord action row / a Slack ``actions`` block.

    Purpose: the unit passed as ``components=`` to ``send_message`` /
    ``edit_message`` / ``respond`` — adapters translate the grouping to the
    platform's layout rules. Contract: contains buttons and select menus
    only (the primitives both platforms can render inline).
    """

    components: list[Button | SelectMenu]
    metadata: dict = field(default_factory=dict)


@dataclass
class FormField:
    """One input field inside a :class:`Modal`.

    What it abstracts: a Discord text-input component / a Slack Block Kit
    ``input`` block element.

    Purpose: structured free-text capture. Contract: ``kind`` is a generic
    hint (``"text"``/``"multiline"``) mapped per platform; submitted values
    arrive keyed by ``custom_id`` in ``Interaction.values``.
    """

    custom_id: str
    label: str
    kind: str = "text"
    required: bool = True
    placeholder: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Modal:
    """A pop-up form opened in response to an interaction.

    What it abstracts: a Discord modal / a Slack ``views.open`` modal view.

    Purpose: multi-field structured input (the only rich-form primitive both
    platforms share). Contract: opened only via ``ChatAdapter.open_modal``
    from a live interaction (both platforms require an interaction trigger);
    submission arrives as an ``Interaction`` of type MODAL_SUBMIT whose
    ``values`` map field ``custom_id`` → submitted value. ``Form`` is a
    public alias of this class.
    """

    custom_id: str
    title: str
    fields: list[FormField]
    metadata: dict = field(default_factory=dict)


# Public alias — some call sites read better as Form (see Modal docstring).
Form = Modal


@dataclass
class CommandOption:
    """One declared argument of a :class:`SlashCommand`.

    What it abstracts: a Discord application-command option / a Slack slash
    command's free-text argument convention (Slack has no typed options —
    adapters parse positionally/named as documented per adapter).

    Purpose: lets command specs declare their arguments once, platform-
    honestly: rich typing where Discord supports it, best-effort parsing on
    Slack. Contract: ``kind`` is a generic hint (``"string"``/``"integer"``/
    ``"boolean"``/``"user"``).
    """

    name: str
    description: str
    kind: str = "string"
    required: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class SlashCommand:
    """A slash-command registration spec.

    What it abstracts: a Discord application command / a Slack slash
    command (app-config-level on Slack; adapters document what
    ``register_commands`` can and cannot automate per platform).

    Purpose: declarative command surface — higher layers declare commands
    once and receive invocations as ``Interaction``s of type COMMAND.
    Contract: ``name`` arrives in ``Interaction.custom_id``; parsed
    arguments in ``Interaction.values``.
    """

    name: str
    description: str
    options: list[CommandOption] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class InteractionType(Enum):
    """The gesture that produced an :class:`Interaction`.

    What it abstracts: Discord interaction types (component/modal/command) /
    Slack interactivity payload types (``block_actions``,
    ``view_submission``, slash command).

    Purpose: one routing key for all click-shaped input.
    """

    BUTTON = "button"
    SELECT = "select"
    MODAL_SUBMIT = "modal_submit"
    COMMAND = "command"


@dataclass
class Interaction:
    """An inbound user gesture (click, selection, form submit, command).

    What it abstracts: a Discord ``INTERACTION_CREATE`` payload / a Slack
    interactivity payload, normalized and **already acknowledged** by the
    adapter.

    Purpose: the single inbound type for all component/command input,
    carrying who acted (``actor``), where (``conversation`` +
    ``message``), which component (``custom_id``) and what was submitted
    (``values``).

    Contract: adapters auto-defer/ack on receipt — an ``Interaction`` is
    yielded pre-acked (``_acked=True``; ``ChatAdapter.ack`` is an
    idempotent no-op), keeping the platforms' ~3 s ack deadline off the
    consumer's path. Consumers reply at their own pace via ``respond`` /
    ``follow_up`` / ``open_modal``; past the follow-up window those raise
    ``InteractionExpired``. Interactions are NOT replayable after a
    disconnect — higher layers must persist outcomes on receipt and
    re-prompt if a window was missed.
    """

    id: str
    type: InteractionType
    actor: Actor
    conversation: ConversationRef
    message: MessageRef | None = None
    custom_id: str | None = None
    values: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    _acked: bool = field(default=False, repr=False, compare=False)
