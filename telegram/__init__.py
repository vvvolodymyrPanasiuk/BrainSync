"""
Extend our local 'telegram' package with python-telegram-bot.

Our local modules (bot, formatter, handlers/) live here.
PTB submodules (ext, constants, error, …) are found via the extended __path__.
PTB top-level names (Update, Bot, …) are imported below so that
  `from telegram import Update`  still works.
"""
from __future__ import annotations

import os
import sys

# ── Locate PTB's installed telegram directory ────────────────────────────────
_this_dir = os.path.dirname(os.path.abspath(__file__))
_ptb_dir: str | None = None

for _entry in sys.path:
    _candidate = os.path.join(os.path.abspath(_entry), "telegram")
    if (
        os.path.isdir(_candidate)
        and _candidate != _this_dir
        and os.path.exists(os.path.join(_candidate, "__init__.py"))
    ):
        _ptb_dir = _candidate
        break

if _ptb_dir and _ptb_dir not in __path__:
    __path__.append(_ptb_dir)  # type: ignore[name-defined]

# ── Re-export PTB top-level names ────────────────────────────────────────────
# We load PTB's __init__ under a private name so we can pull its exports
# without triggering a circular `import telegram`.
if _ptb_dir:
    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location(
        "_ptb_telegram_init",
        os.path.join(_ptb_dir, "__init__.py"),
        submodule_search_locations=[_ptb_dir],
    )
    if _spec and _spec.loader:
        _ptb = _ilu.module_from_spec(_spec)
        _ptb.__package__ = __name__
        sys.modules.setdefault("_ptb_telegram_init", _ptb)
        try:
            _spec.loader.exec_module(_ptb)  # type: ignore[union-attr]
            # Inject public names (Update, Bot, Message, …) into our namespace
            _g = globals()
            for _k, _v in vars(_ptb).items():
                if not _k.startswith("_") and _k not in _g:
                    _g[_k] = _v
        except Exception as _exc:
            import warnings
            warnings.warn(f"BrainSync: could not load PTB telegram exports: {_exc}")
        finally:
            sys.modules.pop("_ptb_telegram_init", None)
