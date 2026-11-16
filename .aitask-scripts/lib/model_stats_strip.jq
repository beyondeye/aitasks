# model_stats_strip.jq - remove the legacy stats counters from a model registry.
#
# The one definition of "a models_<agent>.json without its counters" (t1912_5).
# usagestats / verifiedstats live on the aitask-stats branch; the registry keeps
# every other field, including the `verified` prior. Used by the stats migration
# (remote and no-remote strips), `aitask_opencode_models.sh --sync-seed` and the
# refresh-code-models seed sync. jq's default output keeps the registry files
# byte-stable (2-space indent, key order unchanged), so stripping an
# already-stripped file reproduces it exactly.
if (.models | type) == "array"
then .models |= map(if type == "object" then del(.usagestats, .verifiedstats) else . end)
else . end
