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

# ======================================================================== #
# t1149_5 — live_check: fake-connector rows, teardown, hygiene
# ======================================================================== #
import asyncio  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import chatlink.live_check as live_check  # noqa: E402
assert "textual" not in sys.modules, \
    "FAIL: live_check must not load textual"
assert "discord" not in sys.modules, \
    "FAIL: live_check must not load the discord SDK"
print("ok - live_check imports without textual and without discord")

TOKEN = "tok-SECRET-12345"
IDS = ("live_login", "live_intents", "live_channel_visible",
       "live_permissions")
ALL_PERMS = (live_check.REQUIRED_BOT_PERMISSIONS
             + live_check.OPTIONAL_BOT_PERMISSIONS)


class LoginFailure(Exception): pass
class PrivilegedIntentsRequired(Exception): pass
class ConversationNotFound(Exception): pass
class UserNotFound(Exception): pass


class FakeAdapter:
    def __init__(self, conv_exc=None, perms=None, perm_exc=None,
                 dm=False, conv_slow=0.0, self_id="1234567890"):
        self.closed = 0
        self.self_id = self_id
        self.conv_exc = conv_exc
        self.perms = dict(perms or {})
        self.perm_exc = perm_exc
        self.dm = dm
        self.conv_slow = conv_slow
        self.visibility_refs = []
        self.perm_calls = []

    async def fetch_conversation(self, ref):
        self.visibility_refs.append(ref)
        if self.conv_slow:
            await asyncio.sleep(self.conv_slow)
        if self.conv_exc:
            raise self.conv_exc
        return SimpleNamespace()

    async def fetch_bot_permissions(self, ref, names):
        self.perm_calls.append((ref, tuple(names)))
        if self.perm_exc:
            raise self.perm_exc
        if self.dm:
            return {}
        return {n: bool(self.perms.get(n)) for n in names}

    async def close(self):
        self.closed += 1


def connector_for(adapter=None, exc=None, slow=0.0):
    async def connect(token):
        assert token == TOKEN, "connector must receive the entered token"
        if slow:
            await asyncio.sleep(slow)
        if exc:
            raise exc
        return adapter
    return connect


def run(adapter=None, exc=None, slow=0.0, thread_id=None, timeout=5.0):
    return live_check.run_live_checks(
        TOKEN, "100", "200", thread_id, timeout=timeout,
        connector=connector_for(adapter, exc, slow))


def hygiene(rows):
    return all(TOKEN not in (res.message + res.fix_hint) for res in rows)


# all-pass path
ok_adapter = FakeAdapter(perms={n: True for n in ALL_PERMS})
rows = run(ok_adapter)
check("live: all-pass run returns the four rows in order",
      tuple(r.id for r in rows) == IDS)
check("live: all-pass run all severities pass",
      all(r.severity == "pass" for r in rows))
check("live: teardown close called on the success path",
      ok_adapter.closed == 1)
check("live: rows carry the transport category",
      all(r.category == "transport" for r in rows))
check("live: token never appears in any row (success)", hygiene(rows))

# login failure → distinct row, rest not-checked warns
rows = run(exc=LoginFailure("401 " + TOKEN))
check("live: login failure row", rows[0].id == "live_login"
      and rows[0].severity == "fail"
      and "token rejected" in rows[0].message)
check("live: login failure fills not-checked warns",
      tuple(r.id for r in rows) == IDS
      and all(r.severity == "warn" and "not checked" in r.message
              for r in rows[1:]))
check("live: token never appears in any row (login failure w/ token in exc)",
      hygiene(rows))

# privileged intents failure → login pass + intents fail
rows = run(exc=PrivilegedIntentsRequired("intents"))
check("live: intents failure row",
      rows[0].severity == "pass" and rows[1].id == "live_intents"
      and rows[1].severity == "fail"
      and "privileged intents" in rows[1].message)
check("live: intents fix hint names both intents",
      "Message Content" in rows[1].fix_hint
      and "Server Members" in rows[1].fix_hint)

# unexpected connector error → sanitized class-name-only message
class BoomError(Exception): pass
rows = run(exc=BoomError("kaboom with " + TOKEN))
check("live: unexpected error row carries class name only",
      rows[0].severity == "fail" and "BoomError" in rows[0].message
      and hygiene(rows))

