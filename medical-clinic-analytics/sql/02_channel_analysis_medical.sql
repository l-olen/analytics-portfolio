-- ============================================================
-- MEDICAL: Анализ каналов, воронка по источникам, тренды
-- Данные: crm_leads + ga4_sessions + ga4_events (medical.db)
-- Период: июл 2025 – июн 2026
-- ============================================================
-- ВАЖНО — архитектура воронок:
--   Старая система (до окт 2025): База (10176374) = основной поток
--   Новая система (с окт 2025):   Касание/Квалификация (7844402) = основной поток
--   База сейчас = корзина отклонённых + исторические лиды до окт 2025
--   Октябрь 2025 = точка разрыва: массовое закрытие старых лидов в Базе
--   Анализ новой системы → только pipeline_id=7844402 с created_at >= 2025-10-01
--
-- ОГРАНИЧЕНИЯ ДАННЫХ:
--   1. Звонки (главный канал): нет call tracking → атрибуция к кампании невозможна
--   2. Формы→CRM: интеграция работала нестабильно до дек 2025 (см. Q7)
--   3. Соцсети (Instagram/Telegram): source='other', нет автоматической разметки
--   Следствие: реальный вклад платного трафика в приёмы измерить нельзя без call tracking

-- ─────────────────────────────────────────────────────────────
-- Q1. ВОРОНКА ПО ИСТОЧНИКАМ — все лиды (все воронки, весь период)
-- ─────────────────────────────────────────────────────────────
SELECT
    source,
    COUNT(*)                                                              AS leads,
    SUM(CASE WHEN status='won'         THEN 1 ELSE 0 END)                AS won,
    SUM(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                AS lost,
    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                AS active,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) AS cr_pct
FROM crm_leads
GROUP BY source
ORDER BY leads DESC;

/*
РЕЗУЛЬТАТ (июл 2025 – июн 2026):
  other         17371  won=4136  lost=8974  active=4261  CR=23.8%
  call           9942  won=3213  lost=4686  active=2043  CR=32.3%
  site_organic   1909  won= 266  lost=1456  active= 187  CR=13.9%
  site_paid       503  won=  30  lost= 355  active= 118  CR= 6.0%

NB: "won" здесь = квалифицирован внутри своей воронки (зависит от pipeline).
В Базе "won" = закрыто (часто массово). В Касании "won" = готов к записи.
Для реальной конверсии к приёму → Q4.
*/

-- ─────────────────────────────────────────────────────────────
-- Q2. АНОМАЛИЯ: ОКТЯБРЬ 2025 — расшифровка
-- ─────────────────────────────────────────────────────────────
SELECT
    pipeline_id,
    status,
    COUNT(*) leads
FROM crm_leads
WHERE strftime('%Y-%m', created_at) = '2025-10'
GROUP BY pipeline_id, status
ORDER BY pipeline_id, leads DESC;

/*
РЕЗУЛЬТАТ:
  pipeline=10176374 (База) won=2929 lost=635 → массовое закрытие при запуске Касания
  pipeline=7844402 (Касание) lost=1262 won=74 → первый месяц новой системы
  pipeline=10176362 (Назначение) won=161 lost=18 → обычный поток записей

Объяснение: при переводе на новую систему старые лиды в Базе были массово закрыты.
Октябрь 2025 в сводных отчётах = ИСКЛЮЧИТЬ или пометить как артефакт перехода.
*/

-- ─────────────────────────────────────────────────────────────
-- Q3. ВОРОНКА В КАСАНИИ — контактный уровень (новая система)
-- Отражает реальные показатели обработки лидов с окт 2025
-- ─────────────────────────────────────────────────────────────
WITH contacts AS (
    SELECT contact_id,
           MAX(source)                                                    AS source,
           MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)         AS won,
           MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)         AS lost,
           MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)         AS active
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
)
SELECT
    source,
    COUNT(*)                                                              AS contacts,
    SUM(won)                                                              AS qualified,
    SUM(lost)                                                             AS rejected,
    SUM(active)                                                           AS in_work,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                      AS qual_pct
FROM contacts
GROUP BY source
ORDER BY contacts DESC;

/*
РЕЗУЛЬТАТ (контакты в Касании с окт 2025):
  other         3714  квалиф=438  отклон=2991  в работе=305  12%
  call          1826  квалиф=394  отклон=1488  в работе=  2  22%
  site_organic   638  квалиф= 26  отклон= 615  в работе=  1   4%
  site_paid      360  квалиф= 15  отклон= 346  в работе=  0   4%

"Квалифицирован" в Касании = won = готов к записи на приём.
Итого 6538 контактов, 873 квалифицированы (13.4%).
call — наилучшая квалификация (22%), платный сайт — наихудшая (4%).
*/

