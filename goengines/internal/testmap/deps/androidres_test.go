package deps

import (
	"slices"
	"testing"
)

func TestResKeysAndChangedKeys(t *testing.T) {
	before := []byte(`<resources>
  <string name="title">Title</string>
  <string name="kept">Same</string>
  <string name="gone">Bye</string>
  <string name="fmt" formatted="true">%1$s</string>
  <plurals name="items"><item quantity="one">1</item></plurals>
</resources>`)
	after := []byte(`<resources>
  <string name="title">Title 2</string>
  <string name="kept">Same</string>
  <string name="fmt" formatted="false">%1$s</string>
  <string name="added">New</string>
  <plurals name="items"><item quantity="one">1</item></plurals>
</resources>`)
	keys, err := ResKeys(before)
	if err != nil || len(keys) != 5 {
		t.Fatalf("ResKeys: %v %v", keys, err)
	}
	got, err := ChangedKeys(before, after)
	if err != nil {
		t.Fatal(err)
	}
	if want := []string{"added", "fmt", "gone", "title"}; !slices.Equal(got, want) {
		t.Fatalf("changed %v, want %v (an attribute-only change counts)", got, want)
	}
	all, _ := ChangedKeys(nil, after)
	if want := []string{"added", "fmt", "items", "kept", "title"}; !slices.Equal(all, want) {
		t.Fatalf("no before blob: %v", all)
	}
	gone, _ := ChangedKeys(before, nil)
	if len(gone) != 5 {
		t.Fatalf("no after: %v", gone)
	}
	// A <string> and a <plurals> sharing a name: a change to either one is a
	// change to the key, whichever element comes last.
	shared := func(s, p string) []byte {
		return []byte(`<resources><string name="count">` + s + `</string>` +
			`<plurals name="count"><item quantity="one">` + p + `</item></plurals></resources>`)
	}
	for _, c := range []struct{ name, before, after string }{
		{"string", "one", "uno"},
		{"plurals", "1", "un"},
	} {
		b, a := shared("one", "1"), shared("one", "1")
		if c.name == "string" {
			a = shared(c.after, "1")
		} else {
			a = shared("one", c.after)
		}
		if got, _ := ChangedKeys(b, a); !slices.Equal(got, []string{"count"}) {
			t.Errorf("a %s-only change under a shared name: %v", c.name, got)
		}
	}
	if got, _ := ChangedKeys(shared("one", "1"), shared("one", "1")); len(got) != 0 {
		t.Errorf("unchanged shared name: %v", got)
	}
	if !ResValuesRe.MatchString("app/src/main/res/values-ru/strings.xml") || ResValuesRe.MatchString("app/src/main/res/layout/a.xml") {
		t.Fatal("ResValuesRe")
	}
}
