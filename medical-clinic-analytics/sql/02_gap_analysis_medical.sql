-- Gap Analysis: GA4 (paid traffic) vs CRM (leads)
-- Goal: find where and why data diverges between the ad platforms and the CRM

-- ─────────────────────────────────────────────
-- 1. Sessions and conversions by channel (GA4)
-- ─────────────────────────────────────────────
SELECT
    channel,
    SUM(sessions)     AS sessions_total,
    SUM(conversions)  AS conversions_total
FROM ga4_sessions
GROUP BY channel
ORDER BY sessions_total DESC;

/*
RESULT:
Cross-network    48808    4027   ← PMax (utm_campaign=km_max|...)
Organic Search   22001     302
Paid Search      14660    1497   ← standard search (utm_medium=cpc)
Direct            7048     270
Organic Social    3267      23
Display            702       9

Paid traffic total: ~63k sessions, ~5.5k GA4 "conversions".
NB: GA4 "conversions" here = all key events combined (forms + phone-number clicks).
*/

-- ─────────────────────────────────────────────
-- 2. Conversion events, paid vs total breakdown
-- ─────────────────────────────────────────────
SELECT
    event_label,
    SUM(total) AS total,
    SUM(paid)  AS paid
FROM ga4_events
WHERE event_label IN (
    'form_call_submit',
    'form_appointment_side_submit',
    'form_submit',
    'click_number',
    'click_instagram'
)
GROUP BY event_label;

/*
RESULT:
click_number                   5075    4610  ← the clinic's main conversion
form_call_submit                353     315  ← primary form (old site)
form_appointment_side_submit     20      20  ← side form (present on both sites)
form_submit                      16      16
click_instagram                   7       7

Forms total (paid): 315 + 20 + 16 = 351
Calls (paid): 4610 → roughly 13x more than forms.
The clinic converts through the phone, not the form.

June note: after the new site launched on 06-23, GA4 recorded 25
form_appointment_side_submit events, but only 12 leads remained in CRM — the
rest were removed as test submissions. The gap is explained, not a bug.
*/

-- ─────────────────────────────────────────────
-- 3. GA4 paid forms vs CRM site_paid, by month
-- ─────────────────────────────────────────────
SELECT
    month,
    MAX(ga4_paid_forms) AS ga4_paid_forms,
    MAX(crm_site_paid)  AS crm_site_paid
FROM (
    SELECT strftime('%Y-%m', date) AS month,
           SUM(paid) AS ga4_paid_forms,
           0         AS crm_site_paid
    FROM ga4_events
    WHERE event_label = 'form_call_submit'
    GROUP BY month

    UNION ALL

    SELECT strftime('%Y-%m', created_at) AS month,
           0,
           COUNT(*)
    FROM crm_leads
    WHERE source = 'site_paid'
    GROUP BY month
)
GROUP BY month
ORDER BY month;

/*
RESULT:
2025-07      6      0   ← the site form existed but wasn't reaching CRM
2025-08      4      0
2025-09      2      0
2025-10      7      0
2025-11      3      1
2025-12      8      8   ← the integration starts working
2026-01     99     24   ← GA4 sees 4x more than CRM
2026-02     32     37
2026-03     10     22
2026-04      0     25   ← the event was renamed on the new site
2026-05     25     64
2026-06    119    322   ← new site launched 06-23 + event name change

Key point: the new site's form fires under a different event name
(form_appointment_side_submit instead of form_call_submit), so June's
figures aren't directly comparable to earlier months.
*/

-- ─────────────────────────────────────────────
-- 4. Real business outcome by source
--    (only the Appointment pipeline = an actual visit)
-- ─────────────────────────────────────────────
SELECT
    source,
    COUNT(*)                                                    AS leads,
    SUM(CASE WHEN status = 'won' THEN 1 END)                   AS won,
    ROUND(100.0 * SUM(CASE WHEN status = 'won' THEN 1 END)
          / COUNT(*), 1)                                        AS conv_pct
FROM crm_leads
WHERE pipeline_id = 10176362
GROUP BY source
ORDER BY leads DESC;

