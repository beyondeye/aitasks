//go:build t1954wasm

package provider

import (
	"context"
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/tetratelabs/wazero"
	"github.com/tetratelabs/wazero/api"
	"github.com/tetratelabs/wazero/imports/wasi_snapshot_preview1"
)

func init() { register("tswasm", func() (Provider, error) { return NewTSWasm(TSWasmPath()) }) }

// TSWasmPath is where tswasm/build.sh writes the module (git-ignored).
func TSWasmPath() string { return filepath.Join(".tswasm", "ts.wasm") }

// tsWasmIDs mirrors the language ids in tswasm/shim.c.
var tsWasmIDs = map[string]uint64{
	"bash": 0, "python": 1, "go": 2, "kotlin": 3, "typescript": 4, "tsx": 5,
	"javascript": 6, "java": 7, "rust": 8, "swift": 9,
}

// TSWasm runs the tree-sitter C runtime and the pinned C grammars compiled
// to one WASI module (tswasm/build.sh) inside wazero — pure Go on the host,
// so CGO_ENABLED=0 builds it for every release target. The tree goes
// through the shared MapTree, exactly as tscgo's does.
type TSWasm struct {
	mu          sync.Mutex
	ctx         context.Context
	rt          wazero.Runtime
	mod         api.Module
	malloc      api.Function
	free        api.Function
	parse       api.Function
	symName     api.Function
	names       map[string]map[uint32]string
	Compile     time.Duration // wazero CompileModule
	Instantiate time.Duration // WASI + module instantiation (+ _initialize)
	WasmBytes   int
}

// NewTSWasm compiles and instantiates the module at path.
func NewTSWasm(path string) (*TSWasm, error) {
	bin, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("tswasm: %w (build it with tswasm/build.sh)", err)
	}
	return NewTSWasmBytes(bin)
}

// NewTSWasmBytes compiles and instantiates a module from memory.
func NewTSWasmBytes(bin []byte) (*TSWasm, error) {
	ctx := context.Background()
	w := &TSWasm{ctx: ctx, names: map[string]map[uint32]string{}, WasmBytes: len(bin)}
	w.rt = wazero.NewRuntime(ctx)
	t0 := time.Now()
	compiled, err := w.rt.CompileModule(ctx, bin)
	if err != nil {
		w.rt.Close(ctx)
		return nil, fmt.Errorf("tswasm: compile: %w", err)
	}
	w.Compile = time.Since(t0)
	t1 := time.Now()
	wasi_snapshot_preview1.MustInstantiate(ctx, w.rt)
	w.mod, err = w.rt.InstantiateModule(ctx, compiled, wazero.NewModuleConfig().WithStartFunctions("_initialize"))
	if err != nil {
		w.rt.Close(ctx)
		return nil, fmt.Errorf("tswasm: instantiate: %w", err)
	}
	w.Instantiate = time.Since(t1)
	for name, f := range map[string]*api.Function{"malloc": &w.malloc, "free": &w.free, "t1954_parse": &w.parse, "t1954_symbol_name": &w.symName} {
		if *f = w.mod.ExportedFunction(name); *f == nil {
			w.rt.Close(ctx)
			return nil, fmt.Errorf("tswasm: module does not export %s", name)
		}
	}
	return w, nil
}

func (*TSWasm) Name() string                  { return "tswasm" }
func (*TSWasm) Langs() []string               { return append([]string(nil), TSLangs...) }
func (*TSWasm) Caps(lang string) Capabilities { return TSCaps(lang) }

// InitStats reports the module's start-up cost (supplementary to the bench).
func (w *TSWasm) InitStats() string {
	return fmt.Sprintf("wasm %d bytes; wazero compile %.1f ms, instantiate %.1f ms", w.WasmBytes,
		float64(w.Compile.Microseconds())/1e3, float64(w.Instantiate.Microseconds())/1e3)
}

// Close releases the runtime.
func (w *TSWasm) Close() error { return w.rt.Close(w.ctx) }

// Analyze parses src in the guest and maps the tree.
func (w *TSWasm) Analyze(lang string, src []byte) (Result, error) {
	nodes, stopped, err := w.Flat(lang, src)
	if err != nil {
		return Result{}, err
	}
	return MapTree(lang, nodes, stopped, src), nil
}

// Flat copies src into guest memory, parses it there, and decodes the flat
// preorder buffer. A trap or a failed parse is a provider failure.
func (w *TSWasm) Flat(lang string, src []byte) ([]TSNode, string, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	id, ok := tsWasmIDs[lang]
	if !ok {
		return nil, "", fmt.Errorf("tswasm: no grammar for %q", lang)
	}
	mem := w.mod.Memory()
	r, err := w.malloc.Call(w.ctx, uint64(len(src)+1))
	if err != nil || r[0] == 0 {
		return nil, "", fmt.Errorf("tswasm: malloc: %v", err)
	}
	p := uint32(r[0])
	defer w.free.Call(w.ctx, uint64(p))
	if !mem.Write(p, src) {
		return nil, "", fmt.Errorf("tswasm: write out of range")
	}
	r, err = w.parse.Call(w.ctx, id, uint64(p), uint64(len(src)))
	if err != nil {
		return nil, "", fmt.Errorf("tswasm: parse trapped: %w", err)
	}
	buf := uint32(r[0])
	count, ok := mem.ReadUint32Le(buf)
	if !ok || buf == 0 || count == 0xFFFFFFFF {
		return nil, "", fmt.Errorf("tswasm: %s: parse returned no tree", lang)
	}
	raw, ok := mem.Read(buf+4, count*5*4)
	if !ok {
		return nil, "", fmt.Errorf("tswasm: node buffer out of range")
	}
	nodes := make([]TSNode, count)
	for i := range nodes {
		rec := raw[i*20:]
		sym := binary.LittleEndian.Uint32(rec)
		flags := binary.LittleEndian.Uint32(rec[16:])
		name, err := w.name(lang, id, sym)
		if err != nil {
			return nil, "", err
		}
		nodes[i] = TSNode{
			Kind: name, Start: int(binary.LittleEndian.Uint32(rec[4:])), End: int(binary.LittleEndian.Uint32(rec[8:])),
			Parent: int(binary.LittleEndian.Uint32(rec[12:])) - 1,
			Named:  flags&1 != 0, Error: flags&2 != 0, Missing: flags&4 != 0, Extra: flags&8 != 0, Leaf: flags&16 != 0,
		}
	}
	return nodes, "", nil
}

func (w *TSWasm) name(lang string, id uint64, sym uint32) (string, error) {
	m := w.names[lang]
	if m == nil {
		m = map[uint32]string{}
		w.names[lang] = m
	}
	if n, ok := m[sym]; ok {
		return n, nil
	}
	r, err := w.symName.Call(w.ctx, id, uint64(sym))
	if err != nil || r[0] == 0 {
		return "", fmt.Errorf("tswasm: symbol %d of %s: %v", sym, lang, err)
	}
	mem := w.mod.Memory()
	var b []byte
	for p := uint32(r[0]); ; p++ {
		c, ok := mem.ReadByte(p)
		if !ok {
			return "", fmt.Errorf("tswasm: symbol name out of range")
		}
		if c == 0 {
			break
		}
		b = append(b, c)
	}
	m[sym] = string(b)
	return m[sym], nil
}
