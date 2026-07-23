"""
Загрузка АНОНИМИЗИРОВАННЫХ CSV (dashboards/csv_demo/, после anonymize_csv.py)
в Google Sheets для публичного Looker Studio дашборда портфолио.

Данные уже анонимизированы (spend x12, volume x4, названия клиентов и
кампаний заменены) — эти таблицы безопасно делать доступными по ссылке.
НЕ использовать для реальных, не анонимизированных данных.

Сначала получите токен:
  python dashboards/get_sheets_token.py

Затем прогоните пайплайн анонимизации и загрузите:
  python dashboards/anonymize_csv.py
  python dashboards/upload_to_sheets.py

Создаёт (или обновляет) две таблицы:
  "Education Center — Dashboard Data"
  "Medical Center — Dashboard Data"

Ссылки на таблицы выводятся в конце.
"""

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

DASH_DIR = Path(__file__).parent
TOKEN_FILE = DASH_DIR / "sheets_token.json"
CSV_DIR    = DASH_DIR / "csv_demo"


def load_credentials():
    if not TOKEN_FILE.exists():
        print("! Токен не найден. Запустите сначала:")
        print("    python dashboards/get_sheets_token.py")
        sys.exit(1)

    data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    creds = Credentials(
        token=None,
        refresh_token=data["refresh_token"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ],
    )
    creds.refresh(Request())
    return creds


def read_csv(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def upload_group(gc, title: str, csv_files: list[tuple[str, Path]]) -> str:
    """Создаёт или обновляет таблицу, загружает вкладки из CSV."""
    try:
        sh = gc.open(title)
        print(f"\n  Обновляю существующую таблицу: {title}")
    except gspread.SpreadsheetNotFound:
        sh = gc.create(title)
        # Разрешаем просмотр всем (для Looker Studio без дополнительных прав)
        sh.share(None, perm_type="anyone", role="reader")
        print(f"\n  Создана новая таблицу: {title}")

    existing_titles = [ws.title for ws in sh.worksheets()]

    for tab_name, csv_path in csv_files:
        if not csv_path.exists():
            print(f"  ! {csv_path.name} не найден, пропускаем")
            continue

        data = read_csv(csv_path)
        rows_n = len(data) - 1  # минус заголовок

        if tab_name in existing_titles:
            ws = sh.worksheet(tab_name)
            ws.clear()
        else:
            ws = sh.add_worksheet(title=tab_name, rows=max(rows_n + 10, 50), cols=20)

        ws.update(data)
        print(f"  OK {tab_name:<30} ({rows_n} строк)")

    # Удаляем пустой Sheet1 если он есть и не нужен
    tab_names = [t for t, _ in csv_files]
    try:
        default = sh.worksheet("Sheet1")
        if "Sheet1" not in tab_names and len(sh.worksheets()) > 1:
            sh.del_worksheet(default)
    except gspread.WorksheetNotFound:
        pass

    return sh.url


def main():
    print("Загрузка анонимизированных данных в Google Sheets...")
    creds = load_credentials()
    gc = gspread.authorize(creds)

    # ── EDUCATION CENTER ──────────────────────────────────────
    education_files = [
        ("channel_funnel",   CSV_DIR / "education_channel_funnel.csv"),
        ("monthly_trend",    CSV_DIR / "education_monthly_trend.csv"),
        ("channel_monthly",  CSV_DIR / "education_channel_monthly.csv"),
        ("ads_campaigns",    CSV_DIR / "education_ads_campaigns.csv"),
        ("ads_monthly",      CSV_DIR / "education_ads_monthly.csv"),
        ("audience",         CSV_DIR / "education_audience.csv"),
        ("creative_themes",  CSV_DIR / "education_creative_themes.csv"),
    ]

    url_education = upload_group(gc,
        "Education Center — Dashboard Data",
        education_files)

    # ── MEDICAL CENTER ─────────────────────────────────────────
    medical_files = [
        ("channel_funnel",   CSV_DIR / "medical_channel_funnel.csv"),
        ("monthly_trend",    CSV_DIR / "medical_monthly_trend.csv"),
        ("ga4_channels",     CSV_DIR / "medical_ga4_channels.csv"),
        ("ga4_monthly",      CSV_DIR / "medical_ga4_monthly.csv"),
        ("ga4_events",       CSV_DIR / "medical_ga4_events.csv"),
        ("appointments",     CSV_DIR / "medical_appointments.csv"),
    ]

    url_medical = upload_group(gc,
        "Medical Center — Dashboard Data",
        medical_files)

    # ── ИТОГ ────────────────────────────────────────────────
    print("\n" + "="*60)
    print("ДАННЫЕ ЗАГРУЖЕНЫ")
    print("="*60)
    print(f"\nEducation Center Sheets: {url_education}")
    print(f"Medical Center Sheets: {url_medical}")
    print("""
Следующий шаг — Looker Studio:
  1. Откройте lookerstudio.google.com
  2. Создать > Отчёт > Добавить данные > Google Sheets
  3. Выберите "Education Center — Dashboard Data" → вкладку channel_funnel
  4. Создайте страницу с нужными чартами (см. структуру ниже)
  5. Повторите для Medical Center

Структура дашборда Education Center:
  Стр.1 "Воронка": Таблица channel_funnel + Pie Chart contacts по channel
  Стр.2 "Тренд": Line chart monthly_trend (contacts + won по месяцам)
  Стр.3 "Google Ads": Таблица ads_campaigns (spend/leads/CPL/CPA)
  Стр.4 "Каналы×Месяц": Heatmap из channel_monthly

Структура дашборда Medical Center:
  Стр.1 "Воронка": Таблица channel_funnel (source → qualified → appt)
  Стр.2 "Тренд Касания": Line chart monthly_trend
  Стр.3 "GA4": Bar chart ga4_channels (sessions + conv)
  Стр.4 "GA4 тренд": Line chart ga4_monthly по channel
""")


if __name__ == "__main__":
    main()
