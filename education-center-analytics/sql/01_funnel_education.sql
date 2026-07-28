-- ============================================================
-- Education center: funnel and attribution
-- Database: education.db  |  Leads: Nov 2023 – Jul 2026
-- ============================================================
-- ATTACH DATABASE 'data/education.db' AS b;  -- when running from medical.db
-- Or simply: sqlite3 data/education.db < sql/01_funnel_education.sql

-- ============================================================
-- 0. PIPELINE AND STAGE REFERENCE
-- ============================================================
-- Automated pipelines (where bot detection runs):
--   7599026  Call center
--   7378970  Sales Department
--   7456518  Follow-up
--  10481938  Administration
--  10486794  Archive leads 2024-01-01 to 2025-12-31
--
-- Manual pipelines (no bots, data entered by staff):
--   7693206  Uzbekistan pipeline
--   7645546  Online pipeline
--   8152890  Upsells
--   8254930  Correspondence
--   8928070  DTM test base
--   9587506  Consulting
--   9685134  2025 University Fair
--  10034018  Thomson leads
--
-- Statuses: 142 = won, 143 = closed/lost


-- ============================================================
-- 1. OVERALL FUNNEL (excluding bots)
-- ============================================================
SELECT
    COUNT(*)                                              AS total_leads,
    SUM(CASE WHEN status = 'won'  THEN 1 ELSE 0 END)     AS won,
    SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END)     AS lost,
    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
    ROUND(100.0 * SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0;


-- ============================================================
-- 2. FUNNEL BY PIPELINE TYPE: automated vs manual
-- ============================================================
SELECT
    CASE
        WHEN pipeline_id IN (7599026,7378970,7456518,10481938,10486794)
            THEN 'automated'
        ELSE 'manual'
    END AS pipeline_type,
    COUNT(*)  AS total,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
GROUP BY pipeline_type;


-- ============================================================
-- 3. FUNNEL BY LEAD SOURCE (tag classification)
-- ============================================================
SELECT
    source,
    COUNT(*)  AS total,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
GROUP BY source
ORDER BY total DESC;


-- ============================================================
-- 4. ATTRIBUTION: FUNNEL BY UTM SOURCE
-- (only leads with utm_source, i.e. leads from online ads)
-- ============================================================
SELECT
    utm_source,
    utm_medium,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND utm_source IS NOT NULL
  AND utm_source NOT IN ('UTM Medium:','utm_medium:','test')  -- filters out junk values
GROUP BY utm_source, utm_medium
ORDER BY leads DESC;


-- ============================================================
-- 5. TOP CAMPAIGNS BY VOLUME AND CR
-- ============================================================
SELECT
    utm_source,
    utm_campaign,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
  AND utm_campaign IS NOT NULL
  AND utm_source NOT IN ('UTM Medium:','utm_medium:','test')
  AND utm_campaign NOT IN ('UTM Content:','UTM Term:')
GROUP BY utm_source, utm_campaign
HAVING leads >= 30
ORDER BY leads DESC
LIMIT 25;


-- ============================================================
-- 6. FUNNEL BY PRODUCT
-- ============================================================
SELECT
    product,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND product IS NOT NULL
GROUP BY product
ORDER BY leads DESC
LIMIT 20;


-- ============================================================
-- 7. FUNNEL BY GRADE / COURSE
-- ============================================================
SELECT
    grade_or_course AS grade,
    COUNT(*)     AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND grade_or_course IS NOT NULL
GROUP BY grade_or_course
ORDER BY leads DESC;


-- ============================================================
-- 8. ABC SEGMENTATION: distribution and conversion
-- ============================================================
SELECT
    abc_category,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN price > 0     THEN 1 ELSE 0 END) AS with_price,
    ROUND(AVG(CASE WHEN price > 0 THEN price END), 0) AS avg_price,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND abc_category IS NOT NULL
GROUP BY abc_category
ORDER BY leads DESC;


