module github.com/beyondeye/aitasks/goengines/t1954research

go 1.26.0

toolchain go1.27.1

require github.com/beyondeye/aitasks/goengines v0.0.0

require (
	github.com/bmatcuk/doublestar/v4 v4.10.0 // indirect
	golang.org/x/sync v0.23.0 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
	mvdan.cc/sh/v3 v3.14.1 // indirect
)

replace github.com/beyondeye/aitasks/goengines => ./.baseline-unpatched/goengines
