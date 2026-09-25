#!/usr/bin/env bash
# benchci.sh — CI helpers around the benchmark gate (internal/tools/benchgate).
# Never shipped: build.sh builds only cmd/*.
#
#   benchci.sh seed <baseline-in> <baseline-out>
#       Write a seeded-regression baseline: every non-calibration line's ns/op
#       divided by 2.1, so a healthy host measures a just-over-2x regression.
#       Comments, calibration lines and budget=/cal= fields are kept as-is.
#
#   benchci.sh summary <baseline-used> <gate-output>
#       Print a markdown table of every benchmark's host-scaled ratio. The
#       gate's BENCH_OK line carries no ratio, so it is recomputed here the
#       way benchgate does: scale = <current cal> / <baseline cal>, from the
#       unrounded fields 3 and 4 of the class's BENCH_SCALE line (field 2 is
#       rounded to 3 decimals), and ratio = cur / (base x scale). The ratio is
#       printed at 6 decimals and never judged against a threshold here.
#       Always exits 0 once its arguments are well-formed: the summary must
#       never mask or replace the gate's own verdict.
set -euo pipefail

usage() {
    echo "usage: benchci.sh seed <baseline-in> <baseline-out> | summary <baseline-used> <gate-output>" >&2
    exit 2
}

# Calibration lines are the per-class host-speed references
# (internal/benchgate.Calibrations); they are never seeded or tabulated.
readonly CAL_RE='^internal/benchgate[.]BenchmarkCalibrate'

cmd_seed() {
    local in="$1" out="$2"
    [[ -r "$in" ]] || { echo "ERROR:cannot read $in" >&2; exit 1; }
    awk -v cal="$CAL_RE" '
        /^[[:space:]]*(#|$)/ { print; next }
        $1 ~ cal { print; next }
        {
            $2 = sprintf("%.6f", $2 / 2.1)
            print
        }
    ' "$in" > "$out"
}

cmd_summary() {
    local baseline="$1" gate="$2"
    if [[ ! -r "$baseline" || ! -r "$gate" ]]; then
        echo "_bench summary unavailable: cannot read ${baseline} or ${gate}_"
        return 0
    fi
    awk -v cal="$CAL_RE" '
        # Pass 1: the baseline actually used by the gate.
        FILENAME == ARGV[1] {
            if ($0 ~ /^[[:space:]]*(#|$)/ || $1 ~ cal) next
            name = $1
            order[++n] = name
            base[name] = $2
            class[name] = "cpu"
            for (i = 3; i <= NF; i++)
                if ($i ~ /^cal=/) class[name] = substr($i, 5)
            next
        }
        # Pass 2: the gate output (only protocol lines; go test noise ignored).
        /^BENCH_SCALE:/ {
            split(substr($0, 13), f, "|")
            scale[f[1]] = f[3] / f[4]
            scaleline[++ns] = $0
            next
        }
        /^BENCH_(SCALE_IMPLAUSIBLE|CALIBRATION_MISSING|UNSCALED):/ {
            rest = $0; sub(/^[A-Z_]+:/, "", rest)
            split(rest, f, "|")
            bad[f[1]] = 1
            scaleline[++ns] = $0
            next
        }
        /^BENCH_(OK|REGRESSION|OVER_BUDGET|NEW|MISSING):/ {
            kind = $0; sub(/:.*/, "", kind)
            rest = $0; sub(/^[A-Z_]+:/, "", rest)
            split(rest, f, "|")
            name = f[1]
            if (kind != "BENCH_MISSING") cur[name] = f[2]
            v = kind == "BENCH_OK" ? "ok" : kind == "BENCH_REGRESSION" ? "regression" : \
                kind == "BENCH_OVER_BUDGET" ? "over-budget" : kind == "BENCH_NEW" ? "new" : "missing"
            verdict[name] = (name in verdict) ? verdict[name] "+" v : v
            if (!(name in base) && !(name in seen)) { seen[name] = 1; extra[++ne] = name }
            next
        }
        END {
            print "| benchmark | class | current ns/op | baseline ns/op | scale | scaled ratio | verdict |"
            print "|---|---|---|---|---|---|---|"
            for (i = 1; i <= n; i++) row(order[i])
            for (i = 1; i <= ne; i++) row(extra[i])
            if (ns > 0) {
                print ""
                print "Host scales (gate output):"
                print ""
                for (i = 1; i <= ns; i++) print "    " scaleline[i]
            }
        }
        function row(name,   c, b, k, s, r, v) {
            c = (name in cur) ? cur[name] : "n/a"
            b = (name in base) ? base[name] : "n/a"
            k = (name in class) ? class[name] : "n/a"
            v = (name in verdict) ? verdict[name] : "absent"
            if ((k in scale) && !(k in bad)) s = sprintf("%.6f", scale[k]); else s = "n/a"
            if (c != "n/a" && b != "n/a" && s != "n/a")
                r = sprintf("%.6f", c / (b * scale[k]))
            else
                r = "n/a"
            printf "| %s | %s | %s | %s | %s | %s | %s |\n", name, k, c, b, s, r, v
        }
    ' "$baseline" "$gate"
}

[[ $# -ge 1 ]] || usage
case "$1" in
    seed)    [[ $# -eq 3 ]] || usage; cmd_seed "$2" "$3" ;;
    summary) [[ $# -eq 3 ]] || usage; cmd_summary "$2" "$3" ;;
    *)       usage ;;
esac
