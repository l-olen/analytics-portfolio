# -*- coding: utf-8 -*-
"""
generate_quarterly_analytics.py
Generates analytical sections for the quarterly bitumen market report.

Context chain (same as weekly report):
  1. analyst_context_current.md  -- quarterly market knowledge base
  2. weekly_events_log.md        -- accumulated significant events from current quarter
  3. ИТОГ_* tables from Сборка_квартальные.xlsx -- actual quarterly data
  4. PDF reports from network server (optional, same as weekly)

Usage:
  python generate_quarterly_analytics.py
"""

import os
import sys
import base64
import datetime
from pathlib import Path

import anthropic

_ENV_PATH    = Path(r"C:\projects\my-project\google_ads\.env")
BASE         = Path(r"C:\projects\my-project\ОМТ\Квартальный отчет")
WEEKLY_BASE  = BASE.parent / "Еженедельный отчёт"
EXCEL_FILE   = BASE / "Сборка_квартальные.xlsx"
CONTEXT_FILE = BASE / "analyst_context_current.md"
EVENTS_LOG   = WEEKLY_BASE / "weekly_events_log.md"
SERVER_MOUNT = Path(r"\\192.168.1.3\омт-выпуски")
_MONTH_NAMES_RU = {
    1: "Январь", 2: "Февраль", 3: "Март",  4: "Апрель",
    5: "Май",    6: "Июнь",    7: "Июль",   8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

# Sections to generate. Add new entries when more country sheets are ready.
SECTIONS = [
    (
        "КАЗАХСТАН",
        "Напиши аналитический текст для раздела «Казахстан» квартального отчёта. "
        "Охвати: производство (объём за период, доли производителей, динамика к аналогичному периоду пред. года), "
        "импорт (объём, структура поставщиков, изменение квоты на российский битум), "
        "экспорт (объём, направления), отгрузки по кластерам потребления (Центр/Юг/Запад/Восток), "
        "ценовая динамика (тыс. тг/т, $/т, сезонный тренд). "
        "Объясни ключевые изменения через рыночный контекст и события квартала.",
    ),
    (
        "ИТОГИ_ТРЕНДЫ",
        "Напиши текст для итогового слайда квартального отчёта «Итоги и тренды» по рынку битумных материалов Казахстана. "
        "ТОЛЬКО Казахстан -- не включать данные по Узбекистану, Кыргызстану, Таджикистану. "
        "Формат: 6-8 коротких пунктов по 2-3 предложения каждый (маркированный список для презентации). "
        "Каждый пункт начинается с ключевого вывода-заголовка (жирным), затем 1-2 предложения с цифрами. "
        "Обязательные темы пунктов (все только по Казахстану): "
        "(1) общая оценка рынка за отчётный период; "
        "(2) производство -- итог периода, динамика, ключевые изменения у производителей; "
        "(3) импорт -- объём, влияние квоты на российский битум, структура поставщиков; "
        "(4) экспорт -- объём и направления; "
        "(5) ценовая динамика -- уровень тыс. тг/т, сравнение с аналогичным периодом прошлого года; "
        "(6) отгрузки по кластерам -- региональная структура потребления внутри Казахстана; "
        "(7) государственные программы дорожного строительства Казахстана -- объём программ, ключевые проекты, прогноз спроса; "
        "(8) ожидания на следующий период -- сезонный спрос, ключевые риски. "
        "Стиль: деловой, конкретный, без воды. Только факты из данных и контекста.",
    ),
]

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _load_api_key() -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
                    return
    except FileNotFoundError:
        pass


def _load_context() -> str:
    try:
        return CONTEXT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"  WARN: контекст не найден: {CONTEXT_FILE}")
        return ""


def _load_weekly_events() -> str:
    """Load accumulated weekly events log for the current quarter."""
    try:
        text = EVENTS_LOG.read_text(encoding="utf-8")
        print(f"  Загружен weekly_events_log.md ({len(text)} символов)")
        return text
    except FileNotFoundError:
        print(f"  WARN: events log не найден: {EVENTS_LOG}")
        return ""


