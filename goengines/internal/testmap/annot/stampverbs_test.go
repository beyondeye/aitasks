package annot

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

var bg = context.Background()

// repo is a fixture repository with a registry and the clock pinned.
func repo(t *testing.T, files map[string]string) *fixture.Repo {
	t.Helper()
	r := fixture.New(t)
	r.Write(t, registry.ConfigPath, "contract: 1\nexclude: [\"tests/golden/**\"]\n")
	for p, c := range files {
		r.Write(t, p, c)
	}
	old := now
	now = func() time.Time { return time.Date(2026, 10, 12, 9, 0, 0, 0, time.UTC) }
	t.Cleanup(func() { now = old })
	return r
}

// blob10 is the stamp blob of content under the fixture's sha1 format.
func blob10(t *testing.T, content string) string {
	t.Helper()
	s, err := NewStamp(now(), []byte(content), "sha1")
	if err != nil {
		t.Fatal(err)
	}
	return s.Blob
}

type recorded struct {
	actor Actor
	edges []Restamp
}

// recordHooks registers a hook that records each call, for this test.
func recordHooks(t *testing.T) *[]recorded {
	t.Helper()
	var calls []recorded
	old := restampHooks
	restampHooks = append(restampHooks[:len(restampHooks):len(restampHooks)], func(_ context.Context, _ string, a Actor, e []Restamp) ([]string, error) {
		calls = append(calls, recorded{a, e})
		return nil, nil
	})
	t.Cleanup(func() { restampHooks = old })
	return &calls
}

func TestAnnotateAddsRestampsAndConfirms(t *testing.T) {
	r := repo(t, map[string]string{
		"src/a.sh":   "a\n",
		"src/b.sh":   "b\n",
		"tests/t.sh": "#!/bin/sh\n# header\n# testmap:covers src/a.sh @2026-01-01/0123456789\necho\n",
	})
	calls := recordHooks(t)
	human := Actor{Kind: Human, Value: "x@example.invalid"}
	res, err := Annotate(bg, r.Dir, registry.ID{Path: "tests/t.sh"}, []string{"src/a.sh", "src/b.sh", "src/a.sh"}, human)
	if err != nil {
		t.Fatal(err)
	}
	ba, bb := blob10(t, "a\n"), blob10(t, "b\n")
	want := "#!/bin/sh\n# header\n# testmap:covers src/a.sh @2026-10-12/" + ba + "\n# testmap:covers src/b.sh @2026-10-12/" + bb + "\necho\n"
	if got := readFile(t, r.Dir, "tests/t.sh"); got != want {
		t.Fatalf("got %q\nwant %q", got, want)
	}
	if a, rs, c, s := res.Counts(); a != 1 || rs != 1 || c != 0 || s != 0 || len(res.Wrote) != 1 {
		t.Errorf("counts %d %d %d %d wrote %v", a, rs, c, s, res.Wrote)
	}
	if len(*calls) != 1 || (*calls)[0].actor != human || len((*calls)[0].edges) != 2 {
		t.Fatalf("hook %+v", *calls)
	}
	e := (*calls)[0].edges
	if e[0].State != Restamped || e[0].Line != 3 || e[0].Before.Blob != "0123456789" || e[1].State != Added || e[1].Line != 4 {
		t.Errorf("edges %+v", e)
	}
	// Re-running confirms: nothing written, the hook still sees the edges.
	before := readFile(t, r.Dir, "tests/t.sh")
	res, err = Annotate(bg, r.Dir, registry.ID{Path: "tests/t.sh"}, []string{"src/a.sh", "src/b.sh"}, Actor{})
	if err != nil || len(res.Wrote) != 0 || readFile(t, r.Dir, "tests/t.sh") != before {
		t.Fatalf("re-run wrote: %v %v", res, err)
	}
	if _, _, c, _ := res.Counts(); c != 2 || len(*calls) != 2 || (*calls)[1].edges[0].State != Current {
		t.Errorf("re-run %+v %+v", res, *calls)
	}
}

