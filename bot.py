"""
JamaicaPlanner — bot Telegram per organizzare giornate e serate al mare
con il gruppo.

Funzioni:
- Accesso controllato: gli utenti richiedono accesso, l'admin approva/rifiuta.
- Piano ferie: calendario condiviso a tap, verde = presente.
- Forecast: meteo e vento per una località, via Open-Meteo.

Avvio: python bot.py
"""
import logging
from datetime import date, datetime

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
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


# ---------------------------------------------------------------------------
# Helpers di autorizzazione
# ---------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def require_approved(update: Update) -> bool:
    """Ritorna True se l'utente è approvato; altrimenti risponde e ritorna False."""
    user_id = update.effective_user.id
    if is_admin(user_id) or database.is_approved(user_id):
        return True
    await update.effective_message.reply_text(
        "🚫 Non hai ancora accesso a questo bot.\n"
        "Usa /start per richiederlo all'amministratore."
    )
    return False


# ---------------------------------------------------------------------------
# /start — richiesta di accesso
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if is_admin(user.id) or database.is_approved(user.id):
        await update.message.reply_text(
            f"🏖️ Bentornato su *JamaicaPlanner*, {user.first_name}!\n\n"
            "Comandi disponibili:\n"
            "/calendario — segna la tua presenza\n"
            "/meteo — previsioni vento e meteo\n",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    status = database.request_access(user.id, user.username, user.first_name)

    if status == "pending":
        await update.message.reply_text(
            "✅ Richiesta di accesso inviata. Riceverai un messaggio quando "
            "l'amministratore l'avrà approvata."
        )
        await notify_admins_new_request(context, user.id, user.username, user.first_name)
    elif status == "approved":
        await update.message.reply_text("✅ Sei già stato approvato, benvenuto!")
    elif status == "rejected":
        await update.message.reply_text(
            "🚫 La tua richiesta era stata rifiutata. Contatta l'amministratore "
            "se pensi sia un errore."
        )


async def notify_admins_new_request(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str | None, first_name: str | None
) -> None:
    name = first_name or "Utente"
    handle = f"@{username}" if username else f"id {user_id}"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approva", callback_data=f"approve:{user_id}"),
                InlineKeyboardButton("❌ Rifiuta", callback_data=f"reject:{user_id}"),
            ]
        ]
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 Nuova richiesta di accesso da *{name}* ({handle})",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception("Impossibile notificare admin %s", admin_id)


async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("Solo l'amministratore può farlo.", show_alert=True)
        return

    action, user_id_str = query.data.split(":")
    target_id = int(user_id_str)
    target = database.get_user(target_id)

    if action == "approve":
        database.set_status(target_id, "approved")
        await query.answer("Utente approvato ✅")
        await query.edit_message_text(
            f"✅ Approvato: {target['first_name'] if target else target_id}"
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 Sei stato approvato! Usa /calendario o /meteo per iniziare.",
            )
        except Exception:
            logger.exception("Impossibile notificare l'utente approvato %s", target_id)
    elif action == "reject":
        database.set_status(target_id, "rejected")
        await query.answer("Richiesta rifiutata")
        await query.edit_message_text(
            f"❌ Rifiutato: {target['first_name'] if target else target_id}"
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🚫 La tua richiesta di accesso è stata rifiutata.",
            )
        except Exception:
            logger.exception("Impossibile notificare l'utente rifiutato %s", target_id)


async def list_pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    pending = database.list_pending()
    if not pending:
        await update.message.reply_text("Nessuna richiesta in sospeso.")
        return
    lines = ["📋 *Richieste in sospeso:*\n"]
    for p in pending:
        handle = f"@{p['username']}" if p["username"] else f"id {p['user_id']}"
        lines.append(f"• {p['first_name']} ({handle})")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def list_members_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_approved(update):
        return
    members = database.list_approved()
    if not members:
        await update.message.reply_text("Nessun membro approvato ancora.")
        return
    lines = ["👥 *Membri del gruppo:*\n"]
    for m in members:
        lines.append(f"• {m['first_name']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /calendario — Piano ferie
# ---------------------------------------------------------------------------

async def calendario_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_approved(update):
        return
    today = date.today()
    markup = calendar_view.build_calendar(today.year, today.month, update.effective_user.id)
    await update.message.reply_text(
        "🏖️ *Piano ferie*\n"
        "Tocca un giorno per segnare/togliere la tua presenza.\n"
        "🟩 = presente · ⬜ = assente · il numero indica quanti membri ci saranno.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )


async def handle_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if not (is_admin(user_id) or database.is_approved(user_id)):
        await query.answer("Non hai accesso a questo bot.", show_alert=True)
        return

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
        day_str = parts[1]
        day_obj = datetime.strptime(day_str, "%Y-%m-%d").date()
        attendees = database.get_attendees_for_day(day_obj)
        if attendees:
            names = ", ".join(a["first_name"] for a in attendees)
            text = f"👥 Il {day_str} ci saranno: {names}"
        else:
            text = f"Nessuno ha ancora confermato per il {day_str}."
        await query.answer(text, show_alert=True)


# ---------------------------------------------------------------------------
# /meteo — Forecast vento e meteo
# ---------------------------------------------------------------------------

async def meteo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_approved(update):
        return

    if context.args:
        query_text = " ".join(context.args)
        await send_forecast_for_query(update, query_text)
    else:
        AWAITING_LOCATION.add(update.effective_user.id)
        await update.message.reply_text(
            "📍 Per quale località vuoi il meteo? Scrivi il nome (es. *Gallipoli*).",
            parse_mode=ParseMode.MARKDOWN,
        )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in AWAITING_LOCATION:
        return  # ignora messaggi di testo non richiesti
    AWAITING_LOCATION.discard(user_id)
    if not await require_approved(update):
        return
    await send_forecast_for_query(update, update.message.text)


async def send_forecast_for_query(update: Update, query_text: str) -> None:
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
        forecasts = await weather.get_forecast(place.latitude, place.longitude)
    except Exception:
        logger.exception("Errore forecast")
        await msg.edit_text("⚠️ Errore nel recuperare le previsioni. Riprova più tardi.")
        return

    text = weather.format_forecast_message(place, forecasts)
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Avvio applicazione
# ---------------------------------------------------------------------------

def main() -> None:
    config.validate()
    database.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", list_pending_cmd))
    app.add_handler(CommandHandler("membri", list_members_cmd))
    app.add_handler(CommandHandler("calendario", calendario_cmd))
    app.add_handler(CommandHandler("meteo", meteo_cmd))

    app.add_handler(
        CallbackQueryHandler(handle_approval_callback, pattern=r"^(approve|reject):")
    )
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
