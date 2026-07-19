#!/usr/bin/env bash
# test_chatlink_wizard.sh — chatlink config wizard writer tests (t1149_3).
#
# Headless (no Textual required) suite for the wizard's Textual-free
# helpers:
#   - chatlink/config_write.py — merge-never-drop writer: preservation of
#     unedited top-level keys (sandbox_env_passthrough + unknown future
#     key), one-level nested merge (intake_channel.metadata + unknown
#     subkey survive), fresh-file path (incl. absent parent dir),
#     round-trip through load_config with zero warnings, malformed-YAML
#     conflict (ConfigWriteError, file untouched), allow_replace.
#   - chatlink/preflight_render.py — shared row formatter (glyphs +
#     fix-hint shape the panel tests assert).
#   - Import guard: neither module pulls in textual.
# Run: bash tests/test_chatlink_wizard.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

# --- import guard: both helper modules stay Textual-free -------------------
import chatlink.config_write as config_write  # noqa: E402
import chatlink.preflight_render as preflight_render  # noqa: E402
assert "textual" not in sys.modules, \
    "FAIL: config_write/preflight_render must not load textual"
print("ok - config_write + preflight_render import without textual")

import yaml  # noqa: E402
from chatlink.config import load_config  # noqa: E402
from chatlink.preflight import CheckResult  # noqa: E402

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


tmp = Path(tempfile.mkdtemp(prefix="chatlink-wizard-test-"))

# --- preflight_render: same row shape the panel tests assert ---------------
check("format_row pass glyph",
      preflight_render.format_row(CheckResult(
          id="x", category="transport", severity="pass",
          message="config parses")) == "✓ config parses")
check("format_row non-pass appends fix hint",
      preflight_render.format_row(CheckResult(
          id="x", category="transport", severity="fail",
          message="bot token missing", fix_hint="write the token"))
      == "✗ bot token missing — write the token")
check("format_row warn glyph",
      preflight_render.format_row(CheckResult(
          id="x", category="runtime", severity="warn",
          message="m")).startswith("! "))

# --- merge preserves unedited top-level + unknown keys ---------------------
cfg1 = tmp / "existing.yaml"
cfg1.write_text(
    "sandbox_env_passthrough: [FOO_KEY]\n"
    "future_unknown_key:\n"
    "  nested: value\n"
    "sandbox_cpus: 4\n",
    encoding="utf-8")
config_write.write_config(cfg1, {"sandbox_pids": 1024})
data = yaml.safe_load(cfg1.read_text(encoding="utf-8"))
check("ceilings-only save preserves sandbox_env_passthrough",
      data["sandbox_env_passthrough"] == ["FOO_KEY"])
check("unknown future key survives verbatim",
      data["future_unknown_key"] == {"nested": "value"})
check("unedited key untouched", data["sandbox_cpus"] == 4)
check("edited key applied", data["sandbox_pids"] == 1024)
check("curated header written",
      cfg1.read_text(encoding="utf-8").startswith(
          "# chatlink gateway configuration"))

# --- nested merge: intake_channel.metadata + unknown subkey survive --------
cfg2 = tmp / "nested.yaml"
cfg2.write_text(
    "intake_channel:\n"
    "  provider: discord\n"
    "  workspace_id: '111'\n"
    "  conversation_id: '222'\n"
    "  metadata:\n"
    "    note: keep me\n"
    "  future_provider_field: precious\n",
    encoding="utf-8")
config_write.write_config(cfg2, {"intake_channel": {
    "provider": "discord", "workspace_id": "111",
    "conversation_id": "999", "thread_id": None}})
data = yaml.safe_load(cfg2.read_text(encoding="utf-8"))
check("intake_channel edit applied",
      data["intake_channel"]["conversation_id"] == "999")
check("intake_channel.metadata survives the edit",
      data["intake_channel"]["metadata"] == {"note": "keep me"})
check("unknown intake_channel subkey survives verbatim",
      data["intake_channel"]["future_provider_field"] == "precious")

# --- DELETE sentinel: clearing an exposed optional field -------------------
cfg_del = tmp / "clear.yaml"
cfg_del.write_text(
    "repo_name: oldrepo\n"
    "sandbox_env_passthrough: [FOO_KEY]\n"
    "intake_channel:\n"
    "  provider: discord\n"
    "  thread_id: '123'\n",
    encoding="utf-8")