func TestAnnotateMemberAndRefusals(t *testing.T) {
	r := repo(t, map[string]string{
		"src/a.kt":           "a\n",
		"tests/T.kt":         "object T {\n    // testmap:unit Welcome\n    fun w() = 1\n}\n",
		"tests/golden/x.sh":  "#!/bin/sh\n",
		"tests/notes.txt":    "x\n",
		"tests/open.sh":      "cat <<EOF\nnever closed\n",
		"tests/lookalike.sh": "cat <<EOF\n# testmap:covers src/a.kt\nEOF\n",
	})
	if err := os.Symlink(t.TempDir(), filepath.Join(r.Dir, "link")); err != nil {
		t.Fatal(err)
	}
	r.Write(t, "link/t.sh", "#!/bin/sh\n")
	res, err := Annotate(bg, r.Dir, registry.ID{Path: "tests/T.kt", Member: "Welcome"}, []string{"src/a.kt"}, Actor{})
	if err != nil || len(res.Stamps) != 1 || res.Stamps[0].State != Added {
		t.Fatalf("%+v %v", res, err)
	}
	if got := readFile(t, r.Dir, "tests/T.kt"); !strings.Contains(got, "    // testmap:unit Welcome\n    // testmap:covers src/a.kt @2026-10-12/") {
		t.Errorf("member placement: %q", got)
	}
	for _, tc := range []struct {
		id     registry.ID
		reason string
	}{
		{registry.ID{Path: "tests/T.kt", Member: "Nope"}, "no-member-block"},
		{registry.ID{Path: "tests/golden/x.sh"}, "excluded"},
		{registry.ID{Path: "tests/missing.sh"}, "missing"},
		{registry.ID{Path: "tests/notes.txt"}, "no-leader"},
		{registry.ID{Path: "tests/open.sh"}, "uncertain-context"},
		{registry.ID{Path: "link/t.sh"}, "not-a-file"},
	} {
		res, err := Annotate(bg, r.Dir, tc.id, []string{"src/a.kt"}, Actor{})
		if err != nil || len(res.Refused) != 1 || res.Refused[0].Reason != tc.reason || !res.Failed() {
			t.Errorf("%s: %+v %v, want %s", tc.id, res, err, tc.reason)
		}
	}
	// A heredoc look-alike is data: annotate inserts a real line, the body
	// stays byte-identical.
	res, err = Annotate(bg, r.Dir, registry.ID{Path: "tests/lookalike.sh"}, []string{"src/a.kt"}, Actor{})
	if err != nil || len(res.Stamps) != 1 || res.Stamps[0].State != Added {
		t.Fatalf("lookalike: %+v %v", res, err)
	}
	if got := readFile(t, r.Dir, "tests/lookalike.sh"); !strings.HasSuffix(got, "cat <<EOF\n# testmap:covers src/a.kt\nEOF\n") ||
		!strings.HasPrefix(got, "# testmap:covers src/a.kt @2026-10-12/") {
		t.Errorf("lookalike file: %q", got)
	}
}

// A source that cannot be stamped writes nothing at all (one file, all or
// nothing) — including through a symbolic-link parent.
func TestAnnotateAllOrNothing(t *testing.T) {
	outside := t.TempDir()
	writeFile(t, outside, "src.sh", "external\n", 0o644)
	r := repo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\necho\n"})
	if err := os.Symlink(outside, filepath.Join(r.Dir, "link")); err != nil {
		t.Fatal(err)
	}
	calls := recordHooks(t)
	res, err := Annotate(bg, r.Dir, registry.ID{Path: "tests/t.sh"}, []string{"src/a.sh", "src/gone.sh", "link/src.sh"}, Actor{})
	if err != nil || len(res.Stamps) != 0 || len(res.Skips) != 2 || res.Skips[0].Reason != "missing" || res.Skips[1].Reason != "not-a-file" {
		t.Fatalf("%+v %v", res, err)
	}
	if readFile(t, r.Dir, "tests/t.sh") != "#!/bin/sh\necho\n" || len(*calls) != 0 {
		t.Errorf("written or hooked")
	}
}

