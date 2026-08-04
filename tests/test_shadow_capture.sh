#!/usr/bin/env bash
# test_shadow_capture.sh - Automated tests for aitask_shadow_capture.sh
# Run: bash tests/test_shadow_capture.sh
#
# Exercises the clean/strip logic via the `-` stdin seam (no live tmux) plus
# argument validation as a subprocess. The tmux capture path itself is covered
# by the manual-verification sibling (t986_7) and tests/test_no_raw_tmux.sh
# (gateway-only routing).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

CAPTURE="$PROJECT_DIR/.aitask-scripts/aitask_shadow_capture.sh"

ESC=$(printf '\033')

# ============================================================
# Tests: ANSI / CSI escape stripping (stdin seam)
# ============================================================
echo "--- ansi stripping ---"

out=$(printf '%s[31mRED%s[0m and %s[1mBOLD%s[0m\n' "$ESC" "$ESC" "$ESC" "$ESC" | "$CAPTURE" -)
assert_eq "SGR colour/bold codes stripped, text kept" "RED and BOLD" "$out"
assert_not_contains "no raw ESC byte remains" "$ESC" "$out"

# Cursor-movement CSI (parameter + intermediate + final bytes)
out=$(printf '%s[2J%s[1;1Hhello\n' "$ESC" "$ESC" | "$CAPTURE" -)
assert_eq "cursor/clear CSI stripped" "hello" "$out"

# Plain text passes through unchanged
out=$(printf 'plain line one\nplain line two\n' | "$CAPTURE" -)
assert_eq "plain text unchanged" "plain line one
plain line two" "$out"

# ============================================================
# Tests: whitespace / trailing-blank normalization
# ============================================================
echo "--- whitespace normalization ---"

out=$(printf 'trailing spaces   \n' | "$CAPTURE" -)
assert_eq "trailing whitespace per line stripped" "trailing spaces" "$out"

# Trailing blank + whitespace-only lines dropped; interior blank kept
out=$(printf 'a\n\nb\n   \n\n' | "$CAPTURE" -)
assert_eq "trailing blank lines dropped, interior blank kept" "a

b" "$out"

# ============================================================
# Tests: argument validation
# ============================================================
echo "--- input validation ---"

# `env -u TMUX_PANE -u TMUX` is load-bearing, not tidiness: since t1319 a bare
# invocation RESOLVES its pane from this pane's @aitask_shadow_target binding, so
# running the suite from inside a bound shadow pane would make "no args => error"
# silently untrue. Stripping both vars pins the no-tmux-context case these
# assertions are actually about.
NOCTX=(env -u TMUX_PANE -u TMUX)

out=$("${NOCTX[@]}" "$CAPTURE" 2>&1 </dev/null || true)
assert_contains "missing pane id rejected" "pane id required" "$out"

rc=0
"${NOCTX[@]}" "$CAPTURE" </dev/null >/dev/null 2>&1 || rc=$?
assert_eq "missing pane id exits non-zero" "1" "$rc"

out=$("${NOCTX[@]}" "$CAPTURE" --bogus 2>&1 </dev/null || true)
assert_contains "unknown option rejected" "Unknown option" "$out"

out=$("${NOCTX[@]}" "$CAPTURE" %1 %2 2>&1 </dev/null || true)
assert_contains "extra argument rejected" "Unexpected extra argument" "$out"

out=$("${NOCTX[@]}" "$CAPTURE" --help 2>&1)
assert_contains "help shows usage" "Usage:" "$out"

