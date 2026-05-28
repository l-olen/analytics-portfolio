"""
search_news.py - Search bitumen/road construction news via Tavily API.
Returns only recent news (last 7 days by default).
"""
import sys
import os
import re
import json
import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ENV_PATH = r"C:\projects\my-project\google_ads\.env"


def _load_tavily_key():
    if os.environ.get("TAVILY_API_KEY"):
        return
    try:
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TAVILY_API_KEY="):
                    os.environ["TAVILY_API_KEY"] = line.split("=", 1)[1].strip()
                    return
    except FileNotFoundError:
        pass


_SEEN_FILE = Path(__file__).parent / "news_seen.json"

# Exclude from news search: own site + ad/marketplace sites
_NEWS_EXCLUDE_DOMAINS = [
    "omt-consult.ru",
    "olx.kz", "olx.uz",
    "bicotender.ru",
    "yahoo.com",
    "instagram.com",
    "youtube.com",
    "threads.com",
    "tiktok.com",
    "vk.com",
    "t.me",
    "seawallsavers.com",
    "tradingeconomics.com",
]

# Tiered queries: each tier is tried if previous yielded too few results.
# tier=1 — битум по стране (основной)
# tier=2 — нефтепродукты + дорожное строительство по стране
# tier=3 — инфраструктура / экономика + мировой рынок битума
QUERIES_TIERED = [
    # tier 1 — bitumen-specific
    {"q": "битум Казахстан цена производство",        "tier": 1, "country": "Казахстан"},
    {"q": "запрет экспорт битум Казахстан 2026",      "tier": 1, "country": "Казахстан"},
    {"q": "битум Узбекистан биржа цена поставки",     "tier": 1, "country": "Узбекистан"},
    {"q": "битум Кыргызстан поставки дефицит",        "tier": 1, "country": "Кыргызстан"},
    {"q": "битум Таджикистан поставки импорт",        "tier": 1, "country": "Таджикистан"},
    {"q": "битум поставки экспорт Россия СНГ",        "tier": 1, "country": "регион"},
    # tier 2 — oil products / road construction
    {"q": "дорожное строительство ремонт Казахстан программа",  "tier": 2, "country": "Казахстан"},
    {"q": "нефтепродукты дорожное строительство Узбекистан",    "tier": 2, "country": "Узбекистан"},
    {"q": "дороги строительство Кыргызстан финансирование",     "tier": 2, "country": "Кыргызстан"},
    {"q": "нефтепродукты Таджикистан импорт соглашение",        "tier": 2, "country": "Таджикистан"},
    {"q": "нефтепродукты битум рынок СНГ цена",                 "tier": 2, "country": "регион"},
    # tier 3 — infrastructure / global bitumen
    {"q": "строительство дорог инфраструктура Казахстан финансирование", "tier": 3, "country": "Казахстан"},
    {"q": "строительство дороги программа Узбекистан АБР ЕБРР",          "tier": 3, "country": "Узбекистан"},
    {"q": "мировой рынок битума нефть прогноз",                          "tier": 3, "country": "регион"},
]

# Minimum results from tier 1 before falling through to next tier
_TIER1_MIN = 3

# Publication date patterns
_OLD_YEAR_RE = re.compile(r"\b(202[0-4]|2025)\b")
_MONTH_RU = {
    1: "январ", 2: "феврал", 3: "март", 4: "апрел",
    5: "ма[йя]", 6: "июн", 7: "июл", 8: "август",
    9: "сентябр", 10: "октябр", 11: "ноябр", 12: "декабр",
}
# Short Russian month names for text date extraction (Reuters/ТАСС style: "6 май", "17 апр")
_RU_MONTHS_SHORT = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4,
    "май": 5, "мая": 5, "июн": 6, "июл": 7,
    "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}


def _parse_pub_date(item) -> datetime.date | None:
    """
    Parse publication date from Tavily result.
    Tries: pub_date field → URL pattern → DD.MM.YYYY in text → Russian 'DD мес' in text.
    """
    raw = item.get("pub_date") or item.get("published_date") or ""
    if raw:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.datetime.strptime(str(raw)[:len(fmt)], fmt).date()
            except ValueError:
                continue
    # YYYY/MM/DD from URL
    m = re.search(r"[/_-](20\d{2})[/_-](\d{1,2})[/_-](\d{1,2})", item.get("url", ""))
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Extract date from title/snippet text
    text = item.get("title", "") + " " + item.get("snippet", "")
    # DD.MM.YYYY
    m = re.search(r"\b(\d{1,2})\.(\d{2})\.(20\d{2})\b", text)
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # Russian "DD мес" (e.g. "6 май", "17 апр") -- assume current year
    m = re.search(r"\b(\d{1,2})\s+(янв|фев|мар|апр|май|мая|июн|июл|авг|сен|окт|ноя|дек)\b",
                  text.lower())
    if m:
        day   = int(m.group(1))
        month = _RU_MONTHS_SHORT.get(m.group(2), 0)
        if month:
            try:
                return datetime.date(datetime.date.today().year, month, day)
            except ValueError:
                pass
    return None


