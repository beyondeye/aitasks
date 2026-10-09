"""Tests for the superseded-model offer (t1910).

Covers lib/model_supersession.py (chains, offers, the guarded recorder and the
sibling contract), the shipped table's invariants, and the
aitask_model_supersession.py CLI end to end in legacy-mode, branch-mode and
non-git roots.

Run: python3 tests/test_model_supersession.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS / "lib"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

import branch_mode_repo as bmr  # noqa: E402
import model_supersession as ms  # noqa: E402

CLI = SCRIPTS / "aitask_model_supersession.py"
SHIPPED_TABLE = SCRIPTS / "lib" / "model_supersessions.json"
PROJECT_REL = "aitasks/metadata/codeagent_config.json"
LOCAL_REL = "aitasks/metadata/codeagent_config.local.json"
KEPT_NAME = "ait-codeagent-supersession-kept.json"


def table(**agents) -> dict:
    """``table(claudecode=[("a", "b"), ...])`` -> a valid table."""
    return {"version": 1, "agents": {
        agent: {old: {"by": new, "source": "test"} for old, new in pairs}
        for agent, pairs in agents.items()}}


# --- library -----------------------------------------------------------------

class ChainTests(unittest.TestCase):
    def test_multi_hop_chain_and_furthest_registered_target(self):
        t = table(claudecode=[("a1", "a2"), ("a2", "a3"), ("a3", "a4")])
        self.assertEqual(ms.resolve_chain(t, "claudecode", "a1"), ["a1", "a2", "a3", "a4"])
        self.assertEqual(ms.offer_target(t, "claudecode", "a1", {"a2", "a3", "a4"}), "a4")
        # Terminal not registered -> the furthest node that is.
        self.assertEqual(ms.offer_target(t, "claudecode", "a1", {"a2", "a3"}), "a3")
        self.assertIsNone(ms.offer_target(t, "claudecode", "a1", set()))

    def test_cycle_raises(self):
        t = table(claudecode=[("a", "b"), ("b", "a")])
        with self.assertRaises(ms.SupersessionCycle):
            ms.resolve_chain(t, "claudecode", "a")

    def test_unknown_model_and_agent_have_no_successor(self):
        t = table(claudecode=[("a", "b")])
        self.assertEqual(ms.resolve_chain(t, "claudecode", "zzz"), ["zzz"])
        self.assertIsNone(ms.offer_target(t, "codex", "a", {"b"}))

    def test_unavailable_models_are_not_offerable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models_opencode.json"
            path.write_text(json.dumps({"models": [
                {"name": "x1"}, {"name": "x2", "status": "unavailable"},
                {"name": "x3", "status": "active"}]}))
            self.assertEqual(ms.load_registry(path), {"x1", "x3"})
            self.assertIsNone(ms.load_registry(Path(tmp) / "missing.json"))

    def test_validate_rejects_bad_shapes(self):
        for bad in ({"version": 2, "agents": {}}, {"version": 1},
                    {"version": 1, "agents": {"claudecode": {"a": {"by": "B!"}}}}):
            with self.subTest(bad=bad), self.assertRaises(ms.SupersessionError):
                ms.validate_table(bad)


class FindOffersTests(unittest.TestCase):
    T = table(claudecode=[("opus5", "opus5_5"), ("sonnet5", "sonnet5_5")])
    REG = {"claudecode": {"opus5", "opus5_5", "sonnet5", "sonnet5_5", "haiku4_5"}}

    def test_ops_grouped_per_superseded_model_in_config_order(self):
        defaults = {"pick": "claudecode/opus5", "qa": "claudecode/sonnet5",
                    "explore": "claudecode/opus5", "learn": "claudecode/opus5"}
        offers, warnings = ms.find_offers("project", defaults, self.T, self.REG)
        self.assertEqual(warnings, [])
        self.assertEqual(offers, [
            ms.Offer("project", "claudecode", "opus5", "opus5_5", ("pick", "explore", "learn")),
            ms.Offer("project", "claudecode", "sonnet5", "sonnet5_5", ("qa",)),
        ])

    def test_non_superseded_custom_default_is_never_offered(self):
        defaults = {"pick": "claudecode/haiku4_5", "raw": "codex/gpt5_4",
                    "explain": "claudecode/opus5_5"}
        offers, warnings = ms.find_offers("local", defaults, self.T, self.REG)
        self.assertEqual((offers, warnings), ([], []))

    def test_malformed_values_missing_registry_and_cycles_warn_not_fail(self):
        t = table(claudecode=[("x", "y"), ("y", "x")], codex=[("g1", "g2")])
        defaults = {"pick": "nonsense", "a": "claudecode/x", "b": "codex/g1"}
        offers, warnings = ms.find_offers("project", defaults, t,
                                          {"claudecode": {"x", "y"}})
        self.assertEqual(offers, [])
        self.assertEqual(len(warnings), 3, warnings)
        self.assertTrue(any("malformed" in w for w in warnings))
        self.assertTrue(any("cycle" in w for w in warnings))
        self.assertTrue(any("no model registry for 'codex'" in w for w in warnings))

    def test_trailing_newline_values_are_malformed_not_offered(self):
        self.assertIsNone(ms.parse_agent_string("claudecode/opus5\n"))
        self.assertFalse(ms.valid_agent("claudecode\n"))
        self.assertFalse(ms.valid_model("opus5\n"))
        with self.assertRaises(ms.SupersessionError):
            ms.validate_table({"version": 1, "agents": {
                "claudecode": {"opus5\n": {"by": "opus5_5"}}}})
        offers, warnings = ms.find_offers(
            "project", {"pick": "claudecode/opus5\n"}, self.T, self.REG)
        self.assertEqual(offers, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("malformed", warnings[0])

    def test_seed_violations(self):
        seed = {"pick": "claudecode/opus5_5", "qa": "claudecode/sonnet5"}
        self.assertEqual(ms.seed_violations(self.T, seed), [("qa", "claudecode", "sonnet5")])

    def test_keep_memory_is_per_offered_target(self):
        offer = ms.Offer("project", "claudecode", "opus5", "opus5_5", ("pick",))
        kept = ms.with_kept({}, offer)
        self.assertTrue(ms.is_kept(kept, offer))
        self.assertFalse(ms.is_kept(kept, offer._replace(new="opus6")))
        self.assertFalse(ms.is_kept(kept, offer._replace(layer="local")))
        self.assertFalse(ms.is_kept(ms.without_kept(kept, offer), offer))


class SharedReaderTests(unittest.TestCase):
    """Readers shared by the CLI and the Settings TUI (t1921)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_ms_readers_")
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_load_registries_skips_local_and_warns_on_bad_json(self):
        (self.dir / "models_claudecode.json").write_text(
            json.dumps({"models": [{"name": "opus5"},
                                   {"name": "gone", "status": "unavailable"}]}))
        (self.dir / "models_claudecode.local.json").write_text("{not json")
        (self.dir / "models_codex.json").write_text("{not json")
        registries, warnings = ms.load_registries(str(self.dir))
        self.assertEqual(registries, {"claudecode": {"opus5"}})
        self.assertEqual(len(warnings), 1)
        self.assertIn("cannot read models_codex.json", warnings[0])
        self.assertIn("no offers for 'codex'", warnings[0])

    def test_load_registries_missing_dir_is_empty(self):
        self.assertEqual(ms.load_registries(str(self.dir / "nope")), ({}, []))

    def test_load_kept(self):
        self.assertEqual(ms.load_kept(None), ({}, []))
        self.assertEqual(ms.load_kept(str(self.dir / "absent.json")), ({}, []))
        path = self.dir / KEPT_NAME
        path.write_text(json.dumps({
            "project": {"claudecode/opus5": "claudecode/opus5_5", "x": 1},
            "local": [],
            "other": {"ignored": "yes"}}))
        kept, warnings = ms.load_kept(str(path))
        self.assertEqual(kept, {"project": {"claudecode/opus5": "claudecode/opus5_5"}})
        self.assertEqual(len(warnings), 2)
        path.write_text("[1]")
        self.assertEqual(ms.load_kept(str(path))[0], {})

    def test_kept_path_outside_git_is_none(self):
        self.assertIsNone(ms.kept_path(str(self.dir)))
        subprocess.run(["git", "init", "-q", "."], cwd=self.dir, check=True)
        self.assertEqual(Path(ms.kept_path(str(self.dir))).resolve(),
                         (self.dir / ".git" / KEPT_NAME).resolve())


