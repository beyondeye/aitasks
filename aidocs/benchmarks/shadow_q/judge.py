"""Blinded scoring of shadow ``>q`` answers by both agents' judges (t2179).

* Answers get random blind ids. Agent self-references are stripped, and the
  stripping is logged privately.
* The prompt is the frozen ``judge_prompt.md`` plus ``rubric.md``, the scenario's
  private ``reference.md`` and the screen the subject saw.
* The Claude judge runs with ``--tools ""``. The Codex judge runs read-only in an
  empty scratch dir, and any ``command_execution`` is recorded on the judgment.
* Calibration controls are judged **first**, per scenario × judge. A judge that
  orders a scenario's controls wrongly is not used for that scenario.
* Numbers go to the public ``scores.jsonl``. Rationales and the blinding map go
  to the private store.
"""
from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path

import validate as V
from store import PrivateSink, PublicSink, sha256_file

HERE = Path(__file__).resolve().parent
DIMENSIONS = ("factual_correctness", "decision_explained", "recommendation_reasoning",
              "unsupported_claims", "readability", "could_choose")
SELF_REF = re.compile(
    r"\b(Claude(?: Code)?|Codex|GPT[-\w.]*|gpt-[\w.-]+|claude-[\w.-]+|OpenAI|Anthropic|Opus|Sonnet|Haiku)\b",
    re.I)


def blind(text: str) -> tuple[str, int]:
    out, n = SELF_REF.subn("[assistant]", text)
    return out, n


def build_prompt(blind_id: str, answer: str, reference: str, screen: str, task: str = "") -> str:
    tpl = (HERE / "judge_prompt.md").read_text(encoding="utf-8")
    rubric = (HERE / "rubric.md").read_text(encoding="utf-8")
    return (tpl.replace("{rubric}", rubric).replace("{reference}", reference)
            .replace("{screen}", screen).replace("{task}", task or "(none)")
            .replace("{blind_id}", blind_id).replace("{answer}", answer))


TASK_ALIASES = {"_aitasks": "aitasks", "_aiplans": "aiplans"}


def task_context(store: Path, scenario: str) -> str:
    """The task (and plan) files the subject's sandbox served for ``scenario``, labelled by sandbox path."""
    base = store / "fixtures" / scenario / "task"
    parts = []
    for f in sorted(base.rglob("*")) if base.is_dir() else []:
        if f.is_file():
            rel = "/".join(TASK_ALIASES.get(p, p) for p in f.relative_to(base).parts)
            parts.append(f"--- {rel} ---\n" + f.read_text(encoding="utf-8"))
    return "\n".join(parts)


def judge_argv(agent: str, cli_id: str, scratch: Path, limits: dict) -> list[str]:
    if agent == "claude":
        return ["claude", "-p", "--model", cli_id, "--output-format", "json", "--tools", "",
                "--permission-mode", "dontAsk", "--permission-prompts", "none",
                "--max-budget-usd", str(limits["claude_max_budget_usd_judge_call"])]
    return ["codex", "exec", "--json", "-m", cli_id, "-s", "read-only", "-C", str(scratch),
            "--skip-git-repo-check", "-"]


