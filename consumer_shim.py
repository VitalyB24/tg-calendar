"""Consumer shim: import the module from the sibling clone of this repository.

Copy this file into a bot folder under the name of the module it should
provide - `tg_calendar.py` or `tg_timepick.py` - next to the bot's code. On
import it walks up from the bot folder to the nearest directory that holds a
`tg-calendar/` folder (the clone), loads the module of the same name from
there and aliases itself to it through sys.modules, so `import tg_calendar`
in the bot and any attribute patching in its tests target the repository's
file. Nothing is copied and nothing drifts: edit the module here, run the
gates, restart the consumers. The nearest clone wins; a clone folder that
lacks the module is an error, not a reason to keep looking further up.

Layout the walk-up expects (any parent folder, any depth):

    bots/
    |-- tg-calendar/        <- clone of this repository (folder name unchanged)
    |-- some-bot/
    |   |-- tg_calendar.py  <- this file, renamed
    |   `-- tg_timepick.py  <- this file, renamed
    `-- another-bot/
"""
import importlib.util
import os
import sys

_NAME = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
_HERE = os.path.dirname(os.path.abspath(__file__))
_dir = _HERE
_clone = None
while True:
    _candidate = os.path.join(_dir, "tg-calendar")
    if os.path.isdir(_candidate):
        _clone = _candidate
        break
    _parent = os.path.dirname(_dir)
    if _parent == _dir:
        break
    _dir = _parent
if _clone is None:
    raise ImportError(f"{_NAME}: no tg-calendar/ clone found above {_HERE}")
_src = os.path.join(_clone, _NAME + ".py")
if not os.path.isfile(_src):
    raise ImportError(f"{_NAME}: the clone at {_clone} has no {_NAME}.py")

_spec = importlib.util.spec_from_file_location(__name__, _src)
_module = importlib.util.module_from_spec(_spec)
sys.modules[__name__] = _module
_spec.loader.exec_module(_module)
