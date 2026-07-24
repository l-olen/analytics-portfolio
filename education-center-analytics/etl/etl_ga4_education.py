# Выгружает данные GA4 образовательного центра → education.db

from pathlib import Path
from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os, sqlite3

load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path("C:/projects/my-project/google_ads/.env"), override=True)

DB_PATH     = Path(__file__).parent.parent / "data" / "education.db"
PROPERTY_ID = "428073715"   # GA4 property
START_DATE  = "2025-07-01"
END_DATE    = "2026-06-30"

PAID_MEDIUMS = {"cpc", "cross-network"}


def _ga4_client():
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("REFRESH_TOKEN"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    creds.refresh(Request())
    return BetaAnalyticsDataClient(credentials=creds)


def fetch_sessions(conn):
    client = _ga4_client()
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=START_DATE, end_date=END_DATE)],
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagedSessions"),
            Metric(name="conversions"),
            Metric(name="averageSessionDuration"),
            Metric(name="engagementRate"),
        ],
    )
    response = client.run_report(request)
    rows = []
    for row in response.rows:
        date, channel = row.dimension_values[0].value, row.dimension_values[1].value
        rows.append((
            date, channel,
            int(row.metric_values[0].value),
            int(row.metric_values[1].value),
            float(row.metric_values[2].value),
            float(row.metric_values[3].value),
            float(row.metric_values[4].value),
        ))
    conn.executemany("""
        INSERT OR REPLACE INTO ga4_sessions
        (date, channel, sessions, engaged_sessions, conversions, avg_duration_sec, engagement_rate)
        VALUES (?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    print(f"  Загружено строк: {len(rows)}")


def fetch_events(conn):
    client = _ga4_client()
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=START_DATE, end_date=END_DATE)],
        dimensions=[
            Dimension(name="date"),
            Dimension(name="eventName"),
            Dimension(name="sessionMedium"),
        ],
        metrics=[Metric(name="eventCount")],
    )
    response = client.run_report(request)

    agg: dict = {}
    for row in response.rows:
        date     = row.dimension_values[0].value
        event    = row.dimension_values[1].value
        medium   = row.dimension_values[2].value.lower()
        count    = int(row.metric_values[0].value)
        is_paid  = medium in PAID_MEDIUMS
        key = (date, event)
        if key not in agg:
            agg[key] = [0, 0]
        agg[key][0] += count
        if is_paid:
            agg[key][1] += count

    rows = [(d, e, v[0], v[1]) for (d, e), v in agg.items()]
    conn.executemany("""
        INSERT OR REPLACE INTO ga4_events (date, event_label, total, paid)
        VALUES (?,?,?,?)
    """, rows)
    conn.commit()
    print(f"  Загружено строк: {len(rows)}")


def main():
    conn = sqlite3.connect(DB_PATH)
    print("GA4: тяну сессии...")
    fetch_sessions(conn)
    print("GA4: тяну события...")
    fetch_events(conn)
    conn.close()
    print("\nГотово.")


if __name__ == "__main__":
    main()
