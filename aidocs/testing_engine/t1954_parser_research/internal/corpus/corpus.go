// Package corpus reads the research corpus: <lang>/<case>.<ext>.in fixtures,
// their hand-written .expect oracles and optional .edits operation lists
// (formats: the t1954 shared design, "Oracle files"), and flattens a parsed
// annot.File into the record list both oracles compare against.
package corpus

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// Record is one annotation as ParseFile returns it.
type Record struct {
	Line   int
	Member string
	Key    string
	Value  string
	Stamp  string
	Origin string // comment | docstring
}

// String is the canonical one-line form used in .expect / .edits files.
func (r Record) String() string {
	return fmt.Sprintf("line=%d member=%s key=%s value=%s stamp=%s origin=%s",
		r.Line, r.Member, r.Key, fmtValue(r.Value), r.Stamp, r.Origin)
}

func fmtValue(v string) string {
	plain := v == strings.TrimSpace(v) && !strings.Contains(v, " stamp=") && !strings.HasPrefix(v, `"`)
	for _, c := range v {
		if c < 0x20 || c > 0x7e {
			plain = false
		}
	}
	if plain {
		return v
	}
	return strconv.Quote(v)
}

// ParseRecord parses the canonical form.
func ParseRecord(s string) (Record, error) {
	var r Record
	rest := strings.TrimSpace(s)
	take := func(key string) (string, error) {
		if !strings.HasPrefix(rest, key+"=") {
			return "", fmt.Errorf("record %q: want %s=", s, key)
		}
		rest = rest[len(key)+1:]
		v, after, _ := strings.Cut(rest, " ")
		rest = after
		return v, nil
	}
	ln, err := take("line")
	if err != nil {
		return r, err
	}
	if r.Line, err = strconv.Atoi(ln); err != nil {
		return r, fmt.Errorf("record %q: line: %w", s, err)
	}
	if r.Member, err = take("member"); err != nil {
		return r, err
	}
	if r.Key, err = take("key"); err != nil {
		return r, err
	}
	if !strings.HasPrefix(rest, "value=") {
		return r, fmt.Errorf("record %q: want value=", s)
	}
	rest = rest[len("value="):]
	if strings.HasPrefix(rest, `"`) {
		q, err := strconv.QuotedPrefix(rest)
		if err != nil {
			return r, fmt.Errorf("record %q: value: %w", s, err)
		}
		r.Value, _ = strconv.Unquote(q)
		rest = strings.TrimPrefix(rest[len(q):], " ")
	} else {
		i := strings.LastIndex(rest, " stamp=")
		if i < 0 {
			return r, fmt.Errorf("record %q: want stamp=", s)
		}
		r.Value, rest = rest[:i], rest[i+1:]
	}
	if r.Stamp, err = take("stamp"); err != nil {
		return r, err
	}
	if !strings.HasPrefix(rest, "origin=") {
		return r, fmt.Errorf("record %q: want origin=", s)
	}
	r.Origin = strings.TrimSpace(rest[len("origin="):])
	return r, nil
}

// Records flattens a parsed file, in line order.
func Records(f *annot.File) []Record {
	var out []Record
	origin := func(l annot.Line) string {
		if l.Docstring {
			return "docstring"
		}
		return "comment"
	}
	for _, u := range f.Units {
		if u.Member != "" {
			out = append(out, Record{Line: u.Opener.No, Member: u.Member, Key: "unit", Value: u.Member, Origin: origin(u.Opener)})
		}
		kv := func(k *annot.KeyVal) {
			if k != nil {
				out = append(out, Record{Line: k.Line.No, Member: u.Member, Key: k.Key, Value: strings.Join(k.Args, " "), Origin: origin(k.Line)})
			}
		}
		kv(u.Kind)
		kv(u.Runner)
		kv(u.Batch)
		kv(u.Reviewed)
		for _, list := range [][]annot.KeyVal{u.Areas, u.Scopes, u.Triggers, u.Reads, u.Needs, u.Axes} {
			for i := range list {
				kv(&list[i])
			}
		}
		for _, c := range u.Covers {
			st := ""
			if !c.Stamp.IsZero() {
				st = c.Stamp.String()
			}
			out = append(out, Record{Line: c.Line.No, Member: u.Member, Key: "covers", Value: c.Source, Stamp: st, Origin: origin(c.Line)})
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Line != out[j].Line {
			return out[i].Line < out[j].Line
		}
		return out[i].Key < out[j].Key
	})
	return out
}

// Expect is a fixture's .expect oracle.
type Expect struct {
	Lang       string
	Uncertain  bool
	Read       []Record
	Writable   []int
	Readonly   []int
	Lookalikes []int
	Comments   []int          // lines that are lexically comments (annotation or not)
	Refuse     string         // "" = none; syntax@N | uncertain@N | no-leader
	Placement  map[string]int // "" = file-level block, else member name -> after-line
	Native     []string
	Exec       string
	Notes      []string
	Extra      map[string]string // provider-specific keys (x-<name>: …), kept verbatim
}

