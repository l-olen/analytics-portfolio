# B2B SaaS Funnel Analysis: 2025 Performance + 2026 Forecast

**Marketing analytics assignment for a B2B iGaming software company.**
Full-cycle analysis of a 2025 lead funnel (8,930 leads → 111 signed deals), three-scenario 2026 revenue forecast, A/B test design, and GA4 tracking audit.

---

## The Assignment

Three tasks, each requiring a different analytical mode:

1. **Task 1 — Data analysis + forecasting.** Given raw CSVs for Leads, MQL, SAL, Signed Deals, and Ad Spend across 2025: clean the data, analyze funnel performance by channel/product/region/seasonality, build a 2026 monthly forecast under three scenarios.
2. **Task 2 Case A — Experiment design.** Design an A/B test for a new lead capture format. Define metric, sample size, stopping rule, success criteria.
3. **Task 2 Case B — Analytics audit.** Diagnose a 40% organic session drop in GA4 post-2024. Produce a prioritized hypothesis list with investigation steps.

---

## Task 1: Data Analysis

### Data Quality Problem Found

Before any analysis, the data had a non-obvious attribution bug.

The source data had no direct link between Signed Deals and Leads. The join chain was:

```
Lead ID → SAL (Sales Accepted Lead) → Brand Name → Signed Deal
```

The problem: **43 Lead IDs appeared multiple times in the SAL table with different brand names** (one lead contacted multiple products). A naive `INDEX/MATCH` returns the first match — which could be a brand the lead *never* signed with.

**Result before fix:** 103 attributed signed deals, deal value 2,416,400 EUR.

**Fix:** Array formula that prioritizes the brand name present in the Signed Deals table:

```
=IFERROR(
  INDEX(SAL!Brand, MATCH(1,
    (SAL!LeadID = B2) * ISNUMBER(MATCH(SAL!Brand, Signed!Brand, 0)),
  0)),
  IFERROR(INDEX(SAL!Brand, MATCH(B2, SAL!LeadID, 0)), "")
)
```

**Result after fix:** 111 signed deals, deal value 2,547,100 EUR.

The 130,700 EUR gap (5.1%) would have made every downstream metric — avg deal value, ROI by channel, ROAS — quietly wrong.

---

### 2025 Funnel: Key Numbers

| Stage | Count | Conversion |
|-------|-------|------------|
| Leads | 8,930 | — |
| MQL | 3,282 | 36.75% |
| SAL | 751 | 22.88% |
| Signed | 111 | 14.78% |
| Deal Value | 2,547,100 EUR | Avg: 22,947 EUR |
| Total Spend | 24,881 EUR | ROAS: 102.4x |

---

### Key Analytical Findings

**Channel**
- Google organic drives 52% of leads and 62% of deal value — the dominant acquisition channel
- LinkedIn referral: best unit economics among paid (ROAS 88.5x, Cost/Signed 265 EUR), but only 4 signed deals — small sample, interpret cautiously
- Google CPC: highest Cost/Signed (1,543 EUR) and lowest ROAS (11.5x) among paid channels
- ChatGPT referral: 3 signed deals, 66,000 EUR DV, zero spend — an emerging zero-cost channel worth tracking in 2026

**Product**
- Product 1 accounts for 45% of signed deals and 50% of deal value with the best Lead→MQL conversion (47.8% vs 27–33% for others) and lowest Cost/Signed (129 EUR). Core scale-up candidate
- Product 4: highest avg deal value (31,973 EUR) but worst Cost/Signed (460 EUR) — high-ticket, selective investment
- Product 3: volume product, lowest avg deal (14,305 EUR)

**Region**
- LatAm: 42% of signed deals, best Cost/Signed (206 EUR), ROAS 110.1x — justifies dedicated budget increase
- Europe: highest avg deal value (26,693 EUR), highest concentration of organic traffic, most exposed to locale risk
- US: lowest ROAS (89.0x) and lowest avg deal (19,979 EUR)

**Seasonality**
- Q3 dip: -34% leads, -51% signed vs Q2 (B2B iGaming summer slowdown — expected)
- Q1 deal value premium: 38% of annual DV on 29.5% of leads (Q4 pipeline closes in January)
- April–May Lead→MQL spike: 46–47% vs 36.75% annual average

---

## Task 1: 2026 Forecast

### Methodology

Three strategic inputs applied to the 2025 baseline:

**1. Product 1 paid channel scale-up**

Diminishing returns modeled via elasticity coefficient:

| Scenario | Budget increase | Elasticity | Lead uplift |
|----------|----------------|------------|-------------|
| Conservative | +20% | 0.75 | +15% |
| Base | +40% | 0.70 | +28% |
| Aggressive | +60% | 0.63 | +38% |

Conversion rate degradation applied to scaled paid stream only: at high volumes, paid traffic quality degrades. This is why Base and Aggressive produce the same signed count (122) — the conversion loss in Aggressive precisely offsets the lead gain. Revenue is still higher in Aggressive through product mix shift.

**2. LatAm +20% investment (all channels)**

Diminishing returns: Conservative +12% / Base +15% / Aggressive +20% leads.

**3. German locale deletion**

Impact modeled separately by channel type — organic traffic is more SEO-dependent than paid:

| Channel | Conservative | Base | Aggressive |
|---------|-------------|------|------------|
| Organic | -50% | -60% | -70% |
| Direct | -20% | -30% | -40% |
| Paid | -5% | -10% | -15% |