-- ============================================================
-- 9. MONTHLY TREND: lead volume and CR
-- ============================================================
SELECT
    substr(created_date, 1, 7)                           AS month,
    COUNT(*)                                              AS total,
    SUM(CASE WHEN is_bot=1  THEN 1 ELSE 0 END)           AS bots,
    SUM(CASE WHEN is_bot=0  THEN 1 ELSE 0 END)           AS clean,
    SUM(CASE WHEN is_bot=0 AND status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN is_bot=0 AND status='won' THEN 1 ELSE 0 END)
               / NULLIF(SUM(CASE WHEN is_bot=0 THEN 1 ELSE 0 END),0), 2) AS cr_pct
FROM crm_leads
GROUP BY month
ORDER BY month;


-- ============================================================
-- 10. ATTRIBUTION: utm_source × product — channel intersection
-- ============================================================
SELECT
    utm_source,
    product,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
  AND utm_source IS NOT NULL AND utm_source NOT IN ('UTM Medium:','test')
  AND product IS NOT NULL
GROUP BY utm_source, product
HAVING leads >= 10
ORDER BY utm_source, leads DESC;


-- ============================================================
-- 11. INSTRUCTION LANGUAGE × SOURCE — Uzbek/Russian audience segmentation
-- ============================================================
SELECT
    instruction_language AS language,
    utm_source,
    COUNT(*)     AS leads,
    SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND instruction_language IS NOT NULL
GROUP BY instruction_language, utm_source
ORDER BY instruction_language, leads DESC;


-- ============================================================
-- CHANNEL CLASSIFICATION (shared logic)
-- ============================================================
-- Source classification rules (in the ETL):
--   site_quiz  = tags: "квиз" (quiz), "сайт квиз" (site quiz)
--   site_web   = tags: "заказ с сайта" (site order), "Сайт" (site), "tilda"  <- "Сайт" and "tilda" added later
--   call       = tags: "555100400", "входящий" (inbound), "пропущенный" (missed), + an extra call-widget tag
--   other      = everything else
--
-- Channel logic at the lead level:
--   UTM/click-id takes priority over the source tag.
--   yclid = Yandex web traffic (both paid and organic).
--   To split Yandex paid vs organic, use utm_medium='cpc'.
--   gclid is rarely populated -- rely on utm_source/utm_medium instead.
--   Campaign prefixes fk_ and km_ -- same agency, different structuring periods.

-- 12. CR BY CHANNEL (at lead level, as a volume reference)
WITH channel_classified AS (
    SELECT *,
        CASE
            WHEN yclid IS NOT NULL
              OR utm_source = 'yandex' OR utm_source = 'yd'    THEN 'yandex_web'
            WHEN utm_source = 'google' AND utm_medium = 'cpc'
              OR gclid IS NOT NULL                              THEN 'paid_google'
            WHEN fbclid IS NOT NULL
              OR utm_source IN ('FB','fb','ig')                 THEN 'paid_social'
            WHEN utm_source = 'telegram'                        THEN 'telegram'
            WHEN utm_source = 'chatgpt.com'                     THEN 'chatgpt_ref'
            WHEN source IN ('site_quiz','site_web')             THEN 'organic_web'
            WHEN source = 'call'                                THEN 'inbound_call'
            ELSE 'other'
        END AS channel
    FROM crm_leads WHERE is_bot = 0
)
SELECT channel,
       COUNT(*) AS leads,
       SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won,
       ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM channel_classified
GROUP BY channel ORDER BY leads DESC;


