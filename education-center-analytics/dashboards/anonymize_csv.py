"""
Anonymize CSV exports for portfolio publication.

Applies per-column scaling to conceal real client data while keeping
ratios (CR%, CTR, share%) intact.

    SPEND_FACTOR  = 12  → ad spend ×12
    VOLUME_FACTOR =  4  → leads, contacts, clicks ×4

Requires dashboards/campaign_map_local.py (gitignored, not in this repo)
for real→anonymized campaign name mapping.

Output: dashboards/csv_demo/*.csv — ready for Power BI / Tableau.
Usage:  python dashboards/anonymize_csv.py
"""

import csv
from pathlib import Path

from campaign_map_local import anonymize_name

SPEND_FACTOR  = 12
VOLUME_FACTOR = 4

CSV_DIR  = Path(__file__).parent / "csv"
DEMO_DIR = Path(__file__).parent / "csv_demo"
DEMO_DIR.mkdir(exist_ok=True)

# ── per-file, per-column rules ────────────────────────────────────────────────
# "NAME"    → real→anonymized campaign name mapping
# "S"       → ×SPEND_FACTOR
# "V"       → ×VOLUME_FACTOR
# None      → keep unchanged (rates, %, dates, strings)
# "R:a/b"   → recalculate from already-scaled columns a and b

RULES = {
    "education_channel_funnel.csv": {
        "contacts": "V", "won": "V", "lost": "V", "active": "V", "cr_pct": None,
    },
    "education_monthly_trend.csv": {
        "contacts": "V", "won": "V", "cr_pct": None,
        "ga_spend_usd": "S", "google_crm_leads": "V",
        "cpl_google_usd": "R:ga_spend_usd/google_crm_leads",
    },
    "education_channel_monthly.csv": {
        "contacts": "V", "won": "V",
    },
    "education_ads_campaigns.csv": {
        "campaign_name": "NAME",
        "spend_usd": "S", "clicks": "V", "impressions": "V",
        "crm_leads": "V", "won": "V",
        "cpl_usd": "R:spend_usd/crm_leads",
        "cpa_usd": "R:spend_usd/won",
    },
    "education_ads_monthly.csv": {
        "spend_usd": "S", "clicks": "V", "impressions": "V", "ga_conversions": "V",
    },
    "education_audience.csv": {
        "impressions": "V", "clicks": "V", "ctr_pct": None,
        "conversions": "V", "cvr_pct": None, "spend_usd": "S",
    },
    "education_creative_themes.csv": {
        # headlines_n НЕ масштабируется — это количество реальных вариантов
        # креатива, а не объёмная метрика; ×4 исказило бы масштаб тестирования
        "impressions": "V", "clicks": "V", "ctr_pct": None,
    },
}

COLUMN_RENAME = {}


# ── helpers ───────────────────────────────────────────────────────────────────

def apply_factor(val: str, factor: float, is_int: bool = False) -> str:
    try:
        v = float(val)
        result = v * factor
        return str(int(round(result))) if is_int else str(round(result, 1))
    except (ValueError, TypeError):
        return val


def recalc(row: dict, formula: str) -> str:
    num_col, den_col = formula.split("/")
    try:
        num = float(row[num_col])
        den = float(row[den_col])
        return str(round(num / den, 1)) if den else ""
    except (ValueError, KeyError):
        return ""


def process(fname: str):
    src = CSV_DIR / fname
    dst = DEMO_DIR / fname
    rules = RULES.get(fname, {})

    if not src.exists():
        print(f"  skip  {fname} (not found)")
        return

    with open(src, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows_in = list(reader)
        headers = list(reader.fieldnames)

    out_headers = [COLUMN_RENAME.get(h, h) for h in headers]
    rows_out = []

    for row in rows_in:
        scaled = {}

        # first pass: scale everything except RECALC columns
        for col in headers:
            rule  = rules.get(col)
            val   = row[col]
            ocol  = COLUMN_RENAME.get(col, col)

            if rule == "NAME":
                scaled[ocol] = anonymize_name(val)
            elif rule == "S":
                scaled[ocol] = apply_factor(val, SPEND_FACTOR)
            elif rule == "V":
                scaled[ocol] = apply_factor(val, VOLUME_FACTOR, is_int=True)
            elif isinstance(rule, str) and rule.startswith("R:"):
                scaled[ocol] = "PLACEHOLDER"
            else:
                scaled[ocol] = val   # None / unspecified → unchanged

        # second pass: recalc derived columns
        for col in headers:
            rule = rules.get(col, "")
            if isinstance(rule, str) and rule.startswith("R:"):
                ocol = COLUMN_RENAME.get(col, col)
                scaled[ocol] = recalc(scaled, rule[2:])

        rows_out.append(scaled)

    with open(dst, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_headers)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"  OK  {fname} -> {dst.name}  ({len(rows_out)} rows)")


def main():
    print(f"Anonymizing: spend x{SPEND_FACTOR}, volume x{VOLUME_FACTOR}")
    print(f"Output: {DEMO_DIR}\n")
    for fname in RULES:
        process(fname)
    print("\nDone. Connect Power BI / Tableau to:", DEMO_DIR)


if __name__ == "__main__":
    main()
