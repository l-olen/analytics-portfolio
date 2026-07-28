"""
ETL: Google Ads → education_ads.db
Education center account, full available history.
Tables:
  ads_campaigns      — daily performance by campaign
  ads_keywords       — daily performance by keyword (Search only)
  ads_search_terms   — search terms (last 90 days, a Google Ads API limit)
  ads_demographics   — daily performance by age and gender (aggregated to campaign level)
  ads_creative_assets — daily performance by RSA asset (headlines/descriptions)
"""

import os, sys, sqlite3
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(os.getenv("SHARED_ENV_PATH", Path(__file__).parent / ".env")), override=True)

from google.ads.googleads.client import GoogleAdsClient

# ============================================================
CUSTOMER_ID = "6355895321"
DB_PATH = Path(__file__).parent.parent / "data" / "education_ads.db"
# How many days of history to pull on the first run
INITIAL_DAYS = 540   # ~18 months
# On subsequent runs, re-fetch the last N days (they update with a delay)
REFRESH_DAYS = 7
# ============================================================


def get_client() -> GoogleAdsClient:
    return GoogleAdsClient.load_from_dict({
        "developer_token": os.environ["DEVELOPER_TOKEN"],
        "client_id":       os.environ["CLIENT_ID"],
        "client_secret":   os.environ["CLIENT_SECRET"],
        "refresh_token":   os.environ["REFRESH_TOKEN"],
        "login_customer_id": os.environ["MCC_ID"],
        "use_proto_plus":  True,
    })


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ads_campaigns (
            date            TEXT NOT NULL,
            campaign_id     INTEGER NOT NULL,
            campaign_name   TEXT,
            campaign_type   TEXT,
            status          TEXT,
            impressions     INTEGER DEFAULT 0,
            clicks          INTEGER DEFAULT 0,
            cost_micros     INTEGER DEFAULT 0,
            conversions     REAL DEFAULT 0,
            conv_value      REAL DEFAULT 0,
            PRIMARY KEY (date, campaign_id)
        );

        CREATE TABLE IF NOT EXISTS ads_keywords (
            date            TEXT NOT NULL,
            campaign_id     INTEGER NOT NULL,
            ad_group_id     INTEGER NOT NULL,
            keyword_id      INTEGER NOT NULL,
            keyword_text    TEXT,
            match_type      TEXT,
            impressions     INTEGER DEFAULT 0,
            clicks          INTEGER DEFAULT 0,
            cost_micros     INTEGER DEFAULT 0,
            conversions     REAL DEFAULT 0,
            PRIMARY KEY (date, campaign_id, ad_group_id, keyword_id)
        );

        CREATE TABLE IF NOT EXISTS ads_search_terms (
            date            TEXT NOT NULL,
            campaign_id     INTEGER NOT NULL,
            ad_group_id     INTEGER NOT NULL,
            search_term     TEXT NOT NULL,
            match_type      TEXT,
            impressions     INTEGER DEFAULT 0,
            clicks          INTEGER DEFAULT 0,
            cost_micros     INTEGER DEFAULT 0,
            conversions     REAL DEFAULT 0,
            PRIMARY KEY (date, campaign_id, ad_group_id, search_term)
        );

        CREATE TABLE IF NOT EXISTS ads_demographics (
            date            TEXT NOT NULL,
            campaign_id     INTEGER NOT NULL,
            dimension       TEXT NOT NULL,   -- 'age_range' | 'gender'
            segment_value   TEXT NOT NULL,   -- e.g. AGE_RANGE_18_24, FEMALE
            impressions     INTEGER DEFAULT 0,
            clicks          INTEGER DEFAULT 0,
            cost_micros     INTEGER DEFAULT 0,
            conversions     REAL DEFAULT 0,
            PRIMARY KEY (date, campaign_id, dimension, segment_value)
        );

        CREATE TABLE IF NOT EXISTS ads_creative_assets (
            date               TEXT NOT NULL,
            campaign_id        INTEGER NOT NULL,
            ad_group_id        INTEGER NOT NULL,
            asset_id           INTEGER NOT NULL,
            field_type         TEXT NOT NULL,   -- HEADLINE | DESCRIPTION
            asset_text         TEXT,
            performance_label  TEXT,
            impressions        INTEGER DEFAULT 0,
            clicks             INTEGER DEFAULT 0,
            PRIMARY KEY (date, ad_group_id, asset_id, field_type)
        );
    """)
    conn.commit()


def get_date_range(conn: sqlite3.Connection, table: str = "ads_campaigns"):
    row = conn.execute(f"SELECT MAX(date) FROM {table}").fetchone()[0]
    if row is None:
        start = date.today() - timedelta(days=INITIAL_DAYS)
    else:
        start = date.fromisoformat(row) - timedelta(days=REFRESH_DAYS)
    end = date.today() - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def fetch_campaigns(client, start_date: str, end_date: str) -> list[dict]:
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            segments.date,
            campaign.id,
            campaign.name,
            campaign.advertising_channel_type,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND campaign.status != 'REMOVED'
        ORDER BY segments.date, campaign.id
    """
    stream = ga_service.search_stream(customer_id=CUSTOMER_ID, query=query)
    rows = []
    for batch in stream:
        for row in batch.results:
            rows.append({
                "date":          row.segments.date,
                "campaign_id":   row.campaign.id,
                "campaign_name": row.campaign.name,
                "campaign_type": row.campaign.advertising_channel_type.name,
                "status":        row.campaign.status.name,
                "impressions":   row.metrics.impressions,
                "clicks":        row.metrics.clicks,
                "cost_micros":   row.metrics.cost_micros,
                "conversions":   row.metrics.conversions,
                "conv_value":    row.metrics.conversions_value,
            })
    return rows


