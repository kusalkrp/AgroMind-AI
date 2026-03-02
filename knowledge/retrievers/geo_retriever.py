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
            d.lat,
            d.lon
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
    Find districts within radius_km of the given district.
    Uses Haversine approximation on lat/lon columns.
    """
    # First get the source district coordinates
    source = get_district_context(district_name)
    if not source or "lat" not in source or source.get("lat") is None:
        return []

    src_lat = float(source["lat"])
    src_lon = float(source["lon"])
    # Approx 1 degree lat ≈ 111 km; use bounding box then sort
    deg_radius = radius_km / 111.0

    sql = """
        SELECT
            name,
            agro_zone,
            lat,
            lon
        FROM districts
        WHERE LOWER(name) != LOWER(%s)
          AND lat BETWEEN %s AND %s
          AND lon BETWEEN %s AND %s
        LIMIT 10
    """

    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (
                district_name,
                src_lat - deg_radius, src_lat + deg_radius,
                src_lon - deg_radius, src_lon + deg_radius,
            ))
            rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        logger.error(f"geo_retriever: nearby districts query failed: {exc}")
        return []

    import math
    results = []
    for row in rows:
        if row["lat"] is None or row["lon"] is None:
            continue
        dlat = math.radians(float(row["lat"]) - src_lat)
        dlon = math.radians(float(row["lon"]) - src_lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(src_lat)) * math.cos(math.radians(float(row["lat"]))) * math.sin(dlon / 2) ** 2
        dist_km = round(6371 * 2 * math.asin(math.sqrt(a)), 1)
        if dist_km <= radius_km:
            results.append({"name": row["name"], "agro_zone": row["agro_zone"], "distance_km": dist_km})

    return sorted(results, key=lambda x: x["distance_km"])[:5]