class RecordTests(unittest.TestCase):
    AVAIL = {"m1", "m2", "m3", "m1_1m", "m2_1m"}

    def promote(self, t, new, before, after, available=None):
        return ms.plan_promotion(t, "claudecode", new, before, after,
                                 self.AVAIL if available is None else available, "src")

    def test_complete_retirement_records_edge_and_eligible_sibling(self):
        t, events, blocked = self.promote(
            ms.empty_table(), "m2",
            {"pick": "claudecode/m1", "explore": "claudecode/m1", "qa": "claudecode/m3"},
            {"pick": "claudecode/m2", "explore": "claudecode/m2", "qa": "claudecode/m3"})
        self.assertFalse(blocked)
        self.assertEqual(events, ["RECORDED:claudecode/m1->claudecode/m2",
                                  "RECORDED_SIBLING:claudecode/m1_1m->claudecode/m2_1m"])
        self.assertEqual(ms.successor(t, "claudecode", "m1"), "m2")
        self.assertEqual(ms.successor(t, "claudecode", "m1_1m"), "m2_1m")
        self.assertEqual(t["agents"]["claudecode"]["m1_1m"]["source"], "src (_1m sibling)")

    def test_partial_promotion_is_blocked_naming_remaining_ops(self):
        t0 = ms.empty_table()
        t, events, blocked = self.promote(
            t0, "m2", {"pick": "claudecode/m1", "explore": "claudecode/m1", "trail": "claudecode/m1"},
            {"pick": "claudecode/m2", "explore": "claudecode/m1", "trail": "claudecode/m1"})
        self.assertTrue(blocked)
        self.assertEqual(events, ["BLOCKED:partial:claudecode/m1|explore,trail"])
        self.assertEqual(t, t0)

    def test_conflict_never_overwrites(self):
        t0 = table(claudecode=[("m1", "m2")])
        t, events, blocked = self.promote(t0, "m3", {"pick": "claudecode/m1"},
                                          {"pick": "claudecode/m3"})
        self.assertTrue(blocked)
        self.assertEqual(events, ["BLOCKED:conflict:claudecode/m1->claudecode/m2"])
        self.assertEqual(ms.successor(t, "claudecode", "m1"), "m2")

    def test_cycle_unregistered_exists_self(self):
        _, events, blocked = self.promote(table(claudecode=[("m2", "m1")]), "m2",
                                          {"pick": "claudecode/m1"}, {"pick": "claudecode/m2"})
        self.assertTrue(blocked)
        self.assertIn("BLOCKED:cycle:claudecode/m1->claudecode/m2", events)

        _, events, blocked = self.promote(ms.empty_table(), "zz",
                                          {"pick": "claudecode/m1"}, {"pick": "claudecode/zz"})
        self.assertTrue(blocked)
        self.assertEqual(events, ["BLOCKED:unregistered:claudecode/zz"])

        t0 = table(claudecode=[("m1", "m2"), ("m1_1m", "m2_1m")])
        t, events, blocked = self.promote(t0, "m2", {"pick": "claudecode/m1"},
                                          {"pick": "claudecode/m2"})
        self.assertFalse(blocked)
        self.assertEqual(events, ["SKIPPED:exists:claudecode/m1->claudecode/m2",
                                  "SKIPPED:sibling_exists:claudecode/m1_1m->claudecode/m2_1m"])
        self.assertEqual(t, t0)

        _, events, _ = ms.plan_explicit(ms.empty_table(), "claudecode", "m1", "m1", {},
                                        self.AVAIL, "src")
        self.assertEqual(events, ["SKIPPED:self:claudecode/m1"])

    def test_family_warning_and_cross_agent_skip(self):
        _, events, blocked = ms.plan_promotion(
            ms.empty_table(), "claudecode", "opus5_5",
            {"pick": "claudecode/sonnet5", "shadow": "codex/gpt6_sol"},
            {"pick": "claudecode/opus5_5", "shadow": "claudecode/opus5_5"},
            {"sonnet5", "opus5_5"}, "src")
        self.assertFalse(blocked)
        self.assertEqual(events, ["SKIPPED:cross_agent:codex/gpt6_sol",
                                  "RECORDED:claudecode/sonnet5->claudecode/opus5_5",
                                  "WARN:family:claudecode/sonnet5->claudecode/opus5_5"])

    def test_explicit_in_seed_and_hand_broken_seed_invariant(self):
        _, events, blocked = ms.plan_explicit(
            ms.empty_table(), "claudecode", "m1", "m2", {"qa": "claudecode/m1"},
            self.AVAIL, "src")
        self.assertTrue(blocked)
        self.assertEqual(events, ["BLOCKED:in_seed:claudecode/m1|qa"])
        # An unrelated, pre-existing violation still blocks the write.
        _, events, blocked = ms.plan_explicit(
            table(claudecode=[("m3", "m2")]), "claudecode", "m1", "m2",
            {"qa": "claudecode/m3"}, self.AVAIL, "src")
        self.assertTrue(blocked)
        self.assertIn("BLOCKED:seed_invariant:qa|claudecode/m3", events)


