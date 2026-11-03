# Shadow `>q` variants (t2179)

Each file is one complete `>q` bullet. The harness substitutes it for the
bullet in each agent's frozen fast render (`../frozen/<agent>/render/SKILL.md`,
lines 281-300 at the freeze SHA), and `qspan.assert_only_span_changed` proves
that nothing outside that span moved. Everything around the bullet stays
byte-identical across variants:
- the rest of the skill;
- the advisory-only Guardrail;
- the fresh-capture rule;
- the procedure files;
- the repository instructions.

So a difference between variants is attributable to the bullet alone.

**Held constant in every variant:**
- the bullet lead (the trigger phrases, "in **every** state");
- step 1 (recapture plus `--phase`);
- step 2 (gather the context the decision needs);
- step 5 (the user types the answer themselves).

**v2, v3 and v4 also share one step-4 sentence for the non-question state:**
- the realistic moves are wait / approve / answer / interrupt-or-redirect /
  `>d` `>pc` `>i`;
- a deeper capability is offered by its shortcode and never started.

That way the non-question branch does not differ between them. v1 keeps its own
wording verbatim.

| file | variant | what changes (step 3, plus step 4 for v1) | hypothesis |
|---|---|---|---|
| `v1_baseline.md` | current production wording, frozen by `freeze.py` | "Explain the situation in simple words", then: explain each option and its trade-offs and suggest an answer with reasoning | Reproduces the observed failure. Answers lead with a recommendation and a short justification, and give little explanation of the decision or of the options not recommended. |
| `v2_concise_intent.md` | concise statement of intent | Help a non-expert understand the decision well enough to choose: what is being decided, and for each option what it changes and why that matters, then recommend | A clear purpose is enough for current default agents. Coverage of non-recommended options improves over v1 with no layout prescribed, and the instruction stays short. |
| `v3_explicit_semantics.md` | explicit semantic requirements, no layout | Cover the situation, every option's practical benefits and costs (an explanation of the option itself, not only why it loses), and task-grounded reasoning. Plain language is not brevity. Do not invent drawbacks | Naming the missing semantic content, and separating "accessible" from "short", makes answers more consistent than v2 without the formatting side effects of a template. |
| `v4_prescriptive.md` | the more prescriptive proposal from the shadow conversation | Per-option what happens / main benefit / main drawback / when it makes sense, then recommend in relation to the task, plus a pre-send self-check | The most explicit wording gives the most consistent coverage. The open question is whether it buys anything over v3, or invites slot-filling such as invented drawbacks. |

No optional extra variant (for example, a worked example) is tested. A worked
example would hand one variant more source evidence than the others and
confound the comparison. The report states this.

The minimal-context condition uses the same bullet files on a trimmed SKILL.md:
- the preamble up to Step 0;
- Step 1;
- the Step 3 heading and the `>q` bullet;
- the Guardrail.

It has no repository instruction files and no skill listing.
