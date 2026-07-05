"""relay_ask — agent-side blocking ask CLI for the Q&A relay.

Runs inside the spawned (sandboxed) agent; the ONLY thing the agent needs to
ask a question. Writes the next-seq question into the session spool, blocks
polling for the answer, prints a line-oriented result, and — per the durable
timeout rule (spec §Timeout/cancel ownership) — records a `status: timeout`
answer itself when nobody answered in time.

Contract: **stdlib-only** (imports only ``chatlink.relay``); never hangs
past the timeout; exit 0 for every terminal answer status (answered /
timeout / cancelled — fail-safe), exit 2 only for usage/environment errors.

Output protocol (stdout, line-oriented; consumed by the asking agent):
    STATUS:answered|timeout|cancelled
    VALUE:<label>         (one per selected option, resolved value → label)
    FREE_TEXT:<text>      (last line group; raw text, may span lines)

Usage (normally via the ``aitask_relay_ask.sh`` wrapper):
    python3 -m chatlink.relay_ask --relay-dir <session_dir> \
        --text "Which module?" --header "Module" \
        --option "parser::the tokenizer" --option "renderer::the output" \
        [--multi-select] [--free-text] [--timeout 90]

Spec: ``aidocs/chat/qa_relay_protocol.md``.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from chatlink.relay import (
    Answer,
    Question,
    RelayError,
    SessionDir,
    assign_option_values,
)

POLL_INTERVAL_S = 1.0
# Default deliberately under the ~120 s default Bash-tool timeout of a
# calling headless agent (spike finding — see the protocol doc).
DEFAULT_TIMEOUT_S = 90


def _parse_option(spec: str) -> tuple[str, str]:
    """``label::description`` → (label, description); description optional."""
    label, sep, desc = spec.partition("::")
    return label, desc if sep else ""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="relay_ask",
        description="Ask a blocking question through the chatlink relay spool.")
    p.add_argument("--relay-dir", required=True,
                   help="the relay SESSION directory (bind-mounted in sandbox)")
    p.add_argument("--text", required=True, help="question text")
    p.add_argument("--header", default="", help="short header/topic chip")
    p.add_argument("--option", action="append", default=[],
                   metavar="LABEL::DESC",
                   help="an option (repeatable); value ids are auto-assigned")
    p.add_argument("--multi-select", action="store_true")
    p.add_argument("--free-text", action="store_true",
                   help="offer a free-text answer path")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S,
                   metavar="SECONDS")
    return p


def _emit(answer: Answer, label_by_value: dict[str, str]) -> None:
    print(f"STATUS:{answer.status}")
    if answer.status != "answered":
        return
    for v in answer.values:
        print(f"VALUE:{label_by_value.get(v, v)}")
    if answer.free_text is not None:
        print(f"FREE_TEXT:{answer.free_text}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    session_path = Path(args.relay_dir)
    if not session_path.is_dir():
        print(f"ERROR:relay dir does not exist: {session_path}",
              file=sys.stderr)
        return 2

    session = SessionDir(session_path)
    try:
        seq = session.next_seq()
        options = assign_option_values(
            [_parse_option(s) for s in args.option])
        question = Question(
            id=f"q-{session.session_id}-{seq}",
            seq=seq,
            session_id=session.session_id,
            text=args.text,
            header=args.header,
            options=options,
            multi_select=args.multi_select,
            allow_free_text=args.free_text,
            timeout_s=args.timeout,
        )
        session.write_question(question)
    except RelayError as exc:
        print(f"ERROR:{exc}", file=sys.stderr)
        return 2

    label_by_value = {o.value: o.label for o in options}
    deadline = time.monotonic() + args.timeout

    while time.monotonic() < deadline:
        answer = _read_valid_answer(session, seq)
        if answer is not None:
            _emit(answer, label_by_value)
            return 0
        time.sleep(min(POLL_INTERVAL_S, max(deadline - time.monotonic(), 0)))

    # Deadline reached — final poll, then durably record the timeout
    # (never overwriting an answer that raced in).
    answer = _read_valid_answer(session, seq)
    if answer is None:
        timeout_answer = Answer(id=question.id, seq=seq, status="timeout")
        if not session.write_answer(timeout_answer, overwrite=False):
            # An answer landed between the poll and the write — consume it.
            answer = _read_valid_answer(session, seq)
        else:
            answer = timeout_answer
    if answer is None:  # unreadable racing answer: fail-safe as timeout
        answer = Answer(id=question.id, seq=seq, status="timeout")
    _emit(answer, label_by_value)
    return 0


def _read_valid_answer(session: SessionDir, seq: int) -> Answer | None:
    """Read this seq's answer if present and schema-valid; a malformed
    answer file is treated as absent (fail-safe: the timeout path will
    terminate the wait rather than crash the asking agent)."""
    try:
        return session.read_answer(seq)
    except (RelayError, ValueError):
        return None


if __name__ == "__main__":
    sys.exit(main())
