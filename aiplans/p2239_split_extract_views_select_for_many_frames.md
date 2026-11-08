---
Task: t2239_split_extract_views_select_for_many_frames.md
Base branch: main
Output branch: main
---

# t2239 — extract_views: a select expression that does not hit ffmpeg's depth limit

## Context

`extract_views()` (`.aitask-scripts/screen_recording/video_prep.py:227`) joins one
`eq(pts,N)` term per wanted frame into a flat `a+b+c+…` select expression. On
ffmpeg n9.0.2 this fails at filter-graph init ("Error while parsing expression"
→ "Error opening output files: Cannot allocate memory") once the request goes
past 100 frames. So `bug --max-frames` above 100, the image-folder input
(`bug DIR` / `anim DIR`) and `anim --max-view-frames` all abort.

**Root cause, measured during planning:** the cause is the nesting depth of the
parsed expression, not the string length or the number of terms.
- A flat chain of 100 `eq(n,i)` terms works and 101 fails. Padding with `+0`
  terms fails just as early, even when the string is shorter (807 chars fail,
  while 60 long terms totalling 1669 chars work).
- 98 nested parentheses around one term work and 99 fail, so ffmpeg caps
  nesting at about 100 levels. A flat `+` chain parses left-deep, one level per
  term.
- A **balanced** tree, `((a+b)+(c+d))…`, picked every frame for 250, 2000 and
  6000 terms (6000 terms come to about 80 KB of text).

A second, independent ceiling applies once depth is fixed: Linux refuses a
single argv string of 128 KiB or more (`MAX_ARG_STRLEN`; probed: 131071 bytes
OK, 131072 bytes "Argument list too long"), and the whole `-vf` chain is one
argument. A term is at most about 32 bytes with its parentheses, so batching at
1000 frames per ffmpeg call keeps each argument under about 32 KB.

## Implementation (current branch, profile `fast`)

### 1. `video_prep.py` — balanced expression + bounded batches

- Add the constant next to the other module constants:
  ```python
  EXTRACT_BATCH = 1000  # wanted frames per ffmpeg call: keeps the -vf argument far
                        # below Linux's 128 KiB per-argument limit
  ```
- Add `select_expr(pts)`, which builds the sum as a balanced binary tree by
  pairing terms level by level. A single term gets no parentheses. Its nesting
  depth is ceil(log2 n), so 1000 terms nest 10 deep.
  ```python
  def select_expr(pts) -> str:
      """select expression true exactly on these pts, as a balanced sum: ffmpeg
      refuses expressions nested ~100 deep, and a flat a+b+c parses one level
      per term, so a flat sum fails past ~100 frames."""
      terms = [f"eq(pts,{p})" for p in pts]
      while len(terms) > 1:
          nxt = [f"({terms[i]}+{terms[i + 1]})" for i in range(0, len(terms) - 1, 2)]
          if len(terms) % 2:
              nxt.append(terms[-1])
          terms = nxt
      return terms[0]
  ```
- Split `extract_views`:
  - Move the current body, unchanged, into `_extract_batch(video, wanted, crop,
    vw, vh, *, stream, head)`. The only edit is that `expr` becomes
    `select_expr(sorted(wanted))`. The batch keeps its own `.extract_tmp` dir
    with `rmtree` in `finally`, its own check for exactly two showinfo
    instances, and its own missing-frame check. The `%05d` numbering and the
    instance numbers belong to a single ffmpeg call, so pairing frames to
    showinfo reports stays correct inside each batch.
  - `extract_views` keeps its signature and docstring and returns early on an
    empty `wanted`, as now. It sorts the pts, calls `_extract_batch` once for
    each chunk of `EXTRACT_BATCH`, and merges the returned `sizes` dicts. The
    keys are distinct pts, so the merge never overwrites. One sentence in the
    docstring explains the batching.
