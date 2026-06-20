# 🏖️ JamaicaPlanner

Bot Telegram per organizzare giornate (e serate) al mare con il gruppo:
chi viene quando, e che vento/meteo c'è in spiaggia.

## Funzioni

1. **Piano ferie** — calendario condiviso: tocca un giorno per segnare la
   tua presenza (diventa 🟩), tocca di nuovo per toglierla (torna ⬜).
   Il numero accanto al giorno indica quante persone in totale ci saranno.
2. **Forecast** — scrivi il nome di una località e ricevi meteo e vento
   per i prossimi giorni (dati da [Open-Meteo](https://open-meteo.com),
   gratuito, nessuna chiave API richiesta).

L'accesso al bot è controllato: i nuovi utenti devono essere approvati
manualmente dall'amministratore.

## Setup

### 1. Crea il bot su Telegram

1. Apri una chat con [@BotFather](https://t.me/BotFather)
2. Manda `/newbot` e segui le istruzioni (nome: JamaicaPlanner, username
   a tua scelta, deve finire in `bot`)
3. Copia il token che ti viene dato (es. `123456789:ABCdef...`)

### 2. Scopri il tuo ID Telegram (per diventare admin)

Apri una chat con [@userinfobot](https://t.me/userinfobot) e copia il
numero `Id` che ti restituisce.

### 3. Installa le dipendenze

```bash
cd jamaicaplanner
python3 -m venv venv
source venv/bin/activate   # su Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configura

```bash
cp .env.example .env
```

Apri `.env` e inserisci:
- `BOT_TOKEN` = il token ottenuto da BotFather
- `ADMIN_IDS` = il tuo ID Telegram (separati da virgola se più admin)

### 5. Avvia il bot

```bash
python bot.py
```

Se tutto è configurato correttamente vedrai in console:
`JamaicaPlanner avviato, in polling...`

Il bot resta attivo finché il processo rimane in esecuzione (per test
locali va bene così; per uso continuo nel tempo andrà spostato su un
server sempre acceso — se vuoi, possiamo affrontarlo in seguito).

## Come si usa

### Per i nuovi membri
- `/start` — richiede l'accesso. L'amministratore riceve una notifica
  con due bottoni (Approva / Rifiuta).

### Per l'amministratore
- `/pending` — mostra le richieste di accesso in sospeso
- Le richieste arrivano anche automaticamente come messaggio con bottoni

### Per i membri approvati
- `/calendario` — apre il calendario del mese corrente, naviga con « e »,
  tocca un giorno per segnare/togliere la presenza, tocca "👥 Chi viene
  oggi?" per vedere i presenti del giorno corrente
- `/meteo Gallipoli` — meteo e vento per Gallipoli (o qualunque località)
- `/meteo` (senza nome) — il bot chiede la località nel messaggio successivo
- `/membri` — elenco dei membri approvati

## Struttura dei file

```
jamaicaplanner/
├── bot.py             # entry point e tutti gli handler Telegram
├── config.py          # caricamento configurazione da .env
├── database.py        # accesso SQLite (utenti, presenze)
├── calendar_view.py   # generazione tastiera inline del calendario
├── weather.py         # chiamate a Open-Meteo (geocoding + forecast)
├── requirements.txt
├── .env.example
└── jamaicaplanner.db  # creato automaticamente al primo avvio
```

## Note tecniche

- Il database SQLite (`jamaicaplanner.db`) viene creato automaticamente
  al primo avvio nella stessa cartella del bot. Fanne un backup di tanto
  in tanto se i dati sono importanti (es. copiando il file).
- Il bot usa il *polling*, quindi non serve un server pubblico o un URL
  HTTPS: basta che il processo `python bot.py` resti in esecuzione su un
  PC connesso a internet.
- Se il PC va in sospensione o si stacca dalla rete, il bot smette di
  rispondere finché non lo si riavvia.
- Quando vorrai farlo girare 24/7, le opzioni più semplici sono un piccolo
  VPS (es. 4-5€/mese) oppure servizi come Railway/Fly.io con un piano
  gratuito limitato — possiamo configurarlo quando sarai pronto.

## Possibili estensioni future

- Promemoria automatici (es. la sera prima di un giorno con presenze)
- Comando per "rimuovere" un membro approvato
- Statistiche tipo "giorno con più presenze del mese"
- Salvataggio di una località preferita per evitare di scriverla ogni volta
