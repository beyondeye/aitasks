#!/usr/bin/env bash
# test_install_merge.sh - Tests for aitask_install_merge.py
# Run: bash tests/test_install_merge.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MERGE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_install_merge.py"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

TMP="$(mktemp -d -t aitask_install_merge_XXXXXX)"
trap "rm -rf '$TMP'" EXIT

# --- YAML merge: dest values win, new seed keys added, nested deep-merge ---

cat > "$TMP/src.yaml" <<'EOF'
a: 1
nested:
  x: 10
  z: 30
new_key: from_seed
EOF
cat > "$TMP/dest.yaml" <<'EOF'
a: 999
nested:
  x: 999
  y: 20
extra: user_only
EOF
"$AITASK_PYTHON" "$MERGE_SCRIPT" yaml "$TMP/src.yaml" "$TMP/dest.yaml"
merged_yaml="$(cat "$TMP/dest.yaml")"
assert_contains "yaml: existing scalar dest value wins" "a: 999" "$merged_yaml"
assert_contains "yaml: new seed top-level key added" "new_key: from_seed" "$merged_yaml"
assert_contains "yaml: nested dest scalar wins" "x: 999" "$merged_yaml"
assert_contains "yaml: nested seed-only key added" "z: 30" "$merged_yaml"
assert_contains "yaml: dest-only nested key preserved" "y: 20" "$merged_yaml"
assert_contains "yaml: dest-only top-level key preserved" "extra: user_only" "$merged_yaml"

# --- YAML merge: list values replaced atomically by dest (per deep_merge semantics) ---

cat > "$TMP/src.yaml" <<'EOF'
items:
  - a
  - b
  - c
EOF
cat > "$TMP/dest.yaml" <<'EOF'
items:
  - a
  - custom
EOF
"$AITASK_PYTHON" "$MERGE_SCRIPT" yaml "$TMP/src.yaml" "$TMP/dest.yaml"
list_merged="$(cat "$TMP/dest.yaml")"
assert_contains "yaml: dest list wins (contains 'custom')" "custom" "$list_merged"
assert_not_contains "yaml: dest list wins (seed-only 'b' dropped)" "- b" "$list_merged"

# --- YAML merge: dest-absent falls back to straight copy ---

rm -f "$TMP/new_dest.yaml"
"$AITASK_PYTHON" "$MERGE_SCRIPT" yaml "$TMP/src.yaml" "$TMP/new_dest.yaml"
assert_eq "yaml: dest-missing copies seed bytes verbatim" \
    "$(cat "$TMP/src.yaml")" "$(cat "$TMP/new_dest.yaml")"

# --- JSON merge: same semantics ---

echo '{"a":1,"n":{"x":10,"z":30},"new":"seed"}' > "$TMP/src.json"
echo '{"a":999,"n":{"x":999,"y":20},"extra":"user"}' > "$TMP/dest.json"
"$AITASK_PYTHON" "$MERGE_SCRIPT" json "$TMP/src.json" "$TMP/dest.json"
merged_json="$(cat "$TMP/dest.json")"
assert_contains "json: dest scalar wins" '"a": 999' "$merged_json"
assert_contains "json: nested seed-only key added" '"z": 30' "$merged_json"
assert_contains "json: dest-only nested key preserved" '"y": 20' "$merged_json"
assert_contains "json: new top-level seed key added" '"new": "seed"' "$merged_json"

# --- JSON merge: invalid JSON fails non-zero, dest untouched ---

echo 'not valid json {' > "$TMP/bad.json"
echo '{"ok": true}' > "$TMP/good_dest.json"
original_good_dest="$(cat "$TMP/good_dest.json")"
if "$AITASK_PYTHON" "$MERGE_SCRIPT" json "$TMP/bad.json" "$TMP/good_dest.json" 2>/dev/null; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: json: invalid src should exit non-zero"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi
assert_eq "json: invalid src leaves dest untouched" \
    "$original_good_dest" "$(cat "$TMP/good_dest.json")"

# --- JSON models merge: destination entries preserved, seed-only models appended ---

