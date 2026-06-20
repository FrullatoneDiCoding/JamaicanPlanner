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

# ID Telegram numerico dell'admin che approva i nuovi membri.
# Per scoprire il proprio ID, scrivere a @userinfobot su Telegram.
ADMIN_IDS: list[int] = [
    int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x
]

# Percorso del database SQLite
DB_PATH: str = os.environ.get("DB_PATH", "jamaicaplanner.db")

# Lingua usata nei messaggi (italiano fisso, ma centralizzato qui)
TIMEZONE: str = os.environ.get("TIMEZONE", "Europe/Rome")


def validate() -> None:
    """Controlla che la configurazione minima sia presente, altrimenti
    interrompe l'avvio con un messaggio chiaro."""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not ADMIN_IDS:
        missing.append("ADMIN_IDS")
    if missing:
        raise SystemExit(
            "Configurazione mancante: " + ", ".join(missing) +
            "\nCrea un file .env (vedi .env.example) oppure esporta le variabili d'ambiente."
        )