-- ─────────────────────────────────────────────────────────────
-- Q4. END-TO-END ВОРОНКА: Касание → реальный приём
-- Источник входа × сколько дошли до pipeline 10176362 won
-- ─────────────────────────────────────────────────────────────
WITH kach_contacts AS (
    SELECT contact_id, MAX(source) AS source
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
),
had_appt AS (
    SELECT DISTINCT contact_id FROM crm_leads
    WHERE pipeline_id=10176362 AND status='won'
)
SELECT
    k.source,
    COUNT(DISTINCT k.contact_id)                                          AS entered,
    COUNT(DISTINCT a.contact_id)                                          AS got_appt,
    ROUND(100.0*COUNT(DISTINCT a.contact_id)/COUNT(DISTINCT k.contact_id),1) AS cr_pct
FROM kach_contacts k
LEFT JOIN had_appt a ON k.contact_id=a.contact_id
GROUP BY k.source
ORDER BY entered DESC;

/*
РЕЗУЛЬТАТ (end-to-end: Касание вход → факт приёма):
  other         3714  → 319 приёмов   CR=8.6%
  call          1826  → 380 приёмов   CR=20.8%  ← главный канал конверсии
  site_organic   638  →  19 приёмов   CR=3.0%
  site_paid      360  →  10 приёмов   CR=2.8%

Итого Касание: 6538 → 728 → CR=11.1%
ВАЖНО: 'other' включает Instagram, Telegram, WhatsApp, сарафанку без разметки.
call CR=20.8% — реальный бенчмарк для оценки качества звонкового канала.
site_paid CR=2.8% — нижняя граница: часть платных лидов классифицирована как 'other'.
*/

-- ─────────────────────────────────────────────────────────────
-- Q5. МЕСЯЧНЫЙ ТРЕНД В КАСАНИИ (новая система, окт 2025+)
-- ─────────────────────────────────────────────────────────────
WITH contacts AS (
    SELECT contact_id,
           strftime('%Y-%m', MIN(created_at))                             AS m,
           MAX(source)                                                    AS source,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END)                  AS won
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
)
SELECT
    m,
    COUNT(*)                                                              AS contacts,
    SUM(won)                                                              AS qualified,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                      AS qual_pct,
    SUM(CASE WHEN source='call'         THEN 1 ELSE 0 END)               AS call_n,
    SUM(CASE WHEN source='site_paid'    THEN 1 ELSE 0 END)               AS paid_n,
    SUM(CASE WHEN source='site_organic' THEN 1 ELSE 0 END)               AS organic_n,
    SUM(CASE WHEN source='other'        THEN 1 ELSE 0 END)               AS other_n
FROM contacts
GROUP BY m
ORDER BY m;

/*
РЕЗУЛЬТАТ:
  2025-10  1203  квал=  14  1.2%  | call=280  paid=  0  org= 53  other=870
  2025-11   484  квал=  35  7.2%  | call=218  paid=  1  org= 37  other=228
  2025-12   217  квал=  13  6.0%  | call= 68  paid=  4  org= 27  other=118
  2026-01   714  квал=  38  5.3%  | call=145  paid=  9  org=175  other=385
  2026-02   606  квал=  91 15.0%  | call=122  paid= 14  org= 30  other=440
  2026-03   600  квал=  82 13.7%  | call=138  paid= 11  org= 40  other=411
  2026-04   510  квал= 161 31.6%  | call=211  paid= 12  org= 41  other=246
  2026-05   841  квал= 253 30.1%  | call=327  paid= 51  org= 45  other=418
  2026-06  1363  квал= 186 13.6%  | call=317  paid=258  org=190  other=598

ТРЕНДЫ:
- Окт 2025: первый месяц, все лиды ещё "в работе" → CR=1.2% (артефакт)
- Нояб–янв: CR 5-7%, нормальный разгон новой системы
- Фев–май 2026: CR 13-32% — стабильный рабочий режим
- Апр–май: CR 30%+ — пик (сезонность? акции?)
- Июн 2026: CR падает до 14% при +62% объёма → новый сайт дал много неквала
  site_paid = 258 (x5 vs апрель) — форма нового сайта заработала 23.06
*/

-- ─────────────────────────────────────────────────────────────
-- Q6. GA4 КАНАЛЫ — сессии и конверсии (12 мес)
-- ─────────────────────────────────────────────────────────────
SELECT
    channel,
    SUM(sessions)                                                         AS sessions,
    ROUND(SUM(conversions))                                               AS conversions,
    ROUND(100.0*SUM(conversions)/SUM(sessions),2)                         AS cr_pct
FROM ga4_sessions
GROUP BY channel
ORDER BY sessions DESC;

/*
РЕЗУЛЬТАТ:
  Cross-network   49230  conv=4034  CR=8.2%  ← PMax кампании
  Organic Search  22035  conv= 303  CR=1.4%
  Paid Search     14673  conv=1497  CR=10.2% ← обычный поиск
  Direct           7068  conv= 271  CR=3.8%
  Organic Social   3270  conv=  23  CR=0.7%
  Display           702  conv=   9  CR=1.3%

"Конверсии" в GA4 = click_number (4610), form_call_submit (353) и другие key events.
Главная конверсия клиники = click_number (клик по номеру) = 90% всех конверсий.
GA4 Cross-network 8.2% CR vs Paid Search 10.2% — обе кампании работают сопоставимо.
*/