/*
RESULT:
other        1527    1500    98.2  ← social, messengers, referrals
call          991     971    98.0  ← calls (no attribution to paid)
site_organic   72      70    97.2
site_paid      16      16   100.0  ← only 16 of 510 site_paid leads made it here

Paid traffic: 510 leads in CRM, but only 16 (3.1%) make it to an actual
appointment. The other 494 stall in the "Base" pipeline with no further movement.
*/

-- ─────────────────────────────────────────────
-- 5. Duplicates among site_paid leads
-- ─────────────────────────────────────────────
SELECT
    COUNT(*) AS contacts_with_duplicates
FROM (
    SELECT contact_id
    FROM crm_leads
    WHERE source = 'site_paid'
      AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING COUNT(*) > 1
);

/*
RESULT: 15 contacts with two leads → 15 extra records.

Overall gap:
  CRM site_paid:        510
  minus duplicates:      -15
  Unique leads:          495
  GA4 paid forms:        351
  Difference:            144

Explaining the 144: it's a difference in attribution logic.
CRM reads the UTM tag straight from the URL (always present if the click
came from an ad). GA4 attributes the session via a cookie, which ad blockers
strip and which resets across navigations. So CRM is more accurate for
attributing an individual lead, while GA4 is more accurate for analyzing
on-site behavior.
*/

-- ─────────────────────────────────────────────
-- 6. Real end-to-end funnel by entry source
--    Base → Appointment (via contact_id)
-- ─────────────────────────────────────────────
SELECT
    b.source                                              AS entry_source,
    COUNT(DISTINCT b.contact_id)                         AS contacts_in_base,
    COUNT(DISTINCT a.contact_id)                         AS got_appointment,
    ROUND(100.0 * COUNT(DISTINCT a.contact_id)
          / COUNT(DISTINCT b.contact_id), 1)             AS conversion_pct
FROM crm_leads b
LEFT JOIN (
    SELECT DISTINCT contact_id
    FROM crm_leads
    WHERE pipeline_id = 10176362
      AND status = 'won'
) a ON b.contact_id = a.contact_id
WHERE b.pipeline_id = 10176374
  AND b.contact_id IS NOT NULL
GROUP BY b.source
ORDER BY contacts_in_base DESC;

/*
RESULT:
other        9697    1046    10.8
call         4091     664    16.2
site_organic 1133      62     5.5
site_paid     117      11     9.4  ← 117 unique contacts, not 510 leads

The real end-to-end CR: of everyone who entered Base by source, how many
made it to an actual appointment. call (16.2%) > site_paid (9.4%) >
other (10.8%) > organic (5.5%).

NB: site_paid is a floor. Some paid contacts whose UTM never reached CRM
(78% of cases) are classified as "other" instead. The real CR from paid
traffic is higher than 9.4%, but can't be measured precisely until the
form→CRM integration is fixed.
*/

-- ─────────────────────────────────────────────
-- 7. Touch/Qualification → Appointment (via contact_id)
-- ─────────────────────────────────────────────
SELECT
    COUNT(DISTINCT k.contact_id)  AS contacts_in_touch,
    COUNT(DISTINCT a.contact_id)  AS got_appointment,
    ROUND(100.0 * COUNT(DISTINCT a.contact_id)
          / COUNT(DISTINCT k.contact_id), 1) AS conv_pct
FROM crm_leads k
LEFT JOIN (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id = 10176362 AND status = 'won'
) a ON k.contact_id = a.contact_id
WHERE k.pipeline_id = 7844402
  AND k.contact_id IS NOT NULL;

-- RESULT: 6554 → 728 → 11.1% (comparable to other sources within Base)

-- Overlap: how many Touch contacts were also ever in Base
SELECT
    COUNT(DISTINCT k.contact_id)                              AS in_touch,
    COUNT(DISTINCT b.contact_id)                              AS also_in_base,
    ROUND(100.0 * COUNT(DISTINCT b.contact_id)
          / COUNT(DISTINCT k.contact_id), 1)                  AS overlap_pct
FROM crm_leads k
LEFT JOIN (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id = 10176374
) b ON k.contact_id = b.contact_id
WHERE k.pipeline_id = 7844402
  AND k.contact_id IS NOT NULL;