cat > "$TMP/src_models.json" <<'EOF'
{
  "models": [
    {
      "name": "opus",
      "cli_id": "claude-opus",
      "notes": "seed opus",
      "verified": {
        "pick": 0
      }
    },
    {
      "name": "fable5",
      "cli_id": "claude-fable-5",
      "notes": "seed fable",
      "verified": {},
      "verifiedstats": {}
    }
  ],
  "seed_only": true
}
EOF
cat > "$TMP/dest_models.json" <<'EOF'
{
  "models": [
    {
      "name": "opus",
      "cli_id": "claude-opus",
      "notes": "local opus",
      "verified": {
        "pick": 80
      },
      "verifiedstats": {
        "pick": {
          "all_time": {
            "runs": 4
          }
        }
      }
    }
  ],
  "local_only": true
}
EOF
opus_before="$("$AITASK_PYTHON" -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))["models"][0], sort_keys=True))' "$TMP/dest_models.json")"
"$AITASK_PYTHON" "$MERGE_SCRIPT" json-models "$TMP/src_models.json" "$TMP/dest_models.json"
opus_after="$("$AITASK_PYTHON" -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))["models"][0], sort_keys=True))' "$TMP/dest_models.json")"
model_count="$("$AITASK_PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["models"]))' "$TMP/dest_models.json")"
model_names="$("$AITASK_PYTHON" -c 'import json,sys; print("\n".join(m.get("name", "") for m in json.load(open(sys.argv[1]))["models"]))' "$TMP/dest_models.json")"
merged_model_json="$(cat "$TMP/dest_models.json")"
assert_eq "json-models: existing model entry preserved exactly" "$opus_before" "$opus_after"
assert_eq "json-models: seed-only model appended" "2" "$model_count"
assert_eq "json-models: destination order then seed order" $'opus\nfable5' "$model_names"
assert_contains "json-models: seed-only top-level key added" '"seed_only": true' "$merged_model_json"
assert_contains "json-models: dest-only top-level key preserved" '"local_only": true' "$merged_model_json"

"$AITASK_PYTHON" "$MERGE_SCRIPT" json-models "$TMP/src_models.json" "$TMP/dest_models.json"
model_count_repeat="$("$AITASK_PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["models"]))' "$TMP/dest_models.json")"
assert_eq "json-models: repeat merge is idempotent" "2" "$model_count_repeat"

# --- JSON models merge: cli_id fallback and canonical JSON fallback ---

cat > "$TMP/src_models_cli_fallback.json" <<'EOF'
{
  "models": [
    {
      "cli_id": "provider/model",
      "notes": "seed"
    }
  ]
}
EOF
cat > "$TMP/dest_models_cli_fallback.json" <<'EOF'
{
  "models": [
    {
      "cli_id": "provider/model",
      "notes": "local",
      "verifiedstats": {
        "pick": {
          "all_time": {
            "runs": 1
          }
        }
      }
    }
  ]
}
EOF
"$AITASK_PYTHON" "$MERGE_SCRIPT" json-models "$TMP/src_models_cli_fallback.json" "$TMP/dest_models_cli_fallback.json"
cli_fallback_count="$("$AITASK_PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["models"]))' "$TMP/dest_models_cli_fallback.json")"
cli_fallback_notes="$("$AITASK_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["models"][0]["notes"])' "$TMP/dest_models_cli_fallback.json")"
assert_eq "json-models: cli_id fallback prevents duplicate" "1" "$cli_fallback_count"
assert_eq "json-models: cli_id fallback preserves dest entry" "local" "$cli_fallback_notes"

cat > "$TMP/src_models_json_fallback.json" <<'EOF'
{
  "models": [
    {
      "notes": "anonymous"
    }
  ]
}
EOF
cat > "$TMP/dest_models_json_fallback.json" <<'EOF'
{
  "models": [
    {
      "notes": "anonymous"
    }
  ]
}
EOF
"$AITASK_PYTHON" "$MERGE_SCRIPT" json-models "$TMP/src_models_json_fallback.json" "$TMP/dest_models_json_fallback.json"
json_fallback_count="$("$AITASK_PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["models"]))' "$TMP/dest_models_json_fallback.json")"
assert_eq "json-models: canonical JSON fallback prevents duplicate" "1" "$json_fallback_count"

# --- JSON models merge: invalid models shape fails non-zero, dest untouched ---

echo '{"models": {"name": "bad"}}' > "$TMP/bad_models_shape.json"
echo '{"models": []}' > "$TMP/good_models_dest.json"
original_good_models_dest="$(cat "$TMP/good_models_dest.json")"
if "$AITASK_PYTHON" "$MERGE_SCRIPT" json-models "$TMP/bad_models_shape.json" "$TMP/good_models_dest.json" 2>/dev/null; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: json-models: invalid models shape should exit non-zero"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi
assert_eq "json-models: invalid models shape leaves dest untouched" \
    "$original_good_models_dest" "$(cat "$TMP/good_models_dest.json")"

# --- install.sh seed model path: FORCE upgrade unions model arrays ---

