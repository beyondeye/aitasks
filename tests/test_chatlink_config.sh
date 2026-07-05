#!/usr/bin/env bash
# test_chatlink_config.sh — chatlink config + authorization layer tests (t1120_2).
#
# Covers the t1120_2 verification list: config load/clamp/fail-closed
# (missing file, malformed YAML, per-key independent degradation,
# intake_channel normalization incl. the metadata-scalar guard), policy
# deny-by-default negative controls (one per distinct reason) + positives,
# paths permission enforcement (dir 0700 / token 0600), cwd-independent
# absolute config resolution, the guarded config_utils import bootstrap,
# and the secrets-hygiene git check-ignore rule.
# Run: bash tests/test_chatlink_config.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

PASS_COUNT=0
FAIL_COUNT=0

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - $label"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - $label: expected '$expected', got '$actual'"
    fi
}

assert_contains() {
    local label="$1" haystack="$2" needle="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - $label"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - $label: '$needle' not found in output"
    fi
}

# ---------------------------------------------------------------------------
# Part 1: Python unit tests (config.py + policy.py + paths.py)
# ---------------------------------------------------------------------------

if "$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import io
import contextlib
import stat
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
scripts_dir = root / ".aitask-scripts"
for extra in (scripts_dir, scripts_dir / "lib"):
    sys.path.insert(0, str(extra))

from chatlink import config as cfg_mod
from chatlink import paths as paths_mod
from chatlink.config import ChatlinkConfig, load_config
from chatlink.policy import Decision, decide, may_answer
from chat.model import IdentityClaims, Role, ConversationRef

PASS = 0
FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"ok - {label}")
    else:
        FAIL += 1
        print(f"FAIL - {label}")


