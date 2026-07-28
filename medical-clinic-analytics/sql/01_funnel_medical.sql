-- Funnel: channel → leads → deals
SELECT
    source,
    COUNT(*)                                   AS leads_total,
    SUM(CASE WHEN status = 'won'  THEN 1 END)  AS won,
    SUM(CASE WHEN status = 'lost' THEN 1 END)  AS lost,
    ROUND(100.0 * SUM(CASE WHEN status = 'won' THEN 1 END) / COUNT(*), 1) AS conv_pct
FROM crm_leads
GROUP BY source
ORDER BY leads_total DESC;

/*
RESULT: source → leads / won / lost / conv_pct
  call         → highest conv% (31.4%), the main channel for real patients
  site_paid    → 510 leads, utm_medium=cpc in CRM. But only 16 of 510 (3.1%)
                 make it to an actual appointment — the rest sit in the "Base" stage.
  site_organic → similar completion picture to site_paid
  other        → social/messengers, no attribution

NB: site_paid being lower than GA4's paid-form count (351) isn't lost UTM data —
it's two different attribution methods: CRM reads UTM from the URL directly,
GA4 reads it from a cookie/session (which ad blockers can strip). CRM duplicates:
15 records, don't affect the picture. Details: sql/02_gap_analysis_medical.sql
*/

-- Funnel by pipeline
SELECT
    pipeline_id,
    COUNT(*)                                                           AS leads_total,
    SUM(CASE WHEN status = 'won'  THEN 1 END)                        AS won,
    SUM(CASE WHEN status = 'lost' THEN 1 END)                        AS lost,
    ROUND(100.0 * SUM(CASE WHEN status = 'won' THEN 1 END) / COUNT(*), 1) AS conv_pct
FROM crm_leads
GROUP BY pipeline_id
ORDER BY leads_total DESC;

/*
┌─────────────┬───────────────────────┬─────────────────────────────────────┐
│ pipeline_id │         Name          │           What "won" means           │
├─────────────┼───────────────────────┼─────────────────────────────────────┤
│ 10176374    │ Base                  │ Initial pool of all new leads        │
├─────────────┼───────────────────────┼─────────────────────────────────────┤
│ 7844402     │ Touch/Qualification   │ Qualified, ready to book             │
├─────────────┼───────────────────────┼─────────────────────────────────────┤
│ 10176362    │ Appointment           │ Appointment actually took place      │
├─────────────┼───────────────────────┼─────────────────────────────────────┤
│ 10298490    │ Repeat interactions   │ Reactivation of older leads          │
└─────────────┴───────────────────────┴─────────────────────────────────────┘
Structural summary:
- Base — all new inbound leads, cost is approximate
- Touch/Qualification — a separate stream, often cold or needing qualification
- Appointment — a booking with the real service price attached
- Repeat — reactivation, a separate stream
*/

-- Contacts whose leads span more than one pipeline, to trace the lead's path
SELECT
    contact_id,
    COUNT(DISTINCT pipeline_id)          AS pipelines_count,
    GROUP_CONCAT(DISTINCT pipeline_id)   AS pipelines,
    COUNT(*)                             AS leads_total,
    MAX(CASE WHEN pipeline_id = 10176362
             AND status = 'won' THEN 1 ELSE 0 END) AS had_appointment
FROM crm_leads
WHERE contact_id IS NOT NULL
GROUP BY contact_id
HAVING pipelines_count > 1
ORDER BY pipelines_count DESC, leads_total DESC
LIMIT 20;

-- How many leads went through the full funnel path
SELECT
    COUNT(DISTINCT contact_id) AS unique_contacts,
    SUM(CASE WHEN pipelines_count > 1 THEN 1 END) AS multi_pipeline,
    SUM(CASE WHEN pipelines_count = 1 THEN 1 END) AS single_pipeline
FROM (
    SELECT contact_id, COUNT(DISTINCT pipeline_id) AS pipelines_count
    FROM crm_leads
    WHERE contact_id IS NOT NULL
    GROUP BY contact_id
);
