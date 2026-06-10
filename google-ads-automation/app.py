# -*- coding: utf-8 -*-
"""
Google Ads Dashboard -- локальное веб-приложение для запуска скриптов.

Запуск:
  python app.py
  Открыть: http://localhost:5000
"""

import os
import subprocess
import sys
from pathlib import Path

import json
import re
import plotly
import plotly.graph_objects as go
from flask import Flask, Response, render_template, request, stream_with_context, send_file

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
PYTHON = sys.executable

ANALYSIS_FILE = BASE_DIR / "marketing_analysis_latest.json"

CHANNEL_COLORS = {
    "Реклама (Google)": "#1a73e8",
    "Organic Search": "#34a853",
    "Direct": "#fbbc04",
    "Referral": "#ff6d00",
    "Organic Social": "#ab47bc",
    "Unassigned": "#bdbdbd",
}


def _build_charts(data: dict) -> dict:
    charts = {}
    for acc in data["accounts"]:
        aid = acc["account_id"]

        channels = acc.get("ga4_channels")
        if channels:
            merged = {}
            for c in channels:
                ch = "Реклама (Google)" if c["channel"] in ("Cross-network", "Paid Search") else c["channel"]
                if ch not in merged:
                    merged[ch] = {"sessions": 0, "conversions": 0}
                merged[ch]["sessions"] += c["sessions"]
                merged[ch]["conversions"] += c["conversions"]
            ch_sorted = sorted(merged.items(), key=lambda x: x[1]["sessions"], reverse=True)
            fig = go.Figure(go.Bar(
                x=[k for k, _ in ch_sorted],
                y=[v["sessions"] for _, v in ch_sorted],
                marker_color=[CHANNEL_COLORS.get(k, "#90a4ae") for k, _ in ch_sorted],
                text=[v["sessions"] for _, v in ch_sorted],
                textposition="outside",
                customdata=[[v["conversions"]] for _, v in ch_sorted],
                hovertemplate="<b>%{x}</b><br>Сессии: %{y}<br>Конверсии: %{customdata[0]}<extra></extra>",
            ))
            fig.update_layout(
                title="Сессии по каналам (GA4)", height=320,
                margin=dict(t=40, b=40, l=20, r=20),
                plot_bgcolor="white", yaxis=dict(gridcolor="#f0f0f0"),
            )
            charts[f"{aid}_channels"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            acc["ga4_channels_merged"] = [
                {"channel": k, "sessions": v["sessions"], "conversions": v["conversions"]}
                for k, v in ch_sorted
            ]

        crm = acc.get("crm")
        if crm and crm.get("total_leads"):
            fig = go.Figure(go.Funnel(
                y=["Новые лиды", "В работе", "Успешно реализовано"],
                x=[crm["total_leads"], crm["in_progress"] + crm["won"], crm["won"]],
                marker_color=["#1a73e8", "#fbbc04", "#34a853"],
                textinfo="value+percent initial",
            ))
            fig.update_layout(title="Воронка CRM", height=320, margin=dict(t=40, b=20, l=20, r=20))
            charts[f"{aid}_crm"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

            src = crm["by_source"]
            fig = go.Figure(go.Pie(
                labels=["Сайт (реклама)", "Сайт (органика)", "Звонки", "Прочее"],
                values=[src["site_paid"], src["site_organic"], src["call"], src["other"]],
                hole=0.45, marker_colors=["#1a73e8", "#34a853", "#fbbc04", "#bdbdbd"],
            ))
            fig.update_layout(title="Источники лидов", height=320, margin=dict(t=40, b=20, l=20, r=20))
            charts[f"{aid}_sources"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        if crm and crm.get("won") and crm.get("won_by_source"):
            ws = crm["won_by_source"]
            if sum(ws.values()) > 0:
                fig = go.Figure(go.Pie(
                    labels=["Сайт (реклама)", "Сайт (органика)", "Звонки", "Прочее"],
                    values=[ws["site_paid"], ws["site_organic"], ws["call"], ws["other"]],
                    hole=0.45, marker_colors=["#1a73e8", "#34a853", "#fbbc04", "#bdbdbd"],
                ))
                fig.update_layout(title="Успешно реализовано по источникам", height=320,
                                  margin=dict(t=40, b=20, l=20, r=20))
                charts[f"{aid}_won"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return charts


def markdown_to_html(text: str) -> str:
    """Minimal Markdown to HTML converter for analysis output."""
    lines = text.split("\n")
    out = []
    in_list = False
    in_ol = False

    for line in lines:
        # Headers
        if line.startswith("## "):
            if in_list:
                out.append("</ul>"); in_list = False
            if in_ol:
                out.append("</ol>"); in_ol = False
            out.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith("### "):
            if in_list:
                out.append("</ul>"); in_list = False
            if in_ol:
                out.append("</ol>"); in_ol = False
            out.append(f"<h3>{line[4:].strip()}</h3>")
        elif re.match(r"^\d+\.\s", line):
            if in_list:
                out.append("</ul>"); in_list = False
            if not in_ol:
                out.append("<ol>"); in_ol = True
            content = re.sub(r"^\d+\.\s", "", line)
            out.append(f"<li>{_inline_md(content)}</li>")
        elif line.startswith("- ") or line.startswith("* "):
            if in_ol:
                out.append("</ol>"); in_ol = False
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline_md(line[2:])}</li>")
        elif line.strip() == "" or line.strip() == "---":
            if in_list:
                out.append("</ul>"); in_list = False
            if in_ol:
                out.append("</ol>"); in_ol = False
            if line.strip() == "---":
                out.append("<hr>")
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            if in_ol:
                out.append("</ol>"); in_ol = False
            out.append(f"<p>{_inline_md(line)}</p>")

    if in_list:
        out.append("</ul>")
    if in_ol:
        out.append("</ol>")
    return "\n".join(out)


def _inline_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


SCRIPTS = {
    "weekly_keywords": {
        "label": "Ключевые слова",
        "script": "weekly_keywords.py",
        "apply": True,
        "description": "Единый еженедельный анализ: поисковые запросы + метрики ключей. Один проход Claude формирует три согласованных списка: пауза / минус-слова / новые ключи.",
        "group": "Еженедельно",
        "icon": "search",
    },
    "ads_analysis": {
        "label": "Кампании и объявления",
        "script": "ads_analysis.py",
        "apply": True,
        "description": "Метрики кампаний, RSA заголовки и тексты, аукционы, бюджетные алерты. Preview + применение замен объявлений.",
        "group": "Еженедельно",
        "icon": "chart-bar",
    },
    "crm_sync": {
        "label": "CRM синхронизация",
        "script": "crm_sync.py",
        "apply": True,
        "description": "Офлайн-конверсии из AmoCRM в Google Ads + выгрузка контактов для Customer Match.",
        "group": "Еженедельно",
        "icon": "link",
    },
    "analyst": {
        "label": "AI-анализ (стратегия)",
        "script": "analyst.py",
        "apply": False,
        "description": "Агент читает данные собранных скриптов + GA4 воронку + CRM. Claude-агент пишет стратегический анализ и рекомендации.",
        "group": "Еженедельно",
        "icon": "lightning",
    },
    "competitor_research": {
        "label": "Конкуренты",
        "script": "competitor_research_agent.py",
        "apply": False,
        "description": "Исследование конкурентов по всем аккаунтам через веб-поиск. Запускать раз в месяц или по ситуации.",
        "group": "Периодически",
        "icon": "globe",
    },
    "conversion_path": {
        "label": "Конверсионный путь",
        "script": "conversion_path.py",
        "apply": False,
        "description": "GA4: первое/последнее касание и ассистирующие конверсии по каналам. Запускать ежемесячно.",
        "group": "Периодически",
        "icon": "map",
    },
    "call_correlation": {
        "label": "Корреляция звонков",
        "script": "call_correlation.py",
        "apply": False,
        "description": "Сопоставление кликов по телефону (GA4) и звонков в AmoCRM. Только для аккаунтов с call-трекингом.",
        "group": "Периодически",
        "icon": "phone",
    },
}


def run_script_stream(script_key: str, apply: bool = False):
    config = SCRIPTS.get(script_key)
    if not config:
        yield "data: [ERROR] Скрипт не найден\n\n"
        return

    cmd = [PYTHON, str(BASE_DIR / config["script"])]
    if apply and config.get("apply"):
        cmd.append("--apply")
    if not apply and "extra_args" in config:
        cmd.extend(config["extra_args"])

    yield f"data: > {' '.join(cmd[1:])}\n\n"

    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
            env=env,
        )

        for raw in process.stdout:
            for enc in ("utf-8", "cp1251", "cp866"):
                try:
                    line = raw.decode(enc).rstrip()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                line = raw.decode("ascii", errors="replace").rstrip()
            if line:
                yield f"data: {line}\n\n"

        process.wait()
        code = process.returncode
        if code == 0:
            yield "data: [DONE]\n\n"
        else:
            yield f"data: [ERROR] Код завершения: {code}\n\n"

    except Exception as e:
        yield f"data: [ERROR] {e}\n\n"


@app.route("/")
def index():
    order = ["Еженедельно", "Периодически"]
    raw = {}
    for key, cfg in SCRIPTS.items():
        g = cfg["group"]
        raw.setdefault(g, []).append({"key": key, **cfg})
    groups = {g: raw[g] for g in order if g in raw}
    return render_template("index.html", groups=groups)


@app.route("/stream/<script_key>")
def stream(script_key: str):
    apply = request.args.get("apply") == "1"

    return Response(
        stream_with_context(run_script_stream(script_key, apply=apply)),
        mimetype="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@app.route("/dashboard")
def dashboard():
    from full_report import collect_full_report

    days = int(request.args.get("days", 30))
    date_from = request.args.get("from") or None
    date_to = request.args.get("to") or None

    try:
        data = collect_full_report(days=days, date_from=date_from, date_to=date_to)
    except Exception as e:
        return f"<pre>Ошибка: {e}</pre>", 500

    charts = _build_charts(data)

    return render_template(
        "dashboard.html",
        data=data,
        charts=charts,
        selected_days=days,
        selected_from=date_from or "",
        selected_to=date_to or "",
    )


@app.route("/analysis")
def analysis():
    data = None
    if ANALYSIS_FILE.exists():
        try:
            with open(ANALYSIS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for acc in data["accounts"].values():
                acc["analysis_html"] = markdown_to_html(acc.get("analysis", ""))
        except Exception as e:
            data = None

    return render_template("analysis.html", data=data)


@app.route("/export")
def export():
    import io
    import tempfile
    from full_report import collect_full_report

    days = int(request.args.get("days", 30))
    date_from = request.args.get("from") or None
    date_to = request.args.get("to") or None

    try:
        data = collect_full_report(days=days, date_from=date_from, date_to=date_to)
    except Exception as e:
        return f"<pre>Ошибка: {e}</pre>", 500

    charts = _build_charts(data)

    html = render_template(
        "export.html",
        data=data,
        charts=charts,
    )

    buf = io.BytesIO(html.encode("utf-8"))
    filename = f"dashboard_{data['start_date']}_{data['end_date']}.html"
    return send_file(buf, mimetype="text/html", as_attachment=True, download_name=filename)


if __name__ == "__main__":
    print("Google Ads Dashboard")
    print("Открыть: http://localhost:5000")
    app.run(debug=False, host="127.0.0.1", port=5000, threaded=True)
