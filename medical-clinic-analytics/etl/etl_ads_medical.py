"""
ETL: Google Ads → medical_ads.db
Аккаунт медицинской клиники, период: доступная история.
Исключаем кампанию-зомби 21516649341 (завершённый эксперимент).
"""

import os, sys, sqlite3
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path("C:/projects/my-project/google_ads/.env"), override=True)

sys.path.insert(0, str(Path("C:/projects/my-project")))
from google.ads.googleads.client import GoogleAdsClient

CUSTOMER_ID  = "5159672135"
EXCLUDE_CAMP = 21516649341   # кампания-зомби, исключать везде
DB_PATH      = Path(__file__).parent.parent / "data" / "medical_ads.db"
INITIAL_DAYS = 540
REFRESH_DAYS = 7


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
    """)
    conn.commit()


def get_date_range(conn: sqlite3.Connection):
    row = conn.execute("SELECT MAX(date) FROM ads_campaigns").fetchone()[0]
    if row is None:
        start = date.today() - timedelta(days=INITIAL_DAYS)
    else:
        start = date.fromisoformat(row) - timedelta(days=REFRESH_DAYS)
    end = date.today() - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def fetch_campaigns(client, start_date, end_date):
    svc = client.get_service("GoogleAdsService")
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
          AND campaign.id != {EXCLUDE_CAMP}
        ORDER BY segments.date, campaign.id
    """
    rows = []
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
        for r in batch.results:
            rows.append({
                "date":          r.segments.date,
                "campaign_id":   r.campaign.id,
                "campaign_name": r.campaign.name,
                "campaign_type": r.campaign.advertising_channel_type.name,
                "status":        r.campaign.status.name,
                "impressions":   r.metrics.impressions,
                "clicks":        r.metrics.clicks,
                "cost_micros":   r.metrics.cost_micros,
                "conversions":   r.metrics.conversions,
                "conv_value":    r.metrics.conversions_value,
            })
    return rows


def fetch_keywords(client, start_date, end_date):
    svc = client.get_service("GoogleAdsService")
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
          AND campaign.id != {EXCLUDE_CAMP}
        ORDER BY segments.date, campaign.id
    """
    rows = []
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
        for r in batch.results:
            rows.append({
                "date":         r.segments.date,
                "campaign_id":  r.campaign.id,
                "ad_group_id":  r.ad_group.id,
                "keyword_id":   r.ad_group_criterion.criterion_id,
                "keyword_text": r.ad_group_criterion.keyword.text,
                "match_type":   r.ad_group_criterion.keyword.match_type.name,
                "impressions":  r.metrics.impressions,
                "clicks":       r.metrics.clicks,
                "cost_micros":  r.metrics.cost_micros,
                "conversions":  r.metrics.conversions,
            })
    return rows


def fetch_search_terms(client, start_date, end_date):
    cutoff = (date.today() - timedelta(days=89)).isoformat()
    start_date = max(start_date, cutoff)

    svc = client.get_service("GoogleAdsService")
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
          AND campaign.id != {EXCLUDE_CAMP}
        ORDER BY segments.date, campaign.id
    """
    rows = []
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
        for r in batch.results:
            rows.append({
                "date":        r.segments.date,
                "campaign_id": r.campaign.id,
                "ad_group_id": r.ad_group.id,
                "search_term": r.search_term_view.search_term,
                "match_type":  r.segments.keyword.info.match_type.name
                               if r.segments.keyword.info.match_type else None,
                "impressions": r.metrics.impressions,
                "clicks":      r.metrics.clicks,
                "cost_micros": r.metrics.cost_micros,
                "conversions": r.metrics.conversions,
            })
    return rows


def upsert(conn, table, rows):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" * len(cols))
    skip = {"date", "campaign_id", "ad_group_id", "keyword_id", "search_term"}
    update_set = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in skip)
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
           f" ON CONFLICT DO UPDATE SET {update_set}")
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    start_date, end_date = get_date_range(conn)
    print(f"Период: {start_date} → {end_date}")

    client = get_client()

    print("Кампании...", end=" ", flush=True)
    n = upsert(conn, "ads_campaigns", fetch_campaigns(client, start_date, end_date))
    conn.commit(); print(f"{n} строк")

    print("Ключевые слова...", end=" ", flush=True)
    n = upsert(conn, "ads_keywords", fetch_keywords(client, start_date, end_date))
    conn.commit(); print(f"{n} строк")

    print("Поисковые запросы (≤90 дней)...", end=" ", flush=True)
    n = upsert(conn, "ads_search_terms", fetch_search_terms(client, start_date, end_date))
    conn.commit(); print(f"{n} строк")

    print("\n=== ЗАГРУЖЕНО ===")
    for tbl in ("ads_campaigns", "ads_keywords", "ads_search_terms"):
        r = conn.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {tbl}").fetchone()
        print(f"  {tbl:<22} {r[0]:>7} строк | {r[1]} → {r[2]}")

    conn.close()
    print("\nГотово.")


if __name__ == "__main__":
    main()