# ============================================================
# Tests: wrap-join (-J) over a live tmux pane (t1037_4)
# ============================================================
# Proves the script actually passes `capture-pane -J`: a logical line longer
# than the pane width must come back contiguous, not split mid-string by a
# soft-wrap (the concern parser's capture-join contract). Runs on an isolated
# dedicated socket so it never touches the user's tmux server; skipped when
# tmux is unavailable or a test pane cannot be started.
echo "--- wrap-join (-J) live tmux ---"
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — -J join test skipped"
else
    JSOCK="ait_jtest_$$"
    LONG="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # 20-col pane forces the 62-char string to soft-wrap across display rows.
    tmux -L "$JSOCK" new-session -d -x 20 -y 10 \
        "printf '%s' '$LONG'; sleep 30" 2>/dev/null || true
    jpane=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        jpane=$(tmux -L "$JSOCK" list-panes -F '#{pane_id}' 2>/dev/null | head -1 || true)
        [[ -n "$jpane" ]] && break
        sleep 0.1
    done
    jout=""
    if [[ -n "$jpane" ]]; then
        # NOCTX: this test is about wrap-joining, not about bindings. Run with no
        # tmux context so the ambient TMUX_PANE (a pane on the developer's own
        # server) is not read as a cross-server caller and refused — see the
        # t1319 section below.
        # Poll until the pane's printf output has rendered (the pane exists
        # before its command emits anything — capturing too early races to "").
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            jout=$("${NOCTX[@]}" env AITASKS_TMUX_SOCKET="$JSOCK" "$CAPTURE" "$jpane" 2>/dev/null || true)
            [[ -n "$jout" ]] && break
            sleep 0.1
        done
    fi
    tmux -L "$JSOCK" kill-server 2>/dev/null || true
    if [[ -z "$jpane" ]]; then
        echo "SKIP: could not start test tmux pane — -J join test skipped"
    else
        assert_contains "-J rejoins a soft-wrapped logical line (contiguous)" \
            "$LONG" "$jout"
    fi
fi

# ============================================================
# Tests: --deep plan-review capture depth over a live tmux pane (t1071_3)
# ============================================================
# Proves --deep reaches further back than the default window. capture-pane -S -N
# returns N scrollback lines plus the visible pane, so the test fixes the pane
# height (VIS) and sizes the line count T so the first-line sentinel sits OUTSIDE
# the default window (200 + VIS) but INSIDE the deep window (400 + VIS). Both
# depth env vars are pinned per invocation so ambient SHADOW_CAPTURE_LINES /
# SHADOW_PLAN_CAPTURE_LINES in a dev/CI shell can't skew the math. Skipped when
# tmux is unavailable or a test pane can't start (mirrors the -J test above).
echo "--- --deep capture depth live tmux ---"
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — --deep depth test skipped"
else
    DSOCK="ait_dtest_$$"
    VIS=10
    # T=320: sentinel(1) + seq 2..319 (318) + lastline(1). With VIS=10 the
    # sentinel is ~110 lines above the default window's top (200+VIS) and ~100
    # lines inside the deep window (400+VIS) — comfortable margins both ways.
    tmux -L "$DSOCK" new-session -d -x 80 -y "$VIS" \
        "printf 'SHADOW_DEEP_SENTINEL\n'; seq 2 319; printf 'SHADOW_DEEP_LASTLINE\n'; sleep 30" 2>/dev/null || true
    dpane=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        dpane=$(tmux -L "$DSOCK" list-panes -F '#{pane_id}' 2>/dev/null | head -1 || true)
        [[ -n "$dpane" ]] && break
        sleep 0.1
    done
    deep_out=""
    if [[ -n "$dpane" ]]; then
        # Poll the deep capture until the pane has finished printing (last line
        # rendered) so the default-window assertion below isn't racing render.
        # NOCTX for the same reason as the -J test above: depth, not bindings.
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            deep_out=$("${NOCTX[@]}" env SHADOW_CAPTURE_LINES=200 SHADOW_PLAN_CAPTURE_LINES=400 \
                AITASKS_TMUX_SOCKET="$DSOCK" "$CAPTURE" --deep "$dpane" 2>/dev/null || true)
            [[ "$deep_out" == *SHADOW_DEEP_LASTLINE* ]] && break
            sleep 0.1
        done
        def_out=$("${NOCTX[@]}" env SHADOW_CAPTURE_LINES=200 \
            AITASKS_TMUX_SOCKET="$DSOCK" "$CAPTURE" "$dpane" 2>/dev/null || true)
    fi
    tmux -L "$DSOCK" kill-server 2>/dev/null || true
    if [[ -z "$dpane" || "$deep_out" != *SHADOW_DEEP_LASTLINE* ]]; then
        echo "SKIP: could not start/render test tmux pane — --deep depth test skipped"
    else
        assert_not_contains "default depth (200) misses the first-line sentinel" \
            "SHADOW_DEEP_SENTINEL" "$def_out"
        assert_contains "--deep (400) reaches the first-line sentinel" \
            "SHADOW_DEEP_SENTINEL" "$deep_out"
        assert_contains "default depth still includes the last line (sanity)" \
            "SHADOW_DEEP_LASTLINE" "$def_out"
    fi
