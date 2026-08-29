"""Standalone tests for the reusable tg_calendar module (no clubs/db needed)."""
import calendar
import datetime as dt

import pytest

import tg_calendar

FIGSP = chr(0x2007)  # figure space


def _cal(**kw):
    kw.setdefault("today_fn", lambda: dt.date(2026, 6, 15))
    return tg_calendar.Calendar(**kw)


def test_keyboard_structure():
    kb = _cal().keyboard(2026, 6)["inline_keyboard"]
    assert "June 2026" in kb[0][0]["text"]                       # full-width title
    assert kb[1][0]["callback_data"] == "cal:nav:2026:5"         # < May
    assert kb[1][1]["callback_data"] == "cal:nav:2026:7"         # > July
    assert [b["text"] for b in kb[2]] == list(tg_calendar.LOCALES["en"]["weekdays"])
    assert [b["callback_data"] for b in kb[-2]] == ["cal:yest", "cal:today", "cal:tom"]
    assert kb[-1][0]["callback_data"] == "cal:cancel"


def test_grid_even_columns_no_empty_last_row():
    for m in range(1, 13):
        kb = _cal().keyboard(2026, m)["inline_keyboard"]
        grid = kb[2:-2]                                          # weekday + weeks
        assert all(len(row) == 7 for row in grid)
        assert any(b["callback_data"].startswith("cal:pick") for b in grid[-1])


def test_title_constant_width():
    widths = {len(_cal().keyboard(2026, m)["inline_keyboard"][0][0]["text"])
              for m in range(1, 13)}
    assert widths == {tg_calendar.TITLE_WIDTH}


def test_today_highlight_marker_and_digits():
    kb = _cal().keyboard(2026, 6, marker="\U0001F535", digits="bold")["inline_keyboard"]
    cells = [b for row in kb for b in row]
    today = next(b for b in cells if b["callback_data"] == "cal:pick:2026:6:15")
    assert today["text"] == "\U0001F535" + tg_calendar.style_digits(15, "bold")
    # a non-today, single-digit day is figure-space padded to 2 slots
    d3 = next(b for b in cells if b["callback_data"] == "cal:pick:2026:6:3")
    assert d3["text"] == FIGSP + "3"


def test_no_marker_default():
    kb = _cal().keyboard(2026, 6)["inline_keyboard"]   # marker default 'none'
    today = next(b for row in kb for b in row
                 if b["callback_data"] == "cal:pick:2026:6:15")
    assert today["text"] == tg_calendar.style_digits(15, "bold")


def test_parse():
    c = _cal()
    assert c.parse("cal:nav:2026:7") == ("nav", (2026, 7))
    assert c.parse("cal:pick:2026:6:15") == ("pick", dt.date(2026, 6, 15))
    assert c.parse("cal:today") == ("today", dt.date(2026, 6, 15))
    assert c.parse("cal:yest") == ("yesterday", dt.date(2026, 6, 14))
    assert c.parse("cal:tom") == ("tomorrow", dt.date(2026, 6, 16))
    assert c.parse("cal:cancel") == ("cancel", None)
    assert c.parse("cal:noop") == ("noop", None)
    assert c.parse("other:x") is None
    assert c.parse("") is None


def test_parse_malformed_is_noop_not_crash():
    """A crafted/short callback for OUR prefix must degrade to noop (caller acks
    + does nothing), never raise — else process_update swallows the exception and
    the button's loading spinner hangs forever."""
    c = _cal()
    assert c.parse("cal:pick:2026:6") == ("noop", None)      # missing day
    assert c.parse("cal:pick:x:y:z") == ("noop", None)       # non-numeric
    assert c.parse("cal:pick:0:0:0") == ("noop", None)       # invalid date
    assert c.parse("cal:nav:2026") == ("noop", None)         # missing month
    assert c.parse("cal:nav:x:y") == ("noop", None)          # non-numeric
    assert c.parse("cal:pick") == ("noop", None)             # no args at all
    # M7: numerically valid but out-of-range nav args would pass parse and only
    # blow up later inside keyboard() — hung spinner. Must degrade to noop here.
    assert c.parse("cal:nav:2026:99") == ("noop", None)      # month > 12
    assert c.parse("cal:nav:2026:0") == ("noop", None)       # month 0
    assert c.parse("cal:nav:0:5") == ("noop", None)          # year < 1
    assert c.parse("cal:nav:10000:5") == ("noop", None)      # year > 9999