def load_yaml_text(tmp, text):
    """Write text to a temp yaml file and load_config it, capturing warnings."""
    p = Path(tmp) / "chatlink_config.yaml"
    p.write_text(text, encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        conf = load_config(p)
    return conf, err.getvalue()


with tempfile.TemporaryDirectory() as tmp:
    # --- fail-closed loads -------------------------------------------------
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        check("config: None path => None (fail-closed)", load_config(None) is None)
        check("config: missing file => None (fail-closed)",
              load_config(Path(tmp) / "nope.yaml") is None)
    conf, w = load_yaml_text(tmp, "foo: [unclosed\n  bad::: yaml{")
    check("config: malformed YAML => None (fail-closed)", conf is None)
    conf, w = load_yaml_text(tmp, "- just\n- a\n- list\n")
    check("config: non-mapping top level => None (fail-closed)", conf is None)

    # empty file => valid config with defaults (present-but-empty is a
    # configured-nothing state, not a missing file)
    conf, w = load_yaml_text(tmp, "")
    check("config: empty file => defaults", isinstance(conf, ChatlinkConfig))
    check("config: default ceilings", conf.max_concurrent_sandboxes == 2
          and conf.intake_rate_per_user_per_hour == 4
          and conf.sandbox_memory == "2g" and conf.sandbox_cpus == 2
          and conf.sandbox_pids == 512 and conf.sandbox_wall_clock_s == 1800)
    check("config: default deny_message_mode ignore",
          conf.deny_message_mode == "ignore")
    check("config: default empty allowlists (deny-by-default posture)",
          conf.allowed_user_ids == [] and conf.allowed_role_ids == [])

    # --- valid full load ----------------------------------------------------
    conf, w = load_yaml_text(tmp, """
intake_channel:
  provider: discord
  workspace_id: "g1"
  conversation_id: "c1"
  thread_id: null
  metadata: {}
allowed_user_ids: ["u1", 42]
allowed_role_ids: ["r1"]
deny_message_mode: ephemeral
repo_name: myproj
max_concurrent_sandboxes: 4
intake_rate_per_user_per_hour: 10
sandbox_memory: 512m
sandbox_cpus: 8
sandbox_pids: 1024
sandbox_wall_clock_s: 600
""")
    check("config: valid load intake_channel", conf.intake_channel == {
        "provider": "discord", "workspace_id": "g1",
        "conversation_id": "c1", "thread_id": None, "metadata": {}})
    check("config: int user id coerced to str", conf.allowed_user_ids == ["u1", "42"])
    check("config: valid ceilings kept", conf.max_concurrent_sandboxes == 4
          and conf.intake_rate_per_user_per_hour == 10
          and conf.sandbox_memory == "512m" and conf.sandbox_cpus == 8
          and conf.sandbox_pids == 1024 and conf.sandbox_wall_clock_s == 600)
    check("config: deny_message_mode ephemeral kept",
          conf.deny_message_mode == "ephemeral")
    check("config: repo_name kept", conf.repo_name == "myproj")

    # --- per-key independent degradation ------------------------------------
    conf, w = load_yaml_text(tmp, """
allowed_user_ids: ["u1"]
max_concurrent_sandboxes: banana
intake_rate_per_user_per_hour: -3
sandbox_cpus: 999
sandbox_memory: "lots"
sandbox_pids: true
deny_message_mode: shout
repo_name: 42
""")
    check("config: bad keys still load rest", conf.allowed_user_ids == ["u1"])
    check("config: non-int ceiling => default", conf.max_concurrent_sandboxes == 2)
    check("config: negative ceiling => clamped low",
          conf.intake_rate_per_user_per_hour == 1)
    check("config: over-max ceiling => clamped high", conf.sandbox_cpus == 16)
    check("config: bad sandbox_memory => default", conf.sandbox_memory == "2g")
    check("config: bool ceiling => default (typo guard)", conf.sandbox_pids == 512)
    check("config: unknown deny_message_mode => ignore",
          conf.deny_message_mode == "ignore")
    check("config: non-string repo_name => None", conf.repo_name is None)
    check("config: degradations warn on stderr",
          "max_concurrent_sandboxes" in w and "sandbox_memory" in w
          and "deny_message_mode" in w)

    # --- intake_channel normalization ---------------------------------------
    conf, w = load_yaml_text(tmp, """
intake_channel:
  provider: discord
  workspace_id: "g1"
  conversation_id: ""
""")
    check("config: empty required intake key => intake None, rest loads",
          conf is not None and conf.intake_channel is None)

    conf, w = load_yaml_text(tmp, "intake_channel: just-a-string\n")
    check("config: scalar intake_channel => None", conf.intake_channel is None)

    conf, w = load_yaml_text(tmp, """
intake_channel:
  provider: discord
  workspace_id: "g1"
  conversation_id: "c1"
  thread_id: 123
  metadata: not-a-dict
  bogus_extra: zap
""")
    check("config: non-string thread_id => None",
          conf.intake_channel["thread_id"] is None)
    check("config: scalar metadata => {} (from_dict crash guard)",
          conf.intake_channel["metadata"] == {})
    check("config: unknown intake keys dropped",
          "bogus_extra" not in conf.intake_channel)
    check("config: metadata/extra-key normalization warns",
          "metadata" in w and "bogus_extra" in w)
    # round-trip positive control: the normalized dict must feed
    # ConversationRef.from_dict without raising (independent ground truth)
    ref = ConversationRef.from_dict(conf.intake_channel)
    check("config: normalized intake feeds ConversationRef.from_dict",
          ref.provider == "discord" and ref.workspace_id == "g1"
          and ref.conversation_id == "c1" and ref.thread_id is None
          and ref.metadata == {})

    # list metadata is also non-dict => {}
    conf, w = load_yaml_text(tmp, """
intake_channel:
  provider: discord
  workspace_id: "g1"
  conversation_id: "c1"
  metadata: [1, 2]
""")
    check("config: list metadata => {}", conf.intake_channel["metadata"] == {})

    # --- allowlist shape degradation ----------------------------------------
    conf, w = load_yaml_text(tmp, """
allowed_user_ids: not-a-list
allowed_role_ids: ["r1", {bad: entry}, "", "r2"]
""")
    check("config: non-list allowlist => []", conf.allowed_user_ids == [])
    check("config: non-scalar/empty entries dropped",
          conf.allowed_role_ids == ["r1", "r2"])

# --- policy: deny-by-default, one control per reason -------------------------
GOOD_CONF = ChatlinkConfig(allowed_user_ids=["u1"], allowed_role_ids=["r9"])
member = IdentityClaims(user_id="u1", is_channel_member=True)

check("policy: no config => no_config",
      decide(member, None) == Decision(False, "no_config"))
check("policy: no claims => no_claims",
      decide(None, GOOD_CONF) == Decision(False, "no_claims"))
check("policy: empty user_id => no_claims",
      decide(IdentityClaims(user_id=""), GOOD_CONF) == Decision(False, "no_claims"))
check("policy: non-channel-member => not_channel_member",
      decide(IdentityClaims(user_id="u1", is_channel_member=False), GOOD_CONF)
      == Decision(False, "not_channel_member"))
check("policy: allowed user => ok_user",
      decide(member, GOOD_CONF) == Decision(True, "ok_user"))

role_claims = IdentityClaims(
    user_id="u2", is_channel_member=True,
    roles=[Role(id="r9", name="triager", kind="discord_role")])
check("policy: allowed role => ok_role",
      decide(role_claims, GOOD_CONF) == Decision(True, "ok_role"))

mismatch_claims = IdentityClaims(
    user_id="u2", is_channel_member=True,
    roles=[Role(id="r7", name="lurker", kind="discord_role")])
check("policy: role mismatch => role_not_allowed",
      decide(mismatch_claims, GOOD_CONF) == Decision(False, "role_not_allowed"))

users_only = ChatlinkConfig(allowed_user_ids=["u1"])
check("policy: unknown user (no roles configured) => user_not_allowed",
      decide(IdentityClaims(user_id="u2", is_channel_member=True), users_only)
      == Decision(False, "user_not_allowed"))
empty_conf = ChatlinkConfig()
check("policy: both allowlists empty => deny (user_not_allowed)",
      decide(member, empty_conf) == Decision(False, "user_not_allowed"))

# claims never invent privileges: default is_channel_member=False denies
check("policy: default claims deny (absent knowledge = False)",
      decide(IdentityClaims(user_id="u1"), GOOD_CONF)
      == Decision(False, "not_channel_member"))

# may_answer: the named initiating-user-only primitive
check("policy: initiator may answer => ok_initiator",
      may_answer("u1", "u1") == Decision(True, "ok_initiator"))
check("policy: non-initiator => not_initiator",
      may_answer("u1", "u2") == Decision(False, "not_initiator"))
check("policy: empty actor => not_initiator (fail-closed)",
      may_answer("u1", "") == Decision(False, "not_initiator"))
check("policy: None initiator => not_initiator (fail-closed)",
      may_answer(None, "u2") == Decision(False, "not_initiator"))
check("policy: both empty => not_initiator (never allow on vacuous equality)",
      may_answer("", "") == Decision(False, "not_initiator"))

# --- paths: permissions + absolute config resolution --------------------------
with tempfile.TemporaryDirectory() as tmp:
    fake_root = Path(tmp)
    orig_project_root = paths_mod.project_root
    paths_mod.project_root = lambda: fake_root
    try:
        sdir = paths_mod.ensure_secure_dir(paths_mod.sessions_dir())
        check("paths: sessions dir under aitasks/metadata/chatlink_sessions",
              sdir == fake_root / "aitasks" / "metadata" / "chatlink_sessions")
        mode = stat.S_IMODE(sdir.stat().st_mode)
        check("paths: sessions dir is 0o700", mode == 0o700)

        check("paths: read_token missing => None", paths_mod.read_token() is None)
        tpath = paths_mod.write_token("s3cret\n")
        check("paths: token file location", tpath == sdir / "bot_token")
        tmode = stat.S_IMODE(tpath.stat().st_mode)
        check("paths: token file is 0o600", tmode == 0o600)
        check("paths: read_token round-trip (stripped)",
              paths_mod.read_token() == "s3cret")
        check("paths: relay_root under sessions dir",
              paths_mod.relay_root() == sdir / "relay")

        # config_file: no config anywhere => None (fail-closed)
        check("paths: config_file None when absent", paths_mod.config_file() is None)
        # seeded default present => absolute path to it
        cfile = fake_root / "aitasks" / "metadata" / "chatlink_config.yaml"
        cfile.parent.mkdir(parents=True, exist_ok=True)
        cfile.write_text("allowed_user_ids: [u1]\n", encoding="utf-8")
        resolved = paths_mod.config_file()
        check("paths: config_file is absolute", resolved is not None
              and resolved.is_absolute())
        check("paths: config_file resolves seeded default", resolved == cfile)
        loaded = load_config(resolved)
        check("paths: resolved config loads", loaded is not None
              and loaded.allowed_user_ids == ["u1"])
    finally:
        paths_mod.project_root = orig_project_root

print(f"PYTHON-PASS:{PASS} PYTHON-FAIL:{FAIL}")
sys.exit(1 if FAIL else 0)
PYEOF
then
    PART1_OK=1
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "ok - part 1: python unit tests"
else
    PART1_OK=0
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "FAIL - part 1: python unit tests"
fi

# ---------------------------------------------------------------------------
# Part 2: cwd independence — config resolution from a foreign cwd
# ---------------------------------------------------------------------------
# Guards the relative-path integration bug: resolve_config_path returns a
# repo-root-relative string; config_file() must absolutize it so the daemon
# can be launched from any directory.

CWD_TMP="$(mktemp -d)"
trap 'rm -rf "$CWD_TMP"' EXIT

CWD_OUT="$(cd "$CWD_TMP" && PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
    "$PYTHON" -c "
from chatlink.paths import config_file
from chatlink.config import load_config
p = config_file()
assert p is not None, 'config_file() returned None from foreign cwd'
assert p.is_absolute(), f'config_file() not absolute: {p}'
conf = load_config(p)
assert conf is not None, 'load_config failed on resolved path'
print('CWD_OK')
" 2>&1)" || true
assert_contains "cwd independence: absolute config resolution from foreign cwd" \
    "$CWD_OUT" "CWD_OK"

# ---------------------------------------------------------------------------
# Part 3: import bootstrap — chatlink.paths importable with only
# .aitask-scripts on the path (no pre-inserted lib/)
# ---------------------------------------------------------------------------

BOOT_OUT="$(cd "$CWD_TMP" && PYTHONPATH="$PROJECT_DIR/.aitask-scripts" \
    "$PYTHON" -c "
import sys
assert not any(p.endswith('/lib') for p in sys.path if 'aitask-scripts' in p), \
    'test precondition: lib/ must not be pre-inserted'
from chatlink.paths import config_file
p = config_file()
assert p is not None and p.is_absolute()
print('BOOTSTRAP_OK')
" 2>&1)" || true
assert_contains "import bootstrap: guarded config_utils import works" \
    "$BOOT_OUT" "BOOTSTRAP_OK"

# ---------------------------------------------------------------------------
# Part 4: secrets hygiene — the data-branch gitignore rule covers the token
# ---------------------------------------------------------------------------

if [ -d "$PROJECT_DIR/.aitask-data" ]; then
    if git -C "$PROJECT_DIR/.aitask-data" check-ignore -q \
        "aitasks/metadata/chatlink_sessions/bot_token" 2>/dev/null; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - hygiene: bot_token is gitignored on the data branch"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - hygiene: bot_token NOT gitignored on the data branch"
    fi
else
    echo "skip - hygiene: no .aitask-data worktree (legacy checkout)"
fi

# ---------------------------------------------------------------------------
echo ""
echo "PASS: $PASS_COUNT, FAIL: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ] && [ "$PART1_OK" -eq 1 ]
