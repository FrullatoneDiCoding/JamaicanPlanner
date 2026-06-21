# 🏖️ JamaicaPlanner

Bot Telegram per organizzare giornate (e serate) al mare con il gruppo:
chi viene quando, e che vento/meteo c'è in spiaggia.

## Funzioni

1. **Piano ferie** — calendario condiviso: tocca un giorno per segnare la
   tua presenza (il numero si racchiude in `[15]`), tocca di nuovo per
   toglierla (torna al numero nudo `15`). Un giorno mostrato come `(15)`
   indica che altri membri ci saranno anche se tu non sei tra loro.
   Niente emoji né simboli aggiuntivi: solo il numero, per restare
   compatti anche su mobile dentro un gruppo. Per vedere nomi e conteggio
   esatto di ogni giorno, usa "👥 Presenze del mese".
2. **Forecast** — scrivi il nome di una località e ricevi uno snapshot
   del vento (in **nodi**, con direzione e raffiche) e del meteo per le
   fasce orarie chiave della giornata (09:00, 12:00, 17:00, 00:00). Puoi
   specificare anche quanti giorni vedere direttamente nel comando, es.
   `/meteo Gallipoli 7` (da 1 a 16, default 3). Dati da
   [Open-Meteo](https://open-meteo.com), gratuito, nessuna chiave API
   richiesta.

Il bot è pensato per vivere dentro un gruppo Telegram chiuso: chiunque
nel gruppo può usare tutte le funzioni, senza approvazione.

## Setup

### 1. Crea il bot su Telegram

1. Apri una chat con [@BotFather](https://t.me/BotFather)
2. Manda `/newbot` e segui le istruzioni (nome: JamaicaPlanner, username
   a tua scelta, deve finire in `bot`)
3. Copia il token che ti viene dato (es. `123456789:ABCdef...`)

### 2. (Opzionale) Scopri il tuo ID Telegram

`ADMIN_IDS` non serve per le funzioni base del bot — è riservato a
eventuali comandi futuri ad uso esclusivo admin. Se vuoi impostarlo
comunque, apri una chat con [@userinfobot](https://t.me/userinfobot) e
copia il numero `Id` che ti restituisce.

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

Apri `.env` e inserisci almeno:
- `BOT_TOKEN` = il token ottenuto da BotFather

Lascia `ALLOWED_GROUP_ID` vuoto per ora — lo impostiamo al passo 6.

### 5. Avvia il bot la prima volta

```bash
python bot.py
```

Se tutto è configurato correttamente vedrai in console:
`JamaicaPlanner avviato, in polling...`

### 6. Restringi il bot al tuo gruppo

Senza questo passo, il bot risponderebbe in qualsiasi chat (anche in
privato o in altri gruppi).

1. Aggiungi il bot al gruppo Telegram dedicato
2. Nel gruppo, manda `/groupid` — il bot ti risponde con l'ID di quella chat
   (un numero negativo, es. `-1001234567890`)
3. Apri `.env` e imposta `ALLOWED_GROUP_ID` con quel numero (incluso il `-`)
4. Riavvia il bot (`Ctrl+C` poi `python bot.py` di nuovo)

Da questo momento il bot ignora ogni messaggio che non arrivi da quel
gruppo, avvisando chi scrive altrove che il bot non è disponibile lì.

### 7. (Opzionale) Abilita una chat privata per il debug

Se vuoi poter testare il bot scrivendogli in privato, senza disturbare
il gruppo, mentre la restrizione del passo 6 resta attiva:

1. Scrivi `/groupid` al bot in chat privata (apri una conversazione 1:1
   con lui su Telegram)
2. Copia il numero che ti risponde (questa volta sarà positivo, non
   negativo come per i gruppi)
3. Apri `.env` e imposta `ALLOWED_CHAT_ID` con quel numero
4. Riavvia il bot

Ora il bot funziona sia nel gruppo principale che nella tua chat privata,
ma resta bloccato altrove.

Il bot resta attivo finché il processo rimane in esecuzione (per test
locali va bene così; per uso continuo nel tempo andrà spostato su un
server sempre acceso — se vuoi, possiamo affrontarlo in seguito).

## Come si usa

- `/start` — messaggio di benvenuto con l'elenco dei comandi
- `/groupid` — mostra l'ID della chat corrente (serve in fase di setup
  per configurare `ALLOWED_GROUP_ID`)
- `/calendario` — apre il calendario del mese corrente, naviga con « e »,
  tocca un giorno per segnare/togliere la presenza, tocca "👥 Presenze
  del mese" per vedere l'elenco di tutti i giorni del mese con i nomi
  di chi sarà presente
- `/meteo Gallipoli` — vento (nodi, direzione, raffiche) e meteo per
  Gallipoli (o qualunque località) alle 09:00, 12:00, 17:00 e 00:00 dei
  prossimi 3 giorni (default)
- `/meteo Gallipoli 7` — come sopra ma per 7 giorni (da 1 a 16, limite
  massimo supportato da Open-Meteo; valori fuori range vengono adattati
  automaticamente con un avviso)
- `/meteo` (senza nome) — il bot chiede la località nel messaggio successivo
- `/membri` — elenco di chi ha usato il bot

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
- Statistiche tipo "giorno con più presenze del mese"
- Salvataggio di una località preferita per evitare di scriverla ogni volta
- Allerta automatica al gruppo se il vento previsto per la notte supera
  una soglia configurabile
