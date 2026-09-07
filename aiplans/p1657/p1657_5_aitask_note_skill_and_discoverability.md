---
Task: t1657_5_aitask_note_skill_and_discoverability.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_6_documentation_website_and_aidocs.md, aitasks/t1657/t1657_7_manual_verification_task_note_mailbox.md
Archived Sibling Plans: aiplans/archived/p1657/p1657_1_promote_ledger_block_substrate.md, aiplans/archived/p1657/p1657_2_inbox_format_and_ait_note_writer.md, aiplans/archived/p1657/p1657_3_read_receipts_and_pick_surfacing.md, aiplans/archived/p1657/p1657_4_live_endpoint_resolution_infrastructure.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-07 17:14
---

# p1657_5 — Discoverability: the `aitask-note` skill and always-loaded surfaces

## Context

`ait note` shipped in t1657_2 and its live lane in t1657_4. Both work. **No agent
knows they exist.** Verified this session: `ait note` appears in *zero*
always-loaded instruction surfaces — not `seed/aitasks_agent_instructions.seed.md`,
not `AGENTS.md`, not `CLAUDE.md`, not `.codex/instructions.md`, not
`.opencode/instructions.md`. The only prose anywhere teaches the **read** side, and
only inside `aitask-pick` / `task-workflow` skill bodies. The *sending* side is
reachable today only by someone who already knows the verb.

This child closes that, and it is also the **single composition point** binding
writer → resolver → adapter. t1657_4 relocated two acceptance criteria here
(durable-first ordering; post-write adapter failure reported as success) because
only the composition owner can assert them.

## What the verify pass changed

The plan was written 2026-09-01, before _2/_4 landed. Three corrections:

1. **The `ait-git` precedent does not support "Claude-only".** `ait-git` is
   `user-invocable: false` — that is *why* it has no wrappers. All 33
   user-invocable skills in this repo ship `.agents/` + `.opencode/` wrappers;
   the only Claude-only skills are the three non-invocable helpers (`ait-git`,
   `user-file-select`, `task-workflow`). **Decision (confirmed): ship the
   wrappers here.** They are pointers to the Claude source of truth, not ports.
   No port follow-up is spawned.
2. **The composition needed an executable seam.** Both relocated ACs describe an
   *ordering*, and prose cannot enforce one. **Decision (confirmed): fuse steps
   2–3 into an opt-in `--with-live` mode on the already-shipped
   `aitask_note.sh`** (§2). No new script → no whitelist touchpoints → no
   collision with the roadmap work currently uncommitted in this tree.
3. **Two trigger sites sit inside Jinja conditionals.** `task-workflow` Step 8d
   is inside `{%- if 'risk_evaluated' in rendered_set %}`; `aitask-review`
   Step 5 is inside `{% if profile.review_auto_continue %}`. An offer placed
   literally inside either renders in one branch and vanishes in the other.
   Every offer goes **outside** its conditional, verified against the rendered
   output, not the template.

Two further gaps came out of plan review, both now closed in Verification: the
suite proved only the *degraded* live branches (§V.3 adds the positive
`LIVE_PANE` case against a real pane, plus a t1657_7 item for the adapter
handoff), and goldens cannot prove an offer survives every profile because a
golden *is* the render (§V.7 adds 10 per-profile assertions).

Also verified: `aitask_note.sh` and `aitask_live_endpoint.sh` are already
whitelisted in all 5 touchpoints (`audit-helper-whitelist` returns empty for
both); `related-task-discovery.md` is Jinja-free and self-contained, with
`aitask-contribution-review` (a static skill) as the precedent for calling it by
absolute path; a static skill with no `.j2` is explicitly sanctioned
(`skill_authoring_conventions.md:218`) and is invisible to `aitask_skill_verify.sh`
and to the wrapper parity audit.

**Collision check.** Another session holds uncommitted work in this tree
(`aitask-backlog-roadmap`: the 5 whitelist files, `docs/README.md`,
`website/content/docs/skills/_index.md`, `.gitignore`, two `lib/*.py`). **This
plan touches none of those paths.** Every commit is path-scoped to files listed
below.

