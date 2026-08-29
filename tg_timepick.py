"""Reusable inline TIME picker for Telegram bots — sibling of tg_calendar.

Self-contained (stdlib only). Drop this file into a bot and wire it:

    import tg_timepick
    TP = tg_timepick.TimePick(prefix="tp")            # unique prefix per use

    # when a wizard needs a time:
    send(chat, "⏰ Pick a time:", reply_markup=TP.keyboard_hours())

    # in your callback handler, before your own routing:
    res = TP.parse(data)
    if res:
        kind, val = res
        if kind == "noop":    answer_cb(cb_id)
        if kind == "hours":   edit(..., reply_markup=TP.keyboard_hours())
        if kind == "minutes": edit(..., reply_markup=TP.keyboard_minutes(val))
        if kind == "pick":    use_the_time(val)        # val = "HH:MM"
        if kind == "cancel":  cancel_wizard()

Flow: hour grid (00–23, four rows of six) → minute grid (step 5, two rows of
six) → "HH:MM". minute_step is an int in 1..60, validated at construction like
the locale and the prefix; a step that does not divide 60 gets its last row
padded with blank cells. Typed input stays the host's parallel path — the
picker only adds taps.

Labels are localised. The default is English; pass locale="ru" for the bundled
Russian set, or pass a dict shaped like a LOCALES entry for a custom language —
it is validated at construction time.

Grid discipline mirrors tg_calendar: every cell in a row is the same 2-digit
width (buttons split row width by text length — uneven labels make columns
jump), and the header is a full-width figure-space-padded row so the keyboard
stretches to the screen edge. Button text can't be styled by Telegram at all —
plain glyphs only.

Callback-data format: "<prefix>:h:<H>", ":m:<H>:<M>", ":hours", ":cancel",
":noop". Pick a prefix that doesn't clash with the host bot's buttons.
"""
from __future__ import annotations

from typing import Optional

_FIGSP = chr(0x2007)   # figure space: survives Telegram's whitespace trimming
TITLE_WIDTH = 46       # same screen-edge width as tg_calendar's month title

# Every label the picker renders, per language. "minutes_title" is a format
# string receiving the chosen hour. A custom locale is any dict with these keys.
LOCALES = {
    "en": {
        "hours_title": "Pick an hour",
        "minutes_title": "{hour:02d}:·· — pick the minutes",
        "back_hours": "« Hours",
        "cancel": "❌ Cancel",
    },
    "ru": {
        "hours_title": "Выбери час",
        "minutes_title": "{hour:02d}:·· — выбери минуты",
        "back_hours": "« Часы",
        "cancel": "❌ Отмена",
    },
}

_LOCALE_KEYS = frozenset(LOCALES["en"])


def _resolve_locale(locale):
    """A locale name from LOCALES, or a full label dict of the same shape.
    A typo, a missing label or a broken minutes_title template fails HERE, at
    construction time — not later, inside a callback handler."""
    if isinstance(locale, str):
        if locale not in LOCALES:
            raise ValueError("unknown locale %r; bundled: %s"
                             % (locale, ", ".join(sorted(LOCALES))))
        return LOCALES[locale]
    missing = _LOCALE_KEYS - set(locale)
    if missing:
        raise ValueError("locale dict is missing keys: %s" % ", ".join(sorted(missing)))
    for key in ("hours_title", "minutes_title", "back_hours", "cancel"):
        if not isinstance(locale[key], str):
            raise ValueError("locale[%r] must be a string" % key)
    try:
        locale["minutes_title"].format(hour=0)
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError("minutes_title must be a format string taking {hour}: %s" % e) from None
    return locale


def _pad_center(s: str, width: int = TITLE_WIDTH) -> str:
    pad = width - len(s)
    if pad <= 0:
        return s
    left = pad // 2
    return _FIGSP * left + s + _FIGSP * (pad - left)


