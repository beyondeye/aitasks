"""Every writer of a tracked `aitasks/metadata` file has an owner (t1677).

t1599_3 stopped `ait sync` sweeping ownerless files into unrelated tasks'
commits. t1677 gave those files owners. This guard keeps the second half true:
the guarantee decays the moment someone adds a config writer that commits
nothing, and *that is how the original defect arose* -- `board_config.json` and
`stats_config.json` got writers and never got committers.

WHAT THIS GUARD DOES AND DOES NOT CLAIM
---------------------------------------
No regex over source can enumerate "every write under aitasks/metadata"
completely. `diffviewer/plan_browser.py` builds its path as
``os.path.join("aitasks", "metadata", ...)``, which a `"aitasks/metadata"`
literal scan misses outright -- so a discovery-only test would pass while the
inventory silently shrank, which is exactly the vacuous guard this must not be.

So the inventory is **pinned data**, and discovery is only a tripwire for things
appearing outside it. Four independent assertions, each able to fail:

1. `test_every_pinned_site_still_exists` -- a pinned writer that was renamed,
   moved or deleted FAILS. This is what stops the inventory shrinking silently.
2. `test_wired_sites_still_reference_a_commit_seam` -- removing the commit from
   a writer FAILS.
3. `test_known_uncommitted_entries_carry_a_reason` -- an exemption without a
   stated reason FAILS, so "we deliberately do not commit this" stays an
   executable statement rather than folklore.
4. `test_no_unclassified_file_writes_metadata` -- a NEW file that writes under
   `aitasks/metadata` FAILS until it is classified. Plus
   `test_discovery_still_finds_the_files_it_should`, which fails if the
   discovery patterns rot -- without it, (4) could pass by finding nothing.

**Not caught:** a novel write primitive added inside an *already pinned* file.
That residue is covered by review, and by the rule stated in
`aidocs/framework/tui_conventions.md`. Adding a new write primitive means
updating `_PY_WRITE` / `_SH_WRITE` **and** the pins in the same change.

Run: python3 tests/test_metadata_writer_inventory.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"

# --- Write constructs --------------------------------------------------------
_PY_WRITE = re.compile(
    r'open\([^)]*["\']w["\']|\.write_text\(|json\.dump\(|yaml\.(safe_)?dump\('
    r'|os\.replace\(|atomic_write|save_project_config\(|save_yaml_config\('
    r'|save_local_config\(|_save_json\(|import_all_configs\(|\.unlink\(')
_SH_WRITE = re.compile(r'^\s*(cp|mv|touch)\s|>\s*"\$|>>\s*"\$|sed_inplace|ait_atomic_')

# A file "targets metadata" when it names a path under aitasks/metadata. Kept
# deliberately generous in spelling — the pins, not this, are the safety net.
_TARGETS_METADATA = re.compile(
    r'["\']aitasks/metadata|metadata_dir\(\)|/metadata/|"metadata"\s*/'
    r'|"aitasks",\s*"metadata"|metadata\s*/\s*"')


# --- THE INVENTORY -----------------------------------------------------------
# `file::function` identity, never a line number: line numbers drift on every
# unrelated edit, and a pin that drifts is a pin nobody trusts.
#
# `<module>` means the write is at top level in a shell script.

#: site -> the EXACT seam token that must still appear in that site's file.
#:
#: The check is file-scoped, not body-scoped, because a writer and its committer
#: are legitimately different functions: `aitask_pick_own.sh::store_email`
#: appends to emails.txt and sets a flag, and `commit_and_push` does the commit.
#: Naming the exact token is what keeps file scope meaningful — deleting the
#: seam from the file fails, even though "some seam somewhere" would not.
WIRED: dict[str, str] = {
    # Settings TUI — ConfigManager.save_* / delete_* / import
    ".aitask-scripts/settings/settings_app.py::save_codeagent": "self._commit(",
    ".aitask-scripts/settings/settings_app.py::save_board": "self._commit(",
    ".aitask-scripts/settings/settings_app.py::save_project_settings": "self._commit(",
    ".aitask-scripts/settings/settings_app.py::save_profile": "self._commit(",
    ".aitask-scripts/settings/settings_app.py::delete_profile": "self._commit(",
    ".aitask-scripts/settings/settings_app.py::_handle_import": "_commit_imported(",
    # Board TUI — column CRUD
    ".aitask-scripts/board/aitask_board.py::save_metadata": "_commit_metadata_file(",
    # Headless column CLI (the commit lives at top level, after the exec split)
    ".aitask-scripts/aitask_board_column.sh::<module>": "aitask_metadata_commit.sh",
    # chatlink wizard
    ".aitask-scripts/chatlink/wizard.py::_do_save": "_commit_config(",
    # ait setup's populate-missing / backfill passes
    ".aitask-scripts/aitask_setup.sh::ensure_project_config_defaults": "_note_metadata_write",
    ".aitask-scripts/aitask_setup.sh::ensure_chatlink_config": "_note_metadata_write",
    ".aitask-scripts/aitask_setup.sh::ensure_crew_runner_config": "_note_metadata_write",
    ".aitask-scripts/aitask_setup.sh::ensure_agent_config_seeds": "_note_metadata_write",
    # The contributor list, which established the file-naming-message rule
    ".aitask-scripts/aitask_pick_own.sh::store_email": "task_git_commit_scoped",
    ".aitask-scripts/aitask_create.sh::add_email_to_file": "task_git_commit_scoped",
}

KNOWN_UNCOMMITTED: dict[str, str] = {
    # Low-level writers: their CALLERS own the commit. Committing here would put
    # a git call inside an atomic-write primitive.
    ".aitask-scripts/lib/config_utils.py::save_project_config": "primitive; callers commit",
    ".aitask-scripts/lib/config_utils.py::save_yaml_config": "primitive; callers commit",
    ".aitask-scripts/lib/config_utils.py::save_local_config": "user layer, gitignored",
    ".aitask-scripts/lib/config_utils.py::_save_json": "primitive; callers commit",
    ".aitask-scripts/lib/config_utils.py::import_all_configs": "primitive; settings _handle_import commits",
    ".aitask-scripts/lib/board_columns.py::create_column": "pure lib; aitask_board_column.sh commits",
    ".aitask-scripts/chatlink/config_write.py::write_config": "pure writer; wizard._do_save commits",
    # Deliberate human review.
    ".aitask-scripts/lib/gate_registry_sync.py::sync_registry":
        "gates.yaml is review-then-commit by design (aitask_gate.sh warns)",
    # Out of scope: writes ANOTHER repo's config, which a repo-scoped seam
    # cannot safely commit into. Tracked as a t1677 follow-up.
    ".aitask-scripts/lib/cross_repo_settings.py::apply_push":
        "writes a foreign repo's config; follow-up task owns it",
    # Run inside a task that commits, and also write seed/ on the code branch.
    ".aitask-scripts/aitask_add_model.sh::cmd_add_json": "runs inside a task that commits",
    ".aitask-scripts/aitask_add_model.sh::cmd_promote_config": "runs inside a task that commits",
    ".aitask-scripts/aitask_opencode_models.sh::merge_with_existing": "runs inside a task that commits",
    # Committed by a different, existing seam.
    ".aitask-scripts/aitask_verified_update.sh::update_model_file": "verified_update_lib.sh commits",
    ".aitask-scripts/aitask_usage_update.sh::update_model_file": "verified_update_lib.sh commits",
    ".aitask-scripts/lib/task_utils.sh::add_label_to_file":
        "labels.txt is staged by its callers' _stage_labels gate (create/update)",
    # User layer only — gitignored, must never be committed.
    ".aitask-scripts/stats/stats_config.py::save": "user layer, gitignored",
    ".aitask-scripts/diffviewer/plan_browser.py::_save_history": "user layer, gitignored (t1677)",
    ".aitask-scripts/board/aitask_board.py::_write_user_layer": "user layer, gitignored",
    # Existence-only: `touch` creates an empty file and writes no content, so
    # there is nothing to attribute.
    ".aitask-scripts/aitask_update.sh::ensure_task_types_file": "touch only, no content",
    ".aitask-scripts/aitask_create.sh::ensure_task_types_file": "touch only, no content",
    ".aitask-scripts/aitask_create.sh::ensure_emails_file": "touch only, no content",
    ".aitask-scripts/lib/task_utils.sh::ensure_labels_file": "touch only, no content",
}

#: Files allowed to contain a metadata-targeting write. A file NOT here that the
#: scan flags is a new writer nobody has classified.
PINNED_FILES = frozenset(
    k.split("::", 1)[0] for k in {**WIRED, **KNOWN_UNCOMMITTED}
) | frozenset({
    # Flagged by the scan for reasons unrelated to metadata ownership — they
    # write task files, gitignores, registries or runtime state that merely sit
    # near a metadata path reference. Listed so a genuinely new file stands out.
    ".aitask-scripts/agentcrew/agentcrew_runner.py",
    ".aitask-scripts/aitask_artifact.sh",
    ".aitask-scripts/aitask_attach.sh",
    ".aitask-scripts/aitask_brainstorm_init.sh",
    ".aitask-scripts/aitask_codemap.sh",
    ".aitask-scripts/aitask_fold_mark.sh",
    ".aitask-scripts/aitask_gate_pass.sh",
    ".aitask-scripts/aitask_issue_import.sh",
    ".aitask-scripts/aitask_ls.sh",
    ".aitask-scripts/aitask_pr_import.sh",
    ".aitask-scripts/aitask_projects.sh",
    ".aitask-scripts/aitask_resource_admission.sh",
    ".aitask-scripts/aitask_skillrun.sh",
    ".aitask-scripts/aitask_stats_legacy.sh",
    ".aitask-scripts/aitask_sync.sh",
    ".aitask-scripts/aitask_web_merge.sh",
    ".aitask-scripts/applink/sessions.py",
    ".aitask-scripts/brainstorm/brainstorm_crew.py",
    ".aitask-scripts/chatlink/paths.py",
    ".aitask-scripts/chatlink/sessions_store.py",
    ".aitask-scripts/lib/agent_command_screen.py",
    ".aitask-scripts/lib/artifact_backends/dir.sh",
    ".aitask-scripts/lib/gate_verifier_lib.sh",
    ".aitask-scripts/lib/userconfig_persist.py",
})


# --- Source helpers ----------------------------------------------------------

def _iter_sources():
    for p in sorted(SCRIPTS.rglob("*")):
        if p.is_file() and p.suffix in (".py", ".sh"):
            yield p


def _rel(p: Path) -> str:
    return p.relative_to(REPO_ROOT).as_posix()


def _function_bodies(path: Path) -> dict[str, list[str]]:
    """Map function name -> its lines. `<module>` collects top-level lines."""
    is_py = path.suffix == ".py"
    head = (re.compile(r"\s*def\s+(\w+)") if is_py
            else re.compile(r"\s*(?:function\s+)?([A-Za-z_][\w:-]*)\s*\(\)\s*\{"))
    bodies: dict[str, list[str]] = {"<module>": []}
    cur = "<module>"
    for line in path.read_text(errors="replace").splitlines():
        m = head.match(line)
        if m:
            cur = m.group(1)
            bodies.setdefault(cur, [])
            continue
        bodies.setdefault(cur, []).append(line)
    return bodies


def _has_write(lines, is_py: bool) -> bool:
    pat = _PY_WRITE if is_py else _SH_WRITE
    return any(pat.search(ln) for ln in lines if not ln.lstrip().startswith("#"))


def _files_that_write_metadata() -> set[str]:
    found = set()
    for p in _iter_sources():
        text = p.read_text(errors="replace")
        if not _TARGETS_METADATA.search(text):
            continue
        if _has_write(text.splitlines(), p.suffix == ".py"):
            found.add(_rel(p))
    return found


class InventoryIntegrity(unittest.TestCase):
    """The pins must describe real code, or the inventory has silently rotted."""

    def test_every_pinned_site_still_exists(self):
        missing = []
        for site in {**WIRED, **KNOWN_UNCOMMITTED}:
            rel, func = site.split("::", 1)
            path = REPO_ROOT / rel
            if not path.is_file():
                missing.append(f"{site} (file is gone)")
                continue
            bodies = _function_bodies(path)
            if func not in bodies:
                missing.append(f"{site} (function is gone or renamed)")
        self.assertEqual(missing, [], (
            "Pinned metadata writers no longer exist. A writer that was renamed "
            "or moved must be RE-PINNED, not dropped — dropping it is how the "
            "inventory shrinks without anyone noticing:\n  "
            + "\n  ".join(missing)))

    def test_wired_sites_still_reference_a_commit_seam(self):
        broken = []
        for site, seam in WIRED.items():
            rel, func = site.split("::", 1)
            path = REPO_ROOT / rel
            if not path.is_file():
                continue  # reported by the pin test
            if seam not in path.read_text(errors="replace"):
                broken.append(f"{site} (seam '{seam}' is gone)")
        self.assertEqual(broken, [], (
            "These writers no longer commit what they write. A tracked file "
            "under aitasks/metadata with no committer is an ownerless dirty "
            "file that blocks task-data sync:\n  " + "\n  ".join(broken)))

    def test_known_uncommitted_entries_carry_a_reason(self):
        blank = [s for s, why in KNOWN_UNCOMMITTED.items() if not why.strip()]
        self.assertEqual(blank, [], (
            "An exemption without a stated reason is folklore. Say why this "
            "writer deliberately does not commit:\n  " + "\n  ".join(blank)))

    def test_wired_and_exempt_sets_are_disjoint(self):
        both = set(WIRED) & set(KNOWN_UNCOMMITTED)
        self.assertEqual(both, set(),
                         f"a site cannot be both wired and exempt: {sorted(both)}")


class NewWriterTripwire(unittest.TestCase):

    def test_discovery_still_finds_the_files_it_should(self):
        """Anti-vacuity: without this, the tripwire could pass by finding nothing.

        Fails if the write/target patterns rot — which is the failure mode that
        would otherwise make `test_no_unclassified_file_writes_metadata` pass
        silently while the scan sees an empty world.
        """
        found = _files_that_write_metadata()
        must_find = {
            ".aitask-scripts/settings/settings_app.py",
            ".aitask-scripts/board/aitask_board.py",
            ".aitask-scripts/lib/config_utils.py",
            ".aitask-scripts/aitask_setup.sh",
        }
        self.assertTrue(must_find <= found, (
            "the discovery patterns no longer find known metadata writers — "
            f"missing {sorted(must_find - found)}. Fix _PY_WRITE / _SH_WRITE / "
            "_TARGETS_METADATA; do not weaken the assertion."))
        self.assertGreaterEqual(len(found), len(must_find))

    def test_no_unclassified_file_writes_metadata(self):
        unclassified = sorted(_files_that_write_metadata() - PINNED_FILES)
        self.assertEqual(unclassified, [], (
            "These files write under aitasks/metadata but are not classified. "
            "Add each to WIRED (it commits through the seam) or to "
            "KNOWN_UNCOMMITTED / PINNED_FILES with a reason — see "
            "aidocs/framework/tui_conventions.md:\n  " + "\n  ".join(unclassified)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
