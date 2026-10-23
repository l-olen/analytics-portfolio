# Google Ads Automation Suite

**Python automation pipeline + web dashboard for managing Google Ads across multiple client accounts (MCC).**

The pipeline runs unattended on a schedule. It pulls data from the Google Ads API, GA4 and the CRM, uses Claude to interpret it, and applies only pre-approved changes back to the accounts. Everything else becomes a proposal for a human to approve.

**Agent charter:** [`AGENT.md`](./AGENT.md) covers what the daily agent may apply on its own, what it must propose, what it may never touch, and the guardrails enforced in code.

---

## What It Does

### Daily cycle

1. **Health check** (`ads_health_check.py`) runs every morning across all accounts and covers 8 dimensions:
   - lead quality from the CRM;
   - junk placements (auto-excluded);
   - ad strength, with LLM rewrite suggestions;
   - GA4 engagement as a bot detector;
   - bidding hygiene;
   - the remaining account budget limit;
   - the tracking gap between CRM form leads and platform conversions;
   - an automation guard that diffs daily snapshots and alerts on Search trend drops.
2. **Daily agent** ([`AGENT.md`](./AGENT.md)) is a headless Claude Code session. It reads the health check and applies only Tier-1 actions through guarded tools, with a rollback check on the next day. Everything else goes to a `proposals.md` with checkboxes. Ticked items are applied exactly as written on the next run.

### Weekly cycle

1. **Keyword analysis** (`weekly_keywords.py`) takes 30-day search terms and keyword metrics and sends them to Claude in a single call. The output is campaign-scoped negative keywords and new keyword candidates, graded HIGH or MEDIUM. Every negative passes code-level checks before it is applied: no negative that blocks a term with a lead in the last 12 months, no brand or geo stems, a per-run cap.

2. **Campaign & ad analysis** (`ads_analysis.py`) — RSA headlines/descriptions performance, Quality Score alerts, auction insights snapshot, budget pacing. Claude proposes ad copy replacements (character limits validated before writing).

3. **CRM sync** (`crm_sync.py`) — offline conversions from AmoCRM to Google Ads via GCLID matching. Customer Match audience upload from CRM contacts. 4-hour cache on both CRM fetch and contact list — `--apply` reads cache, no repeated API calls.

4. **Data lake** (`bigquery_etl_*.py`) loads Ads, GA4 and CRM data into BigQuery. The tables are partitioned by date and use idempotent per-day reloads. Full history is backfilled, including dormant accounts. Ad performance can then be joined to actual CRM outcomes across all accounts.

5. **Weekly analyst** is a second headless Claude session with a fresh view. It runs a ~14-category audit checklist covering Quality Score, landing pages and search-term waste, and writes a report ranked by money impact. It has **no edit permissions** at all, so the restriction is enforced by tooling and not only by the prompt.

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
Google Ads API ──► weekly_keywords.py ──► Claude Sonnet ──► weekly_keywords.json
                ──► ads_analysis.py ───► Claude Opus ───► ad_copy_candidates.json
AmoCRM API ─────► crm_sync.py ─────────────────────────► offline conversions upload
                                                        ──► Customer Match upload
GA4 Data API ───► full_report.py ──────────────────────► marketing_analysis_latest.json

All cached data ──► analyst.py ──► Claude Sonnet ──► strategic analysis

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
| LLM | Anthropic Claude API (Sonnet), Claude Code headless sessions for the daily agent and weekly analyst |
| Web dashboard | Flask, Plotly, SSE streaming |
| Data | BigQuery (Ads + GA4 + CRM), JSON cache files, append-only change log |
| Scheduling | Windows Task Scheduler |

---

## Key Design Decisions

**Why guardrails in code, not in the prompt?** Automation on ad accounts can fail silently: an inflated conversion upload or an over-broad negative raises no error, it just distorts bidding or costs leads. And a model does not reliably follow rules that exist only in the prompt. So:
- every change goes to an append-only change log, because the Ads API returns only 30 days of change history;
- business rules are enforced in code;
- automatic changes are capped per run;
- the conversion upload refuses anomalous batches.

**Why staged autonomy?** An action gets automated only after it has been run by a human the same way, with the same safeguards, several times. Until then the agent only proposes it. The agent can never edit its own guardrails.

**Why dry-run by default?** Changes to live ad accounts are irreversible in the short term. Every script prints a preview; `--apply` requires explicit intent.

**Why cache CRM data?** Fetching 30,000+ contacts on every run would exhaust API rate limits and slow the `--apply` pass. A 4-hour TTL file makes dry-run and apply symmetric.

**Why one Claude call for keyword decisions?** Separate calls for "pause" vs "add negatives" vs "add keywords" produce contradictions — the model might recommend pausing a keyword while simultaneously suggesting adding it. A single call with all three tasks sees the full picture.

**Why SSE streaming in the dashboard?** Scripts run for 30–90 seconds. A simple HTTP response would time out or appear frozen. SSE pushes each output line to the browser as it arrives.
