-- ============================================================
-- MEDICAL: Тренды и сравнение периодов
-- Данные: crm_leads + ga4_sessions (medical.db)
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- Q1. МЕСЯЧНЫЙ ТРЕНД: все лиды по статусу (весь период)
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', created_at)                                         AS month,
    COUNT(*)                                                              AS leads,
    SUM(CASE WHEN status='won'         THEN 1 ELSE 0 END)                AS won,
    SUM(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                AS lost,
    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                AS active,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) AS cr_pct
FROM crm_leads
GROUP BY month
ORDER BY month;

/*
РЕЗУЛЬТАТ:
  2025-07   1143  won=349  lost=710  active=84  CR=30.5%
  2025-08   3129  won=359  lost=1985 active=785 CR=11.5%
  2025-09   2597  won=369  lost=1788 active=440 CR=14.2%
  2025-10   5114  won=3165 lost=1963 active=2   CR=61.9% ← АНОМАЛИЯ (переход систем)
  2025-11   2428  won=520  lost=1619 active=289 CR=21.4%
  2025-12   1761  won=310  lost=1169 active=282 CR=17.6%
  2026-01   2248  won=482  lost=1503 active=263 CR=21.4%
  2026-02   1794  won=317  lost=1199 active=278 CR=17.7%
  2026-03   1893  won=357  lost=1259 active=277 CR=18.9%
  2026-04   1918  won=451  lost=1154 active=313 CR=23.5%
  2026-05   2141  won=532  lost=1255 active=354 CR=24.8%
  2026-06   3545  won=423  lost=1810 active=1312 CR=11.9%

Октябрь 2025 CR=62% — артефакт: массовое закрытие старых лидов Базы при переходе
на новую систему. Исключать из трендового анализа.
Июнь 2026 CR=12%: много active (1312) — новый сайт, лиды ещё не обработаны.
*/

-- ─────────────────────────────────────────────────────────────
-- Q2. ТРЕНД ТОЛЬКО НОВОЙ СИСТЕМЫ (Касание, окт 2025+)
--     Убирает шум от старой Базы, показывает реальную динамику
-- ─────────────────────────────────────────────────────────────
WITH contacts AS (
    SELECT contact_id,
           strftime('%Y-%m', MIN(created_at))                             AS m,
           MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)         AS won,
           MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)         AS lost,
           MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)         AS active
    FROM crm_leads
    WHERE pipeline_id=7844402 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-10-01'
)
SELECT
    m                                                                     AS month,
    COUNT(*)                                                              AS contacts,
    SUM(won)                                                              AS qualified,
    SUM(lost)                                                             AS rejected,
    SUM(active)                                                           AS in_work,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                      AS qual_pct
FROM contacts
GROUP BY m
ORDER BY m;

/*
РЕЗУЛЬТАТ (Касание, контактный уровень):
  2025-10  1203  квал=  14  откл=908   работа=281  1.2% ← разгон
  2025-11   484  квал=  35  откл=437   работа= 12  7.2%
  2025-12   217  квал=  13  откл=199   работа=  5  6.0%
  2026-01   714  квал=  38  откл=659   работа= 17  5.3%
  2026-02   606  квал=  91  откл=504   работа= 11 15.0%
  2026-03   600  квал=  82  откл=504   работа= 14 13.7%
  2026-04   510  квал= 161  откл=343   работа=  6 31.6% ← пик
  2026-05   841  квал= 253  откл=567   работа= 21 30.1%
  2026-06  1363  квал= 186  откл=853   работа=324 13.6% ← новый сайт, много неквала
*/

-- ─────────────────────────────────────────────────────────────
-- Q3. GA4: МЕСЯЧНЫЙ ТРЕНД СЕССИЙ ПО КАНАЛАМ
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', date)                                               AS month,
    SUM(CASE WHEN channel='Cross-network' THEN sessions ELSE 0 END)      AS pmax_sess,
    SUM(CASE WHEN channel='Paid Search'   THEN sessions ELSE 0 END)      AS paid_search_sess,
    SUM(CASE WHEN channel='Organic Search' THEN sessions ELSE 0 END)     AS organic_sess,
    SUM(CASE WHEN channel='Direct'        THEN sessions ELSE 0 END)      AS direct_sess,
    SUM(CASE WHEN channel='Organic Social' THEN sessions ELSE 0 END)     AS social_sess,
    SUM(sessions)                                                         AS total_sess
FROM ga4_sessions
GROUP BY month
ORDER BY month;

