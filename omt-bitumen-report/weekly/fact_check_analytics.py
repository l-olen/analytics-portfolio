"""
fact_check_analytics.py - Fact-checking for weekly analytics via Claude Haiku + Gemini.

Flow:
  1. Claude Haiku extracts numerical claims from analytics text
  2. Claude Haiku verifies claims against source data (internal check)
  3. Gemini 2.0 Flash independently verifies the same text (external check)
  4. Results saved to fact_check_DD_MM_YYYY.txt

Usage:
  from fact_check_analytics import fact_check, save_fact_check
  report = fact_check(analytics_dict, source_data_summary)
  save_fact_check(report, report_date)
"""
import os
import re
import datetime
from pathlib import Path

import anthropic

_ENV_PATH = r"C:\projects\my-project\google_ads\.env"
BASE = Path(r"C:\projects\my-project\ОМТ\Еженедельный отчёт")

TAVILY_AVAILABLE = False
try:
    import tavily
    TAVILY_AVAILABLE = True
except ImportError:
    pass

GEMINI_AVAILABLE = False
try:
    from google import genai as google_genai
    GEMINI_AVAILABLE = True
except ImportError:
    pass

try:
    import httpx as _httpx
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False


# ============================================================
# Key loading
# ============================================================

def _load_env_key(var_name: str) -> None:
    if os.environ.get(var_name):
        return
    try:
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{var_name}="):
                    os.environ[var_name] = line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass


def _load_api_key():
    _load_env_key("ANTHROPIC_API_KEY")


def _load_tavily_key():
    _load_env_key("TAVILY_API_KEY")


def _load_gemini_key():
    _load_env_key("GEMINI_API_KEY")


def _load_deepseek_key():
    _load_env_key("DEEPSEEK_API_KEY")


# ============================================================
# Prompts
# ============================================================

_EXTRACT_PROMPT = """Ты проверяешь аналитический текст на фактические ошибки.

Из текста ниже извлеки список конкретных числовых утверждений, которые можно проверить:
- цены ($/т, руб/т, тг/т, сум/т)
- объёмы поставок (тыс. т)
- изменения (% к пред. неделе / месяцу / году)
- курсы валют

Формат вывода -- список строк, каждая строка:
CLAIM: <утверждение> | SECTION: <раздел> | VALUE: <число с единицей>

Текст для анализа:
{text}

Извлеки только конкретные числовые факты, не пересказывай выводы.
"""

_VERIFY_PROMPT = """Ты проверяешь аналитический отчёт по рынку битумов Средней Азии.

ИСХОДНЫЕ ДАННЫЕ (источник истины):
{source_data}

СГЕНЕРИРОВАННЫЙ ТЕКСТ ДЛЯ ПРОВЕРКИ:
{analytics_text}

ДОПОЛНИТЕЛЬНЫЕ ИСТОЧНИКИ ИЗ ПОИСКА (если есть):
{search_results}

Задача: найди расхождения между исходными данными и аналитическим текстом.

Для каждого расхождения выведи:
ОШИБКА | Раздел: <раздел> | Факт: <что написано в тексте> | Источник: <что в данных> | Серьёзность: ВЫСОКАЯ/СРЕДНЯЯ/НИЗКАЯ

Если расхождений нет, выведи:
ОК | Все числа соответствуют исходным данным.

Допустимая погрешность: +-2% для округлённых значений (тыс. т, млн сум).
Не отмечай как ошибку: стилистические различия, округления в допустимых пределах,
выводы и интерпретации (проверяй только факты).
"""

_GEMINI_VERIFY_PROMPT = """Ты независимый аналитик, проверяешь еженедельный отчёт по рынку битумов Средней Азии.

ИСХОДНЫЕ ДАННЫЕ (Excel, источник истины):
{source_data}

АНАЛИТИЧЕСКИЙ ТЕКСТ ДЛЯ ПРОВЕРКИ:
{analytics_text}

Задача: независимо проверь соответствие числовых фактов в тексте исходным данным.

Для каждого расхождения:
ОШИБКА | Раздел: <раздел> | В тексте: <что написано> | В данных: <что есть> | Серьёзность: ВЫСОКАЯ/СРЕДНЯЯ/НИЗКАЯ

Если всё верно:
ОК | Числа соответствуют исходным данным.

Допустимая погрешность округления: +-2%.
Проверяй только числовые факты, не стиль.
"""


# ============================================================
# Claude Haiku: extract claims + verify
# ============================================================

