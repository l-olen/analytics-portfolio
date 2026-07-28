-- ============================================================
-- Education center: audience (age/gender) and creative (RSA) analysis
-- Database: education_ads.db
-- ============================================================
-- Run: python run_sql.py sql/04_audience_creative_education.sql data/education_ads.db

-- ============================================================
-- 1. AGE: volume, CTR, conversion, cost per lead -- full period
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
-- 2. GENDER: the same breakdown
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
-- 3. AGE × MONTH: does the audience profile shift over time
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
-- 4. RSA: top headlines by volume (only ones with real traffic,
--    so CTR isn't just noise from 5 impressions)
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
-- 5. RSA: CTR by message THEME (Google's own performance_label is
--    unusable here -- it's NOT_APPLICABLE for this account, so we
--    classify by what the headline actually says)
-- ============================================================
SELECT
    CASE
        WHEN LOWER(asset_text) LIKE '%боишься%' OR LOWER(asset_text) LIKE '%не поступ%'
            THEN 'fear / problem'
        WHEN LOWER(asset_text) LIKE '%ielts%'
            THEN 'IELTS / language'
        WHEN LOWER(asset_text) LIKE '%поступ%' OR LOWER(asset_text) LIKE '%вуз%'
             OR LOWER(asset_text) LIKE '%университет%'
            THEN 'university admission'
        WHEN LOWER(asset_text) LIKE '%экзамен%' OR LOWER(asset_text) LIKE '%сертифик%'
            THEN 'exam / certification'
        WHEN LOWER(asset_text) LIKE '%пробн%' OR LOWER(asset_text) LIKE '%бесплатн%'
            THEN 'trial lesson / free'
        ELSE 'other / brand'
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
