//go:build linux

package builtin

// bash-file is registered for production only where its real-tool tests run
// (G10): GNU bash on linux. Elsewhere `builtin: bash-file` stays unresolved.
func init() { Register(bashFileAdapter()) }
