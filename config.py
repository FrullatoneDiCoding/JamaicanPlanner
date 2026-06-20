"""
Configurazione del bot JamaicaPlanner.

Imposta le variabili tramite un file .env (consigliato) oppure
esportandole come variabili d'ambiente prima di avviare il bot.
"""
import os
from pathlib import Path

# Carica un file .env se presente (senza dipendenze esterne aggiuntive)
def _load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

# Token del bot ottenuto da @BotFather su Telegram
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")

# ID Telegram numerico/i dell'admin (separati da virgola).
# Il bot vive in un gruppo chiuso quindi non serve per approvare l'accesso;
# serve solo per comandi riservati come /giorniforecast.
# Per scoprire il proprio ID, scrivere a @userinfobot su Telegram.
ADMIN_IDS: list[int] = [
    int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x
]

# Percorso del database SQLite
DB_PATH: str = os.environ.get("DB_PATH", "jamaicaplanner.db")

# ID numerico del gruppo Telegram in cui il bot deve funzionare.
# I gruppi hanno ID negativi (es. -1001234567890), quindi può iniziare con "-".
# Se lasciato vuoto, il bot risponde ovunque (utile in fase di test).
# Per scoprirlo: manda /groupid al bot nel gruppo.
_allowed_group_raw = os.environ.get("ALLOWED_GROUP_ID", "").strip()
ALLOWED_GROUP_ID: int | None = int(_allowed_group_raw) if _allowed_group_raw else None

# ID numerico/i di chat aggiuntive sempre permesse, utili per fare debug in
# privato (es. la tua chat personale col bot) mentre il gruppo resta l'unica
# chat "ufficiale". Separati da virgola se più di uno. Per scoprire l'ID
# della tua chat privata, manda /groupid al bot in quella chat.
ALLOWED_CHAT_IDS: list[int] = [
    int(x) for x in os.environ.get("ALLOWED_CHAT_ID", "").replace(" ", "").split(",") if x
]

# Lingua usata nei messaggi (italiano fisso, ma centralizzato qui)
TIMEZONE: str = os.environ.get("TIMEZONE", "Europe/Rome")


def validate() -> None:
    """Controlla che la configurazione minima sia presente, altrimenti
    interrompe l'avvio con un messaggio chiaro. ADMIN_IDS non è
    obbligatorio: serve solo per i comandi riservati (es. /giorniforecast),
    non per l'accesso generale al bot."""
    if not BOT_TOKEN:
        raise SystemExit(
            "Configurazione mancante: BOT_TOKEN"
            "\nCrea un file .env (vedi .env.example) oppure esporta le variabili d'ambiente."
        )
