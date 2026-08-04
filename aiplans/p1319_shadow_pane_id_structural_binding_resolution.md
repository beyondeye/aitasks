---
Task: t1319_shadow_pane_id_structural_binding_resolution.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1319 — Structural pane-id binding resolution for the shadow capture helper

## Context

`t1307` hardened the `aitask-shadow` skill against model-side truncation of
`<followed_pane_id>` (observed: a Codex agent transcribed `%237` down to `%7`).
Being documentation-only by scope, it could only lower the *probability* of a
mis-copy — it left one case entirely unguarded:

> A mangled id that happens to name a **live** pane succeeds. The capture returns
> another agent's screen, no error is raised, the skill's recovery ladder never
> fires, and the shadow advises on the wrong agent's work.

t1307 recorded this as an accepted goal-achievement risk. This task closes it
structurally, with the two mitigations the task specifies — both **script**
changes in `.aitask-scripts/aitask_shadow_capture.sh`, plus the skill-markdown
edits that consume them.

**Intended outcome:** in the normal (spawned) shadow flow the followed pane id
never crosses the model's token stream at all, and if a model passes one anyway
and it disagrees with the pane's authoritative binding, the capture is **refused**
rather than silently served from the wrong pane.

## Design

### Mitigation 1 — binding-based self-resolution (removes the transcription step)

`spawn_shadow` (`.aitask-scripts/monitor/monitor_core.py:2738`) stamps
`@aitask_shadow_target = <followed_pane_id>` on the shadow's own pane. That
option is already the authoritative classifier and lifecycle binding, and
`aitask_shadow_capture.sh::shadow_stamp_analyzed_at()` already reads it from
`$TMUX_PANE` — so self-resolution is a **reuse of an existing lookup**, not new
machinery.

Invoked with **no `<pane_id>`**, the helper resolves the target from its own
pane's binding and captures that. The shadow skill's Step 1 then becomes an
argument-free command.

#### 1a. The binding is only authoritative if `$TMUX_PANE` is on the gateway server

`ait_tmux` targets socket `ait` by default, while `$TMUX_PANE` names a pane on
whatever server the *caller* is attached to. **Pane ids collide across tmux
servers** (`%3` exists on both), so an unvalidated lookup can read a *foreign*
server's `@aitask_shadow_target` and, on the no-arg path, **capture its target
silently** — a wrong-pane capture, i.e. precisely the failure this task exists
to eliminate. (The earlier framing of this as a merely "loud, overridable"
limitation was wrong: the refusal direction is loud, the *resolution* direction
is silent.)

Fix: read the binding **and** the server identity in one call and require them to
agree before treating the option as authoritative.

```bash
# $TMUX is "<socket-path>,<server-pid>,<session-index>".
out="$(ait_tmux display-message -p -t "$own_pane" \
        '#{socket_path}'$'\t''#{@aitask_shadow_target}' 2>/dev/null || true)"
```

- Split on the tab: `sock` = the **gateway** server's socket path, `target` = the
  binding.
