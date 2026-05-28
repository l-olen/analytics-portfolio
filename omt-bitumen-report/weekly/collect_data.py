"""
collect_data.py - Read weekly data from Excel sources for PPTX update.
Returns structured dict with all values needed for update_pptx.py.
"""
import sys
import io
import datetime
from pathlib import Path

import xlwings as xw

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"C:\projects\my-project\ОМТ\Еженедельный отчёт")
WEATHER_PATH = Path(r"C:\projects\my-project\ОМТ\Погода\weather_central_asia.xlsx")
PRICES_PATH = BASE / "Сборка_Цены.xlsx"
ZHD_PATH = BASE / "нов_ЖД_Сборка.xlsx"
RATES_PATH = BASE / "КурсыВалют.xlsx"
TARIFF_PATH = BASE / "Жд_тарифы.xlsx"
CENY_KAZ_PATH = BASE / "ЦеныКАЗ.xlsx"

MONTHS_RU = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель",
    5: "май", 6: "июнь", 7: "июль", 8: "август",
    9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
}

# Fixed producer list for RF prices table (Slide 2)
# Each entry: (region, company, npz_match_key)
# npz_match_key matches "Пункт отгрузки" in Excel; company also matched
RF_PRODUCERS = [
    ("Омская область",              "ООО «Газпромнефть-Битумные материалы»", "Омский НПЗ"),
    ("Оренбургская область",        "АО «ФортеИнвест»",                      "Орскнефтеоргсинтез"),
    ("Самарская область",           "ООО «РН-Битум»",                        "Новокуйбышевский НПЗ"),
    ("Рязанская область",           "ООО «РН-Битум»",                        "Рязанская НПК"),
    ("Самарская область",           "ООО «РН-Битум»",                        "Сызранский НПЗ"),
    ("Республика Башкортостан",     "ООО «РН-Битум»",                        "Уфимская группа НПЗ"),
    ("Ярославская область",         "ООО «Газпромнефть-Битумные материалы»", "Ярославнефтеоргсинтез"),
    ("Ярославская область",         "ООО «РН-Битум»",                        "Ярославнефтеоргсинтез"),
]


def _open(app, path):
    return app.books.open(str(path))


def _num(v):
    """Return v as float, 0 if None/empty/non-numeric (Excel sometimes returns str)."""
    if v is None:
        return 0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def collect_weather(app):
    wb = _open(app, WEATHER_PATH)
    sh = wb.sheets[0]
    lr = sh.used_range.last_cell.row
    rows = []
    for r in range(3, lr + 1):
        row = sh.range(f"A{r}:E{r}").value
        if row[0]:
            rows.append({
                "country": row[0],
                "city":    row[1],
                "t_min":   row[2],
                "t_max":   row[3],
                "t_avg":   row[4],
            })
    wb.close()
    return rows


# ---------------------------------------------------------------------------
# Currency rates
# ---------------------------------------------------------------------------

def collect_currency(app):
    wb = _open(app, RATES_PATH)
    sh = wb.sheets["Курсы_по_неделям"]
    lr = sh.used_range.last_cell.row
    cur = sh.range(f"A{lr}:O{lr}").value
    wb.close()
    # Col indices (0-based): E=4 KZT, F=5 UZS, G=6 KGS, H=7 TJS, I=8 RUB
    # Changes: K=10 KZT, L=11 UZS, M=12 RUB, N=13 KGS, O=14 TJS
    return {
        "date_from": cur[0],
        "date_to":   cur[1],
        "kzt":       cur[4],
        "uzs":       cur[5],
        "kgs":       cur[6],
        "tjs":       cur[7],
        "rub":       cur[8],
        "kzt_chg":   cur[10],
        "uzs_chg":   cur[11],
        "rub_chg":   cur[12],
        "kgs_chg":   cur[13],
        "tjs_chg":   cur[14],
    }


# ---------------------------------------------------------------------------
# Russian NPZ prices
# ---------------------------------------------------------------------------

