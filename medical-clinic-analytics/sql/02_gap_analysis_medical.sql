-- Gap Analysis: GA4 (платный трафик) vs CRM (лиды)
-- Цель: найти где и почему теряются данные между рекламными системами и CRM

-- ─────────────────────────────────────────────
-- 1. Сессии и конверсии по каналам (GA4)
-- ─────────────────────────────────────────────
SELECT
    channel,
    SUM(sessions)     AS sessions_total,
    SUM(conversions)  AS conversions_total
FROM ga4_sessions
GROUP BY channel
ORDER BY sessions_total DESC;

/*
РЕЗУЛЬТАТ:
Cross-network    48808    4027   ← PMax (utm_campaign=km_max|...)
Organic Search   22001     302
Paid Search      14660    1497   ← обычный поиск (utm_medium=cpc)
Direct            7048     270
Organic Social    3267      23
Display            702       9

Платный трафик суммарно: ~63k сессий, ~5.5k "конверсий" в GA4.
NB: "конверсии" в GA4 = все key events вместе (формы + клики по номеру).
*/

-- ─────────────────────────────────────────────
-- 2. Конверсионные события с разбивкой paid/total
-- ─────────────────────────────────────────────
SELECT
    event_label,
    SUM(total) AS total,
    SUM(paid)  AS paid
FROM ga4_events
WHERE event_label IN (
    'form_call_submit',
    'form_appointment_side_submit',
    'form_submit',
    'click_number',
    'click_instagram'
)
GROUP BY event_label;

/*
РЕЗУЛЬТАТ:
click_number                   5075    4610  ← главная конверсия клиники
form_call_submit                353     315  ← основная форма (старый сайт)
form_appointment_side_submit     20      20  ← боковая форма (была на обоих сайтах)
form_submit                      16      16
click_instagram                   7       7

Формы итого (paid): 315 + 20 + 16 = 351
Звонки (paid): 4610 → в 13x больше чем форм.
Клиника конвертирует через звонок, а не через форму.

NB по июню: после запуска нового сайта 23.06 GA4 зафиксировал 25 form_appointment_side_submit,
в CRM осталось 12 заявок — остальные удалены как тестовые. Расхождение объяснено, не баг.
*/

-- ─────────────────────────────────────────────
-- 3. GA4 paid forms vs CRM site_paid по месяцам
-- ─────────────────────────────────────────────
SELECT
    month,
    MAX(ga4_paid_forms) AS ga4_paid_forms,
    MAX(crm_site_paid)  AS crm_site_paid
FROM (
    SELECT strftime('%Y-%m', date) AS month,
           SUM(paid) AS ga4_paid_forms,
           0         AS crm_site_paid
    FROM ga4_events
    WHERE event_label = 'form_call_submit'
    GROUP BY month

    UNION ALL

    SELECT strftime('%Y-%m', created_at) AS month,
           0,
           COUNT(*)
    FROM crm_leads
    WHERE source = 'site_paid'
    GROUP BY month
)
GROUP BY month
ORDER BY month;

/*
РЕЗУЛЬТАТ:
2025-07      6      0   ← форма на сайте была, но в CRM не попадало
2025-08      4      0
2025-09      2      0
2025-10      7      0
2025-11      3      1
2025-12      8      8   ← интеграция заработала
2026-01     99     24   ← GA4 видит в 4x больше чем CRM
2026-02     32     37
2026-03     10     22
2026-04      0     25   ← событие переименовано на новом сайте
2026-05     25     64
2026-06    119    322   ← запуск нового сайта 23.06 + смена event name

Ключевое: форма на новом сайте называется иначе (form_appointment_side_submit
вместо form_call_submit), поэтому июньские данные несопоставимы с ранними.
*/

-- ─────────────────────────────────────────────
-- 4. Реальный бизнес-результат по источникам
--    (только воронка Назначение/приём = факт визита)
-- ─────────────────────────────────────────────
SELECT
    source,
    COUNT(*)                                                    AS leads,
    SUM(CASE WHEN status = 'won' THEN 1 END)                   AS won,
    ROUND(100.0 * SUM(CASE WHEN status = 'won' THEN 1 END)
          / COUNT(*), 1)                                        AS conv_pct
FROM crm_leads
WHERE pipeline_id = 10176362
GROUP BY source
ORDER BY leads DESC;