def test_custom_prefix_isolation():
    c = tg_calendar.Calendar(prefix="bday")
    kb = c.keyboard(2026, 6)["inline_keyboard"]
    assert kb[1][0]["callback_data"].startswith("bday:nav:")
    assert c.parse("bday:pick:2026:6:1")[0] == "pick"
    assert c.parse("cal:pick:2026:6:1") is None      # different prefix ignored


def test_footer_flags():
    kb = tg_calendar.Calendar(footer_today=False, footer_cancel=False,
                              today_fn=lambda: dt.date(2026, 6, 1)
                              ).keyboard(2026, 6)["inline_keyboard"]
    flat = [b["callback_data"] for row in kb for b in row]
    assert not any(x in ("cal:today", "cal:yest", "cal:tom", "cal:cancel") for x in flat)


def test_year_rollover():
    dec = _cal().keyboard(2026, 12)["inline_keyboard"][1]
    assert dec[1]["callback_data"] == "cal:nav:2027:1"
    jan = _cal().keyboard(2026, 1)["inline_keyboard"][1]
    assert jan[0]["callback_data"] == "cal:nav:2025:12"


def test_style_digits():
    assert tg_calendar.style_digits(15, "plain") == "15"
    bold = tg_calendar.style_digits(15, "bold")
    assert bold != "15" and len(bold) == 2
    wide = tg_calendar.style_digits(15, "wide")
    assert all(0xFF10 <= ord(c) <= 0xFF19 for c in wide)        # fullwidth digits
    assert tg_calendar.style_digits(1, "keycap") == "1️⃣"


def test_figure_space_and_blank_codepoints():
    assert tg_calendar._FIGSP == chr(0x2007)
    assert tg_calendar._BLANK == chr(0x2007) * 2


# -------------------- months_keyboard: year-at-a-glance 4×3 grid --------------------

