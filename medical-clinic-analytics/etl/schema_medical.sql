-- Схема базы данных: medical.db
-- Создаётся один раз: python -c "import sqlite3; ..."

CREATE TABLE IF NOT EXISTS crm_leads (
    lead_id         INTEGER PRIMARY KEY,
    created_at      TEXT NOT NULL,       -- ISO date: 2026-01-15
    status          TEXT,                -- won / lost / in_progress
    source          TEXT,                -- site_paid / site_organic / call / other
    price           REAL DEFAULT 0,
    pipeline_id     INTEGER,
    contact_id      INTEGER,             -- связь с контактом (человеком) для трекинга пути
    updated_at      TEXT
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
    event_label     TEXT NOT NULL,       -- "Отправка форм", "Клики по номеру"
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
    conv_action     TEXT,                -- название конкретной конверсии
    PRIMARY KEY (date, campaign_id, conv_action)
);

CREATE TABLE IF NOT EXISTS events_log (
    event_date      TEXT NOT NULL,
    event_type      TEXT NOT NULL,       -- site_launch / conv_change / campaign_pause
    description     TEXT,
    PRIMARY KEY (event_date, event_type)
);

-- Ключевые события (вставляем сразу)
INSERT OR IGNORE INTO events_log VALUES
    ('2026-06-23', 'site_launch', 'Запуск нового сайта');
