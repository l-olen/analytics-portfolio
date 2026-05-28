import sys
import datetime
import requests
import xml.etree.ElementTree as ET
import xlwings as xw
from pathlib import Path

CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp?date_req={date}"

TARGET_PATH = Path(
    r"C:\projects\my-project\ОМТ\Еженедельный отчёт\КурсыВалют.xlsx"
)

# sheet_name -> (rate_key, decimal_places)
SHEET_MAP = {
    "KZT-RUB": ("KZT_RUB", 2),
    "USD-KZT":  ("KZT",    2),
    "USD-UZS":  ("UZS",    2),
    "USD-KGS":  ("KGS",    4),
    "USD-TJS":  ("TJS",    3),
    "USD-RUB":  ("RUB",    4),
}

# CBR character codes for each currency
CBR_CODES = {"USD", "KZT", "UZS", "KGS", "TJS"}


def fetch_cbr_rates(date: datetime.date) -> dict:
    """
    Fetch official rates from CBR for given date.
    CBR does not publish on weekends — on Sat/Sun the request
    returns Friday's rates automatically.
    Returns dict with calculated pairs vs USD and KZT/RUB.
    """
    date_str = date.strftime("%d/%m/%Y")
    url = CBR_URL.format(date=date_str)
    try:
        resp = requests.get(url, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети: {e}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"HTTP ошибка: {resp.status_code}")
        sys.exit(1)

    # CBR uses windows-1251 encoding
    root = ET.fromstring(resp.content.decode("windows-1251"))

    # Parse: rate per 1 unit vs RUB (value / nominal)
    rub_rates = {}
    for valute in root.findall("Valute"):
        code = valute.find("CharCode").text
        if code in CBR_CODES:
            nominal = int(valute.find("Nominal").text)
            value = float(valute.find("Value").text.replace(",", "."))
            rub_rates[code] = value / nominal  # X RUB per 1 unit of currency

    missing = CBR_CODES - set(rub_rates.keys())
    if missing:
        print(f"Валюты не найдены в ответе ЦБР: {missing}")
        sys.exit(1)

    usd = rub_rates["USD"]   # RUB per 1 USD
    kzt = rub_rates["KZT"]   # RUB per 1 KZT
    uzs = rub_rates["UZS"]   # RUB per 1 UZS
    kgs = rub_rates["KGS"]   # RUB per 1 KGS
    tjs = rub_rates["TJS"]   # RUB per 1 TJS

    return {
        "RUB":     usd,           # USD/RUB: сколько рублей за 1 доллар
        "KZT":     usd / kzt,     # USD/KZT: сколько тенге за 1 доллар
        "UZS":     usd / uzs,     # USD/UZS: сколько сум за 1 доллар
        "KGS":     usd / kgs,     # USD/KGS: сколько сом за 1 доллар
        "TJS":     usd / tjs,     # USD/TJS: сколько сомони за 1 доллар
        "KZT_RUB": 1.0 / kzt,     # KZT/RUB: сколько тенге за 1 рубль
    }


def last_row_in_sheet(ws) -> tuple[int, datetime.datetime | None, float | None]:
    last_row = ws.range("A1").end("down").row
    if last_row == 1:
        return 1, None, None

    last_dt = None
    last_val = None
    for r in range(2, last_row + 1):
        d = ws.range(f"A{r}").value
        v = ws.range(f"B{r}").value
        if isinstance(d, datetime.datetime) and v is not None:
            last_dt = d
            last_val = v

    return last_row, last_dt, last_val


def dates_to_fill(last_dt: datetime.datetime | None) -> list[datetime.datetime]:
    today = datetime.datetime.combine(datetime.date.today(), datetime.time())
    if last_dt is None:
        return [today]
    start = last_dt + datetime.timedelta(days=1)
    result = []
    current = start
    while current <= today:
        result.append(current)
        current += datetime.timedelta(days=1)
    return result


def main():
    today = datetime.date.today()
    print(f"Запуск: {today}\n")

    # Collect rates for all dates we need to fill
    # Determine date range from the first sheet
    if not TARGET_PATH.exists():
        print(f"Файл не найден: {TARGET_PATH}")
        sys.exit(1)

    app = xw.App(visible=False)
    wb = None
    try:
        wb = app.books.open(str(TARGET_PATH))

        # Find the range of missing dates from the first sheet
        first_sheet = wb.sheets[SHEET_MAP and list(SHEET_MAP.keys())[0]]
        _, last_dt, _ = last_row_in_sheet(first_sheet)
        missing_dates = dates_to_fill(last_dt)

        if not missing_dates:
            print("Нет новых данных для записи.")
            return

        # Fetch rates per date from CBR
        # CBR handles weekends automatically:
        # Saturday has its own official rate, Sunday returns Saturday's rate
        rates_cache: dict[datetime.date, dict] = {}
        for dt in missing_dates:
            d = dt.date()
            rates = fetch_cbr_rates(d)
            rates_cache[d] = rates
            print(f"  CBR {d}: USD/RUB={rates['RUB']:.4f}  KZT/RUB={rates['KZT_RUB']:.2f}")

        print()
        total_added = 0

        for sheet_name, (rate_key, decimals) in SHEET_MAP.items():
            sheet_names = [s.name for s in wb.sheets]
            if sheet_name not in sheet_names:
                print(f"  Лист '{sheet_name}' не найден, пропуск")
                continue

            ws = wb.sheets[sheet_name]
            last_row, _, _ = last_row_in_sheet(ws)

            for dt in missing_dates:
                d = dt.date()
                value = round(rates_cache[d][rate_key], decimals)

                last_row += 1
                ws.range(f"A{last_row}").value = dt
                ws.range(f"B{last_row}").value = value
                total_added += 1

            print(f"  [{sheet_name}] добавлено {len(missing_dates)} дней")

        wb.save()
        print(f"\nФайл сохранён: {TARGET_PATH.name}")

    finally:
        if wb is not None:
            try:
                wb.close(save_changes=False)
            except Exception:
                pass
        try:
            app.kill()  # принудительное завершение Excel-процесса
        except Exception:
            pass


if __name__ == "__main__":
    main()
