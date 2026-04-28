#!/usr/bin/env bash
# Resolve the Python interpreter for tests that need yaml / textual / rich.
# Prefers the shared aitask venv at ~/.aitask/venv/bin/python (where ait setup
# installs the deps); falls back to system python3.
# shellcheck disable=SC2034  # AITASK_PYTHON is consumed by sourcing test scripts

if [[ -z "${_AIT_VENV_PYTHON_LOADED:-}" ]]; then
    _AIT_VENV_PYTHON_LOADED=1

    AITASK_PYTHON="python3"
    if [[ -x "$HOME/.aitask/venv/bin/python" ]]; then
        AITASK_PYTHON="$HOME/.aitask/venv/bin/python"
    fi
fi
