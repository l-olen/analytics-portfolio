import os, sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
)
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path("C:/projects/my-project/google_ads/.env"), override=True)

DB_PATH = Path(__file__).parent.parent / "data" / "medical.db"
PROPERTY_ID = "426154993"       # GA4 property
START_DATE  = "2025-07-01"
END_DATE    = "2026-06-30"


def _ga4_client() -> BetaAnalyticsDataClient:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    creds.refresh(Request())
    return BetaAnalyticsDataClient(credentials=creds)


def fetch_sessions(conn):
    """Сессии и конверсии по каналу (Paid Search, Cross-network, Organic Search, ...) по дням."""
    print("GA4: тяну сессии по каналам...")
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
    total = 0

    for row in response.rows:
        raw_date = row.dimension_values[0].value   # "20250701"
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        channel = row.dimension_values[1].value

        sessions       = int(row.metric_values[0].value or 0)
        engaged        = int(row.metric_values[1].value or 0)
        conversions    = float(row.metric_values[2].value or 0)
        avg_duration   = float(row.metric_values[3].value or 0)
        engagement_rate = float(row.metric_values[4].value or 0)

        conn.execute("""
            INSERT OR REPLACE INTO ga4_sessions
                (date, channel, sessions, engaged_sessions, conversions,
                 avg_duration_sec, engagement_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date, channel, sessions, engaged, round(conversions, 2),
              round(avg_duration, 1), round(engagement_rate, 4)))
        total += 1

    conn.commit()
    print(f"  Записано строк: {total}")


def fetch_events(conn):
    """Конверсионные события по дням: сколько всего и сколько из платного трафика."""
    print("GA4: тяну конверсионные события...")
    client = _ga4_client()

    # Все конверсии по событию и medium
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

    # Группируем в памяти: date + eventName → {total, paid}
    agg = {}  # (date, event_label) → [total, paid]

    PAID_MEDIUMS = {"cpc", "cross-network"}

    for row in response.rows:
        raw_date = row.dimension_values[0].value
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        event = row.dimension_values[1].value
        medium = row.dimension_values[2].value.lower()
        count = int(row.metric_values[0].value or 0)

        key = (date, event)
        if key not in agg:
            agg[key] = [0, 0]
        agg[key][0] += count
        if medium in PAID_MEDIUMS:
            agg[key][1] += count

    for (date, event), (total, paid) in agg.items():
        conn.execute("""
            INSERT OR REPLACE INTO ga4_events (date, event_label, total, paid)
            VALUES (?, ?, ?, ?)
        """, (date, event, total, paid))

    conn.commit()
    print(f"  Записано строк: {len(agg)}")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    fetch_sessions(conn)
    fetch_events(conn)
    conn.close()
    print("\nГотово.")
