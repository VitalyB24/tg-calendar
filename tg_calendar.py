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

Styling (optional) is passed per call so a bot can keep user prefs in its own DB:
    CAL.keyboard(y, m, marker="🔹", digits="bold")
  marker: one of tg_calendar.MARKERS values ('none' = no marker)
  digits: one of 'plain' | 'bold' | 'wide' | 'keycap'

Callback-data format: "<prefix>:nav:Y:M", ":pick:Y:M:D", ":yest", ":today",
":tom", ":cancel", ":noop". Pick a prefix that doesn't clash with other buttons.

Also here: months_keyboard(cb_for_month) — a year-at-a-glance month picker
(4×3 quarters grid, MONTHS_SHORT labels); the host routes its own callbacks.
"""
from __future__ import annotations

import calendar as _cal
import datetime as _dt
from typing import Callable

MONTHS_RU = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTHS_SHORT = ("", "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек")
WD_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

# Telegram button text can't be styled (no colour/size/bold/background), so the
# "today" cell is faked inside the glyph: an optional colour marker + a digit
# style. Cells are kept to a constant 2-slot width so columns never "jump".
_BOLD_DIGITS = {str(i): ch for i, ch in enumerate("𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")}
_WIDE_DIGITS = {str(i): ch for i, ch in enumerate("０１２３４５６７８９")}
_FIGSP = chr(0x2007)  # figure space U+2007 (non-breaking, digit width)
_BLANK = _FIGSP * 2    # empty cell, same width as a 2-digit cell

# Pickers a host bot can render to let the user choose look (value, label).
MARKERS = [
    ("none", "без метки"), ("🔹", "ромб синий мал."), ("🔷", "ромб синий бол."),
    ("🔸", "ромб оранж. мал."), ("🔶", "ромб оранж. бол."), ("🔵", "круг синий"),
    ("🟢", "круг зелёный"), ("🟡", "круг жёлтый"), ("🔴", "круг красный"),
    ("🟦", "квадрат синий"), ("🟩", "квадрат зелёный"), ("🟥", "квадрат красный"),
    ("◽", "квадрат серый мал."), ("▪️", "квадрат чёрный мал."),
]
DIGIT_STYLES = [("plain", "обычный"), ("bold", "жирный"),
                ("wide", "крупнее"), ("keycap", "максимум 1️⃣5️⃣")]

# Pad the full-width title row with figure spaces so it reaches the screen edge
# and is the SAME width for every month. Tuned by eye on a phone.
TITLE_WIDTH = 46


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


def month_title(month: int, year: int, width: int = TITLE_WIDTH) -> str:
    return pad_center(f"{MONTHS_RU[month]} {year}", width)


MONTH_CELL = 15  # month-cell width in figure-space slots; 3 cells ≈ TITLE_WIDTH


def months_keyboard(cb_for_month: Callable[[int], str]) -> dict:
    """Year-at-a-glance month picker styled like the calendar grid: 4 rows ×
    3 months (a quarter per row, as on a paper calendar), MONTHS_SHORT labels.
    Every cell is centre-padded with figure spaces to MONTH_CELL slots, so the
    3-wide row totals ≈ TITLE_WIDTH and the grid stretches to the screen edge
    exactly like the day calendar (without the padding the keyboard shrinks to
    fit its content — caught on a real phone). cb_for_month(m) returns the
    callback_data for month m (1..12); the host bot appends its own extra rows
    (cancel/back) if it needs them."""
    return {"inline_keyboard": [
        [{"text": pad_center(MONTHS_SHORT[m], MONTH_CELL),
          "callback_data": cb_for_month(m)}
         for m in range(q * 3 + 1, q * 3 + 4)]
        for q in range(4)]}


class Calendar:
    """Builds month-calendar keyboards and parses their callbacks. Stateless —
    one instance can serve any number of chats."""

    def __init__(self, prefix: str = "cal", *, title_width: int = TITLE_WIDTH,
                 footer_today: bool = True, footer_cancel: bool = True,
                 today_fn: Callable[[], _dt.date] = _dt.date.today):
        self.p = prefix
        self.title_width = title_width
        self.footer_today = footer_today
        self.footer_cancel = footer_cancel
        self._today_fn = today_fn

    # -------------------- build --------------------

    def keyboard(self, year: int, month: int, *,
                 marker: str = "none", digits: str = "bold") -> dict:
        p = self.p
        prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
        next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
        rows = [
            [{"text": month_title(month, year, self.title_width),
              "callback_data": f"{p}:noop"}],
            [{"text": f"‹ {MONTHS_RU[prev_m]}",
              "callback_data": f"{p}:nav:{prev_y}:{prev_m}"},
             {"text": f"{MONTHS_RU[next_m]} ›",
              "callback_data": f"{p}:nav:{next_y}:{next_m}"}],
            [{"text": w, "callback_data": f"{p}:noop"} for w in WD_SHORT],
        ]
        today = self._today_fn()
        for week in _cal.monthcalendar(year, month):   # weeks start Monday
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
            rows.append([{"text": "Вчера", "callback_data": f"{p}:yest"},
                         {"text": "📅 Сегодня", "callback_data": f"{p}:today"},
                         {"text": "Завтра", "callback_data": f"{p}:tom"}])
        if self.footer_cancel:
            rows.append([{"text": "❌ Отмена", "callback_data": f"{p}:cancel"}])
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
        except (IndexError, ValueError):
            return ("noop", None)
        if action == "today":
            return ("today", self._today_fn())
        if action == "yest":
            return ("yesterday", self._today_fn() - _dt.timedelta(days=1))
        if action == "tom":
            return ("tomorrow", self._today_fn() + _dt.timedelta(days=1))
        if action == "cancel":
            return ("cancel", None)
        return ("noop", None)
