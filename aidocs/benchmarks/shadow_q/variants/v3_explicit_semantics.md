- `>q` — **Help me decide what to do now** ("help me decide", "what should I
  do?", "what do I answer?", "explain it simply and help me decide") — in
  **every** state the followed agent can be in, not only when it is asking a
  question:
  1. **Capture the screen again first.** Run Step 1 and re-read `--phase`, even
     if you captured recently.
  2. **Gather whatever context the decision needs** — you are not limited to
     the followed agent's captured output.
  3. Explain the decision so the user can make it. In whatever form suits the
     situation, cover: what is happening and what is actually being decided, in
     language a non-expert can follow (define terms they may not know); for
     every realistic option, what choosing it does in practice and its real
     benefits and costs — an explanation of the option itself, not only a reason
     it loses to another; and your recommendation, reasoned from this task's
     goals and facts. Plain language is not the same as brevity: be as short as
     those explanations allow, not shorter. Do not invent drawbacks to balance
     an option.
  4. In any other state (still working, stuck or erroring, a plan waiting for
     approval, finished), the realistic moves are to wait, approve the plan,
     answer, interrupt or redirect the agent, or ask for a deeper shadow
     capability such as `>d`, `>pc` or `>i`; a deeper capability is offered by
     its shortcode and never started on your own.
  5. Remind the user that whatever they decide, they type it into the followed
     agent themselves — you do not.