def fetch_keywords(client, start_date: str, end_date: str) -> list[dict]:
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            segments.date,
            campaign.id,
            ad_group.id,
            ad_group_criterion.criterion_id,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND campaign.advertising_channel_type = 'SEARCH'
          AND ad_group_criterion.status != 'REMOVED'
        ORDER BY segments.date, campaign.id
    """
    stream = ga_service.search_stream(customer_id=CUSTOMER_ID, query=query)
    rows = []
    for batch in stream:
        for row in batch.results:
            rows.append({
                "date":         row.segments.date,
                "campaign_id":  row.campaign.id,
                "ad_group_id":  row.ad_group.id,
                "keyword_id":   row.ad_group_criterion.criterion_id,
                "keyword_text": row.ad_group_criterion.keyword.text,
                "match_type":   row.ad_group_criterion.keyword.match_type.name,
                "impressions":  row.metrics.impressions,
                "clicks":       row.metrics.clicks,
                "cost_micros":  row.metrics.cost_micros,
                "conversions":  row.metrics.conversions,
            })
    return rows


def fetch_search_terms(client, start_date: str, end_date: str) -> list[dict]:
    # Google Ads only retains search terms for ~90 days
    cutoff = (date.today() - timedelta(days=89)).isoformat()
    start_date = max(start_date, cutoff)

    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            segments.date,
            campaign.id,
            ad_group.id,
            search_term_view.search_term,
            segments.keyword.info.match_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND search_term_view.status != 'EXCLUDED'
        ORDER BY segments.date, campaign.id
    """
    stream = ga_service.search_stream(customer_id=CUSTOMER_ID, query=query)
    rows = []
    for batch in stream:
        for row in batch.results:
            rows.append({
                "date":        row.segments.date,
                "campaign_id": row.campaign.id,
                "ad_group_id": row.ad_group.id,
                "search_term": row.search_term_view.search_term,
                "match_type":  row.segments.keyword.info.match_type.name
                               if row.segments.keyword.info.match_type else None,
                "impressions": row.metrics.impressions,
                "clicks":      row.metrics.clicks,
                "cost_micros": row.metrics.cost_micros,
                "conversions": row.metrics.conversions,
            })
    return rows