-- 13. CONTACT-LEVEL ATTRIBUTION (with UTM carry-over)
-- For each contact, we gather the UTM signals from ALL of their leads.
-- If any of the contact's leads carries a UTM tag, the win is credited to that channel,
-- even if the deal itself closed as a call.
-- Priority: google > yandex > social > telegram > chatgpt > the first lead's tag.
WITH contact_signals AS (
    SELECT contact_id,
           MAX(CASE WHEN utm_source='google' AND utm_medium='cpc'
                     OR gclid IS NOT NULL                       THEN 1 ELSE 0 END) sig_google,
           MAX(CASE WHEN yclid IS NOT NULL
                     OR utm_source IN ('yandex','yd')           THEN 1 ELSE 0 END) sig_yandex,
           MAX(CASE WHEN fbclid IS NOT NULL
                     OR utm_source IN ('FB','fb','ig')          THEN 1 ELSE 0 END) sig_social,
           MAX(CASE WHEN utm_source='telegram'                  THEN 1 ELSE 0 END) sig_telegram,
           MAX(CASE WHEN utm_source='chatgpt.com'               THEN 1 ELSE 0 END) sig_chatgpt,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END)        ever_won
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
),
first_tag AS (
    SELECT contact_id,
           FIRST_VALUE(source) OVER (
               PARTITION BY contact_id ORDER BY created_at ASC, lead_id ASC
           ) AS ft_source
    FROM crm_leads WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT
    CASE
        WHEN cs.sig_google   = 1 THEN 'paid_google'
        WHEN cs.sig_yandex   = 1 THEN 'yandex_web'
        WHEN cs.sig_social   = 1 THEN 'paid_social'
        WHEN cs.sig_telegram = 1 THEN 'telegram'
        WHEN cs.sig_chatgpt  = 1 THEN 'chatgpt_ref'
        ELSE COALESCE(ft.ft_source, 'other')
    END AS attributed_channel,
    COUNT(*)      AS contacts,
    SUM(cs.ever_won) AS won,
    ROUND(100.0*SUM(cs.ever_won)/COUNT(*),2) AS cr_pct
FROM contact_signals cs
LEFT JOIN first_tag ft ON ft.contact_id = cs.contact_id
GROUP BY attributed_channel ORDER BY contacts DESC;


-- 14. TOP CAMPAIGNS (contact-level attribution)
-- fk_ and km_ prefixes = same agency, merge them during analysis.
WITH contact_campaigns AS (
    SELECT contact_id,
           MAX(CASE WHEN utm_source IS NOT NULL
                     AND utm_source NOT IN ('UTM Medium:','test')
                THEN utm_source END) AS best_source,
           MAX(CASE WHEN utm_campaign IS NOT NULL
                     AND utm_campaign NOT IN ('UTM Content:','UTM Term:')
                THEN utm_campaign END) AS best_campaign,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END) AS ever_won
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT best_source, best_campaign,
       COUNT(*) AS contacts,
       SUM(ever_won) AS won,
       ROUND(100.0*SUM(ever_won)/COUNT(*),2) AS cr_pct
FROM contact_campaigns
WHERE best_campaign IS NOT NULL
GROUP BY best_source, best_campaign
HAVING contacts >= 20
ORDER BY contacts DESC LIMIT 25;


-- 15. DARK FUNNEL: UTM coverage of won contacts
-- 96.8% of won contacts carry no UTM tag at all.
-- Structural reasons (not tracking bugs):
--   Archive (29k leads, Nov'23-Dec'25) -- UTM tracking wasn't set up yet
--   Upsells -- upselling existing students, UTM isn't relevant
--   DTM test base / Consulting / Fair -- manual channels
--   Administration -- child leads, UTM is lost when deals are "copied"
WITH contact_utm AS (
    SELECT contact_id,
           MAX(CASE WHEN utm_source IS NOT NULL
                     AND utm_source NOT IN ('UTM Medium:','test')
                THEN 1 ELSE 0 END) AS has_any_utm,
           MAX(CASE WHEN yclid IS NOT NULL OR gclid IS NOT NULL OR fbclid IS NOT NULL
                THEN 1 ELSE 0 END) AS has_click_id,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END) AS ever_won
    FROM crm_leads WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT
    COUNT(*)                                   AS total_contacts,
    SUM(ever_won)                              AS won_contacts,
    SUM((has_any_utm + has_click_id > 0) * ever_won) AS won_with_utm,
    SUM((has_any_utm + has_click_id = 0) * ever_won) AS won_dark,
    ROUND(100.0*SUM((has_any_utm+has_click_id>0)*ever_won)/NULLIF(SUM(ever_won),0),1)
        AS pct_attributed,
    ROUND(100.0*SUM((has_any_utm+has_click_id=0)*ever_won)/NULLIF(SUM(ever_won),0),1)
        AS pct_dark
FROM contact_utm;


-- ============================================================
-- SUMMARY (for the case write-up)
-- ============================================================
-- Database: ~51,900 leads (Nov 2023 - Jul 2026), ~1,248 bots (2.4%)
-- Clean contacts: ~47,100 unique, 2,802 won (CR 6.6%)
--
-- + CR by channel (first-touch with UTM carry-over):
--     inbound_call 13% > telegram 8.2% > yandex_web 3.4% > paid_social 2.7%
--     > paid_google 2.2% > site_web 1.4% > chatgpt_ref 1.1%
-- + CR by product: law 29% / history 29% / math 21% / English 19%
-- + CR by grade: grade 11 is the main audience (5,384 leads)
-- + Volume and conversion trend by month (Q9)
-- + ABC segmentation (A=3k, B=2.5k, C=1.8k leads)
--
-- KEY FINDING 1 -- the attribution dark funnel:
--   96.8% of won contacts carry no UTM tag.
--   Structural reasons:
--     Archive (1389 wins) -- historical data from before UTM tracking existed
--     DTM test base (398) + Consulting (111) -- manual channels, UTM isn't relevant
--     Upsells (259) -- upselling existing students
--     Call center (472) -- direct calls with no online touchpoint
--     Administration (287) -- most leads are created directly, not through
--       an online form; "copying deals" copies UTM correctly, but only
--       when the source lead came from the site (~10 of 784 in Administration).
--   What's fixable: passing gclid/fbclid through hidden quiz fields,
--   systematic contact merging when a call follows an online submission.
--
-- KEY FINDING 2 -- the web-to-call attribution gap:
--   2,622 of 2,625 Google contacts: UTM is on the web lead, the conversion is on a call.
--   Without carrying the UTM over, these contacts look like "other" with a 9% CR.
--   After carrying it over: paid_google CR = 2.2%, the real paid CR.
--
-- KEY FINDING 3 -- yclid covers all of Yandex (paid + organic):
--   yclid is set on all Yandex traffic, not just paid.
--   To split it out: utm_medium='cpc' -> paid (833 leads, CR 2.4%)
--                   without cpc -> organic/direct Yandex (1,216 leads, CR 2.8%)
--   The CR is nearly identical -- Yandex organic performs no worse than paid.
--
-- RECOMMENDATIONS:
--   1. Pass gclid/fbclid through hidden quiz/form fields
--   2. Set up automatic contact merging by phone number
--   3. Set up UTM pass-through in Administration when deals are "copied"
--   4. gclientid (GA4 Client ID) is present on 2,021 leads -- a potential
--      bridge to GA4 data via BigQuery export
--
-- KEY FINDING 4 -- Call center before 2026 is empty, history lives in the Archive:
--   Before January 2026 all inbound leads went into "Archive leads 2024-01-01 to 2025-12-31"
--   (29,365 leads, Dec 2023 - Dec 2025). Call center launched as the main
--   pipeline from Jan 2026. The trend inside CC only reflects data from Jan 2026 on.
--
-- KEY FINDING 5 -- Instagram and Telegram convert through chat, not calls:
--   Instagram: 2,457 leads (2026), 88.7% carry no call tag (Inbound/Outbound).
--   But when a call does happen -> CR 30-63% (vs 6.7% on average).
--   80 wins with no tag = conversions through DMs, no call.
--   Telegram: 432 leads, CR 26.9%. 84.7% carry no call tag.
--   100 wins with no tag = converted through Telegram chat.
--   Takeaway: the "Inbound/Outbound" tags don't capture every touchpoint.
--   "No tag" can't be read as "no work was done on this lead".
--
-- What would require additional ETL work:
--   - Stage-by-stage movement (time spent per stage, where contacts drop off)
--   -> etl_events_education.py -> crm_lead_events
--     ~125k-250k events, ~15 min to load

-- ============================================================
-- Q16: CALL CENTER 2026 -- CHANNEL x STAFF ACTION x STATUS
-- Channel source: crm_source (field 534651, entered manually by staff)
-- Action tag: Inbound/Outbound/No answer/Missed
-- ============================================================

WITH cc AS (
    SELECT *,
        CASE
            WHEN crm_source IN ('инстаграм')              THEN 'Instagram'
            WHEN crm_source IN ('телеграм','телеграм(и)') THEN 'Telegram'
            WHEN crm_source = 'фейсбук'                   THEN 'Facebook'
            WHEN crm_source = 'сарафанное радио'           THEN 'Word of mouth'
            WHEN crm_source = 'наш ученик'                 THEN 'Referral'
            WHEN crm_source = 'дтм тест'                   THEN 'DTM test'
            WHEN crm_source = 'сайт'
                 OR source IN ('site_quiz','site_web')     THEN 'Site/Quiz'
            WHEN utm_source = 'google' AND utm_medium='cpc' THEN 'Google Ads'
            WHEN yclid IS NOT NULL OR utm_source IN ('yandex','yd') THEN 'Yandex'
            WHEN utm_source = 'chatgpt.com'                THEN 'ChatGPT'
            ELSE 'Unclassified'
        END ch,
        CASE
            WHEN tags LIKE '%Входящий%'    THEN 'Inbound call'
            WHEN tags LIKE '%Исходящий%'   THEN 'Outbound call'
            WHEN tags LIKE '%Клиент не%'   THEN 'No answer'
            WHEN tags LIKE '%Пропущенный%' THEN 'Missed'
            WHEN tags IS NULL OR tags = '' THEN 'No action'
            ELSE 'Other'
        END operator_action
    FROM crm_leads
    WHERE pipeline_id = 7599026
      AND is_bot = 0
      AND created_at >= '2026-01-01'
)
SELECT ch,
       operator_action,
       COUNT(*) n,
       SUM(CASE WHEN status='won'         THEN 1 ELSE 0 END) won,
       SUM(CASE WHEN status='lost'        THEN 1 ELSE 0 END) lost,
       SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) active,
       ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) cr_pct
