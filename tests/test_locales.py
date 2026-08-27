"""Locale behaviour of both widgets: English by default, Russian bundled,
custom label dicts validated loudly at construction time."""
import pytest

import tg_calendar
import tg_timepick

FIGSP = tg_calendar._FIGSP


def test_calendar_defaults_to_english():
    k = tg_calendar.Calendar().keyboard(2026, 6)["inline_keyboard"]
    assert "June 2026" in k[0][0]["text"]
    assert [b["text"] for b in k[1]] == ["‹ May", "July ›"]
    assert [b["text"] for b in k[2]] == list(tg_calendar.LOCALES["en"]["weekdays"])
    texts = [b["text"] for row in k for b in row]
    assert "Yesterday" in texts and "📅 Today" in texts and "Tomorrow" in texts
    assert "❌ Cancel" in texts


def test_calendar_russian_locale():
    k = tg_calendar.Calendar(locale="ru").keyboard(2026, 6)["inline_keyboard"]
    assert "Июнь 2026" in k[0][0]["text"]
    assert [b["text"] for b in k[2]] == list(tg_calendar.LOCALES["ru"]["weekdays"])
    texts = [b["text"] for row in k for b in row]
    assert "Вчера" in texts and "📅 Сегодня" in texts and "Завтра" in texts
    assert "❌ Отмена" in texts


def test_months_keyboard_and_month_title_follow_the_locale():
    en = tg_calendar.months_keyboard(lambda m: f"x:{m}")["inline_keyboard"]
    assert [b["text"].strip(FIGSP) for b in en[0]] == ["Jan", "Feb", "Mar"]
    ru = tg_calendar.months_keyboard(lambda m: f"x:{m}", locale="ru")["inline_keyboard"]
    assert [b["text"].strip(FIGSP) for b in ru[0]] == ["Янв", "Фев", "Мар"]
    assert tg_calendar.month_title(6, 2026, locale="ru").strip(FIGSP) == "Июнь 2026"


def test_calendar_custom_locale_dict():
    be = dict(tg_calendar.LOCALES["en"],
              weekdays=("Пан", "Аўт", "Сер", "Чац", "Пят", "Суб", "Няд"))
    k = tg_calendar.Calendar(locale=be).keyboard(2026, 6)["inline_keyboard"]
    assert k[2][0]["text"] == "Пан"


def test_calendar_locale_failures_are_loud_at_construction():
    with pytest.raises(ValueError):
        tg_calendar.Calendar(locale="de")
    with pytest.raises(ValueError):
        tg_calendar.Calendar(locale={"months": []})
    with pytest.raises(ValueError):
        tg_calendar.months_keyboard(lambda m: str(m), locale="xx")


def test_marker_and_digit_style_values_are_locale_independent():
    # a stored user preference (the VALUE) must survive a locale switch
    for key in ("markers", "digit_styles"):
        assert [v for v, _ in tg_calendar.LOCALES["en"][key]] == \
               [v for v, _ in tg_calendar.LOCALES["ru"][key]]


def test_timepick_defaults_to_english():
    tp = tg_timepick.TimePick()
    hours = tp.keyboard_hours()["inline_keyboard"]
    assert "Pick an hour" in hours[0][0]["text"]
    assert hours[-1][0]["text"] == "❌ Cancel"
    minutes = tp.keyboard_minutes(16)["inline_keyboard"]
    assert "16:·· — pick the minutes" in minutes[0][0]["text"]
    assert [b["text"] for b in minutes[-1]] == ["« Hours", "❌ Cancel"]


def test_timepick_russian_locale_and_title_override():
    tp = tg_timepick.TimePick(locale="ru")
    assert "Выбери час" in tp.keyboard_hours()["inline_keyboard"][0][0]["text"]
    minutes = tp.keyboard_minutes(9)["inline_keyboard"]
    assert "09:·· — выбери минуты" in minutes[0][0]["text"]
    assert [b["text"] for b in minutes[-1]] == ["« Часы", "❌ Отмена"]
    custom = tp.keyboard_hours(title="⏰ Своё")["inline_keyboard"]
    assert "⏰ Своё" in custom[0][0]["text"]


def test_timepick_locale_failures_are_loud_at_construction():
    with pytest.raises(ValueError):
        tg_timepick.TimePick(locale="xx")
    with pytest.raises(ValueError):
        tg_timepick.TimePick(locale={"hours_title": "t"})
    broken = dict(tg_timepick.LOCALES["en"], minutes_title="{hour} and {oops}")
    with pytest.raises(ValueError):
        tg_timepick.TimePick(locale=broken)
