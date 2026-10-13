#!/usr/bin/env python3
"""gen_corpus.py - (re)generate the t1954 research corpus.

    python3 corpus/gen/gen_corpus.py          # from the research dir

Writes corpus/<lang>/<case>.<ext>.{in,expect,edits}. Generated files are
committed; this script is how they are reviewed and reproduced. The M2.2
fixtures come from the pinned commit (m22.py); the rest are hand oracles
(hand_*.py). Every existing .in/.expect/.edits under corpus/<lang>/ is
removed first so a deleted fixture cannot linger.
"""

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import core  # noqa: E402
import m22  # noqa: E402

CORPUS = os.path.dirname(HERE)
RESEARCH = os.path.dirname(CORPUS)
LANG_DIRS = ["bash", "python", "go", "kotlin", "typescript", "java", "rust", "swift"]


def hand_modules():
    mods = []
    for d in LANG_DIRS:
        p = os.path.join(HERE, "hand_%s.py" % d)
        if os.path.exists(p):
            mods.append((d, __import__("hand_%s" % d)))
    return mods


def main():
    by_lang = {d: [] for d in LANG_DIRS}
    for d, fx in m22.all_fixtures(RESEARCH):
        by_lang[d].append(fx)
    for d, mod in hand_modules():
        by_lang[d].extend(mod.FIXTURES)
    for d in LANG_DIRS:
        for f in glob.glob(os.path.join(CORPUS, d, "*")):
            if f.endswith((".in", ".expect", ".edits")):
                os.remove(f)
    n = core.write_all(CORPUS, {d: v for d, v in by_lang.items() if v})
    for d in LANG_DIRS:
        print("%-10s %d" % (d, len(by_lang[d])))
    print("total      %d" % n)


if __name__ == "__main__":
    main()