FROM cc
GROUP BY ch, operator_action
ORDER BY ch, n DESC;

-- ============================================================
-- Q17: CALL CENTER 2026 -- SUMMARY BY CHANNEL
-- % "No action" -- leads with no call tag (the conversion may have happened via chat)
-- ============================================================

WITH cc AS (
    SELECT *,
        CASE
            WHEN crm_source IN ('инстаграм')              THEN 'Instagram'
            WHEN crm_source IN ('телеграм','телеграм(и)') THEN 'Telegram'
            WHEN crm_source = 'фейсбук'                   THEN 'Facebook'
            WHEN crm_source = 'сарафанное радио'           THEN 'Word of mouth'
            WHEN crm_source = 'наш ученик'                 THEN 'Referral'
            WHEN crm_source = 'дтм тест'                   THEN 'DTM test'
            WHEN crm_source = 'сайт'
                 OR source IN ('site_quiz','site_web')     THEN 'Site/Quiz'
            WHEN utm_source = 'google' AND utm_medium='cpc' THEN 'Google Ads'
            WHEN yclid IS NOT NULL OR utm_source IN ('yandex','yd') THEN 'Yandex'
            WHEN utm_source = 'chatgpt.com'                THEN 'ChatGPT'
            ELSE 'Unclassified'
        END ch
    FROM crm_leads
    WHERE pipeline_id = 7599026
      AND is_bot = 0
      AND created_at >= '2026-01-01'
)
SELECT ch,
       COUNT(*) total_leads,
       SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) won,
       ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) cr_pct,
       SUM(CASE WHEN tags IS NULL OR tags='' THEN 1 ELSE 0 END) no_phone_tag,
       ROUND(100.0*SUM(CASE WHEN tags IS NULL OR tags='' THEN 1 ELSE 0 END)/COUNT(*),1) pct_no_tag,
       SUM(CASE WHEN tags LIKE '%Клиент не%' THEN 1 ELSE 0 END) no_answer
