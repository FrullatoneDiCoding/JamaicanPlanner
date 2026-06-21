"""
JamaicaPlanner — bot Telegram per organizzare giornate e serate al mare
con il gruppo.

Il bot vive in un gruppo chiuso: non c'è controllo di accesso, chiunque
nel gruppo può usare tutte le funzioni.

Funzioni:
- Piano ferie: calendario condiviso a tap, verde = presente.
- Forecast: meteo e vento (in nodi) per una località, via Open-Meteo.

Avvio: python bot.py
"""
import logging
from datetime import date, datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

import calendar_view
import config
import database
import weather

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("jamaicaplanner")

# Stato in memoria: user_id -> "waiting_for_location" mentre aspettiamo
# che l'utente scriva una località dopo /meteo
AWAITING_LOCATION: set[int] = set()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def restrict_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guardia globale: se ALLOWED_GROUP_ID è configurato, blocca qualsiasi
    update che non provenga da quella chat o da una delle ALLOWED_CHAT_IDS
    (usate per debug in privato), prima che arrivi agli altri handler.
    Se ALLOWED_GROUP_ID non è impostato, non blocca nulla (utile in fase
    di test/sviluppo)."""
    if config.ALLOWED_GROUP_ID is None:
        return  # nessuna restrizione configurata

    chat = update.effective_chat
    if chat is None:
        return
    if chat.id == config.ALLOWED_GROUP_ID or chat.id in config.ALLOWED_CHAT_IDS:
        return  # ok, è la chat giusta (gruppo principale o chat di debug)

    # Chat diversa da quella autorizzata: avvisa (solo per messaggi/comandi
    # diretti, non per i click sui bottoni del calendario) e blocca.
    if update.message is not None:
        try:
            await update.message.reply_text(
                "🚫 Questo bot funziona solo nel gruppo a cui è dedicato."
            )
        except Exception:
            logger.exception("Impossibile avvisare la chat non autorizzata %s", chat.id if chat else "?")
    logger.warning("Update bloccato da chat non autorizzata: chat_id=%s", chat.id if chat else "?")
    raise ApplicationHandlerStop


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # Garantisce che l'utente esista in users (serve perché presence ha una
    # foreign key su users.user_id) — nessuna approvazione richiesta.
    database.ensure_user(user.id, user.username, user.first_name, status="approved")

    lines = [
        f"🏖️ Benvenuto su *JamaicaPlanner*, {user.first_name}!\n",
        "Comandi disponibili: cazzi e peni",
        "/calendario — segna la tua presenza",
        "/meteo <località> <giorni> — previsioni vento e meteo, es. /meteo Gallipoli 7",
        "/membri — elenco di chi ha usato il bot",
    ]

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def groupid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra l'ID della chat corrente, utile per configurare ALLOWED_GROUP_ID."""
    chat = update.effective_chat
    await update.message.reply_text(
        f"ID di questa chat: `{chat.id}`\n"
        f"Copialo in ALLOWED_GROUP_ID nel file .env per restringere il bot a questo gruppo.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def list_members_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    database.ensure_user(user.id, user.username, user.first_name, status="approved")
    members = database.list_approved()
    if not members:
        await update.message.reply_text("Nessun membro registrato ancora.")
        return
    lines = ["👥 *Membri del gruppo:*\n"]
    for m in members:
        lines.append(f"• {m['first_name']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /calendario — Piano ferie
# ---------------------------------------------------------------------------

async def calendario_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    database.ensure_user(user.id, user.username, user.first_name, status="approved")

    today = date.today()
    markup = calendar_view.build_calendar(today.year, today.month, user.id)
    await update.message.reply_text(
        "🏖️ *Piano ferie*\n"
        "Tocca un giorno per segnare/togliere la tua presenza.\n\n"
        "`[15]` = ci sei tu\n"
        "`(15)` = ci sono altri ma non tu\n"
        "`15` = nessuno\n\n"
        "Per i nomi e i numeri esatti, usa \"👥 Presenze del mese\" qui sotto.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )


async def handle_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    user_id = user.id

    # Garantisce che esista una riga in users prima di scrivere in presence,
    # che ha una foreign key su users.user_id.
    database.ensure_user(user_id, user.username, user.first_name, status="approved")

    data = query.data

    if data == calendar_view.CB_NOOP:
        await query.answer()
        return

    parts = data.split(":")
    action = parts[0]

    if action == calendar_view.CB_NAV:
        _, year_str, month_str, direction = parts
        year, month = calendar_view.shift_month(int(year_str), int(month_str), direction)
        markup = calendar_view.build_calendar(year, month, user_id)
        await query.edit_message_reply_markup(reply_markup=markup)
        await query.answer()

    elif action == calendar_view.CB_DAY:
        day_str = parts[1]
        day_obj = datetime.strptime(day_str, "%Y-%m-%d").date()
        now_present = database.toggle_presence(user_id, day_obj)
        markup = calendar_view.build_calendar(day_obj.year, day_obj.month, user_id)
        await query.edit_message_reply_markup(reply_markup=markup)
        await query.answer("Presenza segnata ✅" if now_present else "Presenza rimossa")

    elif action == calendar_view.CB_WHO:
        year, month = int(parts[1]), int(parts[2])
        text = build_month_attendance_text(year, month)
        await query.answer()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )


def build_month_attendance_text(year: int, month: int) -> str:
    """Costruisce il riepilogo testuale delle presenze di un mese,
    giorno per giorno, con i nomi dei partecipanti."""
    by_day = database.get_attendees_by_day_for_month(year, month)
    month_name = calendar_view.MONTH_NAMES_IT[month]

    if not by_day:
        return f"👥 *Presenze di {month_name} {year}*\n\nNessuna presenza ancora segnata."

    lines = [f"👥 *Presenze di {month_name} {year}*\n"]
    for day_str in sorted(by_day.keys()):
        day_num = int(day_str.split("-")[2])
        names = by_day[day_str]
        lines.append(f"*{day_num}* — {', '.join(names)} ({len(names)})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# /meteo — Forecast vento e meteo
# ---------------------------------------------------------------------------

async def meteo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    database.ensure_user(user.id, user.username, user.first_name, status="approved")

    if not context.args:
        AWAITING_LOCATION.add(user.id)
        await update.message.reply_text(
            "📍 Per quale località vuoi il meteo? Scrivi il nome (es. *Gallipoli*).\n"
            f"Puoi anche specificare i giorni: *Gallipoli 7* (da 1 a {weather.MAX_FORECAST_DAYS}, "
            f"default {weather.DEFAULT_FORECAST_DAYS}).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query_text, days = parse_location_and_days(context.args)
    await send_forecast_for_query(update, query_text, days=days)


def parse_location_and_days(args: list[str]) -> tuple[str, int]:
    """Estrae località e giorni opzionali da una lista di argomenti.
    Se l'ultimo token è un intero, viene interpretato come numero di giorni
    e rimosso dal nome della località. Altrimenti tutti gli argomenti
    formano la località e si usa il default."""
    if len(args) > 1:
        try:
            days = int(args[-1])
            return " ".join(args[:-1]), days
        except ValueError:
            pass
    return " ".join(args), weather.DEFAULT_FORECAST_DAYS


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in AWAITING_LOCATION:
        return  # ignora messaggi di testo non richiesti (es. chiacchiere nel gruppo)
    AWAITING_LOCATION.discard(user_id)
    query_text, days = parse_location_and_days(update.message.text.split())
    await send_forecast_for_query(update, query_text, days=days)


async def send_forecast_for_query(
    update: Update, query_text: str, days: int = weather.DEFAULT_FORECAST_DAYS
) -> None:
    clamped_days = max(1, min(days, weather.MAX_FORECAST_DAYS))

    msg = await update.effective_message.reply_text(f"🔎 Cerco '{query_text}'...")

    try:
        places = await weather.geocode(query_text)
    except Exception:
        logger.exception("Errore geocoding")
        await msg.edit_text("⚠️ Errore nel cercare la località. Riprova più tardi.")
        return

    if not places:
        await msg.edit_text(
            f"😕 Nessuna località trovata per '{query_text}'. Provare con un altro nome."
        )
        return

    place = places[0]

    try:
        forecasts = await weather.get_hourly_forecast(place.latitude, place.longitude, days=clamped_days)
    except Exception:
        logger.exception("Errore forecast")
        await msg.edit_text("⚠️ Errore nel recuperare le previsioni. Riprova più tardi.")
        return

    text = weather.format_forecast_message(place, forecasts, days=clamped_days)
    if clamped_days != days:
        text += f"\n\n⚠️ Giorni richiesti fuori range, mostrati {clamped_days} (max {weather.MAX_FORECAST_DAYS})."

    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Avvio applicazione
# ---------------------------------------------------------------------------

def main() -> None:
    config.validate()
    database.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Guardia globale, eseguita prima di tutti gli altri handler (group=-1).
    # Se l'update non blocca con ApplicationHandlerStop, raggiunge gli handler
    # normali (group=0 di default).
    app.add_handler(TypeHandler(Update, restrict_to_group), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("groupid", groupid_cmd))
    app.add_handler(CommandHandler("membri", list_members_cmd))
    app.add_handler(CommandHandler("calendario", calendario_cmd))
    app.add_handler(CommandHandler("meteo", meteo_cmd))

    app.add_handler(
        CallbackQueryHandler(
            handle_calendar_callback,
            pattern=rf"^({calendar_view.CB_DAY}|{calendar_view.CB_NAV}|{calendar_view.CB_WHO}|{calendar_view.CB_NOOP}):?",
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("JamaicaPlanner avviato, in polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
