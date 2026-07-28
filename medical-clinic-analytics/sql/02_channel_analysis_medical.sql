-- ============================================================
-- MEDICAL: Channel analysis, source funnel, trends
-- Data: crm_leads + ga4_sessions + ga4_events (medical.db)
-- Period: Jul 2025 – Jun 2026
-- ============================================================
-- PIPELINE ARCHITECTURE, FOR CONTEXT:
--   Old system (before Oct 2025): Base (10176374) = main lead stream
--   New system (from Oct 2025):  Touch/Qualification (7844402) = main lead stream
--   Base today = a bucket of rejected leads + historical leads from before Oct 2025
--   October 2025 = a break point: a mass closeout of old leads in Base
--   Analyzing the new system → filter to pipeline_id=7844402, created_at >= 2025-10-01
--
-- DATA LIMITATIONS:
--   1. Calls (the main channel): no call tracking → can't attribute to a campaign
--   2. Forms→CRM: the integration was unreliable until Dec 2025 (see Q7)
--   3. Social (Instagram/Telegram): source='other', no automatic tagging
--   Consequence: paid traffic's real contribution to appointments can't be measured
--   without call tracking

-- ─────────────────────────────────────────────────────────────
-- Q1. FUNNEL BY SOURCE — all leads (all pipelines, full period)
-- ─────────────────────────────────────────────────────────────
SELECT
    source,
    COUNT(*)                                                              AS leads,
    SUM(CASE WHEN status='won'         THEN 1 ELSE 0 END)                AS won,
    SUM(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                AS lost,
    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                AS active,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) AS cr_pct
FROM crm_leads
GROUP BY source
ORDER BY leads DESC;

/*
RESULT (Jul 2025 – Jun 2026):
  other         17371  won=4136  lost=8974  active=4261  CR=23.8%
  call           9942  won=3213  lost=4686  active=2043  CR=32.3%
  site_organic   1909  won= 266  lost=1456  active= 187  CR=13.9%
  site_paid       503  won=  30  lost= 355  active= 118  CR= 6.0%

NB: "won" here = qualified within its own pipeline (meaning depends on the pipeline).
In Base, "won" = closed (often in bulk). In Touch, "won" = ready to book.
For the real conversion rate to an appointment → see Q4.
*/

-- ─────────────────────────────────────────────────────────────
-- Q2. ANOMALY: OCTOBER 2025 — breakdown
-- ─────────────────────────────────────────────────────────────
SELECT
    pipeline_id,
    status,
    COUNT(*) leads
FROM crm_leads
WHERE strftime('%Y-%m', created_at) = '2025-10'
GROUP BY pipeline_id, status
ORDER BY pipeline_id, leads DESC;

/*
RESULT:
  pipeline=10176374 (Base) won=2929 lost=635 → mass closeout when Touch launched
  pipeline=7844402 (Touch) lost=1262 won=74 → first month of the new system
  pipeline=10176362 (Appointment) won=161 lost=18 → normal booking flow

Explanation: migrating to the new system triggered a mass closeout of old leads
in Base. October 2025 should be EXCLUDED or flagged as a migration artifact in
any summary reporting.
*/

-- ─────────────────────────────────────────────────────────────
-- Q3. FUNNEL IN TOUCH — contact level (new system)
-- Reflects real lead-processing numbers from Oct 2025 onward
-- ─────────────────────────────────────────────────────────────
WITH contacts AS (
    SELECT contact_id,
           MAX(source)                                                    AS source,
           MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)         AS won,
           MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)         AS lost,
           MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)         AS active
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
)
SELECT
    source,
    COUNT(*)                                                              AS contacts,
    SUM(won)                                                              AS qualified,
    SUM(lost)                                                             AS rejected,
    SUM(active)                                                           AS in_work,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                      AS qual_pct
FROM contacts
GROUP BY source
ORDER BY contacts DESC;

/*
RESULT (contacts in Touch since Oct 2025):
  other         3714  qualified=438  rejected=2991  in_work=305  12%
  call          1826  qualified=394  rejected=1488  in_work=  2  22%
  site_organic   638  qualified= 26  rejected= 615  in_work=  1   4%
  site_paid      360  qualified= 15  rejected= 346  in_work=  0   4%

"Qualified" in Touch = won = ready to book an appointment.
Total: 6538 contacts, 873 qualified (13.4%).
call has the best qualification rate (22%), paid web traffic the worst (4%).
*/

