---
Task: t2250_fix_gitlab_issue_link_readback.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

`_gitlab_verify_contribution_label` now recognises every link form GitLab emits for a new issue, so the dropped-label warning added by t2241 actually fires. The read-back regex changed from `https://[^[:space:]]+/-/issues/[0-9]+` to `https?://[^[:space:]]+/-/(issues|work_items)/[0-9]+`.

## Files Modified

- `.aitask-scripts/aitask_contribute.sh`: changed the regex in `_gitlab_verify_contribution_label`, with a comment naming the link forms and where they appear. The iid is still taken with `${url##*/}`, which works for both path forms.
- `tests/test_contribute.sh`:
  - The `_t2241_create` glab stub now prints `- Creating issue in o/r` followed by `$T2241_URL`. Its default is the real glab 1.126 output against GitLab CE 19.4.5 captured in t2248 Part B, an `http://…/-/work_items/<iid>` link.
  - The Test 44–47 URL assertions use `$T2241_URL`.
  - New Test 48 loops over four link forms: http work_items (the Part B capture), https work_items (gitlab.com), legacy https issues, and a nested-group legacy issues link. Each one must produce the dropped-label warning and the iid read-back, with no "Could not verify".
  - A merge-request link must still report "Could not verify" and must make no read-back call.

## Probable User Intent

The t2248 Part B live run on a local GitLab CE 19.4.5 found defect D1:
- the non-member's label really was silently dropped;
- but `gitlab_create_issue` printed "Could not verify" for every issue, because glab prints `http://localhost:8929/maint/aitask-ct/-/work_items/1`;
- gitlab.com's REST `web_url` is also `/-/work_items/<iid>` (gitlab-org/cli #8724).

So the warning t2241 shipped could never fire on gitlab.com. The t2241 unit test missed it because its fake glab output used `https://gitlab.com/o/r/-/issues/77`. The user asked for the fix to be made right away and recorded through aitask-wrap.

## Final Implementation Notes

- **Actual work done:**
  - The regex fix above.
  - The fixture switched to the real captured output.
  - Test 48 added.
  - `bash tests/test_contribute.sh`: 170 passed, 0 failed. `shellcheck .aitask-scripts/aitask_contribute.sh` is clean.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:**
  - The fixture uses the verbatim Part B capture, not a hand-written link, so the unit test matches what the real tool prints.
  - Pre-fix control: the new `tests/test_contribute.sh` was run in a scratch worktree of HEAD (`git worktree add --detach`, removed afterwards). 161 passed and 9 failed. The failures were the Test 44 dropped-label warning and iid read-back, the Test 45 "no warning", and Test 48's http work_items and https work_items forms (3 assertions each). The legacy `/-/issues/` forms and the merge-request control passed on both versions.
  - Not re-verified live: the Part B containers had already been torn down, so the fix is proven against the captured real output rather than a fresh GitLab run. Re-running t2248 Part B would show the warning end-to-end.
  - The GitHub counterpart `_github_verify_contribution_label` (`https://…/issues/<n>`) is unchanged: GitHub issue URLs keep that form.