def extract_json(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if m:
        t = m.group(1)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(t[start:end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _score(v) -> bool:
    """A finite rubric score in [0, 3]."""
    return _num(v) is not None and math.isfinite(v) and 0 <= v <= 3


OPTION_DIMENSIONS = ("what_it_does", "benefit", "cost")


def valid_judgment(obj: dict | None) -> bool:
    """Strict shape check; anything out of range goes through the one re-ask, then parse_failed."""
    if not obj:
        return False
    if not all(_score(obj.get(d)) for d in DIMENSIONS):
        return False
    opts = obj.get("options")
    if not isinstance(opts, list) or not opts:
        return False
    for o in opts:
        if not isinstance(o, dict) or not all(_score(o.get(k)) for k in OPTION_DIMENSIONS):
            return False
    return isinstance(obj.get("advisory_only"), bool) and isinstance(obj.get("failure_flag"), bool)


def public_scores(obj: dict) -> dict:
    opts = obj["options"]
    per = [(o["what_it_does"] + o["benefit"] + o["cost"]) / 3 for o in opts]
    s = {d: obj[d] for d in DIMENSIONS}
    s["option_coverage_mean"] = round(sum(per) / len(per), 3)
    s["option_coverage_min"] = round(min(per), 3)
    s["options_listed"] = len(opts)
    s["advisory_only"] = obj["advisory_only"]
    s["failure_flag"] = obj["failure_flag"]
    s["composite"] = round(obj["decision_explained"] + s["option_coverage_mean"]
                           + obj["recommendation_reasoning"] + obj["could_choose"], 3)
    return s


def calibrated(shallow: dict | None, adequate: dict | None) -> bool:
    if not shallow or not adequate:
        return False
    return shallow["composite"] < adequate["composite"]


def disputed(a: dict, b: dict) -> bool:
    keys = list(DIMENSIONS) + ["option_coverage_mean"]
    return any(abs(a[k] - b[k]) > 1 for k in keys if k in a and k in b)


def judge_one(exp, agent: str, purpose: str, blind_id: str, prompt: str, scenario: str,
              control: str = "") -> dict | None:
    """One judgment with one re-ask on a parse failure. Returns public scores or None."""
    cli = exp.agents[agent]["cli_id"]
    scratch = exp.scratch_dir(f"judge-{agent}-{blind_id}")
    for attempt in (1, 2):
        reason = exp.budget.acquire(purpose, agent)
        if reason:
            exp.score_sink.append({"batch": exp.batch, "blind_id": blind_id, "judge": agent, "scenario": scenario,
                                   "control": control, "attempt": attempt,
                                   "outcome": f"not_run:pilot_stopped:{reason}"})
            return None
        rel = Path("judging") / exp.batch / f"{blind_id}.{agent}.a{attempt}"
        out_p = exp.private.path(str(rel) + ".stdout.jsonl")
        err_p = exp.private.path(str(rel) + ".stderr.txt")
        env, _ = exp.env_for_judge()
        rr = exp.run_cli(judge_argv(agent, cli, scratch, exp.limits), scratch, env, agent,
                         exp.limits["judge_call_timeout_s"], None, out_p, err_p,
                         exp.limits["kill_grace_s"], stdin_text=prompt)
        raw = out_p.read_text(encoding="utf-8", errors="replace")
        usage: dict = {}
        if agent == "claude":
            text = ""
            try:
                obj = json.loads(raw.strip().splitlines()[-1]) if raw.strip() else {}
            except (ValueError, IndexError):
                obj = {}
            text = obj.get("result", "") if isinstance(obj, dict) else ""
            if isinstance(obj, dict) and obj.get("total_cost_usd") is not None:
                usage["cost_usd"] = obj["total_cost_usd"]
            tools_used = 0
        else:
            events = V.parse_codex(raw)
            text = next((e.text for e in reversed(events) if e.kind == "text"), "")
            from harness import turn_usage, codex_noncached_tokens
            u = turn_usage("codex", events)
            usage = {k: u[k] for k in ("input_tokens", "cached_input_tokens", "output_tokens") if k in u}
            tools_used = sum(1 for e in events if e.kind == "tool")
        has_tokens = any(k in usage for k in ("input_tokens", "output_tokens"))
        exp.budget.add_usage(agent, usage.get("cost_usd"),
                             (usage.get("input_tokens", 0) - usage.get("cached_input_tokens", 0)
                              + usage.get("output_tokens", 0)) if agent == "codex" and has_tokens else None)
        exp.record_invocation(purpose, agent, blind_id, 0, rr.killed or f"exit_{rr.exit_code}", rr.latency_s,
                              usage)
        parsed = extract_json(text)
        ok = valid_judgment(parsed)
        exp.private.write_text(str(rel) + ".judgment.json", json.dumps(
            {"parsed": parsed, "raw_text": text, "tools_used": tools_used}, indent=2) + "\n")
        if ok:
            s = public_scores(parsed)
            exp.score_sink.append({"batch": exp.batch, "blind_id": blind_id, "judge": agent, "scenario": scenario,
                                   "scores": s, "failure_flag": parsed["failure_flag"], "control": control,
                                   "judge_prompt_sha256": sha256_file(HERE / "judge_prompt.md"),
                                   "rubric_sha256": sha256_file(HERE / "rubric.md"), "attempt": attempt,
                                   "outcome": "ok" if not tools_used else f"ok_tools_used_{tools_used}",
                                   "latency_s": round(rr.latency_s, 2), "usage": usage})
            return s
    exp.score_sink.append({"batch": exp.batch, "blind_id": blind_id, "judge": agent, "scenario": scenario,
                           "control": control, "attempt": 2, "outcome": "parse_failed"})
    return None


def judge_batch(exp, answers: list[dict], judges=("claude", "codex"), seed: int = 2179) -> dict:
    """Controls first (per scenario of the answers), then every answer, both judges."""
    rng = random.Random(seed)
    store = exp.store
    blind_map: dict = {}
    calib: dict = {}
    scenarios = sorted({a["scenario"] for a in answers}) or []
    control_scenarios = exp.control_scenarios or scenarios
    for sc in control_scenarios:
        ref = (store / "fixtures" / sc / "reference.md").read_text(encoding="utf-8")
        screen = (store / "fixtures" / sc / "screen_1.txt").read_text(encoding="utf-8")
        for judge in judges:
            res = {}
            for kind in ("shallow", "adequate"):
                bid = f"c{rng.randrange(16**6):06x}"
                blind_map[bid] = {"control": kind, "scenario": sc}
                text = (store / "fixtures" / sc / "controls" / f"{kind}.md").read_text(encoding="utf-8")
                res[kind] = judge_one(exp, judge, "control_judge", bid,
                                      build_prompt(bid, text, ref, screen, task_context(store, sc)), sc,
                                      control=kind)
            calib[(sc, judge)] = calibrated(res["shallow"], res["adequate"])
            exp.score_sink.append({"batch": exp.batch, "blind_id": f"calibration-{sc}", "judge": judge,
                                   "scenario": sc, "calibrated": calib[(sc, judge)], "outcome": "calibration"})
    exp.budget.release_reserve()
    order = list(answers)
    rng.shuffle(order)
    scores: dict = {}
    for a in order:
        bid = f"a{rng.randrange(16**6):06x}"
        raw = exp.private.path(a["answer_path"]).read_text(encoding="utf-8")
        text, n = blind(raw)
        blind_map[bid] = {"trial_id": a["trial_id"], "stripped": n}
        ref = (store / "fixtures" / a["scenario"] / "reference.md").read_text(encoding="utf-8")
        screen = (store / "fixtures" / a["scenario"] / "screen_1.txt").read_text(encoding="utf-8")
        prompt = build_prompt(bid, text, ref, screen, task_context(store, a["scenario"]))
        per = {}
        for judge in judges:
            per[judge] = judge_one(exp, judge, "answer_judge", bid, prompt, a["scenario"])
        scores[bid] = per
        if all(per.get(j) for j in judges) and len(judges) == 2:
            d = disputed(per[judges[0]], per[judges[1]])
            exp.score_sink.append({"batch": exp.batch, "blind_id": bid, "judge": "both", "scenario": a["scenario"],
                                   "disputed": d, "outcome": "agreement"})
    PrivateSink(store).write_text(Path("judging") / exp.batch / "blind_map.json",
                                  json.dumps(blind_map, indent=2) + "\n")
    return {"calibration": {f"{k[0]}|{k[1]}": v for k, v in calib.items()}, "scores": scores,
            "blind_map_size": len(blind_map)}