def collect_rf_prices(app):
    """
    Returns (producers_list, report_friday_date).
    producers_list: list of dicts keyed by (npz_key, company), values=price data.
    """
    wb = _open(app, PRICES_PATH)
    sh = wb.sheets["РФ"]
    lr = sh.used_range.last_cell.row

    # Last aggregated row (rows 2..~14): get the Friday date
    report_date = None
    last_agg_row = None
    for r in range(2, 20):
        v = sh.range(f"A{r}").value
        if isinstance(v, datetime.datetime):
            last_agg_row = r
    if last_agg_row:
        report_date = sh.range(f"A{last_agg_row}").value  # Friday datetime

    # Find detail-rows header (contains "нач недели" or "Нач")
    header_row = None
    for r in range(20, min(40, lr + 1)):
        v = sh.range(f"A{r}").value
        if v and "ач" in str(v).lower():
            header_row = r
            break

    # Read detail rows: col indices (1-based in Excel → 0-based here)
    # A=0 НачНедели, B=1 Пятница, E=4 Пункт отгрузки (НПЗ), F=5 Компания
    # G=6 Ср цена с НДС, H=7 Ср цена без НДС, J=9 Изм.%, N=13 $/т, O=14 Изм.$/т%
    detail = {}  # (npz, company_short) → dict
    if header_row:
        for r in range(header_row + 1, lr + 1):
            row = sh.range(f"A{r}:P{r}").value
            npz     = row[4]
            company = row[5]
            if not npz:
                continue
            key = (npz, company)
            detail[key] = {
                "npz":         npz,
                "company":     company,
                "price_s_nds": row[6],
                "price_b_nds": row[7],
                "chg_rub":     row[9],
                "price_usd":   row[13],
                "chg_usd":     row[14],
                "is_total":    (company == "ВСЕ НПЗ (среднее)"),
            }

    wb.close()
    return detail, report_date


# ---------------------------------------------------------------------------
# Kazakhstan prices
# ---------------------------------------------------------------------------

def collect_kaz_prices(app):
    """
    Returns dict with Kazakhstan bitumen price data:
    - 'last': last weekly row (price_tg, price_usd, chg_tg, chg_usd, ytd_tg, ytd_usd, py_tg, py_usd, chg_ytd_tg, chg_py_tg)
    - 'history': last 6 weekly rows
    - 'producers': list of {name, price_tg, price_usd, chg_usd, period}
    - 'indicative_tg', 'indicative_usd', 'indicative_chg'
    """
    wb = _open(app, PRICES_PATH)
    sh = wb.sheets["Казахстан"]
    lr = sh.used_range.last_cell.row

    # Time series rows (rows 2..~20): header in row 1
    # Col indices (0-based): A=0 date, D=3 тг/т, E=4 $/т, F=5 chg_tg%, G=6 chg_usd%
    # H=7 нач_года_тг, I=8 изм_нач_года_тг%, J=9 нач_года_usd, K=10 изм_нач_года_usd%
    # L=11 ПГ_тг, M=12 ПГ_usd, N=13 изм_ПГ_тг%, O=14 изм_ПГ_usd%
    history = []
    for r in range(2, lr + 1):
        row = sh.range(f"A{r}:P{r}").value
        if not isinstance(row[0], datetime.datetime):
            break
        history.append({
            "date":        row[0],
            "price_tg":    row[3],
            "price_usd":   row[4],
            "chg_tg":      row[5],
            "chg_usd":     row[6],
            "ytd_tg":      row[7],
            "chg_ytd_tg":  row[8],
            "ytd_usd":     row[9],
            "chg_ytd_usd": row[10],
            "py_tg":       row[11],
            "py_usd":      row[12],
            "chg_py_tg":   row[13],
            "chg_py_usd":  row[14],
        })

    last = history[-1] if history else {}

    # Producer breakdown block: find header row with "Производитель"
    prod_header = None
    for r in range(20, min(35, lr + 1)):
        v = sh.range(f"A{r}").value
        if v and "роизвод" in str(v):
            prod_header = r
            break

    producers = []
    if prod_header:
        for r in range(prod_header + 1, min(prod_header + 15, lr + 1)):
            row = sh.range(f"A{r}:G{r}").value
            name = row[0]
            if not name or isinstance(name, datetime.datetime):
                break
            producers.append({
                "name":      name,
                "price_tg":  row[1],
                "chg_tg":    row[2],
                "price_usd": row[3],
                "chg_usd":   row[4],
                "period":    row[6],
            })

    # Summary block: find "Индикативная цена" row
    indicative = {}
    for r in range(lr - 10, lr + 1):
        row = sh.range(f"A{r}:D{r}").value
        if row[0] and "индикат" in str(row[0]).lower():
            indicative = {
                "price_tg":  row[1],
                "price_usd": row[2],
                "chg":       row[3],
            }
            break

    wb.close()
    return {
        "last":     last,
        "history":  history[-6:],
        "producers": producers,
        "indicative": indicative,
    }


