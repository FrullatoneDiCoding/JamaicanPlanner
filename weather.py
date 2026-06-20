"""
Integrazione meteo/vento tramite Open-Meteo (gratuito, nessuna API key).

Pensato per le nottate in spiaggia: il vento è il dato principale (in nodi,
con direzione cardinale), mostrato a 4 fasce orarie chiave della giornata.

Flusso:
1. geocode(localita) -> lista di luoghi candidati (nome, lat, lon, paese)
2. get_hourly_forecast(lat, lon) -> dati orari per i prossimi giorni
3. build_daily_snapshots(...) -> estrae solo le ore richieste (09, 12, 17, 00)
"""
from dataclasses import dataclass
from datetime import datetime

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Ore della giornata da mostrare come "snapshot". 00:00 rappresenta la
# fascia notturna (di fatto la notte del giorno corrente che inizia).
SNAPSHOT_HOURS = [9, 12, 17, 0]

# Open-Meteo supporta al massimo 16 giorni di previsione orarie.
MAX_FORECAST_DAYS = 16
DEFAULT_FORECAST_DAYS = 3

# Codici WMO -> descrizione + emoji (sottoinsieme comune)
WEATHER_CODES = {
    0: ("Sereno", "☀️"),
    1: ("Prevalentemente sereno", "🌤️"),
    2: ("Parzialmente nuvoloso", "⛅"),
    3: ("Nuvoloso", "☁️"),
    45: ("Nebbia", "🌫️"),
    48: ("Nebbia con brina", "🌫️"),
    51: ("Pioggerella leggera", "🌦️"),
    53: ("Pioggerella moderata", "🌦️"),
    55: ("Pioggerella intensa", "🌧️"),
    61: ("Pioggia leggera", "🌦️"),
    63: ("Pioggia moderata", "🌧️"),
    65: ("Pioggia intensa", "🌧️"),
    71: ("Neve leggera", "🌨️"),
    73: ("Neve moderata", "🌨️"),
    75: ("Neve intensa", "🌨️"),
    80: ("Rovesci leggeri", "🌦️"),
    81: ("Rovesci moderati", "🌧️"),
    82: ("Rovesci violenti", "⛈️"),
    95: ("Temporale", "⛈️"),
    96: ("Temporale con grandine", "⛈️"),
    99: ("Temporale violento con grandine", "⛈️"),
}

COMPASS_DIRECTIONS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]


def direction_to_compass(degrees: int) -> str:
    idx = round(degrees / 45) % 8
    return COMPASS_DIRECTIONS[idx]


def wind_emoji(knots: float) -> str:
    """Indicatore visivo rapido dell'intensità del vento, in nodi.
    Scala pensata per uso da spiaggia/mare (Beaufort semplificata)."""
    if knots < 17:
        return "🟢"  # calmo / brezza leggera, ottimo
    if knots < 22:
        return "🟡"  # moderato
    if knots < 27:
        return "🟠"  # teso
    return "🔴"  # forte, attenzione


@dataclass
class Place:
    name: str
    country: str
    admin1: str | None
    latitude: float
    longitude: float

    def label(self) -> str:
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        parts.append(self.country)
        return ", ".join(parts)


@dataclass
class HourSnapshot:
    dt: datetime
    weather_code: int
    temperature: float
    wind_knots: float
    wind_gusts_knots: float
    wind_direction: int

    def description(self) -> str:
        desc, emoji = WEATHER_CODES.get(self.weather_code, ("N/D", "❓"))
        return f"{emoji} {desc}"

    def compass(self) -> str:
        return direction_to_compass(self.wind_direction)

    def wind_label(self) -> str:
        return (
            f"{wind_emoji(self.wind_knots)} {self.wind_knots:.0f} nodi "
            f"(raffiche {self.wind_gusts_knots:.0f}) da {self.compass()}"
        )


async def geocode(query: str, limit: int = 5) -> list[Place]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            GEOCODING_URL,
            params={"name": query, "count": limit, "language": "it", "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results") or []
    return [
        Place(
            name=r["name"],
            country=r.get("country", ""),
            admin1=r.get("admin1"),
            latitude=r["latitude"],
            longitude=r["longitude"],
        )
        for r in results
    ]


async def get_hourly_forecast(lat: float, lon: float, days: int = DEFAULT_FORECAST_DAYS) -> list[HourSnapshot]:
    """Scarica i dati orari (vento in nodi) per i prossimi `days` giorni.
    `days` viene limitato tra 1 e MAX_FORECAST_DAYS (limite imposto da Open-Meteo)."""
    days = max(1, min(days, MAX_FORECAST_DAYS))
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": ",".join(
                    [
                        "weathercode",
                        "temperature_2m",
                        "windspeed_10m",
                        "windgusts_10m",
                        "winddirection_10m",
                    ]
                ),
                "windspeed_unit": "kn",  # nodi nativi, niente conversioni manuali
                "timezone": "Europe/Rome",
                "forecast_days": days,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    hourly = data["hourly"]
    snapshots = []
    for i, dt_str in enumerate(hourly["time"]):
        snapshots.append(
            HourSnapshot(
                dt=datetime.fromisoformat(dt_str),
                weather_code=hourly["weathercode"][i],
                temperature=hourly["temperature_2m"][i],
                wind_knots=hourly["windspeed_10m"][i],
                wind_gusts_knots=hourly["windgusts_10m"][i],
                wind_direction=hourly["winddirection_10m"][i],
            )
        )
    return snapshots


def build_daily_snapshots(
    snapshots: list[HourSnapshot], hours: list[int] = SNAPSHOT_HOURS
) -> dict[str, dict[int, HourSnapshot]]:
    """Raggruppa gli snapshot orari per giorno, mantenendo solo le ore richieste.
    Ritorna {data_iso: {ora: HourSnapshot}}."""
    by_day: dict[str, dict[int, HourSnapshot]] = {}
    for snap in snapshots:
        if snap.dt.hour not in hours:
            continue
        day_key = snap.dt.date().isoformat()
        by_day.setdefault(day_key, {})[snap.dt.hour] = snap
    return by_day


def format_forecast_message(
    place: Place,
    snapshots: list[HourSnapshot],
    hours: list[int] = SNAPSHOT_HOURS,
    days: int = DEFAULT_FORECAST_DAYS,
) -> str:
    days = max(1, min(days, MAX_FORECAST_DAYS))
    by_day = build_daily_snapshots(snapshots, hours)
    day_keys = sorted(by_day.keys())[:days]

    lines = [f"📍 *{place.label()}*\n"]

    for day_key in day_keys:
        day_obj = datetime.fromisoformat(day_key).date()
        lines.append(f"*{day_obj.strftime('%d/%m')}*")
        hours_for_day = by_day[day_key]

        for hour in hours:
            snap = hours_for_day.get(hour)
            if not snap:
                continue
            label = "00:00 🌙" if hour == 0 else f"{hour:02d}:00"
            lines.append(
                f"  {label} — {snap.description()}, {snap.temperature:.0f}°C\n"
                f"     {snap.wind_label()}"
            )
        lines.append("")  # riga vuota tra i giorni

    return "\n".join(lines).rstrip()
