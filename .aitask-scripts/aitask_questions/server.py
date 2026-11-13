"""STDIO MCP server: durable attended questions with timeout → prompt → resume recovery."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import time
import uuid

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from . import owner
from .store import QuestionError, Store


# Clients may truncate instructions: the whole unanswered-question rule must fit
# in the first 512 characters (tests pin this).
INSTRUCTIONS = """Attended aitasks workflow questions. NEVER use for sandbox, command or \
security permissions. If a result's state is not `complete` (timeout, \
awaiting-chat-answer, unavailable, deferred) the question is UNANSWERED: do not \
pick a default, infer consent, skip it or do dependent work. Tell the user the pending \
question and its choices in plain prose, END YOUR TURN and wait; never poll. When their \
next message clearly answers it, call aitask_question_resume with session_id, \
question_id and their exact text.
A status request or unrelated steering is not an answer; use aitask_question_status \
to recover context. Resume shows the remaining questions as forms and never repeats an \
accepted one. A complete result carries a receipt. Before the action the answers \
permit, call aitask_question_consume with that receipt and a stable name for the \
action; proceed only on `claimed`, and on `duplicate` only after checking the action \
is not already done. `stale_approval` or `conflict` means ask again with a new \
opening. Approval gates and the reviewed commit are different: the gate scripts claim \
those receipts (aitask_gate_record.sh approval=..., aitask_gate.sh commit-approved); \
never run git commit for a reviewed change yourself. Never invent answers."""

SERVER_NAME = "aitask_questions"
MAX_TIMEOUT = 900


def form(question, page=None, multi_mode="native"):
    if question["kind"] == "multi":
        message = (f"{question['text']}\nPage {page['index'] + 1}/{page['page_count']}. "
                   f"Selected so far (exact IDs): {page['selected_so_far']}\n" +
                   "\n".join(f"{o['id']} — {o['label']}: {o['description']}" for o in page["options"]) +
                   "\nNext saves this page and advances. Finish saves this page and completes. "
                   "All selects the entire original candidate set. None clears the entire selection. "
                   "All/None require no individually selected items.")
        if multi_mode == "text":
            message += '\nEnter JSON with exact IDs, for example {"selected":["id"],"action":"next"}. ' + \
                       f"Allowed actions: {page['actions']}. An empty list must be explicit."
            properties = {"answer": {"type": "string", "title": "Selection JSON", "minLength": 1}}
        else:
            properties = {
                "selected": {"type": "array", "title": "Select items on this page",
                             "minItems": 0, "maxItems": len(page["options"]),
                             "items": {"anyOf": [{"const": o["id"], "title": o["label"]} for o in page["options"]]}},
                "action": {"type": "string", "title": "Page action",
                           "oneOf": [{"const": a, "title": a.capitalize()} for a in page["actions"]]}}
        return message, {"type": "object", "properties": properties, "required": list(properties)}
    prop = {"type": "string", "title": question["id"], "description": question["text"]}
    message = question["text"]
    if question["kind"] == "choice":
        prop["oneOf"] = [{"const": o["id"], "title": o["label"]} for o in question["options"]]
        message += "\n" + "\n".join(f"{o['label']}: {o['description']}" for o in question["options"])
    else:
        prop.update(minLength=1, maxLength=20000)
    return message, {"type": "object", "properties": {"answer": prop}, "required": ["answer"]}


def build_server(store, timeout, multi_mode="native"):
    server = MCPServer(SERVER_NAME, version="1.0.0", instructions=INSTRUCTIONS)
    process_instance = uuid.uuid4().hex
    writes = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                             open_world_hint=False)

    async def present(session_id, ctx):
        state = store.status(session_id)
        if state["state"] in {"complete", "cancelled", "invalidated"}:
            return state
        capabilities = ctx.client_capabilities
        info = {"protocol": ctx.request_context.protocol_version,
                "elicitation": capabilities.elicitation.model_dump(mode="json", by_alias=True)
                if capabilities and capabilities.elicitation is not None else None,
                "process_instance": process_instance, "pid": os.getpid(),
                "server_timeout_seconds": timeout}
        started = store.begin(session_id, timeout)
        if started.get("outcome") != "started":
            return started
        attempt_id = started["attempt"]["id"]
        elicitation = capabilities.elicitation if capabilities else None
        # An empty elicitation capability is legacy form support (2025-06-18).
        supports_form = elicitation is not None and (
            elicitation.form is not None or not elicitation.model_dump(exclude_none=True))
        if not supports_form:
            store.transport_event(session_id, attempt_id, info)
            return {**store.fail(session_id, attempt_id, "unavailable"), "transport": info}
        question = started["question"]
        page = started["pending_page"]
        info["question_kind"] = question["kind"]
        info["multi_mode"] = multi_mode if question["kind"] == "multi" else None
        if question["kind"] == "multi" and multi_mode == "native" and info["protocol"] < "2025-11-25":
            store.transport_event(session_id, attempt_id, info)
            return {**store.fail(session_id, attempt_id, "unsupported_shape"), "transport": info}
        message, schema = form(question, page, multi_mode)
        start = time.monotonic()
        store.transport_event(session_id, attempt_id, info)
        try:
            with anyio.fail_after(timeout):
                response = await ctx.request_context.session.elicit_form(
                    message, schema, related_request_id=ctx.request_id)
            if response.action == "cancel":
                result = store.cancel(session_id, defer=True, attempt_id=attempt_id)
            elif response.action == "decline":
                result = store.cancel(session_id, attempt_id=attempt_id)
            elif not isinstance(response.content, dict) or set(response.content) != set(schema["properties"]):
                result = store.fail(session_id, attempt_id, "invalid_form_response")
            else:
                value = response.content if question["kind"] == "multi" and multi_mode == "native" else response.content["answer"]
                result = store.submit(session_id, question["id"], value,
                                      "mcp_form", attempt_id, page["page_id"] if page else None)
        except TimeoutError:
            result = store.fail(session_id, attempt_id, "timeout")
        except anyio.get_cancelled_exc_class():
            # Outer tool cancellation can prevent a response; state still survives.
            store.fail(session_id, attempt_id, "transport_cancelled")
            raise
        except QuestionError:
            result = store.fail(session_id, attempt_id, "invalid_form_response")
        except Exception as exc:
            # Avoid emitting exception text, which may include a client's payload.
            result = store.fail(session_id, attempt_id, "transport_failure")
            info["error_type"] = type(exc).__name__
        info["elapsed_seconds"] = round(time.monotonic() - start, 3)
        store.transport_event(session_id, attempt_id, info)
        return {**result, "transport": info}

    @server.tool(annotations=writes)
    async def aitask_question_ask(workflow: str, checkpoint: str, opening: str,
                                  questions: list[dict], ctx: Context,
                                  artifacts: list[str] | None = None,
                                  deleted: list[str] | None = None,
                                  run: str = "", merge_source: str = "",
                                  merge_into: str = "") -> dict:
        """Open an attended question occurrence and show its first unanswered form.

        questions: [{id,text,kind:'choice'|'text'|'multi',options:[{id,label,description}]}].
        opening is a durable retry key for THIS occurrence, never question wording.
        Revisions/re-review require a new opening. artifacts are local relative
        paths to bind (including plans); deleted are relative paths the reviewed
        change removes (a rename: old path in deleted, new path in artifacts).
        run names this skill run so another session's same question is left
        alone; omit it when workflow is a task (t<id>). Multi supports page_size (default 3),
        min_selected (default 0), max_selected and allow_early_finish (default true).
        Multi is shown one page per form; see pending_page for IDs and actions.
        A merge_approved checkpoint binds no files: pass merge_source (the branch
        being merged) and merge_into (the branch it lands on) instead.
        One form per call. Follow next_action. Never ask for security permissions.
        """
        action = ({"source": merge_source, "destination": merge_into}
                  if merge_source or merge_into else None)
        state = store.open(workflow, checkpoint, opening, questions, artifacts or [], deleted or [],
                           run, action)
        return await present(state["session_id"], ctx)

    @server.tool(annotations=writes)
    def aitask_question_status(session_id: str) -> dict:
        """Recover the current question and accepted answers; may invalidate stale state.

        After timeout end the turn; do not poll this tool waiting for an answer.
        """
        return store.status(session_id)

    @server.tool(annotations=writes)
    def aitask_question_outstanding(workflow: str = "", run: str = "") -> dict:
        """List this project's unanswered or unconsumed occurrences (optionally one workflow/run).

        Use after a restart or lost context to recover session IDs. With more
        than one row, match the checkpoint or ask the user; never guess.
        """
        return store.outstanding(workflow or None, run or None)

    @server.tool(annotations=writes)
    async def aitask_question_resume(session_id: str, ctx: Context,
                                     question_id: str | None = None,
                                     prompt_answer: str = "",
                                     page_id: str | None = None) -> dict:
        """Resume same occurrence; optionally reconcile an explicit USER prompt answer.

        Supply both question_id and exact prompt_answer only for a message clearly
        answering that question. Status requests/unrelated steering are not answers.
        Free-text intent is model-associated, not authenticated. Never fabricate it.
        Without an answer, re-present the next pending form (also resumes defer).
        With an accepted answer, show the next question. Conflict/stale/ambiguous
        answers stay stopped. Prior accepted questions are never repeated.
        For multi, also provide the pending_page.page_id and exact user JSON
        with selected IDs and action. Never infer empty selection from no input.
        """
        # SDK 2.3.0 pre-parses JSON strings for union annotations. Keep this
        # plain str so exact user text (including duplicate JSON keys) reaches
        # our own validator unchanged. question_id signals answer presence.
        if question_id is None and prompt_answer != "":
            raise QuestionError("supply question_id and prompt_answer together")
        if question_id is not None:
            try:
                result = store.submit(session_id, question_id, prompt_answer, "codex_prompt_model_forwarded", page_id=page_id)
            except QuestionError as exc:
                return {**store.status(session_id), "outcome": "invalid_prompt_answer",
                        "reason": str(exc), "next_action": "end_turn_and_clarify_pending_question"}
            if result.get("outcome") not in {"accepted", "duplicate"}:
                return result
        return await present(session_id, ctx)

    @server.tool(annotations=writes)
    def aitask_question_cancel(session_id: str, defer: bool = False) -> dict:
        """Explicitly cancel or defer. Neither supplies answers or permits workflow work.

        Defer can be resumed explicitly. Cancel requires a new occurrence.
        """
        return store.cancel(session_id, defer)

    @server.tool(annotations=writes)
    def aitask_question_consume(session_id: str, receipt_id: str, consumer: str) -> dict:
        """Claim a complete receipt for ONE dependent action, immediately before it.

        consumer is a stable name for that action (e.g. 't42:archive'). Not for
        approval gates or the reviewed commit: the gate scripts claim those.
        claimed: proceed. duplicate: this action already claimed it; verify the
        action is not already done before repeating it. conflict/stale_approval:
        do not proceed; the bound files changed or the receipt is not current,
        so ask again under a new opening. Unanswered sessions never claim.
        """
        return store.consume(session_id, receipt_id, consumer)

    @server.tool(annotations=writes)
    def aitask_question_acknowledge(session_id: str, consumption_id: str) -> dict:
        """Record that the claimed action is done (history only; idempotent)."""
        return store.acknowledge(session_id, consumption_id)

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--multiselect-mode", choices=["native", "text"], default="native")
    args = parser.parse_args()
    if not 0.05 <= args.timeout <= MAX_TIMEOUT:
        parser.error(f"--timeout must be 0.05..{MAX_TIMEOUT} seconds")
    store = Store(args.state_dir, args.project, owner=owner.describe())
    build_server(store, args.timeout, args.multiselect_mode).run(transport="stdio")


if __name__ == "__main__":
    main()
