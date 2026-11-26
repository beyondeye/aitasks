---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [shadow, skills, codex]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-26 23:46
updated_at: 2026-11-26 23:46
---

## Problem

The shadow agent's two "help me weigh it" shortcodes do not give the user what they are meant to give
when the shadow runs on `codex/gpt6_2_sol` (the `shadow` default since t2333):

- **`>q`** is meant to explain the situation and the options in simple words (with a little background
  when needed) and to write a **clear list of pros and a clear list of cons for each option**, then
  recommend one.
- **`>pd`** is meant to write a **clear list of pros and cons for each design decision** in the plan.

Neither happens on gpt-6.2-sol. `>pd` used to work on gpt-6.1-sol. This is the production fix that
t2179 never made: t2179 was an experiment only (its main run was declined on budget; t2179_2 closes it
from pilot evidence; t2187, the Codex v1-vs-v2 experiment, is Postponed). The production wording of
`>q` is still the t2094 text.

## Evidence (measured 2026-11-26, from the user's real Codex shadow sessions)

Source: `~/.codex/sessions/2026/{10,11}/*/rollout-*.jsonl` that contain `aitask-shadow`. For every user
message invoking `>q` or `>pd`, the model was taken from the preceding `turn_context` record and the
answer is the last assistant message of that turn. All sessions ran at reasoning effort `high`.

| code | model | n | median chars | answers with `Pros:` and `Cons:` labels |
|---|---|---|---|---|
| `>pd` | gpt-6.1-sol | 48 | 2373 | 46 / 48 |
| `>pd` | gpt-6-astra | 12 | 2521 | 11 / 12 |
| `>pd` | gpt-6.2-sol | 7 | 1615 | **0 / 7** |
| `>q` | gpt-6.1-sol | 411 | 995 | 0 / 411 |
| `>q` | gpt-6.2-sol | 38 | 911 | 0 / 38 |

A wider label match (pro, con, benefit, cost, drawback, downside, upside, advantage, disadvantage at
line start followed by a colon) gives the same counts.

What the answers look like:

- **`>pd` on gpt-6.2-sol:** the task in a few sentences, then usually two numbered decisions. Each is
  ONE prose paragraph in which the choice, the reason, the benefit, the cost and the alternative are
  run together. No pros list, no cons list. Roughly 30% shorter than on 6.1.
- **`>pd` on gpt-6.1-sol:** the same structure, but each decision ends with a `Pros: …` line and a
  `Cons: …` line, as `plan-decisions.md` step 4 asks.
- **`>q` on both models:** recommendation FIRST ("Choose **1. …**"), then one bullet per option that
  mixes a benefit and a cost in a single sentence, then what to type. There is no plain-words
  explanation of the situation up front and no background, although step 3 of the definition asks
  for it before the decision. So `>q` is not a 6.2 regression: it never produced what the user wants.

In every one of the last seven gpt-6.2-sol `>pd` turns the model DID read `plan-decisions.md` in that
turn (plus `round-preamble.md`, the context helper and a capture). So the procedure is loaded and still
not followed for the output shape. This is not a stale render or a missing file.

### Likely cause for `>pd` (hypothesis, strongly supported, not proven)

Codex ships model-specific base instructions (`session_meta.base_instructions` in each rollout).
For gpt-6.2-sol they are a new text (27,750 chars, against 21,524 for gpt-6.1-sol on the same CLI
versions 0.170-0.171). Every gpt-6.2-sol session but one carries it; no gpt-6.1-sol or gpt-6-astra
session does. The new text contains, among other writing rules:

- "In prose, do not use semicolons. Do not use colons to introduce explanations or examples,
  including after list labels."
- "Don't use lead-in phrases or sentences that label a paragraph or announce your next point."
- "Do not provide unsolicited recommendations", "Do not compare to an unsolicited alternative that the
  user did not directly ask about."

`plan-decisions.md` asks for exactly a label followed by a colon (`Pros: …` / `Cons: …`), and it is
shown as an indented example rather than stated as a required output format. Our own wording pushes
the same way: the `>pd` bullet in `SKILL.md.j2` opens its description with "Plain prose", and
`plan-decisions.md` says "It is prose for a human, nothing more" and "For each, a short paragraph".

