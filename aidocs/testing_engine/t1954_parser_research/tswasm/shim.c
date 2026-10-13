// shim.c — the guest side of the tswasm provider. Compiled into one WASI
// reactor module with the tree-sitter runtime (go-tree-sitter v0.25.0's
// vendored src/lib.c, the same C runtime tscgo uses) and the pinned grammars
// (tsref/LOCK). One host->guest call per file: t1954_parse walks the tree
// inside wasm and returns a flat preorder buffer, so no TSNode struct ever
// crosses the boundary by value.
#include <stdint.h>
#include <stdlib.h>
#include "tree_sitter/api.h"

const TSLanguage *tree_sitter_bash(void);
const TSLanguage *tree_sitter_python(void);
const TSLanguage *tree_sitter_go(void);
const TSLanguage *tree_sitter_kotlin(void);
const TSLanguage *tree_sitter_typescript(void);
const TSLanguage *tree_sitter_tsx(void);
const TSLanguage *tree_sitter_javascript(void);
const TSLanguage *tree_sitter_java(void);
const TSLanguage *tree_sitter_rust(void);
const TSLanguage *tree_sitter_swift(void);

// Language ids, in this order: bash python go kotlin typescript tsx
// javascript java rust swift (tswasm.go mirrors it).
static const TSLanguage *language(int id) {
    switch (id) {
    case 0: return tree_sitter_bash();
    case 1: return tree_sitter_python();
    case 2: return tree_sitter_go();
    case 3: return tree_sitter_kotlin();
    case 4: return tree_sitter_typescript();
    case 5: return tree_sitter_tsx();
    case 6: return tree_sitter_javascript();
    case 7: return tree_sitter_java();
    case 8: return tree_sitter_rust();
    case 9: return tree_sitter_swift();
    }
    return 0;
}

static TSParser *parsers[10];
static uint32_t *buf;
static uint32_t cap;

enum { NAMED = 1, ERROR = 2, MISSING = 4, EXTRA = 8, LEAF = 16 };
#define REC 5 /* symbol, start, end, parent+1, flags */

static int grow(uint32_t need) {
    if (need <= cap) return 1;
    uint32_t n = cap ? cap * 2 : 4096;
    while (n < need) n *= 2;
    uint32_t *b = realloc(buf, n * sizeof(uint32_t));
    if (!b) return 0;
    buf = b;
    cap = n;
    return 1;
}

// t1954_parse returns a buffer: [0] = node count (0xFFFFFFFF on failure),
// then REC words per node in preorder. Valid until the next call.
__attribute__((export_name("t1954_parse")))
uint32_t *t1954_parse(int id, const char *src, uint32_t len) {
    if (!grow(1)) return 0;
    buf[0] = 0xFFFFFFFFu;
    if (id < 0 || id > 9) return buf;
    if (!parsers[id]) {
        parsers[id] = ts_parser_new();
        if (!ts_parser_set_language(parsers[id], language(id))) return buf;
    }
    TSTree *tree = ts_parser_parse_string(parsers[id], 0, src, len);
    if (!tree) return buf;
    TSTreeCursor cur = ts_tree_cursor_new(ts_tree_root_node(tree));
    uint32_t count = 0, depth = 0;
    uint32_t stack[4096];
    stack[0] = 0; /* parent+1 of the root = 0 */
    for (;;) {
        TSNode n = ts_tree_cursor_current_node(&cur);
        if (!grow(1 + (count + 1) * REC)) { count = 0xFFFFFFFFu; break; }
        uint32_t *r = buf + 1 + count * REC;
        uint32_t flags = 0;
        if (ts_node_is_named(n)) flags |= NAMED;
        if (ts_node_is_error(n)) flags |= ERROR;
        if (ts_node_is_missing(n)) flags |= MISSING;
        if (ts_node_is_extra(n)) flags |= EXTRA;
        if (ts_node_child_count(n) == 0) flags |= LEAF;
        r[0] = ts_node_symbol(n);
        r[1] = ts_node_start_byte(n);
        r[2] = ts_node_end_byte(n);
        r[3] = stack[depth];
        r[4] = flags;
        count++;
        if (ts_tree_cursor_goto_first_child(&cur)) {
            if (++depth >= 4096) { count = 0xFFFFFFFFu; break; }
            stack[depth] = count; /* this node's index + 1 */
            continue;
        }
        while (!ts_tree_cursor_goto_next_sibling(&cur)) {
            if (!ts_tree_cursor_goto_parent(&cur)) goto done;
            depth--;
        }
    }
done:
    ts_tree_cursor_delete(&cur);
    ts_tree_delete(tree);
    buf[0] = count;
    return buf;
}

__attribute__((export_name("t1954_symbol_name")))
const char *t1954_symbol_name(int id, uint32_t sym) {
    const TSLanguage *l = language(id);
    return l ? ts_language_symbol_name(l, (TSSymbol)sym) : 0;
}
