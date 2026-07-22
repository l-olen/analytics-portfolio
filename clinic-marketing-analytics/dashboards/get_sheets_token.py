"""
Получить токен для Google Sheets API (один раз).
Токен сохраняется в dashboards/sheets_token.json.

Запуск:
  python dashboards/get_sheets_token.py

Требует: CLIENT_ID, CLIENT_SECRET в google_ads/.env
"""

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).parent.parent
ENV_FILE = Path(r"C:\projects\my-project\google_ads\.env")
TOKEN_FILE = Path(__file__).parent / "sheets_token.json"

if not ENV_FILE.exists():
    # Попробуем найти .env рядом
    for candidate in [ROOT / ".env", ROOT.parent / ".env"]:
        if candidate.exists():
            ENV_FILE = candidate
            break
    else:
        print("! .env файл не найден. Укажите CLIENT_ID и CLIENT_SECRET вручную.")
        sys.exit(1)

load_dotenv(ENV_FILE)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

client_config = {
    "installed": {
        "client_id":     os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

print("Открываю браузер для авторизации Google Sheets...")
print("Войдите как olenjova@gmail.com\n")

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)

token_data = {
    "refresh_token": creds.refresh_token,
    "client_id":     os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
}

TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
print(f"Токен сохранён: {TOKEN_FILE}")
print("Теперь запустите: python dashboards/upload_to_sheets.py")
