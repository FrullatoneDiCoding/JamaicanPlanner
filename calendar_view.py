"""
Generazione della tastiera inline per il calendario "Piano ferie".

Telegram non permette di colorare il testo dei bottoni inline (niente
font colorato, niente stile), quindi il segnale "presente/assente" è
dato solo dal numero del giorno, racchiuso in caratteri diversi — niente
emoji né simboli aggiuntivi, per restare il più compatti possibile anche
su mobile dentro un gruppo (dove la colonna dei bottoni è più stretta):

- [15] → l'utente che guarda è presente (parentesi quadre)
- (15) → altri sono presenti, ma non l'utente che guarda (parentesi tonde)
-  15  → nessuno è presente (solo il numero)

Premendo il giorno si fa il toggle. Freccette per cambiare mese.
"""
import calendar

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
            others_present = len(presence_map.get(day_str, [])) > 0

            if is_present:
                label = f"[{day.day}]"
            elif others_present:
                label = f"({day.day})"
            else:
                label = f"{day.day}"

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
        [InlineKeyboardButton("👥 Presenze del mese", callback_data=f"{CB_WHO}:{year}:{month}")]
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
