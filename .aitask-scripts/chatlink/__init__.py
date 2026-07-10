"""chatlink — chat-gateway bridge for spawned headless code agents.

The structured Q&A relay seam of the t1120 umbrella: a spawned agent asks
clarifying questions through a file-based JSON spool; the chatlink gateway
renders them as chat components and routes the answers back. Protocol spec:
``aidocs/chat/qa_relay_protocol.md`` (normative).

Modules: ``relay`` (spool + schemas + identity; stdlib-only — the agent
side imports nothing else), ``render`` (question → ``chat`` components;
gateway side only), ``relay_ask`` (the agent-side blocking ask CLI),
``paths`` (secure runtime dirs + config resolution; gateway side),
``config`` (gateway config schema + fault-tolerant loader; gateway side),
``policy`` (deny-by-default authorization above ``IdentityClaims``;
gateway side), ``sessions_store`` (persistent gateway session records;
gateway side), ``reconcile`` (pure startup/reconnect planners; gateway
side), ``intake`` (intake + minimal interaction pipeline; gateway side),
``spawn_seam`` (sandbox-launcher protocol stub — real backend in t1120_5),
``audit`` (gateway audit log), ``daemon`` (the Textual-free headless
gateway daemon behind ``ait chatlink --headless``), ``flow`` (spool→post
pump + payload completion sink; gateway side), ``payload_guard``
(fail-closed gateway payload validation), ``task_create`` (validated
payload → ``aitask_create.sh`` + push), ``chatlink_app`` (the Textual TUI
behind ``ait chatlink`` — the ONLY module that may import Textual).

Contract: ``relay`` and ``relay_ask`` import ONLY from within ``chatlink/``
and the stdlib — no ``chat/`` module, no aitasks framework module
(guard-tested by ``tests/test_chatlink_relay.sh``). ``render`` may import
``chat``; ``paths``/``config``/``policy`` may import ``yaml`` /
``config_utils`` (they run in the gateway process). Importing any
``chatlink.*`` module requires only ``.aitask-scripts`` on ``sys.path``.
"""
