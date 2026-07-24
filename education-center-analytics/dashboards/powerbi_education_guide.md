# Power BI — Education Center Dashboard

Данные: `dashboards/csv_demo/` (анонимизированные, spend x12, volume x4)

## Шаг 1 — Загрузка данных

Get Data → Text/CSV, подключай каждый файл отдельно:

| Имя таблицы в модели | Файл |
|---------------------|------|
| `ChannelFunnel` | `education_channel_funnel.csv` |
| `MonthlyTrend` | `education_monthly_trend.csv` |
| `ChannelMonthly` | `education_channel_monthly.csv` |
| `Campaigns` | `education_ads_campaigns.csv` |
| `AdsMonthly` | `education_ads_monthly.csv` |
| `Audience` | `education_audience.csv` |
| `CreativeThemes` | `education_creative_themes.csv` |

В Power Query для `MonthlyTrend`, `ChannelMonthly`, `AdsMonthly` — добавь вычисляемый столбец:
```
= Date.FromText([month] & "-01")
```
Назови `date`, тип → Date. Без этого тренд-оси сортируются как текст.

## Шаг 2 — Связи модели (Model View)

- `MonthlyTrend[month]` → `ChannelMonthly[month]` (1:M)
- `MonthlyTrend[month]` → `AdsMonthly[month]` (1:1)

`ChannelFunnel`, `Campaigns`, `Audience`, `CreativeThemes` — отдельные, без связей
(нет поля месяца).

## Шаг 3 — DAX меры

Создай таблицу `_Measures` (Enter Data → пустая), складывай туда:

```dax
Total Spend =
    SUM(AdsMonthly[spend_usd])

Total Impressions =
    SUM(AdsMonthly[impressions])

Total Clicks =
    SUM(AdsMonthly[clicks])

CTR % =
    DIVIDE([Total Clicks], [Total Impressions]) * 100

Total Contacts =
    SUM(ChannelFunnel[contacts])

Total Won =
    SUM(ChannelFunnel[won])

Overall CR % =
    DIVIDE([Total Won], [Total Contacts]) * 100

Avg CPL =
    DIVIDE(
        SUMX(Campaigns, Campaigns[spend_usd]),
        SUMX(Campaigns, Campaigns[crm_leads])
    )

CPA (won) =
    DIVIDE(
        SUMX(Campaigns, Campaigns[spend_usd]),
        SUMX(Campaigns, Campaigns[won])
    )

Audience CTR % =
    DIVIDE(SUM(Audience[clicks]), SUM(Audience[impressions])) * 100

Audience CVR % =
    DIVIDE(SUM(Audience[conversions]), SUM(Audience[clicks])) * 100

Creative CTR % =
    DIVIDE(SUM(CreativeThemes[clicks]), SUM(CreativeThemes[impressions])) * 100
```

Меры `Audience CTR/CVR %` и `Creative CTR %` — через `DIVIDE` от сумм, а не
через готовый столбец `ctr_pct`/`cvr_pct` из CSV: при группировке в чарте
Power BI иначе просуммирует сами проценты, а не пересчитает взвешенное
значение — цифры "поплывут".

## Страница 1 — Overview

**4 карточки** вверху (Card visual):
- `[Total Spend]` → формат `$#,##0` → подпись "Ad Spend (12 mo)"
- `[Total Contacts]` → подпись "Total Leads"
- `[Overall CR%]` → формат `0.0%` → подпись "Won Rate"
- `[Avg CPL]` → формат `$#,##0.0` → подпись "Avg CPL"

**Line chart** под карточками (70% ширины):
- X: `AdsMonthly[date]`
- Y1: `[Total Spend]` (синяя линия)
- Y2: `MonthlyTrend[contacts]` (оранжевая, Secondary axis)
- Заголовок: "Monthly Spend & Lead Volume"

**Donut chart** справа:
- Values: `ChannelFunnel[contacts]`
- Legend: `ChannelFunnel[channel]`
- Заголовок: "Leads by Channel"

## Страница 2 — Channel Funnel

**Clustered Bar** (горизонтальный, сортировка по contacts DESC):
- Y: `ChannelFunnel[channel]`
- X1: `ChannelFunnel[contacts]` (серый)
- X2: `ChannelFunnel[won]` (зелёный)
- Заголовок: "Contacts vs Won by Channel"

**Table** рядом:

| Колонки | Формат |
|---------|--------|
| channel | — |
| contacts | целое |
| won | целое |
| cr_pct | `0.0%` |

Условное форматирование на `cr_pct` — цветовая шкала (красный→зелёный).

## Страница 3 — Google Ads

**Scatter chart**:
- X: `Campaigns[spend_usd]`
- Y: `Campaigns[crm_leads]`
- Size: `Campaigns[won]`
- Details: `Campaigns[campaign_name]`
- Заголовок: "Spend vs Leads (bubble = won)"

**Table** ниже:

| Колонки | Формат |
|---------|--------|
| campaign_name | — |
| spend_usd | `$#,##0` |
| crm_leads | целое |
| cpl_usd | `$#,##0.0` |
| won | целое |
| cpa_usd | `$#,##0` |

Сортировка по `spend_usd` DESC. Conditional formatting на `cpl_usd`.

## Страница 4 — Trends

**Area chart** (верхняя половина):
- X: `ChannelMonthly[date]`
- Y: `ChannelMonthly[contacts]`
- Legend: `ChannelMonthly[channel]`
- Заголовок: "Lead Volume by Channel over Time"

**Line + Clustered Column** (нижняя половина):
- X: `MonthlyTrend[date]`
- Column: `MonthlyTrend[contacts]`
- Line: `AdsMonthly[spend_usd]`
- Заголовок: "Leads vs Ad Spend"

## Страница 5 — Audience & Creative

Важно на этой странице: `conversions`/`cvr_pct` в `Audience` — это конверсии
по трекингу Google Ads, не подтверждённые сделки из CRM (нет click-level
связи между аудиторным сегментом и конкретным лидом — ограничение API).
Стоит явно подписать это в подзаголовке страницы или текстовом блоке.

**Clustered Bar** (верхняя левая четверть, `Audience` с visual-level filter
`dimension = "age_range"`):
- Y: `Audience[segment_value]`
- X: `[Audience CVR %]`
- Заголовок: "Conversion Rate by Age"
- Сортировка по `[Audience CVR %]` DESC

**Clustered Bar** (верхняя правая четверть, `Audience` с filter
`dimension = "gender"`):
- Y: `Audience[segment_value]`
- X: `[Audience CVR %]`
- Заголовок: "Conversion Rate by Gender"

**Table** (нижняя левая четверть, `Audience`, filter `dimension = "age_range"`):

| Колонки | Формат |
|---------|--------|
| segment_value | — |
| impressions | целое |
| ctr_pct | `0.0%` |
| cvr_pct | `0.0%` |
| spend_usd | `$#,##0` |

**Bar chart** (нижняя правая четверть, `CreativeThemes`):
- Y: `CreativeThemes[theme]`
- X: `[Creative CTR %]`
- Заголовок: "CTR by Message Theme"
- Сортировка по `[Creative CTR %]` DESC
- Data label: значение `ctr_pct` + подпись `headlines_n` в tooltip
  ("сколько разных заголовков в теме")
- Условное форматирование столбца — цветовая шкала (красный→зелёный),
  чтобы сразу было видно провал темы "страх / проблема"