FROM cc
GROUP BY ch
ORDER BY total_leads DESC;

-- ============================================================
-- Q18: THREE-SEGMENT CONTACT CLASSIFICATION (all pipelines, 2026)
--
-- Segment 1 -- WEB: the contact has at least one lead tagged "Сайт" (site) / "Сайт Квиз" (site quiz)
--   UTM attribution within it: Google Ads / Yandex paid / Yandex organic / Organic
--   Limitation: Yandex paid vs organic can't be split without utm_medium='cpc'
--
-- Segment 2 -- CALL (pure): tagged "Inbound" / "Missed",
--   BUT this contact has no lead tagged "Сайт" (site)
--
-- Segment 3 -- SOCIAL/MANUAL: everything else.
--   crm_source (field 534651, entered manually by staff) is the best signal available.
--   Caveat: staff can mark a lead "word of mouth" even if it has a UTM tag -- that's noise,
--   but only leads with no site tags and no UTM land in this group, i.e. definitely not web.
-- ============================================================

WITH cs AS (
    SELECT
        contact_id,
        MAX(CASE WHEN tags LIKE '%Сайт%' THEN 1 ELSE 0 END)                          has_web,
        MAX(CASE WHEN (tags LIKE '%Входящий%' OR tags LIKE '%Пропущенный%')
                  AND tags NOT LIKE '%Сайт%' THEN 1 ELSE 0 END)                      has_pure_call,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND utm_source='google' AND utm_medium='cpc' THEN 1 ELSE 0 END)    web_google,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                  AND utm_medium='cpc' THEN 1 ELSE 0 END)                            web_yd_paid,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                  THEN 1 ELSE 0 END)                                                 web_yd_any,
        MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)                        won,
        MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                        lost,
        MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                        active,
        MAX(crm_source)                                                               crm_source_any,
        MIN(created_at)                                                               first_lead
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2026-01-01'      -- new contacts from 2026 only
),
classified AS (
    SELECT *,
        CASE
            WHEN has_web=1 AND web_google=1  THEN 'Web → Google Ads'
            WHEN has_web=1 AND web_yd_paid=1 THEN 'Web → Yandex Paid'
            WHEN has_web=1 AND web_yd_any=1  THEN 'Web → Yandex (organic/unknown)'
            WHEN has_web=1                   THEN 'Web → Organic/Untagged'
            WHEN has_pure_call=1             THEN 'Call (pure)'
            WHEN crm_source_any IN ('инстаграм')               THEN 'Social → Instagram'
            WHEN crm_source_any IN ('телеграм','телеграм(и)')  THEN 'Social → Telegram'
            WHEN crm_source_any = 'фейсбук'                    THEN 'Social → Facebook'
            WHEN crm_source_any = 'сарафанное радио'           THEN 'Referral → Word of mouth'
            WHEN crm_source_any IN ('наш ученик')              THEN 'Referral → Recommendation'
            WHEN crm_source_any = 'дтм тест'                   THEN 'DTM test'
            ELSE 'Manual/Unclassified'
        END segment
    FROM cs
)
SELECT
    segment,
    COUNT(*)                                                                 contacts,
    SUM(won)                                                                 won,
    SUM(lost)                                                                lost,
    SUM(active)                                                              active,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                         cr_pct,
    ROUND(100.0*SUM(lost)/COUNT(*),1)                                        lost_pct
