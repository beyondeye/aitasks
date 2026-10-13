module github.com/beyondeye/aitasks/goengines/t1954research

go 1.26.0

toolchain go1.27.1

require (
	github.com/alecthomas/chroma/v2 v2.27.0
	github.com/antlr4-go/antlr/v4 v4.13.1
	github.com/beyondeye/aitasks/goengines v0.0.0
	github.com/odvcencio/gotreesitter v0.55.1
	github.com/tetratelabs/wazero v1.12.0
	github.com/tree-sitter/go-tree-sitter v0.25.0
	mvdan.cc/sh/v3 v3.14.1
)

require (
	github.com/bmatcuk/doublestar/v4 v4.10.0 // indirect
	github.com/dlclark/regexp2/v2 v2.2.1 // indirect
	github.com/mattn/go-pointer v0.0.1 // indirect
	golang.org/x/exp v0.0.0-20240506185415-9bf2ced13842 // indirect
	golang.org/x/sync v0.23.0 // indirect
	golang.org/x/sys v0.47.0 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)

replace github.com/beyondeye/aitasks/goengines => ./.baseline-unpatched/goengines