/*
РЕЗУЛЬТАТ — топ-3 по каналам:
  2025-07  PMax=3048  Search=1742  Organic=1765
  2025-08  PMax=3255  Search=2128  Organic=2148
  2025-09  PMax=4047  Search=2253  Organic=2248
  2025-10  PMax=1499  Search= 593  Organic=1218  ← oct = сниженная активность
  2025-11  PMax=2946  Search=2336  Organic=1818
  2025-12  PMax=4047  Search=3682  Organic=1988
  2026-01  PMax=6480  Search=3073  Organic=1928
  2026-02  PMax=3073  Search= 634  Organic=1834
  2026-03  PMax=2526  Search= 438  Organic=1823
  2026-04  PMax= 595  Search= 438  Organic=1725  ← апр = низкий paid, но CR в CRM высокий
  2026-05  PMax=1853  Search= 724  Organic=2028
  2026-06  PMax=7861  Search=1573  Organic=2332  ← новый сайт, рост PMax
*/

-- ─────────────────────────────────────────────────────────────
-- Q4. СРАВНЕНИЕ: АПРЕЛЬ vs МАЙ 2026
-- Аномалия: апрель = минимум paid трафика, но максимум CR в Касании (32%)
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', date)                                               AS month,
    SUM(CASE WHEN channel IN ('Cross-network','Paid Search')
        THEN sessions ELSE 0 END)                                         AS paid_sess,
    ROUND(SUM(CASE WHEN channel IN ('Cross-network','Paid Search')
        THEN conversions ELSE 0 END))                                     AS paid_conv
FROM ga4_sessions
WHERE strftime('%Y-%m', date) IN ('2026-03','2026-04','2026-05')
GROUP BY month;

-- Параллельно: CRM Касание в те же месяцы (из Q2 выше)
-- Апрель: 510 контактов, CR=32% — при минимуме paid трафика (595 PMax сессий)
-- Это говорит о том, что апрельские конверсии пришли из другого канала (звонки/соцсети)
-- или произошла задержка обработки лидов (квалифицировали старых)

-- ─────────────────────────────────────────────────────────────
-- Q5. ВОРОНКА ПРИЁМОВ ПО МЕСЯЦАМ (pipeline 10176362)
-- Факт: сколько приёмов фактически состоялось
-- ─────────────────────────────────────────────────────────────
SELECT
    strftime('%Y-%m', created_at)                                         AS month,
    COUNT(*)                                                              AS appt_leads,
    SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)                        AS appt_won,
    ROUND(AVG(NULLIF(price,0)))                                           AS avg_price
FROM crm_leads
WHERE pipeline_id=10176362
GROUP BY month
ORDER BY month;

/*
РЕЗУЛЬТАТ (факт записей и приёмов):
  2025-07     3  won=  2  ← воронка Назначения только запускалась
  2025-08     9  won=  9
  2025-09    18  won= 14
  2025-10   179  won=161  ← запуск: октябрь = первый рабочий месяц воронки
  2025-11   473  won=469
  2025-12   288  won=288
  2026-01   391  won=391
  2026-02   227  won=227
  2026-03   277  won=277
  2026-04   284  won=282  ← совпадает с пиком квалификации в Касании
  2026-05   244  won=243
  2026-06   235  won=210

NB: avg_price в исходных единицах (~670k-1.8M), нужно уточнить валюту/единицы.
Тренд стабилен: 230-470 записей/мес с ноября 2025. Ноябрь аномально высокий —
возможно, накопленные из Касания записи зашли разом. Апрель > мая > июня по CR,
но объём записей похож: 282/243/210 won.
Месячный объём приёмов ограничен мощностью клиники (не трафиком).
*/

-- ─────────────────────────────────────────────────────────────
-- Q6. СВОДНАЯ ТАБЛИЦА: МАРКЕТИНГ vs ОПЕРАЦИОННЫЙ РЕЗУЛЬТАТ
-- ─────────────────────────────────────────────────────────────
/*
СВОДКА ДЛЯ CMO (нов. система, ноябрь 2025 – июнь 2026):

Месяц    Вход   Квал  CR%  | Прием| Paid GA4 sess | CRM site_paid
----------------------------------------------------------------------
2025-11   484    35  7.2%  |  469 |    4883       |   1
2025-12   217    13  6.0%  |  288 |    7715       |   8
2026-01   714    38  5.3%  |  391 |   10553       |  24
2026-02   606    91 15.0%  |  227 |    4482       |  37
2026-03   600    82 13.7%  |  277 |    3914       |  22
2026-04   510   161 31.6%  |  282 |    1033       |  25
2026-05   841   253 30.1%  |  243 |    2740       |  64
2026-06  1363   186 13.6%  |  210 |   10317       | 322

НАБЛЮДЕНИЯ:
1. Апрель: минимум paid трафика + максимум CR → лиды пришли из звонков/соцсетей
2. Май: рост всего одновременно (трафик + CR + приёмы) → лучший месяц
3. Июнь: +62% входа, paid x15, CR упал до 14% — качество формных лидов ниже
4. Корреляция paid трафик → CRM лиды слабая: главный конверсионный инструмент = звонок
*/