fi

# ============================================================
# Tests: freshness stamping is inert on the stdin/no-tmux paths (t1104)
# ============================================================
echo "--- freshness stamping (stdin seam) ---"

# TMUX_PANE unset: the stamp helper must not stamp and must not abort under
# `set -u` with TMUX_PANE unbound — the stdin path emits clean text unchanged.
unset TMUX_PANE
out=$(printf 'plain line\n' | "$CAPTURE" -)
assert_eq "stdin path emits cleaned text (no stamp side effect)" "plain line" "$out"

rc=0
printf 'x\n' | "$CAPTURE" - >/dev/null 2>&1 || rc=$?
assert_eq "stdin path exits 0 with TMUX_PANE unset (no set -u abort)" "0" "$rc"

# ============================================================
# Tests: analyzed-at stamping over a live tmux pane (t1104)
# ============================================================
# A capture running *inside a shadow pane* (its @aitask_shadow_target == the
# captured pane) stamps @aitask_shadow_analyzed_at on its own pane; a capture
# from a non-shadow pane does not. Isolated socket; skipped without tmux.
echo "--- analyzed-at stamping live tmux ---"
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — stamping test skipped"
else
    STSOCK="ait_ststest_$$"
    tmux -L "$STSOCK" new-session -d -x 80 -y 10 "sleep 30" 2>/dev/null || true
    followed=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        followed=$(tmux -L "$STSOCK" list-panes -F '#{pane_id}' 2>/dev/null | head -1 || true)
        [[ -n "$followed" ]] && break
        sleep 0.1
    done
    shadow=""
    if [[ -n "$followed" ]]; then
        tmux -L "$STSOCK" split-window -d "sleep 30" 2>/dev/null || true
        shadow=$(tmux -L "$STSOCK" list-panes -F '#{pane_id}' 2>/dev/null | grep -v "^${followed}$" | head -1 || true)
    fi
    if [[ -z "$followed" || -z "$shadow" ]]; then
        tmux -L "$STSOCK" kill-server 2>/dev/null || true
        echo "SKIP: could not start test tmux panes — stamping test skipped"
    else
        # $TMUX must be set alongside $TMUX_PANE: since t1319 the helper only
        # trusts a binding when the pane it queried lives on the SAME server the
        # caller is attached to (pane ids collide across tmux servers). A
        # TMUX_PANE with no server behind it is — correctly — untrusted, so a
        # fixture that sets only TMUX_PANE would stop stamping.
        # The `-t` is required: this server is detached, so a bare
        # `display-message -p` has no client to resolve its implicit target
        # against. socket_path/pid are server-scoped, so any live pane will do.
        STTMUX=$(tmux -L "$STSOCK" display-message -p -t "$shadow" '#{socket_path},#{pid},0' 2>/dev/null || true)
        # Bind the shadow to the followed pane, then capture from *inside* it.
        tmux -L "$STSOCK" set-option -p -t "$shadow" @aitask_shadow_target "$followed" 2>/dev/null || true
        TMUX="$STTMUX" TMUX_PANE="$shadow" AITASKS_TMUX_SOCKET="$STSOCK" "$CAPTURE" "$followed" >/dev/null 2>&1 || true
        stamped=$(tmux -L "$STSOCK" show-options -pqv -t "$shadow" @aitask_shadow_analyzed_at 2>/dev/null || true)
        # A non-shadow pane (own pane has no @aitask_shadow_target) must NOT stamp.
        TMUX="$STTMUX" TMUX_PANE="$followed" AITASKS_TMUX_SOCKET="$STSOCK" "$CAPTURE" "$followed" >/dev/null 2>&1 || true
        unstamped=$(tmux -L "$STSOCK" show-options -pqv -t "$followed" @aitask_shadow_analyzed_at 2>/dev/null || true)
        tmux -L "$STSOCK" kill-server 2>/dev/null || true
        assert_contains "shadow-pane capture stamps a numeric analyzed-at" \
            "$(printf '%s' "$stamped" | grep -qE '^[0-9]+$' && echo NUMERIC)" "NUMERIC"
        assert_eq "non-shadow-pane capture leaves analyzed-at unset" "" "$unstamped"
    fi
fi

