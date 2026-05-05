"""Brainstorm engine: DAG operations, session management, and schema validation.

Manages the design space DAG for iterative AI architecture exploration.
Data lives in AgentCrew crew worktrees at .aitask-crews/crew-brainstorm-<task_num>/.
"""

from .brainstorm_op_refs import (
    OpDataRef,
    file_for_ref,
    list_op_definition,
    list_op_inputs,
    list_op_logs,
    list_op_outputs,
    resolve_ref,
)

__version__ = "0.1.0"

__all__ = [
    "OpDataRef",
    "file_for_ref",
    "list_op_definition",
    "list_op_inputs",
    "list_op_logs",
    "list_op_outputs",
    "resolve_ref",
]