/*
РЕЗУЛЬТАТ:
other        1527    1500    98.2  ← соцсети, мессенджеры, реферальные
call          991     971    98.0  ← звонки (без атрибуции к платному)
site_organic   72      70    97.2
site_paid      16      16   100.0  ← из 510 site_paid лидов только 16 дошли до приёма

Платный трафик: 510 лидов в CRM, но до реального приёма доходят только 16 (3.1%).
Остальные 494 оседают в воронке "База" без дальнейшего движения.
*/

-- ─────────────────────────────────────────────
-- 5. Дубли в site_paid лидах
-- ─────────────────────────────────────────────
SELECT
    COUNT(*) AS contacts_with_duplicates
FROM (
    SELECT contact_id
    FROM crm_leads
    WHERE source = 'site_paid'
      AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING COUNT(*) > 1
);

/*
РЕЗУЛЬТАТ: 15 контактов с двумя лидами → 15 лишних записей.

Итоговый gap:
  CRM site_paid:       510
  минус дубли:         -15
  Уникальных лидов:    495
  GA4 paid forms:      351
  Разница:             144

Объяснение 144: разная логика атрибуции.
CRM берёт UTM из URL напрямую (всегда есть если клик был из рекламы).
GA4 атрибутирует сессию через куки — блокируется адблокерами,
сбрасывается при переходах. Поэтому CRM точнее для атрибуции конкретного лида,
GA4 точнее для анализа поведения на сайте.
*/

-- ─────────────────────────────────────────────
-- 6. Реальная end-to-end воронка по источнику входа
--    База → Назначение/приём (через contact_id)
-- ─────────────────────────────────────────────
SELECT
    b.source                                              AS entry_source,
    COUNT(DISTINCT b.contact_id)                         AS contacts_in_base,
    COUNT(DISTINCT a.contact_id)                         AS got_appointment,
    ROUND(100.0 * COUNT(DISTINCT a.contact_id)
          / COUNT(DISTINCT b.contact_id), 1)             AS conversion_pct
FROM crm_leads b
LEFT JOIN (
    SELECT DISTINCT contact_id
    FROM crm_leads
    WHERE pipeline_id = 10176362
      AND status = 'won'
) a ON b.contact_id = a.contact_id
WHERE b.pipeline_id = 10176374
  AND b.contact_id IS NOT NULL
GROUP BY b.source
ORDER BY contacts_in_base DESC;

/*
РЕЗУЛЬТАТ:
other        9697    1046    10.8
call         4091     664    16.2
site_organic 1133      62     5.5
site_paid     117      11     9.4  ← 117 уникальных контактов, не 510 лидов

Настоящий end-to-end CR: из всех кто попал в Базу по источнику — сколько
дошли до реального приёма. Call (16.2%) > site_paid (9.4%) > other (10.8%) > organic (5.5%).

ВАЖНО: site_paid = нижняя граница. Часть платных контактов у которых UTM
не попал в CRM (78% случаев) классифицированы как "other". Реальный CR
из платного трафика выше 9.4% но точно измерить невозможно без исправления
интеграции форма→CRM.
*/

-- ─────────────────────────────────────────────
-- 7. Касание/Квалификация → Назначение (через contact_id)
-- ─────────────────────────────────────────────
SELECT
    COUNT(DISTINCT k.contact_id)  AS contacts_in_kachestvo,
    COUNT(DISTINCT a.contact_id)  AS got_appointment,
    ROUND(100.0 * COUNT(DISTINCT a.contact_id)
          / COUNT(DISTINCT k.contact_id), 1) AS conv_pct
FROM crm_leads k
LEFT JOIN (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id = 10176362 AND status = 'won'
) a ON k.contact_id = a.contact_id
WHERE k.pipeline_id = 7844402
  AND k.contact_id IS NOT NULL;

-- РЕЗУЛЬТАТ: 6554 → 728 → 11.1% (сопоставимо с другими источниками в Базе)

-- Пересечение: сколько контактов Касания также были в Базе
SELECT
    COUNT(DISTINCT k.contact_id)                              AS in_kachestvo,
    COUNT(DISTINCT b.contact_id)                              AS also_in_base,
    ROUND(100.0 * COUNT(DISTINCT b.contact_id)
          / COUNT(DISTINCT k.contact_id), 1)                  AS overlap_pct
FROM crm_leads k
LEFT JOIN (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id = 10176374
) b ON k.contact_id = b.contact_id
WHERE k.pipeline_id = 7844402
  AND k.contact_id IS NOT NULL;

