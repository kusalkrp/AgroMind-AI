-- AgroMind AI — Database Initialisation
-- Requires: TimescaleDB extension (community image: timescale/timescaledb:latest-pg16)
-- PostGIS is used when available (timescaledb-ha or postgis image); gracefully skipped otherwise.
-- Run: psql $POSTGRES_URL -f scripts/init_db.sql

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- PostGIS is optional — present in timescaledb-ha, absent in community image.
-- Geo columns fall back to TEXT lat/lon when PostGIS is unavailable.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS postgis CASCADE;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'PostGIS not available — geo columns will use lat/lon TEXT fallback';
END $$;

-- ── Districts ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS districts (
    id                 SERIAL PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,
    province           TEXT NOT NULL,
    agro_zone          TEXT NOT NULL,
    rainfall_zone      TEXT NOT NULL,
    annual_rainfall_mm INTEGER,
    lat                REAL,
    lon                REAL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_districts_agro_zone ON districts (agro_zone);
CREATE INDEX IF NOT EXISTS idx_districts_name ON districts (LOWER(name));

COMMENT ON TABLE districts IS 'Sri Lanka administrative districts with agronomic metadata';

-- ── Seed all 25 districts ─────────────────────────────────────────────────────
INSERT INTO districts (name, province, agro_zone, rainfall_zone, annual_rainfall_mm, lat, lon)
VALUES
  ('Colombo',       'Western',       'Wet Zone',              'High',      2400, 6.9271,  79.8612),
  ('Gampaha',       'Western',       'Wet Zone',              'High',      2100, 7.0917,  80.0000),
  ('Kalutara',      'Western',       'Wet Zone',              'High',      2800, 6.5854,  79.9607),
  ('Kandy',         'Central',       'Mid-country Wet Zone',  'High',      1900, 7.2906,  80.6337),
  ('Matale',        'Central',       'Intermediate Zone',     'Medium',    1650, 7.4675,  80.6234),
  ('Nuwara Eliya',  'Central',       'Upcountry Wet Zone',    'Very High', 2500, 6.9497,  80.7891),
  ('Galle',         'Southern',      'Wet Zone',              'High',      2400, 6.0535,  80.2210),
  ('Matara',        'Southern',      'Wet Zone',              'High',      2200, 5.9549,  80.5550),
  ('Hambantota',    'Southern',      'Dry Zone',              'Low',       1000, 6.1429,  81.1212),
  ('Jaffna',        'Northern',      'Dry Zone',              'Low',       1000, 9.6615,  80.0255),
  ('Kilinochchi',   'Northern',      'Dry Zone',              'Low',       1100, 9.3803,  80.3770),
  ('Mannar',        'Northern',      'Dry Zone',              'Low',        900, 8.9810,  79.9044),
  ('Vavuniya',      'Northern',      'Dry Zone',              'Low',       1200, 8.7514,  80.4971),
  ('Mullaitivu',    'Northern',      'Dry Zone',              'Low',       1400, 9.2671,  80.8128),
  ('Batticaloa',    'Eastern',       'Dry Zone',              'Medium',    1600, 7.7170,  81.7003),
  ('Ampara',        'Eastern',       'Dry Zone',              'Low',       1700, 7.2980,  81.6726),
  ('Trincomalee',   'Eastern',       'Dry Zone',              'Low',       1600, 8.5874,  81.2152),
  ('Kurunegala',    'North Western', 'Intermediate Zone',     'Medium',    1500, 7.4818,  80.3609),
  ('Puttalam',      'North Western', 'Dry Zone',              'Low',        900, 8.0362,  79.8283),
  ('Anuradhapura',  'North Central', 'Dry Zone',              'Low',       1200, 8.3114,  80.4037),
  ('Polonnaruwa',   'North Central', 'Dry Zone',              'Low',       1400, 7.9403,  81.0188),
  ('Badulla',       'Uva',           'Intermediate Zone',     'Medium',    1800, 6.9934,  81.0550),
  ('Monaragala',    'Uva',           'Dry Zone',              'Low',       1300, 6.8728,  81.3507),
  ('Ratnapura',     'Sabaragamuwa',  'Wet Zone',              'Very High', 3500, 6.6828,  80.3992),
  ('Kegalle',       'Sabaragamuwa',  'Wet Zone',              'High',      2600, 7.2513,  80.3464)
ON CONFLICT (name) DO NOTHING;

-- ── Weather (TimescaleDB hypertable) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weather_daily (
    obs_date          DATE NOT NULL,
    district          TEXT NOT NULL,
    temp_max_c        REAL,
    temp_min_c        REAL,
    precipitation_mm  REAL,
    windspeed_max_kmh REAL,
    et0_mm            REAL,
    source            TEXT DEFAULT 'open-meteo',
    ingested_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (district, obs_date)
);

SELECT create_hypertable(
    'weather_daily',
    'obs_date',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 month'
);

CREATE INDEX IF NOT EXISTS idx_weather_district ON weather_daily (district, obs_date DESC);

COMMENT ON TABLE weather_daily IS
    'Daily weather observations per district — TimescaleDB hypertable';

-- ── Soil Profiles (without PostGIS geom for community image compatibility) ────
CREATE TABLE IF NOT EXISTS soil_profiles (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    district_id        INTEGER REFERENCES districts(id),
    soil_type          TEXT NOT NULL,
    ph_value           REAL,
    organic_matter_pct REAL,
    nitrogen_ppm       REAL,
    phosphorus_ppm     REAL,
    potassium_ppm      REAL,
    texture            TEXT,
    drainage           TEXT,
    sampled_date       DATE,
    source             TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_soil_profiles_district ON soil_profiles (district_id);

COMMENT ON TABLE soil_profiles IS 'Soil type and nutrient profiles per district';

-- ── Market Prices ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_prices (
    id          UUID NOT NULL DEFAULT uuid_generate_v4(),
    price_date  DATE NOT NULL,
    commodity   TEXT NOT NULL,
    market      TEXT,
    district_id INTEGER REFERENCES districts(id),
    price_lkr   REAL,
    unit        TEXT DEFAULT 'kg',
    price_type  TEXT DEFAULT 'wholesale',
    source_url  TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- TimescaleDB hypertable: partition column must be in the primary key
    PRIMARY KEY (id, price_date)
);

SELECT create_hypertable(
    'market_prices',
    'price_date',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 month'
);

CREATE INDEX IF NOT EXISTS idx_market_commodity ON market_prices (commodity, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_district  ON market_prices (district_id, price_date DESC);

COMMENT ON TABLE market_prices IS
    'Weekly wholesale/retail crop prices — TimescaleDB hypertable';

-- ── Ingestion Log ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_log (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename      TEXT NOT NULL,
    source        TEXT,
    strategy      TEXT,
    total_pages   INTEGER DEFAULT 0,
    ocr_pages     INTEGER DEFAULT 0,
    chunk_count   INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'processed',
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ingestion_log IS 'Tracks every document processed by the ingestion pipeline';

-- ── Decision Log ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decision_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    query           TEXT NOT NULL,
    intent          TEXT,
    agents_invoked  TEXT[],
    rag_sources     TEXT[],
    crag_grade      TEXT,
    cag_hit         BOOLEAN DEFAULT FALSE,
    response_text   TEXT,
    reasoning_trace JSONB,
    latency_ms      INTEGER,
    district_id     INTEGER REFERENCES districts(id),
    crop_types      TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_log_session ON decision_log (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_log_intent  ON decision_log (intent);
CREATE INDEX IF NOT EXISTS idx_decision_log_created ON decision_log (created_at DESC);

COMMENT ON TABLE decision_log IS 'Audit trail of all agent decisions and RAG retrievals';
