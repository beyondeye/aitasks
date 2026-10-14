package runner

import (
	"fmt"
	"slices"
	"strings"
	"unicode"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// ListRow is one `list` row with its line number.
type ListRow struct {
	Unit registry.ListedUnit
	Line int
}

// ParseList parses a runner's `list` output: one
// `<id>\t<kind>\t<lowering>[\t<artifact>]` row per line, each line ending in
// a newline. A malformed row is an error naming the line — never skipped: a
// list that silently drops a row would make a unit invisible to `check` and
// to `run --all`.
func ParseList(data []byte) ([]ListRow, error) {
	if len(data) == 0 {
		return nil, nil
	}
	text := string(data)
	if !strings.HasSuffix(text, "\n") {
		return nil, fmt.Errorf("list: the last line has no trailing newline")
	}
	var rows []ListRow
	seen := map[registry.ID]int{}
	for i, line := range strings.Split(strings.TrimSuffix(text, "\n"), "\n") {
		no := i + 1
		u, err := parseListRow(line)
		if err != nil {
			return nil, fmt.Errorf("list line %d: %v", no, err)
		}
		if prev, dup := seen[u.ID]; dup {
			return nil, fmt.Errorf("list line %d: id %s already listed on line %d", no, u.ID, prev)
		}
		seen[u.ID] = no
		rows = append(rows, ListRow{Unit: u, Line: no})
	}
	return rows, nil
}

func parseListRow(line string) (registry.ListedUnit, error) {
	f := strings.Split(line, "\t")
	if len(f) != 3 && len(f) != 4 {
		return registry.ListedUnit{}, fmt.Errorf("%d fields, want 3 or 4 (<id> <kind> <lowering> [<artifact>])", len(f))
	}
	for i, v := range f {
		if v == "" {
			return registry.ListedUnit{}, fmt.Errorf("field %d is empty", i+1)
		}
		if strings.ContainsFunc(v, unicode.IsControl) {
			return registry.ListedUnit{}, fmt.Errorf("field %d contains a control character", i+1)
		}
	}
	id, err := registry.ParseID(f[0])
	if err != nil {
		return registry.ListedUnit{}, err
	}
	if !slices.Contains(unitKinds, f[1]) {
		return registry.ListedUnit{}, fmt.Errorf("kind %q is not one of %s", f[1], strings.Join(unitKinds, "|"))
	}
	if f[1] == "variant" && id.Variant == "" {
		return registry.ListedUnit{}, fmt.Errorf("variant row %s has no @<variant>", id)
	}
	u := registry.ListedUnit{ID: id, Kind: f[1], Lowering: f[2]}
	if len(f) == 4 {
		if err := registry.CheckPath(f[3]); err != nil {
			return registry.ListedUnit{}, fmt.Errorf("artifact %q: %v", f[3], err)
		}
		u.Artifact = f[3]
	}
	return u, nil
}