The old gpt-6.1-sol base text instead said "Use lists only when the information is genuinely parallel,
sequential, or easier to compare", which allowed the labels.

Treat this as the leading hypothesis. Do not claim it as the cause without a controlled check (see
Verification).

### Cause for `>q`

The definition never asks for pros and cons. Step 4 says only "explain each option and its trade-offs
and **suggest** an answer with your reasoning", and step 3 ("Explain the situation in simple words")
is a five-word line that both models skip or reduce to one clause after the recommendation.

## Goal

Change the production definitions so that, on gpt-6.2-sol and without regressing other agents:

1. `>q` gives, in this order: the situation in simple words, with a little background when a reader
   would need it; then every option with what it means, a pros list and a cons list; then the
   recommendation with its reason; then the reminder that the user types the answer themselves.
   The "any other state" branch (no question on screen) keeps its list of realistic next moves and
   should get the same treatment where moves are real alternatives.
2. `>pd` gives, per decision, a separate pros list and cons list that a reader can find at a glance.

## Design guidance (decide in planning, with evidence)

- **Pick an output form that does not collide with the gpt-6.2-sol base rules**, rather than fighting
  them with emphasis. Candidates: sub-bullets under a bold `**Pros**` / `**Cons**` word with no colon;
  a two-row or two-column table; `Pros` / `Cons` as short list headings. The base text itself says
  "Use tables … when it makes comparisons / lookups easier, and prefer using lists when it helps the
  reader scan items or steps", so a list or table is on the allowed side. Measure, do not assume.
- **State the shape as the requested output format of the answer**, not as an illustration. The base
  text tells the model to check each deliverable against the user's intended format.
- **Remove the wording that argues against lists**: "Plain prose" in the `>pd` bullet, "prose for a
  human, nothing more" and "a short paragraph" in `plan-decisions.md`. Keep what those sentences were
  protecting (no concern block, no round header, not a complete tour of the plan).
- **Keep it short.** The user's standing concern from t2179 is that a capable agent should follow a
  clear statement of intent without an over-specified template. Prefer the smallest wording that
  measurably works. t2179_1's frozen variants (`aidocs/benchmarks/shadow_q/variants/`, v2 concise
  intent, v3 explicit semantics, v4 prescriptive) are ready-made candidates for `>q`; none of them
  asks for pros and cons lists explicitly, so they need that addition.
- **Do not invent cons to fill a slot.** `plan-decisions.md` already says a choice with no real con is
  not a trade-off. `>q` needs the equivalent: an option with no real downside says so in one line.
- Keep `>e` explanation-only, keep `>pd` "never emitted unprompted", "not a concern producer" and its
  decision-selection rule (step 3). Selection quality on 6.2 looked fine and is out of scope.
- Check whether `>t` (`task-summarize.md`) and `>px` have the same label-and-colon dependency, and
  report it. Fix only if the same edit covers it; otherwise suggest a follow-up.

## Touchpoints

- `.claude/skills/aitask-shadow/SKILL.md.j2`: the `>q` bullet (around lines 281-300 at the time of
  writing) and the `>pd` bullet (around 311-317). Re-resolve the lines.
- `.claude/skills/aitask-shadow/plan-decisions.md`: the header paragraphs and step 4.
- Rendered variants and goldens: re-render every profile and agent, regenerate goldens in the same
  commit, run `./.aitask-scripts/aitask_skill_verify.sh`. Read
  `aidocs/framework/skill_authoring_conventions.md` and `aidocs/framework/shadow_agent.md` first.
  Codex renders are `.agents/skills/aitask-shadow-<profile>-codex-/`; the `>q` text there is
  byte-identical to the Claude render today, so one source edit covers both.
- Tests that pin the rendered `>q` / `>pd` prose (grep `tests/` for `plan-decisions`, `>pd`,
  `Help me decide`).
- Website docs that describe `>q` / `>pd` (grep `website/content/docs` for the shortcodes) if the
  described behaviour changes.
- `aidocs/benchmarks/shadow_q/frozen/` freezes the OLD `>q` bullet by design. Do not edit the frozen
  baseline; see "Notes to send".

