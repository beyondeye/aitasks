#!/usr/bin/env python3
"""Prepare/run the attended t2281 test without changing Codex configuration files.

Run from a separate terminal. Never inject answers: a human must use the form and
the ordinary Codex composer. --prepare prints the exact launch argv and creates
the durable fixture without launching a model. Reuse --state-dir across restarts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".aitask-scripts"))
from aitask_questions.store import Store


QUESTIONS = [
    {"id": "color", "text": "Prototype question 1 of 3: choose a sample color.", "kind": "choice",
     "options": [{"id": "blue", "label": "Blue", "description": "Use the blue sample."},
                 {"id": "green", "label": "Green", "description": "Use the green sample."}]},
    {"id": "name", "text": "Prototype question 2 of 3: what name should this sample have? "
     "For the timeout test, leave this form unanswered until it expires.", "kind": "text"},
    {"id": "finish", "text": "Prototype question 3 of 3: finish this test sequence?", "kind": "choice",
     "options": [{"id": "finish", "label": "Finish", "description": "Finish only this prototype test."},
                 {"id": "repeat", "label": "Repeat later", "description": "Record this preference; no workflow action."}]},
]

MULTI_QUESTIONS = [{
    "id": "dependencies", "kind": "multi", "page_size": 3,
    "text": "Multi-select prototype: select sample dependencies across three pages. "
            "Select two items on page 1 and Next; let page 2 time out; finish page 3 after recovery.",
    "options": [{"id": f"task-{n}", "label": f"Task {n}",
                 "description": f"Sample dependency {n}; this does not change any real task."}
                for n in range(1, 8)],
}]


def command(python, state_dir, timeout, outer_timeout, model=None, resume=None, multi_mode="native"):
    # JSON strings/arrays are valid for these TOML string/array values. Arguments
    # reach exec directly as a list, never shell interpolation.
    settings = {
        "command": str(python),
        "args": [str(ROOT / ".aitask-scripts/aitask_questions_server.py"), "--project", str(ROOT),
                 "--state-dir", str(state_dir), "--timeout", str(timeout), "--multiselect-mode", multi_mode],
        "tool_timeout_sec": outer_timeout,
    }
    argv = ["codex", "--no-daemon", "--no-alt-screen", "-C", str(ROOT)]
    for key, value in settings.items():
        argv.extend(["-c", f"mcp_servers.aitask_questions.{key}={json.dumps(value, ensure_ascii=False)}"])
    if model:
        argv.extend(["--model", model])
    if resume:
        argv.extend(["resume", resume])
    return argv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True, help="Python from the prototype venv")
    parser.add_argument("--state-dir", type=Path, required=True, help="private test state; keep across reconnects")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--outer-timeout", type=float, default=60)
    parser.add_argument("--model", help="optional explicit test model; otherwise configured default")
    parser.add_argument("--resume", help="Codex session ID from the previous probe, to test reconnection")
    parser.add_argument("--prepare", action="store_true", help="prepare fixture and print command only")
    parser.add_argument("--scenario", choices=["baseline", "multi"], default="baseline")
    parser.add_argument("--multiselect-mode", choices=["native", "text"], default="native")
    args = parser.parse_args()
    if not 0.05 <= args.timeout <= 900 or args.outer_timeout <= 0:
        parser.error("timeout must be 0.05..900 and outer-timeout must be positive")
    # Preserve the venv executable path: resolving its symlink would launch the
    # system interpreter, losing the isolated MCP installation.
    python = args.python.absolute()
    if not python.is_file():
        parser.error("--python does not exist")
    state_dir = args.state_dir.resolve()
    store = Store(state_dir, ROOT)
    fixture = QUESTIONS if args.scenario == "baseline" else MULTI_QUESTIONS
    checkpoint = "three-question-sequence" if args.scenario == "baseline" else "multi-selection"
    state = store.open("attended-prototype", checkpoint, "first", fixture, [])
    sid = state["session_id"]
    prompt = (
        "Run ONLY the attended question compatibility test, not aitask implementation. "
        "Use the aitask_questions MCP tools, never built-in request_user_input or Plan mode. "
        f"The durable question session is {sid}. Start with aitask_question_status. "
        "If pending, call aitask_question_resume without a prompt answer to show its next form. "
        "After an accepted form answer, call resume for the next question. "
        "On timeout/awaiting-chat-answer/unavailable/transport failure, END YOUR TURN: "
        "tell the user the pending question, session ID, and that they can answer at the ordinary composer. "
        "Do not poll, pick defaults, invent answers or perform any dependent work. "
        "On the next clearly relevant user answer, call resume with session_id, question_id and "
        "the exact user text as prompt_answer; this returns remaining forms. A status request or "
        "unrelated steering is not an answer. For multi-select recovery, also forward the "
        "pending_page.page_id and the user's exact JSON selected/action payload. "
        "Accepted pages advance with resume; they do not complete the whole question. "
        "On a complete receipt report all accepted answers and the full selected set "
        "and their channels; this test authorizes no implementation, commit, archive or security approval. "
        "Do not claim the test passed without observed results."
    )
    argv = command(python, state_dir, args.timeout, args.outer_timeout, args.model, args.resume, args.multiselect_mode)
    argv.append(prompt)
    record = {"question_session_id": sid, "argv": argv, "server_timeout": args.timeout,
              "outer_timeout": args.outer_timeout, "model_requested": args.model,
              "scenario": args.scenario, "multiselect_mode": args.multiselect_mode,
              "human_results": "not_recorded"}
    (state_dir / "launch.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Question session: {sid}\nState: {state_dir}\n", flush=True)
    if args.prepare:
        print(shlex.join(argv))
    else:
        os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