- **Bound each pass at its last wanted frame (review concern 2).** Today every
  call decodes the input to the end, even after its last wanted frame has gone
  by, and batching would multiply that cost. Place
  `trim=end_pts=<max(batch)+1>` immediately before the `select`, so it sees
  the same pts domain as `select`. Every `head` in this file is a bare
  `trim=start/end` with no `setpts` (lines 1032 and 1041), so the domain is the
  stream's own pts. Probed during planning: on a 1800-frame lavfi input with
  `-f null`, selecting pts 10 and 20 decoded **1800 frames without the bound
  and 25 with it**, with the same selected output. The ffmpeg CLI closes the
  input once the graph reaches EOF.
  - **Fallback.** `trim` reaches EOF at the first frame with pts ≥ end_pts. A
    stream whose decoder emits pts out of order could therefore drop a wanted
    frame that arrives after a larger one. In the extreme case the bound
    excludes every frame. A successful ffmpeg exit with **zero** showinfo
    reports then fails the existing `len(instances) != 2` guard *before* the
    missing-frame check runs.
    - So in `bounded=True` mode **every** report-validation failure raises a
      private `_Unbounded` signal instead of `PrepError`. That covers no
      reports or not exactly two showinfo instances, and missing frames. The
      signal is raised before any instance pairing or file move, and the batch
      tmp dir is still removed in `finally`.
    - `extract_views` catches `_Unbounded` and retries that batch once with
      `bounded=False`, which is today's full-decode chain exactly and keeps the
      **strict** checks. The unbounded attempt raises the existing `PrepError`
      messages unchanged ("could not tell ffmpeg's two showinfo reports apart",
      "could not extract frames with pts …").
    - An ffmpeg failure (non-zero exit, i.e. `run()` raising) is **not**
      retried: it is not a symptom of the bound.
    - So the bound can only make extraction faster, never lose a frame and
      never turn a success into an error.
  - The bound comes from a small helper `_batch_end_pts(pts) -> int`
    (`max + 1`), so a test can force the fallback.
  - **Cost.** Write the accepted cost into the `extract_views` docstring: it
    makes ceil(n / EXTRACT_BATCH) passes, and each one decodes from the start
    of the input (no seek) only up to that batch's last wanted frame. Every
    current caller asks for at most a few hundred frames, which is one pass.
- All three callers (lines ~1121, ~1310 and ~1647) stay as they are, and so
  does every CLI default.

### 2. Tests — `tests/test_screen_recording_cli.py`

- **`SelectExpr` (pure, no ffmpeg needed):** for n in {1, 2, 3, 7, 100, 101,
  1000, 4097}:
  - parse the output with a small recursive shape checker (a bare `eq(pts,N)`,
    or `(A+B)` split at its single top-level `+`), so the flat pre-fix form
    fails the shape;
  - assert tree depth ≤ ceil(log2 n);
  - assert every pts appears exactly once;
  - evaluate it with Python by rewriting `eq(pts,N)` to `(pts==N)`, and assert
    it is true on every wanted pts and false on the pts in between. Include
    negative and large pts values.
- **`ExtractViewsMany` (ffmpeg):** encode a 5 s slide with
  `synth.card_frames(synth.tween(synth.LINEAR, 0, 5), 5.0, "right")`, which
  gives 300 frames. Take the pts from `vp.enumerate_frames(video, None)`.
  - **> 120 frames:** request 150 of them (every other one). Assert every PNG
    exists, `sizes.keys()` equals the requested set, and every size is
    (native, native).
  - **batching differential:** run the same request with
    `mock.patch.object(vp, "EXTRACT_BATCH", 7)` into a second directory, which
    makes 22 batches. Assert the SHA-256 of each pts's PNG matches the
    single-batch run and the `sizes` dicts are equal. This proves the merge and
    the per-batch showinfo pairing.
