"""
Integrazione meteo/vento tramite Open-Meteo (gratuito, nessuna API key).

Flusso:
1. geocode(localita) -> lista di luoghi candidati (nome, lat, lon, paese)
2. get_forecast(lat, lon) -> previsioni giornaliere vento + meteo
"""
from dataclasses import dataclass

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

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
class DayForecast:
    date: str
    weather_code: int
    temp_max: float
    temp_min: float
    wind_speed_max: float  # km/h
    wind_gusts_max: float  # km/h
    wind_direction: int  # gradi

    def description(self) -> str:
        desc, emoji = WEATHER_CODES.get(self.weather_code, ("N/D", "❓"))
        return f"{emoji} {desc}"

    def wind_compass(self) -> str:
        directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        idx = round(self.wind_direction / 45) % 8
        return directions[idx]


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


async def get_forecast(lat: float, lon: float, days: int = 4) -> list[DayForecast]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": ",".join(
                    [
                        "weathercode",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "windspeed_10m_max",
                        "windgusts_10m_max",
                        "winddirection_10m_dominant",
                    ]
                ),
                "timezone": "Europe/Rome",
                "forecast_days": days,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    daily = data["daily"]
    forecasts = []
    for i, day in enumerate(daily["time"]):
        forecasts.append(
            DayForecast(
                date=day,
                weather_code=daily["weathercode"][i],
                temp_max=daily["temperature_2m_max"][i],
                temp_min=daily["temperature_2m_min"][i],
                wind_speed_max=daily["windspeed_10m_max"][i],
                wind_gusts_max=daily["windgusts_10m_max"][i],
                wind_direction=daily["winddirection_10m_dominant"][i],
            )
        )
    return forecasts


def format_forecast_message(place: Place, forecasts: list[DayForecast]) -> str:
    lines = [f"📍 *{place.label()}*\n"]
    for f in forecasts:
        lines.append(
            f"*{f.date}* — {f.description()}\n"
            f"  🌡️ {f.temp_min:.0f}°C / {f.temp_max:.0f}°C\n"
            f"  💨 vento {f.wind_speed_max:.0f} km/h (raffiche {f.wind_gusts_max:.0f} km/h) da {f.wind_compass()}\n"
        )
    return "\n".join(lines)
