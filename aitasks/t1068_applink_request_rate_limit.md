---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [ait_bridge]
anchor: 985
created_at: 2026-06-24 22:27
updated_at: 2026-06-24 22:27
---

## Origin

Risk-mitigation ("after") follow-up for t985, created at Step 8d after implementation landed. t985 shipped a *concurrent* per-IP connection cap but explicitly deferred time-based throttling (documented residual).

## Risk addressed

No time-based per-IP request throttling · t985's `server.py` enforces a concurrent per-IP connection cap (`MAX_PER_IP`) but nothing bounds sustained request/verb rate from an already-paired client.

## Goal

Add per-IP (or per-bearer) token-bucket throttling of authenticated requests/verbs so a paired client cannot drive sustained abuse (e.g. high-rate send_keys/kill loops) even within the connection cap. Keep it cheap and LAN-appropriate; log throttle events to the existing audit log. Update `aidocs/applink/security.md` (listed there as the time-based-throttling residual). When needed: if a misbehaving or compromised paired client's sustained request rate becomes a practical concern.