## Verification

1. **Free compliance scan (add it as a small dev script).** Port the scan below into the repository
   (suggested: `aidocs/benchmarks/shadow_q/scan_sessions.py`, numbers-only output, reading only the
   local `~/.codex/sessions`). It prints per (code, model): n, median length, and the share of answers
   with a separate pros and cons block. Extend the matcher to recognise the NEW output form. It must
   never copy answer text into the repository: aitasks is public and the sessions quote private
   projects. Record the before numbers from the table above in the plan.
2. **Controlled live check before committing the wording.** A small number of real `codex exec` runs
   on gpt-6.2-sol against a replay fixture, old wording against new wording, for both `>q` and `>pd`,
   and at least one gpt-6.1-sol run for the new wording so the fix does not regress the model that
   worked. `aidocs/benchmarks/shadow_q/harness.py` already serves replay fixtures to the real CLI in a
   read-only sandbox for `>q`; reuse it rather than building plumbing. Fixtures live in the private
   aitasks_go store (`./ait projects resolve aitasks_go` → `aidocs/shadow_q_store/`). State the
   planned number of paid invocations and get the user's approval before the first one: the user
   declined a large budget for t2179_2.
3. **Hypothesis check, optional and cheap.** One or two runs with the current wording where only the
   label form changes (no colon) tell whether the colon rule is the cause. Report it as an
   observation with its n.
4. **After landing:** re-run the scan on real use a few days later and record the after numbers.
   A manual-verification follow-up is the right carrier for this.

## Other agents

Claude Code and OpenCode shadows were not measured. The same source renders for all three, so the edit
reaches them. Planning should say how each is checked (Claude Code session transcripts under
`~/.claude/projects/` can be scanned the same way) or record the gap.

## Notes to send (the implementing task owns these)

- **t2187** and **t2179_2**: the production `>q` wording changes under them. t2187's v1 baseline is
  the frozen pre-change text, so its "v1 vs v2" comparison no longer describes production. Also pass
  on the free session-log measurement (it answers part of t2187's question without spend) and the
  gpt-6.2-sol base-instruction finding.
- **t2186** (generic prompt-eval harness): a session-log scan is a zero-cost evidence source worth
  considering as an input.

## Scan used for the evidence (rebuild from this; the original was a scratch file)

```python
"""For each user message invoking >q or >pd in a Codex shadow rollout, record
the model and the assistant messages of that turn."""
import json, os, re, glob
root = os.path.expanduser('~/.codex/sessions/2026')
CODE = re.compile(r'(?<![\w>])>(q|pd)\b')
STRICT = re.compile(r'(?im)^\W*\**\s*(pros|cons)\**\s*[::]')
def text_of(p):
    return ''.join(x.get('text', '') for x in (p.get('content') or []) if isinstance(x, dict))
out = []
for f in sorted(glob.glob(root + '/1[01]/*/rollout-*.jsonl')):
    raw = open(f, errors='replace').read()
    if 'aitask-shadow' not in raw:
        continue
    model = effort = cur = None
    for line in raw.splitlines():
        try: o = json.loads(line)
        except Exception: continue
        t = o.get('type'); p = o.get('payload') or {}
        if t == 'turn_context':
            model, effort = p.get('model'), p.get('effort')
            if cur: cur['model'], cur['effort'] = model, effort
        elif t == 'response_item' and p.get('type') == 'message':
            txt = text_of(p)
            if p.get('role') == 'user':
                s = txt.strip(); m = CODE.search(s)
                cur = None
                if m and len(s) < 400 and 'SKILL' not in s:
                    cur = dict(code=m.group(1), model=model, effort=effort, answers=[])
                    out.append(cur)
            elif p.get('role') == 'assistant' and cur is not None:
                cur['answers'].append(txt)
# answer = cur['answers'][-1]; "has lists" = len(STRICT.findall(answer)) >= 2
```

Known limits of the scan: a turn's model is the last `turn_context` seen at or after the ask; a `>q`
mentioned rather than invoked in a short message is counted; `session_meta.base_instructions.text`
holds the base text compared above.
