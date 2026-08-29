"""Reusable inline-keyboard month calendar for Telegram bots.

Self-contained (stdlib only). Drop this file into a bot and wire it:

    import tg_calendar
    CAL = tg_calendar.Calendar(prefix="cal")          # unique prefix per use

    # show a date picker (e.g. when a wizard needs a date):
    send(chat, "Pick a date:", reply_markup=CAL.keyboard(2026, 6))

    # in your callback handler, before your own routing:
    res = CAL.parse(data)
    if res:
        kind, value = res
        if kind == "noop":
            answer_cb(cb_id); return
        if kind == "nav":                              # value = (year, month)
            answer_cb(cb_id)
            edit(chat, msg_id, "Pick a date:", reply_markup=CAL.keyboard(*value))
            return
        if kind in ("pick", "today", "yesterday", "tomorrow"):  # value = datetime.date
            answer_cb(cb_id)
            use_the_date(value)                         # <- your code
            return
        if kind == "cancel":
            answer_cb(cb_id, "Cancelled"); cancel_wizard(); return

Labels are localised. The default is English; pass locale="ru" for the bundled
Russian set, or pass a dict shaped like a LOCALES entry for a custom language —
it is validated at construction time:

    CAL = tg_calendar.Calendar(prefix="cal", locale="ru")

Styling (optional) is passed per call so a bot can keep user prefs in its own DB:
    CAL.keyboard(y, m, marker="🔹", digits="bold")
  marker: one of the locale's "markers" values ('none' = no marker)
  digits: one of 'plain' | 'bold' | 'wide' | 'keycap'

Callback-data format: "<prefix>:nav:Y:M", ":pick:Y:M:D", ":yest", ":today",
":tom", ":cancel", ":noop". Pick a prefix that doesn't clash with other buttons.

Also here: months_keyboard(cb_for_month) — a year-at-a-glance month picker
(4×3 quarters grid, "months_short" labels); the host routes its own callbacks.
"""
from __future__ import annotations

import calendar as _cal
import datetime as _dt
from typing import Callable