func TestVerify(t *testing.T) {
	r := repo(t, map[string]string{
		"src/a.sh": "a\n", "src/b.sh": "b\n",
		"tests/t.sh": "#!/bin/sh\n# testmap:covers src/a.sh @2026-01-01/0123456789\n" +
			"# testmap:unit M\n# testmap:covers src/b.sh\n# testmap:covers src/gone.sh @2026-01-01/0123456789\n" +
			"# testmap:unit N\n# testmap:covers src/a.sh\n",
		"tests/t.py": "\"\"\"Doc.\ntestmap:covers src/a.sh @2026-01-01/0123456789\n\"\"\"\n",
	})
	calls := recordHooks(t)
	// One member only.
	res, err := Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.sh", Member: "M"}}, Actor{Kind: Agent, Value: "claudecode/x"})
	if err != nil {
		t.Fatal(err)
	}
	got := readFile(t, r.Dir, "tests/t.sh")
	if !strings.Contains(got, "# testmap:covers src/b.sh @2026-10-12/"+blob10(t, "b\n")) ||
		!strings.Contains(got, "# testmap:covers src/a.sh @2026-01-01/0123456789") || // file-level untouched
		!strings.Contains(got, "# testmap:unit N\n# testmap:covers src/a.sh\n") { // N untouched
		t.Errorf("member scope: %q", got)
	}
	if len(res.Skips) != 1 || res.Skips[0].Reason != "missing" || res.Skips[0].Test != "tests/t.sh#M" || !res.Failed() {
		t.Errorf("skips %+v", res.Skips)
	}
	// The whole file, twice: the second run is byte-identical and all current.
	if _, err := Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.sh"}, {Path: "tests/t.sh", Member: "N"}}, Actor{}); err != nil {
		t.Fatal(err)
	}
	once := readFile(t, r.Dir, "tests/t.sh")
	res, err = Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.sh"}}, Actor{})
	if err != nil || readFile(t, r.Dir, "tests/t.sh") != once || len(res.Wrote) != 0 {
		t.Fatalf("re-run not byte-identical: %v %v", res, err)
	}
	if _, rs, c, _ := res.Counts(); rs != 0 || c != 3 {
		t.Errorf("re-run counts %+v", res.Stamps)
	}
	if len(*calls) != 3 || (*calls)[0].actor.String() != "agent:claudecode/x" || (*calls)[2].edges[0].State != Current {
		t.Errorf("hook calls %+v", *calls)
	}
	// A docstring covers line needing a new stamp is skipped, never written.
	before := readFile(t, r.Dir, "tests/t.py")
	res, err = Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.py"}}, Actor{})
	if err != nil || len(res.Skips) != 1 || res.Skips[0].Reason != "docstring" || readFile(t, r.Dir, "tests/t.py") != before {
		t.Errorf("docstring: %+v %v", res, err)
	}
	// No member block, and a refused target among good ones.
	res, err = Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.sh", Member: "Z"}, {Path: "tests/none.sh"}}, Actor{})
	if err != nil || len(res.Refused) != 2 || res.Refused[0].Reason != "no-member-block" || res.Refused[1].Reason != "missing" {
		t.Errorf("refusals %+v %v", res, err)
	}
}

func TestStampingNeedsRegistryAndHookErrors(t *testing.T) {
	r := fixture.New(t)
	r.Write(t, "tests/t.sh", "#!/bin/sh\n")
	if _, err := Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.sh"}}, Actor{}); !errors.Is(err, registry.ErrAbsent) {
		t.Errorf("no aitestmap/: %v", err)
	}
	r2 := repo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\n"})
	old := restampHooks
	restampHooks = []RestampHook{func(context.Context, string, Actor, []Restamp) ([]string, error) {
		return nil, errors.New("ledger|down")
	}}
	t.Cleanup(func() { restampHooks = old })
	_, err := Annotate(bg, r2.Dir, registry.ID{Path: "tests/t.sh"}, []string{"src/a.sh"}, Actor{})
	var he *HookError
	if !errors.As(err, &he) {
		t.Fatalf("hook error: %v", err)
	}
	if l, _ := he.Line(); l != "RESTAMP_HOOK_ERROR:post-re-stamp hook: ledger/down" && l != "RESTAMP_HOOK_ERROR:ledger/down" {
		t.Errorf("line %q", l)
	}
}

func TestParseActor(t *testing.T) {
	for in, want := range map[string]string{"human:a@b.c": "human:a@b.c", "agent:claudecode/opus5_5": "agent:claudecode/opus5_5", "auto": "auto"} {
		if a, err := ParseActor(in); err != nil || a.String() != want {
			t.Errorf("%s: %v %v", in, a, err)
		}
	}
	for _, bad := range []string{"", "human:", "robot:x", "agent:a|b", "agent:a b", "human"} {
		if _, err := ParseActor(bad); err == nil {
			t.Errorf("%q accepted", bad)
		}
	}
	if (Actor{}).String() != "" {
		t.Error("unspecified renders")
	}
}

