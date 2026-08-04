---
Task: t1308_fix_t633_unscoped_kill_server_instruction.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1308 — Fix t633's unscoped `tmux kill-server` instruction

## Context

`aitasks/t633_manual_verification_force_exact_tmux_targeting_followup.md` is a
manual-verification checklist (labelled `tmux_destructive`) whose first item
reads:

```
- [ ] tmux kill-server to clear all sessions
```

Written 2026-04-23, ~7 weeks before **t953** moved every `ait`-managed tmux
session onto a dedicated socket, it has silently rotted into an instruction that
is **destructive to the wrong target and ineffective for its stated purpose**: a
person following it literally kills every pane in their *personal* tmux server —
including code agents running there — while the `ait` sessions the step means to
clear keep running. Item 5 (`tmux list-sessions`) has the same rot.

Outcome: t633's checklist targets the same server `ait ide` does, is safe to
follow, and does what it claims.

## Verified facts this plan is built on

| Fact | Evidence |
|---|---|
| `ait ide` resolves its server from `AITASKS_TMUX_SOCKET`, not from a literal `ait` | `aitask_ide.sh:72` calls `ait_tmux_socket_name()` |
| Socket semantics: unset → `-L ait`; non-empty → `-L <value>` (`default` → `-L default`); set-but-empty → **no flag** (follows `$TMUX`) | `tmux_exec.py:70-91`, `tmux_exec.sh:53-64`; confirmed by running the emitter under all three cases |
| **One** ait server is shared by *all* aitasks projects | `AIT_DEDICATED_SOCKET` comment, `tmux_exec.py:62-65` |
| `source .aitask-scripts/lib/tmux_exec.sh` works standalone (bash), exporting `ait_tmux` | ran it; `ait_tmux_socket_name` → `ait`, emitter → `-L ait` |
| With no server on the socket, `kill-server` **and** `list-sessions` exit **1** with `error connecting to …` | probed on a throwaway socket `ait_probe_t1308_nonexistent` |
| Checklist items must be **one physical line**; a `> `-quoted or fenced line inside the section is inert; ` — ` is only stripped when followed by `PASS\|FAIL\|… YYYY-MM-DD HH:MM` | `aitask_verification_parse.py` `ITEM_RE`, `PLAIN_ITEM_RE`, `_strip_annotation` (t1208) |
| Nothing outside t1308 references t633 or its item indices | `grep -rln 't633\b' aitasks/ aiplans/` |

## Scope

Task-data only — one markdown file, no code. Commit with `./ait git`.

## Change

**File:** `aitasks/t633_manual_verification_force_exact_tmux_targeting_followup.md`

### 1. New `## Socket setup (do this first)` section, immediately *before* `## Verification Checklist`

Placed **outside** the parsed section, so the checklist section stays pure
items. It replaces "substitute the flag yourself" portability prose with a
derivation that is correct for every `AITASKS_TMUX_SOCKET` value, reusing the
sanctioned shell gateway (`lib/tmux_exec.sh` — the same seam
`tests/test_no_raw_tmux.sh` enforces) rather than a hard-coded flag:

~~~markdown
## Socket setup (do this first)

`ait ide` picks its tmux server from `AITASKS_TMUX_SOCKET` via
`ait_tmux_socket_name()` (unset → the dedicated `ait` socket, t953; non-empty →
that socket; set-but-empty → no flag, follows `$TMUX`). Every tmux command in the
checklist must hit the **same** server, so derive it from the same gateway
instead of hard-coding a flag. In the shell you will run the checklist from
(bash — start one with `bash` if your shell is something else):

```bash
cd <project A root>
source .aitask-scripts/lib/tmux_exec.sh
printf 'socket=[%s] flags=[%s] TMUX=[%s]\n' \
  "$(ait_tmux_socket_name)" "$(ait_tmux_socket_args | tr '\n' ' ')" "${TMUX:-not inside tmux}"
```

**Read that line before running anything destructive:**

- `socket=[ait]` (or another name) → good: every `ait_tmux` command is pinned to
  that named server.
