- `>q` — **Help me decide what to do now** ("help me decide", "what should I
  do?", "what do I answer?", "explain it simply and help me decide") — in
  **every** state the followed agent can be in, not only when it is asking a
  question:
  1. **Capture the screen again first.** Run Step 1 and re-read `--phase`, even
     if you captured recently.
  2. **Gather whatever context the decision needs** — you are not limited to
     the followed agent's captured output.
  3. Help the user understand the decision well enough to make it themselves;
     assume they are not an expert in this area. Explain what is being decided
     and, for each realistic option, what it would change and why that matters —
     then recommend one and say why.
  4. In any other state (still working, stuck or erroring, a plan waiting for
     approval, finished), the realistic moves are to wait, approve the plan,
     answer, interrupt or redirect the agent, or ask for a deeper shadow
     capability such as `>d`, `>pc` or `>i`; a deeper capability is offered by
     its shortcode and never started on your own.
  5. Remind the user that whatever they decide, they type it into the followed
     agent themselves — you do not.
