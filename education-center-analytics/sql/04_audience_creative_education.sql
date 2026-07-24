-- ============================================================
-- Образовательный центр: аудитория (возраст/пол) и креативы (RSA)
-- База: education_ads.db
-- ============================================================
-- Запуск: python run_sql.py sql/04_audience_creative_education.sql data/education_ads.db

-- ============================================================
-- 1. ВОЗРАСТ: объём, CTR, конверсия, стоимость лида — за весь период
-- ============================================================
SELECT
    segment_value                                            AS age_range,
    SUM(impressions)                                         AS impressions,
    SUM(clicks)                                               AS clicks,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 2) AS ctr_pct,
    ROUND(SUM(conversions), 1)                                AS conversions,
    ROUND(100.0 * SUM(conversions) / NULLIF(SUM(clicks), 0), 2) AS cvr_pct,
    ROUND(SUM(cost_micros) / 1e6, 1)                          AS spend_usd,
    ROUND(SUM(cost_micros) / 1e6 / NULLIF(SUM(conversions), 0), 1) AS cpa_usd
FROM ads_demographics
WHERE dimension = 'age_range'
GROUP BY segment_value
ORDER BY impressions DESC;


-- ============================================================
-- 2. ПОЛ: та же разбивка
-- ============================================================
SELECT
    segment_value                                            AS gender,
    SUM(impressions)                                         AS impressions,
    SUM(clicks)                                               AS clicks,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 2) AS ctr_pct,
    ROUND(SUM(conversions), 1)                                AS conversions,
    ROUND(100.0 * SUM(conversions) / NULLIF(SUM(clicks), 0), 2) AS cvr_pct,
    ROUND(SUM(cost_micros) / 1e6, 1)                          AS spend_usd,
    ROUND(SUM(cost_micros) / 1e6 / NULLIF(SUM(conversions), 0), 1) AS cpa_usd
FROM ads_demographics
WHERE dimension = 'gender'
GROUP BY segment_value
ORDER BY impressions DESC;


-- ============================================================
-- 3. ВОЗРАСТ × МЕСЯЦ: меняется ли профиль аудитории со временем
-- ============================================================
SELECT
    strftime('%Y-%m', date)                                  AS month,
    segment_value                                            AS age_range,
    SUM(impressions)                                         AS impressions,
    ROUND(100.0 * SUM(conversions) / NULLIF(SUM(clicks), 0), 2) AS cvr_pct
FROM ads_demographics
WHERE dimension = 'age_range'
GROUP BY month, segment_value
ORDER BY month, impressions DESC;


-- ============================================================
-- 4. RSA: топ заголовков по объёму (только с заметным трафиком,
--    чтобы CTR не был шумом на 5 показах)
-- ============================================================
SELECT
    asset_text,
    performance_label,
    SUM(impressions)                                         AS impressions,
    SUM(clicks)                                               AS clicks,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 2) AS ctr_pct
FROM ads_creative_assets
WHERE field_type = 'HEADLINE'
GROUP BY asset_text
HAVING SUM(impressions) >= 500
ORDER BY impressions DESC
LIMIT 30;


-- ============================================================
-- 5. RSA: CTR по ТЕМЕ сообщения (Google performance_label здесь
--    не считается — NOT_APPLICABLE, поэтому смотрим по смыслу текста)
-- ============================================================
SELECT
    CASE
        WHEN LOWER(asset_text) LIKE '%боишься%' OR LOWER(asset_text) LIKE '%не поступ%'
            THEN 'страх / проблема'
        WHEN LOWER(asset_text) LIKE '%ielts%'
            THEN 'IELTS / язык'
        WHEN LOWER(asset_text) LIKE '%поступ%' OR LOWER(asset_text) LIKE '%вуз%'
             OR LOWER(asset_text) LIKE '%университет%'
            THEN 'поступление в ВУЗ'
        WHEN LOWER(asset_text) LIKE '%экзамен%' OR LOWER(asset_text) LIKE '%сертифик%'
            THEN 'экзамен / сертификация'
        WHEN LOWER(asset_text) LIKE '%пробн%' OR LOWER(asset_text) LIKE '%бесплатн%'
            THEN 'пробный урок / бесплатно'
        ELSE 'прочее / бренд'
    END                                                        AS theme,
    COUNT(DISTINCT asset_text)                                AS headlines_n,
    SUM(impressions)                                          AS impressions,
    SUM(clicks)                                                AS clicks,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 2) AS ctr_pct
FROM ads_creative_assets
WHERE field_type = 'HEADLINE'
GROUP BY theme
HAVING SUM(impressions) >= 500
ORDER BY ctr_pct DESC;
