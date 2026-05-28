"""
news_verify.py - Annotate global news with verified Central Asia bitumen market impact.

Called between search_news and generate_analytics.
Identifies global (non-CA) news items and adds honest CA-impact annotations
using Claude Haiku, so the analytics generator works with pre-verified conclusions.
"""
import json
import os

import anthropic

_ENV_PATH = r"C:\projects\my-project\google_ads\.env"

_SA_MARKET_CONTEXT = (
    "Рынок битумов Средней Азии — ключевые факты для оценки влияния внешних событий:\n"
    "- Казахстан самодостаточен: ПНХЗ, Caspi Bitum, Qazaq Bitum покрывают внутренний спрос;\n"
    "  с июля 2026 действует запрет на экспорт битума за пределы ЕАЭС\n"
    "- Узбекистан, Кыргызстан, Таджикистан закупают битум у России по железной дороге\n"
    "- Регион НЕ импортирует битум из Персидского залива и не зависит от морских поставок\n"
    "- Российский ж/д экспорт в СА невозможно быстро переориентировать на морские\n"
    "  направления: другая инфраструктура, санкционные ограничения в расчётах\n"
    "- Глобальные цены влияют косвенно — через нефть и себестоимость российского производства\n"
    "- Дефицит в Персидском заливе или азиатском морском рынке не создаёт дефицита в СА"
)

_ANNOTATE_PROMPT = """\
Ты аналитик рынка нефтепродуктов Средней Азии.

{context}

Ниже — список новостей для еженедельного отчёта по рынку битумов Средней Азии.

Найди ГЛОБАЛЬНЫЕ новости: про мировой рынок битума, Персидский залив, танкеры, морские поставки,
Индию, Китай, Южную Корею, Европу — которые НЕ касаются напрямую Казахстана, Узбекистана,
Кыргызстана, Таджикистана или российского экспорта в СА.

Для каждой глобальной новости верни JSON-объект:
  "start": первые 50 символов заголовка новости (точно из текста, для поиска)
  "impact": честная оценка влияния на рынок СА, 1-2 предложения
            (может быть "прямого влияния нет, так как регион не зависит от...")

Верни ТОЛЬКО JSON-массив. Если глобальных новостей нет — верни [].

НОВОСТИ:
{news_text}
"""


def _load_api_key() -> None:
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


def annotate_global_news(
    news_text: str,
    client: anthropic.Anthropic = None,
    model: str = "claude-haiku-4-5-20251001",
) -> str:
    """
    Scan news_text for global (non-CA) news items and append verified CA-impact
    annotations directly after each matching line.

    Returns modified news_text. On any error returns original text unchanged.
    """
    if not news_text or not news_text.strip():
        return news_text

    _load_api_key()
    if client is None:
        client = anthropic.Anthropic()

    prompt = _ANNOTATE_PROMPT.format(
        context=_SA_MARKET_CONTEXT,
        news_text=news_text[:4000],
    )

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown fences if model wraps output
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:])
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3].strip()
        annotations = json.loads(raw)
    except Exception as e:
        print(f"  [news-verify] Аннотация пропущена: {e}")
        return news_text

    if not annotations:
        print("  [news-verify] Глобальных новостей не обнаружено")
        return news_text

    result_lines = news_text.splitlines()
    inserted = 0
    for item in annotations:
        start = (item.get("start") or "")[:50].lower()
        impact = (item.get("impact") or "").strip()
        if not start or not impact:
            continue
        for i, line in enumerate(result_lines):
            if start in line.lower():
                annotation = f"   [ВЛИЯНИЕ НА СА: {impact}]"
                result_lines.insert(i + 1, annotation)
                print(f"  [news-verify] + {line[:60].strip()}")
                inserted += 1
                break

    if inserted:
        print(f"  [news-verify] Аннотировано глобальных новостей: {inserted}")
    return "\n".join(result_lines)