INSTALL_ROOT="$TMP/install_root"
mkdir -p "$INSTALL_ROOT/.aitask-scripts/lib" "$INSTALL_ROOT/seed" "$INSTALL_ROOT/aitasks/metadata"
cp "$MERGE_SCRIPT" "$INSTALL_ROOT/.aitask-scripts/aitask_install_merge.py"
cp "$PROJECT_DIR/.aitask-scripts/lib/config_utils.py" "$INSTALL_ROOT/.aitask-scripts/lib/config_utils.py"
cat > "$INSTALL_ROOT/seed/models_claudecode.json" <<'EOF'
{
  "models": [
    {
      "name": "opus",
      "cli_id": "claude-opus",
      "notes": "seed opus",
      "verified": {
        "pick": 0
      }
    },
    {
      "name": "fable5",
      "cli_id": "claude-fable-5",
      "notes": "seed fable",
      "verified": {},
      "verifiedstats": {}
    }
  ]
}
EOF
cat > "$INSTALL_ROOT/aitasks/metadata/models_claudecode.json" <<'EOF'
{
  "models": [
    {
      "name": "opus",
      "cli_id": "claude-opus",
      "notes": "local opus",
      "verified": {
        "pick": 80
      },
      "verifiedstats": {
        "pick": {
          "all_time": {
            "runs": 4
          }
        }
      }
    }
  ]
}
EOF
if (
    cd "$PROJECT_DIR"
    # shellcheck source=../install.sh
    source "$PROJECT_DIR/install.sh" --source-only
    INSTALL_DIR="$INSTALL_ROOT"
    FORCE=true
    install_seed_models >/dev/null
); then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: install_seed_models should run successfully in FORCE mode"
fi
install_model_count="$("$AITASK_PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["models"]))' "$INSTALL_ROOT/aitasks/metadata/models_claudecode.json")"
install_opus_pick="$("$AITASK_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["models"][0]["verified"]["pick"])' "$INSTALL_ROOT/aitasks/metadata/models_claudecode.json")"
install_fable_name="$("$AITASK_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["models"][1]["name"])' "$INSTALL_ROOT/aitasks/metadata/models_claudecode.json")"
assert_eq "install_seed_models: model count includes seed addition" "2" "$install_model_count"
assert_eq "install_seed_models: local verified score preserved" "80" "$install_opus_pick"
assert_eq "install_seed_models: seed model appended through install.sh" "fable5" "$install_fable_name"

if (
    cd "$PROJECT_DIR"
    # shellcheck source=../install.sh
    source "$PROJECT_DIR/install.sh" --source-only
    INSTALL_DIR="$INSTALL_ROOT"
    FORCE=true
    install_seed_models >/dev/null
); then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: install_seed_models repeat run should succeed in FORCE mode"
fi
install_model_count_repeat="$("$AITASK_PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["models"]))' "$INSTALL_ROOT/aitasks/metadata/models_claudecode.json")"
assert_eq "install_seed_models: repeat FORCE run is idempotent" "2" "$install_model_count_repeat"

# --- text-union: dest order preserved, seed-only lines appended ---

printf 'bug\nfeature\nchore\ntest\ndocs\n' > "$TMP/src.txt"
printf 'feature\nbug\nmy_custom\n' > "$TMP/dest.txt"
"$AITASK_PYTHON" "$MERGE_SCRIPT" text-union "$TMP/src.txt" "$TMP/dest.txt"
merged_txt="$(cat "$TMP/dest.txt")"
expected_txt="feature
bug
my_custom
chore
test
docs"
assert_eq "text-union: dest order preserved, seed additions appended" \
    "$expected_txt" "$merged_txt"

# --- text-union: idempotent (running twice yields same result) ---

"$AITASK_PYTHON" "$MERGE_SCRIPT" text-union "$TMP/src.txt" "$TMP/dest.txt"
assert_eq "text-union: idempotent on repeat merge" \
    "$expected_txt" "$(cat "$TMP/dest.txt")"

# --- text-union: dest-absent falls back to copy ---

rm -f "$TMP/new_dest.txt"
"$AITASK_PYTHON" "$MERGE_SCRIPT" text-union "$TMP/src.txt" "$TMP/new_dest.txt"
assert_eq "text-union: dest-missing copies seed verbatim" \
    "$(cat "$TMP/src.txt")" "$(cat "$TMP/new_dest.txt")"

# --- Usage errors ---

if "$AITASK_PYTHON" "$MERGE_SCRIPT" unknown_mode "$TMP/src.txt" "$TMP/dest.txt" 2>/dev/null; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: unknown mode should exit non-zero"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi

if "$AITASK_PYTHON" "$MERGE_SCRIPT" yaml 2>/dev/null; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: missing args should exit non-zero"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi

# --- Summary ---

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
