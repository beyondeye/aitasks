"""Real STDIO/SDK process tests of the aitask_questions MCP server.

A scripted client stands in for Codex: NOT evidence of attended Codex UI
behaviour (that is recorded in aidocs/codeagents/codex_questions_prototype.md).
Needs the mcp SDK; the module skips without it.
"""
from contextlib import asynccontextmanager, nullcontext
import json
from pathlib import Path
import subprocess
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import anyio
    from mcp import ClientSession, types
    from mcp.client.stdio import StdioServerParameters, stdio_client
except ImportError as exc:  # the SDK ships with Codex setup, not the core venv
    raise unittest.SkipTest(f"mcp SDK not installed ({exc.name}); run 'ait setup' with Codex configured")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))
from aitask_questions.store import Store
from test_aitask_questions import questions
from test_aitask_questions_selection import multi_question

ROOT = Path(__file__).resolve().parents[1]


def data(result):
    if result.is_error:
        raise AssertionError(result.content)
    return result.structured_content or json.loads(result.content[0].text)


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.state_dir = self.project / "state"
        (self.project / "plan.md").write_text("one")

    @asynccontextmanager
    async def client(self, callback=None, timeout="0.3", multi_mode="native", protocol=None):
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "aitask_questions.server", "--project", str(self.project),
                  "--state-dir", str(self.state_dir), "--timeout", timeout,
                  "--multiselect-mode", multi_mode],
            env={"PYTHONPATH": str(ROOT / ".aitask-scripts")})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, elicitation_callback=callback) as client:
                # Exercise the actual older wire handshake used by the live CLI.
                with patch("mcp.client.session.LATEST_HANDSHAKE_VERSION", protocol) if protocol else nullcontext():
                    initialized = await client.initialize()
                if protocol:
                    self.assertEqual(initialized.protocol_version, protocol)
                head = initialized.instructions[:512]
                for needle in ["NEVER use for sandbox", "UNANSWERED", "infer consent", "END YOUR TURN",
                               "never poll", "aitask_question_resume", "exact text"]:
                    self.assertIn(needle, head)
                yield client

    async def ask(self, client, opening="first"):
        return data(await client.call_tool("aitask_question_ask", {
            "workflow": "process-test", "checkpoint": "probe", "opening": opening,
            "questions": questions(), "artifacts": ["plan.md"]}))

    def test_timeout_prompt_recovery_fresh_process_second_timeout(self):
        async def scenario():
            seen = []
            async def callback(ctx, params):
                seen.append(params.message)
                if params.message.startswith("Choose"):
                    return types.ElicitResult(action="accept", content={"answer": "blue"})
                await anyio.sleep(10)
                return types.ElicitResult(action="accept", content={"answer": "too late"})
            async with self.client(callback) as client:
                result = await self.ask(client)
                sid = result["session_id"]
                self.assertEqual(result["outcome"], "accepted")
                result = data(await client.call_tool("aitask_question_resume", {"session_id": sid}))
                self.assertEqual(result["state"], "awaiting-chat-answer")
                self.assertEqual(result["transport_outcome"], "timeout")
                self.assertEqual(len(result["answers"]), 1)
                # The real server stamped the waiting question with itself; this
                # process is its ancestor, as a pane's shell is of a client's.
                self.assertEqual(waiting_here()["session_id"], sid)
            # Server closed: the question is still open, but nobody waits in a pane.
            for _ in range(50):
                if waiting_here() is None:
                    break
                await anyio.sleep(0.1)
            self.assertIsNone(waiting_here())
            async with self.client(callback) as client:
                result = data(await client.call_tool("aitask_question_resume", {
                    "session_id": sid, "question_id": "q2", "prompt_answer": "sample"}))
                self.assertEqual(result["state"], "awaiting-chat-answer")
                self.assertEqual(len(result["answers"]), 2)
                # Resumed by a new server: the wait is that server's now.
                self.assertEqual(waiting_here()["session_id"], sid)
            async with self.client(callback) as client:
                result = data(await client.call_tool("aitask_question_resume", {
                    "session_id": sid, "question_id": "q3", "prompt_answer": "finished"}))
                self.assertEqual(result["state"], "complete")
                again = data(await client.call_tool("aitask_question_resume", {"session_id": sid}))
                self.assertEqual(result["receipt"], again["receipt"])
            self.assertEqual(len(seen), 3)
            self.assertIsNone(waiting_here())  # answered

        def waiting_here():
            from aitask_questions.waiting import Watcher
            return Watcher(self.state_dir, ttl=0).for_pane(os.getpid())
        anyio.run(scenario)

    def test_recovery_returns_remaining_question_as_form(self):
        async def scenario():
            async def first(ctx, params):
                if params.message.startswith("Choose"):
                    return types.ElicitResult(action="accept", content={"answer": "blue"})
                await anyio.sleep(10)
            async with self.client(first) as client:
                result = await self.ask(client)
                sid = result["session_id"]
                await client.call_tool("aitask_question_resume", {"session_id": sid})
            shown = []
            async def last(ctx, params):
                shown.append(params.message)
                return types.ElicitResult(action="accept", content={"answer": "done"})
            async with self.client(last) as client:
                result = data(await client.call_tool("aitask_question_resume", {
                    "session_id": sid, "question_id": "q2", "prompt_answer": "sample"}))
                self.assertEqual(result["state"], "complete")
                self.assertEqual(result["answers"]["q3"]["source"], "mcp_form")
                self.assertEqual(shown, ["Describe the result"])
        anyio.run(scenario)

    def test_no_elicitation_capability_is_unavailable_not_answered(self):
        async def scenario():
            async with self.client() as client:
                result = await self.ask(client)
                self.assertEqual(result["transport_outcome"], "unavailable")
                self.assertEqual(result["state"], "awaiting-chat-answer")
                self.assertEqual(result["answers"], {})
        anyio.run(scenario)

    def test_old_protocol_rejects_native_and_explicit_text_adapter_recovers(self):
        async def scenario():
            seen = []
            async def callback(ctx, params):
                seen.append(params.requested_schema)
                return types.ElicitResult(action="accept", content={
                    "answer": '{"selected":["task-1","a,b"],"action":"finish"}'})
            async with self.client(callback, protocol="2025-06-18") as client:
                result = data(await client.call_tool("aitask_question_ask", {
                    "workflow": "legacy", "checkpoint": "multi", "opening": "first",
                    "questions": [multi_question()]}))
                sid = result["session_id"]
                self.assertEqual(result["transport_outcome"], "unsupported_shape")
                self.assertEqual(result["state"], "awaiting-chat-answer")
                self.assertEqual(result["answers"], {})
                self.assertIsNone(result["receipt"])
                self.assertEqual(seen, [])
            store = Store(self.state_dir, self.project)
            with store.connect() as conn:
                body = json.loads(conn.execute("SELECT body FROM sessions WHERE id=?", (sid,)).fetchone()[0])
            events = [e for e in body["events"] if e["event"] == "transport"]
            self.assertEqual(events[-1]["protocol"], "2025-06-18")
            self.assertEqual(events[-1]["multi_mode"], "native")
            async with self.client(callback, multi_mode="text", protocol="2025-06-18") as client:
                result = data(await client.call_tool("aitask_question_resume", {"session_id": sid}))
                self.assertEqual(result["state"], "complete")
                self.assertEqual(result["answers"]["deps"]["value"], ["task-1", "a,b"])
                self.assertEqual(result["transport"]["multi_mode"], "text")
                self.assertEqual(len(seen), 1)
                self.assertEqual(set(seen[0]["properties"]), {"answer"})
        anyio.run(scenario)

    def test_outer_cancellation_and_reconnection_preserve_question(self):
        async def scenario():
            started = anyio.Event()
            async def callback(ctx, params):
                started.set()
                await anyio.sleep(10)
            store = Store(self.state_dir, self.project)
            sid = store.open("process-test", "probe", "first", questions(), ["plan.md"])["session_id"]
            async with self.client(callback, timeout="2") as client:
                # Cancel the OUTER tools/call while elicitation is in progress.
                with anyio.move_on_after(0.2):
                    await client.call_tool("aitask_question_resume", {"session_id": sid})
                self.assertTrue(started.is_set())
            await anyio.sleep(2.1)  # also covers a process dying before cleanup
            async with self.client() as client:
                result = data(await client.call_tool("aitask_question_status", {"session_id": sid}))
                self.assertEqual(result["state"], "awaiting-chat-answer")
                self.assertEqual(result["answers"], {})
                self.assertIsNone(result["receipt"])
        anyio.run(scenario)

    def test_bad_prompt_response_returns_pending_context(self):
        async def scenario():
            async with self.client() as client:
                state = await self.ask(client)
                result = data(await client.call_tool("aitask_question_resume", {
                    "session_id": state["session_id"], "question_id": "q1",
                    "prompt_answer": "what is the status?"}))
                self.assertEqual(result["outcome"], "invalid_prompt_answer")
                self.assertEqual(result["pending"][0]["id"], "q1")
                self.assertEqual(result["answers"], {})
                self.assertIsNone(result["receipt"])
        anyio.run(scenario)

    def test_prompt_json_text_is_preserved_before_validation(self):
        async def scenario():
            async with self.client() as client:
                for index, raw in enumerate(['{"name":"sample"}', '[]', 'null', 'true']):
                    result = data(await client.call_tool("aitask_question_ask", {
                        "workflow": "raw-text", "checkpoint": "json", "opening": str(index),
                        "questions": [{"id": "text", "text": "Enter text", "kind": "text"}]}))
                    result = data(await client.call_tool("aitask_question_resume", {
                        "session_id": result["session_id"], "question_id": "text", "prompt_answer": raw}))
                    self.assertEqual(result["answers"]["text"]["value"], raw)
                result = data(await client.call_tool("aitask_question_ask", {
                    "workflow": "raw-text", "checkpoint": "multi", "opening": "first",
                    "questions": [multi_question()]}))
                result = data(await client.call_tool("aitask_question_resume", {
                    "session_id": result["session_id"], "question_id": "deps",
                    "page_id": result["pending_page"]["page_id"],
                    "prompt_answer": '{"selected":[],"selected":["task-1"],"action":"finish"}'}))
                self.assertEqual(result["outcome"], "invalid_prompt_answer")
                self.assertEqual(result["answers"], {})
        anyio.run(scenario)

    def test_revision_during_real_elicitation_rejects_answer(self):
        async def scenario():
            async def callback(ctx, params):
                (self.project / "plan.md").write_text("two")
                return types.ElicitResult(action="accept", content={"answer": "blue"})
            async with self.client(callback) as client:
                result = await self.ask(client)
                self.assertEqual(result["state"], "invalidated")
                self.assertEqual(result["answers"], {})
                self.assertIsNone(result["receipt"])
        anyio.run(scenario)

    def test_consume_through_mcp_claims_once_and_refuses_after_revision(self):
        async def scenario():
            async def callback(ctx, params):
                return types.ElicitResult(action="accept", content={
                    "answer": "blue" if "color" in params.message.lower() else "text"})
            async with self.client(callback) as client:
                tools = {t.name for t in (await client.list_tools()).tools}
                self.assertEqual(tools, {f"aitask_question_{n}" for n in
                                         ["ask", "status", "resume", "cancel", "consume", "acknowledge", "outstanding"]})
                state = await self.ask(client)
                early = data(await client.call_tool("aitask_question_consume", {
                    "session_id": state["session_id"], "receipt_id": "none", "consumer": "t1:act"}))
                self.assertEqual(early["outcome"], "stale_approval")
                while state["state"] != "complete":
                    state = data(await client.call_tool("aitask_question_resume", {"session_id": state["session_id"]}))
                args = {"session_id": state["session_id"], "receipt_id": state["receipt"]["id"]}
                claim = data(await client.call_tool("aitask_question_consume", {**args, "consumer": "t1:act"}))
                self.assertEqual(claim["outcome"], "claimed")
            async with self.client(callback) as client:  # fresh process
                again = data(await client.call_tool("aitask_question_consume", {**args, "consumer": "t1:act"}))
                other = data(await client.call_tool("aitask_question_consume", {**args, "consumer": "t1:other"}))
                self.assertEqual((again["outcome"], other["outcome"]), ("duplicate", "conflict"))
                ack = data(await client.call_tool("aitask_question_acknowledge", {
                    "session_id": args["session_id"], "consumption_id": claim["consumption"]["id"]}))
                self.assertEqual(ack["outcome"], "acknowledged")
                second = await self.ask(client, opening="second")
                while second["state"] != "complete":
                    second = data(await client.call_tool("aitask_question_resume", {"session_id": second["session_id"]}))
                (self.project / "plan.md").write_text("two")
                stale = data(await client.call_tool("aitask_question_consume", {
                    "session_id": second["session_id"], "receipt_id": second["receipt"]["id"], "consumer": "t1:act2"}))
                self.assertEqual(stale["outcome"], "stale_approval")
                self.assertIsNone(stale["consumption"])
        anyio.run(scenario)

    def test_malformed_form_content_never_answers(self):
        async def scenario():
            for n, content in enumerate([{"answer": 7}, {"answer": ["blue"]}, {"answer": "blue", "extra": "x"},
                                         {"other": "blue"}, {"answer": ""}, {"answer": "Blue"}]):
                async def callback(ctx, params):
                    return types.ElicitResult(action="accept", content=content)
                async with self.client(callback) as client:
                    result = await self.ask(client, opening=f"bad-{n}")
                    self.assertEqual(result["state"], "awaiting-chat-answer", content)
                    self.assertEqual(result["answers"], {})
                    self.assertIsNone(result["receipt"])
        anyio.run(scenario)

    def test_prepare_preserves_venv_executable_and_security_policy(self):
        state_dir = self.project / 'state with spaces'
        result = subprocess.run([sys.executable, str(ROOT / "tests/manual/codex_questions_probe.py"),
            "--python", sys.executable, "--state-dir", str(state_dir), "--prepare"],
            capture_output=True, text=True, check=True)
        record = json.loads((state_dir / "launch.json").read_text())
        expected = 'mcp_servers.aitask_questions.command=' + json.dumps(sys.executable)
        self.assertIn(expected, record["argv"])
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", record["argv"])
        self.assertFalse(any("approval_policy" in arg for arg in record["argv"]))
        self.assertIn("Question session:", result.stdout)

    def test_decline_cancel_and_empty_form_never_answer(self):
        async def scenario():
            for action, expected in [("decline", "cancelled"), ("cancel", "deferred"),
                                     ("accept", "awaiting-chat-answer")]:
                async def callback(ctx, params):
                    return types.ElicitResult(action=action, content={} if action == "accept" else None)
                async with self.client(callback) as client:
                    result = await self.ask(client, opening=action)
                    self.assertEqual(result["state"], expected)
                    self.assertEqual(result["answers"], {})
                    self.assertIsNone(result["receipt"])
        anyio.run(scenario)

    def test_paginated_native_and_text_recovery_across_processes(self):
        async def scenario(mode):
            calls = []
            async def first(ctx, params):
                calls.append(params.message)
                schema = params.requested_schema
                if len(calls) == 1:
                    payload = {"selected": ["task-1", 'a"b'], "action": "next"}
                    if mode == "native":
                        self.assertEqual(schema["properties"]["selected"]["type"], "array")
                    else:
                        self.assertEqual(set(schema["properties"]), {"answer"})
                    return types.ElicitResult(action="accept", content=payload if mode == "native"
                                             else {"answer": json.dumps(payload)})
                await anyio.sleep(10)
            async with self.client(first, multi_mode=mode) as client:
                result = data(await client.call_tool("aitask_question_ask", {
                    "workflow": "selection", "checkpoint": "deps", "opening": mode,
                    "questions": [multi_question()], "artifacts": ["plan.md"]}))
                sid = result["session_id"]
                self.assertEqual(result["pending_page"]["selected_so_far"], ["task-1", 'a"b'])
                result = data(await client.call_tool("aitask_question_resume", {"session_id": sid}))
                self.assertEqual(result["transport_outcome"], "timeout")
                page_id = result["pending_page"]["page_id"]
                process = result["transport"]["process_instance"]
            async with self.client(first, multi_mode=mode) as client:
                result = data(await client.call_tool("aitask_question_resume", {
                    "session_id": sid, "question_id": "deps", "page_id": page_id,
                    "prompt_answer": json.dumps({"selected": ["t6", "tests"], "action": "next"})}))
                self.assertNotEqual(process, result["transport"]["process_instance"])
                self.assertEqual(result["transport_outcome"], "timeout")
                self.assertEqual(result["answers"], {})
                self.assertIsNone(result["receipt"])
                page_id = result["pending_page"]["page_id"]
            async with self.client(first, multi_mode=mode) as client:
                result = data(await client.call_tool("aitask_question_resume", {
                    "session_id": sid, "question_id": "deps", "page_id": page_id,
                    "prompt_answer": json.dumps({"selected": ["7"], "action": "finish"})}))
                self.assertEqual(result["state"], "complete")
                self.assertEqual(result["answers"]["deps"]["value"],
                                 ["task-1", 'a"b', "tests", "t6", "7"])
                replay = data(await client.call_tool("aitask_question_resume", {"session_id": sid}))
                self.assertEqual(result["receipt"], replay["receipt"])
            self.assertEqual(len(calls), 3)
        for mode in ["native", "text"]:
            with self.subTest(mode=mode):
                anyio.run(scenario, mode)


if __name__ == "__main__":
    unittest.main()