- `socket=[]` with `flags=[]` → **STOP.** `AITASKS_TMUX_SOCKET` is set but empty
  (the legacy test-harness escape hatch), so tmux takes no socket flag and
  follows `$TMUX` — inside a pane that is *the server this pane lives on*, which
  may be your personal one. The kill step below would then destroy the session
  you are running the checklist from. Fix it before continuing: `unset
  AITASKS_TMUX_SOCKET` (recommended — restores the dedicated `ait` socket) or set
  it to a socket name, then re-source.
- `TMUX=[…]` non-empty → you are inside a tmux pane. Run the destructive steps
  from a plain terminal instead; if that pane belongs to the target server, the
  kill takes your own shell with it mid-checklist. (`$TMUX`'s first field is the
  socket path — compare it against the socket named above.)

Then use `ait_tmux <verb>` wherever the checklist says so, and re-source in any
new shell. Do **not** swap in a plain `tmux` invocation: without the resolved
socket flags it targets your personal default server, which is neither the
server `ait ide` uses nor the one these steps assert about.

When no server exists on the resolved socket, `ait_tmux` exits 1 with
`error connecting to …` / `no server running on …`. In this checklist that
message means "no ait sessions" — a clean slate, **not** a failure.
~~~

### 2. Split the destructive step into a preflight item + a gated kill item

Old item 1 becomes two items, so the blast radius is inspected and accepted
*before* anything is destroyed, and the no-server state has a defined outcome:

~~~markdown
- [ ] **Preflight for the destructive step:** complete **Socket setup** above first — its `socket=…` line must name a real socket (never empty) and you must be running from a shell outside the target server. Then run `ait_tmux list-sessions` and read every line: ONE ait server is shared by ALL aitasks projects, so this lists other projects' sessions and any code agents running in them. Pass this item only once you have confirmed that losing every session listed is acceptable; if it reports no server, you are already at a clean slate.
- [ ] `ait_tmux kill-server` to clear all ait sessions — run it ONLY after the preflight above confirmed nothing you still need is running, because it terminates every session on the shared ait server, not just this project's. If the preflight found no server, mark this item Skip; a no-server message here means the same thing and is not a failure.
~~~

### 3. Rewrite the list-sessions item (old item 5)

~~~markdown
- [ ] `ait_tmux list-sessions` should show both sessions (a plain `tmux` invocation would read your personal default server and show neither)
~~~

### 4. Leave the remaining items unchanged

Items 2, 3, 4, 6, 7, 8 contain no tmux invocation (`ait ide`, `Ctrl-b d`, TUI
switching, brainstorm, companion panes). Re-read for the same rot: the framework
ships no tmux `prefix` override (`seed/tmux.conf` has none), so `Ctrl-b d`
remains correct.

Final checklist length: **9 items** (was 8).

### 5. Bump `updated_at` in t633's frontmatter to the current `YYYY-MM-DD HH:MM`

### Wording rule applied throughout

No line reproduces a bare `tmux <verb>` as something to run — the warnings say
the socket flags must not be omitted and refer to "a plain `tmux` invocation",
so a literal audit cannot mistake warning prose for an instruction. Every
executable tmux step reads `ait_tmux <verb>`.

## Not doing

- `aitasks/archived/t632_force_exact_tmux_session_targeting.md:104,108` carries the
  same stale instruction. It is an **archived** record of what was true when
  written; rewriting archived history is not this task's job, and t1308's AC
  scopes the fix to t633.
- No source-scan guard for unscoped `tmux` verbs in task files: t633 is the only
  active file with the defect (`t1078` and the website docs already use `-L ait`),
  so a guard would be enforcement without a population.

## Verification

1. **Checklist parses cleanly and the new item is a real item** (baseline before
   the edit was `TOTAL:8 PENDING:8`):
   ```bash
   python3 .aitask-scripts/aitask_verification_parse.py parse \
     aitasks/t633_manual_verification_force_exact_tmux_targeting_followup.md
   python3 .aitask-scripts/aitask_verification_parse.py summary \
     aitasks/t633_manual_verification_force_exact_tmux_targeting_followup.md
   ```
   Expect 9 `ITEM:` lines in checklist order, each with its full text on one
   line (no truncation → no accidental wrap), and
   `TOTAL:9 PENDING:9 PASS:0 FAIL:0 SKIP:0 DEFER:0`.

