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
#   - chatlink/wizard_draft.py (t1190) — resumable wizard draft: atomic
#     token-free persistence (the amended contract: config/token still
#     summary-only; drafts go to the gitignored sessions dir),
#     fail-closed load validation, lifecycle, fingerprint, and the
#     SessionsStore.list_ids() draft exclusion.
#   - Import guard: none of the modules pulls in textual.
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

# --- import guard: the helper modules stay Textual-free --------------------
import chatlink.config_write as config_write  # noqa: E402
import chatlink.preflight_render as preflight_render  # noqa: E402
import chatlink.wizard_draft as wizard_draft  # noqa: E402
assert "textual" not in sys.modules, \
    "FAIL: config_write/preflight_render/wizard_draft must not load textual"
print("ok - config_write + preflight_render + wizard_draft import "
      "without textual")

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
# (config_write's own tmp discipline; wizard drafts live in the sessions
# dir and are covered by the t1190 section below)
stray = [p for p in cfg1.parent.iterdir() if p.suffix == ".tmp"]
check("no stray tmp files left behind", stray == [])

# ======================================================================== #
# t1190 — wizard_draft: token-free resumable draft
# ======================================================================== #
import json  # noqa: E402
import stat  # noqa: E402

draft_dir = tmp / "sessions"
dpath = draft_dir / wizard_draft.DRAFT_FILENAME

full_state = {
    "provider": "discord", "workspace_id": "111",
    "conversation_id": "222", "thread_id": "",
    "allowed_user_ids": ["1", "2"], "allowed_role_ids": [],
    "denied_user_ids": [], "denied_role_ids": ["9"],
    "user_authorization_mode": "allowlist",
    "role_authorization_mode": "denylist",
    "deny_message_mode": "ignore", "repo_name": "myrepo",
    "max_concurrent_sandboxes": 2, "intake_rate_per_user_per_hour": 3,
    "sandbox_memory": "2g", "sandbox_cpus": 2, "sandbox_pids": 256,
    "sandbox_wall_clock_s": 3600,
    # secrets / transients that must NEVER reach the draft file:
    "token": "sekrit-token-xyz",
    "_fetched": {"key": "x"},
}
wizard_draft.save_draft("Discord bot token", full_state, "f" * 64,
                        path=dpath)
raw = dpath.read_text(encoding="utf-8")
check("draft file written", dpath.exists())
check("token value provably absent from the draft", "sekrit-token-xyz" not in raw)
check("transient _fetched absent from the draft", "_fetched" not in raw)
check("draft mode 0600",
      stat.S_IMODE(dpath.stat().st_mode) == 0o600)
check("no tmp left beside the draft",
      [p for p in draft_dir.iterdir() if p.suffix == ".tmp"] == [])

loaded = wizard_draft.load_draft(path=dpath)
check("draft round-trips", loaded is not None)
check("round-trip step_name", loaded["step_name"] == "Discord bot token")
check("round-trip fingerprint", loaded["config_fingerprint"] == "f" * 64)
check("token_entered metadata recorded (never the value)",
      loaded["token_entered"] is True)
check("round-trip all allowlisted keys",
      set(loaded["state"]) == set(wizard_draft.DRAFT_STATE_KEYS)
      and loaded["state"]["allowed_user_ids"] == ["1", "2"]
      and loaded["state"]["sandbox_wall_clock_s"] == 3600)
check("token key absent from loaded state", "token" not in loaded["state"])

# unknown keys in a stored draft are dropped on load
payload = json.loads(raw)
payload["state"]["future_unknown"] = "x"
dpath.write_text(json.dumps(payload), encoding="utf-8")
loaded = wizard_draft.load_draft(path=dpath)
check("unknown state keys dropped on load",
      loaded is not None and "future_unknown" not in loaded["state"])

# a key absent from the draft is fine (falls back to initial_state)
payload = json.loads(raw)
del payload["state"]["repo_name"]
dpath.write_text(json.dumps(payload), encoding="utf-8")
loaded = wizard_draft.load_draft(path=dpath)
check("absent key still loads",
      loaded is not None and "repo_name" not in loaded["state"])

# --- fail-closed value validation: reject the WHOLE draft ------------------
def tampered(key, val):
    p = json.loads(raw)
    p["state"][key] = val
    dpath.write_text(json.dumps(p), encoding="utf-8")
    return wizard_draft.load_draft(path=dpath)

check("string where id-list expected rejects draft",
      tampered("allowed_user_ids", "not-a-list") is None)
check("bogus authorization mode rejects draft",
      tampered("user_authorization_mode", "bogus") is None)
check("out-of-range sandbox_cpus rejects draft",
      tampered("sandbox_cpus", 999) is None)
