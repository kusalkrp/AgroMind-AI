"""
Geo Retriever — queries PostGIS for district and soil profile context.
Returns structured dicts consumed by PlannerAgent and ValidationAgent.
"""
from __future__ import annotations

from typing import Optional

import psycopg2
import psycopg2.extras
from loguru import logger

from config.settings import settings


def _get_conn():
    return psycopg2.connect(settings.postgres_url)


def get_district_context(district_name: str) -> dict:
    """
    Fetch district metadata including agro zone, rainfall zone, and coordinates.

    Returns a dict with district agronomic profile, or empty dict if not found.
    """
    sql = """
        SELECT
            d.name,
            d.province,
            d.agro_zone,
            d.rainfall_zone,
            d.annual_rainfall_mm,
            ST_Y(d.geom) AS lat,
            ST_X(d.geom) AS lon
        FROM districts d
        WHERE LOWER(d.name) = LOWER(%s)
        LIMIT 1
    """

    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (district_name,))
            row = cur.fetchone()
        conn.close()
    except Exception as exc:
        logger.error(f"geo_retriever: district query failed for {district_name}: {exc}")
        return {"error": str(exc)}

    if not row:
        logger.warning(f"District '{district_name}' not found in PostGIS")
        return {}

    return dict(row)


def get_soil_context(
    district_name: str,
    crop: Optional[str] = None,
) -> list[dict]:
    """
    Fetch soil profiles for a district, optionally filtered by suitability for a crop.

    Returns a list of soil profile dicts.
    """
    sql = """
        SELECT
            sp.soil_type,
            sp.ph_value,
            sp.organic_matter_pct,
            sp.nitrogen_ppm,
            sp.phosphorus_ppm,
            sp.potassium_ppm,
            sp.texture,
            sp.drainage,
            sp.sampled_date
        FROM soil_profiles sp
        JOIN districts d ON sp.district_id = d.id
        WHERE LOWER(d.name) = LOWER(%s)
        ORDER BY sp.sampled_date DESC
        LIMIT 5
    """

    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (district_name,))
            rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        logger.error(f"geo_retriever: soil query failed for {district_name}: {exc}")
        return []

    return [dict(r) for r in rows]


def get_nearby_districts(
    district_name: str,
    radius_km: float = 50.0,
) -> list[dict]:
    """
    Find districts within radius_km of the given district using PostGIS ST_DWithin.
    Useful for broadening market price and weather lookups.
    """
    sql = """
        SELECT
            target.name,
            target.agro_zone,
            ROUND(
                ST_Distance(
                    source.geom::geography,
                    target.geom::geography
                ) / 1000
            ) AS distance_km
        FROM districts source
        JOIN districts target
          ON target.name != source.name
         AND ST_DWithin(source.geom::geography, target.geom::geography, %s * 1000)
        WHERE LOWER(source.name) = LOWER(%s)
        ORDER BY distance_km ASC
        LIMIT 5
    """

    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (radius_km, district_name))
            rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        logger.error(f"geo_retriever: nearby districts query failed: {exc}")
        return []

    return [dict(r) for r in rows]