class SiblingContractTests(unittest.TestCase):
    """Recorder and contract share sibling_eligibility(): they must agree."""

    REG = {"claudecode": {"a", "b", "a_1m", "b_1m"}}

    def missing(self, t, seed):
        return ms.missing_sibling_edges(t, seed, self.REG)

    def test_eligible_absent_sibling_is_reported(self):
        self.assertEqual(self.missing(table(claudecode=[("a", "b")]), {}),
                         [("claudecode", "a_1m", "b_1m")])

    def test_intentional_skips_are_not_reported(self):
        cases = {
            "sibling_in_seed": (table(claudecode=[("a", "b")]), {"x": "claudecode/a_1m"}),
            "sibling_conflict": (table(claudecode=[("a", "b"), ("a_1m", "a")]), {}),
            "sibling_cycle": (table(claudecode=[("a", "b"), ("b_1m", "a_1m")]), {}),
        }
        for reason, (t, seed) in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.missing(t, seed), [])
                self.assertEqual(
                    ms.sibling_eligibility(t, "claudecode", "a", "b", seed,
                                           self.REG["claudecode"]),
                    (False, reason))
        unregistered = {"claudecode": {"a", "b", "a_1m"}}
        self.assertEqual(ms.missing_sibling_edges(table(claudecode=[("a", "b")]), {},
                                                  unregistered), [])

    def test_recorder_matches_contract(self):
        seed_before = {"pick": "claudecode/a", "x": "claudecode/a_1m"}
        seed_after = {"pick": "claudecode/b", "x": "claudecode/a_1m"}
        t, events, blocked = ms.plan_promotion(
            ms.empty_table(), "claudecode", "b", seed_before, seed_after,
            self.REG["claudecode"], "src")
        self.assertFalse(blocked)
        self.assertIn("SKIPPED:sibling_in_seed:claudecode/a_1m->claudecode/b_1m", events)
        self.assertEqual(self.missing(t, seed_after), [])


