"""
Weather Ingest — fetches daily weather data for Sri Lanka districts from Open-Meteo
(free API, no key required) and writes to TimescaleDB weather_daily hypertable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

# District centroids — fetched from districts.yaml at runtime
DISTRICT_COORDS: dict[str, tuple[float, float]] = {
    "Colombo": (6.9271, 79.8612),
    "Kandy": (7.2906, 80.6337),
    "Galle": (6.0535, 80.2210),
    "Jaffna": (9.6615, 80.0255),
    "Anuradhapura": (8.3114, 80.4037),
    "Kurunegala": (7.4818, 80.3609),
    "Ratnapura": (6.6828, 80.3992),
    "Badulla": (6.9934, 81.0550),
    "Trincomalee": (8.5874, 81.2152),
    "Matara": (5.9549, 80.5550),
}

OPEN_METEO_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "windspeed_10m_max",
    "et0_fao_evapotranspiration",
]


@dataclass
class DailyWeatherRecord:
    district: str
    obs_date: date
    temp_max_c: Optional[float]
    temp_min_c: Optional[float]
    precipitation_mm: Optional[float]
    windspeed_max_kmh: Optional[float]
    et0_mm: Optional[float]


@retry(
    stop=stop_after_attempt(settings.max_crawl_retries),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
async def _fetch_district_weather(
    client: httpx.AsyncClient,
    district: str,
    lat: float,
    lon: float,
    start_date: date,
    end_date: date,
) -> list[DailyWeatherRecord]:
    """Fetch daily weather data for a single district from Open-Meteo archive API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(OPEN_METEO_VARIABLES),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": "Asia/Colombo",
    }

    response = await client.get(settings.openmeteo_base_url, params=params, timeout=30.0)
    response.raise_for_status()
    data = response.json()

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    records = []

    for i, date_str in enumerate(dates):
        records.append(
            DailyWeatherRecord(
                district=district,
                obs_date=date.fromisoformat(date_str),
                temp_max_c=_safe_get(daily, "temperature_2m_max", i),
                temp_min_c=_safe_get(daily, "temperature_2m_min", i),
                precipitation_mm=_safe_get(daily, "precipitation_sum", i),
                windspeed_max_kmh=_safe_get(daily, "windspeed_10m_max", i),
                et0_mm=_safe_get(daily, "et0_fao_evapotranspiration", i),
            )
        )
    return records


def _safe_get(data: dict, key: str, idx: int) -> Optional[float]:
    values = data.get(key, [])
    if idx < len(values) and values[idx] is not None:
        return float(values[idx])
    return None


def _write_to_timescaledb(records: list[DailyWeatherRecord]) -> int:
    """Insert weather records into TimescaleDB weather_daily hypertable."""
    import psycopg2
    from psycopg2.extras import execute_values

    if not records:
        return 0

    insert_sql = """
        INSERT INTO weather_daily
            (district, obs_date, temp_max_c, temp_min_c, precipitation_mm,
             windspeed_max_kmh, et0_mm)
        VALUES %s
        ON CONFLICT (district, obs_date) DO UPDATE SET
            temp_max_c = EXCLUDED.temp_max_c,
            temp_min_c = EXCLUDED.temp_min_c,
            precipitation_mm = EXCLUDED.precipitation_mm,
            windspeed_max_kmh = EXCLUDED.windspeed_max_kmh,
            et0_mm = EXCLUDED.et0_mm;
    """

    rows = [
        (r.district, r.obs_date, r.temp_max_c, r.temp_min_c,
         r.precipitation_mm, r.windspeed_max_kmh, r.et0_mm)
        for r in records
    ]

    conn = psycopg2.connect(settings.postgres_url)
    try:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, rows)
        conn.commit()
        logger.info(f"Inserted/updated {len(rows)} weather records")
        return len(rows)
    except Exception as exc:
        conn.rollback()
        logger.error(f"DB write failed: {exc}")
        raise
    finally:
        conn.close()


async def ingest_weather(
    districts: list[str] | None = None,
    lookback_days: int = 7,
) -> int:
    """
    Fetch recent weather data for specified districts and persist to TimescaleDB.

    Args:
        districts: District names to fetch. Defaults to settings.weather_district_list.
        lookback_days: Number of past days to fetch (default 7).

    Returns:
        Total number of records written.
    """
    districts = districts or settings.weather_district_list
    end_date = date.today() - timedelta(days=1)  # Open-Meteo archive has 1-day lag
    start_date = end_date - timedelta(days=lookback_days - 1)

    logger.info(
        f"Fetching weather for {len(districts)} districts "
        f"from {start_date} to {end_date}"
    )

    all_records: list[DailyWeatherRecord] = []

    async with httpx.AsyncClient() as client:
        for district in districts:
            coords = DISTRICT_COORDS.get(district)
            if coords is None:
                logger.warning(f"No coordinates for district '{district}', skipping")
                continue
            lat, lon = coords
            try:
                records = await _fetch_district_weather(
                    client, district, lat, lon, start_date, end_date
                )
                logger.debug(f"{district}: {len(records)} daily records fetched")
                all_records.extend(records)
            except Exception as exc:
                logger.error(f"Failed to fetch weather for {district}: {exc}")

    written = _write_to_timescaledb(all_records)
    logger.info(f"Weather ingest complete: {written} records written")
    return written
