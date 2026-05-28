# Automated Weekly Market Report: Central Asia Bitumen

**End-to-end Python pipeline that turns raw Excel data into a structured analytical PPTX report with LLM-generated commentary — every week.**

Built for OMT-Consult, a commodity analytics firm covering bitumen markets in Kazakhstan, Uzbekistan, Kyrgyzstan, and Tajikistan.

---

## The Problem

The weekly report required manually:
- Pulling prices, railway volumes, and exchange data from several Excel files
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
Excel sources (Power Query)
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

| Source | What | Format |
|--------|------|--------|
| `Сборка_Цены.xlsx` | Producer prices KAZ + UZB exchange + RF refineries | Excel PQ |
| `нов_ЖД_Сборка.xlsx` | Railway deliveries from RF by country and refinery | Excel PQ |
| `КурсыВалют.xlsx` | Weekly exchange rates (RUB, KZT, UZS, KGS, TJS) | Excel PQ |
| `УзБиржа.xlsx` | Uzbekistan commodity exchange raw transactions | Excel |
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
| Data extraction | Python, xlwings, Power Query |
| Search & enrichment | Tavily API |
| LLM generation | Anthropic Claude API (Sonnet), multimodal (PDF) |
| Report assembly | python-pptx, win32com |
| Scheduling | Windows Task Scheduler (.bat) |

---

## Key Design Decisions

**Why xlwings instead of openpyxl?** Power Query connections break silently with openpyxl. xlwings drives the actual Excel process, so all computed fields stay intact.

**Why a separate fact-check pass?** LLMs hallucinate numbers even when given correct data. A second pass comparing output against the structured data summary catches ~90% of numerical errors before the report goes out.

**Why inject previous report into the prompt?** Without it, the model rewrites identical market situations in full every week. With the previous text as negative example ("don't repeat these phrases"), commentary stays fresh without losing continuity.