# --- the shipped table -------------------------------------------------------

def _seed_registries() -> dict:
    regs = {}
    for path in (REPO_ROOT / "seed").glob("models_*.json"):
        regs[path.name[len("models_"):-len(".json")]] = ms.load_registry(path)
    return regs


class ShippedTableTests(unittest.TestCase):
    def setUp(self):
        self.table = ms.load_table(SHIPPED_TABLE)
        self.seed = json.loads((REPO_ROOT / "seed" / "codeagent_config.json")
                               .read_text())["defaults"]
        self.regs = _seed_registries()

    def test_canonical_format(self):
        self.assertEqual(SHIPPED_TABLE.read_text(encoding="utf-8"),
                         ms.render_table(self.table))

    def test_every_edge_is_registered_acyclic_and_same_family(self):
        for agent, edges in self.table["agents"].items():
            for old, entry in edges.items():
                with self.subTest(edge=f"{agent}/{old}->{entry['by']}"):
                    self.assertIn(old, self.regs[agent])
                    self.assertIn(entry["by"], self.regs[agent])
                    ms.resolve_chain(self.table, agent, old)
                    self.assertEqual(ms.family(old), ms.family(entry["by"]))

    def test_seed_invariant_and_sibling_completeness(self):
        self.assertEqual(ms.seed_violations(self.table, self.seed), [])
        self.assertEqual(ms.missing_sibling_edges(self.table, self.seed, self.regs), [])
        offers, _ = ms.find_offers("project", self.seed, self.table, self.regs)
        self.assertEqual(offers, [], "a fresh config must never be offered a switch")


