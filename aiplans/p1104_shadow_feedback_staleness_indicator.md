---
Task: t1104_shadow_feedback_staleness_indicator.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# t1104 — Shadow feedback staleness indicator

## Context

The shadow companion agent (`/aitask-shadow`) advises on a *followed* coding agent
by capturing that agent's tmux pane on demand (`aitask_shadow_capture.sh`) and
reasoning about the snapshot. Nothing records **which followed-state a given piece
of shadow feedback was about**. When the user follows many parallel agents, the
followed agent races ahead — often *while the shadow is still thinking* — and the
shadow's advice silently becomes stale, with no visible signal. The user can then
forward stale concerns or act on outdated advice.

**Goal:** detect whether the shadow's latest feedback reflects the followed agent's
*current* output or an *older* state, and surface it — as a minimonitor status-line
warning and by annotating the concern auto-offer / picker (the actionable surface).

**Chosen mechanism (confirmed with user): content-signature anchor.** When the
shadow captures the followed pane it stamps a hash of that captured content onto its
own pane; minimonitor re-hashes the followed pane's *current* content (via the same
helper, so normalization matches) and compares. Mismatch ⇒ the followed agent moved
on ⇒ shadow feedback is stale. This is more precise than comparing pane last-change
timestamps because it anchors to the exact state the shadow *read*, so it catches
drift introduced during the shadow's think-time (the motivating case). Rejected
alternative: dual `_last_change_time` comparison — trivial but reports "current" when
the shadow finishes writing after the followed agent already advanced, under-reporting
exactly the scenario that motivated this task.

Advisory-only and best-effort throughout: any capture/hash failure degrades silently
and never blocks the UI or the concern flow.

## Design

```
shadow captures followed pane ──▶ hashes the exact cleaned text it emits, then stamps
    @aitask_shadow_analyzed_sig = "<lines>:<hash>"   (auto, only inside a shadow pane; no recapture)

minimonitor refresh tick:
    stored = @aitask_shadow_analyzed_sig on the shadow pane   # cheap show-options
    stored absent          ⇒ unknown (shadow hasn't analyzed) ⇒ no warning, skip subprocess
    stored "<lines>:<h>"   ⇒ live = sig(followed pane @ now, depth=<lines>)   # same helper ⇒ parity
        h != live  ⇒ STALE     (warn + annotate concerns)
        h == live  ⇒ current
        live failed ⇒ preserve previous state (never clear a true warning)
```

Signature = hash of the **cleaned text the shadow actually emitted** (no second
capture — see below), computed on **both** sides by the same `aitask_shadow_capture.sh`
code path. The stamp is **depth-tagged** — `@aitask_shadow_analyzed_sig = "<lines>:<hash>"`
— so minimonitor reproduces the live signature at the *same* depth the shadow read
(`--deep` reads 400 lines, normal reads 200), guaranteeing parity without a fixed-depth
assumption.

**No recapture race (concern 2):** the stamp is computed from the exact cleaned string
just emitted to stdout, in the same `main` invocation — NOT from a fresh recapture. A
separate recapture could observe newer followed output than the shadow read, making
minimonitor wrongly report stale feedback as current. `main` therefore buffers the
cleaned output into a variable, emits it, and hashes that same variable.

## Changes

### 1. `.aitask-scripts/aitask_shadow_capture.sh` — signature + auto-stamp

- **`shadow_signature`** (new function): given cleaned text on stdin, emit a stable
  digest. Use a portable, same-host hash — `cksum` (POSIX; present on macOS + Linux)
  reduced to `"<checksum>-<bytes>"` via `awk`. (If `terminal_compat.sh` already exposes
  a hash helper, reuse it instead.) Both sides run on the same host, so any consistent
  hash is fine; this is advisory-only.
- **`--sig <pane> [--lines N]` mode** (new): capture `<pane>` at depth `N` (default
  `SHADOW_CAPTURE_LINES`), clean, and print only the signature; **no stamping**. `--lines`
  lets minimonitor reproduce the exact depth recorded in the stamp. Also support
  **`--sig -`** (hash cleaned stdin) — the test/parity seam (no tmux needed). This is what
  minimonitor calls for the live followed signature.
- **Buffer-then-emit-then-hash (concern 2):** restructure `main`'s real-pane branch so the
  cleaned capture is stored once — `output="$(shadow_capture_pane "$pane" "$capture_lines" | shadow_clean)"`
  — then `printf '%s\n' "$output"` to stdout, and the stamp hashes **that same `$output`**
  (`sig="$(printf '%s' "$output" | shadow_signature)"`). No recapture, so the stamped
  signature describes exactly what the shadow read.
