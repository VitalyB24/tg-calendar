"""Standalone tests for the reusable tg_timepick module (hour/minute grids, parse)."""
import pytest

import tg_timepick

FIGSP = chr(0x2007)  # figure space


def test_hours_keyboard_grid():
    tp = tg_timepick.TimePick(prefix="tp")
    kb = tp.keyboard_hours()["inline_keyboard"]
    assert len(kb) == 6                                  # title + 4×6 + cancel
    grid = kb[1:5]
    assert all(len(row) == 6 for row in grid)
    labels = [b["text"] for row in grid for b in row]
    assert labels[0] == "00" and labels[-1] == "23" and len(labels) == 24
    assert all(len(t) == 2 for t in labels)              # even cells
    assert len(kb[0][0]["text"]) == tg_timepick.TITLE_WIDTH   # stretches to the screen edge
    assert kb[-1][0]["callback_data"] == "tp:cancel"


def test_minutes_keyboard_and_parse_roundtrip():
    tp = tg_timepick.TimePick(prefix="tp")
    kb = tp.keyboard_minutes(16)["inline_keyboard"]
    mins = [b for row in kb[1:3] for b in row]
    assert [b["text"] for b in mins] == [
        "00", "05", "10", "15", "20", "25",
        "30", "35", "40", "45", "50", "55"]
    assert tp.parse(mins[6]["callback_data"]) == ("pick", "16:30")
    assert "16" in kb[0][0]["text"]                      # the title carries the hour
    assert tp.parse("tp:h:9") == ("minutes", 9)
    assert tp.parse("tp:hours") == ("hours", None)
    assert tp.parse("tp:cancel") == ("cancel", None)
    assert tp.parse("other:h:9") is None                 # foreign prefix ignored
    assert tp.parse("tp:h:99") == ("noop", None)
    assert tp.parse("tp:m:16:x") == ("noop", None)


def test_prefix_validation_is_loud_at_construction():
    """Same contract as the calendar: ':' or an over-budget prefix must fail
    at construction, not produce a silently dead widget or a send-time 400."""
    with pytest.raises(ValueError):
        tg_timepick.TimePick(prefix="a:b")
    with pytest.raises(ValueError):
        tg_timepick.TimePick(prefix="x" * 57)   # 64 - len(":m:23:59") = 56 is the cap


def test_minute_rows_stay_even_with_non_divisor_step():
    """A step that does not divide 60 must not leave a short last row — the
    tail is padded with blank noop cells, like the calendar's empty days."""
    tp = tg_timepick.TimePick(prefix="tp", minute_step=3)
    kb = tp.keyboard_minutes(16)["inline_keyboard"]
    minute_rows = [row for row in kb if any(":m:16:" in b["callback_data"] for b in row)]
    assert [len(row) for row in minute_rows] == [6, 6, 6, 6]
    tail = minute_rows[-1]
    assert [b["text"] for b in tail[:2]] == ["54", "57"]
    assert all(b["text"] == FIGSP * 2 and b["callback_data"] == "tp:noop" for b in tail[2:])


def test_minute_step_is_validated_loudly():
    """Out-of-contract steps must raise at construction (no silent clamping);
    a valid non-default step builds a padded single row."""
    for bad in (0, -5, True, 2.5, "5", 61):
        with pytest.raises(ValueError):
            tg_timepick.TimePick(minute_step=bad)
    kb = tg_timepick.TimePick(prefix="tp", minute_step=15).keyboard_minutes(9)["inline_keyboard"]
    minute_rows = [row for row in kb if any(":m:9:" in b["callback_data"] for b in row)]
    assert len(minute_rows) == 1
    assert [b["text"] for b in minute_rows[0]] == ["00", "15", "30", "45", FIGSP * 2, FIGSP * 2]


def test_parse_malformed_is_noop_not_crash():
    """Short/crafted payloads for OUR prefix degrade to noop, never raise."""
    tp = tg_timepick.TimePick(prefix="tp")
    for payload in ("tp:h", "tp:m", "tp:m:16", "tp:h:", "tp:h:x", "tp:m:16:"):
        assert tp.parse(payload) == ("noop", None)
    assert tp.parse("x:h:5") is None


def test_hours_keyboard_parse_roundtrip():
    """Every hour button's callback parses back to ('minutes', hour)."""
    tp = tg_timepick.TimePick(prefix="tp")
    kb = tp.keyboard_hours()["inline_keyboard"]
    buttons = [b for row in kb[1:5] for b in row]
    assert len(buttons) == 24
    for h, b in enumerate(buttons):
        assert tp.parse(b["callback_data"]) == ("minutes", h)


def test_parse_range_boundaries():
    tp = tg_timepick.TimePick(prefix="tp")
    assert tp.parse("tp:h:23") == ("minutes", 23)
    assert tp.parse("tp:h:24") == ("noop", None)
    assert tp.parse("tp:m:23:59") == ("pick", "23:59")
    assert tp.parse("tp:m:23:60") == ("noop", None)
    assert tp.parse("tp:m:24:0") == ("noop", None)


def test_back_to_hours_parse_roundtrip():
    """The back button's callback parses back to ('hours', None)."""
    tp = tg_timepick.TimePick(prefix="tp")
    kb = tp.keyboard_minutes(16)["inline_keyboard"]
    assert tp.parse(kb[-1][0]["callback_data"]) == ("hours", None)


def test_minutes_title_stretches_to_title_width():
    tp = tg_timepick.TimePick(prefix="tp")
    kb = tp.keyboard_minutes(16)["inline_keyboard"]
    assert len(kb[0][0]["text"]) == tg_timepick.TITLE_WIDTH


def test_title_width_value_is_pinned():
    """46 is the tuned screen-edge width; a drift must fail by number, not
    by self-reference."""
    assert tg_timepick.TITLE_WIDTH == 46


def test_superstring_prefix_is_foreign():
    """'tpx:*' does not belong to prefix 'tp': the boundary is prefix+':'."""
    assert tg_timepick.TimePick(prefix="tp").parse("tpx:h:5") is None


def test_custom_title_width_is_honoured():
    kb = tg_timepick.TimePick(prefix="tp", title_width=30).keyboard_hours()["inline_keyboard"]
    assert len(kb[0][0]["text"]) == 30
