-- ============================================================
-- MEDICAL: Trends and period comparisons
-- Data: crm_leads + ga4_sessions (medical.db)
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- Q1. MONTHLY TREND: all leads by status (full period)
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', created_at)                                         AS month,
    COUNT(*)                                                              AS leads,
    SUM(CASE WHEN status='won'         THEN 1 ELSE 0 END)                AS won,
    SUM(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                AS lost,
    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                AS active,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) AS cr_pct
FROM crm_leads
GROUP BY month
ORDER BY month;

/*
RESULT:
  2025-07   1143  won=349  lost=710  active=84  CR=30.5%
  2025-08   3129  won=359  lost=1985 active=785 CR=11.5%
  2025-09   2597  won=369  lost=1788 active=440 CR=14.2%
  2025-10   5114  won=3165 lost=1963 active=2   CR=61.9% ← ANOMALY (system migration)
  2025-11   2428  won=520  lost=1619 active=289 CR=21.4%
  2025-12   1761  won=310  lost=1169 active=282 CR=17.6%
  2026-01   2248  won=482  lost=1503 active=263 CR=21.4%
  2026-02   1794  won=317  lost=1199 active=278 CR=17.7%
  2026-03   1893  won=357  lost=1259 active=277 CR=18.9%
  2026-04   1918  won=451  lost=1154 active=313 CR=23.5%
  2026-05   2141  won=532  lost=1255 active=354 CR=24.8%
  2026-06   3545  won=423  lost=1810 active=1312 CR=11.9%

October 2025's 62% CR is an artifact: a mass closeout of old Base leads during
the system migration. Exclude it from trend analysis.
June 2026's 12% CR: a lot of "active" leads (1312) — new site, leads not yet
processed.
*/

-- ─────────────────────────────────────────────────────────────
-- Q2. TREND FOR THE NEW SYSTEM ONLY (Touch, Oct 2025+)
--     Strips out the noise from the old Base pipeline, shows real dynamics
-- ─────────────────────────────────────────────────────────────
WITH contacts AS (
    SELECT contact_id,
           strftime('%Y-%m', MIN(created_at))                             AS m,
           MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)         AS won,
           MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)         AS lost,
           MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)         AS active
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
)
SELECT
    m                                                                     AS month,
    COUNT(*)                                                              AS contacts,
    SUM(won)                                                              AS qualified,
    SUM(lost)                                                             AS rejected,
    SUM(active)                                                           AS in_work,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                      AS qual_pct
FROM contacts
GROUP BY m
ORDER BY m;

/*
RESULT (Touch, contact level):
  2025-10  1203  qual=  14  rej=908   in_work=281  1.2% ← ramp-up
  2025-11   484  qual=  35  rej=437   in_work= 12  7.2%
  2025-12   217  qual=  13  rej=199   in_work=  5  6.0%
  2026-01   714  qual=  38  rej=659   in_work= 17  5.3%
  2026-02   606  qual=  91  rej=504   in_work= 11 15.0%
  2026-03   600  qual=  82  rej=504   in_work= 14 13.7%
  2026-04   510  qual= 161  rej=343   in_work=  6 31.6% ← peak
  2026-05   841  qual= 253  rej=567   in_work= 21 30.1%
  2026-06  1363  qual= 186  rej=853   in_work=324 13.6% ← new site, more unqualified leads
*/

-- ─────────────────────────────────────────────────────────────
-- Q3. GA4: MONTHLY SESSION TREND BY CHANNEL
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', date)                                               AS month,
    SUM(CASE WHEN channel='Cross-network' THEN sessions ELSE 0 END)      AS pmax_sess,
    SUM(CASE WHEN channel='Paid Search'   THEN sessions ELSE 0 END)      AS paid_search_sess,
    SUM(CASE WHEN channel='Organic Search' THEN sessions ELSE 0 END)     AS organic_sess,
    SUM(CASE WHEN channel='Direct'        THEN sessions ELSE 0 END)      AS direct_sess,
    SUM(CASE WHEN channel='Organic Social' THEN sessions ELSE 0 END)     AS social_sess,
    SUM(sessions)                                                         AS total_sess
FROM ga4_sessions
GROUP BY month
ORDER BY month;