- **Bounded pass really stops early:** wrap `vp.ffmpeg` with
  `mock.patch.object(vp, "ffmpeg", wraps=vp.ffmpeg)` to capture each batch's
  `-vf` string. Take the first batch's string, as video_prep built it, and run
  it on the real mp4 directly with `-v verbose -f null -`. Parse
  `N frames decoded`, and assert N is well below the video's 300 frames:
  at most the batch's last wanted frame index plus a small decoder-delay
  margin.
- **Fallback recovers, both routes:**
  - **empty output:** patch `vp._batch_end_pts` to `min(pts)`. The bound then
    excludes every frame and ffmpeg exits 0 with zero showinfo reports, which
    is the instance-guard route.
  - **partial output:** patch it to the median wanted pts, so some frames are
    found and some are missing. This is the missing-frame route.
  - In each case assert every requested frame is written with SHA-256 equal to
    the normal run, and `ffmpeg` is called exactly twice for that batch: first
    with `trim=end_pts` in `-vf`, then without it.
- **Strict validation survives on the unbounded attempt:** patch
  `vp._batch_end_pts` to `min(pts)` *and* request a pts that does not exist in
  the stream. Assert the `PrepError` "could not extract frames with pts" is
  raised after the retry, and that the call does not loop or swallow it.
- **CLI end-to-end (the task's repro):** run `bug <5s slide> --interval 0.01
  --per-sheet 400 --view-size 100 --max-frames 150`. Assert exit 0, more than
  120 picks in `run.json`, and one saved frame per pick.
- In `test_layout_reduced_sheets_list_the_frames_they_hold` (line ~374),
  rewrite the docstring, because the ffmpeg-limit reason it gives is no longer
  true. Say instead that the 500 px edge forces the reduction with 40 frames
  rather than about 130, which keeps the test fast. The test body is unchanged.

### Red proof (during implementation, recorded in Final Implementation Notes)

Use a scratch script under the session scratchpad, **entirely in-process**.
`run_cli` launches a fresh interpreter with `subprocess.run`, so a mock never
reaches it (review concern 1). The script:
1. `import video_prep as vp`, and patch `vp.select_expr` to the old flat form,
   `lambda pts: "+".join(f"eq(pts,{p})" for p in pts)`;
2. calls `vp.extract_views(...)` with the same 150-frame request → expect a
   `PrepError` whose cause is ffmpeg's "Error while parsing expression";
3. calls `vp.main(["bug", video, "--out", …, "--interval", "0.01",
   "--per-sheet", "400", "--view-size", "100", "--max-frames", "150"])`
   in-process, the same route the existing
   `test_layout_reduced_sheets_list_the_frames_they_hold` uses → expect a
   non-zero rc or `PrepError`;
4. repeats both without the patch → expect success.

Record the script verbatim, with both outputs, in the plan's Final
Implementation Notes so the closure evidence is durable. Do not stash and do
not restore anything.

## Verification

- `python3 -m pytest tests/test_screen_recording_cli.py -k "SelectExpr or ExtractViewsMany or BugMode" -q`
  (or `python -m unittest` on the same file)
- the full file `tests/test_screen_recording_cli.py` and
  `tests/test_screen_recording_core.py`, with no regressions
- a manual repro from the task:
  `bug synth.mp4 --interval 0.01 --per-sheet 400 --view-size 100 --max-frames 250`
  now exits 0
- `bash tests/run_all_python_tests.sh --test-dir <dir>` is not needed; the two
  files above cover the module

## Step 9 (Post-Implementation)

Commit the code as `bug: … (t2239)`, then archive with the standard Step 9 flow
(current branch, no merge).

## Risk

### Code-health risk: low
- The `trim=end_pts` bound could drop a wanted frame on a stream whose decoder emits pts out of order · severity: low · → mitigation: already designed into this plan, not a separate follow-up (the batch retries once without the bound, and a forced-fallback test covers it)

### Goal-achievement risk: low
None identified.