/*
РЕЗУЛЬТАТ: 6554 → 1035 → 15.8% пересечение с Базой.
84% контактов в Касании — отдельные люди, никогда не бывшие в Базе.
Касание = самостоятельный входной поток, не продолжение Базы.
15.8% пересечения — скорее всего ручное дублирование менеджерами.
*/

-- ─────────────────────────────────────────────
-- 8. Полная воронка: все пути контакта к приёму
-- ─────────────────────────────────────────────
WITH
in_base AS (SELECT DISTINCT contact_id FROM crm_leads WHERE pipeline_id = 10176374),
in_kach AS (SELECT DISTINCT contact_id FROM crm_leads WHERE pipeline_id = 7844402),
in_appt AS (SELECT DISTINCT contact_id FROM crm_leads
             WHERE pipeline_id = 10176362 AND status = 'won'),
all_contacts AS (
    SELECT contact_id FROM in_base
    UNION SELECT contact_id FROM in_kach
)
SELECT
    CASE
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NOT NULL AND a.contact_id IS NOT NULL
            THEN 'База + Касание → Приём'
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NULL  AND a.contact_id IS NOT NULL
            THEN 'База → Приём'
        WHEN b.contact_id IS NULL  AND k.contact_id IS NOT NULL AND a.contact_id IS NOT NULL
            THEN 'Касание → Приём'
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NOT NULL AND a.contact_id IS NULL
            THEN 'База + Касание (без приёма)'
        WHEN b.contact_id IS NOT NULL AND k.contact_id IS NULL  AND a.contact_id IS NULL
            THEN 'Только База'
        ELSE 'Только Касание'
    END                            AS journey,
    COUNT(*)                       AS contacts
FROM all_contacts c
LEFT JOIN in_base b ON c.contact_id = b.contact_id
LEFT JOIN in_kach k ON c.contact_id = k.contact_id
LEFT JOIN in_appt a ON c.contact_id = a.contact_id
GROUP BY journey
ORDER BY contacts DESC;

/*
РЕЗУЛЬТАТ:
Только База              12720  62%  ← не двигаются дальше
Только Касание            5396  26%  ← не двигаются дальше
База → Приём              1113   5%  ← прямой путь, минуя Касание
База + Касание → Приём     604   3%  ← прошли оба этапа
База + Касание (без)       431   2%  ← прошли оба, но не дошли
Касание → Приём            124   1%  ← сразу в приём из Касания

Итого контактов:  20,388
Итого с приёмом:   1,841  (9%)

ВЫВОДЫ:
1. 88% контактов не доходят до приёма — оседают в Базе или Касании
2. Два пути к приёму: База→Приём (1113) и через Касание (728 = 604+124)
3. Касание работает как квалификатор: CR 11.1% vs ~8% напрямую из Базы
4. Горячий сегмент потерь: 431 контакт прошли оба этапа, но не дошли до приёма
   — это люди с высоким вовлечением, стоит анализировать отдельно
5. Реальный end-to-end CR всей воронки: 9% от всех вошедших контактов
*/