// Results come in target order, and a source is read once per invocation.
func TestVerifyTargetOrderAndOneReadPerSource(t *testing.T) {
	r := repo(t, map[string]string{
		"src/a.sh": "a\n",
		"tests/t.sh": "#!/bin/sh\n# testmap:unit A\n# testmap:covers src/a.sh\n" +
			"# testmap:unit B\n# testmap:covers src/a.sh\n# testmap:unit C\n# testmap:covers src/a.sh\n",
	})
	reads := 0
	beforeOpenLeaf = func(name string) {
		if name == "a.sh" {
			reads++
		}
	}
	t.Cleanup(func() { beforeOpenLeaf = func(string) {} })
	res, err := Verify(bg, r.Dir, []registry.ID{{Path: "tests/t.sh", Member: "B"}, {Path: "tests/t.sh", Member: "A"}, {Path: "tests/t.sh"}}, Actor{})
	if err != nil {
		t.Fatal(err)
	}
	var order []string
	for _, st := range res.Stamps {
		order = append(order, st.Test)
	}
	if strings.Join(order, ",") != "tests/t.sh#B,tests/t.sh#A,tests/t.sh#C" || len(res.Wrote) != 1 {
		t.Errorf("order %v wrote %v", order, res.Wrote)
	}
	if reads != 1 {
		t.Errorf("src/a.sh read %d times, want 1", reads)
	}
}

// AnnotateWith records the caller's provenance on every hook edge; Annotate
// records none.
func TestAnnotateWithOrigin(t *testing.T) {
	r := repo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\necho\n"})
	calls := recordHooks(t)
	if _, err := Annotate(bg, r.Dir, registry.ID{Path: "tests/t.sh"}, []string{"src/a.sh"}, Actor{Kind: Auto}); err != nil {
		t.Fatal(err)
	}
	if _, err := AnnotateWith(bg, r.Dir, registry.ID{Path: "tests/t.sh"}, []string{"src/a.sh"}, Actor{Kind: Auto},
		AnnotateOptions{Origin: "scanner:from-body"}); err != nil {
		t.Fatal(err)
	}
	if len(*calls) != 2 || (*calls)[0].edges[0].Origin != "" || (*calls)[1].edges[0].Origin != "scanner:from-body" {
		t.Fatalf("origins: %+v", *calls)
	}
}

// A caller's snapshot guards the whole window from its reading to the
// rename: a file that differs at AnnotateWith's own reload, or that changes
// after the reload and before Apply, is a snapshot conflict and nothing is
// written.
func TestAnnotateWithSnapshotGuardsTheWrite(t *testing.T) {
	const orig = "#!/bin/sh\necho\n"
	r := repo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": orig})
	planned := snapshotOf([]byte(orig))
	id := registry.ID{Path: "tests/t.sh"}
	edited := "#!/bin/sh\necho changed\n"
	path := filepath.Join(r.Dir, "tests", "t.sh")

	// Changed before the reload.
	r.Write(t, "tests/t.sh", edited)
	_, err := AnnotateWith(bg, r.Dir, id, []string{"src/a.sh"}, Actor{}, AnnotateOptions{Snapshot: planned})
	var ce *ConflictError
	if !errors.As(err, &ce) || ce.Reason != "snapshot" {
		t.Fatalf("changed before reload: %v", err)
	}
	if got, _ := os.ReadFile(path); string(got) != edited {
		t.Fatalf("written: %q", got)
	}

	// Changed after the reload, before Apply: the planned snapshot, not the
	// reload's, guards Apply.
	r.Write(t, "tests/t.sh", orig)
	old := beforeApply
	beforeApply = func(string) { r.Write(t, "tests/t.sh", edited) }
	t.Cleanup(func() { beforeApply = old })
	_, err = AnnotateWith(bg, r.Dir, id, []string{"src/a.sh"}, Actor{}, AnnotateOptions{Snapshot: planned})
	if !errors.As(err, &ce) || ce.Reason != "snapshot" {
		t.Fatalf("changed before Apply: %v", err)
	}
	if got, _ := os.ReadFile(path); string(got) != edited {
		t.Fatalf("written: %q", got)
	}
}