-- ─────────────────────────────────────────────────────────────
-- Q4. END-TO-END FUNNEL: Touch → actual appointment
-- Entry source × how many made it to pipeline 10176362 won
-- ─────────────────────────────────────────────────────────────
WITH touch_contacts AS (
    SELECT contact_id, MAX(source) AS source
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
),
had_appt AS (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id=10176362 AND status='won'
)
SELECT
    t.source,
    COUNT(DISTINCT t.contact_id)                                          AS entered,
    COUNT(DISTINCT a.contact_id)                                          AS got_appt,
    ROUND(100.0*COUNT(DISTINCT a.contact_id)/COUNT(DISTINCT t.contact_id),1) AS cr_pct
FROM touch_contacts t
LEFT JOIN had_appt a ON t.contact_id=a.contact_id
GROUP BY t.source
ORDER BY entered DESC;

/*
RESULT (end-to-end: Touch entry → actual appointment):
  other         3714  → 319 appointments  CR=8.6%
  call          1826  → 380 appointments  CR=20.8%  ← the top conversion channel
  site_organic   638  →  19 appointments  CR=3.0%
  site_paid      360  →  10 appointments  CR=2.8%

Total Touch: 6538 → 728 → CR=11.1%
NB: 'other' includes Instagram, Telegram, WhatsApp, and word-of-mouth with no tagging.
call's CR of 20.8% is the real benchmark for judging the phone channel's quality.
site_paid's CR of 2.8% is a floor: some paid leads get classified as 'other'.
*/

-- ─────────────────────────────────────────────────────────────
-- Q5. MONTHLY TREND IN TOUCH (new system, Oct 2025+)
-- ─────────────────────────────────────────────────────────────
WITH contacts AS (
    SELECT contact_id,
           strftime('%Y-%m', MIN(created_at))                             AS m,
           MAX(source)                                                    AS source,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END)                  AS won
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
)
SELECT
    m,
    COUNT(*)                                                              AS contacts,
    SUM(won)                                                              AS qualified,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                      AS qual_pct,
    SUM(CASE WHEN source='call'         THEN 1 ELSE 0 END)               AS call_n,
    SUM(CASE WHEN source='site_paid'    THEN 1 ELSE 0 END)               AS paid_n,
    SUM(CASE WHEN source='site_organic' THEN 1 ELSE 0 END)               AS organic_n,
    SUM(CASE WHEN source='other'        THEN 1 ELSE 0 END)               AS other_n
FROM contacts
GROUP BY m
ORDER BY m;

/*
RESULT:
  2025-10  1203  qual=  14  1.2%  | call=280  paid=  0  org= 53  other=870
  2025-11   484  qual=  35  7.2%  | call=218  paid=  1  org= 37  other=228
  2025-12   217  qual=  13  6.0%  | call= 68  paid=  4  org= 27  other=118
  2026-01   714  qual=  38  5.3%  | call=145  paid=  9  org=175  other=385
  2026-02   606  qual=  91 15.0%  | call=122  paid= 14  org= 30  other=440
  2026-03   600  qual=  82 13.7%  | call=138  paid= 11  org= 40  other=411
  2026-04   510  qual= 161 31.6%  | call=211  paid= 12  org= 41  other=246
  2026-05   841  qual= 253 30.1%  | call=327  paid= 51  org= 45  other=418
  2026-06  1363  qual= 186 13.6%  | call=317  paid=258  org=190  other=598

TRENDS:
- Oct 2025: first month, most leads still "in progress" → CR=1.2% (artifact)
- Nov–Jan: CR 5-7%, normal ramp-up of the new system
- Feb–May 2026: CR 13-32% — stable steady state
- Apr–May: CR 30%+ — peak (seasonality? promotions?)
- Jun 2026: CR drops to 14% while volume is +62% → the new site brought in
  more low-quality leads; site_paid = 258 (5x April) — the new site's form
  went live 06-23
*/

-- ─────────────────────────────────────────────────────────────
-- Q6. GA4 CHANNELS — sessions and conversions (12 months)
-- ─────────────────────────────────────────────────────────────
SELECT
    channel,
    SUM(sessions)                                                         AS sessions,
    ROUND(SUM(conversions))                                               AS conversions,
    ROUND(100.0*SUM(conversions)/SUM(sessions),2)                         AS cr_pct
FROM ga4_sessions
GROUP BY channel
ORDER BY sessions DESC;

/*
RESULT:
  Cross-network   49230  conv=4034  CR=8.2%  ← PMax campaigns
  Organic Search  22035  conv= 303  CR=1.4%
  Paid Search     14673  conv=1497  CR=10.2% ← standard search
  Direct           7068  conv= 271  CR=3.8%
  Organic Social   3270  conv=  23  CR=0.7%
  Display           702  conv=   9  CR=1.3%

GA4 "conversions" here = click_number (4610), form_call_submit (353), and other
key events. The clinic's primary conversion is click_number (a tap on the phone
number) = 90% of all conversions. Cross-network's 8.2% CR vs Paid Search's 10.2%
puts the two campaign types roughly on par.
*/