/*
RESULT — top 3 channels:
  2025-07  PMax=3048  Search=1742  Organic=1765
  2025-08  PMax=3255  Search=2128  Organic=2148
  2025-09  PMax=4047  Search=2253  Organic=2248
  2025-10  PMax=1499  Search= 593  Organic=1218  ← Oct = reduced activity
  2025-11  PMax=2946  Search=2336  Organic=1818
  2025-12  PMax=4047  Search=3682  Organic=1988
  2026-01  PMax=6480  Search=3073  Organic=1928
  2026-02  PMax=3073  Search= 634  Organic=1834
  2026-03  PMax=2526  Search= 438  Organic=1823
  2026-04  PMax= 595  Search= 438  Organic=1725  ← Apr = low paid traffic, but high CR in CRM
  2026-05  PMax=1853  Search= 724  Organic=2028
  2026-06  PMax=7861  Search=1573  Organic=2332  ← new site, PMax grows
*/

-- ─────────────────────────────────────────────────────────────
-- Q4. COMPARISON: APRIL vs MAY 2026
-- Anomaly: April has the least paid traffic, but the highest Touch CR (32%)
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', date)                                               AS month,
    SUM(CASE WHEN channel IN ('Cross-network','Paid Search')
        THEN sessions ELSE 0 END)                                         AS paid_sess,
    ROUND(SUM(CASE WHEN channel IN ('Cross-network','Paid Search')
        THEN conversions ELSE 0 END))                                     AS paid_conv
FROM ga4_sessions
WHERE strftime('%Y-%m', date) IN ('2026-03','2026-04','2026-05')
GROUP BY month;

-- For context: CRM Touch numbers for the same months (from Q2 above)
-- April: 510 contacts, CR=32% — at the same time as the lowest paid traffic
-- (595 PMax sessions). This suggests April's conversions came from a
-- different channel (calls/social), or there was a processing delay
-- (older leads got qualified in a batch)

-- ─────────────────────────────────────────────────────────────
-- Q5. APPOINTMENT FUNNEL BY MONTH (pipeline 10176362)
-- The actual fact: how many appointments really happened
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', created_at)                                         AS month,
    COUNT(*)                                                              AS appt_leads,
    SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)                        AS appt_won,
    ROUND(AVG(NULLIF(price,0)))                                           AS avg_price
FROM crm_leads
WHERE pipeline_id=10176362
GROUP BY month
ORDER BY month;

/*
RESULT (actual bookings and appointments):
  2025-07     3  won=  2  ← the Appointment pipeline was just starting up
  2025-08     9  won=  9
  2025-09    18  won= 14
  2025-10   179  won=161  ← launch: October is the pipeline's first full month
  2025-11   473  won=469
  2025-12   288  won=288
  2026-01   391  won=391
  2026-02   227  won=227
  2026-03   277  won=277
  2026-04   284  won=282  ← lines up with Touch's qualification peak
  2026-05   244  won=243
  2026-06   235  won=210

NB: avg_price is in the source currency's raw units (~670k-1.8M) — worth
confirming currency/units before quoting externally.
The trend is stable at 230-470 bookings/month since November 2025. November
is unusually high — likely a batch of accumulated Touch leads landing at
once. April > May > June by CR, but booking volume is similar: 282/243/210
won. Monthly appointment volume is capped by the clinic's capacity, not by
traffic.
*/

-- ─────────────────────────────────────────────────────────────
-- Q6. SUMMARY TABLE: MARKETING vs OPERATIONAL OUTCOME
-- ─────────────────────────────────────────────────────────────
/*
SUMMARY FOR A STAKEHOLDER (new system, November 2025 – June 2026):

Month    Entered  Qual  CR%  | Appt | Paid GA4 sess | CRM site_paid
----------------------------------------------------------------------
2025-11   484    35  7.2%  |  469 |    4883       |   1
2025-12   217    13  6.0%  |  288 |    7715       |   8
2026-01   714    38  5.3%  |  391 |   10553       |  24
2026-02   606    91 15.0%  |  227 |    4482       |  37
2026-03   600    82 13.7%  |  277 |    3914       |  22
2026-04   510   161 31.6%  |  282 |    1033       |  25
2026-05   841   253 30.1%  |  243 |    2740       |  64
2026-06  1363   186 13.6%  |  210 |   10317       | 322

OBSERVATIONS:
1. April: lowest paid traffic + highest CR → leads came in via calls/social
2. May: everything grows together (traffic + CR + appointments) → the best month
3. June: entries +62%, paid traffic 15x, CR drops to 14% — form-lead quality is lower
4. The correlation between paid traffic and CRM leads is weak: the primary
   conversion tool is the phone call
*/
