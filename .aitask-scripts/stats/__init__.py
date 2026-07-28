"""TUI package for ait stats.

The data-extraction layer moved to `lib/stats_data.py` in t1235; this package
holds the TUI (app, panes, modals, config) only.
"""

import os
import sys

# Downward dependency: every module in this package reads the base layer.
# Bootstrapping here rather than relying on stats_app.py's import order means
# `import stats.panes` works standalone — the panes' bare
# `from stats_data import …` must not depend on which line of another file ran
# first.
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
