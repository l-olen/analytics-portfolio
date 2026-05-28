"""
generate_analytics.py - Generate analytical texts for weekly PPTX via Claude API.
Saves output to a .txt file organized by section.
"""
import sys
import os
import re
import datetime
from pathlib import Path

import base64

import anthropic

_ENV_PATH = r"C:\projects\my-project\google_ads\.env"
BASE = Path(r"C:\projects\my-project\ОМТ\Еженедельный отчёт")

_CONTEXT_FILE  = BASE.parent / "Квартальный отчет" / "analyst_context_current.md"
_EVENTS_LOG    = BASE / "weekly_events_log.md"
_SERVER_MOUNT  = Path(r"\\192.168.1.3\омт-выпуски")
_MONTH_NAMES_RU = {
    1: "Январь", 2: "Февраль", 3: "Март",  4: "Апрель",
    5: "Май",    6: "Июнь",    7: "Июль",   8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


def _load_api_key():
    """Read ANTHROPIC_API_KEY from .env file if not set in environment."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
                    return
    except FileNotFoundError:
        pass

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _server_reports_dir(date=None) -> Path:
    """Return path to current month's Рынок битумов folder on server."""
    if date is None:
        date = datetime.date.today()
    month_folder = f"{date.month:02d} {_MONTH_NAMES_RU[date.month]}"
    return _SERVER_MOUNT / str(date.year) / month_folder / "Рынок битумов"


def _load_market_context() -> str:
    """Load quarterly market context. Falls back to most recent analyst_context_*.md."""
    try:
        return _CONTEXT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    candidates = sorted(
        (BASE.parent / "Квартальный отчет").glob("analyst_context_*.md"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    for c in candidates:
        if "current" not in c.name:
            try:
                return c.read_text(encoding="utf-8")
            except Exception:
                continue
    return ""


def _load_rf_report_pdfs() -> list:
    """Load recent RF bitumen market PDFs from server. Returns list of (name, base64_data)."""
    reports_dir = _server_reports_dir()
    results = []
    try:
        if not reports_dir.exists():
            print(f"  WARN: сервер недоступен: {reports_dir}")
            return []
        def _latest(prefix):
            matches = sorted(
                [p for p in reports_dir.glob("*.pdf") if p.stem.upper().startswith(prefix)],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            return matches[0] if matches else None

        pdfs = [p for p in (_latest("RB_"), _latest("RPBV_")) if p is not None]
        for pdf_path in pdfs:
            data = pdf_path.read_bytes()
            b64  = base64.standard_b64encode(data).decode("utf-8")
            results.append((pdf_path.name, b64))
            print(f"  Загружен отчёт РФ: {pdf_path.name} ({len(data) // 1024} KB)")
    except Exception as e:
        print(f"  WARN: не удалось загрузить отчёты с сервера: {e}")
    return results


def _save_weekly_events(events_text: str, date_str: str = "") -> None:
    """Append significant weekly events to the cumulative log for quarterly review."""
    header = f"\n## {date_str or datetime.date.today().isoformat()}\n"
    entry  = header + events_text.strip() + "\n"
    try:
        with open(_EVENTS_LOG, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"  WARN: не удалось сохранить события недели: {e}")


def _load_prev_analytics(current_date_str: str = "") -> str:
    """Return text of the most recent previous analytics file, excluding current week."""
    files = sorted(BASE.glob("analytics_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        if current_date_str and current_date_str in f.name:
            continue
        try:
            return f.read_text(encoding="utf-8")
        except Exception:
            continue
    return ""


# Analytics text sections (section label, description)
SECTION_LABELS = [
    "ОБЗОР_РЫНКА",
    "РФ_НПЗ",
    "КАЗАХСТАН",
    "УЗБЕКИСТАН",
    "КЫРГЫЗСТАН",
    "ТАДЖИКИСТАН",
]

SECTION_INSTRUCTIONS = {
    "ОБЗОР_РЫНКА": (
        "Обзор рынка битумов Средней Азии за отчётную неделю. "
        "Укажи общую динамику цен в регионе ($/т) с конкретными цифрами и изменениями, "
        "динамику курсов валют (которые/насколько изменились), "
        "ключевые события и тренды недели. "
        "Добавь актуальные новости по региону. "
        "5-7 предложений. Заголовок 'Обзор рынка' НЕ включай."
    ),
    "РФ_НПЗ": (
        "Анализ цен на битум российских НПЗ за неделю. "
        "Укажи среднюю цену (руб/т с НДС и $/т), изменение к прошлой неделе (% и абс.), "
        "сравнение с началом года и с аналогичным периодом прошлого года. "
        "Перечисли наиболее дорогие и дешёвые НПЗ с конкретными ценами. "
        "4-5 предложений. Заголовок НЕ включай."
    ),
    "КАЗАХСТАН": (
        "Анализ рынка битума в Казахстане. "
        "Укажи индикативные цены по основным производителям (тенге/т, $/т) с изменением к прошлой неделе. "
        "Объём ж/д поставок за месяц и с начала года, изменение к прошлому месяцу. "
        "Топ-3 НПЗ-поставщика с объёмами. "
        "Сравнение с прошлым годом если есть данные. "
        "4-5 предложений. Заголовок 'Казахстан' НЕ включай."
    ),
    "УЗБЕКИСТАН": (
        "Анализ рынка битума в Узбекистане. "
        "Укажи биржевые цены (сум/т, $/т) с изменением к прошлой неделе. "
        "Объём торгов на бирже (т). "
        "Объём ж/д поставок из РФ за месяц и с начала года, изменение к прошлому месяцу. "
        "Топ-3 НПЗ-поставщика с объёмами. "
        "4-5 предложений. Заголовок 'Узбекистан' НЕ включай."
    ),
    "КЫРГЫЗСТАН": (
        "Анализ рынка битума в Кыргызстане. "
        "Укажи цены ($/т). "
        "Объём ж/д поставок за месяц и с начала года, изменение к прошлому месяцу. "
        "Топ-2-3 НПЗ-поставщика с объёмами. "
        "3-4 предложения. Заголовок 'Кыргызстан' НЕ включай."
    ),
    "ТАДЖИКИСТАН": (
        "Анализ рынка битума в Таджикистане. "
        "Укажи цены ($/т). "
        "Объём ж/д поставок за месяц и с начала года, изменение к прошлому месяцу. "
        "3-4 предложения. Заголовок 'Таджикистан' НЕ включай."
    ),
}


def _chg_str(v, cap=9999):
    if v is None:
        return "-"
    pct = v * 100
    if abs(pct) > cap:
        return "н/д (старт сезона)"
    return ("+" if pct > 0 else "") + f"{pct:.1f}%"


_CTRY_ALIASES = {
    "КАЗАХСТАН":   ["КАЗАХСТАН"],
    "УЗБЕКИСТАН":  ["УЗБЕКИСТАН"],
    "КЫРГЫЗСТАН":  ["КЫРГЫЗСТАН", "КИРГИЗИЯ", "КИРГИ"],
    "ТАДЖИКИСТАН": ["ТАДЖИКИСТАН"],
}


def _zhd_country_rows(data, ctry_code):
    aliases = _CTRY_ALIASES[ctry_code]
    return [r for r in data["zhd_per"]
            if r["country"] and any(a in r["country"].upper() for a in aliases)]


def _zhd_block(ctry_rows, ctry_name, month_ru):
    """Return lines for one country ЖД block."""
    lines = [f"  {ctry_name.upper()} (ж/д поставки из РФ, {month_ru}):"]
    # Prefer exact "Итого по стране" row; fall back to last row with "итого"
    ctry_total = next((r for r in ctry_rows if str(r["npz"]).lower() == "итого по стране"), None)
    if not ctry_total:
        for r in ctry_rows:
            if "итого" in str(r["npz"]).lower():
                ctry_total = r

    if ctry_total:
        py_cum = ctry_total.get("vol_prev_year_cum") or 0
        chg_y  = (ctry_total["vol_cur_year"] / py_cum - 1) if py_cum else None
        lines.append(
            f"    Итого: {ctry_total['vol_cur_month']:,.0f} т ({_chg_str(ctry_total['chg_month_pct'])} к пред.мес.)"
            f" | с нач.2026: {ctry_total['vol_cur_year']:,.0f} т"
            f" | анал.период 2025: {py_cum:,.0f} т"
            f" | изм.к 2025: {_chg_str(chg_y)}"
        )
    elif ctry_rows:
        vol_m   = sum(r["vol_cur_month"]      for r in ctry_rows)
        vol_y   = sum(r["vol_cur_year"]       for r in ctry_rows)
        vol_py  = sum(r.get("vol_prev_year_cum", 0) for r in ctry_rows)
        vol_pm  = sum(r["vol_prev_month"]     for r in ctry_rows)
        chg_m   = (vol_m / vol_pm - 1) if vol_pm else None
        chg_y   = (vol_y / vol_py - 1) if vol_py else None
        lines.append(
            f"    Итого (расчёт): {vol_m:,.0f} т ({_chg_str(chg_m)} к пред.мес.)"
            f" | с нач.2026: {vol_y:,.0f} т"
            f" | анал.период 2025: {vol_py:,.0f} т"
            f" | изм.к 2025: {_chg_str(chg_y)}"
        )
    else:
        lines.append("    Данные отсутствуют")
        return lines

    top = sorted(
        [r for r in ctry_rows if "итого" not in str(r["npz"]).lower() and r["vol_cur_month"] > 0],
        key=lambda r: r["vol_cur_month"], reverse=True
    )[:5]
    for r in top:
        year_str = f" | год: {r['vol_cur_year']:,.0f} т" if r.get("vol_cur_year") else ""
        lines.append(
            f"    {r['npz']}: {r['vol_cur_month']:,.0f} т ({_chg_str(r['chg_month_pct'])})"
            f"{year_str}"
        )
    return lines


def _price_trend(history, price_key="price_usd"):
    """Compute trend stats from a list of weekly price rows."""
    prices = [r[price_key] for r in history if r.get(price_key)]
    if len(prices) < 2:
        return None
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    last_chg = changes[-1]
    direction = "рост" if last_chg > 0 else "снижение" if last_chg < 0 else "стабильно"
    streak = 1
    for c in reversed(changes[:-1]):
        if last_chg != 0 and (c > 0) == (last_chg > 0):
            streak += 1
        else:
            break
    total_chg_pct = round((prices[-1] / prices[0] - 1) * 100, 1) if prices[0] else 0
    return {
        "direction":     direction,
        "streak_weeks":  streak,
        "total_chg_pct": total_chg_pct,
        "min_val":       min(prices),
        "max_val":       max(prices),
        "avg_val":       round(sum(prices) / len(prices), 0),
    }


_ORSK_NPZ = "Орскнефтеоргсинтез"

# Total delivery tariff from Orsk to destination (RF portion + transit country portion).
# Orsk is the closest RF refinery to CA markets, so it's the cheapest baseline.
# Other refineries are more expensive because the RF leg is longer (difference taken
# from the tariff table). KGZ is cheaper due to EAEU discount on Kazakhstan transit.
_ORSK_TOTAL_USD = {"Каз": 100, "Узб": 100, "Кирг": 80}


def _delivered_cost(rf_detail, tariffs, rub_rate, country_code):
    """
    Compute delivered cost ($/t) for RF producers to a destination country.
    Uses Orsk as anchor: $100/t total to KZ/UZB, $80/t to KGZ (includes RF + transit).
    Orsk is always included (it's the main CA supplier); other refineries only when
    Orsk's RF-leg tariff is known so the differential can be computed meaningfully.
    tariffs: dict (npz_key, country_code) -> avg_tariff_rub (RF portion only)
    """
    orsk_base = _ORSK_TOTAL_USD.get(country_code, 100)

    # Find Orsk price data and its RF-leg tariff (may be absent from table)
    orsk_rf_rub = None
    orsk_price_usd = None
    orsk_npz_name = None
    for (npz, comp), v in rf_detail.items():
        if _ORSK_NPZ in npz and not v.get("is_total") and v.get("price_usd"):
            orsk_npz_name = npz
            orsk_price_usd = v["price_usd"]
            orsk_rf_rub = tariffs.get((npz, country_code))
            break

    rows = []

    # Always include Orsk when it has price data -- it's the anchor for CA markets
    if orsk_price_usd is not None:
        delivered_orsk = round(orsk_price_usd + orsk_base, 0)
        rows.append((orsk_npz_name, orsk_price_usd, orsk_base, delivered_orsk))

    # Other refineries only if Orsk RF tariff is known (differential must be meaningful)
    if orsk_rf_rub and rub_rate:
        for (npz, comp), v in rf_detail.items():
            if _ORSK_NPZ in npz:
                continue  # already added above
            if v.get("is_total") or not v.get("price_usd"):
                continue
            rf_tariff_rub = tariffs.get((npz, country_code))
            if rf_tariff_rub is None:
                continue
            extra_usd = (rf_tariff_rub - orsk_rf_rub) / rub_rate
            total_tariff_usd = orsk_base + extra_usd
            delivered = round(v["price_usd"] + total_tariff_usd, 0)
            rows.append((npz, v["price_usd"], round(total_tariff_usd, 0), delivered))

    rows.sort(key=lambda x: x[3])
    return rows


def _build_data_summary(data):
    """Build detailed text summary of all collected data for the analytics prompt."""
    cur      = data["currency"]
    rf       = data["rf_detail"]
    kaz      = data.get("kaz_prices", {})
    tariffs  = data.get("tariffs", {})
    month_ru = data.get("month_ru", "")
    rub_rate = cur.get("rub") or 0
    total_rf = next((v for v in rf.values() if v.get("is_total")), None)
    t_all    = next(
        (r for r in data["zhd_all"] if isinstance(r["region"], str) and "все страны" in r["region"].lower()),
        None,
    )

    lines = [
        f"Отчётная дата: {data.get('report_date_str', 'н/д')}",
        f"Текущий месяц: {month_ru}",
        "",
        "=== КУРСЫ ВАЛЮТ (к доллару США) ===",
        f"  USD/KZT: {cur['kzt']:.0f} тенге ({_chg_str(cur['kzt_chg'])} к пред.нед.)",
        f"  USD/UZS: {cur['uzs']:.0f} сум ({_chg_str(cur['uzs_chg'])})",
        f"  USD/KGS: {cur['kgs']:.2f} сом ({_chg_str(cur['kgs_chg'])})",
        f"  USD/TJS: {cur['tjs']:.2f} сомони ({_chg_str(cur['tjs_chg'])})",
        f"  USD/RUB: {cur['rub']:.2f} руб. ({_chg_str(cur['rub_chg'])})",
        "",
        "=== ЦЕНЫ РФ НПЗ (отчётная неделя) ===",
    ]

    if total_rf:
        lines += [
            f"  Среднее по всем НПЗ: {total_rf['price_s_nds']:.0f} руб/т с НДС"
            f" | {total_rf['price_b_nds']:.0f} руб/т без НДС"
            f" | {total_rf['price_usd']:.0f} $/т",
            f"  Изм. к пред.нед.: {_chg_str(total_rf['chg_rub'])} (руб) / {_chg_str(total_rf['chg_usd'])} ($)",
            "  По производителям (НПЗ: цена с НДС | $/т | изм.$/т к пред.нед.):",
        ]
    for (npz, comp), v in rf.items():
        if v.get("is_total") or not v.get("price_s_nds"):
            continue
        lines.append(
            f"    {v['npz']}: {v['price_s_nds']:.0f} руб/т с НДС"
            f" | {v['price_usd']:.0f} $/т ({_chg_str(v['chg_usd'])})"
        )

    # Kazakhstan prices
    lines += ["", "=== ЦЕНЫ КАЗАХСТАН (Сборка_Цены.xlsx) ==="]
    kaz_last = kaz.get("last", {})
    if kaz_last:
        lines += [
            f"  Индикативная цена (последняя неделя): {kaz_last['price_tg']:,.0f} тг/т | {kaz_last['price_usd']:.0f} $/т",
            f"  Изм. к пред.нед.: {_chg_str(kaz_last['chg_tg'])} (тг) / {_chg_str(kaz_last['chg_usd'])} ($)",
            f"  Нач.года: {kaz_last['ytd_tg']:,.0f} тг/т | изм.с нач.года: {_chg_str(kaz_last['chg_ytd_tg'])} (тг)",
            f"  Аналог.период 2025: {kaz_last['py_tg']:,.0f} тг/т | изм.к 2025: {_chg_str(kaz_last['chg_py_tg'])} (тг)",
        ]
        # History
        lines.append("  Динамика индикативной цены (тг/т | $/т):")
        for row in kaz.get("history", []):
            dt = row["date"].strftime("%d.%m") if hasattr(row["date"], "strftime") else ""
            lines.append(
                f"    {dt}: {row['price_tg']:,.0f} тг/т | {row['price_usd']:.0f} $/т"
                f" | {_chg_str(row['chg_tg'])} (тг)"
            )

    # KZ price trend
    kaz_history = kaz.get("history", [])
    kaz_trend_usd = _price_trend(kaz_history, "price_usd")
    kaz_trend_tg  = _price_trend(kaz_history, "price_tg")
    if kaz_trend_usd:
        streak_str = f" {kaz_trend_usd['streak_weeks']} нед. подряд" if kaz_trend_usd['streak_weeks'] > 1 else ""
        lines += [
            f"  Тренд цены за {len(kaz_history)} нед. ($/т): {kaz_trend_usd['direction']}{streak_str}"
            f" | итого за период: {kaz_trend_usd['total_chg_pct']:+.1f}%"
            f" | диапазон: {kaz_trend_usd['min_val']:.0f}–{kaz_trend_usd['max_val']:.0f} $/т"
            f" | среднее: {kaz_trend_usd['avg_val']:.0f} $/т",
        ]
    if kaz_trend_tg:
        lines.append(
            f"  Тренд цены (тг/т): {kaz_trend_tg['direction']}"
            f" | итого за период: {kaz_trend_tg['total_chg_pct']:+.1f}%"
            f" | диапазон: {kaz_trend_tg['min_val']:,.0f}–{kaz_trend_tg['max_val']:,.0f} тг/т"
        )

    kaz_prod = kaz.get("producers", [])
    if kaz_prod:
        lines.append("  Цены производителей Казахстана:")
        prod_usd = [p["price_usd"] for p in kaz_prod if p.get("price_usd")]
        for p in kaz_prod:
            tg  = f"{p['price_tg']:,.0f} тг/т" if p.get("price_tg") else "-"
            usd = f"{p['price_usd']:.0f} $/т"   if p.get("price_usd") else "-"
            chg = f" ({_chg_str(p.get('chg_tg'))})" if p.get("chg_tg") else ""
            lines.append(f"    {p['name']}: {tg} | {usd}{chg}")
        if len(prod_usd) >= 2:
            lines.append(
                f"  Спред между производителями: {min(prod_usd):.0f}–{max(prod_usd):.0f} $/т"
                f" (разница {max(prod_usd) - min(prod_usd):.0f} $/т)"
            )

    kaz_ind = kaz.get("indicative", {})
    if kaz_ind and kaz_ind.get("price_tg"):
        lines.append(
            f"  СВЗ производителей (сводно): {kaz_ind['price_tg']:,.0f} тг/т"
            f" | {kaz_ind['price_usd']:.0f} $/т | изм.{_chg_str(kaz_ind['chg'])}"
        )

    # Delivered cost: RF → KZ
    # Orsk → SaryAgash base = $100/t (RF portion + KZ transit); others add extra RF leg
    if tariffs and rub_rate:
        kaz_delivered = _delivered_cost(rf, tariffs, rub_rate, "Каз")
        if kaz_delivered:
            lines += ["  Расчётная стоимость доставки из РФ в Казахстан ($/т, Орск→Сарыагаш базис $100):"]
            for npz, ex_usd, tariff_usd, delivered in kaz_delivered[:4]:
                lines.append(
                    f"    {npz}: {ex_usd:.0f} (EXW) + {tariff_usd:.0f} (полн.тариф) = {delivered:.0f} $/т delivered"
                )

    # ЖД all countries
    lines += ["", "=== ЖД ПОСТАВКИ ИЗ РФ ==="]
    if t_all:
        py_cum = t_all.get("vol_prev_year_cum") or 0
        chg_y  = (t_all["vol_cur_year"] / py_cum - 1) if py_cum else None
        lines += [
            f"  ВСЕ СТРАНЫ ({month_ru}):",
            f"    За месяц: {t_all['vol_cur_month']:,.0f} т ({_chg_str(t_all['chg_month_pct'])} к пред.мес.)",
            f"    С нач.2026 года: {t_all['vol_cur_year']:,.0f} т",
            f"    Анал.период 2025: {py_cum:,.0f} т | изм.к 2025: {_chg_str(chg_y)}",
        ]

    for ctry_code, ctry_name in (
        ("КАЗАХСТАН",   "Казахстан"),
        ("УЗБЕКИСТАН",  "Узбекистан"),
        ("КЫРГЫЗСТАН",  "Кыргызстан"),
        ("ТАДЖИКИСТАН", "Таджикистан"),
    ):
        ctry_rows = _zhd_country_rows(data, ctry_code)
        lines += _zhd_block(ctry_rows, ctry_name, month_ru)

    # Uzbekistan exchange
    uzb_ex = data.get("uzb_exchange", [])
    if uzb_ex:
        last = uzb_ex[-1]
        lines += ["", "=== БИРЖА УЗБЕКИСТАН (еженедельные торги, история 6 нед.) ==="]
        lines.append("  (нач.нед. | цена сум/т | цена $/т | изм.сум к пред.нед. | объём т | сделок | нараст.БНД т)")
        for row in uzb_ex:
            dt = row["date_from"].strftime("%d.%m") if hasattr(row["date_from"], "strftime") else ""
            lines.append(
                f"  {dt}: {row['price_sum']:,.0f} сум/т | {row['price_usd']:.0f} $/т"
                f" | {_chg_str(row['chg_sum'])} | объём {row['vol']:.0f} т | {row['deals']:.0f} сделок"
                f" | нараст.БНД {row['narast_bnd']:,.0f} т"
            )
        bnd_py  = last.get("narast_bnd_py") or 0
        all_py  = last.get("narast_all_py") or 0
        chg_bnd = (last["narast_bnd"] / bnd_py - 1) if bnd_py else None
        chg_all = (last["narast_all"] / all_py - 1) if all_py else None
        lines += [
            f"  Цена нач.года: {last['ytd_sum']:,.0f} сум/т | {last['ytd_usd']:.0f} $/т",
            f"  Изм.цены к нач.года: {_chg_str(last['chg_ytd_sum'])} (сум) / {_chg_str(last['chg_ytd_usd'])} ($)",
            f"  Нараст.объём БНД с нач.2026: {last['narast_bnd']:,.0f} т | анал.период 2025: {bnd_py:,.0f} т | изм.к 2025: {_chg_str(chg_bnd)}",
            f"  Нараст.объём все виды с нач.2026: {last['narast_all']:,.0f} т | анал.период 2025: {all_py:,.0f} т | изм.к 2025: {_chg_str(chg_all)}",
        ]
        # UZB price trend
        uzb_trend = _price_trend(uzb_ex, "price_usd")
        uzb_vol_trend = _price_trend(uzb_ex, "vol")
        if uzb_trend:
            streak_str = f" {uzb_trend['streak_weeks']} нед. подряд" if uzb_trend['streak_weeks'] > 1 else ""
            lines.append(
                f"  Тренд биржевой цены за {len(uzb_ex)} нед. ($/т): {uzb_trend['direction']}{streak_str}"
                f" | итого: {uzb_trend['total_chg_pct']:+.1f}%"
                f" | диапазон: {uzb_trend['min_val']:.0f}–{uzb_trend['max_val']:.0f} $/т"
            )
        if uzb_vol_trend and uzb_vol_trend["avg_val"]:
            vol_dir = "растёт" if uzb_vol_trend["direction"] == "рост" else \
                      "снижается" if uzb_vol_trend["direction"] == "снижение" else "стабилен"
            streak_vol = f" {uzb_vol_trend['streak_weeks']} нед. подряд" if uzb_vol_trend['streak_weeks'] > 1 else ""
            lines.append(
                f"  Тренд объёма торгов: {vol_dir}{streak_vol}"
                f" | среднее {uzb_vol_trend['avg_val']:,.0f} т/нед."
                f" | мин/макс: {uzb_vol_trend['min_val']:,.0f}–{uzb_vol_trend['max_val']:,.0f} т"
            )

    # Kazakhstan ETS exchange
    kaz_ex = data.get("kaz_exchange", {})
    kaz_ets_weekly  = kaz_ex.get("weekly", [])
    kaz_ets_summary = kaz_ex.get("summary", {})
    kaz_ets_history = kaz_ex.get("history", [])

    if kaz_ets_weekly or kaz_ets_summary:
        lines += ["", "=== БИРЖА КАЗАХСТАН (ETS, еженедельные торги) ==="]

        if kaz_ets_summary and kaz_ets_summary.get("price_tg"):
            usd = f" | {kaz_ets_summary['price_usd']:.0f} $/т" if kaz_ets_summary.get("price_usd") else ""
            chg = f" | изм.{_chg_str(kaz_ets_summary.get('chg'))}" if kaz_ets_summary.get("chg") else ""
            lines.append(f"  ETS биржа (текущая неделя): {kaz_ets_summary['price_tg']:,.0f} тг/т{usd}{chg}")

        if kaz_ets_weekly:
            lines.append("  История ETS (последние недели): Период | цена тг/т | объём т | сделок")
            for row in kaz_ets_weekly:
                if row["had_trades"]:
                    vol   = f"{row['vol']:,.0f} т"   if row.get("vol")   else "-"
                    deals = f"{row['deals']:.0f}"    if row.get("deals") else "-"
                    lines.append(f"    {row['period_str']}: {row['price_tg']:,.0f} тг/т | {vol} | {deals} сделок")
                else:
                    lines.append(f"    {row['period_str']}: торгов не было")

            # Count weeks without trades before last traded week
            no_trade_before = 0
            for row in reversed(kaz_ets_weekly):
                if row["had_trades"]:
                    break
                no_trade_before += 1
            # Reverse: count streak of no-trades just before the final traded row
            traded_rows = [r for r in kaz_ets_weekly if r["had_trades"]]
            no_trade_streak = 0
            for row in reversed(kaz_ets_weekly):
                if not row["had_trades"]:
                    no_trade_streak += 1
                else:
                    break
            # If current week has trades and there was a gap
            if kaz_ets_weekly[-1]["had_trades"] and no_trade_streak == 0:
                # Find streak before the last traded week
                streak = 0
                for row in kaz_ets_weekly[:-1][::-1]:
                    if not row["had_trades"]:
                        streak += 1
                    else:
                        break
                if streak > 0:
                    lines.append(f"  ВАЖНО: торги возобновились после {streak} недель без торгов (в данной таблице)")

        # From full history: find last traded date before current gap
        if kaz_ets_history:
            current_week_traded = kaz_ets_weekly[-1]["had_trades"] if kaz_ets_weekly else False
            if current_week_traded:
                # Find last traded row in history before the most recent entry
                hist_traded = [r for r in kaz_ets_history if r["had_trades"]]
                if len(hist_traded) >= 2:
                    prev_trade = hist_traded[-2]
                    tg  = f"{float(prev_trade['price_tg']):,.0f} тг/т" if prev_trade.get("price_tg") else "-"
                    vol = f"{float(prev_trade['vol']):,.0f} т"          if prev_trade.get("vol")      else "-"
                    lines.append(f"  Предыдущие торги (из архива): {prev_trade['period_str']} | {tg} | {vol}")
                    lines.append(f"  ВАЖНО: торги на ETS Казахстана возобновились впервые с {prev_trade['period_str']}")

    # Delivered cost: RF → UZB, KGZ
    # Orsk → UZB base = $100/t (RF + KZ transit, SaryAgash area)
    # Orsk → KGZ base = $80/t (EAEU rate, lower KZ transit)
    if tariffs and rub_rate:
        for ctry_code, ctry_name, base_note in (
            ("Узб", "Узбекистан", "Орск→УЗБ базис $100"),
            ("Кирг", "Кыргызстан", "Орск→КГЗ базис $80, ЕАЭС"),
        ):
            delivered_rows = _delivered_cost(rf, tariffs, rub_rate, ctry_code)
            if delivered_rows:
                lines += [f"", f"=== РАСЧЁТНАЯ ДОСТАВКА РФ → {ctry_name.upper()} ($/т, {base_note}) ==="]
                for npz, ex_usd, tariff_usd, delivered in delivered_rows[:4]:
                    lines.append(
                        f"  {npz}: {ex_usd:.0f} (EXW) + {tariff_usd:.0f} (полн.тариф) = {delivered:.0f} $/т"
                    )

    return "\n".join(lines)


_VOLUME_SYNONYMS = (
    "СИНОНИМЫ ДЛЯ ОБЪЁМОВ С НАЧАЛА ГОДА — чередуй, не повторяй одну формулировку более 2 раз:\n"
    "  - суммарный объём с начала 2026 года\n"
    "  - поставки за январь–[месяц] 2026\n"
    "  - итого за [N] месяцев 2026 года\n"
    "  - объём с начала года\n"
    "  - совокупные поставки с января\n"
    "  - по итогам [N] месяцев\n"
    "ЗАПРЕЩЕНО: фразы 'нарастающий объём' и 'нарастающий итог' — не использовать совсем."
)


def _build_prompt(data_summary, news_text, prices_text="", prev_text="", market_context=""):
    prices_block = ""
    if prices_text and "не найдены" not in prices_text:
        prices_block = f"""
РЫНОЧНЫЕ ЦЕНЫ ТРЕЙДЕРОВ (предложения на отчётную неделю, используй для уточнения спотовых цен):
{prices_text}
"""
    prev_block = ""
    if prev_text:
        prev_block = f"""
ТЕКСТ ПРЕДЫДУЩЕГО ОТЧЁТА (только для стилистического контроля, не пересказывать):
Запрещено дословно повторять любую фразу длиной 5+ слов из текста ниже.
Если ситуация по стране не изменилась принципиально — напиши одно предложение
("тренд сохраняется", "динамика аналогична прошлой неделе"), не повторяй полный анализ.
---
{prev_text[:3000]}
---
"""
    context_block = ""
    if market_context:
        cutoff = market_context.find("## 8.")
        ctx = market_context[:cutoff].strip() if cutoff > 0 else market_context.strip()
        context_block = f"""
ФУНДАМЕНТАЛЬНЫЙ КОНТЕКСТ РЫНКА (квартальный -- структура рынка, игроки, тренды):
Используй для понимания рыночного фона. Не повторяй этот контекст дословно в тексте отчёта.
---
{ctx}
---
"""
    return f"""Ты старший аналитик рынка битумов. Пиши профессиональные аналитические тексты \
для еженедельного отчёта "Рынок битумов Средней Азии".
Если к сообщению приложены PDF-документы -- это еженедельные отчёты ОМТ-Консалт по рынку \
битума и ПБВ в России. Используй данные из них для раздела [РФ_НПЗ] и общего контекста.
{context_block}
ДАННЫЕ НЕДЕЛИ:
{data_summary}
{prices_block}
АКТУАЛЬНЫЕ НОВОСТИ (ОБЯЗАТЕЛЬНО используй их в каждом разделе по теме;
если новость содержит [ВЛИЯНИЕ НА СА: ...] — используй именно эту формулировку для вывода):
{news_text}
{prev_block}
Напиши 6 текстовых блоков. Каждый начинается с тега на отдельной строке.

ТРЕБОВАНИЯ К ФОРМАТИРОВАНИЮ ЧИСЕЛ (строго):
- Цены в сумах: округляй до тыс. сум/т с 1 знаком после запятой. Пример: 6 008 349 → "6,0 млн сум/т"
- Цены в тенге: округляй до тыс. тг/т с 1 знаком. Пример: 182 378 → "182,4 тыс. тг/т"
- Объёмы т: если > 10 000, пиши в тыс. т с 1 знаком. Пример: 16 177 → "16,2 тыс. т"
- Цены в руб/т: пиши в тыс. руб/т с 1 знаком. Пример: 20 829 → "20,8 тыс. руб/т"
- Цены в $/т: пиши целым числом без сокращений. Пример: 209 $/т
- Изменения в %: всегда с знаком + или -, 1 знак после запятой

[ОБЗОР_РЫНКА]
Самый большой раздел - обзор всего рынка. Структура:
1. Вводное предложение о общей динамике региона за неделю с ценами ($/т) по ключевым рынкам.
2. Курсы валют: динамика тенге, сума, рубля, сома, сомони к доллару - с конкретными значениями и % изм.
3. Общий объём ж/д поставок в регион за месяц и с нач.года, сравнение с 2025 г.
4. Казахстан (2-3 предложения): индикативная цена тг/т и $/т, динамика, ключевые тренды, \
ситуация с ж/д поставками, новость о Казахстане если есть.
5. Узбекистан (2-3 предложения): биржевая цена сум/т и $/т, динамика, объём торгов, \
нарастающий объём, новость об Узбекистане если есть.
6. Кыргызстан и Таджикистан (2-3 предложения вместе): объёмы поставок, динамика, \
тренды, новость если есть.
7. Общие тенденции региона: дорожный сезон, инфраструктурные программы, \
изменения в логистике - с опорой на новости из списка (упомяни 2-3 конкретные новости).
Длина: 10-14 предложений сплошным текстом.

[РФ_НПЗ]
Анализ цен российских НПЗ. Обязательно:
- средняя цена: руб/т с НДС, руб/т без НДС, $/т + изм. к пред.нед. в % (руб и $)
- каждый НПЗ отдельно: тыс. руб/т с НДС, $/т, % изм. к пред.нед.
- диапазон: НПЗ с наиболее высокой ценой и НПЗ с наименьшей ценой
- тренды: сезонный спрос, влияние курса рубля, экспортные потоки
- новость о российском рынке нефтепродуктов/битума если есть в списке
Длина: 5-6 предложений. Нельзя использовать "дорогейший", "дешёвший" - \
только "наиболее высокая цена у...", "минимальная цена у...".

[КАЗАХСТАН]
Анализ рынка Казахстана. Обязательно:
- индикативная цена (тыс. тг/т и $/т), изм. к пред.нед. % в тенге и $
- сравнение: нач.года (тыс. тг/т, % изм.) и анал.период 2025 г. (тыс. тг/т, % изм.)
- ценовой тренд за 6 недель: направление, сколько недель подряд, диапазон мин-макс $/т — \
объясни причину (курс тенге, сезонный спрос, активность НПЗ, логистика)
- спред между производителями: кто дороже/дешевле и почему (местный vs импортный)
- расчётная стоимость доставки из РФ ($/т delivered) vs казахстанские производители: \
есть ли ценовое преимущество у российского битума, или местные дешевле?
- цены производителей ПНХЗ, Caspi Bitum, Qazaq Bitum: тыс. тг/т + $/т
- ж/д поставки: объём за месяц (тыс. т), % изм. к пред.мес., нараст. с нач.года, сравнение с 2025
- топ-3 НПЗ-поставщика РФ с объёмами
- если есть данные "БИРЖА КАЗАХСТАН (ETS)": укажи цену тг/т и $/т, объём, кол-во сделок; \
если торги возобновились после перерыва -- ОБЯЗАТЕЛЬНО укажи это как ключевое событие недели \
("впервые с [дата] на ETS состоялись торги битумом")
- сезонный контекст: начало дорожного сезона, активность закупок, прогноз спроса
- ОБЯЗАТЕЛЬНО: упомяни 1-2 конкретные новости о казахстанском рынке/дорожном строительстве
Длина: 8-10 предложений.
СТРОГО: только данные Казахстана из блоков "ЦЕНЫ КАЗАХСТАН", "КАЗАХСТАН (ж/д поставки)", \
"БИРЖА КАЗАХСТАН". Блок "РАСЧЁТНАЯ ДОСТАВКА РФ → КАЗАХСТАН" используй только для \
сравнения с местными ценами. Данные Узбекистана, Кыргызстана, Таджикистана не включай.

[УЗБЕКИСТАН]
Анализ рынка Узбекистана. Обязательно:
- биржевая цена (млн сум/т и $/т), изм. к пред.нед. % в сумах и $
- сравнение биржевой цены с началом года (млн сум/т, % изм.)
- ценовой тренд биржи за 6 недель: направление, сколько недель подряд, диапазон мин-макс $/т — \
назови причину динамики (активность НПЗ, сезонный спрос, курс сума, объём торгов)
- тренд объёма торгов: растёт или падает, средний объём за период — это признак \
активизации рынка или затишья перед сезоном?
- расчётная стоимость доставки из РФ в Узбекистан ($/т delivered) vs биржевая цена: \
насколько российский битум конкурентоспособен, кто формирует цену биржи?
- объём торгов за последнюю неделю (т) + кол-во сделок
- нарастающий объём БНД с нач.2026 г. (тыс. т) в сравнении с 2025
- ж/д поставки из РФ: объём за месяц, нараст. с нач.2026, топ-3 НПЗ-поставщика
- сезонный контекст: дорожные работы, тендеры, прогноз активности
- ОБЯЗАТЕЛЬНО: упомяни 1-2 конкретные новости об Узбекистане
Длина: 8-10 предложений.
СТРОГО: только данные Узбекистана из блоков "БИРЖА УЗБЕКИСТАН", "УЗБЕКИСТАН (ж/д поставки)", \
"РАСЧЁТНАЯ ДОСТАВКА РФ → УЗБЕКИСТАН". Данные Казахстана, Кыргызстана, Таджикистана не включай.

[КЫРГЫЗСТАН]
Анализ рынка Кыргызстана. Обязательно:
- ж/д поставки: тыс. т за месяц, % изм. к пред.мес., нараст. с нач.2026 (тыс. т), \
сравнение с анал.периодом 2025 (тыс. т, % изм.)
- топ-3 НПЗ-поставщика: тыс. т/мес + % изм. + нараст. за год
- ценовой ориентир $/т с учётом логистики от российских цен
- ОБЯЗАТЕЛЬНО: упомяни новость о дорожном строительстве или ГСМ в Кыргызстане если есть
Длина: 4-5 предложений.
СТРОГО: только данные Кыргызстана из блока "КЫРГЫЗСТАН (ж/д поставки)". \
Данные Казахстана, Узбекистана, Таджикистана не включай.

[ТАДЖИКИСТАН]
Анализ рынка Таджикистана. Обязательно:
- ж/д поставки: тыс. т за месяц, % изм. к пред.мес., нараст. с нач.2026 (тыс. т), \
сравнение с анал.периодом 2025 (тыс. т, % изм.)
- основные поставщики с объёмами тыс. т/мес
- ценовой ориентир $/т
- упомяни новость о Таджикистане если есть в списке
Длина: 4-5 предложений.
СТРОГО: используй только данные Таджикистана. Не повторяй цифры, выводы или формулировки \
из разделов Кыргызстан, Узбекистан, Казахстан. Если данных мало — пиши кратко по фактам, \
не заполняй текст содержимым других стран.

СТРОГИЕ ТРЕБОВАНИЯ К СТИЛЮ:
- {_VOLUME_SYNONYMS}
- Пиши как опытный аналитик сырьевого рынка: цифры - это обоснование выводов, а не сам текст
- Каждый блок начинай с ключевого вывода о динамике, затем обосновывай цифрами
- Объясняй причины изменений (сезонность, курс валют, логистика, спрос)
- Сравнивай с предыдущим периодом и прошлым годом - делай выводы о трендах
- Каждый блок - сплошной текст без маркеров, списков, подзаголовков
- Не включай заголовки разделов в текст (Казахстан, Обзор и т.д.)
- Не используй длинное тире, только запятую или дефис
- Только цифры из данных, не придумывай числа
- Не объясняй причины изменений, если они не следуют напрямую из данных или новостей. \
Не используй: "транспортное давление", "инфляционное давление", "рыночная консолидация" \
и подобные клише без конкретного обоснования в данных.
- Грамотный русский: "наиболее высокая", "наименьшая"
- Если данных нет - "Данные за период отсутствуют"
- НОВОСТИ: используй по приоритету:
  1. Новости без метки — строго за отчётную неделю, упоминай обязательно: "По данным [источник], ..."
  2. Новости с меткой [нефтепродукты/дороги] — использовать как контекст если нет новостей tier-1
  3. Новости с меткой [инфраструктура/регион] — только как общий фон, без прямых ссылок на цены
  4. Если по стране новостей нет вообще — не упоминать отсутствие, просто писать аналитику по данным
- ТОЧНОСТЬ НОВОСТЕЙ — критически важно:
  1. Сниппеты из поиска могут содержать фрагменты соседних статей на той же странице.
     Опирайся строго на заголовок. Не переноси дату, статус или детали из одного фрагмента
     сниппета на тему другого заголовка.
  2. Если заголовок в будущем времени ("запретит", "введёт", "планирует") — это проект или
     намерение, не принятый документ. Пиши "рассматривается проект", "планируется", а не
     "принят указ" или "введён".
  3. "Нефтепродукты" НЕ равно "битум". Если новость о налоге, пошлине или ограничении
     касается "нефтепродуктов" без явного упоминания битума — не применяй её к битуму.
     Используй только если в тексте прямо указан битум или битумные материалы.
  4. Если новость неоднозначна или сниппет слишком короткий — лучше пропусти её,
     чем домысли детали.
- РЫНОЧНЫЕ ЦЕНЫ ТРЕЙДЕРОВ: если найдены предложения по стране - упомяни спотовую цену \
с формулировкой "рыночные предложения трейдеров на уровне ... $/т" и сравни с биржевой/индикативной ценой. \
Если предложений нет - не упоминай их отсутствие.
- Разделитель между блоками - одна пустая строка

[СОБЫТИЯ_НЕДЕЛИ]
Перечисли 3-5 значимых событий этой недели для рынка битума ЦА, которые важны для квартального анализа.
Только реально значимые факты: изменения регулирования, новые игроки/поставщики, резкие ценовые сдвиги \
(более 5%), инфраструктурные решения с прямым влиянием на рынок.
Формат -- одна строка на событие: ДАТА | СТРАНА/ТЕМА | Краткое описание.
Если значимых событий нет -- напиши "Значимых событий нет".
"""


def _parse_response(text):
    """Parse Claude response into dict {section_label: text}."""
    result = {}
    current_label = None
    current_lines = []

    for line in text.splitlines():
        m = re.match(r"^\[([A-ZА-ЯЁ_\d]+)\]\s*$", line.strip())
        if m:
            if current_label:
                result[current_label] = "\n".join(current_lines).strip()
            current_label = m.group(1)
            current_lines = []
        elif current_label is not None:
            current_lines.append(line)

    if current_label:
        result[current_label] = "\n".join(current_lines).strip()

    return result


def generate_texts(data, news_text, prices_text="", prev_text="", model="claude-sonnet-4-6"):
    """Call Claude API to generate all analytical blocks. Returns dict {label: text}."""
    print("  Генерация аналитических текстов...")
    _load_api_key()
    client = anthropic.Anthropic()

    data_summary   = _build_data_summary(data)
    market_context = _load_market_context()
    rf_pdfs        = _load_rf_report_pdfs()

    (BASE / "debug_data_summary.txt").write_text(data_summary, encoding="utf-8")
    prompt = _build_prompt(data_summary, news_text, prices_text, prev_text, market_context)

    # Build multimodal content: PDFs (if any) followed by the prompt text
    if rf_pdfs:
        content = []
        for pdf_name, pdf_b64 in rf_pdfs:
            content.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_b64,
                },
                "title": pdf_name,
            })
        content.append({"type": "text", "text": prompt})
    else:
        content = prompt

    message = client.messages.create(
        model=model,
        max_tokens=8000,
        system=(
            "Ты старший аналитик рынка битумов. "
            "Каждый раздел аналитики должен содержать ТОЛЬКО данные своей страны/темы. "
            "Никогда не переноси данные одной страны в раздел другой страны. "
            "Строго соблюдай структуру: каждый блок начинается с тега [НАЗВАНИЕ] на отдельной строке, "
            "затем текст. Никакого другого форматирования вокруг тегов."
        ),
        messages=[{"role": "user", "content": content}],
    )
    response_text = message.content[0].text
    parsed        = _parse_response(response_text)

    missing = [lbl for lbl in SECTION_LABELS if lbl not in parsed]
    if missing:
        print(f"  WARN: не найдены блоки: {missing}")

    if "СОБЫТИЯ_НЕДЕЛИ" in parsed:
        _save_weekly_events(parsed["СОБЫТИЯ_НЕДЕЛИ"], data.get("report_date_str", ""))
        print(f"  События недели сохранены -> {_EVENTS_LOG.name}")

    return {k: v for k, v in parsed.items() if k in SECTION_LABELS}


def save_analytics(analytics, report_date=None, out_path=None):
    """Save analytics dict to a .txt file organized by section."""
    if out_path is None:
        if report_date and hasattr(report_date, "strftime"):
            d = report_date.date() if hasattr(report_date, "date") else report_date
            fname = f"analytics_{d.strftime('%d_%m_%Y')}.txt"
        else:
            fname = f"analytics_{datetime.date.today().strftime('%d_%m_%Y')}.txt"
        out_path = BASE / fname

    SECTION_HEADERS = {
        "ОБЗОР_РЫНКА": "Обзор рынка",
        "РФ_НПЗ":      "Россия, НПЗ",
        "КАЗАХСТАН":   "Казахстан",
        "УЗБЕКИСТАН":  "Узбекистан",
        "КЫРГЫЗСТАН":  "Кыргызстан",
        "ТАДЖИКИСТАН": "Таджикистан",
    }

    lines = [
        f"РЫНОК БИТУМОВ СРЕДНЕЙ АЗИИ",
        f"Дата: {datetime.date.today().strftime('%d.%m.%Y')}",
        "=" * 60,
        "",
    ]
    for i, label in enumerate(SECTION_LABELS):
        header = SECTION_HEADERS.get(label, label)
        text   = analytics.get(label, "Данные за период отсутствуют")
        lines += [
            header,
            "-" * len(header),
            text,
            "",
        ]
        if i < len(SECTION_LABELS) - 1:
            lines += ["---", ""]

    out_path = Path(out_path)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Тексты сохранены: {out_path.name}")
    return out_path


if __name__ == "__main__":
    from collect_data import collect_all
    from search_news import search_all_news, format_news_for_prompt

    data = collect_all()
    print("Поиск новостей...")
    news = search_all_news(verbose=True)
    news_text = format_news_for_prompt(news)
    analytics = generate_texts(data, news_text)
    save_analytics(analytics, report_date=data.get("report_date"))