FROM classified
GROUP BY segment
ORDER BY contacts DESC;

-- ============================================================
-- Q19: WEB -- QUIZ vs CONTACT FORM x UTM CHANNEL
-- Contacts tagged "Сайт Квиз" (site quiz) vs "Сайт" (site, no quiz) x paid/organic
-- ============================================================

WITH cw AS (
    SELECT
        contact_id,
        MAX(CASE WHEN tags LIKE '%Сайт Квиз%'                             THEN 1 ELSE 0 END) is_quiz,
        MAX(CASE WHEN tags LIKE '%Сайт%' AND tags NOT LIKE '%Сайт Квиз%' THEN 1 ELSE 0 END) is_form,
        MAX(CASE WHEN utm_source='google' AND utm_medium='cpc'            THEN 1 ELSE 0 END) g,
        MAX(CASE WHEN (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                  AND utm_medium='cpc'                                     THEN 1 ELSE 0 END) yd_paid,
        MAX(CASE WHEN yclid IS NOT NULL OR utm_source IN ('yandex','yd') THEN 1 ELSE 0 END) yd_any,
        MAX(CASE WHEN status='won'  THEN 1 ELSE 0 END) won,
        MAX(CASE WHEN status='lost' THEN 1 ELSE 0 END) lost
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL AND tags LIKE '%Сайт%'
    GROUP BY contact_id
)
SELECT
    CASE
        WHEN is_form=1 AND is_quiz=0 AND g=1      THEN 'Form → Google Ads'
        WHEN is_form=1 AND is_quiz=0 AND yd_paid=1 THEN 'Form → Yandex Paid'
        WHEN is_form=1 AND is_quiz=0 AND yd_any=1 THEN 'Form → Yandex (organic)'
        WHEN is_form=1 AND is_quiz=0               THEN 'Form → Organic/Untagged'
        WHEN is_quiz=1 AND is_form=0 AND g=1      THEN 'Quiz → Google Ads'
        WHEN is_quiz=1 AND is_form=0 AND yd_paid=1 THEN 'Quiz → Yandex Paid'
        WHEN is_quiz=1 AND is_form=0 AND yd_any=1 THEN 'Quiz → Yandex (organic)'
        WHEN is_quiz=1 AND is_form=0               THEN 'Quiz → Organic/Untagged'
        ELSE 'Form + Quiz (both tags)'
    END sub_channel,
    COUNT(*)                                       contacts,
    SUM(won)                                       won,
    SUM(lost)                                      lost,
    ROUND(100.0*SUM(won)/COUNT(*),1)               cr_pct
FROM cw
GROUP BY sub_channel
ORDER BY contacts DESC;

-- ============================================================
-- Q20-Q22: 12-MONTH ANALYSIS (Jul 2025 - Jun 2026)
-- Source: ALL pipelines (Archive + Call Center + others)
-- A contact is included based on their first lead's date within the period
--
-- Archive (10486794): Dec 2023 - Dec 2025, crm_source filled for 78% of leads
-- Call center (7599026): from Jan 2026, crm_source filled for ~60% of leads
-- Shared channel classification: tags -> UTM -> crm_source
-- ============================================================

-- The shared contacts CTE -- used across all three queries below
-- ATTACH DATABASE 'data/education_ads.db' AS ads;   -- needed for Q22

-- ============================================================
-- Q20: FUNNEL BY CHANNEL -- 12 MONTHS
-- ============================================================

WITH all_contacts AS (
    SELECT contact_id,
        MIN(created_at)                                                      first_lead,
        strftime('%Y-%m', MIN(created_at))                                   first_month,
        MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)                ever_won,
        MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                ever_lost,
        MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                ever_active,
        MAX(CASE WHEN tags LIKE '%Сайт%'   THEN 1 ELSE 0 END)                has_web,
        MAX(CASE WHEN tags LIKE '%Сайт%' AND utm_source='google'
                  AND utm_medium='cpc'                         THEN 1 ELSE 0 END) web_google,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                                                               THEN 1 ELSE 0 END) web_yd,
        MAX(CASE WHEN (tags LIKE '%Входящий%' OR tags LIKE '%Пропущенный%')
                  AND tags NOT LIKE '%Сайт%'                   THEN 1 ELSE 0 END) has_call,
        MAX(crm_source)                                                      crm_src
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-07-01'
       AND MIN(created_at) <  '2026-07-01'
),
classified AS (
    SELECT *,
        CASE
            WHEN has_web=1 AND web_google=1   THEN 'Google Ads (web)'
            WHEN has_web=1 AND web_yd=1       THEN 'Yandex (web)'
            WHEN has_web=1                    THEN 'Organic / untagged (web)'
            WHEN has_call=1                   THEN 'Inbound calls'
            WHEN crm_src IN ('инстаграм')     THEN 'Instagram'
            WHEN crm_src IN ('телеграм','телеграм(и)') THEN 'Telegram'
            WHEN crm_src = 'фейсбук'          THEN 'Facebook'
            WHEN crm_src = 'сарафанное радио' THEN 'Word of mouth'
            WHEN crm_src IN ('наш ученик')    THEN 'Referral'
            WHEN crm_src = 'наружная реклама' THEN 'Outdoor advertising'
            WHEN crm_src IN ('дтм тест','рассылка дтм') THEN 'DTM test'
            ELSE 'Unclassified'
        END channel
    FROM all_contacts
)
SELECT channel,
       COUNT(*)                                    contacts,
       SUM(ever_won)                               won,
       ROUND(100.0*SUM(ever_won)/COUNT(*),1)       cr_pct,
       SUM(ever_lost)                              lost,
       SUM(ever_active)                            active