-- ─────────────────────────────────────────────────────────────
-- Q7. GA4 paid СЕССИИ vs CRM site_paid ЛИДЫ — по месяцам
-- Показывает масштаб gap: сколько paid сессий не доходят в CRM
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', g.date)                                             AS month,
    SUM(CASE WHEN g.channel IN ('Cross-network','Paid Search')
        THEN g.sessions ELSE 0 END)                                       AS ga4_paid_sessions,
    ROUND(SUM(CASE WHEN g.channel IN ('Cross-network','Paid Search')
        THEN g.conversions ELSE 0 END))                                   AS ga4_paid_conv
FROM ga4_sessions g
GROUP BY month
ORDER BY month;

-- (Для сравнения с CRM site_paid — JOIN через Python или вручную):
-- CRM site_paid по месяцам:
SELECT
    strftime('%Y-%m', created_at)                                         AS month,
    COUNT(*)                                                              AS crm_site_paid
FROM crm_leads
WHERE source='site_paid'
GROUP BY month
ORDER BY month;

/*
СРАВНЕНИЕ (GA4 paid конверсии vs CRM site_paid лиды):
  2025-07: GA4=526 | CRM=0   ← форма-CRM интеграция не работала
  2025-08: GA4=599 | CRM=0
  2025-09: GA4=668 | CRM=0
  2025-10: GA4=276 | CRM=0
  2025-11: GA4=379 | CRM=1
  2025-12: GA4=408 | CRM=8   ← интеграция появилась
  2026-01: GA4=686 | CRM=24  ← GA4 в 28x больше (звонки + формы vs только формы CRM)
  2026-02: GA4=476 | CRM=37
  2026-03: GA4=480 | CRM=22
  2026-04: GA4=120 | CRM=25
  2026-05: GA4=517 | CRM=64
  2026-06: GA4=396 | CRM=322 ← новый сайт: форма работает, разрыв минимален

GA4 "конверсии" ≠ CRM лиды: большинство GA4 conv = клики по номеру (звонки),
в CRM попадают как source='call', а не 'site_paid'. Это объясняет постоянный разрыв.
*/

-- ─────────────────────────────────────────────────────────────
-- Q8. КОНВЕРСИОННЫЕ СОБЫТИЯ GA4 (paid vs organic)
-- ─────────────────────────────────────────────────────────────
SELECT
    event_label,
    SUM(total)                                                            AS total,
    SUM(paid)                                                             AS paid,
    ROUND(100.0*SUM(paid)/SUM(total),1)                                   AS paid_share_pct
FROM ga4_events
GROUP BY event_label
ORDER BY total DESC;

/*
РЕЗУЛЬТАТ:
  click_number              5066   4613   91%  ← главная "конверсия" = клик по номеру
  form_call_submit           353    315   89%  ← старая форма, до нового сайта
  form_start                  62     56   90%
  form_appointment_side_submit 23    23  100%  ← новая форма (с 23.06.2026)
  form_submit                 16     16  100%
  click_instagram              7      7  100%

Платный трафик генерирует 91% кликов по номеру и 89% отправок форм.
Всего paid форм: 315 + 23 + 16 = 354 за год → сопоставимо с CRM site_paid (503).
Главный инструмент конверсии клиники — ЗВОНОК, не форма.
Без call tracking ROI платного трафика неизмерим.
*/

-- ─────────────────────────────────────────────────────────────
-- Q9. ИТОГОВОЕ РЕЗЮМЕ — для обсуждения с CMO
-- ─────────────────────────────────────────────────────────────
/*
КАНАЛЬНАЯ ВОРОНКА (новая система, окт 2025 – июн 2026):

                Вход     → Квалиф  → Приём    | CR квал  CR приём
  call          1826     →  394    →  380      | 22%      20.8%
  other         3714     →  438    →  319      |  12%      8.6%
  site_paid      360     →   15    →   10      |   4%      2.8%
  site_organic   638     →   26    →   19      |   4%      3.0%
  ИТОГО         6538     →  873    →  728      |  13%     11.1%

КЛЮЧЕВЫЕ ВЫВОДЫ:
1. Звонки = лучший канал (CR 20.8%), но без call tracking не знаем откуда звонки.
2. 'other' (57% всего потока) = соцсети/мессенджеры. CR 8.6% — хороший результат,
   но нельзя разбить на Instagram/Telegram/WhatsApp без автотеггинга.
3. Платный трафик site_paid: нижняя граница 2.8% CR. Реальная цифра выше,
   т.к. часть платных лидов звонит → попадает в 'call'.
4. Июнь 2026: новый сайт дал x5 site_paid лидов, CR Касания упал (много неквала
   с форм) — нормально для первого месяца, нужно мониторить.

ЧТО НУЖНО ПОЧИНИТЬ (приоритет):
1. Call tracking (Calltouch/CoMagic) — разблокирует атрибуцию 90% конверсий
2. Автотеггинг Instagram/Telegram (виджет Калькулятор полей) — расшифрует 'other'
3. UTM→CRM на новом сайте — мониторинг уже работает (форма починена 23.06)
*/