---

## 1. Always-loaded surfaces (layer 1 — the guarantee that needs no invocation)

### `seed/aitasks_agent_instructions.seed.md`

Add one `## Sending Notes to Other Tasks` section between the existing
`## Git Operations on Task/Plan Files` (:56–67) and `## Commit Message Format`
(:68). Match the seed's voice: imperative, hard-wrapped ~72 cols, backticked
identifiers, a "say this, never that" closer. Content, ~20 lines:

- the verb and its shape — `./ait note <target-task-id> --from <your-task-id>
  --text "…"`, and `--file -` with a **quoted** heredoc for a multi-line body
  (the house convention, same as `--desc-file -`);
- **when** — context a task that *already exists* needs, that is not itself
  work. If the content is work, create a task instead;
- what comes back — `NOTE_APPENDED:<note-id>|<path>` is the durable, committed
  result and is authoritative;
- the sender's obligation — hedge *moment-relative* claims (a `git status`
  reading); a `base` SHA fixes tree-relative staleness only;
- the receiving posture in one line — a note is advisory, `from=` is a claim,
  and it never bypasses the reader's own planning, gates or review.

### Regenerate all three mirrors — drive the generator

Never copy from `AGENTS.md`: it carries the shared layer only and a verbatim copy
destroys each mirror's `## Agent Identification` tail.

```bash
source .aitask-scripts/aitask_setup.sh --source-only
update_agentsmd .
for agent in codex opencode; do
  case "$agent" in
    codex)    target=.codex/instructions.md ;;
    opencode) target=.opencode/instructions.md ;;
  esac
  content="$(assemble_aitasks_instructions . "$agent")"
  insert_aitasks_instructions "$target" "$content"
done
```

Guarded byte-for-byte by `tests/test_agent_instructions.sh` T25–T27 (`cmp`
against the live generator). Run it after the edit — drift is a failing test.

### `CLAUDE.md` (hand-maintained; sentinel-guarded, `ait setup` leaves it alone)

Add the same section after `## Git Operations on Task/Plan Files` (:228–244),
before `## Working on Skills / Custom Commands` (:246) — the existing home for
"which `ait` verb, and why". Add the `/aitask-note` skill pointer, which the seed
version omits (the seed is agent-neutral).

---

## 2. `aitask_note.sh --with-live` — the executable composition seam

Opt-in. **The default path is byte-identical**, so every current caller and the
"exactly one line on stdout" contract are untouched.

Insert after the terminal `printf 'NOTE_APPENDED:…'` (`aitask_note.sh:1017`):

- Run only on a **successful** durable write (`NOTE_APPENDED:`). On
  `NOTE_APPENDED_UNCOMMITTED:` / `NOTE_TARGET_MISSING:` / `NOTE_SELF:` /
  `NOTE_ERROR:` the resolver is **not invoked at all** and stdout stays one
  line. This is what makes "step 2 completes before step 3 begins" structural
  rather than advisory.
- Then `aitask_live_endpoint.sh <target>`, and print its **first stdout line
  verbatim** as line 2.
- **Never remap a reason code.** `LIVE_NONE` and `LIVE_ERROR` are disjoint by
  t1657_4's design; passing through preserves that.
- If the resolver is missing, non-executable, or emits no line matching
  `^LIVE_(PANE|NONE|ERROR):`, emit `LIVE_ERROR:resolver_unavailable`. An empty
  parse is not a result.
- **Exit status follows the durable lane alone** — 0 whenever the note landed,
  whatever the live lane said. This is "the durable result is authoritative"
  made executable.
- New documented test seam `AIT_LIVE_ENDPOINT_SH` (overrides the resolver path),
  mirroring `AIT_LIVE_DELIVERY_DIR`.

### The capture must be errexit-safe — this is the load-bearing detail

