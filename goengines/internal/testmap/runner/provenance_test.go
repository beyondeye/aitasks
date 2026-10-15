package runner

import (
	"encoding/json"
	"os"
	"path/filepath"
	"slices"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

// provRepo is a repository with one passing runner and committed files to
// dirty. ignoreState decides whether .gitignore covers the state directory.
func provRepo(t *testing.T, run string, ignoreState bool) *fixture.Repo {
	t.Helper()
	files := map[string]string{
		"tests/a.sh": "", "src/del_staged": "1\n", "src/del_unstaged": "2\n", "src/mod": "3\n",
	}
	r := newRepo(t, files)
	if !ignoreState {
		r.Write(t, ".gitignore", "")
	}
	put(t, r, "shell", spec{describe: "unit: file", list: "tests/a.sh|file|a\n", run: run})
	runners(t, r, "runners:\n  - name: shell\n    timeout_s: 5\n")
	commitAll(t, r)
	return r
}

func record(t *testing.T, r *fixture.Repo, rep *RunReport) Record {
	t.Helper()
	var rec Record
	b, err := os.ReadFile(filepath.Join(r.Dir, filepath.FromSlash(rep.Dir), "inv-001", "record.json"))
	if err != nil || json.Unmarshal(b, &rec) != nil {
		t.Fatalf("record.json: %v", err)
	}
	return rec
}

// Every dirty shape lands in the record's modified set: a staged deletion,
// an unstaged deletion, an untracked file and a modified tracked file.
// Negative control: a clean tree records an empty set — also when nothing
// ignores the engine's own state directory.
func TestRecordProvenance(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	for _, ignore := range []bool{true, false} {
		r := provRepo(t, "row tests/a.sh pass", ignore)
		head := r.Head(t)
		clean := record(t, r, runAll(t, r))
		if len(clean.Modified) != 0 || clean.HeadStart != head || clean.HeadEnd != head {
			t.Fatalf("clean tree (ignore=%v): %+v", ignore, clean)
		}
	}
	r := provRepo(t, "row tests/a.sh pass", true)
	r.Run(t, "rm", "-q", "src/del_staged")
	r.Remove(t, "src/del_unstaged")
	r.Write(t, "src/mod", "changed\n")
	r.Write(t, "src/untracked", "new\n")
	rep, err := Run(bg, r.Dir, Options{All: true, RunID: "dirty"})
	if err != nil {
		t.Fatal(err)
	}
	rec := record(t, r, rep)
	want := []string{"src/del_staged", "src/del_unstaged", "src/mod", "src/untracked"}
	if !slices.Equal(rec.Modified, want) || rec.Cause != "" {
		t.Fatalf("modified %v want %v (%+v)", rec.Modified, want, rec)
	}
}

// A change made during the invocation is captured at its end: HEAD moving
// and a file dirtied mid-run are both recorded.
func TestRecordHeadMoved(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := provRepo(t, `git -C "$AIT_TESTMAP_ROOT" commit -q --allow-empty -m moved
echo mid > "$AIT_TESTMAP_ROOT/src/mod"
row tests/a.sh pass`, true)
	before := r.Head(t)
	rec := record(t, r, runAll(t, r))
	after := r.Head(t)
	if before == after || rec.HeadStart != before || rec.HeadEnd != after || !slices.Equal(rec.Modified, []string{"src/mod"}) {
		t.Fatalf("head %s→%s record %+v", before, after, rec)
	}
}

// A mechanism failure carries its cause in the written record.
func TestRecordMechanismCause(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := provRepo(t, "exit 5", true)
	rep := runAll(t, r)
	rec := record(t, r, rep)
	if rec.Cause != CauseMechanism || rec.CauseDetail != "runner_exit:5" || rep.Exit() != 3 {
		t.Fatalf("%+v exit %d", rec, rep.Exit())
	}
}