def extract_claims(analytics_dict: dict, client: anthropic.Anthropic) -> list[str]:
    all_text = "\n\n".join(
        f"[{label}]\n{text}"
        for label, text in analytics_dict.items()
        if text and "отсутствуют" not in text
    )
    if not all_text.strip():
        return []

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(text=all_text)}],
    )
    lines = msg.content[0].text.strip().splitlines()
    return [l for l in lines if l.startswith("CLAIM:")]


def verify_with_claude(
    analytics_dict: dict,
    source_data_summary: str,
    search_results: str,
    client: anthropic.Anthropic,
) -> str:
    all_text = "\n\n".join(
        f"[{label}]\n{text}"
        for label, text in analytics_dict.items()
        if text
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": _VERIFY_PROMPT.format(
                source_data=source_data_summary[:8000],
                analytics_text=all_text[:6000],
                search_results=search_results or "Поиск не выполнялся.",
            ),
        }],
    )
    return msg.content[0].text.strip()


# ============================================================
# Gemini: independent external verification
# ============================================================

def verify_with_gemini(analytics_dict: dict, source_data_summary: str) -> str:
    if not GEMINI_AVAILABLE:
        return "Gemini недоступен: установи google-generativeai"

    _load_gemini_key()
    if not os.environ.get("GEMINI_API_KEY"):
        return "Gemini недоступен: GEMINI_API_KEY не найден в .env"

    all_text = "\n\n".join(
        f"[{label}]\n{text}"
        for label, text in analytics_dict.items()
        if text
    )

    prompt = _GEMINI_VERIFY_PROMPT.format(
        source_data=source_data_summary[:8000],
        analytics_text=all_text[:6000],
    )
    client = google_genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    for model_name in ("models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-2.0-flash-lite"):
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return f"[модель: {model_name}]\n{response.text.strip()}"
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                continue
            return f"Ошибка Gemini ({model_name}): {e}"
    return "Gemini недоступен: квота исчерпана на всех моделях. Попробуй позже."


# ============================================================
# DeepSeek: independent external verification
# ============================================================

_DEEPSEEK_VERIFY_PROMPT = """Ты независимый аналитик. Проверь еженедельный отчёт по рынку битумов Средней Азии.

ИСХОДНЫЕ ДАННЫЕ (Excel, источник истины):
{source_data}

АНАЛИТИЧЕСКИЙ ТЕКСТ ДЛЯ ПРОВЕРКИ:
{analytics_text}

Задача: независимо проверь числовые факты в тексте против исходных данных.

Для каждого расхождения:
ОШИБКА | Раздел: <раздел> | В тексте: <что написано> | В данных: <что есть> | Серьёзность: ВЫСОКАЯ/СРЕДНЯЯ/НИЗКАЯ

Если всё верно:
ОК | Числа соответствуют исходным данным.

Допустимая погрешность округления: +-2%.
Проверяй только числовые факты, не стиль и не выводы.
"""

_DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
_DEEPSEEK_MODEL = "deepseek-chat"


def verify_with_deepseek(analytics_dict: dict, source_data_summary: str) -> str:
    if not DEEPSEEK_AVAILABLE:
        return "DeepSeek недоступен: установи httpx"

    _load_deepseek_key()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "DeepSeek недоступен: DEEPSEEK_API_KEY не найден в .env"

    all_text = "\n\n".join(
        f"[{label}]\n{text}"
        for label, text in analytics_dict.items()
        if text
    )
    prompt = _DEEPSEEK_VERIFY_PROMPT.format(
        source_data=source_data_summary[:8000],
        analytics_text=all_text[:6000],
    )

    try:
        with _httpx.Client(timeout=60) as client:
            resp = client.post(
                _DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8192,
                },
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
            return f"[модель: {_DEEPSEEK_MODEL}]\n{result}"
    except Exception as e:
        return f"Ошибка DeepSeek: {e}"


# ============================================================
# Tavily: optional price search for cross-check
# ============================================================

def _search_price_verification(claims: list[str]) -> str:
    if not TAVILY_AVAILABLE or not claims:
        return ""
    _load_tavily_key()
    if not os.environ.get("TAVILY_API_KEY"):
        return ""

    from tavily import TavilyClient
    tc = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    price_claims = [c for c in claims if "$/т" in c or "$/t" in c.lower()][:3]
    if not price_claims:
        return ""

    snippets = []
    for claim in price_claims:
        val_m = re.search(r"VALUE: (\d+[\d\s,]*)", claim)
        if not val_m:
            continue
        val = val_m.group(1).strip()
        query = f"bitumen price Central Asia {val} USD per ton {datetime.date.today().year}"
        try:
            results = tc.search(query=query, max_results=2, search_depth="basic")
            for r in results.get("results", []):
                snippets.append(f"- {r.get('title', '')}: {r.get('content', '')[:200]}")
        except Exception as e:
            snippets.append(f"- Поиск не удался: {e}")

    return "\n".join(snippets) if snippets else ""