/*
RESULT: 6554 → 1035 → 15.8% overlap with Base.
84% of Touch contacts are separate people who were never in Base.
Touch is an independent entry stream, not a continuation of Base.
The 15.8% overlap is most likely manual duplication by staff.
*/

-- ─────────────────────────────────────────────
-- 8. Full funnel: every path a contact can take to an appointment
-- ─────────────────────────────────────────────
WITH
in_base AS (SELECT DISTINCT contact_id FROM crm_leads WHERE pipeline_id = 10176374),
in_touch AS (SELECT DISTINCT contact_id FROM crm_leads WHERE pipeline_id = 7844402),
in_appt AS (SELECT DISTINCT contact_id FROM crm_leads
             WHERE pipeline_id = 10176362 AND status = 'won'),
all_contacts AS (
    SELECT contact_id FROM in_base
    UNION SELECT contact_id FROM in_touch
)
SELECT
    CASE
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NOT NULL AND a.contact_id IS NOT NULL
            THEN 'Base + Touch → Appointment'
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NULL  AND a.contact_id IS NOT NULL
            THEN 'Base → Appointment'
        WHEN b.contact_id IS NULL  AND k.contact_id IS NOT NULL AND a.contact_id IS NOT NULL
            THEN 'Touch → Appointment'
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NOT NULL AND a.contact_id IS NULL
            THEN 'Base + Touch (no appointment)'
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NULL  AND a.contact_id IS NULL
            THEN 'Base only'
        ELSE 'Touch only'
    END                            AS journey,
    COUNT(*)                       AS contacts
FROM all_contacts c
LEFT JOIN in_base b ON c.contact_id = b.contact_id
LEFT JOIN in_touch k ON c.contact_id = k.contact_id
LEFT JOIN in_appt a ON c.contact_id = a.contact_id
GROUP BY journey
ORDER BY contacts DESC;

/*
RESULT:
Base only                12720  62%  ← never move further
Touch only                5396  26%  ← never move further
Base → Appointment        1113   5%  ← direct path, bypassing Touch
Base + Touch → Appt        604   3%  ← went through both stages
Base + Touch (no appt)     431   2%  ← went through both, didn't convert
Touch → Appointment         124   1%  ← straight to appointment from Touch

Total contacts:   20,388
Total with appt:   1,841  (9%)

TAKEAWAYS:
1. 88% of contacts never reach an appointment — they stall in Base or Touch
2. Two paths to an appointment: Base→Appt (1113) and via Touch (728 = 604+124)
3. Touch works as a qualifier: 11.1% CR vs ~8% going directly from Base
4. A "hot loss" segment: 431 contacts went through both stages but didn't
   convert — these are highly engaged people worth analyzing separately
5. The real end-to-end CR of the whole funnel: 9% of all contacts who entered
*/