`aitask_note.sh:34` is `set -euo pipefail`, and the resolver **deliberately
exits 2** on `LIVE_ERROR:*` (`aitask_live_endpoint.sh:222`, `:225`, `:253`). A
plain invocation or a bare `$( )` therefore aborts the script *after* the append
and commit have already landed — the caller would see `NOTE_APPENDED:`, no line
2, and a non-zero status, breaking both the two-line contract and the
durable-authoritative rule in one go. Two further traps: `local x="$(…)"` masks
the status in `local`'s own exit code, so the `|| rc=$?` never fires; and piping
through `head -n1` re-surfaces the resolver's status via `pipefail`.

```bash
# The resolver's exit 2 is a legitimate ANSWER, not our failure. Declare first,
# assign second (`local x="$(…)"` masks the status). No pipe — pipefail would
# hand the resolver's 2 straight back.
local live_out="" live_rc=0 live_line=""
live_out="$("$LIVE_ENDPOINT_SH" "$target_bare" 2>/dev/null)" || live_rc=$?
live_line="${live_out%%$'\n'*}"
case "$live_line" in
    LIVE_PANE:*|LIVE_NONE:*|LIVE_ERROR:*) ;;
    *)  warn "live endpoint unreadable (exit $live_rc) — note is durable"
        live_line="LIVE_ERROR:resolver_unavailable" ;;
esac
printf '%s\n' "$live_line"
return 0    # DURABLE is authoritative — returned explicitly, never as $?
```

The in-file precedent for the idiom is `aitask_note.sh:484`; the same rule is
spelled out for callers at `tests/test_agent_instructions.sh:94-98`.

Amend the `Output` block in `show_help` (:225–229): one line per lane under
`--with-live`, one line otherwise. Add the flag to the usage and to the
duplicate-option guard set.

```
$ ait note 1657_6 --from 1657_5 --with-live --text "…"
NOTE_APPENDED:2026-09-06T…Z.a1b2…|aitasks/t1657/t1657_6_….md
LIVE_NONE:unlocked
$ echo $?
0
```

## 3. `.claude/skills/aitask-note/SKILL.md` (new, static — no `.j2`)

Frontmatter: `name: aitask-note`, `user-invocable: true`, and a `description:`
that carries the **when**, since the description *is* the discoverability hook:

> Send a durable note to an existing aitask — context that task needs which is
> not itself work. Use when a finding belongs to a task that already exists.

Body:

- **Two entry paths, an explicit mode selector** (never an inferred signal):
  - explicit target — `/aitask-note 357 --from 1657 --text "…"`; zero prompts,
    so it is usable headlessly and callable from another skill;
  - discovery — execute the **Related Task Discovery Procedure** (see
    `.claude/skills/task-workflow/related-task-discovery.md`) with
    `matching_context`, `purpose_text`, `min_eligible: 1`,
    `selection_mode: ai_filtered`. Do not reinvent task matching.
- **The composition**, now three commands and a judgement:
  1. resolve the target id;
  2. `./ait note <target> --from <id> --with-live --file -` (quoted heredoc);
  3. on `LIVE_PANE:` only, follow the adapter procedure named by
     `.aitask-scripts/live_delivery/agents.txt` for that family — for
     `claudecode`, `.aitask-scripts/live_delivery/claudecode.md`. Join on the
     **pane id** alone; the payload must carry the `<note-id>`;
  4. report both outcomes.
- **Reporting rules, stated as rules** (these are what the prose-contract test
  pins): the durable result is authoritative; `LIVE_NONE:<reason>` after
  `NOTE_APPENDED:` is a **success with live delivery unavailable**, never a
  partial failure and never a reason to retry the write; `LIVE_QUEUED` means
  *enqueued*, never *read*.
- **Judgement the helper cannot carry**: note vs. spawn a task; the trust
  posture (advisory, attributed, never auto-actioned, `from=` is a claim);
  staleness hygiene for senders — hedge moment-relative claims. Both notes in
  the t349→t357→t353 chain that motivated this work were confidently wrong
  rather than hedged.

### Cross-agent wrappers (thin pointers, not ports)

Matching every other user-invocable skill, and `aitask-backlog-roadmap` as the
freshest example of the shape:

- `.agents/skills/aitask-note/SKILL.md` — "Source of Truth" pointer at
  `.claude/skills/aitask-note/SKILL.md` + the `codex_tool_mapping.md` reference;
- `.opencode/skills/aitask-note/SKILL.md` — same shape;
- `.opencode/commands/aitask-note.md` — `@`-includes the mapping and the Claude
  SKILL.md, passes `$ARGUMENTS`.

Verify with `./.aitask-scripts/aitask_audit_wrappers.sh` (parity + helper
whitelist) — both must stay clean.

## 4. Trigger points — three one-line offers, never automatic

Each is an *offer* at the moment a finding belongs to a task that **already
exists** — the repo's standing "hand findings to the owning task" convention,
which today has no mechanism to act on. Each is placed **outside** every Jinja
conditional and confirmed against the rendered variants.

| site | authored file | placement |
|---|---|---|
| `task-workflow` | `.claude/skills/task-workflow/SKILL.md` (authored despite the `.md` name — 47 inline Jinja constructs) | new `### Step 8e`, **after** the `{%- endif %}` at :802; retarget both "proceed to Step 9" strings (:799, :801) to Step 8e; 8e ends by proceeding to Step 9 |
| `aitask-qa` | `.claude/skills/aitask-qa/SKILL.md.j2` | unconditional region around Step 5's action list / Step 6 (:68–74) — exact line fixed by reading the render, not the template |
| `aitask-review` | `.claude/skills/aitask-review/SKILL.md.j2` | Step 3, at the "no findings selected" seam (:168) — findings surfaced but declined as new tasks is exactly the case; unconditional |

### Goldens are necessary but **cannot** prove the guarantee

A golden is generated *from* the template, so template and golden agree by
construction: regenerating them after removing an offer produces a green suite
with the offer gone. Goldens catch unintended drift; they cannot assert that a
specific line survives every profile. That claim needs its own assertions —
§V.7.

### Goldens — regenerate in the same commit

- `task-workflow` → `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
  **plus** `./.aitask-scripts/aitask_skill_rerender.sh remote` (the
  `task-workflow-remote-` closure is committed, `.gitignore:74`).
- `aitask-qa` → `tests/golden/skills/aitask-qa/SKILL-{default,fast,remote}-claude.md`.
- `aitask-review` → `tests/golden/skills/aitask-review/SKILL-{default,fast,remote}-claude.md`.

Generator (goldens come from `skill_template.py` stdout, never from copying a
rendered variant):

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    ".claude/skills/<skill>/SKILL.md.j2" "aitasks/metadata/profiles/$profile.yaml" claude \
    > "tests/golden/skills/<skill>/SKILL-${profile}-claude.md"
done
```

## 5. Hand the docs gap to its owner

`t1657_6` plans `commands/note.md` and `workflows/task-notes.md` but **no
`website/content/docs/skills/aitask-note.md`**, and no rows in the
hand-maintained `docs/README.md` / `website/content/docs/skills/_index.md` — a
page not listed there is invisible. That is t1657_6's surface, not this task's,
and both index files are currently dirty with another session's work. Send it as
a note rather than editing across the boundary — dogfooding the mechanism this
task exists to make reachable:

```bash
./ait note 1657_6 --from 1657_5 --with-live --file - <<'EOF'
…
EOF
```

---

### Post-phase (risk mitigations)

Both confirmed inline; they land with this task and no mitigation task is
created. Each is a case in `tests/test_note_with_live_composition.sh` (§V.5 and
§V.6 below), written **after** the main implementation so it probes shipped
behaviour rather than an intention.

- **`default_path_one_line_control`** — assert that without `--with-live`,
  `aitask_note.sh` stdout is exactly one line and byte-identical to today.
  Addresses: the second-stdout-line code-health risk.
- **`skill_prose_contract_test`** — assert `.claude/skills/aitask-note/SKILL.md`
  *states* the four reporting rules. Addresses: the post-adapter AC being
  assertable only in prose.

## Verification

### New — `tests/test_note_with_live_composition.sh`