check("invalid sandbox_memory rejects draft",
      tampered("sandbox_memory", "lots") is None)

# --- envelope validation ---------------------------------------------------
check("missing file loads as None",
      wizard_draft.load_draft(path=draft_dir / "nope.json") is None)
dpath.write_text("{nope", encoding="utf-8")
check("corrupt JSON loads as None",
      wizard_draft.load_draft(path=dpath) is None)
payload = json.loads(raw)
payload["version"] = 999
dpath.write_text(json.dumps(payload), encoding="utf-8")
check("wrong version loads as None",
      wizard_draft.load_draft(path=dpath) is None)

# --- lifecycle -------------------------------------------------------------
dpath.write_text(raw, encoding="utf-8")
wizard_draft.clear_draft(path=dpath)
wizard_draft.clear_draft(path=dpath)  # idempotent
check("clear_draft idempotent and file gone", not dpath.exists())

# --- config_fingerprint ----------------------------------------------------
check("fingerprint None for missing path",
      wizard_draft.config_fingerprint(tmp / "no-such.yaml") is None)
fp_file = tmp / "fp.yaml"
fp_file.write_text("a: 1\n", encoding="utf-8")
fp1 = wizard_draft.config_fingerprint(fp_file)
fp_file.write_text("a: 2\n", encoding="utf-8")
fp2 = wizard_draft.config_fingerprint(fp_file)
check("fingerprint stable type and changes with content",
      isinstance(fp1, str) and len(fp1) == 64 and fp1 != fp2)

# --- SessionsStore.list_ids() excludes the draft ---------------------------
# The TUI roots its store at the sessions dir where the draft lives; a
# regression in the exclusion would render a bogus session row even
# though every round-trip test above still passes.
from chatlink.sessions_store import SessionRecord, SessionsStore  # noqa: E402
store_root = tmp / "store_root"
store = SessionsStore(store_root)
store.save(SessionRecord(session_id="s1", initiator_id="u1",
                         state="spawning", thread={"provider": "discord"}))
wizard_draft.save_draft("Summary & save", full_state, None,
                        path=store_root / wizard_draft.DRAFT_FILENAME)
check("list_ids excludes the wizard draft file",
      store.list_ids() == ["s1"])

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

# ======================================================================== #
# t1186_2 — allowlist_fetch: member/role picker data source
# ======================================================================== #
import chatlink.allowlist_fetch as allowlist_fetch  # noqa: E402
assert "textual" not in sys.modules, \
    "FAIL: allowlist_fetch must not load textual"
assert "discord" not in sys.modules, \
    "FAIL: allowlist_fetch must not load the discord SDK"
print("ok - allowlist_fetch imports without textual and without discord")


def fake_user(uid, name, bot=False):
    return SimpleNamespace(id=uid, display_name=name, is_bot=bot)


class FakeAllowAdapter:
    def __init__(self, members=None, roles=None, members_exc=None,
                 roles_exc=None, members_slow=0.0):
        self.closed = 0
        self.members = list(members or [])
        self.roles = list(roles or [])
        self.members_exc = members_exc
        self.roles_exc = roles_exc
        self.members_slow = members_slow
        self.member_refs = []
        self.role_refs = []

    async def fetch_channel_members(self, ref):
        self.member_refs.append(ref)
        if self.members_slow:
            await asyncio.sleep(self.members_slow)
        if self.members_exc:
            raise self.members_exc
        return list(self.members)

    async def fetch_roles(self, ref):
        self.role_refs.append(ref)
        if self.roles_exc:
            raise self.roles_exc
        return list(self.roles)

    async def close(self):
        self.closed += 1


def af_run(adapter=None, exc=None, slow=0.0, thread_id=None, timeout=5.0):
    return allowlist_fetch.run_allowlist_fetch(
        TOKEN, "100", "200", thread_id, timeout=timeout,
        connector=connector_for(adapter, exc, slow))


def af_hygiene(res):
    return all(TOKEN not in (s or "")
               for s in (res.members_error, res.roles_error))


TWO_ROLES = [SimpleNamespace(id="31", name="mods"),
             SimpleNamespace(id="32", name="devs")]

# all-pass: shape + ordering preserved, bots filtered
ok_af = FakeAllowAdapter(
    members=[fake_user("1", "alice"), fake_user("2", "botty", bot=True),
             fake_user("3", "carol")],
    roles=TWO_ROLES)
res = af_run(ok_af)
check("allowlist: members are ordered (id, display_name) pairs",
      res.members == [("1", "alice"), ("3", "carol")])
check("allowlist: bot members are filtered out",
      all(i != "2" for i, _ in res.members))
check("allowlist: roles are ordered (id, name) pairs",
      res.roles == [("31", "mods"), ("32", "devs")])
