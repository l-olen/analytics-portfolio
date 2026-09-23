# Pulls the education center's leads from AmoCRM into SQLite (education.db)

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
AMO_ENV_PATH = Path(os.getenv("SHARED_ENV_PATH", Path(__file__).parent / ".env"))
load_dotenv(AMO_ENV_PATH, override=True)

DB_PATH     = Path(__file__).parent.parent / "data" / "education.db"
SCHEMA_PATH = Path(__file__).parent / "schema_education.sql"

AMO_SUBDOMAIN   = os.environ["EDUCATION_AMO_SUBDOMAIN"]
AMO_BASE        = f"https://{AMO_SUBDOMAIN}.amocrm.ru"
SKIP_PIPELINES  = set()   # load everything, bot filtering happens via is_bot after load
WON             = 142
LOST            = 143

# Tags that identify the lead source (matched against the CRM's own tag names)
SITE_WEB_TAGS  = {"заказ с сайта", "сайт", "tilda"}
SITE_QUIZ_TAGS = {"квиз", "сайт квиз"}
CALL_TAGS      = {"555100400", "входящий", "пропущенный", os.environ["EDUCATION_CALL_TAG_EXTRA"]}

# AmoCRM custom field ID → database column
CF_MAP = {
    528579: "utm_source",
    528575: "utm_medium",
    528577: "utm_campaign",
    528573: "utm_content",
    528581: "utm_term",
    528605: "gclid",
    528607: "yclid",
    528609: "fbclid",
    528585: "roistat",
    528587: "referrer",
    528599: "gclientid",
    534651: "crm_source",
    539111: "study_location",
    893529: "grade_or_course",
    1583291: "inquiry_type",
    1583293: "instruction_language",
    1603123: "product",
    1631669: "abc_category",
    1638495: "ad_channel",
}

# Columns in INSERT order (excluding lead_id and is_bot)
CF_COLS = list(CF_MAP.values())


def _classify_source(tags_list: list[str]) -> str:
    tags_lower = {t.lower().strip() for t in tags_list}
    if tags_lower & SITE_QUIZ_TAGS:
        return "site_quiz"
    if tags_lower & SITE_WEB_TAGS:
        return "site_web"
    if tags_lower & CALL_TAGS:
        return "call"
    return "other"


def _extract_cf(cf_list: list) -> dict:
    result = {col: None for col in CF_COLS}
    for cf in (cf_list or []):
        fid = cf.get("field_id")
        if fid in CF_MAP:
            values = cf.get("values") or []
            if values:
                result[CF_MAP[fid]] = str(values[0].get("value", "")).strip() or None
    return result


def _migrate_columns(conn):
    """Adds new columns to an existing database (safe to re-run)."""
    new_cols = [
        ("utm_source", "TEXT"), ("utm_medium", "TEXT"), ("utm_campaign", "TEXT"),
        ("utm_content", "TEXT"), ("utm_term", "TEXT"), ("gclid", "TEXT"),
        ("yclid", "TEXT"), ("fbclid", "TEXT"), ("roistat", "TEXT"), ("referrer", "TEXT"),
        ("gclientid", "TEXT"),
        ("crm_source", "TEXT"), ("study_location", "TEXT"), ("grade_or_course", "TEXT"),
        ("inquiry_type", "TEXT"), ("instruction_language", "TEXT"), ("product", "TEXT"),
        ("abc_category", "TEXT"), ("ad_channel", "TEXT"),
    ]
    for col, typ in new_cols:
        try:
            conn.execute(f"ALTER TABLE crm_leads ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass  # already there


# BUNKER_AMO_ACCESS_TOKEN -- долгосрочный токен приватной интеграции (до 5 лет), не OAuth-пара.
# Нет refresh_token -- если истечёт, вручную сгенерировать новый в amoCRM
# (Настройки -> Интеграции -> эта интеграция -> "Ключи и доступы") и обновить
# BUNKER_AMO_ACCESS_TOKEN в google_ads/.env (SHARED_ENV_PATH).

def get_token() -> str:
    token = os.getenv("BUNKER_AMO_ACCESS_TOKEN", "")
    resp = requests.get(
        f"{AMO_BASE}/api/v4/leads",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 1},
    )
    if resp.status_code == 401:
        raise RuntimeError(
            "BUNKER_AMO_ACCESS_TOKEN истёк или невалиден -- сгенерировать новый долгосрочный "
            "токен вручную в amoCRM и обновить BUNKER_AMO_ACCESS_TOKEN в google_ads/.env"
        )
    return token


def _status(status_id: int) -> str:
    if status_id == WON:
        return "won"
    if status_id == LOST:
        return "lost"
    return "in_progress"


def fetch_leads(conn):
    token   = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Build the UPSERT: update every field EXCEPT is_bot (don't clear bot flags)
    base_cols = ["created_at", "created_date", "updated_at", "status", "source",
                 "tags", "price", "pipeline_id", "stage_id", "contact_id"]
    all_data_cols = base_cols + CF_COLS
    placeholders = ", ".join(["?"] * (1 + len(all_data_cols)))   # +1 для lead_id
    update_set = ", ".join(f"{c} = excluded.{c}" for c in all_data_cols)

    upsert_sql = f"""
        INSERT INTO crm_leads (lead_id, {", ".join(all_data_cols)})
        VALUES ({placeholders})
        ON CONFLICT(lead_id) DO UPDATE SET {update_set}
    """

    print("Loading full history (no date filter)...")
    total = 0
    page  = 1

    while True:
        resp = requests.get(
            f"{AMO_BASE}/api/v4/leads",
            headers=headers,
            params={
                "with": "tags,contacts,custom_fields_values",
                "limit": 250,
                "page":  page,
            },
        )
        if resp.status_code == 204:
            break
        data = resp.json()
        leads = data.get("_embedded", {}).get("leads", [])
        if not leads:
            break

        rows = []
        for lead in leads:
            pid = lead.get("pipeline_id")
            if pid in SKIP_PIPELINES:
                continue

            tags_list = [t["name"] for t in
                         lead.get("_embedded", {}).get("tags", [])]
            tags_str  = ", ".join(tags_list)
            source    = _classify_source(tags_list)

            contacts = lead.get("_embedded", {}).get("contacts", [])
            contact_id = contacts[0]["id"] if contacts else None

            created_ts = lead.get("created_at", 0)
            updated_ts = lead.get("updated_at", 0)
            created_dt = datetime.fromtimestamp(created_ts, tz=timezone.utc)

            cf = _extract_cf(lead.get("custom_fields_values"))

            rows.append((
                lead["id"],
                created_dt.strftime("%Y-%m-%d %H:%M:%S"),
                created_dt.strftime("%Y-%m-%d"),
                datetime.fromtimestamp(updated_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if updated_ts else None,
                _status(lead.get("status_id", 0)),
                source,
                tags_str,
                lead.get("price", 0) or 0,
                pid,
                lead.get("status_id"),
                contact_id,
                *[cf[c] for c in CF_COLS],
            ))

        conn.executemany(upsert_sql, rows)
        conn.commit()

        total += len(rows)
        if page % 10 == 0:
            print(f"  Page {page}: {total} leads so far")

        if len(leads) < 250:
            break
        page += 1

    print(f"\nTotal: {total} leads loaded")


def main():
    conn = sqlite3.connect(DB_PATH)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    _migrate_columns(conn)
    conn.commit()
    fetch_leads(conn)
    conn.close()


if __name__ == "__main__":
    main()