- **Auto-stamp on the normal capture path**: detect whether this process runs *inside a
  shadow pane* by reading its own pane option through the gateway — but **guard `TMUX_PANE`
  under `set -u` (concern 1)**: only attempt stamping when `${TMUX_PANE:-}` is non-empty.
  ```
  own_pane="${TMUX_PANE:-}"
  if [[ -n "$own_pane" && "$pane" != "-" ]]; then
    self_target="$(ait_tmux show-options -pqv -t "$own_pane" @aitask_shadow_target 2>/dev/null || true)"
    if [[ -n "$self_target" && "$self_target" == "$pane" ]]; then
      ait_tmux set-option -p -t "$own_pane" \
        @aitask_shadow_analyzed_sig "${capture_lines}:${sig}" 2>/dev/null || true
    fi
  fi
  ```
  The stamp value is **depth-tagged** (`<capture_lines>:<sig>`). Every tmux call is wrapped so
  failure is swallowed — never breaks the capture. Automatic (no flag, no skill-markdown edits)
  and self-guarding: minimonitor's calls run from the minimonitor pane (no
  `@aitask_shadow_target`), and the `-`/`--sig`/no-TMUX paths never stamp. **Default stdout
  contract unchanged** — stamping is a side effect on the normal path; `--sig` is a separate mode.

### 2. `.aitask-scripts/monitor/monitor_core.py` — option constant + reader

- Add `SHADOW_ANALYZED_SIG_OPTION = "@aitask_shadow_analyzed_sig"` beside
  `SHADOW_TARGET_OPTION` (near line 186).