check("allowlist: all-pass has no stage errors and no truncation",
      res.members_error is None and res.roles_error is None
      and res.members_truncated is False)
check("allowlist: teardown close called on the success path",
      ok_af.closed == 1)

# truncation at the cap (bots dropped before the cap applies)
big = [fake_user(str(i), f"u{i}") for i in range(allowlist_fetch.MAX_MEMBERS + 7)]
res = af_run(FakeAllowAdapter(members=big, roles=TWO_ROLES))
check("allowlist: member list truncated at MAX_MEMBERS",
      len(res.members) == allowlist_fetch.MAX_MEMBERS
      and res.members_truncated is True)
res = af_run(FakeAllowAdapter(
    members=[fake_user(str(i), f"u{i}") for i in range(allowlist_fetch.MAX_MEMBERS)],
    roles=TWO_ROLES))
check("allowlist: exactly-at-cap list is not marked truncated",
      len(res.members) == allowlist_fetch.MAX_MEMBERS
      and res.members_truncated is False)

# per-stage isolation: members fail, roles still delivered
iso1 = FakeAllowAdapter(members_exc=BoomError("no members " + TOKEN),
                        roles=TWO_ROLES)
res = af_run(iso1)
check("allowlist: members failure is isolated — roles still fetched",
      res.members == [] and "BoomError" in res.members_error
      and res.roles == [("31", "mods"), ("32", "devs")]
      and res.roles_error is None)
check("allowlist: members error carries class name only (hygiene)",
      af_hygiene(res))
check("allowlist: teardown close called on the members-failure path",
      iso1.closed == 1)

# per-stage isolation: roles fail, members still delivered
res = af_run(FakeAllowAdapter(members=[fake_user("1", "alice")],
                              roles_exc=BoomError("no roles " + TOKEN)))
check("allowlist: roles failure is isolated — members still fetched",
      res.members == [("1", "alice")] and res.roles == []
      and "BoomError" in res.roles_error and res.members_error is None
      and af_hygiene(res))

# connection failure → both stages errored, sanitized
res = af_run(exc=LoginFailure("401 " + TOKEN))
check("allowlist: rejected token errors both stages without leaking",
      res.members_error == "token rejected by Discord"
      and res.roles_error == "token rejected by Discord"
      and res.members == [] and res.roles == [] and af_hygiene(res))
res = af_run(exc=BoomError("kaboom " + TOKEN))
check("allowlist: unexpected connect error carries class name only",
      "BoomError" in res.members_error and "BoomError" in res.roles_error
      and af_hygiene(res))

# connect timeout → bounded, both stages errored, nothing to close
res = af_run(slow=30.0, timeout=0.2)
check("allowlist: connect timeout errors both stages",
      "timed out" in res.members_error and "timed out" in res.roles_error)

# stage timeout → members timed out, roles still attempted, teardown runs
slow_af = FakeAllowAdapter(members_slow=30.0, roles=TWO_ROLES)
res = af_run(slow_af, timeout=0.2)
check("allowlist: member-stage timeout is isolated",
      "timed out" in res.members_error
      and res.roles == [("31", "mods"), ("32", "devs")])
check("allowlist: teardown close called on the timeout path",
      slow_af.closed == 1)

# thread scoping: BOTH stages target the parent conversation ref
th_af = FakeAllowAdapter(members=[fake_user("1", "alice")], roles=TWO_ROLES)
af_run(th_af, thread_id="777")
check("allowlist: member fetch targets the PARENT channel ref",
      th_af.member_refs[0].thread_id is None
      and th_af.member_refs[0].conversation_id == "200")
check("allowlist: role fetch targets the PARENT channel ref",
      th_af.role_refs[0].thread_id is None
      and th_af.role_refs[0].conversation_id == "200")

# --- validation helpers ----------------------------------------------------
check("allowlist: dedupe_ids preserves first-seen order",
      allowlist_fetch.dedupe_ids(["2", "1", "2", "3", "1"]) == ["2", "1", "3"])
check("allowlist: dedupe_ids on empty input", allowlist_fetch.dedupe_ids([]) == [])
check("allowlist: invalid_snowflakes flags non-snowflake shapes",
      allowlist_fetch.invalid_snowflakes(
          ["123456789012345678", "12345", "abc", "1" * 22, ""])
      == ["12345", "abc", "1" * 22, ""])
check("allowlist: invalid_snowflakes accepts 15- and 21-digit bounds",
      allowlist_fetch.invalid_snowflakes(["1" * 15, "1" * 21]) == [])

print(f"\nPASS: {PASS}, FAIL: 0")
PYEOF

echo
echo "PASS: test_chatlink_wizard.sh"
