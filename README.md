# Analytics Portfolio

Real-world automation and analytics projects. Each case is production code built for an actual client or business process.

## Cases

### [Automated Weekly Market Report: Central Asia Bitumen](./omt-bitumen-report/)
End-to-end pipeline: web scraping + Excel (Power Query) → Python → LLM analytics (two-pass generation + fact-check) → PPTX. Weekly bitumen market report covering 4 Central Asian countries, automated from data collection to slide text insertion.
**Stack:** Python, xlwings, Playwright, Claude API (multimodal), Tavily, python-pptx, Power Query

### [B2B SaaS Funnel Analysis: 2025 Performance + 2026 Forecast](./b2b-saas-funnel-analysis/)
Full-cycle marketing analytics case: lead funnel analysis (8,930 leads → 111 signed deals → 2.5M EUR), three-scenario 2026 revenue forecast, A/B test design, and GA4/GTM audit.
**Stack:** Google Sheets (array formulas, SUMPRODUCT), Python (DuckDB), Markdown

### [Marketing Analytics: Medical Clinic — Funnel & Attribution](./medical-clinic-analytics/)
End-to-end funnel analysis for a real clinic (anonymized) — from Google Ads/GA4/AmoCRM API to SQL. Finds a 13x call-vs-form attribution gap: paid phone clicks vastly outnumber paid form submissions, but calls can't be attributed to a campaign.
**Stack:** Python (ETL), SQLite, SQL (CTEs, window functions), Power BI

### [Marketing Analytics: Education Center — Audience & Creative](./education-center-analytics/)
Google Ads audience and ad-creative analysis for a real education client (anonymized). Finds a 6x CTR gap between fear-based and result-based ad copy, and that women and the 45-54 age group convert better than the stereotypical "young male" target audience.
**Stack:** Python (ETL), SQLite, SQL, Power BI

### [Google Ads Automation Suite](./google-ads-automation/)
Python automation pipeline + web dashboard for managing Google Ads across multiple client accounts. Weekly keyword/ad analysis via Claude, CRM offline-conversion sync, and a Flask dashboard with live script execution.
**Stack:** Google Ads API, GA4 Data API, AmoCRM API, Claude API, Flask, Plotly
