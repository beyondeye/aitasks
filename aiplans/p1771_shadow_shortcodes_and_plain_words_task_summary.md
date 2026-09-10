---
Task: t1771_shadow_shortcodes_and_plain_words_task_summary.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1771 — Shadow shortcodes + "the task in plain words"

## Context

The shadow companion (`/aitask-shadow`) exposes eleven capabilities, all reached
by describing them in words ("challenge the plan", "review the implementation at
the advanced tier"). That is fine the first time and tedious the twentieth,
especially for the implementation review where the tier has to be spelled out to
beat the profile default. And a human who walks up to a followed agent's pane —
or who queued the task days ago — has no cheap way to learn *what the task is
even about*; every existing capability either reads the screen or interrogates
the plan, and none of them explains the task itself.

This task adds two things:

1. **A shortcode per capability** — `>e`, `>t`, `>i3`, … — declared next to each
   Step 3 capability and rendered into the Step 0 greeting, so the greeting stays
   derived from Step 3 (the maintainer note in `SKILL.md.j2` forbids a second
   hardcoded copy).
2. **A new on-demand sub-procedure, "the task in plain words"** — a
   non-interactive, task-first summary built from the task file and, when one
   exists, the current plan. Reachable only by asking (`>t` or words); **never**
   shown automatically.

Both are prose-level changes to a profile-aware skill: the source of truth is
`.claude/skills/aitask-shadow/SKILL.md.j2` and its ten sibling `.md`
sub-procedures, which the dep-walker renders into the Claude, Codex and OpenCode
trees. Nothing in `.aitask-scripts/` changes — no new helper, no new profile key.

**Decided during planning:** the new file is `task-summarize.md` (the sibling
`<topic>-<verb>` shape; the task body's provisional `task-summary.md` is
superseded), and `website/content/docs/workflows/shadow-agent.md` — which
enumerates every capability in prose and is *not* in the task's pinned-contracts
list — is updated in this task rather than deferred.

**Two decisions in the task body are superseded by the user during planning,
deliberately and on the record** (the task's "Decisions already taken" section
and its AC list still say otherwise, so the implementation must not "restore"
them):

- **No bare-code routing.** The task decided a message that is *exactly* a bare
  code (`t`, `i3`) would also route. Dropped: a code is only ever recognised
  `>`-prefixed. This removes the whole-message-equality special case and the
  ambiguity of a one-letter message. AC 2 ("Sending `>t` (or `t`) …") is read as
  `>t` only.
- **Letter assignment.** `>x` → **`>px`**, `>s` → **`>ps`**, `>a` → **`>pa`**,
  and `>c` → **`>pc`**, grouping the plan-only analyses under a `p` prefix. The task's proposed table
  used the bare letters; it explicitly allowed adjusting letters during planning.

**Adjacent staleness found and fixed here** (it is the same sentence this change
must edit anyway): `round-preamble.md` shipped 2026-09-08 and was never added to
the "nine sub-procedure `.md` files" enumeration in
`aidocs/framework/shadow_agent.md:72`, nor to the "The nine sub-procedures" claim
in `tests/test_skill_render_aitask_shadow.sh`. Disk holds ten today, eleven after
this change.

---

## The shortcode table (final)

| code | capability | served by |
|---|---|---|
| `>e` | explain the screen / "what is the agent doing?" | inline (Step 3) |
| `>q` | help answer the `AskUserQuestion` on screen | inline (Step 3) |
| `>t` | **the task in plain words** | **new** `task-summarize.md` |
| `>px` | explain the plan to a non-expert | `plan-explain.md` |
| `>pc` | adversarially challenge the plan | `plan-challenge.md` |
| `>i`, `>i1`–`>i4` | review the implementation (ladder / quick / default / advanced / deep) | `impl-challenge.md` |
| `>r` | **refetch and recheck** — a new review round, re-running the last review | Step 3 recheck rule |
| `>rpc`, `>ri`, `>ri3`, `>rpa`, `>rd` | a new round of a **named** review (`>r` + that review's code) | Step 3 recheck rule |
| `>ps` | socratic questioning of the plan | `plan-socratic.md` |
| `>pa` | surface the plan's assumptions | `plan-assumptions.md` |
| `>d` | diagnose skill/helper errors | `plan-diagnose-errors.md` |
| `>l` | learn a skill from what the agent did | `spawn-learn-skill.md` |
| `>f` | refetch the followed screen now | Step 1 |
| `>?` | reprint the capability list | Step 0 greeting |

Every code is **`>`-prefixed, always** — there is no bare form. The `p*` family
(`>px`, `>pc`, `>ps`, `>pa`) groups the plan-only analyses. The rows are listed
in **Step 3 bullet order**, not alphabetically, because that is the order the
Step 0 greeting derives them in — no bullet is reordered by this change.

**`>r` composes with a review code.** A recheck is *a new round of some
review*, and today the only way to say which is prose. So `>r` takes an
optional target:

- `>r` alone — re-run the review that produced your last round; if you have
  run none in this conversation, fall back to the phase-driven default ladder
  (unchanged behaviour).
- `>r<code>` — run a new round of **that** review, whether or not it was the
  last one: `>rpc` plan-challenge, `>ri` implementation review, `>rpa`
  assumptions, `>rd` error diagnosis. The tier digit rides along, so `>ri3` is
  a new implementation-review round at Advanced.

The composable set is exactly the four **concern producers** (`plan-challenge`,
`impl-challenge`, `plan-assumptions`, `plan-diagnose-errors`) — the
sub-procedures that emit a round-headed concern block and are therefore the only
ones a *round* is defined for. `>rt`, `>rpx`, `>rps`, `>rl` are not codes; treat
them as unrecognised and reprint the list.

---

## Step 1 — `SKILL.md.j2`: declare the codes at their Step 3 entries

`.claude/skills/aitask-shadow/SKILL.md.j2`

**1a. New subsection at the top of Step 3**, immediately after the
"Read what the user asked and route" paragraph and *before* the phase-driven
default table:

```markdown
### Shortcodes — a shorter spelling of the ask

Every capability below opens with its **shortcode**: the `` `>…` `` token at the
start of its bullet. Two non-capability codes live here too — `` `>f` ``
refetches the followed agent's screen (Step 1) and `` `>?` `` reprints the Step 0
capability list.

- **Form** — `>` followed by a registered code: one or two letters (`>e`,
  `>px`), `>i` with an optional tier digit (`>i3`), or `>r` with an optional
  review code (`>rpc`, `>ri3`). The registered codes are exactly the tokens
  that open the bullets below plus `>f` and `>?`; nothing else is a code.
- **The `>` is required.** A bare letter or word is always prose, never a code
  — a message of just `t` is a message, not a request for the task summary.
  There is no unprefixed form to disambiguate.
- **Embedded is fine; mentioned is not.** A code is recognised anywhere in a
  message when the message is *asking for it*: `>i3 but only the callers` is
  an advanced review scoped to the callers. A code that is merely *talked
  about* is conversation, not invocation — a question about it ("what does
  `>l` do?"), a quoted example, or a negated or hypothetical mention ("don't
  run `>i4`, just explain that option") gets an answer in words and runs
  nothing. When you genuinely cannot tell, ask in one line rather than run;
  `>l` in particular opens a new window, so a mistaken launch is not free.
- **Composition** — `>r` (recheck) takes an optional review code — `>rpc`,
  `>ri`, `>ri3`, `>rpa`, `>rd` each start a new round of that named review.
  `>r` on its own re-runs whichever review produced your last round.
- **Unrecognised code** — say so in one line and reprint the list; never guess
  at a neighbouring letter.

A shortcode is only a shorter way to say the ask. It carries no authority the
same request in words would not have, and every capability stays reachable
however it is spelled.
```

> **Constraint while writing this block and `task-summarize.md`:**
> `tests/test_shadow_phase_advisory.sh` sweeps every rendered closure for a
> refusal verb (`refuse|do not run|cannot run|must not run|is unavailable|not
> available|too early|abort the run|stop the run|only if the phase|…`) within
> ±2 lines of the word *phase*. Keep the word "phase" out of the new prose
> entirely — the block above deliberately says "however it is spelled" rather
> than "at every phase". The existing `never removes a capability` clause in
> Step 1 (which the test also pins) is untouched.

**1b. Prefix every Step 3 capability bullet with its code**, e.g.

```markdown
- `` `>e` `` — **Explain the output / "what is the agent doing?"** — read the …
- `` `>q` `` — **Help answer an `AskUserQuestion`** — when the screen shows …
```

and, under *Structured analyses*, add `>t` as the **first** entry (it is the
cheapest orientation and the one a newcomer wants first):

```markdown
- `` `>t` `` — **The task in plain words** ("what is this task about?", "explain
  the task", "what is it actually doing this for?") → read and follow
  `task-summarize.md`. Task-first and non-interactive: it explains *what the
  followed agent is working on* from the task file plus, when one exists, the
  current plan. Distinct from `plan-explain.md`, which is plan-only and
  interactive. **Never emit it unprompted** — not at startup, not after a
  capture, not as a proactive offer.
```

then `>px` `plan-explain.md`, `>pc` `plan-challenge.md`, `>i` `impl-challenge.md`
(bullet updated to name `>i1`–`>i4` and say a digit is honoured as a named
tier), `>ps`, `>pa`, `>d`, `>l` on the existing bullets unchanged apart from the
leading token.

The **recheck** bullet needs more than a leading token, because it is the one
capability whose target is another capability. Rewrite its opening to:

```markdown
- `` `>r` ``, `` `>r<code>` `` — **Re-review after the agent moved on — a
  recheck round** ("refetch and recheck", "recheck round N", "review it again
  after the changes") → refetch the followed screen (Step 1), then run a new
  round of a review sub-procedure. `>r` on its own (and the free-text forms) re-runs
  the one that produced your previous round, or, if you have run none, the one
  the phase-driven default ladder picks. `>r` **plus a review code** names the
  review instead — `>rpc` challenge the plan, `>ri` review the implementation
  (`>ri3` at Advanced), `>rpa` assumptions, `>rd` error diagnosis — and runs a
  new round of it whether or not it was the last one. Only these four compose
  with `>r`: they are the round-headed concern producers, and a "round" is not
  defined for the others.
```

The rest of that bullet — "a recheck is a full new review round, not a
conversational follow-up", the re-enter-and-emit rule, the round numbering — is
unchanged. Note the auto-recheck loop (`review_loop.py` sends the free text
`refetch and recheck round N: …` into the shadow pane) keeps working untouched;
`>r` is an additional spelling, not a replacement.

**Why leading tokens and not a table at the top of Step 3:** a table would be a
second copy of the capability list living three lines from the first — exactly
the drift the Step 0 maintainer note exists to prevent.

**1c. Step 0 renders the codes.** In the "Build the capability list by reading
your own Step 3" paragraph, change "Present each one to the user in a single
short phrase" to "…**led by its shortcode** (the `` `>…` `` token that opens its
Step 3 bullet)", and add one line to the two-things list:

- state the shortcode rule in one sentence (a `>`-prefixed code works anywhere in
  a message, and the `>` is always required), and name `>?` as
  the way to see the list again;
- attach `>f` to the existing refetch bullet.

---

## Step 2 — `impl-challenge.md`: tier digits as explicit wording

`.claude/skills/aitask-shadow/impl-challenge.md`, "Tier selection (after the
assessment)". The four recognition bullets sit **outside** the
`{% if profile.shadow_impl_review_tier %}` block, so one edit serves both arms:

```markdown
- "quick" / "fast" / `>i1` → **Quick**
- "default" / "basic" / "legacy" / an unqualified "adversarial review" /
  `>i2` → **Default**
- "advanced" / "standard" / "normal" / `>i3` → **Advanced**
- "deep" / "thorough" / "max" / "exhaustive" / `>i4` → **Deep**

A tier digit counts as **explicit wording** — rank 1 of the resolution order
below — so `>i3` runs Advanced whatever the profile configures, and needs no
"inferred tier" announcement. `>i` with no digit names no tier: it is the *generic* ask
the next bullet resolves.
```

The "generic ask" line in each Jinja arm gains "(including a digitless `>i`)" so both
arms agree on what `>i` means. The `Resolution order` paragraph and the
`Announce an inferred tier (required)` paragraph are unchanged — the digit codes
are already covered by "the four explicit-wording bullets above".

**Keep each pinned substring on one source line.** `tests/…_render_aitask_shadow.sh`
Test 2p greps for these bullets as literal strings; a bullet that wraps mid-pin
makes the assertion unsatisfiable.

---

## Step 3 — New sub-procedure `task-summarize.md`

`.claude/skills/aitask-shadow/task-summarize.md`, modelled on `plan-explain.md`
(header block → `## Procedure` → numbered steps). Content:

- **Header** — what it is, its shortcode `>t`, when to use it, and the two
  binding constraints: **never emitted unprompted**, and **not a concern
  producer** (no concern block, no rejection-store consult, no round header;
  `concern-format.md` and the round-preamble's *preamble* rules do not apply).
- **Inputs** — the source task id from shadow Step 2, then
  `./.aitask-scripts/aitask_shadow_context.sh <source_task_id>`; read
  `TASK_FILE:` and, when it is not `NOT_FOUND`, `PLAN_FILE:`. No new helper, no
  `--siblings`, no `aitask_explain_context.sh` — this is the cheap one.
- **`PLAN_FILE:NOT_FOUND` is not "no plan".** The helper resolves only
  externalized plans under `aiplans/`. While the followed agent is *in* plan
  mode its plan is a draft at `~/.claude/plans/<name>.md` (verified on this
  very task: the helper answered `NOT_FOUND` while a complete approval-ready
  draft was on screen). So on `NOT_FOUND`, fall through the same source ladder
  `round-preamble.md` §6 already defines — point at it, do not restate it:
  rung 2 (exactly one distinct `~/.claude/plans/<name>.md` path on the deep
  capture → read that file), else rung 3 (the plan as rendered on the deep
  capture, treated as possibly partial). Only when every rung is empty say
  that **no plan could be found** — never that none exists — and summarise the
  task alone. Say which source the plan came from in one line.
- **Audience** — *point at*, do not restate: the reader is the one
  `round-preamble.md` §1 defines (someone who will not read the plan; outcomes
  and behaviours, not file paths or function names). Duplicating that rule here
  would recreate the drift class it exists to prevent.
- **Advisory-only** — the standard sibling clause.

`## Procedure`:

1. **Resolve the task id** by shadow Step 2's rules. Degrade explicitly: no id
   and the user cannot supply one → say you cannot summarise a task without
   knowing which one, and offer `>e` instead; `TASK_FILE:NOT_FOUND` → say the
   task file could not be resolved and stop.
2. **Read** the task file; then the plan, from the first source that applies:
   `PLAN_FILE:<path>` → that file; else the `round-preamble.md` §6 ladder
   (draft-plan path on screen → deep capture). Nothing found → summarise the
   task alone and say a plan could not be found from here (not "no plan
   exists"). A capture-sourced plan is read as possibly partial; say so.
3. **Write a few short paragraphs**, in this order — the last two only when a
   plan exists:
   - what this is trying to achieve, and why it is worth doing;
   - what changes for someone using the thing;
   - how the agent means to get there;
   - roughly how far along it is.
4. **Writing rules** — lead with outcomes; no jargon unless unpacked in the same
   sentence; no file paths, function names or ids; a minute to read, not five.
5. **Offer follow-ups** — `>px` for a deeper plan walkthrough, `>pc` to challenge
   it, `>pa` for its assumptions.

**One-line edit to `round-preamble.md` §1** so the pointer is honest: its
audience rule currently binds "every shadow review producer" and names the four
producers. Add `task-summarize.md` as a **non-producer consumer of §1 only**
(the plain-words audience rule, not the preamble headings or the verdict rule).
No second copy of the rule anywhere.

The dep-walker discovers `task-summarize.md` from the bare filename in
`SKILL.md.j2` (`SHORT_REF_RE`, sibling ref, existence-checked), so it renders
into all three agent trees automatically. `.opencode/commands/aitask-shadow.md`
carries no capability list and needs no port.

---

## Step 4 — `tests/test_shadow_phase_advisory.sh`

Add one entry to `CAPABILITIES` (7 → 8):

```bash
    "task-summarize.md"
```

Nothing else: the refusal sweep already globs `"$dir"/*.md`, so the new file is
swept the moment it lands in a closure.

---

## Step 5 — `tests/test_skill_render_aitask_shadow.sh`

1. **`PROC_FILES_INVARIANT`** — add `task-summarize` (9 → 10). It carries no
   Jinja, so Test 1i's identity-transform sweep covers it and it needs no
   golden.
2. **Fix the three stale counts** in the same file: the header's "eight
   Jinja-free procedures", the "the other nine are identity transforms" comment,
   and Test 4's "The nine sub-procedures must all land in the closure" → ten,
   ten, eleven respectively.
3. **Test 2p `RECOGNITION_LINES`** — update the three bullets that gain a digit
   and add the digit-semantics pin:
   ```bash
   '"quick" / "fast" / `>i1` → **Quick**'
   '"default" / "basic" / "legacy"'
   '"advanced" / "standard" / "normal" / `>i3` → **Advanced**'
   '"deep" / "thorough" / "max" / "exhaustive" / `>i4` → **Deep**'
   'A tier digit counts as **explicit wording**'
   '`>i` with no digit names no tier'
   ```
   Test 2p already loops all three profiles, which is what makes this the
   "present in **both** Jinja arms" assertion the task asks for (`fast` renders
   the if arm, `default`/`remote` the else arm).
4. **New Test 2s — the shortcode surface survives rendering.** For each profile,
   render the entry-point template and assert:
   - every code in the table above appears (`` `>e` `` … `` `>?` ``);
   - the three rule sentences survive, pinned as one-line literals:
     `The `>` is required.`, `Embedded is fine; mentioned is not.`, and
     `nothing else is a code` (the closed-registry clause) — and the removed
     bare-form wording (`exactly a code and nothing else`, `bare code`) is
     **absent** (`assert_not_contains`), so restoring bare routing fails here;
   - the recheck composition survives: each of `>rpc`, `>ri`, `>ri3`, `>rpa`,
     `>rd` appears, and so does the sentence restricting composition to the
     four concern producers;
   - `task-summarize.md` is referenced from Step 3;
   - `>?` is named as the reprint code.

   This is new coverage: no test asserts anything about Step 0 / the greeting
   today.
5. **New Test 0 — procedure inventory guard**, mirroring the one
   `tests/test_skill_render_task_workflow.sh` already has: every `*.md` in
   `.claude/skills/aitask-shadow/` except `SKILL.md` must appear in
   `PROC_FILES`. This is the guard whose absence let `round-preamble.md` go
   uncovered and the "nine" counts drift; adding a procedure file is exactly the
   moment to close it.
6. **Regenerate all six goldens and review the diff** (same commit as the source
   edits — `aidocs/framework/skill_authoring_conventions.md` commit rule):
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for p in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       .claude/skills/aitask-shadow/SKILL.md.j2 \
       aitasks/metadata/profiles/$p.yaml claude \
       > tests/golden/skills/aitask-shadow/SKILL-$p-claude.md
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       .claude/skills/aitask-shadow/impl-challenge.md \
       aitasks/metadata/profiles/$p.yaml claude \
       > tests/golden/procs/aitask-shadow/impl-challenge-$p.md
   done
   ```
   Expected diff: SKILL goldens gain the Step 3 shortcode block + the leading
   tokens + the `>t` bullet + the Step 0 wording; impl-challenge goldens gain the
   digit codes and the digit-semantics paragraph. **Anything else is a
   regression.**

---

## Step 6 — Docs

**`aidocs/framework/shadow_agent.md`, "The skill" section:**

- line 72 — "nine sub-procedure `.md` files (five `plan-*.md`,
  `impl-challenge.md`, `impl-review-angles.md`, `concern-format.md`,
  `spawn-learn-skill.md`)" → **eleven**, with `round-preamble.md` and
  `task-summarize.md` added to the enumeration (5 `plan-*` + 6 = 11).
- line ~83 — "the nine sub-procedures are rendered into the Codex and OpenCode
  trees" → eleven.
- Step 3 bullet list — add the `task-summarize.md` entry and extend the
  parenthetical "(four review a plan; one reviews the implementation; one
  diagnoses …)" with "one summarises the task".
- Step 0 bullet — note the greeting renders each capability **with its
  shortcode**.
- New short **Shortcodes** paragraph in the same section: canonical `>` prefix,
  the `>`-always-required rule, the `>i1`–`>i4` tier digits and their rank-1
  precedence, the `>r<code>` recheck composition (and why only the four concern
  producers compose), and `>?`.

**`website/content/docs/workflows/shadow-agent.md`:**

- "What happens once it is running" — a fourth bullet introducing shortcodes
  (with a compact code list), the always-`>`-prefixed rule, `>r<code>` for a
  new round of a named review, and `>?`.
- "Follow where the review is heading" / the recheck prose — name `>r` and
  `>rpc` / `>ri` alongside the existing free-text "recheck" wording, so the page
  does not read as free-text-only.
- "What the shadow can do" — a new `### The task in plain words` section placed
  after "Help you answer a prompt" and before "Interrogate a plan"; state
  plainly that it is on request only.
- The review-tier paragraph (~line 76) — mention `>i1`–`>i4` and that a digit
  beats the `shadow_impl_review_tier` profile setting exactly as a named tier
  does.
- Then, per CLAUDE.md: `cd website && python3 check_links.py --build`.

---

## Verification

Run from the repo root, in this order:

```bash
bash tests/test_skill_render_aitask_shadow.sh      # goldens, arms, Test 0/2p/2s
bash tests/test_shadow_phase_advisory.sh           # capability sweep, no refusals
./.aitask-scripts/aitask_skill_verify.sh           # renders + closure walk + stubs
```

Expected: `PASSED` from both test files, and
`aitask_skill_verify.sh: OK (13 template(s) verified …)` at exit 0.

Python guards that read the shadow skill files (they re-render the `fast`
closure themselves):

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
# Pick the runner by availability FIRST; never chain `pytest … || unittest …`,
# because a fallback over fewer files masks a real failure in the larger run.
if "$PYTHON" -c 'import pytest' 2>/dev/null; then
  "$PYTHON" -m pytest -q tests/test_shadow_disposition_surfaces.py tests/test_concern_parser.py
else
  "$PYTHON" -m unittest -v tests.test_shadow_disposition_surfaces tests.test_concern_parser
fi
echo "python-guards exit=$?"
```
Both files run under whichever runner is present, and the exit status is the
verdict — no `||`.

Website:

```bash
cd website && python3 check_links.py --build
```

**Manual (cannot be proven by prose pins)** — these are the ACs a rendered-text
assertion can only approximate, and they are what the spawned
manual-verification follow-up covers: launch a shadow with `e` from minimonitor
against a live agent and check that (a) the greeting lists every capability with
its code and names `>?`; (b) `>?` reprints the list; (c) `>t`
produces the plain-words summary, and it is **never** printed at startup or
after a refetch; (d) `>i3` runs Advanced with no tier prompt and no "inferred
tier" line under the `fast` profile (`shadow_impl_review_tier: advanced` — pick a
tier other than advanced to make the assertion discriminating, e.g. `>i1` /
`>i4`); (e) `>i` alone still resolves via the existing ladder; (f) with the
followed agent **still in plan mode** (draft only, `aitask_shadow_context.sh`
returns `PLAN_FILE:NOT_FOUND`), `>t` summarises from the draft plan and names its
source, and does not claim no plan exists; (g) a *mention* of a code ("what does
`>l` do?") answers in words and opens no window; (h) `>r` starts a
new round of the last review and `>rpc` / `>ri3` start a new round of the *named*
one, each emitting a fresh round-headed concern block rather than a prose
answer.

---

## Step 9 (Post-Implementation)

Standard: commit source edits, tests and goldens **together** (the golden commit
rule), record Final Implementation Notes, run the `risk_evaluated` gate, then
archive t1771 and its plan. The manual-verification follow-up below is created
at Step 8d ("after" timing).

---

## Risk

### Code-health risk: low

- The change is skill prose, one new markdown procedure, two test files and six
  regenerated goldens; nothing under `.aitask-scripts/` changes, so no runtime
  code path moves. · severity: low · → mitigation: none needed
- The phase-advisory refusal sweep is a ±2-line regex over every `.md` in every
  rendered closure, so an unlucky wording in the new prose (a refusal verb near
  the word "phase") fails the sweep. · severity: low · → mitigation: none needed
  (Step 1's stated constraint plus `tests/test_shadow_phase_advisory.sh`, which
  fails loudly rather than silently)
- Test 2p pins recognition bullets as literal substrings; re-wrapping a bullet
  while adding a digit code silently unsatisfies a pin. · severity: low · →
  mitigation: none needed (the test fails, and Step 2 states the one-line rule)

### Goal-achievement risk: medium

- The deliverable is **agent-behavioural**: whether a running shadow actually
  routes `>i3` to Advanced without prompting, and never volunteers the task
  summary. Every test in this plan pins *rendered prose*, which is a proxy, not
  proof — a correct-looking rendered instruction can still be mis-followed. ·
  severity: medium · → mitigation: verify_shadow_shortcodes_live
- The Step 0 greeting is generated at runtime from Step 3, so "the greeting lists
  every capability with its code" is only checkable by running a shadow; the new
  Test 2s proves the codes and the rule text are *present to be derived from*, no
  more. · severity: medium · → mitigation: verify_shadow_shortcodes_live
- `>t`'s degrade paths (no task id; `PLAN_FILE:NOT_FOUND`) are instructions, not
  code, and are the states a real session hits most often. · severity: low · →
  mitigation: verify_shadow_shortcodes_live

### Planned mitigations
- timing: after | name: verify_shadow_shortcodes_live | type: manual_verification | priority: medium | effort: low | inline_risk: high | added_complexity: high | addresses: all three goal-achievement risks | desc: Launch a shadow from minimonitor against a live agent and check the eight behavioural ACs — greeting lists every capability with its code and names `>?`; `>?` reprints the list; `>t` summarises and it is never auto-shown at startup or after a refetch; `>i3` runs Advanced with no tier prompt and no inferred-tier line under `fast` (use `>i1`/`>i4` to make it discriminating, since `fast` already configures advanced); `>i` alone still resolves via the existing ladder; `>r` and `>rpc`/`>ri3` each emit a fresh round-headed concern block rather than a prose answer; with the followed agent still in plan mode, `>t` summarises from the draft plan via the round-preamble source ladder and never claims no plan exists; a mention of a code ("what does `>l` do?") answers in words and opens no window. | created: t1780

---

## Implementation progress

- [x] Step 1 — `SKILL.md.j2`: Step 0 renders codes + one-sentence rule + `>f`; Step 3 "Shortcodes" subsection (closed registry, `>` required, embedded-vs-mentioned intent rule, `>r` composition, unrecognised-code rule); every bullet led by its code; `>t` bullet first under structured analyses; `>i` bullet names the digits; recheck bullet rewritten for `>r<code>`.
- [x] Step 2 — `impl-challenge.md`: digits on the four recognition bullets; "(including a digitless `>i`)" in both Jinja arms; digit-semantics paragraph after `{% endif %}` (shared by both arms).
- [x] Step 3 — new `task-summarize.md`; `round-preamble.md` header names it as a §1-only non-producer consumer.
- [x] Step 4 — `CAPABILITIES` += `task-summarize.md` (8).
- [x] Step 5 — render test: `PROC_FILES_INVARIANT` += `task-summarize`; new Test 0 (inventory from disk, dupes check); Test 2p pins updated + two digit-semantics pins; new Test 2s (20 codes, 7 rule literals, 2 bare-form absences); three stale counts fixed; six goldens regenerated — diff reviewed, only the intended hunks.
- [x] Step 6 — `aidocs/framework/shadow_agent.md` (eleven, `round-preamble.md` + `task-summarize.md` in the enumeration, Test 0 pointer, Step 0/Step 3 updates, Shortcodes paragraph); website page (shortcode bullet, `### The task in plain words`, tier digits, `>r<code>` in the recheck prose).

**Deviations / notes**
- The digit-semantics paragraph sits *after* `{% endif %}` rather than between the recognition bullets and the generic-ask bullet, so the bullet list is not split; it is still shared by both arms and Test 2p pins it in all three profiles.
- `tests/test_shadow_phase_advisory.sh` first reported 4 failures: it reads the gitignored rendered closures from disk without rendering them, and the `-default-`/`-remote-` closures were a day stale (Test 4 of the render test re-renders only `fast`). Re-rendering every profile × agent made it 55/55. Not fixed here (out of scope; the explore pass had flagged it) — a fresh checkout still degrades to a single "rendered closures were found" failure rather than a skip.
- The working tree carries another session's uncommitted work (aitask-note docs, pickrem/pickweb/wrap goldens, task-workflow procs). Nothing of it is touched; the commit names every path explicitly.

## Post-Review Changes

### Change Request 1 (2026-09-10 12:05)
- **Requested by user:** two review concerns. (1) `tests/test_concern_parser.py:2297` — under the `unittest` runner, `TestProducerPlainWordsRule.test_production_assertion_fails_on_a_real_offender` fails twice because the inner `subTest` records the assertion instead of propagating it to `assertRaises`; pytest passes. Verified: file byte-identical to HEAD, reproduced 2 failures / 184 under `unittest` — pre-existing, not caused by t1771; disposition follow-up (recorded under Upstream defects for Step 8b). (2) `task-summarize.md` said "of `round-preamble.md` only §1 applies" while relying on §6's source ladder twice; `round-preamble.md` and `aidocs/framework/shadow_agent.md` repeated "§1 only".
- **Changes made:** (2) all three sites now say §1 (audience rule) **and** §6's source selection apply, excluding snapshot writes, round headers and review preambles. (1) not changed — different file, pre-existing, follow-up.
- **Files affected:** `.claude/skills/aitask-shadow/task-summarize.md`, `.claude/skills/aitask-shadow/round-preamble.md`, `aidocs/framework/shadow_agent.md`.

## Final Implementation Notes
- **Actual work done:** Shortcodes for every shadow capability, declared as the leading token of each Step 3 bullet in `SKILL.md.j2` and rendered into the Step 0 greeting (no second copy); a closed-registry rule block in Step 3 (`>` always required, embedded-vs-mentioned intent rule, `>r<code>` composition, unrecognised-code handling); `>i1`–`>i4` as explicit tier wording in `impl-challenge.md` (both Jinja arms); the new `task-summarize.md` ("the task in plain words", `>t`, on request only, with the `round-preamble.md` §6 source ladder for a not-yet-externalized plan); `round-preamble.md` header names it as a §1 + §6-source-selection consumer; tests (`CAPABILITIES` += 1; render test gains Test 0 inventory-from-disk, Test 2s shortcode surface, updated 2p pins, corrected counts); six goldens regenerated; `aidocs/framework/shadow_agent.md` and the website shadow-agent page updated.
- **Deviations from plan:** Two task-body decisions were superseded by the user during planning and are recorded in the plan's Context: no bare-code routing (`>` always required), and the plan family renamed to `>px`/`>pc`/`>ps`/`>pa`; `>r` gained composition with a review code. The digit-semantics paragraph in `impl-challenge.md` sits after `{% endif %}` (not between bullets) to keep the list intact. The new file is `task-summarize.md`, not the task body's provisional `task-summary.md`.
- **Issues encountered:** `tests/test_shadow_phase_advisory.sh` reads gitignored rendered closures without rendering them; the day-old `-default-`/`-remote-` closures failed 4 checks until every profile × agent was re-rendered (55/55 after). The working tree carried another session's uncommitted work throughout; every commit here names its paths explicitly.
- **Key decisions:** leading tokens per bullet rather than a table (a table is a second copy of the list the maintainer note forbids); composition restricted to the four round-headed concern producers (a "round" is defined for nothing else); `PLAN_FILE:NOT_FOUND` is treated as "not externalized", never "no plan", because the helper resolves only `aiplans/` and a followed agent in plan mode has only a draft — verified on this task itself.
- **Upstream defects identified:**
  - `tests/test_concern_parser.py:2297` — `TestProducerPlainWordsRule.test_production_assertion_fails_on_a_real_offender` fails under the `unittest` runner (2 failures, `producer='leak.md'` subTest and the outer test) because the inner `subTest` records the assertion instead of propagating it to `assertRaises`; passes under pytest. Pre-existing (file byte-identical to HEAD); the negative control needs to work under both supported runners.
  - `tests/test_shadow_phase_advisory.sh:149-159` — layer 2 reads gitignored rendered closures from disk without rendering them (unlike `test_shadow_disposition_surfaces.py`), so a stale or fresh checkout fails on a stale inventory rather than rendering or skipping.