def _is_recent(item, report_date: datetime.date, max_days: int = 21) -> bool:
    """
    Check recency. Primary: pub_date within max_days before report_date.
    Fallback (truly no date extractable): require current year in text.
    """
    pub_date = _parse_pub_date(item)
    if pub_date is not None:
        delta = (report_date - pub_date).days
        return 0 <= delta <= max_days
    # Last resort: at least current year must appear somewhere
    text = (
        item.get("title", "") + " " +
        item.get("snippet", "") + " " +
        item.get("url", "")
    ).lower()
    return str(report_date.year) in text and not re.search(r"\b202[0-4]\b", text)


def _search_tavily(query, max_results=5, days=7, exclude_domains=None):
    """Search via Tavily with days recency filter."""
    _load_tavily_key()
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        kwargs = dict(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
            days=days,
        )
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        resp = client.search(**kwargs)
        results = []
        for r in (resp.get("results") or []):
            title   = (r.get("title") or "").strip()
            url     = r.get("url", "")
            snippet = (r.get("content") or "")[:350].strip()
            pub_date = r.get("published_date", "")
            if title:
                results.append({
                    "title":    title,
                    "url":      url,
                    "snippet":  snippet,
                    "pub_date": pub_date,
                })
        return results
    except Exception as e:
        if "import" not in str(e).lower():
            print(f"  Tavily error ({query[:30]}...): {e}")
        return []


def _load_seen_data() -> dict:
    """Load URLs and date from previous report."""
    if not _SEEN_FILE.exists():
        return {"urls": set(), "last_report": None}
    try:
        data = json.loads(_SEEN_FILE.read_text(encoding="utf-8"))
        last = datetime.date.fromisoformat(data["last_report"]) if data.get("last_report") else None
        return {"urls": set(data.get("urls", [])), "last_report": last}
    except Exception:
        return {"urls": set(), "last_report": None}