# Telegram caps callback_data at 64 bytes. The longest suffix this module ever
# appends is ":m:23:59" (8 bytes), so a prefix may spend the rest.
_PREFIX_BUDGET = 64 - len(":m:23:59")


class TimePick:
    """Builds hour/minute keyboards and parses their callbacks. Stateless —
    one instance can serve any number of chats."""

    def __init__(self, prefix: str = "tp", *, minute_step: int = 5,
                 title_width: int = TITLE_WIDTH, locale="en"):
        if not prefix or ":" in prefix:
            raise ValueError("prefix must be non-empty and contain no ':', got %r" % (prefix,))
        if len(prefix.encode("utf-8")) > _PREFIX_BUDGET:
            raise ValueError("prefix must fit %d UTF-8 bytes (Telegram caps callback_data "
                             "at 64), got %d" % (_PREFIX_BUDGET, len(prefix.encode("utf-8"))))
        if isinstance(minute_step, bool) or not isinstance(minute_step, int) \
                or not 1 <= minute_step <= 60:
            raise ValueError("minute_step must be an int in 1..60, got %r" % (minute_step,))
        self.p = prefix
        self.step = minute_step
        self.title_width = title_width
        self.labels = _resolve_locale(locale)

    # -------------------- build --------------------

    def keyboard_hours(self, title: Optional[str] = None) -> dict:
        p = self.p
        rows = [[{"text": _pad_center(title or self.labels["hours_title"],
                                      self.title_width),
                  "callback_data": f"{p}:noop"}]]
        # 00–23: calendar-style 4×6 grid
        rows.extend([{"text": f"{h:02d}", "callback_data": f"{p}:h:{h}"}
                     for h in range(r * 6, r * 6 + 6)]
                    for r in range(4))
        rows.append([{"text": self.labels["cancel"], "callback_data": f"{p}:cancel"}])
        return {"inline_keyboard": rows}

    def keyboard_minutes(self, hour: int) -> dict:
        p = self.p
        rows = [[{"text": _pad_center(self.labels["minutes_title"].format(hour=hour),
                                      self.title_width),
                  "callback_data": f"{p}:noop"}]]
        mins = list(range(0, 60, self.step))
        for i in range(0, len(mins), 6):
            row = [{"text": f"{m:02d}", "callback_data": f"{p}:m:{hour}:{m}"}
                   for m in mins[i:i + 6]]
            # A step that does not divide 60 leaves the last row short: pad it
            # with blank noop cells so every row keeps the 6-column geometry.
            row.extend({"text": _FIGSP * 2, "callback_data": f"{p}:noop"}
                       for _ in range(6 - len(row)))
            rows.append(row)
        rows.append([{"text": self.labels["back_hours"], "callback_data": f"{p}:hours"},
                     {"text": self.labels["cancel"], "callback_data": f"{p}:cancel"}])
        return {"inline_keyboard": rows}

    # -------------------- parse --------------------

    def parse(self, data: str) -> Optional[tuple]:
        """(kind, value) for one of OUR callbacks, else None.
        kinds: 'minutes'->hour · 'pick'->"HH:MM" · 'hours'/'cancel'/'noop'->None.
        Malformed numeric payloads degrade to noop (never raise — a swallowed
        exception would leave the button spinner hung)."""
        if not data or not data.startswith(self.p + ":"):
            return None
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        try:
            if action == "h":
                h = int(parts[2])
                return ("minutes", h) if 0 <= h <= 23 else ("noop", None)
            if action == "m":
                h, m = int(parts[2]), int(parts[3])
                if 0 <= h <= 23 and 0 <= m <= 59:
                    return ("pick", f"{h:02d}:{m:02d}")
                return ("noop", None)
        except (IndexError, ValueError):
            return ("noop", None)
        if action == "hours":
            return ("hours", None)
        if action == "cancel":
            return ("cancel", None)
        return ("noop", None)
