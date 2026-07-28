-- Database schema: education.db
-- Education center

CREATE TABLE IF NOT EXISTS crm_leads (
    lead_id         INTEGER PRIMARY KEY,
    created_at      TEXT NOT NULL,       -- full datetime: '2024-03-15 14:23:07' (UTC)
    created_date    TEXT,                -- date only: '2024-03-15' (for GROUP BY)
    updated_at      TEXT,
    status          TEXT,                -- won / lost / in_progress
    source          TEXT,                -- site_web / site_quiz / call / other
    tags            TEXT,                -- raw comma-separated tags
    price           REAL DEFAULT 0,
    pipeline_id     INTEGER,
    stage_id        INTEGER,             -- status_id in AmoCRM (current funnel stage)
    contact_id      INTEGER,
    is_bot          INTEGER DEFAULT 0,   -- 1 = flagged as a bot (burst detection)
    -- UTM attribution (tracking_data fields from AmoCRM)
    utm_source      TEXT,
    utm_medium      TEXT,
    utm_campaign    TEXT,
    utm_content     TEXT,
    utm_term        TEXT,
    gclid           TEXT,
    yclid           TEXT,
    fbclid          TEXT,
    roistat         TEXT,
    referrer        TEXT,
    gclientid       TEXT,                -- Google Analytics client ID (_ga cookie)
    -- Business classification
    crm_source        TEXT,                -- the "Source" field in AmoCRM
    study_location    TEXT,                -- "Place of study": school / university / ...
    grade_or_course   TEXT,                -- "Grade/Course": 9, 10, 11, ...
    inquiry_type      TEXT,                -- "First inquiry type": prospective student / ...
    instruction_language TEXT,             -- "Language of instruction": Russian / Uzbek
    product           TEXT,                -- "Product": Russian language / math / ...
    abc_category      TEXT,                -- "ABC category": A / B / C
    ad_channel        TEXT                 -- "Ad channel"
);

CREATE TABLE IF NOT EXISTS ga4_sessions (
    date            TEXT NOT NULL,
    channel         TEXT NOT NULL,
    sessions        INTEGER DEFAULT 0,
    engaged_sessions INTEGER DEFAULT 0,
    conversions     REAL DEFAULT 0,
    avg_duration_sec REAL DEFAULT 0,
    engagement_rate REAL DEFAULT 0,
    PRIMARY KEY (date, channel)
);

CREATE TABLE IF NOT EXISTS ga4_events (
    date            TEXT NOT NULL,
    event_label     TEXT NOT NULL,
    total           INTEGER DEFAULT 0,
    paid            INTEGER DEFAULT 0,
    PRIMARY KEY (date, event_label)
);

CREATE TABLE IF NOT EXISTS campaigns (
    date            TEXT NOT NULL,
    campaign_id     INTEGER NOT NULL,
    campaign_name   TEXT,
    impressions     INTEGER DEFAULT 0,
    clicks          INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0,
    conversions     REAL DEFAULT 0,
    conv_action     TEXT,
    PRIMARY KEY (date, campaign_id, conv_action)
);

CREATE TABLE IF NOT EXISTS events_log (
    event_date      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    description     TEXT,
    PRIMARY KEY (event_date, event_type)
);