-- ─────────────────────────────────────────────
-- 9. When the funnel logic changed: Base stops being the entry point
-- ─────────────────────────────────────────────
WITH first_lead AS (
    SELECT contact_id, pipeline_id AS first_pipeline,
           MIN(created_at) AS first_date
    FROM crm_leads
    WHERE contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT
    strftime('%Y-%m', first_date)                              AS month,
    SUM(CASE WHEN first_pipeline = 10176374 THEN 1 END)       AS entered_base,
    SUM(CASE WHEN first_pipeline = 7844402  THEN 1 END)       AS entered_touch,
    SUM(CASE WHEN first_pipeline NOT IN (10176374, 7844402)
             THEN 1 END)                                       AS other
FROM first_lead
GROUP BY month
ORDER BY month;

/*
RESULT (a contact's first lead, by pipeline):
2025-07    859     3    84   ← almost everything through Base
2025-08   2574     8    38
2025-09   1748     8    75
2025-10   2028  1163   142   ← TRANSITION: Touch launched in October
2025-11    779   429   387
2025-12    885   205   245
2026-01    558   693   315   ← Touch overtakes Base
2026-02    553   590   206
2026-03    546   572   259
...

FUNNEL ARCHITECTURE (reconstructed from the AmoCRM pipeline settings):

Old system (before Oct 2025):
  New lead → Base (unsorted included) → qualification → Appointment

New system (from Oct 2025):
  New lead → Touch/Qualification (unsorted included, Base excluded)
      ↓ qualified            ↓ closed (7 reasons)     ↓ closed (3 reasons)
  Meeting booked          Base "Rejected/ignored"    Base "Unqualified"

Base today = an archive of rejected leads + leads from before October 2025.
"Unsorted" in Base has been switched off since the migration to the new system.

Sources feeding Touch: Telegram, Instagram (DMs + comments), Facebook, a site
CRM plugin widget, a Google Sheet. The "Source" field is filled in manually
by staff (unreliable). Automatic Instagram/Telegram tagging would need a
dedicated widget or API integration.
*/

-- ─────────────────────────────────────────────
-- 10. Funnel by era: old system vs new
-- ─────────────────────────────────────────────
WITH
first_lead AS (
    SELECT contact_id, pipeline_id AS first_pipeline,
           MIN(created_at) AS first_date
    FROM crm_leads
    WHERE contact_id IS NOT NULL
    GROUP BY contact_id
),
got_appt AS (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id = 10176362 AND status = 'won'
)
SELECT
    CASE
        WHEN fl.first_pipeline = 10176374 AND fl.first_date < '2025-10-01'
            THEN '1. Old system: entered via Base'
        WHEN fl.first_pipeline = 7844402
            THEN '2. New system: entered via Touch'
        WHEN fl.first_pipeline = 10176374 AND fl.first_date >= '2025-10-01'
            THEN '3. Base after Oct (rejected from Touch)'
        ELSE '4. Direct entry (Appointment/Repeat pipelines)'
    END                              AS segment,
    COUNT(*)                         AS contacts,
    COUNT(ga.contact_id)             AS got_appointment,
    ROUND(100.0 * COUNT(ga.contact_id) / COUNT(*), 1) AS conv_pct
FROM first_lead fl
LEFT JOIN got_appt ga ON fl.contact_id = ga.contact_id
GROUP BY segment
ORDER BY segment;

/*
RESULT:
1. Old system (Base before Oct):    5195 → 76  → 1.5% CR
2. New system (Touch):              6273 → 574 → 9.2% CR  ← working benchmark
3. Base after Oct (rejected):       7717 → 68  → 0.9% CR  ← confirmed: a reject bin
4. Direct entry:                    2252 → 1297 → 57.6%   ← artifact: entered straight into Appointment

TAKEAWAYS:
- The new system (Touch) performs 6x better than the old one: 9.2% vs 1.5%
- 7,717 rejected contacts vs 6,273 active ones — a high unqualified rate,
  which is normal for this clinic
- "Direct entry" (57.6%) isn't a real funnel conversion — a staff member
  created the lead straight in the Appointment pipeline
- The full year of data isn't directly comparable: October 2025 is a break
  point in the underlying logic
*/

-- ─────────────────────────────────────────────
-- SUMMARY (for the portfolio write-up and interviews)
-- ─────────────────────────────────────────────
/*
THE CENTRAL QUESTION: what is the ROI of the clinic's paid traffic?
THE HONEST ANSWER: it can't be measured precisely — three structural gaps:

1. CALLS (the main channel): 4,610 paid phone-number clicks in GA4
   → can't attribute to a campaign without call tracking
   → the owner isn't ready to invest in call tracking yet

2. FORMS: the form→CRM UTM integration was unreliable for most of the year
   → fixed on 2026-06-30 with the new site
   → historical data can't be recovered

3. SOCIAL (Instagram/Telegram): no automatic tagging
   → the "Source" field is filled in manually by staff
   → automatic tagging needs extra setup (a widget or API integration)

WHAT CAN BE MEASURED:
- The new system (Touch, Oct 2025+): 9.2% CR — a working benchmark
- Rejections: 7,717 of ~14k entrants (~55%) don't qualify
- Paid traffic: 510 site_paid leads, 11 made it to an appointment (a floor)
- The main conversion channel is the phone call, but it's a black box

RECOMMENDATIONS (in priority order):
1. Call tracking — would unlock attribution for 90% of conversions
2. UTM→CRM integration — already fixed, needs monitoring
3. Automatic social tagging — a dedicated widget, or a developer ticket
*/
