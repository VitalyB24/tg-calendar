"""Standalone tests for the reusable tg_timepick module (hour/minute grids, parse)."""
import tg_timepick


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
