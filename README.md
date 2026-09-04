# tg-calendar

*[Русская версия](README.ru.md)*

Inline-keyboard date and time pickers for Telegram bots: two self-contained files, standard
library only. Drop `tg_calendar.py` (month calendar) and, if you need it, `tg_timepick.py`
(hour/minute picker) into a bot, give each a callback prefix, and they render keyboards
whose columns stay even and whose width never jumps while you navigate — which, on Telegram
inline keyboards, is the hard part. Keyboards speak English by default; a Russian label set
is bundled, and any other language can be supplied as a dict (the `locale=` parameter).

Both modules run in production; the sizing rules below came out of dozens of
iterations on a real phone screen.

## Why it exists

Telegram inline buttons cannot be styled — no bold, no colour, no font size — and Telegram
divides button widths proportionally to the text length. A naive calendar therefore renders
with "dancing" columns and a keyboard that resizes on every navigation. This module encodes
the workarounds:

- **Constant-width cells.** Every day cell is padded to two "slots" with the figure space
  `U+2007` — a non-breaking space exactly one digit wide that Telegram does not trim
  (ordinary spaces are trimmed). Empty cells are two figure spaces. Columns stay put.
- **Constant-width title.** The month title is a full-width row padded with figure spaces
  to `TITLE_WIDTH`, so the longest row — and with it the whole keyboard — is the same
  width for every month.
- **A "today" you can actually see.** Button text cannot be styled, so today is highlighted
  inside the glyphs: an optional emoji marker plus a digit style — Unicode bold, fullwidth,
  or keycap digits.

## Features

- Month grid with prev/next navigation; weeks start on Monday.
- Optional quick-date footer — Yesterday / 📅 Today / Tomorrow — and an optional cancel row.
- Localised labels: English by default, Russian bundled (`locale="ru"`), any other language
  as a custom dict — validated at construction time. See Localisation.
- Today highlight: 14 markers × 4 digit styles; each locale carries `markers` and
  `digit_styles` (value, label) catalogues a host bot can expose as per-user settings — the
  values are locale-independent, so a stored preference survives a locale switch.
- `months_keyboard()` — a year-at-a-glance month picker, 4 rows × 3 months like a paper
  calendar, padded with the same discipline so the grid stretches to the screen edge.
- `pad_center()` — the exported padding helper, reusable for any full-width title button.
- Hostile-callback safe: a crafted or truncated callback with the calendar's prefix degrades
  to a no-op instead of raising — an exception swallowed by a callback handler would leave
  the Telegram button spinner hanging forever.
- Stateless: one `Calendar` instance serves any number of chats. "Today" is injectable
  (`today_fn`), which also makes the behaviour testable with a fixed date.
- `tg_timepick.py` — a sibling time picker: hour grid → minute grid → `"HH:MM"`, same
  width discipline, same noop-degrading parsing. See below.

## Quick start

```python
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
```

## API

- `Calendar(prefix="cal", *, title_width=46, footer_today=True, footer_cancel=True,
  today_fn=datetime.date.today, locale="en")` — give every use its own `prefix` so its
  callbacks (`<prefix>:nav|pick|yest|today|tom|cancel|noop`) never clash with other
  buttons.
- `Calendar.keyboard(year, month, *, marker="none", digits="bold")` → a
  `{"inline_keyboard": ...}` dict for `reply_markup`. `marker` is one of the locale's
  `markers` values; `digits` is `plain | bold | wide | keycap`.
- `Calendar.parse(data)` → `(kind, value)` for the calendar's own callbacks, else `None`:

  | callback | result |
  |---|---|
  | navigation | `("nav", (year, month))` — redraw with `keyboard(year, month)` |
  | a day, or a footer date | `("pick" / "today" / "yesterday" / "tomorrow", datetime.date)` |
  | cancel | `("cancel", None)` |
  | anything else with our prefix, malformed included | `("noop", None)` |
  | a foreign callback | `None` |

