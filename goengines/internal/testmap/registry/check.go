package registry

import (
	"context"
	"sort"
	"strings"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
)

// Severity says when a finding fails `check`.
type Severity int

const (
	// Always fails: rotted paths, fail-closed member drift, merge-rule
	// violations.
	Always Severity = iota
	// StrictPastBootstrap fails under --strict once `bootstrap_until` has
	// passed: structural drift a bootstrapping repository is allowed.
	StrictPastBootstrap
	// Info never fails.
	Info
)

// Finding is one check line, `<RULE>:<field>|<field>…`.
type Finding struct {
	Rule     string   `json:"rule"`
	Fields   []string `json:"fields"`
	Severity Severity `json:"-"`
	Fail     bool     `json:"fail"` // set by the run that reports it
}

// Line is the protocol line of the finding.
func (f Finding) Line() (string, error) {
	return lineproto.Format(f.Rule, f.Fields...)
}

func sortFindings(fs []Finding) {
	sort.SliceStable(fs, func(i, j int) bool {
		if fs[i].Rule != fs[j].Rule {
			return fs[i].Rule < fs[j].Rule
		}
		return strings.Join(fs[i].Fields, "|") < strings.Join(fs[j].Fields, "|")
	})
}

// CheckRule is one check rule. Patterns names the declared patterns whose
// matching files the rule needs (gathered into one MatchFiles call per run;
// nil when it needs none); Run returns the rule's findings, or an error when
// it could not inspect what it judges — which aborts the run.
type CheckRule struct {
	Name     string
	Patterns func(*CheckContext) []string
	Run      func(*CheckContext) ([]Finding, error)
}

var rules []CheckRule

// RegisterRule adds a check rule. Rules run in registration order; M2.4,
// M2.5 and M2.6 register theirs from init functions in their own files.
func RegisterRule(r CheckRule) { rules = append(rules, r) }

// CheckContext is what a rule reads.
type CheckContext struct {
	Root        string
	Reg         *Registry
	Anns        []FileAnnotations
	Lists       []Listing
	Scanned     ScannedDoc // what scan --apply would write now
	MemberDrift []Finding  // UNANNOTATED_MEMBER / DEAD_MEMBER from BuildScanned
	Strict      bool
	Today       time.Time
	Match       map[string][]string // MatchFiles over every rule's Patterns
}

// CheckOptions are the flags of `check`.
type CheckOptions struct {
	Strict bool
}

// CheckResult is what `check` found.
type CheckResult struct {
	Status   string    `json:"status"` // pass | fail
	Findings []Finding `json:"findings"`
	Failing  int       `json:"failing"`
}

// now is the clock `check` judges dates against; tests replace it.
var now = time.Now

// Check loads the registry under root, reads the two inputs and runs every
// registered rule. Any failure to load, read or inspect is returned as an
// error (*testmap.ContractMismatchError, *InvalidError, *UnavailableError,
// *InputError, *CheckError) and no result is produced — a check that could
// not look never passes.
func Check(ctx context.Context, root string, in Inputs, opts CheckOptions) (*CheckResult, error) {
	reg, err := Load(root)
	if err != nil {
		return nil, err
	}
	anns, lists, err := readInputs(ctx, root, in)
	if err != nil {
		return nil, err
	}
	doc, drift := BuildScanned(reg.Config, anns, lists)
	c := &CheckContext{
		Root: root, Reg: reg, Anns: anns, Lists: lists, Scanned: doc, MemberDrift: drift,
		Strict: opts.Strict, Today: now(),
	}
	var patterns []string
	for _, r := range rules {
		if r.Patterns != nil {
			patterns = append(patterns, r.Patterns(c)...)
		}
	}
	c.Match, err = MatchFiles(root, patterns, reg.Config.Exclude)
	if err != nil {
		return nil, &CheckError{Rule: "enumerate", Err: err}
	}
	res := &CheckResult{Findings: []Finding{}}
	strict := opts.Strict && reg.Config.PastBootstrap(c.Today)
	for _, r := range rules {
		found, err := r.Run(c)
		if err != nil {
			return nil, &CheckError{Rule: r.Name, Err: err}
		}
		sortFindings(found)
		for _, f := range found {
			f.Fail = f.Severity == Always || (f.Severity == StrictPastBootstrap && strict)
			if f.Fail {
				res.Failing++
			}
			res.Findings = append(res.Findings, f)
		}
	}
	res.Status = "pass"
	if res.Failing > 0 {
		res.Status = "fail"
	}
	return res, nil
}