Drives the **real entry point** (`aitask_note.sh`), never a replica, on a real
fixture repo. Reuses `test_live_endpoint_degradation.sh`'s documented seams:
`forge_lock` (git plumbing onto the fixture's lock branch),
`AIT_LIVE_DELIVERY_DIR`, `AITASKS_TMUX_SOCKET` pointed at a nonexistent server,
plus the new `AIT_LIVE_ENDPOINT_SH`.

1. **WRITE-BEFORE-LIVE, complete enumeration.** For each of the 7
   `LIVE_NONE:<reason>` values (`unlocked`, `remote_host`, `holder_dead`,
   `holder_unknown`, `agent_unknown`, `agent_unsupported:<family>`, `no_pane`):
   assert stdout is exactly two lines, line 1 is `NOTE_APPENDED:<id>|<path>`,
   the note is present in the target's `## Inbox`, the commit landed, and
   **exit is 0**.

   **All three `LIVE_ERROR` reasons are unreachable through the real
   composition, by construction** — `usage` and `bad_task_id` cannot occur
   because `ait note` validates and canonicalizes the id before the resolver is
   ever called, and `task_not_found` cannot occur because a missing target
   returns `NOTE_TARGET_MISSING:` and short-circuits the live lane. So
   `LIVE_ERROR` coverage comes from the `AIT_LIVE_ENDPOINT_SH` stub (item 3),
   not from a real path dressed up as one.

2. **The errexit regression — the one that would ship a broken flag.** A stub
   that prints `LIVE_ERROR:task_not_found:999` and **exits 2**: assert stdout is
   exactly two lines with that line verbatim as line 2, and **exit 0**. Under a
   naive `$( )` capture this test fails with a truncated single line and a
   non-zero status. Companions on the same seam: a stub that exits 2 printing
   nothing, one that prints garbage and exits 0, and one that prints three
   lines — the first two yield `LIVE_ERROR:resolver_unavailable`, the third uses
   only its first line, all three exit 0 with exactly two lines of stdout.
3. **The positive `LIVE_PANE` branch — a real pane, not a stub.** Modelled on
   `tests/test_live_endpoint_tmux_live.sh`: a throwaway tmux server on a private
   `-L` socket via `require_isolated_tmux` (`tests/lib/tmux_isolation.sh`), SKIP
   when tmux is absent. Seed the target with `implemented_with: claudecode/…`
   (Step 7 writes it, not the claim — an unseeded task short-circuits at
   `agent_unknown`), claim it *inside* the pane, then send with `--with-live`:
   assert two lines, line 1 `NOTE_APPENDED:<id>|<path>`, line 2 the **whole**
   `LIVE_PANE:<%pane>|<target>|<pid>|agent=claudecode` line with `<target>` read
   back from tmux's own `#{session_name}:#{window_id}.#{pane_id}` rather than
   rebuilt, the note present and committed, exit 0.
   **Ordering control:** the identical setup with `implemented_with` cleared
   must yield `LIVE_NONE:agent_unknown` — without it, a positive case can pass
   for the wrong reason.
4. **Durable failure short-circuits the live lane.** `NOTE_TARGET_MISSING:` and
   `AIT_NOTE_FAIL_AFTER_APPEND=1` → one line only, non-zero exit, resolver never
   invoked (proved with a counting stub via `AIT_LIVE_ENDPOINT_SH`).
5. **Negative control:** without `--with-live`, exactly one line (`grep -c .`),
   byte-identical to today.
6. **Prose contract over `.claude/skills/aitask-note/SKILL.md`** — the
   `test_live_endpoint_no_sendkeys.sh` precedent: the file must *state* that the
   durable result is authoritative, that `LIVE_NONE` after `NOTE_APPENDED` is a
   success and not a partial failure, that `LIVE_QUEUED` is enqueued and never
   read, and that a note is never auto-actioned.

7. **Trigger points survive every profile** — the assertion goldens cannot make.
   For each of `task-workflow/SKILL.md`, `aitask-qa/SKILL.md.j2`,
   `aitask-review/SKILL.md.j2` × `{default, fast, remote}`, render with
   `skill_template.py <file> aitasks/metadata/profiles/<p>.yaml claude` and
   assert the offer marker (the literal `` `/aitask-note` ``) appears **exactly
   once** — 9 assertions. Then the same assertion against the **committed**
   `.claude/skills/task-workflow-remote-/SKILL.md`, which is the artifact that
   actually ships, so a stale `aitask_skill_rerender.sh remote` is caught too.
   Exactly-once, not merely present: it also pins that an offer was not
   duplicated into both arms of a conditional.

**Mutation checks** (each must fail the suite): move the resolver call before
the append; make exit follow the live lane; drop the `^LIVE_` shape guard; drop
the default-path one-line control; move any one offer inside its neighbouring
`{% if %}` and regenerate the goldens — the render assertions must go red while
the goldens stay green, which is the whole point of adding them.

**Honest limit, stated rather than papered over:** the adapter is a model-facing
procedure (`ListAgents`/`SendMessage` have no CLI), so nothing past
`LIVE_PANE:` — the `SendMessage` call, the payload's contents, `LIVE_QUEUED` —
can be reached from a shell test. Item 3 proves the composition hands off a
correct, live endpoint; item 6 pins the reporting rules; the handoff itself is
manual, below.

### t1657_7 — one new `[t1657_5]` checklist item

t1657_7 already carries `[t1657_4]` items for "reaches it live; the message
names the same note id" and "reported as queued, never as read". Both were
written on 2026-09-01, before the composition existed: neither invokes the
skill, and none of the `[t1657_5]` items exercises a *successful* live
delivery — they cover only the failure-after-write case. Add one item, so the
acceptance contract this task owns is verified end to end:

> `- [ ] [t1657_5] With a second live Claude session holding the target task on
> this host, invoking /aitask-note end-to-end resolves LIVE_PANE, the adapter
> payload names the exact note id appended to that task's ## Inbox, and the
> result is reported as LIVE_QUEUED — enqueued, never read or delivered.`

Editing a sibling's checklist is deliberate and path-scoped: t1657_7 is the
aggregate verification sibling (`verifies: [1657_2, 1657_3, 1657_4, 1657_5]`)
and this is a t1657_5 acceptance criterion, so it belongs there rather than in a
new task.

### Existing suites

- `bash tests/test_agent_instructions.sh` — T25–T27 for the three mirrors, plus
  a new **T44** asserting the assembled *shared* layer teaches sending (`ait
  note` + `--from` present). Assertions stay **outside** subshells: this file
  uses in-process counters and deliberately declines the file-backed opt-in.
- `bash tests/test_note_append.sh`, `tests/test_note_read_receipts.sh`,
  `tests/test_note_section_order.sh` — unchanged behaviour on the default path.
- `bash tests/test_live_endpoint_degradation.sh`, `_tmux_live.sh`,
  `_no_sendkeys.sh`.
- `bash tests/test_skill_render_task_workflow.sh`,
  `tests/test_skill_render_aitask_qa.sh`,
  `tests/test_skill_render_aitask_review.sh`.
- `./.aitask-scripts/aitask_skill_verify.sh` and
  `./.aitask-scripts/aitask_audit_wrappers.sh`.
- `shellcheck .aitask-scripts/aitask_note.sh`.
- `bash tests/run_all_python_tests.sh --test-dir tests`.
- **End-to-end dogfood:** the §5 note to t1657_6, sent with `--with-live`.

### Not automatable — and not claimed to be

Two things, both routed to t1657_7 rather than faked in a shell test:

- **"Discoverable in a fresh session"** is a property of an agent's context, not
  of a file. Layer 1 is the guarantee that does not depend on an agent choosing
  to look; t1657_7 items 17–18 are the human check.
- **Everything past `LIVE_PANE:`** — the `SendMessage` call and its payload —
  needs a live second session; the new `[t1657_5]` item above covers it.

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **medium**

- Adding a second stdout line to `aitask_note.sh`, a 1021-line shipped script
  whose one-line contract three other surfaces parse · severity: medium ·
  → mitigation: `default_path_one_line_control` — opt-in flag, default path
  byte-identical, pinned by an explicit negative control.
- Editing `task-workflow/SKILL.md`, the highest-fanout template in the repo,
  with a **committed** rendered `-remote-` closure that drifts silently ·
  severity: medium · → mitigation: goldens + `aitask_skill_rerender.sh remote`
  in the same commit, `test_skill_render_task_workflow.sh` as the check.
- A seed edit that does not reach all three tracked mirrors · severity: low ·
  → mitigation: T25–T27 already turn drift into a failing test.
- Path-scoped commits sweeping the other session's uncommitted work · severity:
  medium · → mitigation: verified zero path overlap; commit by explicit
  pathspec, never `git add -A`, and check `--stat` before each commit.

### Goal-achievement risk: **medium**

- The relocated AC about a *post-adapter* failure cannot be forced from a shell
  test, because the adapter is a model-facing procedure · severity: medium ·
  → mitigation: `skill_prose_contract_test` — pin the reporting rule in the
  artifact an agent actually reads, and state the limit rather than claiming
  coverage. The reachable half (up to and including `LIVE_PANE:`) is proved by
  §V.3 against a real pane; the handoff past it by the new t1657_7 item.
- A green suite proving nothing about the trigger points: goldens are generated
  from the templates they check, so an offer deleted for one profile passes ·
  severity: medium · → mitigation: §V.7's 10 per-profile render assertions,
  with the "move an offer inside a conditional and regenerate" mutation as the
  check that they actually discriminate.
- "Discoverable" is not assertable by any unit test · severity: medium ·
  → mitigation: layer 1 does not depend on the agent choosing to look, and
  t1657_7 items 17–18 are the human check.

### Planned mitigations

- timing: post-phase | name: default_path_one_line_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: second stdout line on a shipped one-line contract | desc: negative control pinning that the default (no --with-live) path stays exactly one line and byte-identical
- timing: post-phase | name: skill_prose_contract_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: post-adapter AC assertable only in prose | desc: static prose-contract test pinning the four reporting rules in the aitask-note SKILL.md an agent actually reads

## Final Implementation Notes

- **Actual work done:** All five plan sections landed as designed, plus both
  inline post-phase mitigations. Two commits: `03a66c7ec` (28 files, code) and
  `6d7d9997a` (task data).
  - `seed/aitasks_agent_instructions.seed.md` gained `## Sending Notes to Other
    Tasks`; `AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md`
    regenerated by driving `update_agentsmd` + `assemble_aitasks_instructions` /
    `insert_aitasks_instructions`, per-agent tails intact. `CLAUDE.md` edited by
    hand (it is sentinel-guarded, so `ait setup` leaves it alone).
  - `aitask_note.sh --with-live` (+107 lines): opt-in, resolver invoked only
    after a successful append+commit, reason codes passed through verbatim,
    exit status from the durable lane alone, `AIT_LIVE_ENDPOINT_SH` test seam.
  - `.claude/skills/aitask-note/SKILL.md` (static, `user-invocable: true`) plus
    `.agents/`, `.opencode/skills/` and `.opencode/commands/` wrappers.
  - Trigger points: `task-workflow` **Step 8e** (new), `aitask-qa` Step 6,
    `aitask-review` Step 3. Nine goldens regenerated, plus
    `aitask_skill_rerender.sh remote` for the three committed remote closures.
  - `tests/test_note_with_live_composition.sh` (117 assertions) and T44 in
    `tests/test_agent_instructions.sh`.

- **Deviations from plan:** Three, all recorded above in "What the verify pass
  changed" and one found during implementation.
  (1) Wrappers shipped here rather than as a port follow-up — `ait-git` is
  Claude-only because it is `user-invocable: false`, so the plan's precedent did
  not support "Claude-first". (2) Composition fused into `--with-live` rather
  than left as prose. (3) **`test_skill_render_task_workflow.sh` had to change**:
  its Test-5 assertion "Step 8c routes straight to Step 9" is false once an
  unconditional Step 8e exists. The guard's intent — lean profiles omit Step 8d
  and 8c must not route into it — was preserved and strengthened from one
  assertion to three (new target pinned, `proceed to Step 8d` asserted absent,
  Step 8e asserted present), and its rationale comment updated so the recorded
  reasoning does not go stale.

- **Issues encountered:**
  - **The errexit capture was the real defect risk**, raised in plan review and
    confirmed by mutation: the resolver deliberately exits 2 on `LIVE_ERROR:*`
    and this script runs `set -euo pipefail`, so a bare `$( )` aborts *after* the
    note is appended and committed — emitting `NOTE_APPENDED:`, no second line,
    and exit 2. Test 2a/2b/2e reproduce exactly that under the naive capture.
    Three traps avoided: declare-then-assign (`local x="$(…)"` masks the status
    in `local`'s own exit code), no pipe (`pipefail` re-surfaces the 2), and no
    reason-code remapping.
  - **`LIVE_ERROR` is unreachable through the real composition**, discovered while
    writing §V.1: `usage` and `bad_task_id` cannot occur because `ait note`
    validates the id first, and `task_not_found` cannot occur because a missing
    target returns `NOTE_TARGET_MISSING:` and short-circuits the live lane. Its
    coverage therefore comes from the `AIT_LIVE_ENDPOINT_SH` stub, stated as such
    rather than dressed up as a real path.
  - First draft of test 1a forged a lock to reach `unlocked`, which yields
    `remote_host` instead — `unlocked` means no lock *record*, so it has to run
    on the fixture's initial state.
  - A help-text example using `<<'EOF'` collided with the enclosing `cat <<EOF`
    (SC1039); renamed to `NOTE_BODY`.
  - Test 6e failed because the rule spanned a newline and the guard is
    line-oriented. Fixed in the **skill**, not the assertion: a rule an agent
    must follow belongs on one line.

- **Key decisions:**
  - **Fused into the existing `aitask_note.sh` rather than a new script.** A new
    helper would need all 5 whitelist touchpoints, and those files were carrying
    another session's uncommitted work at the time. `aitask_note.sh` and
    `aitask_live_endpoint.sh` were already whitelisted, so the change needed none.
  - **Opt-in flag, not a default.** The one-line stdout contract is parsed by
    other surfaces; `--with-live` leaves the default path byte-identical, pinned
    by an explicit negative control (`default_path_one_line_control`).
  - **Exit status returned explicitly (`return 0`), never as `$?`** — so no later
    edit can let the live lane leak into it.
  - **An unparseable resolver answer is `LIVE_ERROR:resolver_unavailable`, never
    `LIVE_NONE`.** An empty parse is not a result; collapsing them would make a
    broken resolver indistinguishable from an idle task.
  - **Offers placed outside every Jinja conditional**, and asserted per profile
    rather than by golden — a golden is generated *from* the template it checks,
    so it agrees by construction and cannot catch a profile-specific deletion.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t1657_6 has been sent a durable note** (`2026-09-07T14:46:16Z.e0d65fa4…`,
    `from_verified=yes`) covering the `website/content/docs/skills/aitask-note.md`
    gap and the two hand-maintained skill indexes its plan does not mention,
    plus the `--with-live` contract it now has to document. Read its `## Inbox`.
  - **Do not document a Codex/OpenCode port follow-up for `aitask-note`** — the
    wrappers shipped here. The existing note in t1657_6's inbox about the
    "three trees" claim is right for *templated* skills; static user-invocable
    skills do ship the three thin wrappers, and `aitask_audit_wrappers.sh parity`
    is blind to Claude-only skills by construction, so it would not have caught
    their absence.
  - **t1657_7 gained one `[t1657_5]` item** for the live two-session path —
    everything past `LIVE_PANE:` is a model-facing adapter with no CLI and cannot
    be forced from a shell test.
  - `AIT_LIVE_ENDPOINT_SH` joins `AIT_LIVE_DELIVERY_DIR` and `AITASKS_TMUX_SOCKET`
    as a documented injection seam; `tests/test_note_with_live_composition.sh`
    is the template for driving the composition end to end.
