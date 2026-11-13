"""Lossless selection, page recovery, and native/text adapter parity."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))
from aitask_questions.store import QuestionError, Store


def multi_question():
    return {"id": "deps", "kind": "multi", "text": "Choose dependencies", "page_size": 3,
            "options": [{"id": x, "label": "Same label", "description": f"Description for {x}"}
                        for x in ["task-1", "a,b", 'a"b', "tests", "5", "t6", "7"]]}


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "state", self.root)
        self.q = multi_question()
        self.sid = self.store.open("run", "check", "first", [self.q], [])["session_id"]

    def send(self, selected, action, page_id=None, source="codex_prompt_model_forwarded", attempt=None):
        value = {"selected": selected, "action": action}
        if source != "mcp_form":
            value = json.dumps(value)
        page_id = page_id or self.store.status(self.sid)["pending_page"]["page_id"]
        return self.store.submit(self.sid, "deps", value, source, attempt, page_id)

    def test_native_page_prompt_recovery_and_native_finish_preserve_order(self):
        first = self.store.begin(self.sid, 20)
        self.send(['a"b', "task-1"], "next", source="mcp_form", attempt=first["attempt"]["id"])
        second = self.store.begin(self.sid, 20)
        self.store.fail(self.sid, second["attempt"]["id"], "timeout")
        self.store = Store(self.root / "state", self.root)
        recovered = self.send(["t6", "tests"], "next")
        self.assertEqual(recovered["pending_page"]["selected_so_far"], ["task-1", 'a"b', "tests", "t6"])
        self.assertEqual(recovered["answers"], {})
        self.assertIsNone(recovered["receipt"])
        last = self.store.begin(self.sid, 20)
        done = self.send(["7"], "finish", source="mcp_form", attempt=last["attempt"]["id"])
        self.assertEqual(done["answers"]["deps"]["value"], ["task-1", 'a"b', "tests", "t6", "7"])
        self.assertEqual(done["state"], "complete")
        self.assertEqual([x["source"] for x in done["answers"]["deps"]["pages"].values()],
                         ["mcp_form", "codex_prompt_model_forwarded", "mcp_form"])

    def test_page_replay_is_idempotent_and_conflict_does_not_drop_selection(self):
        page_id = self.store.status(self.sid)["pending_page"]["page_id"]
        self.send(["a,b"], "next", page_id)
        repeated = self.send(["a,b"], "next", page_id)
        self.assertEqual(repeated["outcome"], "duplicate")
        conflict = self.send(["task-1"], "next", page_id)
        self.assertEqual(conflict["outcome"], "conflict")
        self.assertEqual(conflict["pending_page"]["selected_so_far"], ["a,b"])
        self.assertEqual(conflict["pending_page"]["index"], 1)

    def test_none_is_explicit_and_clears_prior_pages(self):
        self.send(["task-1"], "next")
        done = self.send([], "none")
        self.assertEqual(done["state"], "complete")
        self.assertEqual(done["answers"]["deps"]["value"], [])

    def test_all_includes_full_original_candidate_set(self):
        done = self.send([], "all")
        self.assertEqual(done["answers"]["deps"]["value"], [o["id"] for o in self.q["options"]])

    def test_early_finish_does_not_select_unseen_items(self):
        done = self.send(["a,b"], "finish")
        self.assertEqual(done["answers"]["deps"]["value"], ["a,b"])

    def test_invalid_or_ambiguous_input_never_completes_empty_selection(self):
        page_id = self.store.status(self.sid)["pending_page"]["page_id"]
        for raw in ["", "status?", "task-1, a,b", "[]", '{"selected":[]}',
                    '{"selected":[],"selected":["task-1"],"action":"finish"}']:
            with self.subTest(raw=raw), self.assertRaises(QuestionError):
                self.store.submit(self.sid, "deps", raw, "codex_prompt_model_forwarded", page_id=page_id)
        for selected, action in [(["missing"], "finish"), (["7"], "next"),
                                 (["task-1"], "none"), (["task-1"], "all"),
                                 (["task-1", "task-1"], "next")]:
            with self.subTest(selected=selected, action=action), self.assertRaises(QuestionError):
                self.send(selected, action)
        self.assertEqual(self.store.status(self.sid)["answers"], {})

    def test_missing_page_identity_and_stale_form_are_rejected(self):
        with self.assertRaises(QuestionError):
            self.store.submit(self.sid, "deps", {"selected": [], "action": "finish"}, "codex_prompt_model_forwarded")
        first = self.store.begin(self.sid, 20)
        self.store.fail(self.sid, first["attempt"]["id"], "timeout")
        self.store.begin(self.sid, 20)
        late = self.send(["task-1"], "next", source="mcp_form", attempt=first["attempt"]["id"])
        self.assertEqual(late["outcome"], "stale_attempt")

    def test_candidate_change_requires_new_occurrence(self):
        self.send(["task-1"], "next")
        changed = deepcopy(self.q)
        changed["options"].append({"id": "new", "label": "New", "description": "Added later"})
        with self.assertRaises(QuestionError):
            self.store.open("run", "check", "first", [changed], [])
        new = self.store.open("run", "check", "revised", [changed], [])
        self.assertEqual(new["pending_page"]["selected_so_far"], [])
        self.assertEqual(self.store.status(self.sid)["state"], "invalidated")

    def test_cardinality_and_no_early_finish(self):
        q = deepcopy(self.q)
        q.update(min_selected=2, max_selected=3, allow_early_finish=False)
        self.sid = self.store.open("run", "check", "bounded", [q], [])["session_id"]
        for selected, action in [(["task-1"], "finish"), ([], "none"), ([], "all")]:
            with self.assertRaises(QuestionError):
                self.send(selected, action)
        self.send(["task-1"], "next")
        self.send(["tests"], "next")
        done = self.send([], "finish")
        self.assertEqual(done["answers"]["deps"]["value"], ["task-1", "tests"])


if __name__ == "__main__":
    unittest.main()
