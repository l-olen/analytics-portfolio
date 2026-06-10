# Google Ads Automation Suite

**Python automation pipeline + web dashboard for managing Google Ads across multiple client accounts (MCC).**

Weekly analysis runs unattended: pulls data from Google Ads API and GA4, sends it through Claude for interpretation, applies approved changes back to the accounts.

---

## What It Does

### Weekly automation cycle

1. **Keyword analysis** (`weekly_keywords.py`) — pulls 30-day search terms + keyword metrics, sends to Claude Haiku, gets back three coordinated lists: keywords to pause, new negative keywords per campaign, new keyword candidates. One Claude call sees everything at once — no contradictions between the three outputs.

2. **Campaign & ad analysis** (`ads_analysis.py`) — RSA headlines/descriptions performance, Quality Score alerts, auction insights snapshot, budget pacing. Claude proposes ad copy replacements (character limits validated before writing).

3. **CRM sync** (`crm_sync.py`) — offline conversions from AmoCRM to Google Ads via GCLID matching. Customer Match audience upload from CRM contacts. 4-hour cache on both CRM fetch and contact list — `--apply` reads cache, no repeated API calls.

4. **Strategic analysis** (`analyst.py`) — reads cached data from steps 1–3 + GA4 funnel + CRM pipeline, produces a strategic written analysis via Claude claude-sonnet-4-6.

All scripts run in **dry-run mode by default** — print what would change, apply nothing. `--apply` flag triggers real changes.

### Web dashboard (`app.py`)

Flask application at `http://localhost:5000`:
- **Scripts panel** — run any script from browser, see live output via SSE streaming
- **Dashboard** — GA4 channel breakdown (Plotly), CRM funnel, lead source pie charts, per-account metrics
- **Analysis page** — formatted output from the last strategic analysis run
- **Export** — self-contained HTML report for sharing

---

## Architecture

```
Google Ads API ──► weekly_keywords.py ──► Claude Haiku ──► weekly_keywords.json
                ──► ads_analysis.py ───► Claude Haiku ──► ad_copy_candidates.json
AmoCRM API ─────► crm_sync.py ─────────────────────────► offline conversions upload
                                                        ──► Customer Match upload
GA4 Data API ───► full_report.py ──────────────────────► marketing_analysis_latest.json

All cached data ──► analyst.py ──► Claude claude-sonnet-4-6 ──► strategic analysis

app.py (Flask) ──► serves dashboard + runs scripts via subprocess SSE stream
```

### Google Ads Scripts (MCC-level, run on Google's servers)

| Script | What | Schedule |
|--------|------|----------|
| `weekly_keywords.js` | Search terms with conversions → exact keywords | Weekly |
| `dayparting.js` | Hour-of-day bid adjustments based on CVR | Weekly |
| `device_bidding.js` | Mobile/tablet bid adjustments | Weekly |
| `keyword_conflicts.js` | Keyword cannibalization detection → Sheets | Monthly |
| `rsa_asset_pause.js` | LOW-rated RSA assets → Sheets (manual pause) | Weekly |
| `quality_score.js` | Weekly QS snapshot → Sheets | Weekly |

Scripts API limitation: auction insights and RSA asset pausing are not available via Scripts — handled by Python scripts instead.

---

## Stack

| Layer | Tools |
|-------|-------|
| Google Ads API | `google-ads` Python client, OAuth2 |
| GA4 | GA4 Data API v1 |
| CRM | AmoCRM REST API |
| LLM | Anthropic Claude API (Haiku for analysis, Sonnet for strategy) |
| Web dashboard | Flask, Plotly, SSE streaming |
| Data | JSON cache files, Excel (xlwings for auction history) |
| Scheduling | Windows Task Scheduler |

---

## Screenshots

![Scripts panel](screenshots/scripts_panel.png)
![Dashboard — GA4 channels](screenshots/dashboard_channels.png)
![Dashboard — CRM funnel](screenshots/dashboard_crm.png)

---

## Key Design Decisions

**Why dry-run by default?** Changes to live ad accounts are irreversible in the short term. Every script prints a preview; `--apply` requires explicit intent.

**Why cache CRM data?** Fetching 30,000+ contacts on every run would exhaust API rate limits and slow the `--apply` pass. A 4-hour TTL file makes dry-run and apply symmetric.

**Why one Claude call for keyword decisions?** Separate calls for "pause" vs "add negatives" vs "add keywords" produce contradictions — the model might recommend pausing a keyword while simultaneously suggesting adding it. A single call with all three tasks sees the full picture.

**Why SSE streaming in the dashboard?** Scripts run for 30–90 seconds. A simple HTTP response would time out or appear frozen. SSE pushes each output line to the browser as it arrives.
