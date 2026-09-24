package main

import (
	"fmt"
	"strings"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
)

// verb is one row of the verb table. A verb has either Run or Sub.
type verb struct {
	Name  string
	Run   func(e env, args []string) int
	Exits lineproto.ExitContract
	Sub   []verb
}

// notImplemented is the exit contract of a stub.
var notImplemented = lineproto.ExitContract{lineproto.ExitUsage}

// stub registers a verb whose submodule has not landed. Each engine
// submodule replaces its own row(s) with the real Run and exit contract —
// and nothing else in this table.
func stub(name string) verb {
	return verb{Name: name, Run: stubRun(name), Exits: notImplemented}
}

func stubRun(name string) func(env, []string) int {
	return func(e env, _ []string) int {
		fmt.Fprintf(e.stderr, "NOT_IMPLEMENTED:%s\n", name)
		return lineproto.ExitUsage
	}
}

// verbs is the engine's verb table (proposal: Engine binary identity and
// budget). `runner <name>` takes any runner name as its argument.
var verbs = []verb{
	stub("test"),
	stub("select"),
	stub("schedule"),
	stub("run"),
	stub("scan"),
	stub("check"),
	stub("stale"),
	stub("annotate"),
	stub("verify"),
	stub("explain"),
	stub("axes"),
	stub("areas"),
	stub("classify"),
	stub("costs"),
	stub("score"),
	stub("attribute"),
	stub("readiness"),
	stub("brief"),
	{Name: "onboard", Sub: []verb{
		stub("onboard detect"),
		stub("onboard inventory"),
		stub("onboard seed"),
		stub("onboard review"),
		stub("onboard classify"),
		stub("onboard adopt"),
		stub("onboard reject"),
		stub("onboard scaffold"),
		stub("onboard status"),
		stub("onboard finish"),
	}},
	stub("runner"),
	{Name: "version", Run: runVersion, Exits: lineproto.ExitContract{lineproto.ExitOK, lineproto.ExitFramework, lineproto.ExitUsage}},
}

// leaf returns a verb's own word (`onboard seed` → `seed`).
func leaf(name string) string {
	return name[strings.LastIndexByte(name, ' ')+1:]
}

func dispatch(table []verb, parent string, args []string, e env) int {
	usage := strings.Join(strings.Fields("ait-testmap "+parent+" <verb> [args]"), " ")
	if len(args) == 0 {
		return lineproto.Usage(e.stderr, usage)
	}
	for _, v := range table {
		if leaf(v.Name) != args[0] {
			continue
		}
		if v.Sub != nil {
			return dispatch(v.Sub, v.Name, args[1:], e)
		}
		return lineproto.Enforce(v.Name, v.Exits, v.Run(e, args[1:]), e.stderr)
	}
	fmt.Fprintf(e.stderr, "UNKNOWN_VERB:%s\n", strings.TrimSpace(parent+" "+args[0]))
	return lineproto.Usage(e.stderr, usage)
}