FROM classified
GROUP BY channel
ORDER BY contacts DESC;

-- ============================================================
-- Q21: MONTHLY TREND -- 12 MONTHS
-- Contacts + CR + Google Ads spend + Google leads from CRM
-- Note: the Google Ads figures require ATTACH-ing the ads database
-- ============================================================

WITH all_contacts AS (
    SELECT contact_id,
        strftime('%Y-%m', MIN(created_at)) first_month,
        MAX(CASE WHEN status='won' THEN 1 ELSE 0 END) ever_won
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-07-01'
       AND MIN(created_at) <  '2026-07-01'
),
monthly_crm AS (
    SELECT first_month m, COUNT(*) contacts, SUM(ever_won) won
    FROM all_contacts GROUP BY first_month
),
monthly_ads AS (
    SELECT strftime('%Y-%m', date) m,
           ROUND(SUM(cost_micros)/1e6,0) spend
    FROM ads.ads_campaigns
    WHERE date >= '2025-07-01' AND date < '2026-07-01'
    GROUP BY m
),
monthly_gleads AS (
    SELECT strftime('%Y-%m', created_at) m, COUNT(*) gleads
    FROM crm_leads
    WHERE is_bot=0 AND created_at >= '2025-07-01' AND created_at < '2026-07-01'
      AND utm_source='google' AND utm_medium='cpc'
    GROUP BY m
)
SELECT c.m,
       c.contacts,
       c.won,
       ROUND(100.0*c.won/c.contacts,1)             cr_pct,
       COALESCE(a.spend,0)                         ga_spend_usd,
       COALESCE(g.gleads,0)                        google_crm_leads,
       CASE WHEN COALESCE(g.gleads,0)>0
            THEN ROUND(COALESCE(a.spend,0)/g.gleads,1) END cpl_usd