# --- CLI ---------------------------------------------------------------------

def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check,
                          capture_output=True, text=True)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _models(meta: Path, names) -> None:
    _write_json(meta / "models_claudecode.json",
                {"models": [{"name": n, "cli_id": n} for n in names]})


def make_legacy_repo(root: Path, project, local=None, names=("opus5", "opus5_5", "sonnet5", "sonnet5_5")):
    """Legacy mode: aitasks/ on the code branch, real metadata-commit helper."""
    meta = root / "aitasks" / "metadata"
    _write_json(meta / "codeagent_config.json", {"defaults": project})
    if local is not None:
        _write_json(meta / "codeagent_config.local.json", {"defaults": local})
    _models(meta, names)
    (root / ".gitignore").write_text("aitasks/metadata/*.local.json\n")
    scripts = root / ".aitask-scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    helper = scripts / "aitask_metadata_commit.sh"
    helper.write_bytes((SCRIPTS / "aitask_metadata_commit.sh").read_bytes())
    helper.chmod(0o755)
    (scripts / "lib").symlink_to(SCRIPTS / "lib")
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "test@test.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def run_check(root, *flags, stdin_text=None, table_path=None, timeout=60):
    argv = [sys.executable, str(CLI), "check", "--root", str(root), "--porcelain", *flags]
    if table_path is not None:
        argv += ["--table", str(table_path)]
    env = dict(os.environ)
    env.pop("TASK_DIR", None)
    return subprocess.run(argv, input=stdin_text if stdin_text is not None else "",
                          capture_output=True, text=True, timeout=timeout, env=env)


def project_defaults(root: Path) -> dict:
    return json.loads((root / PROJECT_REL).read_text())["defaults"]


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.table_path = self.tmp / "table.json"
        self.set_table(table(claudecode=[("opus5", "opus5_5"), ("sonnet5", "sonnet5_5")]))

    def set_table(self, t):
        self.table_path.write_text(ms.render_table(t))