# channel not visible → visibility fail, teardown still runs
nf_adapter = FakeAdapter(conv_exc=ConversationNotFound("gone " + TOKEN))
rows = run(nf_adapter)
check("live: channel-not-found row",
      rows[2].id == "live_channel_visible" and rows[2].severity == "fail"
      and "not found or not visible" in rows[2].message)
check("live: perms not checked after visibility failure",
      rows[3].severity == "warn" and "not checked" in rows[3].message)
check("live: teardown close called on the failure path",
      nf_adapter.closed == 1)
check("live: token never appears in any row (visibility failure)",
      hygiene(rows))
check("live: visibility fix hint carries the concrete invite URL",
      "discord.com/oauth2/authorize" in rows[2].fix_hint
      and "client_id=1234567890" in rows[2].fix_hint)
check("live: visibility fix hint references the public docs page",
      "aitasks.io/docs/workflows/bug-report-intake" in rows[2].fix_hint
      and "aidocs/" not in rows[2].fix_hint)

# adapter without a bot user id → plain hint, no invite URL spliced
rows = run(FakeAdapter(conv_exc=ConversationNotFound("gone"), self_id=None))
check("live: no bot id falls back to the plain docs hint",
      "aitasks.io/docs/workflows/bug-report-intake" in rows[2].fix_hint
      and "oauth2/authorize" not in rows[2].fix_hint)

# non-digit bot id (hygiene negative control) → never spliced into the URL
rows = run(FakeAdapter(conv_exc=ConversationNotFound("gone"),
                       self_id="boom " + TOKEN))
check("live: non-digit bot id is never spliced into the invite URL",
      "oauth2/authorize" not in rows[2].fix_hint and hygiene(rows))

# permission gaps → fail listing missing required names
gap_perms = {n: True for n in ALL_PERMS}
gap_perms["manage_threads"] = False
gap_perms["add_reactions"] = False
gap_adapter = FakeAdapter(perms=gap_perms)
rows = run(gap_adapter)
check("live: missing required permissions row lists the names",
      rows[3].severity == "fail" and "manage_threads" in rows[3].message
      and "add_reactions" in rows[3].message)
check("live: teardown close called on the permission-gap path",
      gap_adapter.closed == 1)
check("live: permission fix hint carries the concrete invite URL",
      "discord.com/oauth2/authorize" in rows[3].fix_hint
      and "client_id=1234567890" in rows[3].fix_hint
      and "permissions=397552863296" in rows[3].fix_hint)

# only the optional permission missing → warn, not fail
opt_perms = {n: True for n in ALL_PERMS}
opt_perms["manage_messages"] = False
rows = run(FakeAdapter(perms=opt_perms))
check("live: missing optional permission is a warn",
      rows[3].severity == "warn" and "manage_messages" in rows[3].message)

# member-resolution failure surfaces distinctly
rows = run(FakeAdapter(perms={}, perm_exc=UserNotFound("who")))
check("live: bot-member resolution failure row",
      rows[3].severity == "fail"
      and "bot's own member" in rows[3].message)

# DM channel → permissions n/a pass
rows = run(FakeAdapter(dm=True))
check("live: DM channel renders permissions n/a",
      rows[3].severity == "pass" and "DM channel" in rows[3].message)

# thread scoping: visibility uses the thread ref, permissions the parent
th_adapter = FakeAdapter(perms={n: True for n in ALL_PERMS})
rows = run(th_adapter, thread_id="777")
check("live: visibility checks the configured thread ref",
      th_adapter.visibility_refs[0].thread_id == "777"
      and "(thread)" in rows[2].message)
check("live: permissions check the PARENT channel ref",
      th_adapter.perm_calls[0][0].thread_id is None
      and th_adapter.perm_calls[0][0].conversation_id == "200")

# connect timeout → bounded, login row fails, nothing to close
rows = run(slow=30.0, timeout=0.2)
check("live: connect timeout renders a timed-out login row",
      rows[0].severity == "fail" and "timed out" in rows[0].message
      and all(r.severity == "warn" for r in rows[1:]))

# post-connect stage timeout → row fails AND teardown still runs
slow_adapter = FakeAdapter(conv_slow=30.0)
rows = run(slow_adapter, timeout=0.2)
check("live: stage timeout renders a timed-out visibility row",
      rows[2].severity == "fail" and "timed out" in rows[2].message)
check("live: teardown close called on the timeout path",
      slow_adapter.closed == 1)

print(f"\nPASS: {PASS}, FAIL: 0")
PYEOF

echo
echo "PASS: test_chatlink_wizard.sh"
