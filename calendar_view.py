"""
Generazione della tastiera inline per il calendario "Piano ferie".

Ogni giorno è un bottone:
- 🟩 se l'utente che guarda è presente quel giorno
- ⬜ se non è presente
Premendo il giorno si fa il toggle. Freccette per cambiare mese.
"""
import calendar
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import database

WEEKDAY_LABELS = ["Lu", "Ma", "Me", "Gi", "Ve", "Sa", "Do"]

MONTH_NAMES_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

# Prefissi usati nei callback_data per riconoscere il tipo di azione
CB_DAY = "day"
CB_NAV = "nav"
CB_WHO = "who"
CB_NOOP = "noop"


def build_calendar(year: int, month: int, user_id: int) -> InlineKeyboardMarkup:
    cal = calendar.Calendar(firstweekday=0)  # lunedì
    month_days = cal.itermonthdates(year, month)

    user_days = database.get_user_presence_days(user_id, year, month)
    presence_map = database.get_presence_for_month(year, month)

    month_name = MONTH_NAMES_IT[month]
    header = [
        InlineKeyboardButton("«", callback_data=f"{CB_NAV}:{year}:{month}:prev"),
        InlineKeyboardButton(f"{month_name} {year}", callback_data=CB_NOOP),
        InlineKeyboardButton("»", callback_data=f"{CB_NAV}:{year}:{month}:next"),
    ]

    weekday_row = [
        InlineKeyboardButton(label, callback_data=CB_NOOP) for label in WEEKDAY_LABELS
    ]

    rows = [header, weekday_row]
    week_row: list[InlineKeyboardButton] = []

    for day in month_days:
        if day.month != month:
            # giorno fuori dal mese corrente: bottone vuoto non interattivo
            week_row.append(InlineKeyboardButton(" ", callback_data=CB_NOOP))
        else:
            day_str = day.isoformat()
            is_present = day_str in user_days
            count = len(presence_map.get(day_str, []))

            symbol = "🟩" if is_present else "⬜"
            label = f"{symbol}{day.day}"
            if count > 0:
                label += f"·{count}"

            week_row.append(
                InlineKeyboardButton(label, callback_data=f"{CB_DAY}:{day_str}")
            )

        if len(week_row) == 7:
            rows.append(week_row)
            week_row = []

    if week_row:
        # completa l'ultima riga se incompleta
        while len(week_row) < 7:
            week_row.append(InlineKeyboardButton(" ", callback_data=CB_NOOP))
        rows.append(week_row)

    rows.append(
        [InlineKeyboardButton("👥 Chi viene oggi?", callback_data=f"{CB_WHO}:{date.today().isoformat()}")]
    )

    return InlineKeyboardMarkup(rows)


def shift_month(year: int, month: int, direction: str) -> tuple[int, int]:
    if direction == "next":
        if month == 12:
            return year + 1, 1
        return year, month + 1
    else:
        if month == 1:
            return year - 1, 12
        return year, month - 1
