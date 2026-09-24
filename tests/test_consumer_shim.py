"""The consumer shim: a bot folder next to a tg-calendar clone imports the
repository's modules through it; the nearest clone wins, and a clone without
the module fails loudly instead of the shim looking further up."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = ("tg_calendar.py", "tg_timepick.py")


def _layout(tmp_path, with_modules=True):
    bots = tmp_path / "bots"
    bot = bots / "some-bot"
    bot.mkdir(parents=True)
    clone = bots / "tg-calendar"
    clone.mkdir()
    if with_modules:
        for name in MODULES:
            shutil.copyfile(ROOT / name, clone / name)
    for name in MODULES:
        shutil.copyfile(ROOT / "consumer_shim.py", bot / name)
    return bot


def _run(bot, code):
    return subprocess.run([sys.executable, "-c", code], cwd=bot,  # noqa: S603
                          capture_output=True, text=True, timeout=120)


def test_shim_loads_both_modules_from_the_sibling_clone(tmp_path):
    bot = _layout(tmp_path)
    r = _run(bot, "import sys, tg_calendar, tg_timepick\n"
                  "assert sys.modules['tg_calendar'] is tg_calendar\n"
                  "assert sys.modules['tg_timepick'] is tg_timepick\n"
                  "print(tg_calendar.__file__)\n"
                  "print(tg_timepick.__file__)\n"
                  "print(tg_calendar.Calendar(prefix='cal').parse('cal:noop'))\n"
                  "print(type(tg_timepick.TimePick(prefix='tp').keyboard_hours()).__name__)\n")
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    clone = (tmp_path / "bots" / "tg-calendar").resolve()
    assert Path(lines[0]).resolve() == clone / "tg_calendar.py"
    assert Path(lines[1]).resolve() == clone / "tg_timepick.py"
    assert lines[2] == "('noop', None)"
    assert lines[3] == "dict"


def test_nearest_clone_without_the_module_fails_loudly(tmp_path):
    # A real clone may sit further up the tree (it does on the machine the
    # suite runs on); the shim must stop at the nearest tg-calendar folder.
    bot = _layout(tmp_path, with_modules=False)
    r = _run(bot, "import tg_calendar")
    assert r.returncode != 0
    assert "has no tg_calendar.py" in r.stderr