# ---------------------------------------------------------------------------
# Kazakhstan ETS exchange
# ---------------------------------------------------------------------------

def collect_kaz_exchange(app):
    """
    Read KZ ETS exchange data from two sources:
    1. Сборка_Цены.xlsx "Казахстан" - ETS weekly table (right of producers)
       and summary block (SVZ/ETS/Indicative rows at bottom)
    2. ЦеныКАЗ.xlsx "Каз_ETS_база" - full ETS history to determine gap length
    Returns dict: {weekly, summary, history}
    """
    from xlwings.utils import col_name as cn

    wb = _open(app, PRICES_PATH)
    sh = wb.sheets["Казахстан"]
    lr = sh.used_range.last_cell.row
    lc = sh.used_range.last_cell.column

    # Find "Период" header by scanning rows then columns
    period_col = period_row = None
    for r in range(1, min(50, lr + 1)):
        for c in range(1, lc + 1):
            val = sh.range(f"{cn(c)}{r}").value
            if val and str(val).strip().lower() == "период":
                period_col, period_row = c, r
                break
        if period_col:
            break

    weekly = []
    if period_col and period_row:
        for r in range(period_row + 1, lr + 1):
            row = sh.range(f"{cn(period_col)}{r}:{cn(period_col + 3)}{r}").value
            if row[0] is None:
                break
            weekly.append({
                "period_str": str(row[0]).strip(),
                "price_tg":   row[1],
                "vol":        row[2],
                "deals":      row[3],
                "had_trades": bool(row[1]),
            })

    # Summary block: find "ETS" row (ETS биржа line at bottom of sheet)
    summary = {}
    for r in range(max(1, lr - 15), lr + 1):
        row = sh.range(f"A{r}:D{r}").value
        if row[0] and "ets" in str(row[0]).lower():
            summary = {
                "price_tg":  row[1],
                "price_usd": row[2],
                "chg":       row[3],
            }
            break

    wb.close()

    # Full history from ЦеныКАЗ.xlsx "Каз_ETS_база"
    history = []
    if CENY_KAZ_PATH.exists():
        try:
            wb2 = _open(app, CENY_KAZ_PATH)
            sh2 = wb2.sheets["Каз_ETS_база"]
            lr2 = sh2.used_range.last_cell.row
            # Find header row (first row with non-numeric text)
            header_row2 = 1
            for r in range(1, min(5, lr2 + 1)):
                v = sh2.range(f"A{r}").value
                if v and not isinstance(v, (int, float, datetime.datetime)):
                    header_row2 = r
                    break
            def _to_float(v):
                try:
                    return float(v) if v is not None else None
                except (ValueError, TypeError):
                    return None

            for r in range(header_row2 + 1, lr2 + 1):
                row = sh2.range(f"A{r}:D{r}").value
                if row[0] is None:
                    continue
                price = _to_float(row[1])
                history.append({
                    "period_str": str(row[0]).strip(),
                    "price_tg":   price,
                    "vol":        _to_float(row[2]),
                    "deals":      _to_float(row[3]),
                    "had_trades": bool(price),
                })
            wb2.close()
        except Exception as e:
            print(f"  WARN: ЦеныКАЗ.xlsx Каз_ETS_база: {e}")

    return {"weekly": weekly, "summary": summary, "history": history}