config_write.write_config(cfg_del, {
    "repo_name": config_write.DELETE,
    "intake_channel": {"thread_id": config_write.DELETE},
})
data = yaml.safe_load(cfg_del.read_text(encoding="utf-8"))
check("DELETE removes a pre-existing repo_name",
      "repo_name" not in data)
check("nested DELETE removes a pre-existing subkey",
      "thread_id" not in data["intake_channel"]
      and data["intake_channel"]["provider"] == "discord")
check("DELETE of an absent key is a no-op (other keys preserved)",
      data["sandbox_env_passthrough"] == ["FOO_KEY"])
config_write.write_config(cfg_del, {"repo_name": config_write.DELETE})
check("DELETE on an already-absent key stays absent",
      "repo_name" not in yaml.safe_load(
          cfg_del.read_text(encoding="utf-8")))

# --- fresh file + absent parent directory ----------------------------------
cfg3 = tmp / "no" / "such" / "dir" / "fresh.yaml"
config_write.write_config(cfg3, {"deny_message_mode": "ephemeral"})
data = yaml.safe_load(cfg3.read_text(encoding="utf-8"))
check("fresh path with absent parent dir succeeds",
      data == {"deny_message_mode": "ephemeral"})

# --- valid wizard output round-trips with zero warnings --------------------
cfg4 = tmp / "roundtrip.yaml"
config_write.write_config(cfg4, {
    "intake_channel": {"provider": "discord", "workspace_id": "1",
                       "conversation_id": "2", "thread_id": None},
    "allowed_user_ids": ["42"],
    "allowed_role_ids": [],
    "deny_message_mode": "ignore",
    "repo_name": "myrepo",
    "max_concurrent_sandboxes": 2,
    "intake_rate_per_user_per_hour": 4,
    "sandbox_memory": "2g",
    "sandbox_cpus": 2,
    "sandbox_pids": 512,
    "sandbox_wall_clock_s": 1800,
})
import io, contextlib  # noqa: E402
buf = io.StringIO()
with contextlib.redirect_stderr(buf):
    loaded = load_config(cfg4)
check("round-trip loads with zero warnings", buf.getvalue() == "")
check("round-trip effective values",
      loaded is not None
      and loaded.intake_channel["conversation_id"] == "2"
      and loaded.allowed_user_ids == ["42"]
      and loaded.repo_name == "myrepo"
      and loaded.sandbox_memory == "2g")

# --- empty / fully-commented file merges as {} -----------------------------
cfg5 = tmp / "commented.yaml"
cfg5.write_text("# only comments here\n#sandbox_cpus: 4\n",
                encoding="utf-8")
config_write.write_config(cfg5, {"sandbox_cpus": 8})
data = yaml.safe_load(cfg5.read_text(encoding="utf-8"))
check("fully-commented file merges as fresh", data == {"sandbox_cpus": 8})

# --- malformed existing YAML: explicit conflict, file untouched ------------
cfg6 = tmp / "broken.yaml"
broken = "intake_channel: [unclosed\n"
cfg6.write_text(broken, encoding="utf-8")
try:
    config_write.write_config(cfg6, {"sandbox_cpus": 8})
    check("malformed YAML raises ConfigWriteError", False)
except config_write.ConfigWriteError:
    check("malformed YAML raises ConfigWriteError", True)
check("malformed file left untouched",
      cfg6.read_text(encoding="utf-8") == broken)

# non-mapping top level is the same conflict
cfg7 = tmp / "scalar.yaml"
cfg7.write_text("- just\n- a list\n", encoding="utf-8")
try:
    config_write.write_config(cfg7, {"sandbox_cpus": 8})
    check("non-mapping top level raises ConfigWriteError", False)
except config_write.ConfigWriteError:
    check("non-mapping top level raises ConfigWriteError", True)

# --- allow_replace=True replaces the unmergeable file ----------------------
config_write.write_config(cfg6, {"sandbox_cpus": 8}, allow_replace=True)
data = yaml.safe_load(cfg6.read_text(encoding="utf-8"))
check("allow_replace replaces malformed file", data == {"sandbox_cpus": 8})

# --- no stray tmp files left beside the config -----------------------------
stray = [p for p in cfg1.parent.iterdir() if p.suffix == ".tmp"]
check("no stray tmp files left behind", stray == [])

print(f"\nPASS: {PASS}, FAIL: 0")
PYEOF

echo
echo "PASS: test_chatlink_wizard.sh"