def fetch_demographics(client, start_date: str, end_date: str) -> list[dict]:
    """Age and gender — aggregated to campaign level (the raw views are ad-group level)."""
    ga_service = client.get_service("GoogleAdsService")
    agg: dict = {}   # (date, campaign_id, dimension, segment_value) → [impr, clicks, cost, conv]

    def add(key, impressions, clicks, cost_micros, conversions):
        bucket = agg.setdefault(key, [0, 0, 0, 0.0])
        bucket[0] += impressions
        bucket[1] += clicks
        bucket[2] += cost_micros
        bucket[3] += conversions

    age_query = f"""
        SELECT
            segments.date,
            campaign.id,
            ad_group_criterion.age_range.type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM age_range_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
    """
    for batch in ga_service.search_stream(customer_id=CUSTOMER_ID, query=age_query):
        for row in batch.results:
            key = (row.segments.date, row.campaign.id, "age_range",
                   row.ad_group_criterion.age_range.type_.name)
            add(key, row.metrics.impressions, row.metrics.clicks,
                row.metrics.cost_micros, row.metrics.conversions)

    gender_query = f"""
        SELECT
            segments.date,
            campaign.id,
            ad_group_criterion.gender.type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM gender_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
    """
    for batch in ga_service.search_stream(customer_id=CUSTOMER_ID, query=gender_query):
        for row in batch.results:
            key = (row.segments.date, row.campaign.id, "gender",
                   row.ad_group_criterion.gender.type_.name)
            add(key, row.metrics.impressions, row.metrics.clicks,
                row.metrics.cost_micros, row.metrics.conversions)

    return [
        {
            "date": d, "campaign_id": cid, "dimension": dim, "segment_value": seg,
            "impressions": v[0], "clicks": v[1], "cost_micros": v[2], "conversions": v[3],
        }
        for (d, cid, dim, seg), v in agg.items()
    ]


def fetch_creative_assets(client, start_date: str, end_date: str) -> list[dict]:
    """RSA assets (headlines/descriptions): text + performance_label + impressions/clicks."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            segments.date,
            campaign.id,
            ad_group.id,
            asset.id,
            asset.text_asset.text,
            ad_group_ad_asset_view.field_type,
            ad_group_ad_asset_view.performance_label,
            metrics.impressions,
            metrics.clicks
        FROM ad_group_ad_asset_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND ad_group_ad_asset_view.field_type IN ('HEADLINE', 'DESCRIPTION')
    """
    rows = []
    for batch in ga_service.search_stream(customer_id=CUSTOMER_ID, query=query):
        for row in batch.results:
            rows.append({
                "date":              row.segments.date,
                "campaign_id":       row.campaign.id,
                "ad_group_id":       row.ad_group.id,
                "asset_id":          row.asset.id,
                "field_type":        row.ad_group_ad_asset_view.field_type.name,
                "asset_text":        row.asset.text_asset.text,
                "performance_label": row.ad_group_ad_asset_view.performance_label.name,
                "impressions":       row.metrics.impressions,
                "clicks":            row.metrics.clicks,
            })
    return rows


def upsert(conn, table: str, rows: list[dict]):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" * len(cols))
    update_set = ", ".join(f"{c}=excluded.{c}" for c in cols
                           if c not in ("date", "campaign_id", "ad_group_id",
                                        "keyword_id", "search_term",
                                        "dimension", "segment_value",
                                        "asset_id", "field_type"))
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
           f" ON CONFLICT DO UPDATE SET {update_set}")
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    start_date, end_date = get_date_range(conn)
    print(f"Period: {start_date} → {end_date}")

    client = get_client()

    print("Campaigns...", end=" ", flush=True)
    camps = fetch_campaigns(client, start_date, end_date)
    n = upsert(conn, "ads_campaigns", camps)
    conn.commit()
    print(f"{n} rows")

    print("Keywords...", end=" ", flush=True)
    kws = fetch_keywords(client, start_date, end_date)
    n = upsert(conn, "ads_keywords", kws)
    conn.commit()
    print(f"{n} rows")

    print("Search terms (last 90 days)...", end=" ", flush=True)
    sts = fetch_search_terms(client, start_date, end_date)
    n = upsert(conn, "ads_search_terms", sts)
    conn.commit()
    print(f"{n} rows")

    demo_start, demo_end = get_date_range(conn, "ads_demographics")
    print("Demographics (age/gender)...", end=" ", flush=True)
    demo = fetch_demographics(client, demo_start, demo_end)
    n = upsert(conn, "ads_demographics", demo)
    conn.commit()
    print(f"{n} rows")

    asset_start, asset_end = get_date_range(conn, "ads_creative_assets")
    print("RSA assets (headlines/descriptions)...", end=" ", flush=True)
    assets = fetch_creative_assets(client, asset_start, asset_end)
    n = upsert(conn, "ads_creative_assets", assets)
    conn.commit()
    print(f"{n} rows")

    # Summary
    print("\n=== LOADED ===")
    for tbl in ("ads_campaigns", "ads_keywords", "ads_search_terms",
                "ads_demographics", "ads_creative_assets"):
        row = conn.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {tbl}").fetchone()
        print(f"  {tbl:<22} {row[0]:>7} rows | {row[1]} → {row[2]}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