- `months_keyboard(cb_for_month, locale="en")` → the 4×3 month picker; `cb_for_month(m)`
  supplies the callback data for month 1..12, extra rows (back / cancel) are appended by
  the host.
- `pad_center(s, width=TITLE_WIDTH)`, `style_digits(day, style)`,
  `month_title(month, year, width=TITLE_WIDTH, locale="en")`, and the `LOCALES` dict with
  every label set.

## The time picker: tg_timepick.py

The sibling module — independent, copy it only if you need it:

```python
import tg_timepick

TP = tg_timepick.TimePick(prefix="tp", minute_step=5)   # locale="ru" for Russian

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
```

Flow: hour grid (00–23, four rows of six) → minute grid (`minute_step`, default 5, two
rows of six) → `("pick", "HH:MM")`. The minute view carries "back to hours" and cancel
rows; `keyboard_hours(title=...)` accepts a custom title. Every cell is two digits, the
header is a full-width figure-space-padded row — the same discipline as the calendar, and
the same parsing contract: malformed payloads degrade to `("noop", None)`, foreign
prefixes return `None`. Typed text input stays the host's parallel path — the picker only
adds taps.

## Localisation

Every label lives in the `LOCALES` dict of each module. The default locale is English;
`locale="ru"` selects the bundled Russian set (the modules were extracted from production
Russian-speaking bots, so the Russian strings are first-class data, not an afterthought):

```python
CAL = tg_calendar.Calendar(prefix="cal", locale="ru")
TP = tg_timepick.TimePick(prefix="tp", locale="ru")
```

Any other language is a dict of the same shape passed as `locale=` — it is validated at
construction time, so a typo or a missing label fails immediately rather than later inside
a callback handler. Marker and digit-style *values* are identical across locales — only
their labels translate — so a user preference stored by value survives a locale switch.
The width discipline does not depend on the language; just keep the title row the longest
row of the keyboard.

## Requirements

Python 3.12+. No dependencies.

## Development

Run these checks before every commit — CI runs the same five on every push:

```bash
ruff check .
python check_language.py
python check_versions.py
python sync.py
pytest
```

- **The repository is English-only** — code, comments, docstrings, commit messages, docs.
  Russian string literals are the product's data (UI labels, test fixtures), and
  `check_language.py` guards exactly that line: prose must be English, data may not be
  "fixed" into English silently.
- **Dependency ranges are bounded on both sides** (`requirements-dev.txt`): the lower bound
  is what the suite is run against, the upper one keeps a new major from arriving unread.
  `check_versions.py` proves the machine matches the ranges; Dependabot proposes bumps and
  CI answers on the pull request.
- **Line endings are LF in git** (`.gitattributes`), whatever the OS prefers locally.
- **Consumers sync from the repository.** The repository is the single source of truth for
  the modules and their tests (both are synced, so a consumer's suite always tests the
  copy it actually runs). The synced tests carry no `sys.path` bootstrap of their own: the
  consumer needs a `conftest.py` that puts the module directory on `sys.path`, kept in
  its own `tests/`. Consumers are listed, one directory per line, in
  `sync_targets.txt` (machine-specific, deliberately untracked); `python sync.py` reports
  any copy that drifted from the repository, `python sync.py --apply` overwrites the
  copies with the repository version. Never edit a module inside a consumer: make the
  change here, run the checks, then apply the sync.
- **Mind the literal figure spaces.** `tests/test_tg_calendar.py` contains literal `U+2007`
  characters inside string arguments — they look like ordinary spaces. Editors and tools
  may silently normalise them to `0x20`; the assertions are written so that this breaks the
  suite rather than passing silently, so run `pytest` after touching that file. In
  `tg_calendar.py` itself the figure space is built as `chr(0x2007)` — keep it that way.

## License

Apache-2.0.

## Author

Vitali Butkevich — [LinkedIn](https://www.linkedin.com/in/vitalybutkevich)
