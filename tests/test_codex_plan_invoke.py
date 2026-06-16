"""Regression tests for the Codex plan-mode PTY helper.

Run:
  python3 tests/test_codex_plan_invoke.py
"""
from __future__ import annotations

import os
import stat
import sys
import tempfile
import textwrap
from pathlib import Path

import pexpect


REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / ".aitask-scripts" / "aitask_codex_plan_invoke.py"


def _write_fake(tmpdir: Path, name: str, body: str) -> Path:
    path = tmpdir / name
    path.write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n"
        + textwrap.dedent(body).lstrip(),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _spawn_helper(fake_codex: Path, prompt: str = "$aitask-pick 1006") -> pexpect.spawn:
    env = os.environ.copy()
    env["AITASK_CODEX_PLAN_STARTUP_DELAY"] = "0"
    env["AITASK_CODEX_PLAN_READY_TIMEOUT"] = "5"
    return pexpect.spawn(
        sys.executable,
        [
            str(HELPER),
            "--prompt",
            prompt,
            "--",
            str(fake_codex),
        ],
        encoding="utf-8",
        timeout=5,
        env=env,
    )


def test_immediate_ready_receives_plan_prompt() -> None:
    with tempfile.TemporaryDirectory() as raw_tmpdir:
        tmpdir = Path(raw_tmpdir)
        fake = _write_fake(
            tmpdir,
            "fake_ready.py",
            r"""
            import sys

            print("Explain this codebase", flush=True)
            line = sys.stdin.readline().strip()
            print(f"PROMPT:{line}", flush=True)
            """,
        )

        child = _spawn_helper(fake)
        child.expect_exact("PROMPT:/plan $aitask-pick 1006")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0


def test_trust_gate_is_not_given_plan_prompt() -> None:
    with tempfile.TemporaryDirectory() as raw_tmpdir:
        tmpdir = Path(raw_tmpdir)
        fake = _write_fake(
            tmpdir,
            "fake_trust_then_ready.py",
            r"""
            import sys

            print("Do you trust the contents of this directory?", flush=True)
            answer = sys.stdin.readline().strip()
            if answer.startswith("/plan"):
                print(f"EARLY_PROMPT:{answer}", flush=True)
                sys.exit(42)
            print(f"ANSWER:{answer}", flush=True)
            print("Explain this codebase", flush=True)
            line = sys.stdin.readline().strip()
            print(f"PROMPT:{line}", flush=True)
            """,
        )

        child = _spawn_helper(fake)
        child.expect_exact("Do you trust the contents of this directory?")
        child.sendline("1")
        child.expect_exact("ANSWER:1")
        child.expect_exact("PROMPT:/plan $aitask-pick 1006")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0


def test_child_exit_before_ready_preserves_exit_status() -> None:
    with tempfile.TemporaryDirectory() as raw_tmpdir:
        tmpdir = Path(raw_tmpdir)
        fake = _write_fake(
            tmpdir,
            "fake_exits.py",
            r"""
            import sys

            print("Do you trust the contents of this directory?", flush=True)
            sys.exit(37)
            """,
        )

        child = _spawn_helper(fake)
        child.expect_exact("Do you trust the contents of this directory?")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 37


if __name__ == "__main__":
    tests = [
        test_immediate_ready_receives_plan_prompt,
        test_trust_gate_is_not_given_plan_prompt,
        test_child_exit_before_ready_preserves_exit_status,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"  FAIL: {test.__name__}: {exc!r}")
    print()
    if failures:
        print(f"FAIL: {failures}/{len(tests)} tests failed")
        raise SystemExit(1)
    print(f"PASS: all {len(tests)} tests passed")