# Every label a keyboard renders, per language. "markers" and "digit_styles" are
# (value, label) catalogues a host bot can show as user settings; the VALUES are
# identical across locales — only the labels translate — so a stored preference
# survives a locale switch. A custom locale is any dict with these exact keys.
LOCALES = {
    "en": {
        "months": ["", "January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"],
        "months_short": ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        "weekdays": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "yesterday": "Yesterday", "today": "📅 Today", "tomorrow": "Tomorrow",
        "cancel": "❌ Cancel",
        "markers": [
            ("none", "no marker"), ("🔹", "blue diamond, small"), ("🔷", "blue diamond, large"),
            ("🔸", "orange diamond, small"), ("🔶", "orange diamond, large"), ("🔵", "blue circle"),
            ("🟢", "green circle"), ("🟡", "yellow circle"), ("🔴", "red circle"),
            ("🟦", "blue square"), ("🟩", "green square"), ("🟥", "red square"),
            ("◽", "grey square, small"), ("▪️", "black square, small"),
        ],
        "digit_styles": [("plain", "plain"), ("bold", "bold"),
                         ("wide", "wider"), ("keycap", "keycap 1️⃣5️⃣")],
    },
    "ru": {
        "months": ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
        "months_short": ("", "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                         "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"),
        "weekdays": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
        "yesterday": "Вчера", "today": "📅 Сегодня", "tomorrow": "Завтра",
        "cancel": "❌ Отмена",
        "markers": [
            ("none", "без метки"), ("🔹", "ромб синий мал."), ("🔷", "ромб синий бол."),
            ("🔸", "ромб оранж. мал."), ("🔶", "ромб оранж. бол."), ("🔵", "круг синий"),
            ("🟢", "круг зелёный"), ("🟡", "круг жёлтый"), ("🔴", "круг красный"),
            ("🟦", "квадрат синий"), ("🟩", "квадрат зелёный"), ("🟥", "квадрат красный"),
            ("◽", "квадрат серый мал."), ("▪️", "квадрат чёрный мал."),
        ],
        "digit_styles": [("plain", "обычный"), ("bold", "жирный"),
                         ("wide", "крупнее"), ("keycap", "максимум 1️⃣5️⃣")],
    },
}

_LOCALE_KEYS = frozenset(LOCALES["en"])


def _resolve_locale(locale):
    """A locale name from LOCALES, or a full label dict of the same shape.
    A typo, a missing label or a mis-shaped value fails HERE, at construction
    time — not later, somewhere inside a callback handler."""
    if isinstance(locale, str):
        if locale not in LOCALES:
            raise ValueError("unknown locale %r; bundled: %s"
                             % (locale, ", ".join(sorted(LOCALES))))
        return LOCALES[locale]
    missing = _LOCALE_KEYS - set(locale)
    if missing:
        raise ValueError("locale dict is missing keys: %s" % ", ".join(sorted(missing)))
    for key in ("months", "months_short"):
        seq = locale[key]
        if isinstance(seq, str) or len(seq) != 13 or seq[0] != "" \
                or not all(isinstance(x, str) for x in seq):
            raise ValueError("locale[%r] must be 13 strings with a '' sentinel at index 0" % key)
    wd = locale["weekdays"]
    if isinstance(wd, str) or len(wd) != 7 or not all(isinstance(x, str) for x in wd):
        raise ValueError("locale['weekdays'] must be 7 strings, Mon..Sun")
    for key in ("yesterday", "today", "tomorrow", "cancel"):
        if not isinstance(locale[key], str):
            raise ValueError("locale[%r] must be a string" % key)
    return locale


# Telegram button text can't be styled (no colour/size/bold/background), so the
# "today" cell is faked inside the glyph: an optional colour marker + a digit
# style. Cells are kept to a constant 2-slot width so columns never "jump".
_BOLD_DIGITS = {str(i): ch for i, ch in enumerate("𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")}
_WIDE_DIGITS = {str(i): ch for i, ch in enumerate("０１２３４５６７８９")}
_FIGSP = chr(0x2007)  # figure space U+2007 (non-breaking, digit width)
_BLANK = _FIGSP * 2    # empty cell, same width as a 2-digit cell

# Pad the full-width title row with figure spaces so it reaches the screen edge
# and is the SAME width for every month. Tuned by eye on a phone.
TITLE_WIDTH = 46

# The grid comes from a private Calendar instance pinned to Monday: a host (or
# any of its libraries) calling the global calendar.setfirstweekday() must not
# shift our dates under the fixed Mon..Sun header.
_GRID = _cal.Calendar(firstweekday=0)

# Telegram caps callback_data at 64 bytes. The longest suffix this module ever
# appends is ":pick:9999:12:31" (16 bytes), so a prefix may spend the rest.
_PREFIX_BUDGET = 64 - len(":pick:9999:12:31")


def style_digits(day: int, style: str) -> str:
    s = str(day)
    if style == "bold":
        return "".join(_BOLD_DIGITS[c] for c in s)
    if style == "wide":
        return "".join(_WIDE_DIGITS[c] for c in s)
    if style == "keycap":
        return "".join(f"{c}️⃣" for c in s)   # digit + VS16 + keycap
    return s


def today_label(day: int, marker: str, digits: str) -> str:
    prefix = "" if marker in ("", "none") else marker
    return prefix + style_digits(day, digits)


def _cell(text: str, day: int) -> str:
    return _FIGSP + text if day < 10 else text


def pad_center(s: str, width: int = TITLE_WIDTH) -> str:
    """Center `s` in a row of figure spaces so the button stretches to the
    screen edge (and thus dictates the whole keyboard's width). Figure space
    U+2007 survives Telegram's whitespace trimming; regular spaces don't."""
    pad = width - len(s)
    if pad <= 0:
        return s
    left = pad // 2
    return _FIGSP * left + s + _FIGSP * (pad - left)


def month_title(month: int, year: int, width: int = TITLE_WIDTH, locale="en") -> str:
    return pad_center(f"{_resolve_locale(locale)['months'][month]} {year}", width)


MONTH_CELL = 15  # month-cell width in figure-space slots; 3 cells ≈ TITLE_WIDTH


def months_keyboard(cb_for_month: Callable[[int], str], locale="en") -> dict:
    """Year-at-a-glance month picker styled like the calendar grid: 4 rows ×
    3 months (a quarter per row, as on a paper calendar), "months_short" labels.
    Every cell is centre-padded with figure spaces to MONTH_CELL slots, so the
    3-wide row totals ≈ TITLE_WIDTH and the grid stretches to the screen edge
    exactly like the day calendar (without the padding the keyboard shrinks to
    fit its content — caught on a real phone). cb_for_month(m) returns the
    callback_data for month m (1..12); the host bot appends its own extra rows
    (cancel/back) if it needs them."""
    short = _resolve_locale(locale)["months_short"]
    return {"inline_keyboard": [
        [{"text": pad_center(short[m], MONTH_CELL),
          "callback_data": cb_for_month(m)}
         for m in range(q * 3 + 1, q * 3 + 4)]
        for q in range(4)]}


class Calendar:
    """Builds month-calendar keyboards and parses their callbacks. Stateless —
    one instance can serve any number of chats."""

    def __init__(self, prefix: str = "cal", *, title_width: int = TITLE_WIDTH,
                 footer_today: bool = True, footer_cancel: bool = True,
                 today_fn: Callable[[], _dt.date] = _dt.date.today,
                 locale="en"):
        if not prefix or ":" in prefix:
            raise ValueError("prefix must be non-empty and contain no ':', got %r" % (prefix,))
        if len(prefix.encode("utf-8")) > _PREFIX_BUDGET:
            raise ValueError("prefix must fit %d UTF-8 bytes (Telegram caps callback_data "
                             "at 64), got %d" % (_PREFIX_BUDGET, len(prefix.encode("utf-8"))))
        self.p = prefix
        self.title_width = title_width
        self.footer_today = footer_today
        self.footer_cancel = footer_cancel
        self._today_fn = today_fn
        self.labels = _resolve_locale(locale)

    # -------------------- build --------------------

    def keyboard(self, year: int, month: int, *,
                 marker: str = "none", digits: str = "bold") -> dict:
        p, lab = self.p, self.labels
        months = lab["months"]
        prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
        next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
        rows = [
            [{"text": pad_center(f"{months[month]} {year}", self.title_width),
              "callback_data": f"{p}:noop"}],
            [{"text": f"‹ {months[prev_m]}",
              "callback_data": f"{p}:nav:{prev_y}:{prev_m}"},
             {"text": f"{months[next_m]} ›",
              "callback_data": f"{p}:nav:{next_y}:{next_m}"}],
            [{"text": w, "callback_data": f"{p}:noop"} for w in lab["weekdays"]],
        ]
        today = self._today_fn()
        for week in _GRID.monthdayscalendar(year, month):   # weeks start Monday
            row = []
            for d in week:
                if d == 0:
                    row.append({"text": _BLANK, "callback_data": f"{p}:noop"})
                else:
                    is_today = (year == today.year and month == today.month
                                and d == today.day)
                    core = today_label(d, marker, digits) if is_today else str(d)
                    row.append({"text": _cell(core, d),
                                "callback_data": f"{p}:pick:{year}:{month}:{d}"})
            rows.append(row)
        if self.footer_today:
            rows.append([{"text": lab["yesterday"], "callback_data": f"{p}:yest"},
                         {"text": lab["today"], "callback_data": f"{p}:today"},
                         {"text": lab["tomorrow"], "callback_data": f"{p}:tom"}])
        if self.footer_cancel:
            rows.append([{"text": lab["cancel"], "callback_data": f"{p}:cancel"}])
        return {"inline_keyboard": rows}

    # -------------------- parse --------------------

    def parse(self, data: str):
        """Return (kind, value) for one of OUR callbacks, else None.
        kinds: 'nav'->(y,m) · 'pick'/'today'/'yesterday'/'tomorrow'->date · 'cancel'/'noop'->None."""
        if not data or not data.startswith(self.p + ":"):
            return None
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        # nav/pick carry numeric args from an untrusted callback — a crafted or
        # truncated payload must degrade to noop (caller acks, does nothing),
        # never raise (a swallowed exception leaves the button spinner hung).
        # yest/tom sit under the same net: one day past date.min/max overflows.
        try:
            if action == "nav":
                y, m = int(parts[2]), int(parts[3])
                # Range-check here, not in keyboard(): a crafted in-range-typed
                # payload like nav:2026:99 parses fine but keyboard() would
                # raise later (hung spinner). Same contract as pick → noop.
                if not (1 <= y <= 9999 and 1 <= m <= 12):
                    return ("noop", None)
                return ("nav", (y, m))
            if action == "pick":
                return ("pick", _dt.date(int(parts[2]), int(parts[3]), int(parts[4])))
            if action == "today":
                return ("today", self._today_fn())
            if action == "yest":
                return ("yesterday", self._today_fn() - _dt.timedelta(days=1))
            if action == "tom":
                return ("tomorrow", self._today_fn() + _dt.timedelta(days=1))
        except (IndexError, ValueError, OverflowError):
            return ("noop", None)
        if action == "cancel":
            return ("cancel", None)
        return ("noop", None)
