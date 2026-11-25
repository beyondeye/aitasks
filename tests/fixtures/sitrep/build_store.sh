#!/usr/bin/env bash
# build_fixture.sh <writer> <store_v3 dir> <out dir>
# Rebuilds tests/fixtures/sitrep/store (format 4) from the format-3 fixture,
# through the real writer, with the clock pinned. Deterministic: ids, revs and
# the baseline digest come out the same on every run.
set -euo pipefail
H="$1"; SRC="$2"; OUT="$3"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/sitrep_fixture_XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
cp -R "$SRC/." "$WORK/"
export AITASK_SITREP_DIR="$WORK" AITASK_SITREP_NOW="2026-11-20T10:00:00Z"

# c7 loses its explicit direction: a derived member of crashed-agents.
"$H" upsert-context c7 --expect-rev 9 <<'EOF'
- background: Agent on t42 died with its PID anchor gone; plan approved, work left in the shared tree.
- origin: task=t42 date=2026-11-15 skill=aitask-sitrep incarnation=0123456789ab
- sources:
  - task: aitasks/t42_example_task.md
  - plan: aiplans/p42_example_task.md
EOF

# The baseline the sitrep summary is written from: its pending members.
digest="$("$H" retain-baseline <<'EOF' | sed -n 's/^RETAINED_BASELINE:[^|]*|//p'
sitrep direction baseline v1
direction: sitrep
member: c1|open|t2175_2
member: c6|open|push:main@1a2b3c4d5e6f
task: t2175_2|Implementing
trail: art:trail-sitrep-1|v3:current
next: t2175_2|valid
EOF
)"

rev_of() { "$H" directions "$1" | sed -n "s/^DIRECTION:$1|\([^|]*\)|.*/\1/p"; }
stamp_of() { "$H" directions "$1" | sed -n "s/^DIRECTION:$1|[^|]*|\([^|]*\)|.*/\1/p"; }

"$H" direction-set sitrep --expect-rev "$(rev_of sitrep)" \
    --title "Sitrep work directions" --trails art:trail-sitrep-1 --next t2175_2 \
    --summary-file - --digest "$digest" <<'EOF'
Store format landed; skill and TUI children open.
EOF
"$H" direction-set crashed-agents --expect-rev absent --title "Crashed agents"
printf 'sitrep|%s\ncrashed-agents|%s\n' "$(rev_of sitrep)" "$(rev_of crashed-agents)" \
    | "$H" direction-rank --expect-ranked -
printf 'sitrep|%s|%s|stale|now|member_closed:2:c2+c5,trail_stale:1:art:trail-sitrep-1\n' \
    "$(rev_of sitrep)" "$(stamp_of sitrep)" | "$H" direction-freshness --batch

rm -rf "$OUT"
mkdir -p "$OUT"
cp -R "$WORK/next_id" "$WORK/next_rev" "$WORK/qa.md" "$WORK/store.init" \
      "$WORK/todo.md" "$WORK/sources" "$WORK/baselines" "$OUT/"
echo "FIXTURE_BUILT:$OUT (digest $digest)"