def _save_seen_urls(news_items: list, report_date: datetime.date):
    """Persist current week's URLs so next week can deduplicate."""
    existing = {}
    if _SEEN_FILE.exists():
        try:
            existing = json.loads(_SEEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["urls"] = [item["url"] for item in news_items if item.get("url")]
    existing["last_report"] = report_date.isoformat()
    _SEEN_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def search_all_news(verbose=False, days=10, report_date: datetime.date = None):
    """
    Tiered news search with deduplication against previous week.

    Tier 1 (bitumen-specific) is always searched first.
    If results < _TIER1_MIN, tier 2 (oil products / roads) is added.
    If still < _TIER1_MIN, tier 3 (infrastructure / global) is added.
    Items already used in the previous report (news_seen.json) are skipped.
    Each item is tagged with tier and country for Claude context.
    """
    if report_date is None:
        report_date = datetime.date.today()

    month_names = {
        1: "январь", 2: "февраль", 3: "март", 4: "апрель",
        5: "май", 6: "июнь", 7: "июль", 8: "август",
        9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
    }
    date_suffix = f"{month_names[report_date.month]} {report_date.year}"
    seen_data = _load_seen_data()
    last_report = seen_data["last_report"]
    # Apply deduplication only when re-running within the same week (< 4 days since last run)
    if last_report and (report_date - last_report).days < 4:
        seen_urls = seen_data["urls"]
        if verbose:
            print(f"  Дедупликация: {len(seen_urls)} URL из предыдущего запуска ({last_report})")
    else:
        seen_urls = set()
        if verbose and last_report:
            print(f"  Дедупликация отключена: прошло {(report_date - last_report).days} дн. с последнего отчёта")

    all_results = []
    seen_titles: set = set()

    def _run_tier(max_tier: int):
        for entry in QUERIES_TIERED:
            if entry["tier"] > max_tier:
                continue
            full_query = f"{entry['q']} {date_suffix}"
            if verbose:
                print(f"  [tier{entry['tier']}] {full_query}")
            items = _search_tavily(full_query, max_results=5, days=days,
                                   exclude_domains=_NEWS_EXCLUDE_DOMAINS)
            for r in items:
                # Normalize pub_date: extract from text if Tavily didn't provide it
                if not r.get("pub_date"):
                    parsed = _parse_pub_date(r)
                    if parsed:
                        r["pub_date"] = parsed.isoformat()
                if not _is_recent(r, report_date, max_days=days + 4):
                    continue
                if r.get("url") in seen_urls:
                    if verbose:
                        print(f"    пропуск (прошлая неделя): {r['title'][:60]}")
                    continue
                key = re.sub(r"\s+", " ", r["title"]).lower()[:60]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                r["country"] = entry["country"]
                # Downgrade to tier-2 if "битум" not in title — likely general oil/roads news
                title_lower = r["title"].lower()
                if entry["tier"] == 1 and "битум" not in title_lower:
                    r["tier"] = 2
                else:
                    r["tier"] = entry["tier"]
                all_results.append(r)

    # Tier 1 always
    _run_tier(1)
    tier1_count = len(all_results)
    if verbose:
        print(f"  Tier 1: {tier1_count} новостей")

    # Tier 2 if not enough tier-1 results
    if tier1_count < _TIER1_MIN:
        if verbose:
            print(f"  Мало tier-1 ({tier1_count} < {_TIER1_MIN}), добавляю tier 2...")
        _run_tier(2)

    # Tier 3 if still not enough
    if len(all_results) < _TIER1_MIN:
        if verbose:
            print(f"  Мало результатов ({len(all_results)}), добавляю tier 3...")
        _run_tier(3)

    if verbose:
        t1 = sum(1 for r in all_results if r.get("tier") == 1)
        t2 = sum(1 for r in all_results if r.get("tier") == 2)
        t3 = sum(1 for r in all_results if r.get("tier") == 3)
        print(f"  Итого: {len(all_results)} новостей (tier1={t1}, tier2={t2}, tier3={t3})")
    return all_results


def format_news_for_prompt(news_items):
    """Format as text block for analytics prompt.
    Tier-2/3 items are labelled so Claude knows they are fallback context."""
    if not news_items:
        return "Новостей по теме за отчётную неделю не найдено — ссылки на новости не использовать."

    tier_label = {1: "", 2: " [нефтепродукты/дороги]", 3: " [инфраструктура/регион]"}
    lines = []
    for i, item in enumerate(news_items, 1):
        date_str = f" [{item['pub_date']}]" if item.get("pub_date") else ""
        label    = tier_label.get(item.get("tier", 1), "")
        snippet  = f"\n   {item['snippet']}" if item.get("snippet") else ""
        lines.append(f"{i}. {item['title']}{date_str}{label}{snippet}")
    return "\n".join(lines)


def save_news(news_items, report_date=None, out_dir=None):
    """Save news list to .txt and persist seen URLs for next week's deduplication."""
    if out_dir is None:
        out_dir = Path(__file__).parent

    rdate = report_date
    if hasattr(rdate, "date"):
        rdate = rdate.date()
    if rdate is None:
        rdate = datetime.date.today()

    fname = f"news_{rdate.strftime('%d_%m_%Y')}.txt"
    out_path = Path(out_dir) / fname

    tier_label = {1: "", 2: " [нефтепродукты/дороги]", 3: " [инфраструктура/регион]"}
    lines = [
        "НОВОСТИ РЫНКА БИТУМОВ",
        f"Дата отчёта: {rdate.strftime('%d.%m.%Y')}",
        f"Найдено: {len(news_items)} новостей",
        "=" * 60,
        "",
    ]
    for i, item in enumerate(news_items, 1):
        label    = tier_label.get(item.get("tier", 1), "")
        date_str = f"  Дата: {item['pub_date']}" if item.get("pub_date") else ""
        url_str  = f"  URL: {item['url']}" if item.get("url") else ""
        snippet  = f"  {item['snippet']}" if item.get("snippet") else ""
        lines.append(f"{i}. {item['title']}{label}")
        for s in [date_str, url_str, snippet]:
            if s:
                lines.append(s)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Новости сохранены: {out_path.name}")

    # Persist URLs for next week deduplication
    _save_seen_urls(news_items, rdate)
    print(f"  URL сохранены в {_SEEN_FILE.name} (дедупликация след. недели)")
    return out_path


# Known marketplaces with trader price listings per country
PRICE_SOURCES = {
    "Казахстан": {
        "domains": ["flagma.kz", "pulscen.kz", "satu.kz"],
        "queries": [
            "битум БНД 60/90 цена тонна",
            "битум дорожный купить оптом тенге",
        ],
    },
    "Узбекистан": {
        "domains": ["prom.uz", "flagma.uz"],
        "queries": [
            "битум БНД цена сум тонна",
            "битум дорожный купить оптом",
        ],
    },
    "Кыргызстан": {
        "domains": ["flagma-kg.com"],
        "queries": [
            "битум цена тонна Бишкек",
        ],
    },
    "Таджикистан": {
        "domains": [],
        "queries": [
            "битум цена тонна Душанбе Таджикистан",
        ],
    },
    "регион": {
        "domains": [],
        "queries": [
            "битум БНД Средняя Азия цена доллар тонна трейдер",
        ],
    },
}


def _search_tavily_domains(query, domains=None, max_results=5, days=14):
    """Search via Tavily with optional domain filter."""
    _load_tavily_key()
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        kwargs = dict(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
            days=days,
        )
        if domains:
            kwargs["include_domains"] = domains
        resp = client.search(**kwargs)
        results = []
        for r in (resp.get("results") or []):
            title = (r.get("title") or "").strip()
            url = r.get("url", "")
            snippet = (r.get("content") or "")[:400].strip()
            pub_date = r.get("published_date", "")
            if title:
                results.append({
                    "title":    title,
                    "url":      url,
                    "snippet":  snippet,
                    "pub_date": pub_date,
                })
        return results
    except Exception as e:
        if "import" not in str(e).lower():
            print(f"  Tavily price error ({query[:30]}...): {e}")
        return []


def search_market_prices(verbose=False, days=14, report_date: datetime.date = None):
    """
    Search for current trader spot price offers for bitumen in Central Asia.
    Uses domain-targeted search for known marketplaces (flagma.kz, prom.uz, etc.).
    Returns list of {country, title, url, snippet, pub_date}.
    """
    if report_date is None:
        report_date = datetime.date.today()

    month_names = {
        1: "январь", 2: "февраль", 3: "март", 4: "апрель",
        5: "май", 6: "июнь", 7: "июль", 8: "август",
        9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
    }
    date_suffix = f"{month_names[report_date.month]} {report_date.year}"

    all_results = []
    seen = set()

    for country, cfg in PRICE_SOURCES.items():
        domains = cfg["domains"]
        for query in cfg["queries"]:
            full_query = f"{query} {date_suffix}"
            if verbose:
                sites = ", ".join(domains) if domains else "без фильтра"
                print(f"  Цены [{country}] ({sites}): {full_query}")
            items = _search_tavily_domains(
                full_query, domains=domains or None, max_results=4, days=days
            )
            for r in items:
                key = re.sub(r"\s+", " ", r["title"]).lower()[:60]
                if key not in seen:
                    seen.add(key)
                    r["country"] = country
                    all_results.append(r)

    if verbose:
        print(f"  Найдено ценовых предложений: {len(all_results)}")
    return all_results


def format_prices_for_prompt(price_items):
    """Format trader price results as a text block for the analytics prompt."""
    if not price_items:
        return "Рыночные предложения трейдеров за отчётную неделю не найдены."

    by_country = {}
    for item in price_items:
        c = item.get("country", "регион")
        by_country.setdefault(c, []).append(item)

    lines = []
    for country, items in by_country.items():
        lines.append(f"{country}:")
        for item in items:
            date_str = f" [{item['pub_date']}]" if item.get("pub_date") else ""
            snippet = f"\n   {item['snippet']}" if item.get("snippet") else ""
            lines.append(f"  - {item['title']}{date_str}{snippet}")
    return "\n".join(lines)


def save_prices(price_items, report_date=None, out_dir=None):
    """Save market price search results to a .txt file."""
    from pathlib import Path

    if out_dir is None:
        out_dir = Path(__file__).parent

    if report_date and hasattr(report_date, "strftime"):
        d = report_date.date() if hasattr(report_date, "date") else report_date
        fname = f"market_prices_{d.strftime('%d_%m_%Y')}.txt"
    else:
        fname = f"market_prices_{datetime.date.today().strftime('%d_%m_%Y')}.txt"

    out_path = Path(out_dir) / fname

    lines = [
        "РЫНОЧНЫЕ ЦЕНЫ ТРЕЙДЕРОВ",
        f"Дата: {datetime.date.today().strftime('%d.%m.%Y')}",
        f"Найдено: {len(price_items)} предложений",
        "=" * 60,
        "",
    ]
    for i, item in enumerate(price_items, 1):
        date_str = f"  Дата: {item['pub_date']}" if item.get("pub_date") else ""
        url_str = f"  URL: {item['url']}" if item.get("url") else ""
        snippet = f"  {item['snippet']}" if item.get("snippet") else ""
        country = f"  Страна: {item['country']}" if item.get("country") else ""
        lines += [f"{i}. {item['title']}"]
        for s in [country, date_str, url_str, snippet]:
            if s:
                lines.append(s)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Рыночные цены сохранены: {out_path.name}")
    return out_path


if __name__ == "__main__":
    print("Поиск новостей (Tavily, последние 7 дней)...")
    items = search_all_news(verbose=True)
    print()
    print(format_news_for_prompt(items))
