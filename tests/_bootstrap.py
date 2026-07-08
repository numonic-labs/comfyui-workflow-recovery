"""Import the (hyphen-named) node package under a valid alias for testing.

ComfyUI loads a custom-node directory as a package, so the modules use relative
imports (``from . import config``). The staging directory name contains hyphens
and cannot be imported directly, so we register it in ``sys.modules`` under the
alias ``wr`` with the correct submodule search path. After importing this module,
``import wr.config`` (etc.) resolves relative imports correctly.
"""

import importlib.util
import pathlib
import sys

PKG_DIR = pathlib.Path(__file__).resolve().parents[1]
PKG_NAME = "wr"

if PKG_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PKG_NAME,
        str(PKG_DIR / "__init__.py"),
        submodule_search_locations=[str(PKG_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG_NAME] = module
    spec.loader.exec_module(module)
