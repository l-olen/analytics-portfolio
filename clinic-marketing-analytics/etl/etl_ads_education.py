"""
ETL: Google Ads → education_ads.db
Аккаунт образовательного центра, период: доступная история.
Таблицы:
  ads_campaigns   — daily performance по кампаниям
  ads_keywords    — daily performance по ключевым словам (только Search)
  ads_search_terms — поисковые запросы (последние 90 дней, Google Ads limit)
"""

import os, sys, sqlite3
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path("C:/projects/my-project/google_ads/.env"), override=True)

sys.path.insert(0, str(Path("C:/projects/my-project")))
from google.ads.googleads.client import GoogleAdsClient

# ============================================================
CUSTOMER_ID = "6355895321"
DB_PATH = Path(__file__).parent.parent / "data" / "education_ads.db"
# Сколько дней истории тянуть при первом запуске
INITIAL_DAYS = 540   # ~18 месяцев
# При повторных — перекрываем последние N дней (обновляются с задержкой)
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
    # Google Ads хранит search terms только ~90 дней
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


def upsert(conn, table: str, rows: list[dict]):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" * len(cols))
    update_set = ", ".join(f"{c}=excluded.{c}" for c in cols
                           if c not in ("date", "campaign_id", "ad_group_id",
                                        "keyword_id", "search_term"))
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
    camps = fetch_campaigns(client, start_date, end_date)
    n = upsert(conn, "ads_campaigns", camps)
    conn.commit()
    print(f"{n} строк")

    print("Ключевые слова...", end=" ", flush=True)
    kws = fetch_keywords(client, start_date, end_date)
    n = upsert(conn, "ads_keywords", kws)
    conn.commit()
    print(f"{n} строк")

    print("Поисковые запросы (≤90 дней)...", end=" ", flush=True)
    sts = fetch_search_terms(client, start_date, end_date)
    n = upsert(conn, "ads_search_terms", sts)
    conn.commit()
    print(f"{n} строк")

    # Сводка
    print("\n=== ЗАГРУЖЕНО ===")
    for tbl in ("ads_campaigns", "ads_keywords", "ads_search_terms"):
        row = conn.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {tbl}").fetchone()
        print(f"  {tbl:<22} {row[0]:>7} строк | {row[1]} → {row[2]}")

    conn.close()
    print("\nГотово.")


if __name__ == "__main__":
    main()