class CheckReportTests(CliCase):
    def test_report_lists_offers_and_never_reads_stdin(self):
        root = self.tmp / "nogit"
        meta = root / "aitasks" / "metadata"
        _write_json(meta / "codeagent_config.json",
                    {"defaults": {"pick": "claudecode/opus5", "qa": "claudecode/haiku4_5"}})
        _write_json(meta / "codeagent_config.local.json",
                    {"defaults": {"explain": "claudecode/sonnet5", "pick": "claudecode/opus5"}})
        _models(meta, ["opus5", "opus5_5", "sonnet5", "sonnet5_5", "haiku4_5"])
        # A stdin pipe that is never closed: a read would block until the timeout.
        proc = subprocess.Popen(
            [sys.executable, str(CLI), "check", "--root", str(root), "--porcelain",
             "--table", str(self.table_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # wait(), not communicate(): communicate() would close stdin first.
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.fail("report mode blocked on stdin")
        finally:
            proc.stdin.close()
        out = proc.stdout.read()
        proc.stdout.close()
        proc.stderr.close()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(out.splitlines(), [
            "OFFER:project|claudecode/opus5|claudecode/opus5_5|pick",
            "OFFER:local|claudecode/opus5|claudecode/opus5_5|pick",
            "OFFER:local|claudecode/sonnet5|claudecode/sonnet5_5|explain",
        ])
        self.assertNotIn("haiku4_5", out)

    def test_none_and_human_hint(self):
        root = self.tmp / "nogit"
        meta = root / "aitasks" / "metadata"
        _write_json(meta / "codeagent_config.json", {"defaults": {"pick": "claudecode/opus5_5"}})
        _models(meta, ["opus5", "opus5_5"])
        self.assertEqual(run_check(root, table_path=self.table_path).stdout.strip(), "NONE")
        _write_json(meta / "codeagent_config.json", {"defaults": {"pick": "claudecode/opus5"}})
        human = subprocess.run(
            [sys.executable, str(CLI), "check", "--root", str(root),
             "--table", str(self.table_path)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertIn("ait codeagent check-superseded", human.stdout)

    def test_record_exit_3_on_blocked(self):
        seed_before = self.tmp / "before.json"
        seed_after = self.tmp / "after.json"
        _write_json(seed_before, {"defaults": {"pick": "claudecode/opus5", "qa": "claudecode/opus5"}})
        _write_json(seed_after, {"defaults": {"pick": "claudecode/opus6", "qa": "claudecode/opus5"}})
        models = self.tmp / "models.json"
        _write_json(models, {"models": [{"name": "opus5"}, {"name": "opus6"}]})
        proc = subprocess.run(
            [sys.executable, str(CLI), "record", "--table", str(self.tmp / "absent.json"),
             "--output", str(self.tmp / "out.json"), "--models", str(models),
             "--agent", "claudecode", "--new", "opus6",
             "--seed-before", str(seed_before), "--seed-after", str(seed_after)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn("BLOCKED:partial:claudecode/opus5|qa", proc.stdout)


class CheckInteractiveTests(CliCase):
    def test_accept_and_decline_then_keep_memory(self):
        root = make_legacy_repo(self.tmp / "legacy", {
            "pick": "claudecode/opus5", "explore": "claudecode/opus5",
            "qa": "claudecode/sonnet5", "raw": "claudecode/haiku4_5"})
        proc = run_check(root, "--interactive", stdin_text="y\nn\n", table_path=self.table_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SWITCHED:project|claudecode/opus5|claudecode/opus5_5|pick,explore",
                      proc.stdout)
        self.assertIn("DECLINED:project|claudecode/sonnet5|claudecode/sonnet5_5|qa", proc.stdout)
        self.assertIn("COMMIT:committed:ait: Update codeagent_config.json", proc.stdout)
        self.assertEqual(project_defaults(root), {
            "pick": "claudecode/opus5_5", "explore": "claudecode/opus5_5",
            "qa": "claudecode/sonnet5", "raw": "claudecode/haiku4_5"})
        self.assertEqual(_git(root, "status", "--porcelain").stdout, "")
        self.assertEqual(_git(root, "log", "-1", "--format=%s", "--", PROJECT_REL).stdout.strip(),
                         "ait: Update codeagent_config.json")
        kept = json.loads((root / ".git" / KEPT_NAME).read_text())
        self.assertEqual(kept, {"project": {"claudecode/sonnet5": "claudecode/sonnet5_5"}})

        # Re-run: the declined offer is not asked again (an ask would hit EOF).
        again = run_check(root, "--interactive", table_path=self.table_path)
        self.assertEqual(again.stdout.splitlines(),
                         ["KEPT:project|claudecode/sonnet5|claudecode/sonnet5_5|qa"])

        # A different target (a newer successor) re-asks.
        self.set_table(table(claudecode=[("opus5", "opus5_5"), ("sonnet5", "sonnet5_5"),
                                         ("sonnet5_5", "sonnet6")]))
        _models(root / "aitasks" / "metadata", ["opus5", "opus5_5", "sonnet5", "sonnet5_5", "sonnet6"])
        _git(root, "commit", "-q", "-am", "register sonnet6")
        third = run_check(root, "--interactive", stdin_text="y\n", table_path=self.table_path)
        self.assertIn("SWITCHED:project|claudecode/sonnet5|claudecode/sonnet6|qa", third.stdout)

    def test_eof_mid_prompt_applies_only_prior_answers(self):
        root = make_legacy_repo(self.tmp / "legacy", {
            "pick": "claudecode/opus5", "qa": "claudecode/sonnet5"})
        proc = run_check(root, "--interactive", stdin_text="y\n", table_path=self.table_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("UNANSWERED:project|claudecode/sonnet5|claudecode/sonnet5_5|qa", proc.stdout)
        self.assertEqual(project_defaults(root),
                         {"pick": "claudecode/opus5_5", "qa": "claudecode/sonnet5"})
        self.assertFalse((root / ".git" / KEPT_NAME).exists())

    def test_dirty_project_file_is_written_but_not_committed(self):
        root = make_legacy_repo(self.tmp / "legacy", {"pick": "claudecode/opus5"})
        data = json.loads((root / PROJECT_REL).read_text())
        data["defaults"]["explain"] = "claudecode/haiku4_5"  # someone's uncommitted edit
        _write_json(root / PROJECT_REL, data)
        head = _git(root, "rev-parse", "HEAD").stdout
        proc = run_check(root, "--interactive", stdin_text="y\n", table_path=self.table_path)
        self.assertIn("UNCOMMITTED:it already had uncommitted changes", proc.stdout)
        self.assertEqual(_git(root, "rev-parse", "HEAD").stdout, head)
        self.assertEqual(project_defaults(root),
                         {"pick": "claudecode/opus5_5", "explain": "claudecode/haiku4_5"})

    def test_local_layer_is_written_never_committed(self):
        root = make_legacy_repo(self.tmp / "legacy", {"pick": "claudecode/opus5_5"},
                                local={"pick": "claudecode/opus5"})
        head = _git(root, "rev-parse", "HEAD").stdout
        proc = run_check(root, "--interactive", stdin_text="y\n", table_path=self.table_path)
        self.assertIn("SWITCHED:local|claudecode/opus5|claudecode/opus5_5|pick", proc.stdout)
        self.assertNotIn("COMMIT:", proc.stdout)
        self.assertEqual(_git(root, "rev-parse", "HEAD").stdout, head)
        local = json.loads((root / LOCAL_REL).read_text())["defaults"]
        self.assertEqual(local, {"pick": "claudecode/opus5_5"})

    def test_non_git_root_neither_commits_nor_remembers(self):
        root = self.tmp / "nogit"
        meta = root / "aitasks" / "metadata"
        _write_json(meta / "codeagent_config.json",
                    {"defaults": {"pick": "claudecode/opus5", "qa": "claudecode/sonnet5"}})
        _models(meta, ["opus5", "opus5_5", "sonnet5", "sonnet5_5"])
        proc = run_check(root, "--interactive", stdin_text="y\nn\n", table_path=self.table_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("UNCOMMITTED:not a git repository", proc.stdout)
        self.assertIn("NOT_REMEMBERED:project|claudecode/sonnet5", proc.stdout)
        self.assertNotIn("REFUSED", proc.stdout + proc.stderr)
        self.assertEqual(project_defaults(root)["pick"], "claudecode/opus5_5")

    def test_branch_mode_commit_lands_on_the_data_branch(self):
        root = bmr.make_branch_mode_repo(
            self.tmp / "branch", project={"pick": "claudecode/opus5", "raw": "claudecode/haiku4_5"},
            models={"claudecode": ["opus5", "opus5_5", "haiku4_5"]})
        main_head = _git(root, "rev-parse", "HEAD").stdout
        proc = run_check(root, "--interactive", stdin_text="y\n", table_path=self.table_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("COMMIT:committed:ait: Update codeagent_config.json", proc.stdout)
        self.assertEqual(bmr.head_subject(root), "ait: Update codeagent_config.json")
        self.assertEqual(bmr.head_files(root), [PROJECT_REL])
        self.assertTrue(bmr.worktree_clean(root))
        self.assertEqual(_git(root, "rev-parse", "HEAD").stdout, main_head)


class RobustnessTests(CliCase):
    """A broken input skips its own part of the scan, never the whole check."""

    def _nogit_root(self, project_bytes=None, project=None, local=None, names=("opus5", "opus5_5")):
        root = self.tmp / "nogit"
        meta = root / "aitasks" / "metadata"
        meta.mkdir(parents=True, exist_ok=True)
        if project_bytes is not None:
            (meta / "codeagent_config.json").write_bytes(project_bytes)
        elif project is not None:
            _write_json(meta / "codeagent_config.json", {"defaults": project})
        if local is not None:
            _write_json(meta / "codeagent_config.local.json", {"defaults": local})
        _models(meta, names)
        return root

    def test_undecodable_layer_is_skipped_and_the_other_layer_still_scanned(self):
        root = self._nogit_root(project_bytes=b'{"defaults": {"pick": "\xff"}}\n',
                                local={"pick": "claudecode/opus5"})
        proc = run_check(root, table_path=self.table_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("project: cannot read", proc.stderr)
        self.assertEqual(proc.stdout.splitlines(),
                         ["OFFER:local|claudecode/opus5|claudecode/opus5_5|pick"])

    def test_trailing_newline_value_is_warned_and_never_prompted(self):
        root = self._nogit_root(project={"pick": "claudecode/opus5\n"})
        report = run_check(root, table_path=self.table_path)
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertEqual(report.stdout.strip(), "NONE")
        self.assertIn("malformed value for 'pick'", report.stderr)
        # Interactive: nothing to ask, so nothing is left unanswered.
        asked = run_check(root, "--interactive", table_path=self.table_path)
        self.assertEqual(asked.stdout.strip(), "NONE")
        self.assertEqual(project_defaults(root), {"pick": "claudecode/opus5\n"})

    def test_unreadable_registry_does_not_stop_other_agents(self):
        root = self._nogit_root(project={"pick": "claudecode/opus5"})
        (root / "aitasks" / "metadata" / "models_codex.json").mkdir()
        proc = run_check(root, table_path=self.table_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("models_codex.json", proc.stderr)
        self.assertEqual(proc.stdout.splitlines(),
                         ["OFFER:project|claudecode/opus5|claudecode/opus5_5|pick"])

    def test_malformed_keep_memory_is_ignored_with_a_warning(self):
        root = make_legacy_repo(self.tmp / "legacy", {"pick": "claudecode/opus5"})
        (root / ".git" / KEPT_NAME).write_text('{"project": null, "local": {"x": 1}}')
        proc = run_check(root, table_path=self.table_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("ignoring malformed 'project'", proc.stderr)
        self.assertEqual(proc.stdout.splitlines(),
                         ["OFFER:project|claudecode/opus5|claudecode/opus5_5|pick"])
        # Declining rewrites a well-formed memory.
        run_check(root, "--interactive", stdin_text="n\n", table_path=self.table_path)
        self.assertEqual(json.loads((root / ".git" / KEPT_NAME).read_text()),
                         {"project": {"claudecode/opus5": "claudecode/opus5_5"}, "local": {}})

    def test_recovery_command_quotes_the_repository_path(self):
        root = make_legacy_repo(self.tmp / "my project", {"pick": "claudecode/opus5"})
        hook = root / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        proc = subprocess.run(
            [sys.executable, str(CLI), "check", "--root", str(root), "--interactive",
             "--table", str(self.table_path)],
            input="y\n", capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        marker = "Review it, then run: "
        self.assertIn(marker, proc.stdout)
        command = proc.stdout.split(marker, 1)[1].splitlines()[0].strip()
        self.assertTrue(command.startswith(f"cd '{root}' && "), command)
        # The advertised command works once the cause is gone.
        hook.unlink()
        fixed = subprocess.run(["bash", "-c", command], cwd=str(self.tmp),
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)
        self.assertEqual(_git(root, "log", "-1", "--format=%s", "--", PROJECT_REL).stdout.strip(),
                         "ait: Update codeagent_config.json")


class CodeagentVerbTests(CliCase):
    def test_check_superseded_report_in_a_temp_root(self):
        root = self.tmp / "proj"
        scripts = root / ".aitask-scripts"
        scripts.mkdir(parents=True)
        for name in ("aitask_codeagent.sh", "aitask_model_supersession.py"):
            shutil.copy2(SCRIPTS / name, scripts / name)
        (scripts / "lib").symlink_to(SCRIPTS / "lib")
        meta = root / "aitasks" / "metadata"
        _write_json(meta / "codeagent_config.json", {"defaults": {"pick": "claudecode/opus5"}})
        _models(meta, ["opus5", "opus5_5"])
        proc = subprocess.run(["bash", str(scripts / "aitask_codeagent.sh"),
                               "check-superseded", "--report"],
                              cwd=str(self.tmp), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("claudecode/opus5 (pick) — superseded by claudecode/opus5_5", proc.stdout)
        self.assertIn("ait codeagent check-superseded", proc.stdout)


if __name__ == "__main__":
    unittest.main()