# ============================================================
# Tests: binding-based resolution + wrong-pane refusal (t1319)
# ============================================================
# The hazard: a model transcribing <followed_pane_id> can truncate it (%237 ->
# %7) into an id that names a DIFFERENT live pane. That capture SUCCEEDS and
# raises no error, so nothing downstream can notice. Two structural guards close
# it — resolving the pane from the shadow's own @aitask_shadow_target binding
# (no argument to mangle), and refusing an explicit id that the binding
# contradicts or cannot vouch for.
#
# Fixture (one isolated socket): `followed` and `other` each print a distinct
# sentinel so a wrong-pane capture is *visible* rather than merely "not an
# error"; `shadow` is bound to `followed`.
echo "--- binding resolution + wrong-pane refusal (t1319) ---"
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — binding-resolution tests skipped"
else
    BSOCK="ait_btest_$$"
    FOLLOWED_SENTINEL="T1319_FOLLOWED_SENTINEL"
    OTHER_SENTINEL="T1319_OTHER_SENTINEL"

    tmux -L "$BSOCK" new-session -d -x 80 -y 10 \
        "printf '%s\n' '$FOLLOWED_SENTINEL'; sleep 60" 2>/dev/null || true
    b_followed=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        b_followed=$(tmux -L "$BSOCK" list-panes -F '#{pane_id}' 2>/dev/null | head -1 || true)
        [[ -n "$b_followed" ]] && break
        sleep 0.1
    done
    b_other=""; b_shadow=""
    if [[ -n "$b_followed" ]]; then
        # `-P -F` prints the NEW pane's id: identifying the panes by creation
        # rather than by their position in `list-panes` matters, because a `-d`
        # split leaves the original pane active, so both splits divide the same
        # pane and the resulting index order does not follow creation order.
        # Reading them positionally silently swaps `other` and `shadow`.
        b_other=$(tmux -L "$BSOCK" split-window -d -P -F '#{pane_id}' \
            "printf '%s\n' '$OTHER_SENTINEL'; sleep 60" 2>/dev/null || true)
        b_shadow=$(tmux -L "$BSOCK" split-window -d -P -F '#{pane_id}' \
            "sleep 60" 2>/dev/null || true)
    fi

    if [[ -z "$b_followed" || -z "$b_other" || -z "$b_shadow" ]]; then
        tmux -L "$BSOCK" kill-server 2>/dev/null || true
        echo "SKIP: could not start test tmux panes — binding-resolution tests skipped"
    else
        # See the analyzed-at fixture above for why $TMUX is derived with `-t`.
        BTMUX=$(tmux -L "$BSOCK" display-message -p -t "$b_shadow" '#{socket_path},#{pid},0' 2>/dev/null || true)
        tmux -L "$BSOCK" set-option -p -t "$b_shadow" @aitask_shadow_target "$b_followed" 2>/dev/null || true

        # Run $CAPTURE as if from inside <pane>, against this fixture server.
        b_cap() {
            local from="$1"; shift
            TMUX="$BTMUX" TMUX_PANE="$from" AITASKS_TMUX_SOCKET="$BSOCK" \
                "$CAPTURE" "$@" 2>/dev/null || true
        }
        b_err() {
            local from="$1"; shift
            TMUX="$BTMUX" TMUX_PANE="$from" AITASKS_TMUX_SOCKET="$BSOCK" \
                "$CAPTURE" "$@" 2>&1 >/dev/null || true
        }
        b_rc() {
            local from="$1"; shift
            local rc=0
            TMUX="$BTMUX" TMUX_PANE="$from" AITASKS_TMUX_SOCKET="$BSOCK" \
                "$CAPTURE" "$@" >/dev/null 2>&1 || rc=$?
            printf '%s' "$rc"
        }

        # Let both sentinel panes render before asserting on their content.
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            [[ "$(b_cap "$b_shadow" --any-pane "$b_other")" == *"$OTHER_SENTINEL"* ]] && break
            sleep 0.1
        done

        # 1. No argument + a binding => capture the BOUND pane.
        assert_contains "no-arg capture resolves the bound followed pane" \
            "$FOLLOWED_SENTINEL" "$(b_cap "$b_shadow")"

        # 2. No argument + no binding => fail closed, capture nothing.
        assert_contains "no-arg without a binding fails closed" \
            "pane id required" "$(b_err "$b_other")"
        assert_eq "no-arg without a binding exits 1" "1" "$(b_rc "$b_other")"
        assert_eq "no-arg without a binding emits no capture" "" "$(b_cap "$b_other")"

        # 3. Explicit id matching the binding => allowed.
        assert_contains "explicit id matching the binding is captured" \
            "$FOLLOWED_SENTINEL" "$(b_cap "$b_shadow" "$b_followed")"

        # 4. Explicit id contradicting the binding => refused, nothing captured.
        assert_eq "conflicting explicit id exits 2" "2" "$(b_rc "$b_shadow" "$b_other")"
        conflict_err="$(b_err "$b_shadow" "$b_other")"
        assert_contains "conflict error names the requested pane" "$b_other" "$conflict_err"
        assert_contains "conflict error names the bound pane" "$b_followed" "$conflict_err"
        assert_eq "conflicting explicit id emits no capture" "" \
            "$(b_cap "$b_shadow" "$b_other")"

        # 5. NEGATIVE CONTROL for 4: the same call with --any-pane really does
        #    capture the wrong pane. Without this, "exit 2" could be passing for
        #    an unrelated reason and case 4 would prove nothing.
        assert_contains "--any-pane overrides the refusal (proves 4 discriminates)" \
            "$OTHER_SENTINEL" "$(b_cap "$b_shadow" --any-pane "$b_other")"

        # 6. A same-server caller with NO binding is never refused — this is the
        #    learner pane / gateway-side TUI case, which must keep working.
        assert_contains "unbound same-server caller is not refused" \
            "$FOLLOWED_SENTINEL" "$(b_cap "$b_other" "$b_followed")"

        # 7. Cross-server caller.
        #
        #    The lookup addresses the GATEWAY server, so a caller on another
        #    server reads the gateway's SAME-NUMBERED pane — a pane it has no
        #    relationship with. The fixture therefore has to make the ids
        #    collide, and the colliding gateway pane has to be one that IS
        #    bound: server A's `b_shadow` is bound to `b_followed`, so without
        #    the socket check a no-arg call from server B's identically-numbered
        #    pane would resolve to `b_followed` and capture it. Give server B
        #    three panes so the counters line up, then pick the collision.
        XSOCK="ait_xtest_$$"
        tmux -L "$XSOCK" new-session -d -x 80 -y 10 "sleep 60" 2>/dev/null || true
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            [[ -n "$(tmux -L "$XSOCK" list-panes -F '#{pane_id}' 2>/dev/null | head -1 || true)" ]] && break
            sleep 0.1
        done
        tmux -L "$XSOCK" split-window -d "sleep 60" 2>/dev/null || true
        tmux -L "$XSOCK" split-window -d "sleep 60" 2>/dev/null || true
        x_pane=$(tmux -L "$XSOCK" list-panes -F '#{pane_id}' 2>/dev/null \
            | grep -Fx "$b_shadow" || true)
        if [[ -z "$x_pane" ]]; then
            echo "SKIP: no colliding pane id across the two servers — cross-server test skipped"
        else
            XTMUX=$(tmux -L "$XSOCK" display-message -p -t "$x_pane" '#{socket_path},#{pid},0' 2>/dev/null || true)
            x_run() {
                local rc=0 out
                out=$(TMUX="$XTMUX" TMUX_PANE="$x_pane" AITASKS_TMUX_SOCKET="$BSOCK" \
                    "$CAPTURE" "$@" 2>&1) || rc=$?
                printf '%s\n%s' "$rc" "$out"
            }
            xr="$(x_run)"
            assert_contains "cross-server no-arg fails closed" \
                "pane id required" "$xr"
            assert_eq "cross-server no-arg exits 1" "1" "$(printf '%s' "$xr" | head -1)"
            # The point of the socket check: without it this call resolves the
            # colliding gateway pane's binding and captures ITS followed agent.
            assert_not_contains "cross-server no-arg does not capture the collided binding's target" \
                "$FOLLOWED_SENTINEL" "$xr"
            xr="$(x_run "$b_other")"
            assert_eq "cross-server explicit id exits 2" "2" "$(printf '%s' "$xr" | head -1)"
            assert_contains "cross-server refusal explains why" \
                "different tmux server" "$xr"
            assert_not_contains "cross-server refusal captures nothing" \
                "$OTHER_SENTINEL" "$xr"
            xr="$(x_run --any-pane "$b_other")"
            assert_contains "cross-server --any-pane captures deliberately" \
                "$OTHER_SENTINEL" "$xr"
            tmux -L "$XSOCK" kill-server 2>/dev/null || true
        fi

        tmux -L "$BSOCK" kill-server 2>/dev/null || true
    fi
