package annot

// The test-only reader of the t1954 research corpus format (.expect / .edits,
// the t1954 shared design, "Oracle files"), trimmed from the research
// harness's internal/corpus. It stays as strict as the original: an unknown
// key, a duplicate key or a malformed record is an error, so a format drift
// fails the gate instead of silently dropping an expectation.

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
)

// confRecord is one annotation as ParseFile returns it, flattened.
type confRecord struct {
	Line   int
	Member string
	Key    string
	Value  string
	Stamp  string
	Origin string // comment | docstring
}

// String is the canonical one-line form of .expect / .edits files.
func (r confRecord) String() string {
	return fmt.Sprintf("line=%d member=%s key=%s value=%s stamp=%s origin=%s",
		r.Line, r.Member, r.Key, confFmtValue(r.Value), r.Stamp, r.Origin)
}

func confFmtValue(v string) string {
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

func parseConfRecord(s string) (confRecord, error) {
	var r confRecord
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

// confExpect is a fixture's .expect oracle.
type confExpect struct {
	Lang       string
	Uncertain  bool
	Read       []confRecord
	Writable   []int
	Readonly   []int
	Lookalikes []int
	Comments   []int          // lines that are lexically comments (annotation or not)
	Refuse     string         // "" = none; syntax[@N] | uncertain[@N] | no-leader
	Placement  map[string]int // "" = the file-level block, else member -> after-line
	Extra      map[string]string
}

// confOp is one .edits operation.
type confOp struct {
	Kind    string // annotate | stale | raw
	Args    map[string]string
	Outcome string // applied | unchanged | refused:<reason>
	After   []confRecord
	Text    string // the op line, for findings
}

// confCase is one fixture.
type confCase struct {
	Lang  string // corpus directory
	Name  string // <case>.<ext>
	Data  []byte
	Mode  os.FileMode
	Exp   confExpect
	Edits []confOp
}

// ID is the case's name in findings and in confKnown: <lang>/<case>.<ext>.
func (c confCase) ID() string { return c.Lang + "/" + c.Name }

// loadConfCases reads every case under dir/<lang>/, sorted.
func loadConfCases(dir string) ([]confCase, error) {
	ins, err := filepath.Glob(filepath.Join(dir, "*", "*.in"))
	if err != nil {
		return nil, err
	}
	sort.Strings(ins)
	var out []confCase
	for _, in := range ins {
		c, err := loadConfCase(in)
		if err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, nil
}

func loadConfCase(in string) (confCase, error) {
	st, err := os.Stat(in)
	if err != nil {
		return confCase{}, err
	}
	data, err := os.ReadFile(in)
	if err != nil {
		return confCase{}, err
	}
	c := confCase{
		Lang: filepath.Base(filepath.Dir(in)),
		Name: strings.TrimSuffix(filepath.Base(in), ".in"),
		Data: data,
		Mode: st.Mode().Perm(),
	}
	base := strings.TrimSuffix(in, ".in")
	exp, err := os.ReadFile(base + ".expect")
	if err != nil {
		return c, fmt.Errorf("%s: missing .expect: %w", in, err)
	}
	if c.Exp, err = parseConfExpect(exp); err != nil {
		return c, fmt.Errorf("%s.expect: %w", base, err)
	}
	if ed, err := os.ReadFile(base + ".edits"); err == nil {
		if c.Edits, err = parseConfEdits(ed); err != nil {
			return c, fmt.Errorf("%s.edits: %w", base, err)
		}
	} else if !os.IsNotExist(err) {
		return c, err
	}
	return c, nil
}

// parseConfLines parses "3,7,12", "20-25,31", "" or "-".
func parseConfLines(s string) ([]int, error) {
	s = strings.TrimSpace(s)
	if s == "" || s == "-" {
		return nil, nil
	}
	var out []int
	for _, part := range strings.Split(s, ",") {
		a, b, isRange := strings.Cut(strings.TrimSpace(part), "-")
		lo, err := strconv.Atoi(a)
		if err != nil {
			return nil, fmt.Errorf("line list %q: %w", s, err)
		}
		hi := lo
		if isRange {
			if hi, err = strconv.Atoi(b); err != nil {
				return nil, fmt.Errorf("line list %q: %w", s, err)
			}
			if hi < lo {
				return nil, fmt.Errorf("line list %q: reversed range %s", s, part)
			}
		}
		for i := lo; i <= hi; i++ {
			out = append(out, i)
		}
	}
	return out, nil
}

func confTextLines(data []byte) []string {
	sc := bufio.NewScanner(bytes.NewReader(data))
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	var out []string
	for sc.Scan() {
		out = append(out, sc.Text())
	}
	return out
}

func parseConfExpect(data []byte) (confExpect, error) {
	e := confExpect{Placement: map[string]int{}, Extra: map[string]string{}}
	ls := confTextLines(data)
	seen := map[string]bool{}
	for i := 0; i < len(ls); i++ {
		l := ls[i]
		if t := strings.TrimSpace(l); t == "" || strings.HasPrefix(t, "#") {
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
			e.Read, i, err = confRecordList(ls, i)
		case k == "writable":
			e.Writable, err = parseConfLines(v)
		case k == "readonly":
			e.Readonly, err = parseConfLines(v)
		case k == "lookalikes":
			e.Lookalikes, err = parseConfLines(v)
		case k == "comments":
			e.Comments, err = parseConfLines(v)
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
		case k == "native", k == "exec", k == "note":
			// Research-only: native oracles and controlled execution stay in
			// the research harness; the gate launches no subprocess.
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

// confRecordList reads "  - <record>" lines after line i and returns the
// index of the last line it consumed.
func confRecordList(ls []string, i int) ([]confRecord, int, error) {
	var out []confRecord
	for i+1 < len(ls) {
		t := strings.TrimSpace(ls[i+1])
		if !strings.HasPrefix(t, "- ") {
			break
		}
		r, err := parseConfRecord(strings.TrimPrefix(t, "- "))
		if err != nil {
			return nil, i, err
		}
		out = append(out, r)
		i++
	}
	return out, i, nil
}

func parseConfEdits(data []byte) ([]confOp, error) {
	var ops []confOp
	hasAfter := map[int]bool{}
	// Each op takes one outcome: and one after: — a second one would
	// silently replace the first expectation.
	once := func(i int, key string, set bool) error {
		if len(ops) == 0 {
			return fmt.Errorf("line %d: %s before op", i+1, key)
		}
		if set {
			return fmt.Errorf("line %d: op %d (%s): duplicate %s:", i+1, len(ops), ops[len(ops)-1].Text, key)
		}
		return nil
	}
	ls := confTextLines(data)
	for i := 0; i < len(ls); i++ {
		l := strings.TrimSpace(ls[i])
		if l == "" || strings.HasPrefix(l, "#") {
			continue
		}
		k, v, _ := strings.Cut(l, ":")
		k, v = strings.TrimSpace(k), strings.TrimSpace(v)
		switch k {
		case "op":
			op := confOp{Args: map[string]string{}, Text: v}
			kind, rest, _ := strings.Cut(v, " ")
			op.Kind = kind
			switch kind {
			case "annotate", "stale", "raw":
			default:
				return nil, fmt.Errorf("line %d: unknown op %q", i+1, kind)
			}
			// new= and mutate= take the rest of the line (they may hold spaces).
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
			if err := once(i, "outcome", len(ops) > 0 && ops[len(ops)-1].Outcome != ""); err != nil {
				return nil, err
			}
			if v == "" {
				return nil, fmt.Errorf("line %d: empty outcome:", i+1)
			}
			ops[len(ops)-1].Outcome = v
		case "after":
			if err := once(i, "after", hasAfter[len(ops)-1]); err != nil {
				return nil, err
			}
			recs, ni, err := confRecordList(ls, i)
			if err != nil {
				return nil, fmt.Errorf("line %d: %w", i+1, err)
			}
			ops[len(ops)-1].After, i = recs, ni
			hasAfter[len(ops)-1] = true
		case "note":
		default:
			return nil, fmt.Errorf("line %d: unknown key %q", i+1, k)
		}
	}
	for n, op := range ops {
		if op.Outcome == "" || !hasAfter[n] {
			return nil, fmt.Errorf("op %d (%s): needs outcome: and after:", n+1, op.Text)
		}
	}
	return ops, nil
}

// TestConformanceReaderRejectsMalformed: a malformed or merged oracle is an
// error, never a silently dropped or replaced expectation.
func TestConformanceReaderRejectsMalformed(t *testing.T) {
	const op = "op: annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb\n"
	const rec = "  - line=2 member= key=covers value=src/a.sh stamp= origin=comment\n"
	for _, tc := range []struct{ name, edits, want string }{
		{"duplicate outcome", op + "outcome: applied\noutcome: refused:not-comment\nafter:\n" + rec, "duplicate outcome:"},
		{"duplicate after", op + "outcome: applied\nafter:\n" + rec + "after:\n", "duplicate after:"},
		{"empty outcome", op + "outcome:\nafter:\n", "empty outcome:"},
		{"outcome before op", "outcome: applied\n", "outcome before op"},
		{"after before op", "after:\n" + rec, "after before op"},
		{"missing after", op + "outcome: applied\n", "needs outcome: and after:"},
		{"unknown op", "op: delete line=3\noutcome: applied\nafter:\n", `unknown op "delete"`},
		{"unknown key", op + "outcome: applied\nafter:\nresult: x\n", `unknown key "result"`},
		{"malformed record", op + "outcome: applied\nafter:\n  - line=x member= key=covers value=a stamp= origin=comment\n", "line:"},
	} {
		if _, err := parseConfEdits([]byte(tc.edits)); err == nil || !strings.Contains(err.Error(), tc.want) {
			t.Errorf("edits %s: error %v, want one containing %q", tc.name, err, tc.want)
		}
	}
	two := op + "outcome: applied\nafter:\n" + rec + op + "outcome: refused:conflict\nafter:\n"
	if ops, err := parseConfEdits([]byte(two)); err != nil || len(ops) != 2 || ops[0].Outcome != "applied" ||
		len(ops[0].After) != 1 || ops[1].Outcome != "refused:conflict" || len(ops[1].After) != 0 {
		t.Errorf("two well-formed ops: %+v, %v", ops, err)
	}

	for _, s := range []string{"4-1", "3,7-5"} {
		if _, err := parseConfLines(s); err == nil || !strings.Contains(err.Error(), "reversed range") {
			t.Errorf("parseConfLines(%q): error %v, want a reversed range", s, err)
		}
	}
	if got, err := parseConfLines("3,5-5,7-8"); err != nil || fmt.Sprint(got) != "[3 5 7 8]" {
		t.Errorf("parseConfLines(3,5-5,7-8) = %v, %v", got, err)
	}

	const expect = "lang: bash\nexpect: certain\nread:\n"
	for _, tc := range []struct{ name, expect, want string }{
		{"reversed range", expect + "lookalikes: 4-1\n", "reversed range"},
		{"duplicate key", expect + "writable: 2\nwritable: 3\n", `duplicate key "writable"`},
		{"unknown key", expect + "lookalike: 2\n", `unknown key "lookalike"`},
		{"missing read", "lang: bash\nexpect: certain\n", "missing read:"},
		{"bad expect", "lang: bash\nexpect: maybe\nread:\n", "expect: certain|uncertain"},
	} {
		if _, err := parseConfExpect([]byte(tc.expect)); err == nil || !strings.Contains(err.Error(), tc.want) {
			t.Errorf("expect %s: error %v, want one containing %q", tc.name, err, tc.want)
		}
	}
}
