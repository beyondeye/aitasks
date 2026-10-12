package annot

import (
	"context"
	"fmt"
	"strings"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// ActorKind is who confirmed a stamp.
type ActorKind int

const (
	// Unspecified: no actor was named. It is never a human.
	Unspecified ActorKind = iota
	Human
	Agent
	Auto
)

// Actor is the confirmer the post-re-stamp hook receives. It is recorded
// data, never a gate: no path requires one, and only an explicit `human:`
// actor is a person.
type Actor struct {
	Kind  ActorKind
	Value string // the email (Human) or the agent-string (Agent)
}

// ParseActor parses `human:<email>`, `agent:<agent-string>` or `auto`.
func ParseActor(s string) (Actor, error) {
	kind, val, _ := strings.Cut(s, ":")
	switch {
	case s == "auto":
		return Actor{Kind: Auto}, nil
	case (kind == "human" || kind == "agent") && val != "" && word(val) && !strings.ContainsAny(val, " \t"):
		if kind == "human" {
			return Actor{Kind: Human, Value: val}, nil
		}
		return Actor{Kind: Agent, Value: val}, nil
	}
	return Actor{}, fmt.Errorf("invalid actor %q: want human:<email>, agent:<agent-string> or auto", s)
}

// String is the actor as written in `by:` fields; "" when unspecified.
func (a Actor) String() string {
	switch a.Kind {
	case Human:
		return "human:" + a.Value
	case Agent:
		return "agent:" + a.Value
	case Auto:
		return "auto"
	}
	return ""
}

// EdgeState is what a stamping verb did to one edge.
type EdgeState string

const (
	Added     EdgeState = "added"     // a new covers line was written
	Restamped EdgeState = "restamped" // an existing line got a new stamp
	Current   EdgeState = "current"   // the stamp already named the current blob; the line is untouched
)

// Restamp is one edge a stamping verb confirmed.
type Restamp struct {
	Test   registry.ID `json:"test"`
	Source string      `json:"source"`
	File   string      `json:"file"`
	Line   int         `json:"line"` // in the file as written
	Before Stamp       `json:"before"`
	After  Stamp       `json:"after"`
	State  EdgeState   `json:"state"`
}

// RestampHook runs once after `annotate` or `verify` wrote every file, with
// every edge it confirmed (Current ones included) and the actor. M2.6 fills
// it from an init in its own file in this package: an automated actor
// refreshes the matching adopted.yaml row and keeps its `by:`; only an
// explicit human actor deletes it.
type RestampHook func(ctx context.Context, root string, actor Actor, edges []Restamp) error

var restampHooks []RestampHook

// RegisterRestampHook adds a post-re-stamp hook.
func RegisterRestampHook(h RestampHook) { restampHooks = append(restampHooks, h) }

// HookError is a hook that failed after the files were written:
// RESTAMP_HOOK_ERROR:<detail>, exit 3.
type HookError struct{ Err error }

func (e *HookError) Error() string { return "post-re-stamp hook: " + e.Err.Error() }
func (e *HookError) Unwrap() error { return e.Err }

// Line is RESTAMP_HOOK_ERROR:<detail>.
func (e *HookError) Line() (string, error) {
	return lineproto.Format("RESTAMP_HOOK_ERROR", oneLine(e.Err.Error()))
}

// ExitCode is the framework-error exit.
func (e *HookError) ExitCode() int { return lineproto.ExitFramework }

func runRestampHooks(ctx context.Context, root string, a Actor, edges []Restamp) error {
	if len(edges) == 0 {
		return nil
	}
	for _, h := range restampHooks {
		if err := h(ctx, root, a, edges); err != nil {
			return &HookError{Err: err}
		}
	}
	return nil
}

func oneLine(s string) string {
	return strings.NewReplacer("|", "/", "\n", " ", "\r", " ").Replace(s)
}