- Trust `target` only when `${TMUX%%,*}` (the caller's own socket path) is
  non-empty and **equals** `sock`.
- A mismatch means the caller has a live tmux context we **cannot read** — its
  binding lives on another server. That is *not* the same as "unbound", and
  treating it as such is unsafe on the explicit path (see §2a): it is classified
  as its own state, `cross-server`.
- An unset `$TMUX` (no tmux context at all — an inherited or stale `TMUX_PANE`),
  a failed lookup, or an unsupported format ⇒ **unverifiable**: fails closed on
  the no-arg path, and is treated as `cross-server` on the explicit path when
  `$TMUX_PANE` is nonetheless set. No path degrades to a silent wrong-pane
  capture.

This costs **no extra round-trip** (one `display-message` replaces the current
`show-options`) and is exact — no assumptions about `TMUX_TMPDIR` or socket-name
basenames. `socket_path` / `pid` are tmux ≥ 2.2 formats; local tmux is 3.7b. It
also correctly self-configures for the test-isolation escape hatch
(`AITASKS_TMUX_SOCKET=""` ⇒ no `-L` ⇒ gateway *is* the caller's server ⇒ match).

The same validation now covers the t1104 analyzed-at stamp, which shares the
lookup — a strict improvement (it could previously stamp a foreign pane).

#### 1b. The stamp race is bridged by a bounded, fail-closed wait

`spawn_shadow` **launches at `monitor_core.py:2720` and stamps at `:2738`** — the
shadow's process starts before the binding exists. "SKILL.md Step 0 greets first,
so seconds elapse" is an assumption about model behavior, not a runtime
guarantee, and must not be what the design rests on.

On the **no-arg path only**, poll for the binding for a bounded budget:
`SHADOW_BIND_WAIT_MS` (default `2000`, polled every 100 ms; `0` disables). After
the budget it still **dies** — fail-closed is preserved, never a fallback guess.
The explicit-argument path and the conflict guard use a **single-shot,
non-waiting** lookup, so no TUI capture is ever delayed.

This is verified by an **ordering test that reproduces the real launch order**
(see Tests §5), not deferred to a follow-up.

### Mitigation 2 — wrong-pane collision refusal (catches the silent case)

When an explicit `<pane_id>` is given, decide from the caller's own pane state.
This is the only check that can catch a truncated id colliding with a
live-but-wrong pane, because that path produces a *successful* capture and no
error.

| Caller's own pane | Decision |
|---|---|
| `TMUX_PANE` unset — no tmux context at all | **allow** (nothing can contradict the argument) |
| same server, binding empty | **allow** — a true unbound gateway caller |
| same server, binding **==** argument | **allow** |
| same server, binding **!=** argument | **refuse**, exit 2 — conflicting binding |
| `cross-server` (different server, or server unverifiable while `TMUX_PANE` is set) | **refuse**, exit 2 — cross-server |

`--any-pane` overrides both refusals.

#### 2a. Why `cross-server` must refuse, not fall through to "unbound"

Treating a cross-server caller as unbound reopens the exact hole: a shadow whose
own pane lives on server B, handed a truncated id that happens to name a live
pane on the **gateway** server, would have its binding silently unreadable, the
guard silently skipped, and the wrong pane silently captured. Refusing makes a
cross-server capture an **explicit choice** (`--any-pane`) instead of an
unnoticed default, while leaving genuine unbound *gateway* callers untouched.

**Blast-radius survey — one framework caller legitimately reads across contexts
and must opt out explicitly:**

| Caller | Own pane | Effect |
|---|---|---|
| shadow skill Step 1 / `plan-*` / `impl-challenge` | shadow pane, bound, gateway | no arg → self-resolves; matching arg → allowed |
| `capture_shadow_text` (`monitor_core.py:460`, both TUIs) | TUI pane, never stamped — but a TUI run from the user's **personal** tmux while the framework is on `-L ait` is `cross-server` | **passes `--any-pane`** (see below) |
| `aitask-learn-skill` in a learner pane | learner pane — `aitask_shadow_spawn_learner.py:19` documents it "carries NO `@aitask_shadow_target`"; spawned via the gateway, so same server | allowed unchanged; a *manually* run learner in a foreign tmux is refused **loudly**, with `--any-pane` named in the error |
| manual shell invocation | unbound / no tmux | allowed |

**`capture_shadow_text` opts out — narrowly and on purpose.** Its pane id is
machine-supplied (`find_shadow_pane`), never model-transcribed, so the guard
protects nothing there; meanwhile it sends stderr to `DEVNULL` and returns `None`
on a non-zero exit, so a refusal would surface as a **silent "no concerns"** in
the picker. Add `--any-pane` to its argv at `monitor_core.py:466` with a comment
stating both halves of that reasoning. It is the only opt-out in the codebase.

## Changes

### 1. `.aitask-scripts/aitask_shadow_capture.sh`

- **New `shadow_self_target()`** — the validated single-shot lookup of §1a.
  Echoes this pane's `@aitask_shadow_target`, or empty when unverifiable.
  **Must keep the literal line `[[ -n "$own_pane" ]] || return 0`** —
  `tests/test_shadow_seam.py:260` source-pins that exact string.
- **New `shadow_wait_self_target()`** — §1b bounded poll around
  `shadow_self_target()`; used **only** by the no-arg path.
- **Rewrite `shadow_stamp_analyzed_at()`** to take the already-resolved value:
  `shadow_stamp_analyzed_at <pane> <self_target>`, falling back to
  `shadow_self_target()` when `$2` is absent. **Must keep the literal comparison
  `"$self_target" == "$pane"`** — pinned by `test_shadow_seam.py:261`. Computing
  it once in `main()` keeps the tmux call count at today's level.
- **`main()`**: add `--any-pane`; after option parsing,
  - `pane == "-"` → unchanged (stdin; no resolution, no guard, no stamp).
  - `pane` empty → `shadow_wait_self_target()`. Non-empty ⇒ use it and print
    `resolved followed pane <id> from @aitask_shadow_target` to **stderr**
    (stdout must stay pure capture text — note `info()` in
    `lib/terminal_compat.sh` writes to *stdout*, so use a direct `printf … >&2`).
    Empty ⇒ `die` with a message that **keeps the substring `pane id required`**
    (the existing test asserts it):
    `pane id required: no <pane_id> argument and no @aitask_shadow_target binding on this pane`.
  - `pane` non-empty and `--any-pane` not given → the §2 decision table.
    `die_code 2` (from `lib/terminal_compat.sh`) for both refusals, with
    **distinct messages**: the conflict case names both ids and says "re-run with
    no argument"; the cross-server case says the caller's pane is on a different
    tmux server so its binding cannot be verified. Both name `--any-pane`. The
    distinct exit code makes the guard programmatically discriminable.
- `shadow_self_target()` must therefore return a **tri-state**, not a bare
  string: `bound:<id>` / `unbound` / `cross-server`. A bare-string return cannot
  distinguish "verified unbound" from "could not verify", which is exactly the
  conflation §2a exists to prevent (scope-honest return, not a collapsed
  boolean).
- Update the header block and `show_help()`: no-arg form, `--any-pane`,
  `SHADOW_BIND_WAIT_MS`, exit code 2, both refusal reasons, and the
  gateway-server validation rule.

### 1bis. `.aitask-scripts/monitor/monitor_core.py`

`capture_shadow_text` (line ~466): `str(script), "--deep", "--any-pane", shadow_pane`,
with the two-part comment from §2a (machine-supplied id ⇒ guard protects nothing;
`DEVNULL` + `None`-on-nonzero ⇒ a refusal would be a silent "no concerns").

Two test classes pin this argv and **both** must be updated in the same commit:
- `tests/test_shadow_seam.py:236,242` — `rec["argv"][1:] == ["--deep", "%5"]`
- `tests/test_minimonitor_concern_action.py:320,328` — same assertion via `mm.`

Extend one of them with an assertion that `--any-pane` is present *and* a
docstring stating why, so the opt-out cannot be dropped or copied elsewhere
unnoticed.

### 2. `.claude/skills/aitask-shadow/SKILL.md.j2` — Step 1

- Primary command becomes argument-free:
  `./.aitask-scripts/aitask_shadow_capture.sh` (and `--deep` for plan reads).
- Replace the 3-step recovery ladder. Its step 1 (raw
  `tmux show-options … @aitask_shadow_target`) now lives **inside** the helper, so
  it is deleted; the remaining ladder handles the explicit-id path only:
  - `pane id required: …no @aitask_shadow_target binding…` → not a bound shadow
    pane (manual invocation): re-run with the id you were given, **verbatim**.
  - `refusing to capture …` (exit 2) → you passed a non-bound id: drop the
    argument and re-run with none.
  - `can't find pane: <id>` on the explicit path → `tmux list-panes`, accept
    **only an exact match**, else **stop and ask the user** (unchanged; a
    truncation is not invertible).
- Rewrite the closing "note the limit of the exact-match rule" paragraph — that
  residual hazard is now closed by the helper. Current-state prose only, per
  `documentation_conventions.md`.
- Keep the `<followed_pane_id>` **argument contract** in the Arguments section —
  the launcher still passes it, `spawn-learn-skill.md` needs it, and it is the
  manual-invocation fallback.

### 3. Deep-capture sub-procedures — all five go argument-free

`plan-explain.md`, `plan-challenge.md`, `plan-socratic.md`,
`plan-assumptions.md` (each ~line 11–16) and `impl-challenge.md:72`: change
`--deep <followed_pane_id>` → `--deep`, with a short clause that the helper
resolves the bound followed pane and an explicit id is only needed if Step 1 also
needed one. `plan-diagnose-errors.md:15` already shows no argument — leave it.

### 4. Docs

- `aidocs/framework/shadow_agent.md` — pipeline item 1 (capture) gains the
  resolution order; add a **"Rule: the validated pane binding, not the argument,
  is the source of truth"** subsection under "Spawn path and binding" covering
  the gateway-server check, the three-way explicit-path decision, the single
  sanctioned `--any-pane` opt-out and why it exists, the bounded wait, and the
  launch↔stamp order it bridges. Update the "Feedback freshness" stamp bullet to
  mention the shared validated lookup.
- `.claude/skills/aitask-learn-skill/SKILL.md` (~line 64) — one sentence: a
  learner run from a tmux server other than the framework's is refused with exit
  2 and can pass `--any-pane`. Static skill, no goldens.
- No `CLAUDE.md` change needed. `.agents/` / `.opencode/` shadow wrappers are
  pure redirects — **no port**.

### 5. Goldens (same commit — `skill_authoring_conventions.md`)

`SKILL.md.j2` and `impl-challenge.md` both carry Jinja, so regenerate:

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-shadow/SKILL.md.j2 \
    "aitasks/metadata/profiles/$profile.yaml" claude \
    > "tests/golden/skills/aitask-shadow/SKILL-${profile}-claude.md"
done
```

plus the three `tests/golden/procs/aitask-shadow/impl-challenge-<profile>.md`
(mirror the proc-golden invocation used by
`tests/test_skill_render_aitask_shadow.sh`). **Review the golden diff** — it must
contain only the capture-line changes; anything else is a render regression.

### 6. `tests/test_shadow_capture.sh`

All new cases extend the existing live-tmux pattern (isolated socket,
poll-for-pane, `SKIP` when tmux is unavailable). **Every fixture that sets
`TMUX_PANE` must now also set `TMUX`** to the fixture server's real identity,
because the §1a validation (correctly) distrusts a `TMUX_PANE` with no server
behind it. Derive it with an **explicit `-t` target**:

```bash
TMUX="$(tmux -L "$SOCK" display-message -p -t "$shadow" '#{socket_path},#{pid},0')"
```

The `-t` is load-bearing, not decoration: the fixture servers are created
detached (`new-session -d`), so a bare `display-message -p` falls back to tmux's
implicit "current" target — which has no client to resolve against and can fail
or silently resolve to a different session once the fixture has more than one.
That would make these very tests flaky or vacuous. `socket_path` and `pid` are
**server-scoped**, so any known-good pane on that server (`$shadow`, `$followed`,
or server B's pane for the cross-server fixture) yields the same identity — pin
one and use it everywhere the plan derives a server identity.

This includes **updating the existing t1104 analyzed-at fixture**, which sets
`TMUX_PANE` without `TMUX` today and would otherwise stop stamping.

Fixture: three panes on one throwaway socket — `followed` printing
`FOLLOWED_SENTINEL`, `other` printing `OTHER_SENTINEL`, `shadow` (sleep) stamped
`@aitask_shadow_target = $followed`.

1. **no-arg + binding** → stdout contains `FOLLOWED_SENTINEL`.
2. **no-arg + option unset** (`TMUX_PANE=$other`) → non-zero, stderr contains
   `pane id required`, stdout empty.
3. **explicit id == binding** → contains `FOLLOWED_SENTINEL`.
4. **explicit id conflicts** (`TMUX_PANE=$shadow … "$other"`) → exit **2**, stderr
   names both ids, **stdout empty**.
5. **negative control / override** — same call with `--any-pane` → contains
   `OTHER_SENTINEL`. This is what proves case 4 discriminates: without the guard
   that invocation really does capture the wrong pane.
6. **same-server unbound caller + explicit id is never refused**
   (`TMUX_PANE=$other … "$followed"`) → succeeds. Pins that a genuine unbound
   gateway caller (learner pane, TUI on the gateway server) stays unaffected.
7. **cross-server caller** — start a *second* throwaway server whose pane carries
   an `@aitask_shadow_target`, and choose ids that **collide** with the first
   server's. Invoke with `TMUX`/`TMUX_PANE` pointing at server B (its `TMUX`
   derived with `-t <B's pane>`, per the rule above) while `AITASKS_TMUX_SOCKET`
   points at server A. Three assertions:
   - no-arg → **fails closed** (`pane id required`), never captures B's target;
   - explicit id → **refused**, exit 2, stderr says "different tmux server",
     stdout empty;
   - explicit id **+ `--any-pane`** → captures A's pane (the deliberate override).

   This is the executable proof of §1a **and** §2a: without the socket check the
   no-arg call captures the foreign target, and without the cross-server refusal
   the explicit call silently captures the colliding gateway pane.
8. **launch-order race (§1b)** — reproduce production ordering exactly: create
   `followed`, then `split-window` a pane whose command is
   `aitask_shadow_capture.sh > out.txt 2>&1; sleep 30` (**started before any
   stamp**), then stamp `@aitask_shadow_target` on the new pane *after* the split
   returns — mirroring `launch_in_tmux` → stamp. Poll `out.txt`; it must contain
   `FOLLOWED_SENTINEL`. **Negative control:** the same fixture with
   `SHADOW_BIND_WAIT_MS=0` must produce the `pane id required` error instead —
   proving the bounded wait is what bridges the race *and* that fail-closed
   survives. Pass `AITASKS_TMUX_SOCKET` explicitly in the pane command rather than
   relying on server-env inheritance.

Also make the existing argument-validation block hermetic: run those `$CAPTURE`
invocations under `env -u TMUX_PANE -u TMUX` so "no args ⇒ error" cannot flip
when the suite is run from inside a bound shadow pane.

## Verification

```bash
bash tests/test_shadow_capture.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_skill_render_aitask_shadow.sh
bash tests/run_all_python_tests.sh --test-dir tests   # test_shadow_seam.py source pins
shellcheck .aitask-scripts/aitask_shadow_capture.sh
./.aitask-scripts/aitask_skill_verify.sh
```

Prove each new guard can actually fail (not merely that the happy path passes) —
**one mutation at a time**, restoring by undoing exactly that edit (never
`git checkout`, which would sweep in a concurrent session's work):

- **Conflict guard** — delete the conflicting-binding branch; case 4 must fail.
- **Socket validation** — drop the `${TMUX%%,*}` comparison; case 7's no-arg
  assertion must fail.
- **Cross-server refusal** — collapse `cross-server` back into `unbound` on the
  explicit path (the exact defect this revision fixes); case 7's explicit-id
  assertion must fail while cases 4 and 6 still pass.
- **Bounded wait** — set the budget to 0 in the code; case 8 must fail while
  case 1 still passes (the two are independent).
- **Framework call-site smoke** — `tests/test_minimonitor_concern_smoke.py`
  exercises the real `pane → aitask_shadow_capture.sh → capture_shadow_text`
  chain; run it to confirm the explicit-id TUI path is neither refused nor
  slowed.

`tests/test_monitor_shadow_spawn_live.sh` is **not** run here: it refuses inside
tmux and refuses while the `-L ait` server holds panes, both of which are true in
this session. Case 8 covers the same ordering fact at the tmux level without that
precondition; the real agent-CLI spawn is covered by the manual-verification
follow-up below.

Then **Step 9 (Post-Implementation)** for cleanup, gate verification, and archival.

## Risk

### Code-health risk: medium
- The guard could refuse a call site the survey missed, breaking the minimonitor
  concern picker (which degrades to a **silent** "no concerns" on a non-zero
  exit). Widened by the cross-server refusal, which fires on caller *placement*
  rather than on a mangled id · severity: medium · → mitigation: survey completed
  across all call sites; `capture_shadow_text` opts out explicitly at
  `monitor_core.py:466`; case 6 pins "same-server unbound is never refused"; the
  concern smoke test is an explicit verification step.
- `--any-pane` at the TUI call site is a standing bypass that a later caller
  could cargo-cult, re-opening the hole it is scoped out of · severity: medium ·
  → mitigation: it is the only opt-out in the codebase, carries a two-part
  why-comment, is asserted with a rationale docstring in the argv pin, and is
  documented in `shadow_agent.md` as the single sanctioned exception.
- The refactor must preserve two strings source-pinned by
  `tests/test_shadow_seam.py:260-261`, and the new server validation changes when
  the t1104 stamp fires · severity: medium · → mitigation: both literals are
  called out as must-keep in the change list; the existing live stamping test
  (with its corrected `TMUX` fixture) covers both the stamp and no-stamp branches.

### Goal-achievement risk: low
- The launch↔stamp race could leave the no-arg path unresolved, silently pushing
  the flow back to the explicit-id path this task exists to remove · severity:
  medium · → mitigation: shadow_no_arg_capture_live_verification (in-plan: the
  bounded wait of §1b, proven by the ordering test case 8 and its
  `SHADOW_BIND_WAIT_MS=0` negative control).
- Argument-free markdown may still be ignored by a model that transcribes the id
  anyway — and the **learner-spawn path** (`spawn-learn-skill.md` →
  `aitask_shadow_spawn_learner.py`) has no argument-free form at all, so it keeps
  the full mangle hazard · severity: low · → mitigation:
  shadow_learner_pane_id_binding_resolution (in-plan, capture path only:
  mitigation 2 refuses a mangled id instead of capturing).

### Planned mitigations
- timing: after | name: shadow_learner_pane_id_binding_resolution | type: enhancement | priority: medium | effort: low | addresses: goal-achievement — the learner-spawn path still transcribes `<followed_pane_id>` through the model | desc: Teach `aitask_shadow_spawn_learner.py` to resolve the followed pane from its own pane's validated `@aitask_shadow_target` when invoked with no pane argument (reusing t1319's gateway-server-checked lookup), and make `spawn-learn-skill.md` Step 2 argument-free.
- timing: after | name: shadow_no_arg_capture_live_verification | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement — the launch↔stamp race, at the real agent-CLI layer | desc: Spawn a real shadow from minimonitor (`e`) against a live agent and confirm its first argument-free `aitask_shadow_capture.sh` call resolves the bound followed pane with no error. t1319's case 8 proves the tmux-level ordering on a throwaway socket; this covers the real code-agent boot path, which no automated test in this repo can run inside tmux.