**Interaction effect:** Product 1 × LatAm is multiplicative (not additive) — the same lead is both Product 1 and LatAm. Base combined effect: ×1.28 × ×1.15 = ×1.472.

### Forecast Results

| Metric | 2025 Actual | Conservative | Base | Aggressive |
|--------|------------|-------------|------|------------|
| Leads | 8,930 | 9,314 (+4.3%) | 9,715 (+8.8%) | 10,116 (+13.3%) |
| MQL | 3,282 | 3,424 | 3,549 | 3,664 |
| SAL | 751 | 784 | 808 | 833 |
| Signed | 111 | 113 (+1.8%) | 122 (+9.9%) | 122 (+9.9%) |
| Deal Value | 2,547,100 EUR | 2,593,011 (+1.8%) | 2,867,000 (+12.6%) | 2,928,000 (+14.9%) |

Recommended use: Base = operational plan. Conservative = downside bound. Aggressive = upside; monitor Europe separately.

---

## Task 2 Case A: A/B Test Design

**Test objective:** Measure whether a new lead capture format increases MQL rate from the baseline 36.75%.

**Primary metric:** MQL rate (not CTR, not form submissions — because the business goal is qualified leads, not clicks)

**Sample size:** ~2,900 leads per variant at 80% power, α=0.05, MDE=3 percentage points. With current lead volume (~745/month), minimum runtime is 4 weeks.

**Key design decisions:**

- **SRM check first.** Before analyzing results, run a chi-square test on variant assignment. An imbalance >5% signals a broken randomization — the experiment result is invalid regardless of what it shows.
- **MQL attribution window: 30 days.** B2B MQL conversion is not immediate — a lead from Week 1 may qualify in Week 3. The analysis window must extend 30 days past the last impression.
- **Novelty effect handling.** New UI formats often spike in Week 1 due to novelty, then decay. If Week 1 shows an outlier spike that drops in Week 2+, analyze Week 2+ only. If no spike-decay pattern is observed, use the full window.
- **Ship rule: BOTH conditions required simultaneously** — statistical significance AND practical significance (MDE threshold met). Significance alone without business-meaningful effect size is not sufficient to ship.
- **Segment analysis is exploratory only.** Post-hoc segments (mobile vs desktop, region, product) are hypothesis-generating, not confirmatory. Treat them as input to the next experiment.

---

## Task 2 Case B: GA4 / GTM Audit

**Problem:** 35% organic session drop in GA4 starting post-2024. Could be a tracking issue or a real traffic drop.

**Critical first step: rule out non-tracking causes.** Before touching GTM or GA4, check:
- robots.txt / noindex tags — was the site accidentally de-indexed?
- Google Search Console: are impressions/clicks also down, or just GA4 sessions?
- Canonical tags and redirect chains — were URLs restructured?
- Core Web Vitals (ranking factor since 2021)

If GSC impressions are also down → SEO problem, not tracking. If GSC is stable → tracking problem.

**Priority 1 tracking hypothesis: Consent Mode v2 implementation.**
Google required Consent Mode v2 for EEA traffic in March 2024. Sites without proper CMPv2 integration stop sending modeled data to GA4. A 40% drop in European organic sessions is consistent with this timeline and has no other explanation that affects organic specifically.

**Other ranked hypotheses:**

| Priority | Hypothesis | Key check |
|----------|-----------|-----------|
| 1 | Consent Mode v2 missing/misconfigured | CMP audit, `gtag('consent', 'default')` presence |
| 2 | GA4 configuration tag firing on wrong trigger | GTM Preview: does config tag fire on all pages? |
| 3 | Duplicate tracking (GTM + hardcoded gtag.js) | Page source check, `window.dataLayer` inspection |
| 4 | Cross-domain tracking misconfigured | `_ga` parameter in URLs, GA4 domain list |
| 5 | `(not set)` source/medium growth | Broken session context (referrer stripping, redirects) |

**`(not set)` in GA4 source/medium** is not a measurement error — it means the session context was broken. The session fired before the config tag loaded (page load order issue) or after a redirect that stripped the referrer.

**Action sequence:**
1. Freeze GTM — no new changes until audit is done
2. Diagnose: GSC vs GA4 comparison, consent audit, GTM Preview
3. Reconstruct: fix Consent Mode v2, establish single event source (GTM OR hardcoded gtag.js, not both)
4. Validate: run parallel tracking for 2 weeks, compare session counts
5. Relaunch: document baseline post-fix, set up Looker Studio anomaly monitoring

---

## Stack

| Layer | Tool |
|-------|------|
| Data storage & joins | Google Sheets (ARRAYFORMULA, INDEX/MATCH, SUMPRODUCT) |
| Local diagnostics | Python + DuckDB (SQL on CSV, attribution debugging) |
| Forecasting model | Google Sheets (scenario parameters, monthly breakdowns) |
| Experiment analysis | Manual power calculation (z-test), chi-square SRM check |
| Analytics audit | GA4, GTM Preview, Google Search Console, Looker Studio |
| Documentation | Markdown |

---

## Files

| File | Description |
|------|-------------|
| `case_a_ab_test.md` | Full A/B test design with rationale (EN + RU) |
| `case_b_ga4_audit.md` | Full GA4/GTM audit playbook (EN + RU) |
| `forecast_methodology.md` | Forecast parameters, elasticity table, scenario assumptions |
