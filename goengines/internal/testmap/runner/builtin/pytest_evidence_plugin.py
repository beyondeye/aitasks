"""ait-testmap pytest evidence plugin (M3.2f): engine-owned and observe-only.

The pytest builtin loads it with `-p _aitestmap_pytest_evidence` from an
engine-private directory on PYTHONPATH, and the engine reads what it writes
as the run's evidence. It records exact runtime identities: the rootdir, the
collected node ids, every collect report that did not pass, every test phase
report, and the exit status, one JSON object per line, into the file
$AIT_TESTMAP_PYTEST_EVIDENCE.

It only records: it changes no item, report or outcome, and it judges
nothing; the engine owns every rule. Only the controller writes: on an
xdist worker (or with the variable unset) it does nothing, because xdist
forwards every worker report to the controller's hooks.
"""

import json
import os
import platform

import pytest

_MESSAGE_MAX = 512
_out = None


def _write(record):
    if _out is not None:
        _out.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")


def _bounded(text):
    if text is None:
        return ""
    text = str(text).strip()
    first = text.split("\n", 1)[0] if text else ""
    return first[:_MESSAGE_MAX]


def _skip_reason(longrepr):
    # A skip's longrepr is (path, lineno, "Skipped: <reason>").
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        reason = str(longrepr[2])
        if reason.startswith("Skipped: "):
            reason = reason[len("Skipped: "):]
        return _bounded(reason)
    return _bounded(longrepr)


def _message(report):
    if report.outcome == "skipped":
        return _skip_reason(report.longrepr)
    if report.outcome == "failed":
        crash = getattr(report.longrepr, "reprcrash", None)
        if crash is not None and getattr(crash, "message", None):
            return _bounded(crash.message)
        return _bounded(report.longreprtext)
    return ""


def pytest_configure(config):
    global _out
    path = os.environ.get("AIT_TESTMAP_PYTEST_EVIDENCE")
    if not path or hasattr(config, "workerinput"):
        return
    _out = open(path, "a", encoding="ascii", buffering=1)
    _write({
        "k": "session",
        "v": 1,
        "rootdir": str(config.rootpath),
        "pytest": pytest.__version__,
        "python": platform.python_version(),
        "impl": platform.python_implementation(),
    })


def pytest_collectreport(report):
    if report.outcome != "passed":
        _write({"k": "collect", "nodeid": report.nodeid, "outcome": report.outcome, "message": _message(report)})


def pytest_collection_finish(session):
    _write({"k": "items", "nodeids": [item.nodeid for item in session.items]})


def pytest_runtest_logreport(report):
    xfail = getattr(report, "wasxfail", None)
    _write({
        "k": "test",
        "nodeid": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
        "xfail": None if xfail is None else _bounded(xfail),
        "message": _message(report),
        "duration": float(getattr(report, "duration", 0.0) or 0.0),
    })


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    _write({"k": "end", "exitstatus": int(exitstatus)})


def pytest_unconfigure(config):
    global _out
    if _out is not None:
        _out.close()
        _out = None