FROM monthly_crm c
LEFT JOIN monthly_ads  a ON a.m=c.m
LEFT JOIN monthly_gleads g ON g.m=c.m
ORDER BY c.m;

-- ============================================================
-- Q22: GOOGLE ADS -- SPEND x CRM LEADS x CPL (12 MONTHS)
-- Matched via campaign_id embedded in utm_campaign ('|cid|12345')
-- Campaigns without |cid| (e.g. fk_sert_pmax) won't appear in the join
-- ============================================================

WITH crm_by_cid AS (
    SELECT
        CAST(SUBSTR(utm_campaign, INSTR(utm_campaign,'|cid|')+5) AS INTEGER) cid,
        COUNT(*) leads,
        SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) won
    FROM crm_leads
    WHERE is_bot=0 AND created_at >= '2025-07-01' AND created_at < '2026-07-01'
      AND utm_source='google' AND utm_campaign LIKE '%|cid|%'
    GROUP BY cid
),
ads_agg AS (
    SELECT campaign_id, campaign_name,
           ROUND(SUM(cost_micros)/1e6,1) spend,
           SUM(clicks) clicks,
           SUM(conversions) ga_conv
    FROM ads.ads_campaigns
    WHERE date >= '2025-07-01' AND date < '2026-07-01'
    GROUP BY campaign_id, campaign_name
)
SELECT a.campaign_name,
       a.spend                                     spend_usd,
       a.clicks,
       a.ga_conv                                   ga_conversions,
       COALESCE(c.leads,0)                         crm_leads,
       COALESCE(c.won,0)                           won,
       CASE WHEN COALESCE(c.leads,0)>0
            THEN ROUND(a.spend/c.leads,1) END      cpl_usd,
       CASE WHEN COALESCE(c.won,0)>0
            THEN ROUND(a.spend/c.won,0)  END       cpa_usd
FROM ads_agg a
LEFT JOIN crm_by_cid c ON c.cid=a.campaign_id
WHERE a.spend > 1
ORDER BY a.spend DESC;
