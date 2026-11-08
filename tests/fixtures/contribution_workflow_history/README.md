# Shipped contribution-check workflow templates (t2235)

Byte-exact copies of every GitHub workflow template `ait setup` shipped before
the current one, named `<order>_<commit>.yml` (oldest first). They are test data
for `tests/test_setup_contribution_workflow.sh`, which needs them to exist even
in a shallow clone where `git log` cannot reach the history.

When you change `.aitask-scripts/ci_templates/github/contribution-check.yml`,
add the OUTGOING version here (next order number, the commit that shipped it)
and append its sha256 to `_CONTRIBUTION_WORKFLOW_SHIPPED_SHA256` in
`.aitask-scripts/aitask_setup.sh`. The test fails until both are done.
