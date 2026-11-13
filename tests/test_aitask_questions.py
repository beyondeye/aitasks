"""Durability and freshness tests for the isolated t2281 compatibility spike."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))
from aitask_questions.store import QuestionError, Store, validate_questions


def questions():
    return [
        {"id": "q1", "text": "Choose a color", "kind": "choice", "options": [
            {"id": "blue", "label": "Blue", "description": "Blue sample"},
            {"id": "green", "label": "Green", "description": "Green sample"}]},
        {"id": "q2", "text": "Name the sample", "kind": "text"},
        {"id": "q3", "text": "Describe the result", "kind": "text"},
    ]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "plan.md").write_text("revision one")
        self.store = Store(self.root / "state", self.root)
        self.state = self.store.open("test-run", "test-checkpoint", "opening-1", questions(), ["plan.md"])
        self.sid = self.state["session_id"]

    def submit(self, qid, value, store=None):
        return (store or self.store).submit(self.sid, qid, value, "codex_prompt_model_forwarded")

    def complete(self):
        self.submit("q1", "blue")
        self.submit("q2", "sample")
        return self.submit("q3", "done")

    def test_timeout_restart_prompt_then_remaining_forms(self):
        first = self.store.begin(self.sid, 20)
        self.store.submit(self.sid, "q1", "blue", "mcp_form", first["attempt"]["id"])
        second = self.store.begin(self.sid, 20)
        pending = self.store.fail(self.sid, second["attempt"]["id"], "timeout")
        self.assertEqual(pending["state"], "awaiting-chat-answer")
        self.assertIsNone(pending["receipt"])
        restarted = Store(self.root / "state", self.root)
        self.submit("q2", "sample", restarted)
        third = restarted.begin(self.sid, 20)
        self.assertEqual(third["question"]["id"], "q3")
        restarted.fail(self.sid, third["attempt"]["id"], "timeout")
        last = self.submit("q3", "done", Store(self.root / "state", self.root))
        self.assertEqual(last["state"], "complete")
        self.assertEqual(len(last["answers"]), 3)
        self.assertEqual(last["answers"]["q1"]["source"], "mcp_form")
        self.assertEqual(last["answers"]["q2"]["source"], "codex_prompt_model_forwarded")
        self.assertEqual(restarted.status(self.sid)["receipt"], last["receipt"])

    def test_orphaned_attempt_expires_without_polling_or_answer(self):
        attempt = self.store.begin(self.sid, 20)
        with patch("aitask_questions.store.time.time", return_value=attempt["attempt"]["deadline"] + 1):
            state = Store(self.root / "state", self.root).status(self.sid)
        self.assertEqual(state["state"], "awaiting-chat-answer")
        self.assertEqual(state["answers"], {})

    def test_retry_does_not_replace_live_form_or_repeat_answers(self):
        first = self.store.begin(self.sid, 20)
        retry = self.store.open("test-run", "test-checkpoint", "opening-1", questions(), ["plan.md"])
        self.assertEqual(retry["session_id"], self.sid)
        self.assertEqual(retry["attempt"], first["attempt"])
        self.assertEqual(self.store.begin(self.sid, 20)["outcome"], "busy")
        self.submit("q1", "blue")
        self.assertEqual(self.store.begin(self.sid, 20)["question"]["id"], "q2")

    def test_revision_before_answer_invalidates_even_after_revert(self):
        old = self.store.begin(self.sid, 20)
        (self.root / "plan.md").write_text("revision two")
        result = self.store.submit(self.sid, "q1", "blue", "mcp_form", old["attempt"]["id"])
        self.assertEqual(result["state"], "invalidated")
        (self.root / "plan.md").write_text("revision one")
        self.assertEqual(self.submit("q1", "blue")["state"], "invalidated")
        self.assertEqual(self.store.open("test-run", "test-checkpoint", "opening-1", questions(), ["plan.md"])["state"], "invalidated")

    def test_revision_after_receipt_and_unreadable_artifact(self):
        receipt = self.complete()["receipt"]
        self.assertIsNotNone(receipt)
        (self.root / "plan.md").unlink()
        result = self.store.status(self.sid)
        self.assertEqual(result["state"], "invalidated")
        self.assertIsNone(result["receipt"])
        self.assertEqual(len(result["answers"]), 3)  # retained only as history

    def test_edited_plan_after_receipt_does_not_reissue_receipt(self):
        receipt = self.complete()["receipt"]
        (self.root / "plan.md").write_text("different approved action")
        retry = self.store.open("test-run", "test-checkpoint", "opening-1", questions(), ["plan.md"])
        self.assertEqual(retry["state"], "invalidated")
        self.assertIsNone(retry["receipt"])
        self.assertNotEqual(retry["receipt"], receipt)

    def test_new_occurrence_same_words_same_bytes_invalidates_old_receipt(self):
        old_receipt = self.complete()["receipt"]
        new = self.store.open("test-run", "test-checkpoint", "opening-2", questions(), ["plan.md"])
        self.assertNotEqual(new["occurrence_id"], old_receipt["occurrence_id"])
        self.assertEqual(new["answers"], {})
        self.assertEqual(self.store.status(self.sid)["state"], "invalidated")
        self.assertEqual(self.submit("q1", "blue")["outcome"], "not_accepted")

    def test_reconnect_same_occurrence_keeps_receipt(self):
        receipt = self.complete()["receipt"]
        again = Store(self.root / "state", self.root).open("test-run", "test-checkpoint", "opening-1", questions(), ["plan.md"])
        self.assertEqual(again["receipt"], receipt)

    def test_late_form_cannot_overwrite_prompt_or_cancel_next_question(self):
        first = self.store.begin(self.sid, 20)
        self.submit("q1", "blue")
        second = self.store.begin(self.sid, 20)
        result = self.store.submit(self.sid, "q1", "green", "mcp_form", first["attempt"]["id"])
        self.assertEqual(result["outcome"], "conflict")
        late = self.store.cancel(self.sid, attempt_id=first["attempt"]["id"])
        self.assertEqual(late["outcome"], "stale_attempt")
        self.assertEqual(late["attempt"], second["attempt"])
        self.assertEqual(late["answers"]["q1"]["value"], "blue")

    def test_expired_form_does_not_answer_new_attempt(self):
        first = self.store.begin(self.sid, 20)
        self.store.fail(self.sid, first["attempt"]["id"], "timeout")
        second = self.store.begin(self.sid, 20)
        result = self.store.submit(self.sid, "q1", "blue", "mcp_form", first["attempt"]["id"])
        self.assertEqual(result["outcome"], "stale_attempt")
        self.assertEqual(result["attempt"], second["attempt"])

    def test_concurrent_answers_have_one_winner(self):
        def answer(value):
            return self.submit("q1", value, Store(self.root / "state", self.root))
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(answer, ["blue", "green"]))
        self.assertEqual(sorted(r["outcome"] for r in results), ["accepted", "conflict"])
        self.assertEqual(len(self.store.status(self.sid)["answers"]), 1)

    def test_bad_or_unrelated_choices_and_out_of_order_answers_stay_pending(self):
        for value in ["status?", "blue or green", "", None, [], "Please choose Blue"]:
            with self.assertRaises(QuestionError):
                self.submit("q1", value)
        with self.assertRaises(QuestionError):
            self.submit("q3", "done")
        self.assertEqual(self.store.status(self.sid)["answers"], {})

    def test_duplicate_answer_preserves_original_source(self):
        self.submit("q1", "Blue")
        duplicate = self.store.submit(self.sid, "q1", "blue", "mcp_form", "old-attempt")
        self.assertEqual(duplicate["outcome"], "duplicate")
        self.assertEqual(duplicate["answers"]["q1"]["source"], "codex_prompt_model_forwarded")

    def test_defer_and_cancel_never_produce_receipt(self):
        deferred = self.store.cancel(self.sid, defer=True)
        self.assertEqual(deferred["state"], "deferred")
        self.assertIsNone(deferred["receipt"])
        self.assertEqual(deferred["answers"], {})
        self.assertEqual(deferred["next_action"], "end_turn_and_request_explicit_prompt_answer")
        self.assertEqual(self.store.begin(self.sid, 20)["outcome"], "started")
        cancelled = self.store.cancel(self.sid)
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertIsNone(cancelled["receipt"])
        self.assertEqual(self.submit("q1", "blue")["outcome"], "not_accepted")

    def test_deferred_question_accepts_explicit_prompt_answer_only(self):
        # Live run 2026-11-12: Esc on a form deferred the occurrence and the
        # user's next prompt answer was refused, leaving no way to answer.
        attempt = self.store.begin(self.sid, 20)["attempt"]["id"]
        self.assertEqual(self.store.cancel(self.sid, defer=True, attempt_id=attempt)["state"], "deferred")
        late = self.store.submit(self.sid, "q1", "blue", "mcp_form", attempt)
        self.assertEqual(late["outcome"], "stale_attempt")
        self.assertEqual(late["answers"], {})
        self.assertEqual(late["state"], "deferred")
        accepted = self.submit("q1", "blue")
        self.assertEqual(accepted["outcome"], "accepted")
        self.assertEqual(accepted["answers"]["q1"]["source"], "codex_prompt_model_forwarded")
        self.assertEqual(accepted["state"], "pending")

    def test_outstanding_reports_a_recently_voided_question(self):
        # Live run 2026-11-12: editing a bound file voided an open question and
        # outstanding() answered "none", as if nothing had ever been asked.
        (self.root / "plan.md").write_text("v1")
        sid = self.store.open("test-run", "bound", "o1", questions(), ["plan.md"])["session_id"]
        self.assertEqual([r["session_id"] for r in self.store.outstanding()["outstanding"]].count(sid), 1)
        (self.root / "plan.md").write_text("v2")
        result = self.store.outstanding("test-run")
        self.assertNotIn(sid, [r["session_id"] for r in result["outstanding"]])
        retired = [r for r in result["retired"] if r["session_id"] == sid]
        self.assertEqual(len(retired), 1)
        self.assertEqual(retired[0]["reason"], "artifact_revision_changed_or_unverifiable")
        self.assertEqual(retired[0]["next_action"], "ask_again_with_new_opening")
        self.assertNotIn("answers", retired[0])
        later = time.time() + 90000
        with patch("aitask_questions.store.time.time", return_value=later):
            self.assertEqual(self.store.outstanding("test-run")["retired"], [])

    def test_isolation_and_opening_key_mismatch(self):
        other = self.store.open("other-run", "test-checkpoint", "opening-1", questions(), [])
        self.assertNotEqual(other["session_id"], self.sid)
        self.assertEqual(self.store.status(self.sid)["state"], "pending")
        with self.assertRaises(QuestionError):
            self.store.open("test-run", "test-checkpoint", "opening-1", questions()[:1], ["plan.md"])
        other_root = self.root / "other-project"
        other_root.mkdir()
        with self.assertRaises(QuestionError):
            Store(self.root / "state", other_root).status(self.sid)

    def test_schema_unsupported_multiselect_and_escaping_artifacts(self):
        bad = questions()
        bad[0]["kind"] = "multi_select"
        with self.assertRaisesRegex(QuestionError, "unsupported_shape"):
            validate_questions(bad)
        for path in ["../plan.md", "/etc/passwd", "missing.md"]:
            with self.assertRaises(QuestionError):
                self.store.open("run", "check", "open", questions(), [path])
        with self.assertRaises(QuestionError):
            validate_questions([questions()[0], questions()[0]])

    def test_consume_claims_once_and_reconciles_same_consumer(self):
        receipt = self.complete()["receipt"]["id"]
        first = self.store.consume(self.sid, receipt, "record-plan-approved")
        self.assertEqual(first["outcome"], "claimed")
        self.assertFalse(first["consumption"]["acknowledged"])
        # Crash between claim and effect: same consumer sees its own claim.
        again = Store(self.root / "state", self.root).consume(self.sid, receipt, "record-plan-approved")
        self.assertEqual(again["outcome"], "duplicate")
        self.assertEqual(again["consumption"]["id"], first["consumption"]["id"])
        self.assertEqual(self.store.consume(self.sid, receipt, "start-implementation")["outcome"], "conflict")
        cid = first["consumption"]["id"]
        self.assertEqual(self.store.acknowledge(self.sid, cid)["outcome"], "acknowledged")
        self.assertEqual(self.store.acknowledge(self.sid, cid)["outcome"], "duplicate")
        self.assertEqual(self.store.acknowledge(self.sid, "other")["outcome"], "unknown_consumption")
        final = self.store.status(self.sid)
        self.assertTrue(final["consumption"]["acknowledged"])
        self.assertEqual(final["state"], "complete")

    def test_consume_refuses_unanswered_foreign_and_stale_receipts(self):
        self.submit("q1", "blue")
        self.assertEqual(self.store.consume(self.sid, "anything", "c")["outcome"], "stale_approval")
        receipt = self.complete()["receipt"]["id"]
        self.assertEqual(self.store.consume(self.sid, "not-this-receipt", "c")["outcome"], "stale_approval")
        self.assertIsNone(self.store.status(self.sid)["consumption"])
        # Revision after the receipt, before consumption: nothing is claimed,
        # and reverting the bytes does not resurrect the approval.
        (self.root / "plan.md").write_text("revision two")
        stale = self.store.consume(self.sid, receipt, "c")
        self.assertEqual((stale["outcome"], stale["state"]), ("stale_approval", "invalidated"))
        (self.root / "plan.md").write_text("revision one")
        self.assertEqual(self.store.consume(self.sid, receipt, "c")["outcome"], "stale_approval")
        self.assertIsNone(self.store.status(self.sid)["consumption"])

    def test_writer_after_claim_cannot_change_what_the_consumer_reads(self):
        receipt = self.complete()["receipt"]["id"]
        claim = self.store.consume(self.sid, receipt, "c")
        (self.root / "plan.md").write_text("revision two")
        self.assertEqual(self.store.snapshot(self.sid, "plan.md"), b"revision one")
        after = self.store.status(self.sid)
        # Later dependent work needs a new occurrence; the claim stays history.
        self.assertEqual(after["state"], "invalidated")
        self.assertEqual(after["consumption"]["id"], claim["consumption"]["id"])
        self.assertEqual(self.store.consume(self.sid, receipt, "c")["outcome"], "stale_approval")
        self.assertEqual(self.store.acknowledge(self.sid, claim["consumption"]["id"])["outcome"], "acknowledged")
        with self.assertRaises(QuestionError):
            self.store.snapshot(self.sid, "other.md")

    def test_concurrent_consumers_have_one_claim(self):
        receipt = self.complete()["receipt"]["id"]
        def claim(n):
            return Store(self.root / "state", self.root).consume(self.sid, receipt, f"consumer-{n}")["outcome"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(claim, range(8)))
        self.assertEqual(outcomes.count("claimed"), 1)
        self.assertEqual(outcomes.count("conflict"), 7)

    def test_missing_artifact_blocks_consumption(self):
        receipt = self.complete()["receipt"]["id"]
        (self.root / "plan.md").unlink()
        self.assertEqual(self.store.consume(self.sid, receipt, "c")["outcome"], "stale_approval")


    def raw(self):
        conn = sqlite3.connect(self.root / "state" / "questions.sqlite3", timeout=0.2)
        self.addCleanup(conn.close)
        return conn

    def test_writer_killed_before_commit_leaves_previous_state(self):
        self.submit("q1", "blue")
        conn = self.raw()
        conn.execute("BEGIN IMMEDIATE")
        forged = '{"schema":1,"answers":{"q1":1,"q2":1,"q3":1},"state":"complete"}'
        conn.execute("UPDATE sessions SET body=? WHERE id=?", (forged, self.sid))
        conn.close()  # process death: the open transaction is rolled back
        state = Store(self.root / "state", self.root).status(self.sid)
        self.assertEqual(list(state["answers"]), ["q1"])
        self.assertIsNone(state["receipt"])
        self.assertEqual(self.complete()["state"], "complete")

    def test_corrupt_state_is_an_error_never_an_answer(self):
        for damaged in ["{not json", "[]", '{"schema":2,"answers":{}}', '{"schema":1,"answers":[]}']:
            with self.subTest(damaged=damaged):
                conn = self.raw()
                conn.execute("UPDATE sessions SET body=? WHERE id=?", (damaged, self.sid))
                conn.commit()
                for call in [lambda: self.store.status(self.sid), lambda: self.submit("q1", "blue"),
                             lambda: self.store.begin(self.sid, 1), lambda: self.store.consume(self.sid, "r", "c"),
                             lambda: self.store.snapshot(self.sid, "plan.md"),
                             lambda: self.store.open("test-run", "test-checkpoint", "opening-1", questions(), ["plan.md"])]:
                    with self.assertRaisesRegex(QuestionError, "corrupt"):
                        call()
        # A new opening still works beside the unreadable occurrence.
        fresh = self.store.open("test-run", "test-checkpoint", "opening-2", questions(), ["plan.md"])
        self.assertEqual(fresh["state"], "pending")

    def test_locked_storage_reports_busy_and_accepts_nothing(self):
        conn = self.raw()
        conn.execute("BEGIN IMMEDIATE")
        with patch.object(Store, "connect", self.fast_connect()):
            with self.assertRaisesRegex(QuestionError, "busy"):
                self.submit("q1", "blue")
        conn.rollback()
        self.assertEqual(self.store.status(self.sid)["answers"], {})

    def fast_connect(self):
        from contextlib import contextmanager
        @contextmanager
        def connect(store):
            conn = sqlite3.connect(store.db, timeout=0.05)
            try:
                with conn:
                    yield conn
            except sqlite3.Error as exc:
                raise QuestionError("question state is busy or unreadable") from exc
            finally:
                conn.close()
        return connect

    def test_outstanding_recovers_sessions_per_workflow_and_project(self):
        other = self.store.open("other-run", "test-checkpoint", "o", questions(), [])
        self.assertEqual(self.store.outstanding()["count"], 2)
        self.assertEqual(self.store.outstanding()["next_action"], "match_checkpoint_then_status_or_resume")
        mine = Store(self.root / "state", self.root).outstanding("test-run")
        self.assertEqual([r["session_id"] for r in mine["outstanding"]], [self.sid])
        self.assertEqual(mine["outstanding"][0]["workflow"], "test-run")
        self.store.cancel(other["session_id"])
        receipt = self.complete()["receipt"]["id"]
        self.assertEqual(self.store.outstanding()["outstanding"][0]["state"], "complete")
        self.store.consume(self.sid, receipt, "c")
        self.assertEqual(self.store.outstanding(), {"outstanding": [], "count": 0, "retired": [],
                                                    "next_action": "none_outstanding"})
        reopened = self.store.open("test-run", "test-checkpoint", "opening-2", questions(), ["plan.md"])
        (self.root / "plan.md").write_text("changed")
        self.assertEqual(self.store.outstanding()["count"], 0)
        self.assertEqual(self.store.status(reopened["session_id"])["state"], "invalidated")
        with tempfile.TemporaryDirectory() as elsewhere:
            self.assertEqual(Store(self.root / "state", Path(elsewhere)).outstanding()["count"], 0)

    def test_runs_of_one_skill_do_not_retire_each_other(self):
        # Two independent sessions at the same skill checkpoint.
        a = self.store.open("aitask-explore", "label_filter", "o1", questions(), [], run="run-a")
        b = self.store.open("aitask-explore", "label_filter", "o1", questions(), [], run="run-b")
        self.assertNotEqual(a["session_id"], b["session_id"])
        self.assertEqual(self.store.status(a["session_id"])["state"], "pending")
        # A reconnect of run-a (fresh process, same opening) is the same occurrence.
        again = Store(self.root / "state", self.root).open(
            "aitask-explore", "label_filter", "o1", questions(), [], run="run-a")
        self.assertEqual(again["session_id"], a["session_id"])
        # Asking again supersedes only within the run.
        newer = self.store.open("aitask-explore", "label_filter", "o2", questions(), [], run="run-a")
        self.assertEqual(self.store.status(a["session_id"])["state"], "invalidated")
        self.assertEqual(self.store.status(b["session_id"])["state"], "pending")
        mine = self.store.outstanding("aitask-explore", "run-a")["outstanding"]
        self.assertEqual([(r["session_id"], r["run"]) for r in mine], [(newer["session_id"], "run-a")])
        self.assertEqual(self.store.outstanding("aitask-explore")["count"], 2)
        # A task is one run by construction.
        with self.assertRaises(QuestionError):
            self.store.open("t12", "label_filter", "o1", questions(), [], run="run-a")
        with self.assertRaises(QuestionError):
            self.store.open("t12_3", "label_filter", "o1", questions(), [], run="run-a")

    def test_task_requirements_projection(self):
        from aitask_questions.projection import task_requirements
        base = "---\npriority: high\n---\n\nDo the thing.\n\n> a quoted remark stays\n"
        ledger = ("\n## Gate Runs\n<!-- Appended by the gate framework. Do not edit by hand; "
                  "use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->\n\n"
                  "> **\u2705 gate:plan_approved** run=2026-11-11T11:02:28Z status=pass attempt=1 type=human\n"
                  ">\n> Note: approval:abc:def\n\n"
                  "## Inbox\n<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->\n\n"
                  "> **\U0001f4dd note:n1** from=t1\n> | body\n")
        want = task_requirements(base.encode())
        self.assertEqual(want, b"---\nDo the thing.\n\n> a quoted remark stays")
        self.assertEqual(task_requirements((base + ledger).encode()), want)
        self.assertEqual(task_requirements(base.replace("high", "low").encode()), want)
        self.assertNotEqual(task_requirements((base + ledger + "\nAlso this.\n").encode()), want)
        self.assertNotEqual(task_requirements(base.replace("thing", "other thing").encode()), want)
        with self.assertRaises(QuestionError):
            task_requirements(b"---\npriority: high\nno close\n")

    def test_question_waiting_at_the_prompt_is_tied_to_its_server_and_clears(self):
        import os
        from aitask_questions import owner, waiting
        me = owner.describe()
        self.assertEqual(me["pid"], os.getpid())
        self.assertIn(os.getppid(), me["ancestors"])
        self.assertTrue(owner.alive(me))
        served = Store(self.root / "state", self.root, owner=me)
        watcher = lambda: waiting.Watcher(self.root / "state", ttl=0)
        pane = os.getppid()  # an ancestor of the serving process, as a pane's shell is
        # An open form is on screen: not this signal.
        attempt = served.begin(self.sid, 30)["attempt"]["id"]
        self.assertIsNone(watcher().for_pane(pane))
        # The form timed out: the question waits at the prompt, in that pane only.
        served.fail(self.sid, attempt, "timeout")
        found = watcher().for_pane(pane)
        self.assertEqual(found["session_id"], self.sid)
        self.assertEqual(found["checkpoint"], "test-checkpoint")
        self.assertIsNone(watcher().for_pane(2 ** 22 + 12345))
        self.assertIsNone(watcher().for_pane(0))
        # A reader without an owner (gate scripts, another tool) leaves the stamp alone,
        # and a listing by another server does not move it.
        self.store.status(self.sid)
        other = {"pid": 1, "start": "x", "ancestors": [7]}
        Store(self.root / "state", self.root, owner=other).outstanding()
        self.assertEqual(watcher().for_pane(pane)["session_id"], self.sid)
        # Deferred is still waiting; an answer that leaves questions open is a
        # live exchange again, not a wait.
        served.cancel(self.sid, defer=True)
        self.assertIsNotNone(watcher().for_pane(pane))
        self.submit("q1", "blue", served)
        self.assertIsNone(watcher().for_pane(pane))
        # Timed out again, then cancelled: cleared.
        attempt = served.begin(self.sid, 30)["attempt"]["id"]
        served.fail(self.sid, attempt, "timeout")
        self.assertIsNotNone(watcher().for_pane(pane))
        served.cancel(self.sid)
        self.assertIsNone(watcher().for_pane(pane))

    def _client(self, cwd=None, serving="", name="codex"):
        """A running stand-in for a codex terminal client: {"pid", "start"}.

        argv is [python, <dir>/codex], the shape of the node launcher.
        serving selects what it runs below itself:
          "main"    a question server, started from the main thread;
          "thread"  the same, started from a worker thread (Linux then lists
                    the child under that thread only);
          "daemon"  a shared app-server that in turn runs the question
                    server - the client that happened to start the daemon;
          "host"    a session host only (`codex-code-mode-host`), no question
                    server: an in-process client started before the server
                    was configured, or in a project without it.
        """
        import subprocess
        import sys
        from aitask_questions import owner
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / owner.SERVER_SCRIPT).write_text("import time\ntime.sleep(120)\n")
        (bin_dir / "idle.py").write_text("import time\ntime.sleep(120)\n")
        # The daemon stand-in is this interpreter under an argv[0] inside an
        # app-server-daemon package path, which is what owner.is_app_server reads.
        daemon = str(bin_dir / "packages" / "app-server-daemon" / "bin" / "codex")
        daemon_code = ("import subprocess, sys, time; "
                       "subprocess.Popen([sys.argv[2], sys.argv[1]]); time.sleep(120)")
        # (sys.executable is unusable there: it is derived from the made-up argv[0].)
        (bin_dir / "codex").write_text(
            "import subprocess, sys, threading, time\n"
            "mode = sys.argv[1] if len(sys.argv) > 1 else ''\n"
            "def serve():\n"
            "    subprocess.Popen([sys.executable, sys.argv[2]])\n"
            "    time.sleep(120)\n"
            "if mode == 'main':\n"
            "    subprocess.Popen([sys.executable, sys.argv[2]])\n"
            "elif mode == 'thread':\n"
            "    threading.Thread(target=serve, daemon=True).start()\n"
            "elif mode == 'daemon':\n"
            "    subprocess.Popen([sys.argv[3], '-c', sys.argv[4], sys.argv[2], sys.executable],\n"
            "                     executable=sys.executable)\n"
            "elif mode == 'host':\n"
            "    subprocess.Popen(['codex-code-mode-host', sys.argv[2]], executable=sys.executable)\n"
            "print('up', flush=True)\ntime.sleep(120)\n")
        if name != "codex":
            (bin_dir / name).write_text((bin_dir / "codex").read_text())
        argv = [sys.executable, str(bin_dir / name)]
        if serving:
            script = "idle.py" if serving == "host" else owner.SERVER_SCRIPT
            argv += [serving, str(bin_dir / script), daemon, daemon_code]
        proc = subprocess.Popen(argv, cwd=cwd or self.root, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        # Run in reverse: close, end the whole process group (the stand-in and
        # everything it started), reap it.
        self.addCleanup(proc.wait)
        self.addCleanup(lambda: self._end_group(proc.pid))
        self.addCleanup(proc.stdout.close)
        proc.stdout.readline()
        if serving:
            for _ in range(250):
                if self._runs_below(proc.pid, "codex-code-mode-host" if serving == "host"
                                    else owner.SERVER_SCRIPT):
                    break
                time.sleep(0.02)
            else:
                self.fail(f"stand-in ({serving}) never started its child")
        return {"pid": proc.pid, "start": owner._probe(proc.pid)[1], "proc": proc}

    @staticmethod
    def _end_group(pgid):
        import os
        import signal
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass

    @staticmethod
    def _runs_below(pid, marker):
        """Independent of the code under test: `ps` over the stand-in's
        process group (its session), not owner's procfs walk. The child's own
        line has the marker in its first two words; the stand-in merely
        carries script paths as later arguments."""
        import subprocess
        done = subprocess.run(["ps", "-o", "args=", "-g", str(pid)],
                              capture_output=True, text=True, check=False)
        return any(word.endswith(marker) for line in done.stdout.splitlines()
                   for word in line.split()[:2])

    def _hosted_question(self):
        """Leave self.sid waiting under a daemon-hosted (detached) server."""
        from aitask_questions import owner
        # A server the client's shared daemon runs: its ancestors say nothing
        # about the pane (measured on codex 0.167.2 / 0.168.0), so the chain is cut.
        hosted = {**owner.describe(), "ancestors": [], "detached": True}
        served = Store(self.root / "state", self.root, owner=hosted)
        served.fail(self.sid, served.begin(self.sid, 30)["attempt"]["id"], "timeout")
        return served

    def _panes(self, mapping):
        """Patch the pane -> foreground process lookup: {pane_pid: client}."""
        from unittest import mock
        from aitask_questions import owner
        patcher = mock.patch.object(owner, "foreground", lambda pid: (
            {"pid": mapping[pid]["pid"], "start": mapping[pid]["start"]} if mapping.get(pid) else None))
        patcher.start()
        self.addCleanup(patcher.stop)
        return mapping

    def test_daemon_hosted_question_names_no_pane_and_flags_every_candidate(self):
        import os
        from aitask_questions import waiting
        served = self._hosted_question()
        real, other = self._client(), self._client()
        panes = self._panes({4242: real, 4343: other})
        fresh = lambda: waiting.Watcher(self.root / "state", ttl=0)
        self.assertIsNone(fresh().for_pane(os.getppid()), "ancestry must not match a detached server")
        # Nothing was ever shown on a screen and this monitor has just
        # started: both clients that could hold the question are candidates,
        # neither is called its owner.
        for pane in (4242, 4343):
            found = fresh().for_pane(pane)
            self.assertEqual(found["session_id"], self.sid)
            self.assertEqual(found["association"], waiting.CANDIDATE)
        # The lookup takes no screen text at all: a quoted id cannot move or
        # claim anything.
        with self.assertRaises(TypeError):
            fresh().for_pane(4343, f"quoting {self.sid}")
        # Nothing is written beside the question state.
        self.assertEqual(sorted(p.name for p in (self.root / "state").iterdir()
                                if not p.name.startswith("questions.sqlite3")), [])
        # The pane's program changed (back at a shell, here this test process).
        panes[4242] = {"pid": os.getpid(), "start": "x"}
        self.assertIsNone(fresh().for_pane(4242))
        self.assertIsNotNone(fresh().for_pane(4343))
        # Answered: no pane waits.
        self.submit("q1", "blue", served)
        self.assertIsNone(fresh().for_pane(4343))

    def test_candidate_is_a_remote_client_inside_the_project(self):
        import shutil
        import subprocess
        import tempfile
        from aitask_questions import owner, waiting
        self._hosted_question()
        elsewhere = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, elsewhere, True)
        idle = subprocess.Popen(["sleep", "120"], cwd=self.root)
        self.addCleanup(idle.wait)
        self.addCleanup(idle.kill)
        shell = {"pid": idle.pid, "start": owner._probe(idle.pid)[1]}
        self.assertTrue(owner.inside(shell["pid"], self.root))
        self._panes({1001: self._client(serving="main"), 1002: self._client(cwd=elsewhere),
                     1003: self._client(), 1004: shell,
                     1005: self._client(serving="thread"), 1006: self._client(serving="daemon"),
                     1007: self._client(name="codex-app-server-not"),
                     1008: self._client(serving="host")})
        watcher = waiting.Watcher(self.root / "state", ttl=0)
        self.assertIsNone(watcher.for_pane(1004), "a program that is not the client")
        self.assertIsNone(watcher.for_pane(1001), "a client hosting its own question server")
        self.assertIsNone(watcher.for_pane(1005),
                          "a client whose own server was started from a worker thread")
        self.assertIsNone(watcher.for_pane(1002), "a client outside the project")
        self.assertIsNone(watcher.for_pane(1008),
                          "an in-process client that runs no question server")
        self.assertEqual(watcher.for_pane(1003)["association"], waiting.CANDIDATE)
        # The client that started the shared daemon hosts nothing itself: the
        # server below the daemon is the daemon's, so it is a candidate too.
        self.assertEqual(watcher.for_pane(1006)["association"], waiting.CANDIDATE)
        self.assertIsNotNone(watcher.for_pane(1007))

    def test_children_are_read_from_every_thread_and_hosting_stops_at_an_app_server(self):
        import os
        from aitask_questions import owner
        threaded, main = self._client(serving="thread"), self._client(serving="main")
        behind_daemon, plain = self._client(serving="daemon"), self._client()
        if os.path.isdir(f"/proc/{threaded['pid']}/task"):
            with open(f"/proc/{threaded['pid']}/task/{threaded['pid']}/children") as handle:
                self.assertEqual(handle.read().split(), [],
                                 "fixture: the main thread must list no child")
        self.assertEqual(len(owner._children(threaded["pid"])), 1)
        self.assertTrue(owner.hosts_sessions(threaded["pid"]))
        self.assertTrue(owner.hosts_sessions(main["pid"]))
        self.assertTrue(owner.hosts_sessions(self._client(serving="host")["pid"]))
        self.assertFalse(owner.hosts_sessions(plain["pid"]))
        # client -> app-server -> question server: the app-server is found,
        # and the walk ends there.
        (daemon,) = owner._children(behind_daemon["pid"])
        self.assertTrue(owner.is_app_server(owner._argv(daemon)))
        self.assertTrue(owner.hosts_sessions(daemon), "fixture: the server runs below the daemon")
        self.assertFalse(owner.hosts_sessions(behind_daemon["pid"]))

    def test_serving_pane_is_never_a_mere_candidate(self):
        import os
        from aitask_questions import owner, waiting
        served = Store(self.root / "state", self.root, owner=owner.describe())
        served.fail(self.sid, served.begin(self.sid, 30)["attempt"]["id"], "timeout")
        self.assertFalse(owner.describe()["detached"])
        watcher = waiting.Watcher(self.root / "state", ttl=0)
        # An in-process question: other panes get nothing, however eligible.
        self._panes({4242: self._client()})
        self.assertIsNone(watcher.for_pane(4242))
        self.assertEqual(watcher.for_pane(os.getppid())["association"], waiting.PROCESS)

    def test_app_server_processes_end_the_ancestor_chain(self):
        from aitask_questions import owner
        daemon = "/home/u/.codex/packages/app-server-daemon/releases/0.167.2/bin/codex"
        self.assertTrue(owner.is_app_server([daemon, "app-server", "--listen", "unix://", "--managed-daemon"]))
        self.assertTrue(owner.is_app_server(["/usr/bin/codex", "app-server"]))
        self.assertTrue(owner.is_app_server([daemon.replace("/codex", "/codex-code-mode-host")]))
        # The TUI itself, and a prompt that merely says the words.
        self.assertFalse(owner.is_app_server(["/usr/bin/codex", "--no-alt-screen", "app-server"]))
        self.assertFalse(owner.is_app_server(["/usr/bin/codex", "exec", "app-server"]))
        self.assertFalse(owner.is_app_server(["/usr/bin/python", "app-server"]))
        self.assertFalse(owner.is_app_server([]))

    def test_every_result_starts_with_the_session_id(self):
        # The client prints the first lines of a tool result in the pane, so
        # the user can see which question a pane's conversation is holding.
        import json
        view = self.store.status(self.sid)
        self.assertTrue(json.dumps(view).startswith(f'{{"session_id": "{self.sid}"'))

    def test_waiting_question_of_a_closed_session_is_not_reported(self):
        import os
        from aitask_questions import owner, waiting
        me = owner.describe()
        for label, stamp in (("pid gone", {**me, "pid": 2 ** 22 + 54321}),
                             ("pid reused by another process", {**me, "start": "0"}),
                             ("malformed stamp", {"pid": "x"})):
            with self.subTest(label):
                served = Store(self.root / "state", self.root, owner=stamp)
                state = served.open("test-run", "closed-" + label.replace(" ", "-"), "o1", questions(), [])
                attempt = served.begin(state["session_id"], 30)["attempt"]["id"]
                served.fail(state["session_id"], attempt, "timeout")
                self.assertIsNone(waiting.Watcher(self.root / "state", ttl=0).for_pane(os.getppid()))
        # No state at all, and the reader never creates any.
        self.assertEqual(waiting.waiting(self.root / "absent"), [])
        self.assertFalse((self.root / "absent").exists())

    def test_requirement_fields_are_bound_and_workflow_state_is_not(self):
        from aitask_questions.projection import task_requirements as req
        base = b"---\npriority: high\nstatus: Ready\ndepends: [1, 3]\ngates: [risk_evaluated]\n---\nBody\n"
        same = (b"---\nstatus: Implementing\nassigned_to: a@b\npriority: low\nboardidx: 5\n"
                b"depends:\n  - 1\n  - 3\ngates: [ risk_evaluated ]\nactive_gates: [risk_evaluated]\n"
                b"updated_at: 2026-01-01 10:00\n---\nBody\n")
        self.assertEqual(req(base), req(same))
        for label, changed in (("dependency added", base.replace(b"[1, 3]", b"[1, 3, 9]")),
                               ("dependency removed", base.replace(b"depends: [1, 3]\n", b"")),
                               ("gate added", base.replace(b"[risk_evaluated]", b"[risk_evaluated, docs_updated]")),
                               ("issue type set", base.replace(b"priority: high", b"priority: high\nissue_type: bug")),
                               ("body edited", base.replace(b"Body", b"Body, and more"))):
            with self.subTest(label):
                self.assertNotEqual(req(base), req(changed))
        self.assertEqual(req(b"---\ndepends: []\n---\nBody\n"), req(b"---\npriority: low\n---\nBody\n"))
        # A requirement line in the body cannot pass for frontmatter, or the reverse.
        self.assertNotEqual(req(b"---\ndepends: [1]\n---\nBody\n"), req(b'---\n---\ndepends: ["1"]\n---\nBody\n'))

    def test_plan_bookkeeping_is_checkbox_state_only(self):
        from aitask_questions.projection import plan_covers
        plan = b"# Plan\n\n- [ ] one\n  * [ ] nested\n1. [ ] numbered\n"
        self.assertTrue(plan_covers(plan, plan.replace(b"[ ] one", b"[x] one").replace(b"[ ] numbered", b"[X] numbered")))
        for label, live in (("appended workflow section", plan + b"\n## Implementation Progress\n- delete the database\n"),
                            ("appended blank line", plan + b"\n"),
                            ("edited step", plan.replace(b"[ ] one", b"[x] one more")),
                            ("removed step", plan.replace(b"1. [ ] numbered\n", b"")),
                            ("new checked step", plan + b"- [x] also delete the database\n")):
            with self.subTest(label):
                self.assertFalse(plan_covers(plan, live))

    def test_approved_commit_is_built_from_stored_bytes_not_from_the_file(self):
        import subprocess
        from aitask_questions import commit as approved_commit

        def git(*args):
            return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git("init", "-q", "-b", "main")
        for key, value in (("user.name", "t"), ("user.email", "t@example.invalid"),
                           ("commit.gpgsign", "false"), ("core.hooksPath", ".git/hooks")):
            git("config", key, value)
        (self.root / "kept.txt").write_text("kept\n")
        (self.root / "old.txt").write_text("old\n")
        git("add", "kept.txt", "old.txt")
        git("commit", "-q", "-m", "fixture")
        (self.root / "code.txt").write_text("approved\n")
        (self.root / "old.txt").unlink()
        choice = [questions()[0]]
        state = self.store.open("t7", "review_approved", "o1", choice, ["code.txt"], ["old.txt"])
        entry = next(e for e in state["manifest"] if e["path"] == "code.txt")
        self.assertEqual((entry["mode"], entry["base"]), ("100644", None))
        self.assertEqual(self.store.status(state["session_id"])["state"], "pending")
        with self.store.connect() as conn:
            body = json.loads(conn.execute("SELECT body FROM sessions WHERE id=?",
                                           (state["session_id"],)).fetchone()[0])
        self.assertEqual(body["target"], {"ref": "refs/heads/main"})
        # Whatever the files hold while the tree is built is not what is committed.
        (self.root / "code.txt").write_text("unapproved\n")
        (self.root / "old.txt").write_text("back again\n")
        (self.root / "kept.txt").write_text("edited, not part of the change\n")
        parent = git("rev-parse", "HEAD")
        oid = approved_commit.build(self.store, body, parent, b"feature: x (t7)\n")
        self.assertEqual(git("show", f"{oid}:code.txt"), "approved")
        self.assertEqual(git("show", f"{oid}:kept.txt"), "kept")
        self.assertEqual(git("ls-tree", oid, "old.txt"), "")
        self.assertEqual(git("rev-parse", f"{oid}^"), parent)
        self.assertEqual(git("rev-parse", "HEAD"), parent)  # building moves nothing
        # The branch holding something else at an approved path is a changed target.
        (self.root / "code.txt").write_text("someone else\n")
        git("add", "code.txt")
        git("commit", "-q", "-m", "concurrent", "--", "code.txt")
        with self.assertRaises(approved_commit.Refused) as refused:
            approved_commit.build(self.store, body, git("rev-parse", "HEAD"), b"m\n")
        self.assertEqual(str(refused.exception), "target_changed:code.txt")

    def test_event_history_is_bounded_without_losing_answers(self):
        self.submit("q1", "blue")
        with patch("aitask_questions.store.MAX_EVENTS", 10):
            for _ in range(30):
                attempt = self.store.begin(self.sid, 1)["attempt"]["id"]
                self.store.fail(self.sid, attempt, "timeout")
            state = self.complete()
        conn = self.raw()
        body = json.loads(conn.execute("SELECT body FROM sessions").fetchone()[0])
        self.assertEqual(len(body["events"]), 10)
        self.assertEqual(body["events"][0]["event"], "opened")
        self.assertGreater(body["events_dropped"], 0)
        self.assertEqual(state["state"], "complete")
        self.assertEqual(state["answers"]["q1"]["value"], "blue")
        self.assertEqual(state["last_event"]["event"], "answer_accepted")


if __name__ == "__main__":
    unittest.main()
