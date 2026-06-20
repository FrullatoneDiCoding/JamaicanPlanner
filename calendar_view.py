"""
Generazione della tastiera inline per il calendario "Piano ferie".

Telegram non permette di colorare il testo dei bottoni inline, quindi il
segnale "presente/assente" è dato dallo STILE delle cifre del numero,
non da emoji o simboli aggiuntivi (che su mobile, specie nei gruppi,
fanno traboccare il bottone e troncano il testo):

- numero in GRASSETTO Unicode (𝟏𝟓) → l'utente che guarda è presente
- numero in CORSIVO/SANS Unicode (𝟣𝟧) → altri sono presenti, ma non l'utente
- numero normale (15) → nessuno è presente

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

# Mappe cifra normale -> cifra Unicode stilizzata, stessa larghezza visiva
# di un numero normale (nessuna emoji, nessun carattere doppio).
_BOLD_DIGITS = {str(i): chr(0x1D7CE + i) for i in range(10)}   # 𝟎𝟏𝟐...
_SANS_DIGITS = {str(i): chr(0x1D7E2 + i) for i in range(10)}   # 𝟢𝟣𝟤...


def style_day_number(day: int, style: str) -> str:
    """Convverte il numero del giorno nello stile richiesto.
    style: 'bold' (presente), 'sans' (altri presenti), 'normal' (nessuno)."""
    digits = _BOLD_DIGITS if style == "bold" else _SANS_DIGITS if style == "sans" else None
    text = str(day)
    if digits is None:
        return text
    return "".join(digits[c] for c in text)


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
                style = "bold"
            elif others_present:
                style = "sans"
            else:
                style = "normal"

            label = style_day_number(day.day, style)

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