def _load_server_pdfs() -> list:
    """Load recent RF bitumen market PDFs from server. Returns list of (name, base64_data)."""
    today = datetime.date.today()
    month_folder = f"{today.month:02d} {_MONTH_NAMES_RU[today.month]}"
    reports_dir = SERVER_MOUNT / str(today.year) / month_folder / "Рынок битумов"
    results = []
    try:
        if not reports_dir.exists():
            print(f"  WARN: сервер недоступен: {reports_dir}")
            return []
        pdfs = sorted(
            [p for p in reports_dir.glob("*.pdf") if not p.stem.upper().startswith("RBSA")],
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        for pdf_path in pdfs[:2]:
            data = pdf_path.read_bytes()
            b64  = base64.standard_b64encode(data).decode("utf-8")
            results.append((pdf_path.name, b64))
            print(f"  Загружен PDF: {pdf_path.name} ({len(data) // 1024} KB)")
    except Exception as e:
        print(f"  WARN: не удалось загрузить PDF с сервера: {e}")
    return results


def _collect_excel_data() -> str:
    try:
        import xlwings as xw
    except ImportError:
        print("  WARN: xlwings не установлен, данные Excel не будут прочитаны")
        return ""

    lines: list[str] = []
    wb = None
    opened_here = False
    try:
        # Prefer already-open workbook; open if not found
        try:
            wb = xw.books[EXCEL_FILE.name]
            print(f"  Подключился к открытому: {EXCEL_FILE.name}")
        except Exception:
            wb = xw.Book(str(EXCEL_FILE))
            opened_here = True
            print(f"  Открыт файл: {EXCEL_FILE.name}")

        found = 0
        for sheet in wb.sheets:
            for tbl in sheet.tables:
                if not tbl.name.startswith("ИТОГ_"):
                    continue
                try:
                    data = tbl.range.value
                    if not data or len(data) < 2:
                        continue
                    header = [str(h) if h is not None else "" for h in data[0]]
                    lines.append(f"\n=== {tbl.name} (лист: {sheet.name}) ===")
                    lines.append(" | ".join(header))
                    for row in data[1:]:
                        if all(c is None for c in row):
                            continue
                        cells = []
                        for c in row:
                            if isinstance(c, float):
                                cells.append(f"{c:.1f}")
                            elif c is None:
                                cells.append("")
                            else:
                                cells.append(str(c))
                        lines.append(" | ".join(cells))
                    found += 1
                except Exception as e:
                    lines.append(f"=== {tbl.name}: ошибка ({e}) ===")

        print(f"  Таблиц ИТОГ_ прочитано: {found}")
    except Exception as e:
        print(f"  WARN: не удалось прочитать Excel: {e}")
        return ""
    finally:
        if opened_here and wb is not None:
            try:
                wb.close()
            except Exception:
                pass

    return "\n".join(lines)


def _load_context() -> str:
    try:
        return CONTEXT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"  WARN: контекст не найден: {CONTEXT_FILE}")
        return ""


def _generate_section(client: anthropic.Anthropic, section_name: str, task: str,
                       context: str, data: str, pdfs: list) -> str:
    today = datetime.date.today()

    prompt = f"""Ты старший аналитик рынка битумных материалов. Пишешь раздел квартального отчёта ОМТ-Консалт.
Если к сообщению приложены PDF -- это отчёты ОМТ-Консалт по российскому рынку. Используй их как дополнительный контекст.

Дата составления: {today}

## Квартальный контекст рынка
{context}

## Данные из таблиц Excel (ИТОГ_*)
{data}

## Задание: {section_name}
{task}

Требования к тексту:
- Только конкретные цифры из данных выше, ничего не придумывать
- Деловой аналитический стиль, без вводных фраз и воды
- Динамика обязательна: текущий период vs аналогичный период прошлого года (% изм.)
- Объясняй причины через контекст (квота, нефтяные цены, инфраструктура, сезонность)
- Форматирование: объёмы > 10 тыс. т -- в тыс. т с 1 знаком; цены тг -- тыс. тг/т
- Без заголовков -- только связный текст раздела
- 5-7 абзацев, каждый абзац -- одна законченная мысль
- Не используй длинное тире, только запятую или дефис
- СТРОГО ЗАПРЕЩЕНО использовать сокращения Q1, Q2, Q3, Q4 --
  только полные формы: "первый квартал", "второй квартал", "январь-март", "первые три месяца года" и т.п.
- Не упоминай данные за пределами отчётного периода (недельные данные мая и позже -- не использовать)"""

    if pdfs:
        content: list = []
        for pdf_name, pdf_b64 in pdfs:
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                "title": pdf_name,
            })
        content.append({"type": "text", "text": prompt})
    else:
        content = prompt

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": content}],
    )
    return msg.content[0].text


def main() -> None:
    _load_api_key()
    client = anthropic.Anthropic()

    print("Загрузка контекста рынка...")
    context = _load_context()

    print("Загрузка событий квартала...")
    events = _load_weekly_events()

    print("Загрузка PDF с сервера...")
    pdfs = _load_server_pdfs()

    print("Чтение данных из Excel...")
    data = _collect_excel_data()
    if not data:
        print("  WARN: данные Excel не получены -- текст будет только на основе контекста")

    today_str = datetime.date.today().strftime("%d_%m_%Y")
    output_path = BASE / f"analytics_quarterly_{today_str}.txt"

    results: dict[str, str] = {}
    for section_name, task in SECTIONS:
        print(f"Генерация раздела: {section_name}...")
        text = _generate_section(client, section_name, task, context, data, pdfs)
        results[section_name] = text
        print(f"  Готово ({len(text)} символов)")

    # Write output file
    header = f"Квартальный отчёт -- аналитика {today_str}\n{'=' * 60}\n"
    body = "\n".join(f"\n## {name}\n\n{text}\n" for name, text in results.items())
    output_path.write_text(header + body, encoding="utf-8")
    print(f"\nСохранено: {output_path}")
    print(f"Верификация: запусти вручную через research_verify.py или передай файл в Claude для проверки фактов.")


if __name__ == "__main__":
    main()
