---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [python, cli, testing, chat_surface, security]
gates: [risk_evaluated]
created_at: 2026-07-19 22:35
updated_at: 2026-07-19 22:35
---

## Goal

Build a phased, local-first pipeline that turns a written bug description plus an Android/device screen recording into timestamp-grounded evidence, then later integrates that capability into Chatlink after the in-flight multi-workflow rewrite stabilizes.

The task must be split into phased child tasks during planning. Phase 1 must remain independently unit-testable and must not import or modify Chatlink.

## Confirmed product decisions

- The work belongs in the `aitasks` framework repository.
- Use an umbrella task with phased children.
- Start with deterministic ingestion and versioned contracts; no cloud calls in phase 1.
- Use a provider-neutral semantic-analysis interface, with explicitly opted-in Gemini as the first hosted provider and local Qwen3-VL as a compatible follow-up.
- A recording is required; logcat or `adb bugreport` inputs are optional enrichments.
- Processing is local-first. Cloud upload must require explicit consent and cleanup.
- Do not integrate with the current singleton Chatlink intake. The integration child must wait for `t1157_4`.
- Keep original recordings transient by default. Persist compact derived evidence; retain originals only through explicitly configured large-file remote storage.

## Phase 1 — independent ingestion foundation

Add a human-facing command:

```text
ait bug-video prepare <video> --description-file <file> --out <dir> [--diagnostics <path>]
```

Implement it as a thin Bash launcher plus a Chatlink-independent Python package. The core API must accept a local video path, reporter text, optional diagnostics, and hard processing limits, with injected media/OCR/analyzer seams for deterministic tests.

Use argv-list `ffprobe`/`ffmpeg` subprocesses rather than adding OpenCV/PyAV or other heavy dependencies to the shared framework environment. Treat FFmpeg as an optional feature dependency with actionable preflight errors.

Produce a versioned evidence bundle containing:

- source SHA-256, byte size, probed MIME/container, duration, resolution, rotation, and stream metadata;
- the original reporter description and optional diagnostic references;
- bounded, ordered timestamped frames with stable frame IDs and selection reasons;
- regular samples plus change-triggered bursts so transient UI events and rapid taps are less likely to be missed;
- applied limits, warnings, and deterministic machine-readable failure codes.

Phase 1 performs no cloud calls and no task, attachment, or artifact persistence.

## Phase 2 — semantic evidence analysis

Add:

```text
ait bug-video analyze <video> --description-file <file> --out <dir> \
  --provider gemini --allow-cloud-upload [--diagnostics <path>]
```

Introduce a provider-neutral semantic analyzer. Implement Gemini first because it accepts video and structured JSON output, while compensating for its coarse default video sampling with the local event-frame bundle. Preserve an interface suitable for a later local Qwen3-VL backend.

Require explicit cloud consent on every invocation, validate provider output against the versioned analysis schema, never log credentials, and delete remotely uploaded files in success and failure paths.

The analysis result must include:

- a claim-to-evidence matrix mapping each reporter claim to stable evidence references;
- claim status restricted to `supported`, `contradicted`, or `not_visible`;
- timestamped action/screen timeline, expected versus observed behavior, reproduction steps, missing diagnostic questions, and confidence;
- visible text/OCR and optional repository source hints;
- inferred root-cause candidates separated explicitly from observed facts.

For repository-aware analysis, permit fuzzy matching OCR text against project strings/resources and routes to suggest likely files without presenting those matches as proof.

## Phase 3 — deferred Chatlink integration

This child must depend on the analyzer phases and on `t1157_4`. Integrate through the post-t1157 bug-workflow input-preparation seam, not the current `_open_session` implementation.

Before accepting videos, add a bounded/streaming chat attachment-download contract. Current adapters buffer complete downloads and attachment size/MIME metadata is advisory; video intake must enforce its own count, byte, duration, frame, pixel, output, and timeout limits while treating filename, MIME, metadata, and media contents as untrusted.

The later workflow must:

1. Validate attachment count/type without trusting the supplied filename.
2. Download through the authenticated adapter boundary into an attempt-owned, hash-derived path with a hard byte ceiling.
3. Run preprocessing in an isolated worker; background work may only compute and enqueue a result so Chatlink retains its single sequential mutation consumer.
4. Persist analysis state and source digest in the durable attempt record for crash-safe retry and deduplication.
5. Supply the bounded evidence report as generic attempt context to the sandbox without adding raw media to `TaskPayload`.
6. Require the existing explicit initiator approval before task creation.
7. On approval, embed a concise evidence summary in the task and persist a compact `bug-evidence.zip` report artifact containing Markdown, JSON, contact sheet, and minimal repro clip.
8. Clean transient media after completion/failure; retain the original only when a compatible remote backend and explicit retention policy are configured.

Do not block the daemon event loop with FFmpeg. Do not commit large recordings to the local task-data branch by default. Define explicit failure/rollback and push ordering for any task-plus-artifact persistence so partial creation is visible and recoverable.

## Phase 4 — documentation and verification

Document a recommended capture bundle: screen recording with Show Taps enabled when possible, written expected/actual behavior, and optional time-aligned logcat or `adb bugreport`. Make clear that recordings alone cannot expose hidden application state or logs.

Add a manual-verification child only after automated integration tests pass, covering a live Discord intake with Hebrew/RTL UI, visible and absent tap indicators, a transient popup/toast, and optional diagnostics.

## Public contracts and safety invariants

- Version preparation and analysis JSON schemas from their first release.
- Evidence references use stable frame IDs plus integer `timestamp_ms`.
- Model claims must cite existing evidence references; unknown references fail validation.
- Enforce configurable byte, duration, frame-count, decoded-pixel, output-size, and subprocess-time limits before and during processing.
- Use argv-list subprocesses, bounded stdout/stderr capture, timeouts, and isolated temporary directories.
- The core package must not import `chat`, `chatlink`, task frontmatter, attachment, or artifact APIs.
- Cloud processing is never implicit; automatic redaction must not be represented as perfect or used as a substitute for explicit consent.
- Preserve Chatlink sandbox isolation: no bot token, git credentials, or broader host filesystem access reaches the analyzer/model worker.

## Verification

- Pure Python unit tests with injected fakes: metadata parsing, hashing, adaptive sampling, timestamp ordering, schema round-trip, Unicode/Hebrew descriptions, limit math, warnings, and deterministic failures.
- CLI tests with fake `ffprobe`/`ffmpeg` executables: exact argv, whitespace/metacharacter filenames, corrupt/spoofed media, timeouts, oversized inputs, bounded output, and actionable missing-tool errors.
- Optional real-codec integration test that generates a short synthetic recording when FFmpeg is available.
- Provider contract tests: missing consent, structured-output validation, unknown evidence references, provider/network failures, credential redaction, and remote-file deletion on every exit path.
- Later MockChatAdapter tests: streaming overflow, advisory-size mismatch, worker event routing, crash/restart idempotency, concurrent-session isolation, no daemon-loop blocking, approval-only persistence, rollback behavior, and transient cleanup.
- Live manual verification after automated coverage, not as a substitute for it.

## Coordination

- `t1157_1`–`t1157_4`: in-flight Chatlink configuration, durable session, router, and bug-intake rewrite; phase 3 waits for `t1157_4`.
- `t1134`: attachment/artifact schema evaluation; do not invent a third task reference schema.
- `t1089`/`t1090`: remote artifact backends; original-video retention must not assume they have landed.
- `t1120_8`: existing live Discord baseline remains separate; this feature gets its own later manual-verification child.