# ============================================================
# Main entry point
# ============================================================

def fact_check(
    analytics_dict: dict,
    source_data_summary: str,
    use_search: bool = True,
    use_gemini: bool = True,
    use_deepseek: bool = True,
) -> dict:
    """
    Run fact-checking: Claude Haiku (internal) + Gemini + DeepSeek (external).

    Returns dict:
      claims, search_results, claude_verdict, gemini_verdict,
      deepseek_verdict, errors_found, timestamp
    """
    _load_api_key()
    client = anthropic.Anthropic()

    print("  [fact-check] Извлекаю утверждения (Claude Haiku)...")
    claims = extract_claims(analytics_dict, client)
    print(f"  [fact-check] Найдено утверждений: {len(claims)}")

    search_results = ""
    if use_search and claims:
        print("  [fact-check] Поиск для верификации цен (Tavily)...")
        search_results = _search_price_verification(claims)

    print("  [fact-check] Верификация по данным (Claude Haiku)...")
    claude_verdict = verify_with_claude(
        analytics_dict, source_data_summary, search_results, client
    )

    gemini_verdict = ""
    if use_gemini:
        print("  [fact-check] Независимая проверка (Gemini 2.0 Flash)...")
        gemini_verdict = verify_with_gemini(analytics_dict, source_data_summary)

    deepseek_verdict = ""
    if use_deepseek:
        print("  [fact-check] Независимая проверка (DeepSeek)...")
        deepseek_verdict = verify_with_deepseek(analytics_dict, source_data_summary)

    all_verdicts = "\n".join([claude_verdict, gemini_verdict, deepseek_verdict])
    errors_found = any(
        line.startswith("ОШИБКА") and "ВЫСОКАЯ" in line
        for line in all_verdicts.splitlines()
    )

    return {
        "claims": claims,
        "search_results": search_results,
        "claude_verdict": claude_verdict,
        "gemini_verdict": gemini_verdict,
        "deepseek_verdict": deepseek_verdict,
        "errors_found": errors_found,
        "timestamp": datetime.datetime.now().isoformat(timespec="minutes"),
    }


def save_fact_check(report: dict, report_date=None) -> Path:
    if report_date and hasattr(report_date, "strftime"):
        d = report_date.date() if hasattr(report_date, "date") else report_date
        fname = f"fact_check_{d.strftime('%d_%m_%Y')}.txt"
    else:
        fname = f"fact_check_{datetime.date.today().strftime('%d_%m_%Y')}.txt"

    out = BASE / fname
    lines = [
        "FACT-CHECK ОТЧЁТ",
        f"Дата: {report['timestamp']}",
        f"Статус: {'! ОШИБКИ НАЙДЕНЫ' if report['errors_found'] else 'OK'}",
        "=" * 60,
        "",
        "ИЗВЛЕЧЁННЫЕ УТВЕРЖДЕНИЯ:",
        "-" * 30,
    ]
    lines += report["claims"] or ["Утверждения не извлечены."]
    lines += [
        "",
        "ПРОВЕРКА: Claude Haiku (внутренняя)",
        "-" * 30,
        report["claude_verdict"],
    ]
    if report.get("gemini_verdict"):
        lines += [
            "",
            "ПРОВЕРКА: Gemini 2.0 Flash (внешняя, независимая)",
            "-" * 30,
            report["gemini_verdict"],
        ]
    if report.get("deepseek_verdict"):
        lines += [
            "",
            "ПРОВЕРКА: DeepSeek (внешняя, независимая)",
            "-" * 30,
            report["deepseek_verdict"],
        ]
    if report.get("search_results"):
        lines += [
            "",
            "ДАННЫЕ ИЗ ПОИСКА (Tavily):",
            "-" * 30,
            report["search_results"],
        ]

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [fact-check] Отчёт сохранён: {out.name}")
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE))
    from collect_data import collect_all
    from generate_analytics import _build_data_summary

    data = collect_all()
    summary = _build_data_summary(data)
    sample = {"ТЕСТ": "Средняя цена РФ НПЗ составила 210 $/т, рост на +2,3% к прошлой неделе."}
    report = fact_check(sample, summary, use_search=False)
    path = save_fact_check(report)
    print(path)