-- ─────────────────────────────────────────────────────────────
-- Q7. GA4 PAID SESSIONS vs CRM site_paid LEADS — by month
-- Shows the scale of the gap: how many paid sessions never make it to CRM
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', g.date)                                             AS month,
    SUM(CASE WHEN g.channel IN ('Cross-network','Paid Search')
        THEN g.sessions ELSE 0 END)                                       AS ga4_paid_sessions,
    ROUND(SUM(CASE WHEN g.channel IN ('Cross-network','Paid Search')
        THEN g.conversions ELSE 0 END))                                   AS ga4_paid_conv
FROM ga4_sessions g
GROUP BY month
ORDER BY month;

-- CRM site_paid by month (compared against the above manually/in Python):
SELECT
    strftime('%Y-%m', created_at)                                         AS month,
    COUNT(*)                                                              AS crm_site_paid
FROM crm_leads
WHERE source='site_paid'
GROUP BY month
ORDER BY month;

/*
COMPARISON (GA4 paid conversions vs CRM site_paid leads):
  2025-07: GA4=526 | CRM=0   ← form-to-CRM integration wasn't working yet
  2025-08: GA4=599 | CRM=0
  2025-09: GA4=668 | CRM=0
  2025-10: GA4=276 | CRM=0
  2025-11: GA4=379 | CRM=1
  2025-12: GA4=408 | CRM=8   ← integration comes online
  2026-01: GA4=686 | CRM=24  ← GA4 is 28x higher (calls + forms vs CRM forms only)
  2026-02: GA4=476 | CRM=37
  2026-03: GA4=480 | CRM=22
  2026-04: GA4=120 | CRM=25
  2026-05: GA4=517 | CRM=64
  2026-06: GA4=396 | CRM=322 ← new site: the form works, the gap nearly closes

GA4 "conversions" ≠ CRM leads: most GA4 conversions are phone-number clicks
(calls), which land in CRM as source='call', not 'site_paid'. This explains
the persistent gap.
*/

-- ─────────────────────────────────────────────────────────────
-- Q8. GA4 CONVERSION EVENTS (paid vs organic)
-- ─────────────────────────────────────────────────────────────
SELECT
    event_label,
    SUM(total)                                                            AS total,
    SUM(paid)                                                             AS paid,
    ROUND(100.0*SUM(paid)/SUM(total),1)                                   AS paid_share_pct
FROM ga4_events
GROUP BY event_label
ORDER BY total DESC;

/*
RESULT:
  click_number              5066   4613   91%  ← the main "conversion" is a phone tap
  form_call_submit           353    315   89%  ← old form, before the new site
  form_start                  62     56   90%
  form_appointment_side_submit 23    23  100%  ← new form (since 2026-06-23)
  form_submit                 16     16  100%
  click_instagram              7      7  100%

Paid traffic drives 91% of phone-number clicks and 89% of form submissions.
Total paid forms: 315 + 23 + 16 = 354 over the year — comparable to CRM's
site_paid count (503). The clinic's main conversion tool is the PHONE CALL,
not the form. Without call tracking, paid traffic's real ROI can't be measured.
*/

-- ─────────────────────────────────────────────────────────────
-- Q9. SUMMARY — for a stakeholder discussion
-- ─────────────────────────────────────────────────────────────
/*
CHANNEL FUNNEL (new system, Oct 2025 – Jun 2026):

                Entered  → Qualified → Appt     | Qual CR  Appt CR
  call          1826     →  394     →  380      | 22%      20.8%
  other         3714     →  438     →  319      | 12%       8.6%
  site_paid      360     →   15     →   10      |  4%       2.8%
  site_organic   638     →   26     →   19      |  4%       3.0%
  TOTAL         6538     →  873     →  728      | 13%      11.1%

KEY TAKEAWAYS:
1. Calls are the best channel (CR 20.8%), but without call tracking we don't
   know which campaign drove them.
2. 'other' (57% of all volume) is social/messengers. An 8.6% CR is a solid
   result, but it can't be broken down into Instagram/Telegram/WhatsApp
   without automatic tagging.
3. Paid web traffic (site_paid): a 2.8% CR is a floor. The real number is
   higher, since some paid leads call in and land under 'call' instead.
4. June 2026: the new site brought in 5x more site_paid leads, and Touch's
   CR dropped (more unqualified form leads) — normal for a first month, but
   worth monitoring.

WHAT TO FIX (in priority order):
1. Call tracking (Calltouch/CoMagic) — would unlock attribution for 90% of
   conversions
2. Automatic tagging for Instagram/Telegram — would break down 'other'
3. UTM→CRM on the new site — already being monitored (the form was fixed
   on 2026-06-23)
*/
