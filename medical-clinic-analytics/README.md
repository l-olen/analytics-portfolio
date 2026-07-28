# Case: Marketing Analytics for a Private Medical Clinic

**Context:** A private medical clinic in Tashkent, Uzbekistan. Advertising runs on Google Ads, tracking through GA4, leads land in AmoCRM.

**Task:** Build an end-to-end analytics system — from raw API data to SQL-based funnel analysis and attribution-gap detection.

## Stack

- **Python** — ETL: pulling data from the Google Ads API, GA4 API, AmoCRM API
- **SQLite** — 12 months of historical data
- **SQL** — CTEs, window functions (LAG/LEAD), multi-step funnel analysis via `contact_id`
- **Power BI** — dashboard

## Architecture

```
Google Ads API ──┐
GA4 API        ──┼──► ETL (Python) ──► SQLite ──► SQL analysis ──► Power BI
AmoCRM API     ──┘
```

## Structure

```
etl/            extraction scripts
    etl_crm_medical.py, etl_ga4_medical.py, etl_ads_medical.py
    schema_medical.sql
sql/
    01_funnel_medical.sql            channel → lead → appointment funnel
    02_channel_analysis_medical.sql  CTR, CPC, cost per lead by channel
    02_gap_analysis_medical.sql      GA4 vs CRM: where and why data diverges
    03_trends_medical.sql            monthly trends, period comparisons
dashboards/csv_demo/
    anonymized exports for publication
```

## Key Findings

*Figures below come from the anonymized public export (`dashboards/csv_demo/`). Ratios (CTR/CVR/CR) are preserved exactly as measured — only absolute volumes are scaled for anonymization.*

- **Channel matters more than anything else in the funnel.** Phone-in leads convert to a booked appointment 20.8% of the time, versus only 2.8% for paid web traffic and 3.0% for organic. That's an order of magnitude gap between the "warm" channel and web forms.
- **The main volume of conversions comes from phone calls, not forms.** Paid clicks on the phone number outnumber paid form submissions roughly 13x. But calls can't be attributed to a specific ad campaign — a structural attribution gap that form tracking alone can't fix.
- **The discrepancy between GA4 and CRM paid-form counts isn't a bug.** CRM reads the UTM tag from the URL; GA4 reads it from a cookie session (which ad blockers can strip) — two different counting methods for the same event, not data loss.

## Data Notes

- Google Ads conversions use the `conversion_action_name` breakdown, counting only on-site form submissions (calls and Google Maps actions excluded)
- New site launch date: 2026-06-23 (the breakpoint used in trend analysis)
- Data is anonymized: absolute figures are scaled, and the client's real name is replaced with a generic label throughout
