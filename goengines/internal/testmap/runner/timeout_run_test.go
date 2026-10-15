package runner

import (
	"reflect"
	"slices"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// threeRepo is a repository with one runner over three units.
func threeRepo(t *testing.T, describe, yaml, run string) *fixture.Repo {
	t.Helper()
	r := newRepo(t, map[string]string{"tests/a.sh": "", "tests/b.sh": "", "tests/c.sh": ""})
	put(t, r, "shell", spec{describe: describe, list: "tests/a.sh|file|a\ntests/b.sh|file|b\ntests/c.sh|file|c\n", run: run})
	runners(t, r, yaml)
	commitAll(t, r)
	return r
}

// timedRun runs everything and fails the test if the run took longer than
// limit — a broken kill must fail, never hang the suite.
func timedRun(t *testing.T, r *fixture.Repo, limit time.Duration) *RunReport {
	t.Helper()
	start := time.Now()
	rep := runAll(t, r)
	if d := time.Since(start); d > limit {
		t.Fatalf("run took %v (limit %v)", d, limit)
	}
	return rep
}

// A per_unit runner enforces each unit's bound itself: the over-time unit is
// `timeout`, the next unit in the same invocation still runs and passes, and
// the invocation carries no cause (a unit result, not a mechanism failure).
func TestTimeoutPerUnitRunnerEnforced(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := threeRepo(t, "unit: file\ntimeouts: per_unit", "runners:\n  - name: shell\n    timeout_s: 1\n",
		`for i in $IDS; do start $i
  if [ $i = tests/a.sh ]; then d=30; else d=0; fi
  if timeout 0.3 sleep $d; then row $i pass 1; else row $i timeout 300; fi
done; exit 1`)
	rep := timedRun(t, r, 10*time.Second)
	want := map[string]string{"tests/a.sh": StatusTimeout, "tests/b.sh": StatusPass, "tests/c.sh": StatusPass}
	if rec := rep.Invocations[0]; !reflect.DeepEqual(statuses(rep), want) || rec.Cause != "" || rec.Killed || rep.Exit() != 1 {
		t.Fatalf("%v %+v exit %d", statuses(rep), rec, rep.Exit())
	}
}

// A per_unit runner that reports a result past its bound did not enforce it.
func TestTimeoutPerUnitNotEnforced(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := threeRepo(t, "unit: file\ntimeouts: per_unit", "runners:\n  - name: shell\n    timeout_s: 1\n",
		`for i in $IDS; do start $i; row $i pass 1; done
sed -i 's|"id":"tests/b.sh","status":"pass","duration_ms":1|"id":"tests/b.sh","status":"pass","duration_ms":9000|' "$R"`)
	rep := timedRun(t, r, 10*time.Second)
	rec := rep.Invocations[0]
	if statuses(rep)["tests/b.sh"] != StatusError || rec.Cause != CauseReconciliation || !slices.Equal(rec.ProtocolErrors, []string{"timeout_not_enforced:tests/b.sh"}) {
		t.Fatalf("%v %+v", statuses(rep), rec)
	}
}

// The engine's separate ceiling: a per_unit runner hanging on unit b is
// killed at max_invocation_s — a keeps its pass, the started b is
// `timeout`, the never-started c is `not_started`.
func TestTimeoutInvocationMax(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := threeRepo(t, "unit: file\ntimeouts: per_unit", "max_invocation_s: 1\nrunners:\n  - name: shell\n    timeout_s: 1\n",
		"start tests/a.sh; row tests/a.sh pass; start tests/b.sh; exec sleep 30")
	rep := timedRun(t, r, 10*time.Second)
	rec := rep.Invocations[0]
	want := map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusTimeout, "tests/c.sh": StatusNotStarted}
	if !reflect.DeepEqual(statuses(rep), want) || !rec.Killed || rec.TimedOut != BoundInvocationMax || rec.Cause != CauseTimeout || rec.CauseDetail != BoundInvocationMax || rep.Exit() != 1 {
		t.Fatalf("%v %+v", statuses(rep), rec)
	}
}

// A batch runner is bounded only by its explicit batch timeout. With start
// rows the kill is attributed per unit; without any, every unreported unit
// is `batch_timeout`. Reported results survive either way.
func TestTimeoutBatchBounded(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	yaml := "runners:\n  - name: shell\n    timeout_s: 1\n    batch_timeout_s: 1\n"
	for run, want := range map[string]map[string]string{
		"start tests/a.sh; row tests/a.sh pass; start tests/b.sh; exec sleep 30": {"tests/a.sh": StatusPass, "tests/b.sh": StatusTimeout, "tests/c.sh": StatusNotStarted},
		"row tests/a.sh pass; exec sleep 30":                                     {"tests/a.sh": StatusPass, "tests/b.sh": StatusBatchTimeout, "tests/c.sh": StatusBatchTimeout},
	} {
		rep := timedRun(t, threeRepo(t, "unit: file\ntimeouts: batch", yaml, run), 10*time.Second)
		rec := rep.Invocations[0]
		if !reflect.DeepEqual(statuses(rep), want) || rec.TimedOut != BoundBatch || rec.Cause != CauseTimeout || rec.DeadlineS != 1 {
			t.Errorf("%q: %v %+v", run, statuses(rep), rec)
		}
	}
}

// timeouts: none — the engine bounds each unit: two units are two
// invocations, the hanging one is killed at its own timeout_s, the other
// passes in its own invocation.
func TestTimeoutNoneSingletons(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"tests/a.sh": "", "tests/b.sh": ""})
	put(t, r, "shell", spec{describe: "unit: file", list: "tests/a.sh|file|a\ntests/b.sh|file|b\n",
		run: "for i in $IDS; do [ $i = tests/a.sh ] && exec sleep 30; row $i pass; done"})
	runners(t, r, "runners:\n  - name: shell\n    timeout_s: 0.5\n")
	commitAll(t, r)
	rep := timedRun(t, r, 10*time.Second)
	if len(rep.Invocations) != 2 {
		t.Fatalf("%d invocations", len(rep.Invocations))
	}
	a, b := rep.Invocations[0], rep.Invocations[1]
	if a.Cause != CauseTimeout || a.CauseDetail != BoundUnit || a.DeadlineS != 0.5 || b.Cause != "" {
		t.Fatalf("records %+v %+v", a, b)
	}
	if !reflect.DeepEqual(statuses(rep), map[string]string{"tests/a.sh": StatusTimeout, "tests/b.sh": StatusPass}) {
		t.Fatalf("%v", statuses(rep))
	}
}

// not_started is reserved for engine kills: a runner that exits on its own
// after starting b without a result leaves b `missing` (reconciliation).
func TestTimeoutNotStartedVsMissing(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := threeRepo(t, "unit: file\ntimeouts: per_unit", "runners:\n  - name: shell\n    timeout_s: 1\n",
		"start tests/a.sh; row tests/a.sh pass; start tests/b.sh; exit 1")
	rep := timedRun(t, r, 10*time.Second)
	rec := rep.Invocations[0]
	want := map[string]string{"tests/a.sh": StatusPass, "tests/b.sh": StatusMissing, "tests/c.sh": StatusMissing}
	if !reflect.DeepEqual(statuses(rep), want) || rec.Killed || rec.Cause != CauseReconciliation {
		t.Fatalf("%v %+v", statuses(rep), rec)
	}
}