2. **AC 1 + AC 2 — no bare tmux invocation survives** (word-boundary check, so
   `ait_tmux …` is correctly excluded rather than falsely flagged):
   ```bash
   grep -nE '(^|[^_[:alnum:]])tmux[[:space:]]+(kill-server|list-sessions|kill-session|new-session|attach|has-session)' \
     aitasks/t633_manual_verification_force_exact_tmux_targeting_followup.md   # must print NOTHING
   grep -c 'ait_tmux' aitasks/t633_manual_verification_force_exact_tmux_targeting_followup.md   # >= 5
   ```
   Prove the check discriminates: the same first grep run against the **pre-edit**
   file (`git show HEAD:<path>`) must print the two offending lines.

3. **The instructions I am writing actually work** — run the setup snippet
   verbatim (read-only) and confirm both documented outcomes:
   ```bash
   bash -c 'source .aitask-scripts/lib/tmux_exec.sh; ait_tmux list-sessions; echo "rc=$?"'
   ```
   Must either list this box's ait sessions, or print
   `error connecting to …` with `rc=1` — the state item 1 tells the verifier to
   read as "clean slate".

4. **The STOP condition fires when it should** (negative control for the guard —
   read-only, resolves flags without running any tmux verb):
   ```bash
   bash -c 'source .aitask-scripts/lib/tmux_exec.sh; printf "socket=[%s] flags=[%s]\n" \
     "$(ait_tmux_socket_name)" "$(ait_tmux_socket_args | tr "\n" " ")"'                      # socket=[ait]  → proceed
   AITASKS_TMUX_SOCKET= bash -c 'source .aitask-scripts/lib/tmux_exec.sh; printf "socket=[%s] flags=[%s]\n" \
     "$(ait_tmux_socket_name)" "$(ait_tmux_socket_args | tr "\n" " ")"'                      # socket=[] flags=[] → STOP
   ```
   The second form must print the empty pair the guard keys on; if it did not,
   the guard text would be unreachable prose.

5. **AC 3 — original intent preserved:** the checklist still opens by reaching a
   clean slate of ait sessions before `ait ide` is exercised.

6. **Frontmatter intact:** step 1's commands read the frontmatter and would fail
   on a malformed file; additionally `./.aitask-scripts/aitask_ls.sh -v 15` must
   still list t633 normally.

## Risk

### Code-health risk: medium
- The `AITASKS_TMUX_SOCKET`-set-but-empty escape hatch makes `ait_tmux` follow `$TMUX`, so a verifier running the kill step from inside a tmux pane would destroy the server that pane lives on — possibly their personal one · severity: high if unguarded · → mitigation: none needed as a follow-up task — the Socket setup section resolves and *prints* the socket name/flags plus `$TMUX` before anything destructive, hard-STOPs on an empty socket, and tells the verifier to run from outside the target server; the preflight item requires that setup to have passed, and verification step 4 is a negative control proving the STOP condition is reachable. Residual risk is that the guard is prose a human must obey, not code.
- The checklist now depends on a framework symbol (`ait_tmux` in `.aitask-scripts/lib/tmux_exec.sh`) rather than a literal command, so renaming that helper would rot the checklist again — quietly · severity: low · → mitigation: none needed — `lib/tmux_exec.sh` is the sanctioned public shell seam (enforced by `tests/test_no_raw_tmux.sh`), a rename would already have to sweep `grep -rl ait_tmux`, and this file is caught by that sweep; the alternative (a hard-coded flag) is exactly the failure mode being fixed.
- The parsed `## Verification Checklist` section gains one item and the setup prose sits outside it, so `aitask_verification_parse.py` indexing shifts by one · severity: low · → mitigation: none needed — nothing outside t1308 references t633 or its indices (verified), all items are `pending` with no recorded state to invalidate, and verification step 1 re-parses.

### Goal-achievement risk: low
- A verifier whose shell is zsh/fish cannot `source` the bash gateway · severity: low · → mitigation: none needed — the setup section tells them to start `bash` first, and verification step 3 runs the snippet as written.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`, `create_worktree: false`) — no worktree or
branch cleanup. Gate orchestrator runs `risk_evaluated`; then archive t1308 via
`./.aitask-scripts/aitask_archive.sh 1308` and `./ait git push`.