-- ─────────────────────────────────────────────
-- 9. Смена логики воронок: когда База перестала быть точкой входа
-- ─────────────────────────────────────────────
WITH first_lead AS (
    SELECT contact_id, pipeline_id AS first_pipeline,
           MIN(created_at) AS first_date
    FROM crm_leads
    WHERE contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT
    strftime('%Y-%m', first_date)                              AS month,
    SUM(CASE WHEN first_pipeline = 10176374 THEN 1 END)       AS entered_base,
    SUM(CASE WHEN first_pipeline = 7844402  THEN 1 END)       AS entered_kach,
    SUM(CASE WHEN first_pipeline NOT IN (10176374, 7844402)
             THEN 1 END)                                       AS other
FROM first_lead
GROUP BY month
ORDER BY month;

/*
РЕЗУЛЬТАТ (первый лид контакта по воронке):
2025-07    859     3    84   ← почти всё через Базу
2025-08   2574     8    38
2025-09   1748     8    75
2025-10   2028  1163   142   ← ПЕРЕХОД: Касание запущено в октябре
2025-11    779   429   387
2025-12    885   205   245
2026-01    558   693   315   ← Касание обгоняет Базу
2026-02    553   590   206
2026-03    546   572   259
...

АРХИТЕКТУРА ВОРОНОК (выяснили из настроек AmoCRM):

Старая система (до окт 2025):
  Новый лид → База (Неразобранное включено) → квалификация → Назначение/Приём

Новая система (с окт 2025):
  Новый лид → Касание/Квалификация (Неразобранное включено, База выключено)
      ↓ квалифицирован      ↓ закрыт (7 причин)    ↓ закрыт (3 причины)
  Встреча назначена       База "Отказ/игнор"       База "Не квал лиды"

База сейчас = архив отклонённых + старые лиды до октября 2025.
Неразобранное в Базе — ВЫКЛЮЧЕНО с момента перехода на новую систему.

Источники в Касании: Telegram, Instagram (мессенджер + комментарии),
Facebook, CRM Plugin сайта, Google Таблица.
Источник поля "Источник" — заполняется менеджерами вручную (ненадёжно).
Автотеггинг Instagram/Telegram требует виджета "Калькулятор полей" или API.
*/

-- ─────────────────────────────────────────────
-- 10. Воронка по эрам: старая система vs новая
-- ─────────────────────────────────────────────
WITH
first_lead AS (
    SELECT contact_id, pipeline_id AS first_pipeline,
           MIN(created_at) AS first_date
    FROM crm_leads
    WHERE contact_id IS NOT NULL
    GROUP BY contact_id
),
got_appt AS (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id = 10176362 AND status = 'won'
)
SELECT
    CASE
        WHEN fl.first_pipeline = 10176374 AND fl.first_date < '2025-10-01'
            THEN '1. Старая система: вход через Базу'
        WHEN fl.first_pipeline = 7844402
            THEN '2. Новая система: вход через Касание'
        WHEN fl.first_pipeline = 10176374 AND fl.first_date >= '2025-10-01'
            THEN '3. База после окт (отклонённые из Касания)'
        ELSE '4. Прямая запись (Назначение/Повторные)'
    END                              AS segment,
    COUNT(*)                         AS contacts,
    COUNT(ga.contact_id)             AS got_appointment,
    ROUND(100.0 * COUNT(ga.contact_id) / COUNT(*), 1) AS conv_pct
FROM first_lead fl
LEFT JOIN got_appt ga ON fl.contact_id = ga.contact_id
GROUP BY segment
ORDER BY segment;

/*
РЕЗУЛЬТАТ:
1. Старая система (База до окт):    5195 → 76  → 1.5% CR
2. Новая система (Касание):         6273 → 574 → 9.2% CR  ← рабочий бенчмарк
3. База после окт (отклонённые):    7717 → 68  → 0.9% CR  ← подтверждено: корзина
4. Прямая запись:                   2252 → 1297 → 57.6%   ← артефакт: вошли сразу в Назначение

ВЫВОДЫ:
- Новая система (Касание) работает в 6x лучше старой: 9.2% vs 1.5%
- 7,717 отклонённых > 6,273 активных — высокий % неквала, норма для клиники
- "Прямая запись" (57.6%) — не конверсия воронки, а менеджер сразу создал лид в Назначении
- Данные за год несопоставимы напрямую: октябрь 2025 = точка разрыва в логике
*/

-- ─────────────────────────────────────────────
-- ИТОГОВАЯ ИСТОРИЯ (для портфолио и интервью)
-- ─────────────────────────────────────────────
/*
ГЛАВНЫЙ ВОПРОС: какой ROI у платного трафика клиники?
ЧЕСТНЫЙ ОТВЕТ: измерить точно нельзя — три системных gap:

1. ЗВОНКИ (главный канал): 4,610 paid кликов по номеру в GA4
   → атрибуция к кампании невозможна без call tracking
   → владелец пока не готов к call tracking

2. ФОРМЫ: UTM форма→CRM работала нестабильно весь год
   → починено 30.06.2026 на новом сайте
   → исторические данные не восстановить

3. СОЦСЕТИ (Instagram/Telegram): нет автоматической разметки
   → поле "Источник" заполняется менеджерами вручную
   → автотеггинг требует доп. настройки (виджет или API)

ЧТО МОЖЕМ ИЗМЕРИТЬ:
- Новая система (Касание, окт 2025+): 9.2% CR — рабочий бенчмарк
- Отклонения: 7,717 из ~14k вошедших = ~55% не квалифицируются
- Платный трафик: 510 site_paid лидов, 11 дошли до приёма (нижняя граница)
- Главный канал конверсии — звонок, но он "чёрный ящик"

РЕКОМЕНДАЦИИ (приоритет):
1. Call tracking — разблокирует 90% attribution
2. UTM→CRM интеграция — починена, нужно мониторить
3. Автотеггинг соцсетей — виджет "Калькулятор полей" или прогер
*/