def test_months_keyboard_grid():
    kb = tg_calendar.months_keyboard(lambda m: f"x:{m}")["inline_keyboard"]
    assert len(kb) == 4 and all(len(row) == 3 for row in kb)   # a quarter per row
    labels = [b["text"] for row in kb for b in row]
    assert [t.strip(" ") for t in labels] == [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # cells are figure-space padded to MONTH_CELL — the grid stretches to the
    # full screen width (3×15 ≈ TITLE_WIDTH) and the cells stay even
    assert all(len(t) == tg_calendar.MONTH_CELL for t in labels)
    assert all(" " in t for t in labels)
    assert kb[0][0]["callback_data"] == "x:1"
    assert kb[3][2]["callback_data"] == "x:12"


def test_prefix_validation_is_loud_at_construction():
    """':' inside a prefix makes parse() misread every own callback (a silently
    dead widget); a long prefix only blows the 64-byte callback_data cap at
    send time. Both must fail at construction instead."""
    with pytest.raises(ValueError):
        tg_calendar.Calendar(prefix="a:b")
    with pytest.raises(ValueError):
        tg_calendar.Calendar(prefix="")
    with pytest.raises(ValueError):
        tg_calendar.Calendar(prefix="x" * 49)   # 64 - len(":pick:9999:12:31") = 48 is the cap


def test_grid_is_immune_to_global_setfirstweekday():
    """A host (or any of its libraries) may call calendar.setfirstweekday();
    the grid must stay Monday-first under the fixed Mon..Sun header."""
    calendar.setfirstweekday(6)                       # Sunday-first, globally
    try:
        kb = _cal().keyboard(2026, 6)["inline_keyboard"]
        first_week = [b["text"].strip(FIGSP) for b in kb[3]]
        # June 1, 2026 is a Monday: the first week under Mon..Sun is exactly 1..7
        assert first_week == ["1", "2", "3", "4", "5", "6", "7"]
    finally:
        calendar.setfirstweekday(0)


def test_quick_date_overflow_degrades_to_noop():
    """The never-raise contract covers the quick-date footer too: one day past
    date.min/date.max must parse to noop, not OverflowError."""
    at_min = tg_calendar.Calendar(today_fn=lambda: dt.date.min)
    assert at_min.parse("cal:yest") == ("noop", None)
    at_max = tg_calendar.Calendar(today_fn=lambda: dt.date.max)
    assert at_max.parse("cal:tom") == ("noop", None)


def test_today_not_highlighted_in_another_month_or_year():
    """day+month+year must ALL match: day 15 of a neighbouring month/year
    renders as a plain '15', not as the styled today cell."""
    c = _cal()                                        # today = 2026-06-15
    for y, m in ((2026, 7), (2027, 6)):
        kb = c.keyboard(y, m)["inline_keyboard"]
        cell = next(b for row in kb for b in row
                    if b["callback_data"] == f"cal:pick:{y}:{m}:15")
        assert cell["text"] == "15"


def test_blank_grid_cells_are_figure_spaces():
    """Empty day cells are two U+2007: Telegram trims ASCII spaces, which
    would collapse the columns."""
    kb = _cal().keyboard(2026, 6)["inline_keyboard"]
    blanks = [b for row in kb[3:-2] for b in row if b["callback_data"] == "cal:noop"]
    assert blanks                                     # June 2026 has empty cells
    assert all(b["text"] == FIGSP * 2 for b in blanks)


def test_width_constants_are_pinned_by_value():
    """46/15 are tuned-by-eye screen widths; a drifted value must fail by
    number, not by self-reference."""
    assert tg_calendar.TITLE_WIDTH == 46
    assert tg_calendar.MONTH_CELL == 15
    assert len(tg_calendar.month_title(6, 2026)) == 46


def test_style_digits_two_digit_glyphs_are_exact():
    assert tg_calendar.style_digits(15, "bold") == "\U0001d7ed\U0001d7f1"
    assert tg_calendar.style_digits(15, "wide") == "\uff11\uff15"
    assert tg_calendar.style_digits(15, "keycap") == "1\ufe0f\u20e35\ufe0f\u20e3"


def test_single_digit_padding_boundary():
    """Day 9 is the last padded day, day 10 the first unpadded one."""
    kb = _cal().keyboard(2026, 6)["inline_keyboard"]
    cells = {b["callback_data"]: b["text"] for row in kb for b in row}
    assert cells["cal:pick:2026:6:9"] == FIGSP + "9"
    assert cells["cal:pick:2026:6:10"] == "10"


def test_superstring_prefix_is_foreign():
    """'calx:*' does not belong to prefix 'cal': the boundary is prefix+':'."""
    assert tg_calendar.Calendar(prefix="cal").parse("calx:pick:2026:6:1") is None


def test_custom_title_width_is_honoured():
    kb = _cal(title_width=30).keyboard(2026, 6)["inline_keyboard"]
    assert len(kb[0][0]["text"]) == 30
    assert len(tg_calendar.month_title(6, 2026, width=20)) == 20


def test_pad_center_stretches_with_figure_spaces():
    out = tg_calendar.pad_center("— Вторник —")
    assert len(out) == tg_calendar.TITLE_WIDTH
    assert out.strip(" ") == "— Вторник —"          # padding is figure space only
    left = len(out) - len(out.lstrip(" "))
    right = len(out) - len(out.rstrip(" "))
    assert abs(left - right) <= 1                        # centred
    # a long string is not truncated
    long = "x" * (tg_calendar.TITLE_WIDTH + 5)
    assert tg_calendar.pad_center(long) == long
    # month_title keeps the same padding
    assert tg_calendar.month_title(6, 2026).strip(" ") == "June 2026"
