"""The roadmap's freshness contract: a capped trail is not born stale (t1569_6).

Two encoder decisions keep a capped, ad-hoc roadmap from being **born STALE**,
and neither is obvious from reading the encoder:

1. ``generation`` is built from a NARROW snapshot over only the published
   members. Built from the wide snapshot, every unpublished candidate becomes a
   digest input and unrelated churn reports as drift.
2. ``scope.topics`` lists the PUBLISHED MEMBERS, not their anchor roots.
   ``new_related_task`` fires for any task whose topic key matches an entry in
   ``scope.topics``, and a cap guarantees unpublished siblings -- so roots made
   the trail permanently stale (29 reasons at creation, measured).

Each is pinned with the negative control that makes the assertion able to fail:
re-encode the same document with the wrong choice and require the drift the
right choice avoids. Without those controls both tests would pass against an
implementation that made neither decision.

Assertions target the drift reasons attributable to the choice under test, not
the bare CURRENT/STALE verdict. `new_related_task` has three independent
triggers, and a sibling fixture always fires the `depends`/`verifies` one
(children auto-depend on siblings) -- so a verdict-level assertion would report
STALE for a reason that has nothing to do with `scope.topics` and would pass
whichever choice the encoder made.

Runs against the REAL repository, read-only, using a fixture pair discovered at
run time (two sibling tasks sharing an anchor root) so the module cannot rot
into a silent skip when specific task ids are archived.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
LIB_DIR = os.path.join(REPO_ROOT, ".aitask-scripts", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

GATHER = os.path.join(REPO_ROOT, ".aitask-scripts", "aitask_trail_gather.sh")


def _gather(args):
    proc = subprocess.run([GATHER] + args, cwd=REPO_ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=180)
    return proc.returncode, proc.stdout.decode("utf-8", "replace").splitlines()


def _find_sibling_pair():
    """Two sibling task ids under one parent, plus a third id outside them.

    Discovered from the task tree rather than hard-coded: siblings share an
    anchor root, which is what lets the `scope.topics` control discriminate
    roots from members. Returns ``(id_a, id_b, id_c)`` or ``None``.
    """
    task_dir = os.path.join(REPO_ROOT, "aitasks")
    if not os.path.isdir(task_dir):
        return None
    for entry in sorted(os.listdir(task_dir)):
        child_dir = os.path.join(task_dir, entry)
        if not (entry.startswith("t") and entry[1:].isdigit()
                and os.path.isdir(child_dir)):
            continue
        ids = []
        for name in sorted(os.listdir(child_dir)):
            if name.startswith("t") and name.endswith(".md"):
                stem = name[1:].split("_")
                if len(stem) >= 2 and stem[0].isdigit() and stem[1].isdigit():
                    ids.append("%s_%s" % (stem[0], stem[1]))
        if len(ids) >= 3:
            return ids[0], ids[1], ids[2]
    return None


def _records(lines):
    """``(digest, inputs, member_refs, scope_topics)`` from a snapshot."""
    digest, inputs, members, topics = None, [], [], []
    for line in lines:
        if line.startswith("DIGEST:"):
            digest = line[len("DIGEST:"):]
        elif line.startswith("INPUT:"):
            body = line[len("INPUT:"):]
            inputs.append({"kind": body.split("|", 1)[0],
                           "ref": body.rsplit("|", 1)[-1]})
        elif line.startswith("MEMBER:"):
            members.append(line[len("MEMBER:"):].split("|", 1)[0])
        elif line.startswith("SCOPE:"):
            body = line[len("SCOPE:"):]
            topics = [t for t in body.split("|", 1)[-1].split(",") if t]
    return digest, inputs, members, topics


def _document(members, digest, inputs, topics):
    """A minimal but SCHEMA-VALID deep trail over ``members``."""
    return {
        "schema_version": "1.1.0",
        "trail_id": "trail-drift-contract-probe",
        "title": "Drift contract probe",
        "owner": members[0],
        "scope": {"kind": "ad_hoc", "topics": sorted(topics)},
        "generation": {
            "generated_at": "2026-09-06T12:00Z",
            "generator": {"agent_string": "claudecode/opus5",
                          "skill": "aitask-backlog-roadmap"},
            "input_digest": digest,
            "inputs": inputs,
        },
        "freshness": {"state": "current", "checked_at": "2026-09-06T12:00Z"},
        "narrative": {
            "problem_statement": "Probe the freshness contract.",
            "recommendation_summary": "An estimate that reserves nothing.",
        },
        "waves": [{
            "wave_id": "wave-1",
            "ordinal": 1,
            "title": "Parallel-safe",
            "purpose": "No known conflict at check time.",
            "entries": [
                # `entry_id` is `^[a-z][a-z0-9_-]{1,63}$` -- no dots, so the
                # child separator stays `_`.
                {"entry_id": "e%s" % ref.split("#", 1)[-1],
                 "task": ref,
                 "topic": ref,
                 "position": i,
                 "classification": "core",
                 "snapshot": {"status": "Ready"},
                 "rationale": "Probe entry.",
                 "confidence": "low",
                 "evidence_refs": ["ev-probe"]}
                for i, ref in enumerate(members, start=1)
            ],
        }],
        "evidence": [{
            "evidence_id": "ev-probe",
            "source_type": "command_output",
            "ref": "aitask_trail_gather.sh snapshot --scope task",
            "observed_at": "2026-09-06T12:00Z",
            "summary": "Snapshot records for the probe members.",
        }],
        "rendering_hints": {"depth": "deep"},
    }


def _drift(document):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump(document, fh)
        path = fh.name
    try:
        rc, lines = _gather(["drift", "--trail", path])
        return lines
    finally:
        os.unlink(path)


class DriftContractTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pair = _find_sibling_pair()
        if pair is None:
            raise unittest.SkipTest(
                "no parent task directory with >=3 children to build the "
                "fixture from")
        cls.a, cls.b, cls.c = pair
        rc, lines = _gather(["snapshot", "--scope", "task", cls.a, cls.b])
        if rc != 0:
            raise unittest.SkipTest("gatherer unavailable (rc=%d)" % rc)
        cls.digest, cls.inputs, cls.members, cls.roots = _records(lines)
        if len(cls.members) < 2:
            raise unittest.SkipTest("fixture snapshot returned <2 members")

    @staticmethod
    def _topic_reasons(out):
        """Drift reasons attributable to `scope.topics` MATCHING, specifically.

        `new_related_task` has three independent triggers -- a topic-key match,
        a `depends`/`verifies` edge into the member set, and a member's
        `risk_mitigation_tasks`. Only the first is the choice under test, and a
        sibling fixture always fires the second (children auto-depend on
        siblings), so asserting on the bare verdict would measure the wrong
        trigger. The detail text is what separates them.
        """
        return [l for l in out
                if l.startswith("DRIFT:new_related_task") and "in topic" in l]

    def test_scoping_topics_to_members_raises_no_topic_drift(self):
        """The contract: publishing a capped subset must not, by itself, make
        the trail stale."""
        doc = _document(self.members, self.digest, self.inputs, self.members)
        self.assertEqual(self._topic_reasons(_drift(doc)), [])

    def test_anchor_roots_in_scope_topics_DO_raise_topic_drift(self):
        """NEGATIVE CONTROL for decision 2 -- the discriminating half.

        The gatherer's own SCOPE line reports the anchor ROOT, so this is the
        value an implementation would naturally copy. With roots, every
        unpublished sibling in the covered topic becomes a `new_related_task`,
        which is what made the roadmap born-stale. Paired with the test above,
        this proves the assertion responds to the choice rather than to the
        fixture.
        """
        if not self.roots or set(self.roots) <= set(self.members):
            self.skipTest("fixture root is not distinct from its members")
        doc = _document(self.members, self.digest, self.inputs, self.roots)
        out = _drift(doc)
        self.assertEqual(out[0], "STALE")
        self.assertTrue(self._topic_reasons(out),
                        "expected a topic-attributable new_related_task, "
                        "got: %s" % out[1:4])

    def test_a_wide_generation_over_unpublished_candidates_makes_it_STALE(self):
        """NEGATIVE CONTROL for decision 1.

        `generation` built over a candidate that is not a published member --
        what the wide snapshot would produce -- must not read CURRENT, or the
        narrow-snapshot step is unverified.
        """
        rc, wide = _gather(["snapshot", "--scope", "task",
                            self.a, self.b, self.c])
        if rc != 0:
            self.skipTest("gatherer unavailable for the wide pass")
        wide_digest, wide_inputs, wide_members, _ = _records(wide)
        if set(wide_members) <= set(self.members):
            self.skipTest("third fixture id added no distinct member")
        doc = _document(self.members, wide_digest, wide_inputs, self.members)
        self.assertEqual(_drift(doc)[0], "STALE")


if __name__ == "__main__":
    unittest.main()
