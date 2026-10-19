package annot

import (
	"errors"
	"reflect"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// (b) The intent phase wrote the provenance row and then Apply failed (a
// concurrent edit): the row names a stamp that never landed, so it is an
// orphan; the retry re-plans the same first stamp, the stamp lands and the
// row names it. Both first-stamp shapes: an inserted line and an existing
// unstamped one.
func TestApplyFailureAfterIntentLeavesOrphanUntilRetry(t *testing.T) {
	for name, orig := range map[string]string{
		"insert":         "#!/bin/sh\necho\n",
		"unstamped-line": "#!/bin/sh\n# testmap:covers src/a.sh\necho\n",
	} {
		t.Run(name, func(t *testing.T) {
			r := repo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": orig})
			agent := Actor{Kind: Agent, Value: "claudecode/opus5_5"}
			id := registry.ID{Path: "tests/t.sh"}
			old := beforeApply
			beforeApply = func(string) { r.Write(t, "tests/t.sh", orig+"# edited meanwhile\n") }
			res, err := Annotate(bg, r.Dir, id, []string{"src/a.sh"}, agent)
			beforeApply = old
			var ce *ConflictError
			if !errors.As(err, &ce) {
				t.Fatalf("err %v", err)
			}
			if res == nil || !res.Incomplete || !reflect.DeepEqual(res.Wrote, []string{registry.AdoptedPath}) || len(res.Stamps) != 0 {
				t.Fatalf("incomplete result: %+v", res)
			}
			reg, err := registry.Load(r.Dir)
			if err != nil {
				t.Fatal(err)
			}
			a := registry.AdoptionOf(reg)
			if len(a.Orphans) != 1 || len(a.Adopted) != 0 {
				t.Fatalf("after the failed write: %+v", a)
			}

			res, err = Annotate(bg, r.Dir, id, []string{"src/a.sh"}, agent)
			if err != nil || len(res.Stamps) != 1 {
				t.Fatalf("retry: %+v %v", res, err)
			}
			// The orphan row already names the stamp the retry lands (same
			// day, same source bytes): only the test file is written.
			if !reflect.DeepEqual(res.Wrote, []string{"tests/t.sh"}) {
				t.Errorf("wrote %v", res.Wrote)
			}
			landed := res.Stamps[0].Stamp
			reg, err = registry.Load(r.Dir)
			if err != nil {
				t.Fatal(err)
			}
			rows := registry.AdoptionOf(reg).RawAdopted
			if len(rows) != 1 || rows[0].Stamp != landed || rows[0].By != "agent:claudecode/opus5_5" {
				t.Fatalf("rows %+v (landed %s)", rows, landed)
			}
			live := registry.AdoptionOf(reg).Classified(registry.StampedSet{{"tests/t.sh", "src/a.sh"}: true})
			if len(live.Orphans) != 0 || len(live.Adopted) != 1 {
				t.Fatalf("still an orphan once the stamp landed: %+v", live)
			}
		})
	}
}