// Op is one .edits operation.
type Op struct {
	Kind    string // annotate | stale | raw
	Args    map[string]string
	Outcome string // applied | refused:<reason> | unchanged
	After   []Record
	Text    string // the op line, for reports
}

// Case is one fixture.
type Case struct {
	Lang  string // corpus directory
	Name  string // <case>.<ext>
	Path  string // the .in file
	Data  []byte
	Mode  os.FileMode
	Exp   Expect
	Edits []Op
}

// Ext is the fixture's language extension (".sh", ".py", …).
func (c Case) Ext() string { return filepath.Ext(c.Name) }

// Load reads every case under dir/<lang>/, sorted.
func Load(dir string) ([]Case, error) {
	ins, err := filepath.Glob(filepath.Join(dir, "*", "*.in"))
	if err != nil {
		return nil, err
	}
	sort.Strings(ins)
	var out []Case
	for _, in := range ins {
		c, err := LoadCase(in)
		if err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, nil
}

// LoadCase reads one fixture and its oracle files.
func LoadCase(in string) (Case, error) {
	st, err := os.Stat(in)
	if err != nil {
		return Case{}, err
	}
	data, err := os.ReadFile(in)
	if err != nil {
		return Case{}, err
	}
	name := strings.TrimSuffix(filepath.Base(in), ".in")
	c := Case{Lang: filepath.Base(filepath.Dir(in)), Name: name, Path: in, Data: data, Mode: st.Mode().Perm()}
	base := strings.TrimSuffix(in, ".in")
	exp, err := os.ReadFile(base + ".expect")
	if err != nil {
		return c, fmt.Errorf("%s: missing .expect: %w", in, err)
	}
	if c.Exp, err = parseExpect(exp); err != nil {
		return c, fmt.Errorf("%s.expect: %w", base, err)
	}
	if ed, err := os.ReadFile(base + ".edits"); err == nil {
		if c.Edits, err = parseEdits(ed); err != nil {
			return c, fmt.Errorf("%s.edits: %w", base, err)
		}
	} else if !os.IsNotExist(err) {
		return c, err
	}
	if !utf8.Valid([]byte(c.Name)) {
		return c, fmt.Errorf("%s: non-UTF-8 name", in)
	}
	return c, nil
}

// ParseLines parses "3,7,12", "20-25,31", "" or "-".
func ParseLines(s string) ([]int, error) {
	s = strings.TrimSpace(s)
	if s == "" || s == "-" {
		return nil, nil
	}
	var out []int
	for _, part := range strings.Split(s, ",") {
		part = strings.TrimSpace(part)
		a, b, isRange := strings.Cut(part, "-")
		lo, err := strconv.Atoi(a)
		if err != nil {
			return nil, fmt.Errorf("line list %q: %w", s, err)
		}
		hi := lo
		if isRange {
			if hi, err = strconv.Atoi(b); err != nil {
				return nil, fmt.Errorf("line list %q: %w", s, err)
			}
		}
		for i := lo; i <= hi; i++ {
			out = append(out, i)
		}
	}
	return out, nil
}

func lines(data []byte) []string {
	sc := bufio.NewScanner(bytes.NewReader(data))
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	var out []string
	for sc.Scan() {
		out = append(out, sc.Text())
	}
	return out
}

func parseExpect(data []byte) (Expect, error) {
	e := Expect{Placement: map[string]int{}, Extra: map[string]string{}}
	ls := lines(data)
	seen := map[string]bool{}
	for i := 0; i < len(ls); i++ {
		l := ls[i]
		if strings.TrimSpace(l) == "" || strings.HasPrefix(strings.TrimSpace(l), "#") {
			continue
		}
		k, v, ok := strings.Cut(l, ":")
		if !ok {
			return e, fmt.Errorf("line %d: want key: value, got %q", i+1, l)
		}
		k, v = strings.TrimSpace(k), strings.TrimSpace(v)
		if seen[k] && k != "note" {
			return e, fmt.Errorf("line %d: duplicate key %q", i+1, k)
		}
		seen[k] = true
		var err error
		switch {
		case k == "lang":
			e.Lang = v
		case k == "expect":
			switch v {
			case "certain":
			case "uncertain":
				e.Uncertain = true
			default:
				return e, fmt.Errorf("line %d: expect: certain|uncertain, got %q", i+1, v)
			}
		case k == "read":
			if v != "" {
				return e, fmt.Errorf("line %d: read: takes an indented list", i+1)
			}
			e.Read, i, err = recordList(ls, i)
		case k == "writable":
			e.Writable, err = ParseLines(v)
		case k == "readonly":
			e.Readonly, err = ParseLines(v)
		case k == "lookalikes":
			e.Lookalikes, err = ParseLines(v)
		case k == "comments":
			e.Comments, err = ParseLines(v)
		case k == "refuse":
			if v != "none" {
				e.Refuse = v
			}
		case k == "placement":
			for _, tok := range strings.Fields(v) {
				blk, n, ok := strings.Cut(tok, "=")
				if !ok {
					return e, fmt.Errorf("line %d: placement token %q", i+1, tok)
				}
				at, perr := strconv.Atoi(n)
				if perr != nil {
					return e, fmt.Errorf("line %d: placement %q: %w", i+1, tok, perr)
				}
				switch {
				case blk == "file":
					e.Placement[""] = at
				case strings.HasPrefix(blk, "member:"):
					e.Placement[strings.TrimPrefix(blk, "member:")] = at
				default:
					return e, fmt.Errorf("line %d: placement block %q", i+1, blk)
				}
			}
		case k == "native":
			for _, n := range strings.Split(v, "+") {
				if n = strings.TrimSpace(n); n != "" {
					e.Native = append(e.Native, n)
				}
			}
		case k == "exec":
			e.Exec = v
		case k == "note":
			e.Notes = append(e.Notes, v)
		case strings.HasPrefix(k, "x-"):
			e.Extra[k] = v
		default:
			return e, fmt.Errorf("line %d: unknown key %q", i+1, k)
		}
		if err != nil {
			return e, fmt.Errorf("line %d: %w", i+1, err)
		}
	}
	if e.Lang == "" {
		return e, fmt.Errorf("missing lang:")
	}
	if !seen["read"] {
		return e, fmt.Errorf("missing read: (write `read:` with no items for none)")
	}
	return e, nil
}

// recordList reads "  - <record>" lines after line i; returns the index of
// the last consumed line.
func recordList(ls []string, i int) ([]Record, int, error) {
	var out []Record
	for i+1 < len(ls) {
		t := strings.TrimSpace(ls[i+1])
		if !strings.HasPrefix(t, "- ") {
			break
		}
		r, err := ParseRecord(strings.TrimPrefix(t, "- "))
		if err != nil {
			return nil, i, err
		}
		out = append(out, r)
		i++
	}
	return out, i, nil
}

func parseEdits(data []byte) ([]Op, error) {
	var ops []Op
	ls := lines(data)
	for i := 0; i < len(ls); i++ {
		l := strings.TrimSpace(ls[i])
		if l == "" || strings.HasPrefix(l, "#") {
			continue
		}
		k, v, _ := strings.Cut(l, ":")
		k, v = strings.TrimSpace(k), strings.TrimSpace(v)
		switch k {
		case "op":
			op := Op{Args: map[string]string{}, Text: v}
			kind, rest, _ := strings.Cut(v, " ")
			op.Kind = kind
			switch kind {
			case "annotate", "stale", "raw":
			default:
				return nil, fmt.Errorf("line %d: unknown op %q", i+1, kind)
			}
			// new= takes the rest of the line (it may contain spaces).
			if j := strings.Index(rest, "new="); j >= 0 {
				op.Args["new"] = rest[j+len("new="):]
				rest = rest[:j]
			}
			if j := strings.Index(rest, "mutate="); j >= 0 {
				op.Args["mutate"] = rest[j+len("mutate="):]
				rest = rest[:j]
			}
			for _, tok := range strings.Fields(rest) {
				a, b, ok := strings.Cut(tok, "=")
				if !ok {
					return nil, fmt.Errorf("line %d: op argument %q", i+1, tok)
				}
				op.Args[a] = b
			}
			ops = append(ops, op)
		case "outcome":
			if len(ops) == 0 {
				return nil, fmt.Errorf("line %d: outcome before op", i+1)
			}
			ops[len(ops)-1].Outcome = v
		case "after":
			if len(ops) == 0 {
				return nil, fmt.Errorf("line %d: after before op", i+1)
			}
			recs, ni, err := recordList(ls, i)
			if err != nil {
				return nil, fmt.Errorf("line %d: %w", i+1, err)
			}
			ops[len(ops)-1].After, i = recs, ni
			ops[len(ops)-1].Args["_after"] = "set"
		case "note":
		default:
			return nil, fmt.Errorf("line %d: unknown key %q", i+1, k)
		}
	}
	for n, op := range ops {
		if op.Outcome == "" || op.Args["_after"] != "set" {
			return nil, fmt.Errorf("op %d (%s): needs outcome: and after:", n+1, op.Text)
		}
		delete(op.Args, "_after")
	}
	return ops, nil
}
