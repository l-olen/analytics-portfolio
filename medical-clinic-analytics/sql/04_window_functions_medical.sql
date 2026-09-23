-- ============================================================
-- MEDICAL: Window functions -- month-over-month trend analysis
-- Extends 03_trends_medical.sql Q2 (Touch qualification rate by month)
-- with LAG() for period-over-period change and a rolling average.
-- ============================================================

-- Q1. Touch qualification rate: month-over-month change + 3-month rolling avg
WITH contacts AS (
    SELECT contact_id,
           strftime('%Y-%m', MIN(created_at))                     AS m,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END)          AS won
    FROM crm_leads
    WHERE pipeline_id = 7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
),
monthly AS (
    SELECT m                                                       AS month,
           COUNT(*)                                                AS contacts,
           SUM(won)                                                AS qualified,
           ROUND(100.0 * SUM(won) / COUNT(*), 1)                   AS qual_pct
    FROM contacts
    GROUP BY m
)
SELECT
    month,
    contacts,
    qualified,
    qual_pct,
    LAG(qual_pct) OVER (ORDER BY month)                             AS prev_month_pct,
    ROUND(qual_pct - LAG(qual_pct) OVER (ORDER BY month), 1)        AS mom_change_pp,
    ROUND(AVG(qual_pct) OVER (
        ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 1)                                                            AS rolling_3mo_avg
FROM monthly
ORDER BY month;

/*
RESULT:
month    contacts qualified qual_pct prev_month_pct mom_change_pp rolling_3mo_avg
2025-10  1203     14        1.2      NULL           NULL          1.2
2025-11  484      35        7.2      1.2            6.0           4.2
2025-12  217      13        6.0      7.2           -1.2           4.8
2026-01  714      38        5.3      6.0           -0.7           6.2
2026-02  606      91        15.0     5.3            9.7           8.8
2026-03  600      82        13.7     15.0          -1.3           11.3
2026-04  510      161       31.6     13.7           17.9          20.1
2026-05  841      253       30.1     31.6          -1.5           25.1
2026-06  1363     186       13.6     30.1          -16.5          25.1

TAKEAWAYS:
- Feb 2026 is the inflection point: qual_pct jumps from 5.3% to 15.0% (+9.7pp)
  and stays elevated through May -- the system stabilizes ~4 months after
  the Oct 2025 migration (ramp-up period).
- Jun 2026's -16.5pp month-over-month drop is the sharpest swing in the series
  -- flagged separately in 03_trends as coinciding with the new site launch
  (more unqualified form leads diluting the qualification rate). LAG() makes
  this magnitude explicit rather than eyeballing it from the raw numbers.
- Rolling 3-month average smooths the Oct-Jan ramp-up noise, showing the
  real steady-state level (~25%) more clearly than any single month.
*/

-- Q2. Same technique applied to GA4 paid sessions -- month-over-month % growth
WITH paid AS (
    SELECT strftime('%Y-%m', date)                                  AS month,
           SUM(CASE WHEN channel IN ('Cross-network','Paid Search')
               THEN sessions ELSE 0 END)                            AS paid_sessions
    FROM ga4_sessions
    GROUP BY month
)
SELECT
    month,
    paid_sessions,
    LAG(paid_sessions) OVER (ORDER BY month)                        AS prev_month_sessions,
    ROUND(100.0 * (paid_sessions - LAG(paid_sessions) OVER (ORDER BY month))
          / NULLIF(LAG(paid_sessions) OVER (ORDER BY month), 0), 1) AS mom_growth_pct
FROM paid
ORDER BY month;

-- Same LAG pattern, different metric -- reusable for any month-over-month
-- growth/decline question (budget review, channel-mix shift, etc.)