- Add a small gateway-routed reader, e.g. `get_pane_option(pane_id, option) -> str`
  using `show-options -pqv -t <pane> <option>` via `self.tmux_run(...)`, returning `""`
  on failure. (Keeps all tmux access inside the monitor's gateway, per `tmux_gateway.md`.)

### 3. `.aitask-scripts/monitor/minimonitor_app.py` — compute freshness + display

- **Compose:** add `yield Static("", id="mini-shadow-stale")` after `#mini-session-bar`
  (line 256); minimal CSS near line 137 (empty ⇒ occupies no visible row). Leave the
  built-once `#mini-own-agent` panel untouched (respects its static-by-design contract).
- **State:** add `self._shadow_feedback_stale: bool | None = None` beside
  `self._last_concern_block_payload` (line 253). Tri-state: `None` = unknown (never resolved
  / transient failure — see concern 4), `False` = current, `True` = stale.
- **Refactor `_maybe_offer_concerns`** into a per-tick `_refresh_shadow_state` (still called
  at the end of `_refresh_data`, line 442) that resolves the shadow pane **once**, then:
  1. If no shadow pane → clear the warning Static, set flag `None`, reset dedup, return.
  2. **Freshness (cost-gated — concern 5):** first read the **cheap** pane option
     `stored = get_pane_option(shadow_pane, SHADOW_ANALYZED_SIG_OPTION)` (one `show-options`).
     - `stored == ""` → shadow hasn't analyzed yet → flag `False`/`None`, clear the warning
       Static, **skip the subprocess entirely**.
     - `stored` present → parse `"<lines>:<hash>"`; only now spend the subprocess: compute
       `live` via a new async `_followed_signature(followed_pane, lines)` (shells
       `aitask_shadow_capture.sh --sig <pane> --lines <lines>`, mirroring `_capture_shadow_text`'s
       async + hard `_SHADOW_CAPTURE_TIMEOUT` + silent-degrade pattern).
       - **On success:** `stale = (stored_hash != live)`; set `self._shadow_feedback_stale`
         and update `#mini-shadow-stale` (stale → `"[bold red]⚠ shadow feedback is stale — agent moved on[/]"`,
         current → `""`).
       - **On failure/timeout (concern 4):** do **NOT** clear a previously-`True` warning.
         Leave `self._shadow_feedback_stale` and the Static text **unchanged** (preserve last
         known state); a transient tmux/helper hiccup must not silently flip an actionable
         "stale" to "current".
  3. **Concern auto-offer:** existing strict `has_concern_block` + payload-dedup logic; when it
     fires, append `" (⚠ STALE — agent moved on)"` to the notify when `self._shadow_feedback_stale`
     is `True`.
- **`action_pick_concerns` (hotkey 'c'):** use the already-computed `self._shadow_feedback_stale`
  (avoid a second live-sig spend on the hotkey path); pass `stale=bool(...)` into
  `ConcernPickerModal`. If freshness is unknown (`None`), treat as not-stale for the banner.

### 4. `.aitask-scripts/monitor/monitor_shared.py` — `ConcernPickerModal` stale banner

`ConcernPickerModal` lives at `monitor_shared.py:563` (NOT a `concern_picker_modal.py` — concern 3).
Add an optional `stale: bool=False` constructor arg and render a one-line red banner
("⚠ These concerns may be stale — the agent has moved on") when set. Its tests are
`tests/test_concern_picker_modal.py`. (If widening the shared modal's contract is unwanted, fall
back to a `self.notify(...)` warning in §3 before `push_screen` and skip the modal edit.)

### 5. Docs — `aidocs/framework/shadow_agent.md`

Document: the `@aitask_shadow_analyzed_sig` pane-option and the auto-stamp-when-shadow
behavior; the `--sig` mode; the minimonitor per-tick freshness compare, the status-line
warning, and the concern-surface annotations. Add a cross-note in `shadow_concern_format.md`
that the concern-forward surfaces show a staleness warning. (Current-state prose only.)

## Tests

- **`tests/test_shadow_capture.sh`** (extend): `--sig -` deterministic (same cleaned input →
  same sig); different input → different sig; **parity** — `--sig -` equals the signature the
  read path computes for identical content (normalization-parity AC); `--sig -` / stdin / no-tmux
  paths do **not** stamp and don't abort under `set -u` with `TMUX_PANE` unset (concern 1);
  unknown flag still errors; default stdout unchanged.
- **`tests/test_minimonitor_concern_action.py`** (extend), monkeypatching `get_pane_option` +
  `_followed_signature`: `stored`=`"200:A"`, live `B` ⇒ `_shadow_feedback_stale True` + warning
  text set; live `A` ⇒ `False` + cleared; `stored == ""` ⇒ no warning **and `_followed_signature`
  not called** (cost gate, concern 5); the auto-offer notify carries the STALE marker when stale.
  **Preservation (concern 4):** with flag already `True`, a `_followed_signature` failure
  (returns `None`/raises) leaves the flag `True` and the warning text unchanged, and raises nothing.
- **`tests/test_concern_picker_modal.py`** (extend): `stale=True` renders the banner row;
  `stale=False` (and default) does not — assert via `widget.render().plain` (render-level check).
- Run `bash tests/test_shadow_capture.sh`, `python tests/test_minimonitor_concern_action.py`,
  `python tests/test_concern_picker_modal.py`, `bash tests/test_no_raw_tmux.sh`, and
  `shellcheck .aitask-scripts/aitask_shadow_capture.sh`.

## Verification (end-to-end, manual)

In tmux: launch an agent, `ait minimonitor`, press `e` to spawn a shadow, have the shadow
capture the followed agent (any `/aitask-shadow` flow) so it stamps a sig. Then cause the
followed agent to emit new output → next refresh shows the `⚠ shadow feedback is stale` line and
the `c` concern picker shows the stale banner; with no new output the warning stays clear. (This
live-TUI behavior is the candidate for a manual-verification follow-up in Step 8c.)

## Blast radius / cautions

- New pane-option is set only on shadow panes and dies with them (same lifecycle as
  `@aitask_shadow_target`); `is_shadow_target` semantics are unchanged.
- All new tmux access goes through the gateway (`ait_tmux` in shell, `self._monitor.tmux_run`
  in Python); the allowlisted raw `subprocess.run(["tmux", ...])` in `on_mount` is left alone.
- Signature parity is the one correctness-critical seam — both sides MUST share the
  `aitask_shadow_capture.sh` cleaning path; the `--sig -` parity test pins it.
- Cross-agent: shell + Python only (no `/aitask-shadow` SKILL surface change), so no
  Codex/OpenCode skill port is needed.

## Risk

### Code-health risk: medium
- Auto-stamp is a new side effect on the **shared** capture path
  (`aitask_shadow_capture.sh`, also used by minimonitor's `_capture_shadow_text`);
  a regression there affects every concern-refresh tick · severity: medium · →
  mitigation: in-plan (stamping wrapped `|| true`, default stdout contract preserved
  and asserted by test).
- Signature **parity** is an implicit cross-file contract — an edit to `shadow_clean`
  could silently break the compare, and someone editing it unaware would not see it ·
  severity: medium · → mitigation: in-plan (both sides share the one
  `aitask_shadow_capture.sh` path; the `--sig -` parity test pins it).

### Goal-achievement risk: low
- Benign scrolling could shift the followed pane's default-depth window and yield an
  occasional false "stale" even when the agent has not semantically moved on ·
  severity: low · → mitigation: acceptable — advisory-only signal, no action gated on it.

_No risks warrant a separate before/after mitigation task; all are handled inline
(see "Blast radius / cautions"). `risk_mitigations_planned = false`._

## Post-implementation

Follow task-workflow Step 8 (review) → 8b/8c (offer the manual-verification follow-up above)
→ Step 9 (gates run incl. `risk_evaluated`, archive t1104).
