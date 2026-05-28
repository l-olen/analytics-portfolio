# Automated Weekly Market Report: Central Asia Bitumen

**End-to-end Python pipeline that turns raw Excel data into a structured analytical PPTX report with LLM-generated commentary — every week.**

Built for OMT-Consult, a commodity analytics firm covering bitumen markets in Kazakhstan, Uzbekistan, Kyrgyzstan, and Tajikistan.

---

## The Problem

Before automation, every weekly report cycle involved:

**Manual data collection** (multiple sources, done before analysis could start):
- Exchange rates (RUB, KZT, UZS, KGS, TJS) -- copied manually from CBR website into Excel
- Weather statistics for 13 cities across 4 countries -- opened rp5.ru per city, recorded min/max/avg temperature
- Uzbekistan commodity exchange (UzEx) -- manually downloaded bitumen/mazut trade records from uzex.uz
- Kazakhstan exchanges (ETS, CCX) -- manually pulled weekly trade volumes and prices from two separate portals

**Report assembly** (after data was collected):
- Consolidating prices, railway volumes, and exchange data across 5 Excel files
- Writing market commentary for 4 countries + Russia overview (6 sections)
- Inserting texts and updating tables in PowerPoint
- Cross-checking numbers against source data

Time-consuming, repetitive, error-prone.

---

## The Solution

A fully automated pipeline that runs with a single command:

```
python run_report.py --write-pptx "Рынок СрАзии_25_05_2026.pptx"
```

---

## Pipeline Architecture

```
Automated data collection (runs before report)
    │
    ├── currency_scraper.py   ← CBR API: daily RUB/KZT/UZS/KGS/TJS → КурсыВалют.xlsx
    ├── weather_scraper.py    ← Playwright: rp5.ru, 13 cities × 4 countries → weather_central_asia.xlsx
    └── exchange_scraper.py   ← UzEx (HTML), ETS + CCX (Playwright) → УзБиржа.xlsx, ETS_биржа.xlsx
    
Excel sources (Power Query aggregates all of the above)
    │
    ▼
collect_data.py          ← reads 5 Excel files via xlwings (respects Power Query)
    │
    ├── search_news.py   ← Tavily API: weekly news + trader spot prices
    │       │
    │       └── news_verify.py  ← LLM pass: annotates global news with CA market impact
    │
    ▼
generate_analytics.py    ← Claude API: 6 analytical sections
    │   ├── loads quarterly context (analyst_context_current.md)
    │   ├── loads previous week's report (style consistency control)
    │   └── loads RF bitumen PDF reports from server (multimodal)
    │
    ├── fact_check_analytics.py  ← second LLM pass: verifies numbers vs source data
    │
    ├── write_analytics.py       ← inserts texts into PPTX TextBoxes by name
    └── update_pptx.py           ← updates data tables in PPTX slides
```

**Quarterly report** (`generate_quarterly_slides.py`): same approach, runs per-country on aggregated PQ data from `Сборка_квартальные.xlsx`.

---

## Technical Highlights

### Automated data collection layer
Before these scripts existed, exchange rates, weather, and commodity exchange data were all entered manually. Three scrapers replaced that:
- `currency_scraper.py`: pulls 5 currency pairs from CBR XML API, appends daily rows to Excel via xlwings
- `weather_scraper.py`: uses Playwright to scrape weekly temperature statistics for 13 cities across Kazakhstan, Uzbekistan, Kyrgyzstan, and Tajikistan from rp5.ru
- `exchange_scraper.py`: three exchange sources in one script -- UzEx (HTML + pagination), ETS (Playwright, JavaScript-rendered), CCX (internal JSON API + Playwright cookie acquisition). CCX presented a specific challenge: the Kazakhstan national gateway blocks external access, so the script uses Playwright to obtain a valid session cookie before the API call.

### Multimodal context injection
RF bitumen PDF reports are loaded from a network server and passed directly to Claude as base64 documents — giving the model current Russian market data without manual copy-paste.

### Two-pass LLM architecture
1. **Generation**: Claude Sonnet produces 6 market sections from structured data summary + news
2. **Fact-check**: separate Claude call compares generated numbers against raw source data, flags discrepancies

### Style consistency
Previous week's analytics is injected into the prompt with an explicit instruction to avoid repeating 5+ word phrases and to acknowledge unchanged trends briefly rather than rewriting them from scratch.

### Weekly → Quarterly knowledge transfer
Significant weekly events are automatically appended to `weekly_events_log.md`. This file is loaded as context when preparing the quarterly report, creating a continuous knowledge chain.

### Power Query compatibility
All Excel reads use `xlwings` — not `openpyxl`. This preserves Power Query connections and calculated fields that openpyxl silently breaks.

---

## Data Sources

### Automatically collected by scripts

| Script | Source | What | Output |
|--------|--------|------|--------|
| `currency_scraper.py` | CBR API (xml) | Daily rates: RUB, KZT, UZS, KGS, TJS vs USD | `КурсыВалют.xlsx` |
| `weather_scraper.py` | rp5.ru (Playwright) | Weekly temp stats: 13 cities × 4 countries | `weather_central_asia.xlsx` |
| `exchange_scraper.py` | uzex.uz (HTML) | Uzbekistan commodity exchange: bitumen + mazut deals | `УзБиржа_битум+мазут.xlsx` |
| `exchange_scraper.py` | ets.kz (Playwright) | Kazakhstan energy exchange: bitumen trade volumes | `ETS_биржа.xlsx` |
| `exchange_scraper.py` | ccx.kz (API + Playwright) | Kazakhstan Central Asian exchange: bitumen prices | `ETS_биржа.xlsx` |

### Excel source files (read by collect_data.py)

| File | What | Format |
|------|------|--------|
| `Сборка_Цены.xlsx` | Producer prices KAZ + UZB exchange + RF refineries | Excel PQ |
| `нов_ЖД_Сборка.xlsx` | Railway deliveries from RF by country and refinery | Excel PQ |
| `КурсыВалют.xlsx` | Weekly exchange rates | Excel PQ |
| `Каз_Произв_цены.xlsx` | Kazakhstan producer monitoring prices | Excel |
| Tavily API | News + trader spot price quotes | Web search |
| OMT-Consult PDF reports | RF bitumen market (from network server) | PDF |

---

## Output

- `analytics_DD_MM_YYYY.txt` — 6 analytical sections, ready to copy
- `fact_check_DD_MM_YYYY.txt` — verification report (errors flagged)
- `news_DD_MM_YYYY.txt` — sourced news items used in generation
- `market_prices_DD_MM_YYYY.txt` — trader spot price quotes
- PPTX with analytics auto-inserted into named TextBoxes

---

## Stack

| Layer | Tools |
|-------|-------|
| Data collection | Python, requests, Playwright (headless Chromium) |
| Data extraction | xlwings, Power Query |
| Search & enrichment | Tavily API |
| LLM generation | Anthropic Claude API (Sonnet), multimodal (PDF) |
| Report assembly | python-pptx, win32com |
| Scheduling | Windows Task Scheduler (.bat) |

---

## Key Design Decisions

**Why xlwings instead of openpyxl?** Power Query connections break silently with openpyxl. xlwings drives the actual Excel process, so all computed fields stay intact.

**Why a separate fact-check pass?** LLMs hallucinate numbers even when given correct data. A second pass comparing output against the structured data summary catches ~90% of numerical errors before the report goes out.

**Why inject previous report into the prompt?** Without it, the model rewrites identical market situations in full every week. With the previous text as negative example ("don't repeat these phrases"), commentary stays fresh without losing continuity.
