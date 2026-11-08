#!/usr/bin/env python3
"""stub_agent.py - a stand-in for ``aitask_codeagent.sh --headless invoke relations``.

Invoked by the worker (through AIT_RELATIONS_AGENT_CMD) as
``stub_agent.py <prompt_file> <input_dir>``. It prints Claude's
``--output-format json`` result shape. Behaviour comes from the spec file named
by STUB_AGENT_SPEC:

    {"mode": "ok" | "fenced" | "invalid" | "two_objects" | "error" | "exit1"
             | "sleep" | "spawn_child_sleep" | "no_usage",
     "considered": [...], "relations": [...],
     "launch_log": "<file>",      # one line per launch: "<pid>"
     "pid_file": "<file>",        # spawn_child_sleep: "<leader> <child>"
     "check_dead": "<file>",      # pids that must be dead when this one starts
     "violation": "<file>",       # written when a check_dead pid is still alive
     "sleep_s": 30,
     "hold_s": 0.5,                # sleep before answering (ok modes)
     "timeline": "<file>"}         # "start <t>" / "end <t>" per launch
"""
import json
import os
import subprocess
import sys
import time


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main():
    prompt, inputs = sys.argv[1], sys.argv[2]
    with open(os.environ["STUB_AGENT_SPEC"], encoding="utf-8") as fh:
        spec = json.load(fh)
    if spec.get("launch_log"):
        with open(spec["launch_log"], "a") as fh:
            fh.write(f"{os.getpid()}\n")
    if spec.get("check_dead") and os.path.exists(spec["check_dead"]):
        with open(spec["check_dead"]) as fh:
            pids = [int(p) for p in fh.read().split()]
        still = [p for p in pids if alive(p)]
        if still:
            with open(spec["violation"], "w") as fh:
                fh.write(" ".join(map(str, still)))
    assert os.path.exists(prompt) and os.path.isdir(inputs)
    mode = spec.get("mode", "ok")
    if spec.get("timeline"):
        with open(spec["timeline"], "a") as fh:
            fh.write(f"start {time.time()}\n")
    if spec.get("hold_s"):
        time.sleep(spec["hold_s"])
    if spec.get("timeline"):
        with open(spec["timeline"], "a") as fh:
            fh.write(f"end {time.time()}\n")
    if mode in ("sleep", "spawn_child_sleep"):
        if mode == "spawn_child_sleep":
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
            with open(spec["pid_file"], "w") as fh:
                fh.write(f"{os.getpid()} {child.pid}")
        time.sleep(spec.get("sleep_s", 600))
    if mode == "exit1":
        sys.stderr.write("stub agent failing\n")
        return 1
    payload = {"considered": spec.get("considered", []), "relations": spec.get("relations", [])}
    if mode == "invalid":
        payload = {"relations": [{"from": "x", "to": "y", "type": "teleports"}]}
    text = json.dumps(payload)
    if mode == "fenced":
        text = "```json\n" + text + "\n```"
    if mode == "two_objects":
        text = text + "\n" + text
    outer = {"type": "result", "subtype": "success", "is_error": mode == "error",
             "result": text, "total_cost_usd": 0.0123,
             "usage": {"input_tokens": 10, "cache_creation_input_tokens": 5,
                       "cache_read_input_tokens": 100, "output_tokens": 42}}
    if mode == "no_usage":
        outer.pop("usage")
        outer.pop("total_cost_usd")
    print(json.dumps(outer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
