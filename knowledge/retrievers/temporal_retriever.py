"""
Temporal Retriever — queries TimescaleDB for weather and market price context.
Returns structured dicts consumed by RiskAgent and MarketAgent.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import psycopg2
import psycopg2.extras
from loguru import logger

from config.settings import settings


def _get_conn():
    return psycopg2.connect(settings.postgres_url)


# ── Weather ───────────────────────────────────────────────────────────────────

def get_weather_risk_context(
    district: str,
    days_lookback: int = 30,
) -> dict:
    """
    Fetch recent weather data for a district and compute risk indicators.

    Returns a dict with:
      - daily_summary: list of recent daily records
      - avg_temp_max_c, avg_temp_min_c, total_precip_mm
      - drought_risk: bool (< 10 mm rain over lookback period)
      - flood_risk: bool (any day > 100 mm rainfall)
      - heat_stress_risk: bool (any day > 35°C max)
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days_lookback)

    sql = """
        SELECT obs_date, temp_max_c, temp_min_c, precipitation_mm, et0_mm
        FROM weather_daily
        WHERE district = %s
          AND obs_date BETWEEN %s AND %s
        ORDER BY obs_date DESC
        LIMIT 60
    """

    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (district, start_date, end_date))
            rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        logger.error(f"temporal_retriever: weather query failed for {district}: {exc}")
        return {"error": str(exc), "district": district}

    if not rows:
        logger.warning(f"No weather data found for district '{district}'")
        return {"district": district, "records": 0}

    temps_max = [r["temp_max_c"] for r in rows if r["temp_max_c"] is not None]
    temps_min = [r["temp_min_c"] for r in rows if r["temp_min_c"] is not None]
    precips = [r["precipitation_mm"] for r in rows if r["precipitation_mm"] is not None]

    total_precip = sum(precips)
    avg_temp_max = round(sum(temps_max) / len(temps_max), 1) if temps_max else None
    avg_temp_min = round(sum(temps_min) / len(temps_min), 1) if temps_min else None

    return {
        "district": district,
        "period_days": days_lookback,
        "records": len(rows),
        "avg_temp_max_c": avg_temp_max,
        "avg_temp_min_c": avg_temp_min,
        "total_precipitation_mm": round(total_precip, 1),
        "max_daily_precip_mm": round(max(precips), 1) if precips else None,
        "drought_risk": total_precip < 10,
        "flood_risk": any(p > 100 for p in precips),
        "heat_stress_risk": any(t > 35 for t in temps_max),
        "daily_summary": [dict(r) for r in rows[:7]],  # last 7 days for prompt context
    }


# ── Market prices ─────────────────────────────────────────────────────────────

def get_market_price_context(
    commodity: str,
    district: Optional[str] = None,
    weeks: int = 8,
) -> dict:
    """
    Fetch recent market price history for a commodity.

    Returns a dict with:
      - prices: list of recent price records
      - avg_price_lkr, min_price_lkr, max_price_lkr
      - price_trend: "rising" | "falling" | "stable"
      - latest_price_lkr
    """
    end_date = date.today()
    start_date = end_date - timedelta(weeks=weeks)

    if district:
        sql = """
            SELECT mp.price_date, mp.commodity, mp.price_lkr, mp.unit,
                   mp.price_type, mp.market, d.name AS district_name
            FROM market_prices mp
            LEFT JOIN districts d ON mp.district_id = d.id
            WHERE LOWER(mp.commodity) LIKE LOWER(%s)
              AND d.name = %s
              AND mp.price_date BETWEEN %s AND %s
            ORDER BY mp.price_date DESC
            LIMIT 50
        """
        params = (f"%{commodity}%", district, start_date, end_date)
    else:
        sql = """
            SELECT price_date, commodity, price_lkr, unit, price_type, market
            FROM market_prices
            WHERE LOWER(commodity) LIKE LOWER(%s)
              AND price_date BETWEEN %s AND %s
            ORDER BY price_date DESC
            LIMIT 50
        """
        params = (f"%{commodity}%", start_date, end_date)

    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        logger.error(f"temporal_retriever: market query failed for {commodity}: {exc}")
        return {"error": str(exc), "commodity": commodity}

    if not rows:
        logger.warning(f"No market price data for commodity '{commodity}'")
        return {"commodity": commodity, "records": 0}

    prices = [float(r["price_lkr"]) for r in rows if r["price_lkr"] is not None]
    latest = prices[0] if prices else None

    # Simple trend: compare first half vs second half average
    mid = len(prices) // 2
    if mid > 0 and len(prices) > mid:
        recent_avg = sum(prices[:mid]) / mid
        older_avg = sum(prices[mid:]) / (len(prices) - mid)
        if recent_avg > older_avg * 1.05:
            trend = "rising"
        elif recent_avg < older_avg * 0.95:
            trend = "falling"
        else:
            trend = "stable"
    else:
        trend = "unknown"

    return {
        "commodity": commodity,
        "district": district,
        "period_weeks": weeks,
        "records": len(rows),
        "latest_price_lkr": latest,
        "avg_price_lkr": round(sum(prices) / len(prices), 2) if prices else None,
        "min_price_lkr": round(min(prices), 2) if prices else None,
        "max_price_lkr": round(max(prices), 2) if prices else None,
        "price_trend": trend,
        "recent_prices": [dict(r) for r in rows[:8]],
    }