# ---------------------------------------------------------------------------
# ЖД deliveries
# ---------------------------------------------------------------------------

def collect_zhd(app):
    wb = _open(app, ZHD_PATH)

    from xlwings.utils import col_name as cn

    # --- All-countries combined ---
    sh = wb.sheets["Отчетный_период_все_страны"]
    lr = sh.used_range.last_cell.row
    lc = sh.used_range.last_cell.column
    all_rows = []
    for r in range(2, lr + 1):
        row = sh.range(f"A{r}:{cn(lc)}{r}").value
        all_rows.append({
            "region":            row[0],
            "company":           row[1],
            "npz":               row[2],
            "vol_cur_month":     _num(row[4]),
            "vol_prev_month":    _num(row[5]),
            "chg_month_pct":     row[7],
            "vol_prev_year":     _num(row[8]),
            "vol_cur_year":      _num(row[11]),
            "vol_prev_year_cum": _num(row[12]),
        })

    # --- Per-country ---
    sh2 = wb.sheets["Отчетный_период"]
    lr2 = sh2.used_range.last_cell.row
    lc2 = sh2.used_range.last_cell.column
    per_rows = []
    for r in range(2, lr2 + 1):
        row = sh2.range(f"A{r}:{cn(lc2)}{r}").value
        per_rows.append({
            "country":           row[0],
            "region":            row[1],
            "company":           row[2],
            "npz":               row[3],
            "vol_cur_month":     _num(row[5]),
            "vol_prev_month":    _num(row[6]),
            "chg_month_pct":     row[8],
            "vol_prev_year":     _num(row[9]),
            "vol_cur_year":      _num(row[12]),
            "vol_prev_year_cum": _num(row[13]),
        })
    wb.close()
    return all_rows, per_rows


# ---------------------------------------------------------------------------
# ЖД tariffs lookup
# ---------------------------------------------------------------------------

def collect_tariffs(app):
    """Returns dict (npz_name, country_code) → avg_tariff_rub."""
    wb = _open(app, TARIFF_PATH)
    sh = wb.sheets[0]
    lr = sh.used_range.last_cell.row
    tariffs = {}
    for r in range(2, lr + 1):
        row = sh.range(f"A{r}:J{r}").value
        npz      = row[1]   # col B
        avg_rate = row[5]   # col F: Ср.тариф Итог
        ctry_str = str(row[9]) if row[9] else ""
        if not npz or not avg_rate:
            continue
        for code in ("Каз", "Кирг", "Узб"):
            if code in ctry_str:
                key = (npz, code)
                # Keep only the first (best) tariff per route
                if key not in tariffs:
                    tariffs[key] = avg_rate
    wb.close()
    return tariffs


# ---------------------------------------------------------------------------
# Uzbekistan exchange weekly (for Slide 7 "Таблица 8")
# ---------------------------------------------------------------------------

