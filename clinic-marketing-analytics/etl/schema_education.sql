-- Схема базы данных: education.db
-- Образовательный центр

CREATE TABLE IF NOT EXISTS crm_leads (
    lead_id         INTEGER PRIMARY KEY,
    created_at      TEXT NOT NULL,       -- полный datetime: '2024-03-15 14:23:07' (UTC)
    created_date    TEXT,                -- только дата: '2024-03-15' (для GROUP BY)
    updated_at      TEXT,
    status          TEXT,                -- won / lost / in_progress
    source          TEXT,                -- site_web / site_quiz / call / other
    tags            TEXT,                -- сырые теги через запятую
    price           REAL DEFAULT 0,
    pipeline_id     INTEGER,
    stage_id        INTEGER,             -- status_id в AmoCRM (текущий этап воронки)
    contact_id      INTEGER,
    is_bot          INTEGER DEFAULT 0,   -- 1 = помечен как бот (burst detection)
    -- UTM attribution (tracking_data поля из AmoCRM)
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
    -- Бизнес-классификация
    crm_source      TEXT,                -- поле "Источник" (AmoCRM)
    mesto_ucheby    TEXT,                -- "Место учёбы": Школа / Вуз / ...
    klass_kurs      TEXT,                -- "Класс/Курс": 9, 10, 11, ...
    pervoe_obr      TEXT,                -- "Первое обращение": Абитуриент / ...
    yazyk_obuch     TEXT,                -- "Язык обучения": Русский / Узбекский
    produkt         TEXT,                -- "Продукт": русский язык / математика / ...
    abc_category    TEXT,                -- "ABC - категории": A / B / C
    reklama_kanal   TEXT                 -- "каналы рекламы"
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
