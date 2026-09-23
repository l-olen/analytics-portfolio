# Pulls the clinic's leads from AmoCRM for the last 12 months into SQLite

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
AMO_ENV_PATH = Path(os.getenv("SHARED_ENV_PATH", Path(__file__).parent / ".env"))
load_dotenv(AMO_ENV_PATH, override=True)  # live AMO tokens always come from here

DB_PATH = Path(__file__).parent.parent / "data" / "medical.db"
SCHEMA_PATH = Path(__file__).parent / "schema_medical.sql"

AMO_SUBDOMAIN = os.environ["AYA_AMO_SUBDOMAIN"]
AMO_BASE = f"https://{AMO_SUBDOMAIN}.amocrm.ru"

SKIP_PIPELINES = {10457526, 10457530}
WON = 142
LOST = 143


# AYA_AMO_ACCESS_TOKEN -- долгосрочный токен приватной интеграции (до 5 лет), не OAuth-пара.
# Нет refresh_token -- если истечёт, вручную сгенерировать новый в amoCRM
# (Настройки -> Интеграции -> эта интеграция -> "Ключи и доступы") и обновить
# AYA_AMO_ACCESS_TOKEN в google_ads/.env (SHARED_ENV_PATH).

def _refresh_token() -> str:
    raise RuntimeError(
        "AYA_AMO_ACCESS_TOKEN истёк или невалиден -- сгенерировать новый долгосрочный "
        "токен вручную в amoCRM и обновить AYA_AMO_ACCESS_TOKEN в google_ads/.env"
    )


def get_token() -> str:
    return os.getenv("AYA_AMO_ACCESS_TOKEN", "")


def classify_source(tags: list, custom_fields: list) -> str:
    tags_lower = [t.lower() for t in tags]

    site_tags = ["заказ с сайта", "квиз", "сайт"]
    for st in site_tags:
        if any(st in tag for tag in tags_lower):
            for cf in custom_fields:
                if cf.get("field_name", "").lower() == "utm_medium":
                    vals = cf.get("values", [])
                    if vals and vals[0].get("value", "").lower() == "cpc":
                        return "site_paid"
            return "site_organic"

    call_tags = ["utel", "beeline", "ucell", "humans", "555155522", "входящий", "пропущенный"]
    for ct in call_tags:
        if any(ct in tag for tag in tags_lower):
            return "call"

    return "other"


def status_name(status_id: int) -> str:
    if status_id == WON:
        return "won"
    elif status_id == LOST:
        return "lost"
    return "in_progress"


def fetch_leads(conn):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    start = datetime(2025, 7, 1, tzinfo=timezone.utc)
    end   = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

    since = int(start.timestamp())
    until = int(end.timestamp())

    print(f"Period: {start.strftime('%Y-%m-%d')} — {end.strftime('%Y-%m-%d')}")

    total = 0
    page = 1

    while True:
        resp = requests.get(
            f"{AMO_BASE}/api/v4/leads",
            headers=headers,
            params={
                "filter[created_at][from]": since,
                "filter[created_at][to]": until,
                "with": "tags,custom_fields,contacts",
                "limit": 250,
                "page": page,
            },
        )

        if resp.status_code == 401:
            token = _refresh_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(resp.url, headers=headers)

        leads = resp.json().get("_embedded", {}).get("leads", [])
        if not leads:
            break

        for lead in leads:
            if lead.get("pipeline_id") in SKIP_PIPELINES:
                continue

            tags = [t["name"] for t in lead.get("_embedded", {}).get("tags", [])]
            fields = lead.get("custom_fields_values") or []
            contacts = lead.get("_embedded", {}).get("contacts", [])
            contact_id = contacts[0]["id"] if contacts else None

            conn.execute(
                """
                INSERT OR REPLACE INTO crm_leads
                    (lead_id, created_at, status, source, price, pipeline_id, contact_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lead["id"],
                    datetime.fromtimestamp(lead["created_at"]).strftime("%Y-%m-%d"),
                    status_name(lead.get("status_id")),
                    classify_source(tags, fields),
                    lead.get("price") or 0,
                    lead.get("pipeline_id"),
                    contact_id,
                    datetime.fromtimestamp(lead["updated_at"]).strftime("%Y-%m-%d"),
                ),
            )
            total += 1

        conn.commit()
        print(f"  Page {page}: {len(leads)} leads")

        if len(leads) < 250:
            break
        page += 1

    print(f"\nDone: {total} leads written")


def init_db(conn):
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        fetch_leads(conn)
    finally:
        conn.close()