def collect_uzb_exchange(app):
    """
    Returns last 6 data rows from Сборка_Цены.xlsx Узбекистан sheet.
    Each row: {date_label, price_sum, volume, chg_sum}
    Plus one delta row.
    """
    wb = _open(app, PRICES_PATH)
    sh = wb.sheets["Узбекистан"]
    lr = sh.used_range.last_cell.row

    # Find data rows: col A = datetime (weekly), col C = price sum, col N = volume нарастающий?
    # From earlier analysis: col A=НачНедели, B=Пятница, C=ТекущийСр сум/т, F=$/т, G=ИзмСум%, H=Изм$/т%
    # col M (idx 12) = Объём_ун, N (idx 13) = Сделки_ун
    rows = []
    for r in range(2, lr + 1):
        row = sh.range(f"A{r}:R{r}").value
        if not isinstance(row[0], datetime.datetime):
            continue
        # Skip rows where both price and volume are 0/None
        price = row[2]
        vol   = row[12]
        if not price:
            continue
        rows.append({
            "date_from":    row[0],
            "date_to":      row[1],
            "price_sum":    price,
            "price_usd":    row[5],
            "vol":          vol or 0,
            "deals":        row[13] or 0,
            "chg_sum":      row[6],
            "chg_usd":      row[7],
            "ytd_sum":      row[8],    # Цена нач года, сум/т
            "chg_ytd_sum":  row[9],    # Изм к нач. года, сум/т %
            "ytd_usd":      row[10],   # Цена нач года, $/т
            "chg_ytd_usd":  row[11],
            "narast_bnd":    row[14] or 0,  # нарастающий объём БНД тек.год, т
            "narast_all":    row[15] or 0,  # нарастающий все виды тек.год, т
            "narast_bnd_py": row[16] or 0,  # нарастающий БНД ПГ, т
            "narast_all_py": row[17] or 0,  # нарастающий все виды ПГ, т
        })

    wb.close()
    # Take last 6 rows with actual trades (vol > 0), then last 6 total
    rows_with_vol = [r for r in rows if r["vol"] > 0]
    return rows_with_vol[-6:] if len(rows_with_vol) >= 6 else rows_with_vol


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def collect_all():
    print("Чтение данных из Excel...")
    app = xw.App(visible=False)
    try:
        weather      = collect_weather(app)
        currency     = collect_currency(app)
        rf_detail, report_date = collect_rf_prices(app)
        kaz_prices   = collect_kaz_prices(app)
        zhd_all, zhd_per = collect_zhd(app)
        tariffs      = collect_tariffs(app)
        uzb_exchange = collect_uzb_exchange(app)
        kaz_exchange = collect_kaz_exchange(app)
    finally:
        app.quit()

    # Determine report Friday: most recent Friday on or before today.
    # This is more reliable than deriving from Excel dates, which may be mid-week.
    today = datetime.date.today()
    days_since_friday = (today.weekday() - 4) % 7  # Mon=0..Fri=4..Sun=6
    default_friday = today - datetime.timedelta(days=days_since_friday)
    report_date = datetime.datetime.combine(default_friday, datetime.time())

    # Derive month name from start of reporting week (currency date_from),
    # not from Friday date - weekly report may cross month boundary
    week_start = currency.get("date_from")
    if isinstance(week_start, datetime.datetime):
        month_ru = MONTHS_RU[week_start.month]
    elif isinstance(report_date, datetime.datetime):
        month_ru = MONTHS_RU[report_date.month]
    else:
        month_ru = ""

    if isinstance(report_date, datetime.datetime):
        report_date_str = report_date.strftime("%d.%m.%Y")
    else:
        report_date_str = ""

    data = {
        "weather":        weather,
        "currency":       currency,
        "rf_detail":      rf_detail,
        "kaz_prices":     kaz_prices,
        "report_date":    report_date,
        "report_date_str": report_date_str,
        "month_ru":       month_ru,
        "zhd_all":        zhd_all,
        "zhd_per":        zhd_per,
        "tariffs":        tariffs,
        "uzb_exchange":   uzb_exchange,
        "kaz_exchange":   kaz_exchange,
    }

    # Summary printout
    print(f"  Дата отчёта: {report_date_str}  месяц: {month_ru}")
    print(f"  Курсы: USD/KZT={currency['kzt']:.0f}  USD/UZS={currency['uzs']:.0f}  USD/RUB={currency['rub']:.2f}")
    print(f"  Погода: {len(weather)} городов")
    print(f"  РФ цены: {len(rf_detail)} производителей")
    print(f"  ЖД все страны: {len(zhd_all)} строк  per-country: {len(zhd_per)} строк")
    print(f"  КЗ цены: {len(kaz_prices.get('history', []))} недель, {len(kaz_prices.get('producers', []))} производителей")
    print(f"  УЗБ биржа: {len(uzb_exchange)} недель")
    kaz_ets_w = kaz_exchange.get("weekly", [])
    kaz_ets_traded = sum(1 for r in kaz_ets_w if r["had_trades"])
    print(f"  КАЗ ETS: {len(kaz_ets_w)} недель в таблице, {kaz_ets_traded} с торгами")
    return data


if __name__ == "__main__":
    d = collect_all()
    print("\nОК")
