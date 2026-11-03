- `>q` — **Help me decide what to do now** ("help me decide", "what should I
  do?", "what do I answer?", "explain it simply and help me decide") — in
  **every** state the followed agent can be in, not only when it is asking a
  question:
  1. **Capture the screen again first.** Run Step 1 and re-read `--phase`, even
     if you captured recently.
  2. **Gather whatever context the decision needs** — you are not limited to
     the followed agent's captured output.
  3. **Explain the situation in simple words.**
  4. **Then the decision.**
     - **An `AskUserQuestion` is on screen:** explain each option and its
       trade-offs and **suggest** an answer with your reasoning.
     - **Any other state** (still working, stuck or erroring, a plan waiting
       for approval, finished): list the realistic next moves — wait, approve
       the plan, answer, interrupt or redirect the agent, or ask for a deeper
       shadow capability such as `>d`, `>pc` or `>i` — and recommend one with a
       short reason. A deeper capability is **offered by its shortcode,
       never started on your own**; the user asks for it.
  5. Remind the user that whatever they decide, they type it into the followed
     agent themselves — you do not.