fi

# ============================================================
# Tests: launch-order race — stamp lands AFTER the capture starts (t1319)
# ============================================================
# `spawn_shadow` stamps @aitask_shadow_target only after `launch_in_tmux`
# returns, so a shadow's first capture can outrun its own binding. This
# reproduces that ordering exactly: the capturing pane's command starts at split
# time, and the stamp is written afterwards. The bounded wait
# (SHADOW_BIND_WAIT_MS) is what bridges the gap.
echo "--- launch-order race (t1319) ---"
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — launch-order test skipped"
else
    race_run() {
        # $1 = SHADOW_BIND_WAIT_MS for the capturing pane. Echoes what the
        # no-arg capture wrote (stdout+stderr), or "" if the fixture failed.
        local wait_ms="$1"
        local sock="ait_rtest_$$_${wait_ms}"
        local outfile="${TMPDIR:-/tmp}/ait_race_$$_${wait_ms}.txt"
        rm -f "$outfile"
        tmux -L "$sock" new-session -d -x 80 -y 10 \
            "printf '%s\n' 'T1319_RACE_SENTINEL'; sleep 60" 2>/dev/null || true
        local rfollowed=""
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            rfollowed=$(tmux -L "$sock" list-panes -F '#{pane_id}' 2>/dev/null | head -1 || true)
            [[ -n "$rfollowed" ]] && break
            sleep 0.1
        done
        if [[ -z "$rfollowed" ]]; then
            tmux -L "$sock" kill-server 2>/dev/null || true
            return 0
        fi
        # The capture starts HERE — before any stamp exists. AITASKS_TMUX_SOCKET
        # is passed in the command itself rather than relying on the server's
        # inherited environment; $TMUX is set by tmux for the new pane.
        local rshadow
        rshadow=$(tmux -L "$sock" split-window -d -P -F '#{pane_id}' \
            "AITASKS_TMUX_SOCKET='$sock' SHADOW_BIND_WAIT_MS='$wait_ms' '$CAPTURE' >'$outfile' 2>&1; sleep 60" \
            2>/dev/null || true)
        # ...and the binding lands only now, mirroring spawn_shadow's order
        # (`launch_in_tmux` returns, THEN the stamp is written).
        #
        # The delay is what makes this deterministic rather than a coin flip.
        # Production's launch->stamp gap is smaller than a second but is not
        # bounded (it is two tmux round-trips under arbitrary system load), and
        # without a delay the stamp reliably wins the race here — which would
        # make the SHADOW_BIND_WAIT_MS=0 control below pass vacuously and prove
        # nothing about the wait.
        sleep 1
        [[ -n "$rshadow" ]] && tmux -L "$sock" set-option -p -t "$rshadow" \
            @aitask_shadow_target "$rfollowed" 2>/dev/null || true
        local content=""
        for _ in $(seq 1 40); do
            content=$(cat "$outfile" 2>/dev/null || true)
            [[ -n "$content" ]] && break
            sleep 0.1
        done
        tmux -L "$sock" kill-server 2>/dev/null || true
        rm -f "$outfile"
        printf '%s' "$content"
    }

    race_waited="$(race_run 2000)"
    race_nowait="$(race_run 0)"
    if [[ -z "$race_waited" && -z "$race_nowait" ]]; then
        echo "SKIP: could not start race-fixture tmux panes — launch-order test skipped"
    else
        assert_contains "bounded wait bridges the launch->stamp race" \
            "T1319_RACE_SENTINEL" "$race_waited"
        # NEGATIVE CONTROL: with the wait disabled the very same fixture fails
        # closed. This is what proves the assertion above is the WAIT working,
        # not the stamp happening to land first — and that fail-closed survives.
        assert_contains "with the wait disabled the same race fails closed" \
            "pane id required" "$race_nowait"
        assert_not_contains "the failed-closed run captured nothing" \
            "T1319_RACE_SENTINEL" "$race_nowait"
    fi
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
