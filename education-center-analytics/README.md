# Case: Education Center Analytics — Audience & Creative

**Context:** An education center offering exam-prep and university-admission courses. Advertising runs on Google Ads, tracking through GA4, leads land in AmoCRM — plus audience and ad-creative breakdowns pulled directly from the Google Ads API.

**Task:** Build an end-to-end analytics system — from raw API data to SQL-based funnel analysis and ad-creative performance by audience segment.

## Stack

- **Python** — ETL: pulling data from the Google Ads API, GA4 API, AmoCRM API
- **SQLite** — 12 months of historical data
- **SQL** — CTEs, window functions, multi-step funnel analysis via `contact_id`
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
    etl_crm_education.py, etl_ga4_education.py, etl_ads_education.py
    schema_education.sql
sql/
    01_funnel_education.sql              channel → lead → deal funnel
    04_audience_creative_education.sql   age/gender breakdown, CTR by ad theme
dashboards/csv_demo/
    anonymized exports for publication
```

## Key Findings

*Figures below come from the anonymized public export (`dashboards/csv_demo/`). Ratios (CTR/CVR) are preserved exactly as measured.*

- **Fear-based ad headlines get a 1.6% CTR, versus 9.8% for result-oriented copy (e.g. IELTS-focused ads)** — almost a 6x gap. Caveat worth stating plainly: the "fear" theme is represented by a single headline on a modest number of impressions, so the direction is clear but this isn't a statistically robust sample.
- **Women convert better than men:** 4.0% CVR versus 3.12% — even though the ad creative has historically skewed toward a young-male visual style.
- **The 45–54 age group has the best CVR (4.34%) of any defined age bracket** — better than the 18–24 audience the campaigns are typically built around.
- **An honestly documented limitation:** audience/creative-level data can't be joined to actual CRM sales — the Google Ads API doesn't expose `gclid` at that level of granularity. There's only a rough campaign-level bridge (4.5% coverage), too thin a sample to build a separate analysis on.

## Data Notes

- Data is anonymized: absolute figures are scaled, and the client's real name and campaign names are replaced with generic labels throughout
