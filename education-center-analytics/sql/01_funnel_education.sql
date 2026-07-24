-- ============================================================
-- Образовательный центр: воронка и атрибуция
-- База: education.db  |  Лиды: Nov 2023 – Jul 2026
-- ============================================================
-- ATTACH DATABASE 'data/education.db' AS b;  -- при запуске из medical.db
-- Или просто: sqlite3 data/education.db < sql/01_funnel_education.sql

-- ============================================================
-- 0. СПРАВОЧНИК ВОРОНОК И ЭТАПОВ
-- ============================================================
-- Автоматические воронки (где работает bot detection):
--   7599026  Сall center
--   7378970  Отдел Продаж
--   7456518  Дожим
--  10481938  Administration
--  10486794  Архив лиды 01.01.2024 по 31.12.2025
--
-- Ручные воронки (ботов нет, данные вносятся менеджерами):
--   7693206  Воронка Узб
--   7645546  Онлайн воронка
--   8152890  Доп Продажи
--   8254930  Переписки
--   8928070  дтм тест база
--   9587506  Консалтинг
--   9685134  Выставка вузов 2025
--  10034018  Томсон лиды
--
-- Статусы: 142 = Успешно (won), 143 = Закрыто/Потеря (lost)


-- ============================================================
-- 1. ОБЩАЯ ВОРОНКА (без ботов)
-- ============================================================
SELECT
    COUNT(*)                                              AS total_leads,
    SUM(CASE WHEN status = 'won'  THEN 1 ELSE 0 END)     AS won,
    SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END)     AS lost,
    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
    ROUND(100.0 * SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0;


-- ============================================================
-- 2. ВОРОНКА ПО ТИПУ ВОРОНКИ: авто vs ручные
-- ============================================================
SELECT
    CASE
        WHEN pipeline_id IN (7599026,7378970,7456518,10481938,10486794)
            THEN 'automated'
        ELSE 'manual'
    END AS pipeline_type,
    COUNT(*)  AS total,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
GROUP BY pipeline_type;


-- ============================================================
-- 3. ВОРОНКА ПО ИСТОЧНИКУ ЛИДА (тег-классификация)
-- ============================================================
SELECT
    source,
    COUNT(*)  AS total,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
GROUP BY source
ORDER BY total DESC;


-- ============================================================
-- 4. АТРИБУЦИЯ: ВОРОНКА ПО UTM-ИСТОЧНИКУ
-- (только лиды с utm_source, т.е. пришедшие с онлайн-рекламы)
-- ============================================================
SELECT
    utm_source,
    utm_medium,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND utm_source IS NOT NULL
  AND utm_source NOT IN ('UTM Medium:','utm_medium:','test')  -- фильтр мусора
GROUP BY utm_source, utm_medium
ORDER BY leads DESC;


-- ============================================================
-- 5. ТОП КАМПАНИЙ ПО ОБЪЁМУ И CR
-- ============================================================
SELECT
    utm_source,
    utm_campaign,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
  AND utm_campaign IS NOT NULL
  AND utm_source NOT IN ('UTM Medium:','utm_medium:','test')
  AND utm_campaign NOT IN ('UTM Content:','UTM Term:')
GROUP BY utm_source, utm_campaign
HAVING leads >= 30
ORDER BY leads DESC
LIMIT 25;


-- ============================================================
-- 6. ВОРОНКА ПО ПРОДУКТУ
-- ============================================================
SELECT
    produkt,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND produkt IS NOT NULL
GROUP BY produkt
ORDER BY leads DESC
LIMIT 20;


-- ============================================================
-- 7. ВОРОНКА ПО КЛАССУ / КУРСУ
-- ============================================================
SELECT
    klass_kurs   AS grade,
    COUNT(*)     AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND klass_kurs IS NOT NULL
GROUP BY klass_kurs
ORDER BY leads DESC;


-- ============================================================
-- 8. ABC-СЕГМЕНТАЦИЯ: распределение и конверсия
-- ============================================================
SELECT
    abc_category,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN price > 0     THEN 1 ELSE 0 END) AS with_price,
    ROUND(AVG(CASE WHEN price > 0 THEN price END), 0) AS avg_price,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND abc_category IS NOT NULL
GROUP BY abc_category
ORDER BY leads DESC;


-- ============================================================
-- 9. МЕСЯЧНЫЙ ТРЕНД: объём лидов и CR
-- ============================================================
SELECT
    substr(created_date, 1, 7)                           AS month,
    COUNT(*)                                              AS total,
    SUM(CASE WHEN is_bot=1  THEN 1 ELSE 0 END)           AS bots,
    SUM(CASE WHEN is_bot=0  THEN 1 ELSE 0 END)           AS clean,
    SUM(CASE WHEN is_bot=0 AND status='won'  THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN is_bot=0 AND status='won' THEN 1 ELSE 0 END)
               / NULLIF(SUM(CASE WHEN is_bot=0 THEN 1 ELSE 0 END),0), 2) AS cr_pct
FROM crm_leads
GROUP BY month
ORDER BY month;


-- ============================================================
-- 10. АТРИБУЦИЯ: utm_source × продукт — пересечение каналов
-- ============================================================
SELECT
    utm_source,
    produkt,
    COUNT(*)  AS leads,
    SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0
  AND utm_source IS NOT NULL AND utm_source NOT IN ('UTM Medium:','test')
  AND produkt IS NOT NULL
GROUP BY utm_source, produkt
HAVING leads >= 10
ORDER BY utm_source, leads DESC;


-- ============================================================
-- 11. ЯЗЫК ОБУЧЕНИЯ × ИСТОЧНИК — сегментация Узб/Рус аудитории
-- ============================================================
SELECT
    yazyk_obuch  AS language,
    utm_source,
    COUNT(*)     AS leads,
    SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won,
    ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM crm_leads
WHERE is_bot = 0 AND yazyk_obuch IS NOT NULL
GROUP BY yazyk_obuch, utm_source
ORDER BY yazyk_obuch, leads DESC;


-- ============================================================
-- КАНАЛЬНАЯ КЛАССИФИКАЦИЯ (единая логика)
-- ============================================================
-- Правила классификации source (в ETL):
--   site_quiz  = теги: "квиз", "сайт квиз"
--   site_web   = теги: "заказ с сайта", "Сайт", "tilda"  ← Сайт и tilda добавлены
--   call       = теги: "555100400", "входящий", "пропущенный", + доп. тег колл-виджета
--   other      = всё остальное
--
-- Канальная логика на уровне лида:
--   UTM/click-id имеет приоритет над тегом-источником.
--   yclid = Яндекс веб-трафик (и платный и органический).
--   Для разделения paid vs organic Яндекс используй utm_medium='cpc'.
--   gclid передаётся редко — ориентируемся на utm_source/utm_medium.
--   Префиксы кампаний fk_ и km_ — одно агентство, разные периоды структуры.

-- 12. CR ПО КАНАЛУ (по лиду, для ориентира по объёму)
WITH channel_classified AS (
    SELECT *,
        CASE
            WHEN yclid IS NOT NULL
              OR utm_source = 'yandex' OR utm_source = 'yd'    THEN 'yandex_web'
            WHEN utm_source = 'google' AND utm_medium = 'cpc'
              OR gclid IS NOT NULL                              THEN 'paid_google'
            WHEN fbclid IS NOT NULL
              OR utm_source IN ('FB','fb','ig')                 THEN 'paid_social'
            WHEN utm_source = 'telegram'                        THEN 'telegram'
            WHEN utm_source = 'chatgpt.com'                     THEN 'chatgpt_ref'
            WHEN source IN ('site_quiz','site_web')             THEN 'organic_web'
            WHEN source = 'call'                                THEN 'inbound_call'
            ELSE 'other'
        END AS channel
    FROM crm_leads WHERE is_bot = 0
)
SELECT channel,
       COUNT(*) AS leads,
       SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won,
       ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),2) AS cr_pct
FROM channel_classified
GROUP BY channel ORDER BY leads DESC;


-- 13. АТРИБУЦИЯ НА УРОВНЕ КОНТАКТА (с переносом UTM)
-- Для каждого контакта собираем UTM-сигналы ВСЕХ его лидов.
-- Если в любом лиде контакта есть UTM — победа засчитывается этому каналу,
-- даже если сама сделка закрылась как звонок.
-- Приоритет: google > yandex > social > telegram > chatgpt > тег первого лида.
WITH contact_signals AS (
    SELECT contact_id,
           MAX(CASE WHEN utm_source='google' AND utm_medium='cpc'
                     OR gclid IS NOT NULL                       THEN 1 ELSE 0 END) sig_google,
           MAX(CASE WHEN yclid IS NOT NULL
                     OR utm_source IN ('yandex','yd')           THEN 1 ELSE 0 END) sig_yandex,
           MAX(CASE WHEN fbclid IS NOT NULL
                     OR utm_source IN ('FB','fb','ig')          THEN 1 ELSE 0 END) sig_social,
           MAX(CASE WHEN utm_source='telegram'                  THEN 1 ELSE 0 END) sig_telegram,
           MAX(CASE WHEN utm_source='chatgpt.com'               THEN 1 ELSE 0 END) sig_chatgpt,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END)        ever_won
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
),
first_tag AS (
    SELECT contact_id,
           FIRST_VALUE(source) OVER (
               PARTITION BY contact_id ORDER BY created_at ASC, lead_id ASC
           ) AS ft_source
    FROM crm_leads WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT
    CASE
        WHEN cs.sig_google   = 1 THEN 'paid_google'
        WHEN cs.sig_yandex   = 1 THEN 'yandex_web'
        WHEN cs.sig_social   = 1 THEN 'paid_social'
        WHEN cs.sig_telegram = 1 THEN 'telegram'
        WHEN cs.sig_chatgpt  = 1 THEN 'chatgpt_ref'
        ELSE COALESCE(ft.ft_source, 'other')
    END AS attributed_channel,
    COUNT(*)      AS contacts,
    SUM(cs.ever_won) AS won,
    ROUND(100.0*SUM(cs.ever_won)/COUNT(*),2) AS cr_pct
FROM contact_signals cs
LEFT JOIN first_tag ft ON ft.contact_id = cs.contact_id
GROUP BY attributed_channel ORDER BY contacts DESC;


-- 14. ТОП КАМПАНИЙ (атрибуция на уровне контакта)
-- fk_ и km_ префиксы = одно агентство, объединять при анализе.
WITH contact_campaigns AS (
    SELECT contact_id,
           MAX(CASE WHEN utm_source IS NOT NULL
                     AND utm_source NOT IN ('UTM Medium:','test')
                THEN utm_source END) AS best_source,
           MAX(CASE WHEN utm_campaign IS NOT NULL
                     AND utm_campaign NOT IN ('UTM Content:','UTM Term:')
                THEN utm_campaign END) AS best_campaign,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END) AS ever_won
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT best_source, best_campaign,
       COUNT(*) AS contacts,
       SUM(ever_won) AS won,
       ROUND(100.0*SUM(ever_won)/COUNT(*),2) AS cr_pct
FROM contact_campaigns
WHERE best_campaign IS NOT NULL
GROUP BY best_source, best_campaign
HAVING contacts >= 20
ORDER BY contacts DESC LIMIT 25;


-- 15. ТЁМНЫЙ ПУЛЬ: UTM-покрытие выигранных контактов
-- 96.8% выигранных контактов не имеют никаких UTM-меток.
-- Структурные причины (не ошибки трекинга):
--   Архив (29k лидов, Nov'23–Dec'25) — UTM ещё не настраивался
--   Доп продажи — апсейл текущих студентов, UTM не нужен
--   дтм тест база / Консалтинг / Выставка — ручные каналы
--   Administration — дочерние лиды, UTM теряется при "Копировании сделок"
WITH contact_utm AS (
    SELECT contact_id,
           MAX(CASE WHEN utm_source IS NOT NULL
                     AND utm_source NOT IN ('UTM Medium:','test')
                THEN 1 ELSE 0 END) AS has_any_utm,
           MAX(CASE WHEN yclid IS NOT NULL OR gclid IS NOT NULL OR fbclid IS NOT NULL
                THEN 1 ELSE 0 END) AS has_click_id,
           MAX(CASE WHEN status='won' THEN 1 ELSE 0 END) AS ever_won
    FROM crm_leads WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
)
SELECT
    COUNT(*)                                   AS total_contacts,
    SUM(ever_won)                              AS won_contacts,
    SUM((has_any_utm + has_click_id > 0) * ever_won) AS won_with_utm,
    SUM((has_any_utm + has_click_id = 0) * ever_won) AS won_dark,
    ROUND(100.0*SUM((has_any_utm+has_click_id>0)*ever_won)/NULLIF(SUM(ever_won),0),1)
        AS pct_attributed,
    ROUND(100.0*SUM((has_any_utm+has_click_id=0)*ever_won)/NULLIF(SUM(ever_won),0),1)
        AS pct_dark
FROM contact_utm;


-- ============================================================
-- ИТОГОВАЯ ИСТОРИЯ (для кейса)
-- ============================================================
-- База: ~51,900 лидов (Nov 2023 – Jul 2026), ~1,248 ботов (2.4%)
-- Чистых контактов: ~47,100 уникальных, 2,802 выиграно (CR 6.6%)
--
-- ✓ CR по каналу (first-touch с переносом UTM):
--     inbound_call 13% > telegram 8.2% > yandex_web 3.4% > paid_social 2.7%
--     > paid_google 2.2% > site_web 1.4% > chatgpt_ref 1.1%
-- ✓ CR по продукту: право 29% / история 29% / математика 21% / английский 19%
-- ✓ CR по классу: 11 класс основная аудитория (5,384 лидов)
-- ✓ Тренд объёма и конверсий по месяцам (Q9)
-- ✓ ABC-сегментация (A=3k, B=2.5k, C=1.8k лидов)
--
-- КЛЮЧЕВОЙ ИНСАЙТ 1 — тёмный пуль атрибуции:
--   96.8% выигранных контактов не имеют UTM-разметки.
--   Структурные причины:
--     Архив (1389 wins) — исторические данные до настройки UTM-трекинга
--     дтм тест база (398) + Консалтинг (111) — ручные каналы, UTM не нужен
--     Доп продажи (259) — апсейл текущих студентов
--     Call center (472) — прямые звонки без онлайн-касания
--     Administration (287) — большинство лидов созданы напрямую, не через
--       онлайн-форму; "Копирование сделок" копирует UTM корректно, но только
--       когда исходный лид пришёл с сайта (таких ~10 из 784 в Administration).
--   Что поддаётся фиксу: передача gclid/fbclid через скрытые поля квиза,
--   систематический мёрдж контактов при звонке по онлайн-заявке.
--
-- КЛЮЧЕВОЙ ИНСАЙТ 2 — разрыв атрибуции веб → звонок:
--   2,622 из 2,625 Google-контактов: UTM на веб-лиде, конверсия на звонке.
--   Без переноса UTM эти контакты выглядят как "other" с CR 9%.
--   После переноса: paid_google CR = 2.2%, это реальный платный CR.
--
-- КЛЮЧЕВОЙ ИНСАЙТ 3 — yclid = весь Яндекс (paid + organic):
--   yclid проставляется на всём яндекс-трафике, не только платном.
--   Для разделения: utm_medium='cpc' → paid (833 лидов, CR 2.4%)
--                   без cpc → organic/direct Яндекс (1,216 лидов, CR 2.8%)
--   CR почти одинаковый — органика Яндекса не хуже платной.
--
-- РЕКОМЕНДАЦИИ:
--   1. Передавать gclid/fbclid в скрытые поля квиза/формы
--   2. Настроить автоматический мёрдж контактов по номеру телефона
--   3. Настроить передачу UTM в Administration при "Копировании сделок"
--   4. gclientid (GA4 Client ID) есть у 2,021 лидов → потенциальный
--      мост к GA4 данным через BigQuery export
--
-- КЛЮЧЕВОЙ ИНСАЙТ 4 — Call center до 2026 = пустота, история в Архиве:
--   До января 2026 все входящие лиды шли в "Архив лиды 01.01.2024 по 31.12.2025"
--   (29,365 лидов, дек 2023 – дек 2025). Call center запущен как основная
--   воронка с янв 2026. Тренд внутри CC — только данные с янв 2026.
--
-- КЛЮЧЕВОЙ ИНСАЙТ 5 — Instagram и Telegram конвертируют через чат, не звонок:
--   Instagram: 2,457 лидов (2026), 88.7% без тега звонка (Входящий/Исходящий).
--   Но когда звонок делается → CR 30-63% (vs 6.7% в среднем).
--   80 won с пустым тегом = конверсия через DM без звонка.
--   Telegram: 432 лидов, CR 26.9%. 84.7% без тега звонка.
--   100 won с пустым тегом = конвертируются через Telegram-чат.
--   Вывод: теги "Входящий/Исходящий" не отражают все касания.
--   Нельзя считать "нет тега = нет работы с лидом".
--
-- Что потребует дополнительного ETL:
--   ✗ Движение по этапам (время в каждом этапе, где отваливаются)
--   → etl_events_education.py → crm_lead_events
--     ~125k-250k событий, ~15 мин загрузки

-- ============================================================
-- Q16: CALL CENTER 2026 — КАНАЛЫ × ДЕЙСТВИЕ ОПЕРАТОРА × СТАТУС
-- Источник канала: crm_source (поле 534651, ручная отметка оператора)
-- Тег действия: Входящий/Исходящий/Клиент не ответил/Пропущенный
-- ============================================================

WITH cc AS (
    SELECT *,
        CASE
            WHEN crm_source IN ('инстаграм')              THEN 'Instagram'
            WHEN crm_source IN ('телеграм','телеграм(и)') THEN 'Telegram'
            WHEN crm_source = 'фейсбук'                   THEN 'Facebook'
            WHEN crm_source = 'сарафанное радио'           THEN 'Сарафанка'
            WHEN crm_source = 'наш ученик'                 THEN 'Рекомендация'
            WHEN crm_source = 'дтм тест'                   THEN 'ДТМ тест'
            WHEN crm_source = 'сайт'
                 OR source IN ('site_quiz','site_web')     THEN 'Сайт/Квиз'
            WHEN utm_source = 'google' AND utm_medium='cpc' THEN 'Google Ads'
            WHEN yclid IS NOT NULL OR utm_source IN ('yandex','yd') THEN 'Яндекс'
            WHEN utm_source = 'chatgpt.com'                THEN 'ChatGPT'
            ELSE 'Не определён'
        END ch,
        CASE
            WHEN tags LIKE '%Входящий%'    THEN 'Входящий звонок'
            WHEN tags LIKE '%Исходящий%'   THEN 'Исходящий звонок'
            WHEN tags LIKE '%Клиент не%'   THEN 'Недозвон'
            WHEN tags LIKE '%Пропущенный%' THEN 'Пропущенный'
            WHEN tags IS NULL OR tags = '' THEN 'Нет действия'
            ELSE 'Другое'
        END operator_action
    FROM crm_leads
    WHERE pipeline_id = 7599026
      AND is_bot = 0
      AND created_at >= '2026-01-01'
)
SELECT ch,
       operator_action,
       COUNT(*) n,
       SUM(CASE WHEN status='won'         THEN 1 ELSE 0 END) won,
       SUM(CASE WHEN status='lost'        THEN 1 ELSE 0 END) lost,
       SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) active,
       ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) cr_pct
FROM cc
GROUP BY ch, operator_action
ORDER BY ch, n DESC;

-- ============================================================
-- Q17: CALL CENTER 2026 — ИТОГ ПО КАНАЛУ
-- % "Нет действия" — лиды без тега звонка (конверсия может быть через чат)
-- ============================================================

WITH cc AS (
    SELECT *,
        CASE
            WHEN crm_source IN ('инстаграм')              THEN 'Instagram'
            WHEN crm_source IN ('телеграм','телеграм(и)') THEN 'Telegram'
            WHEN crm_source = 'фейсбук'                   THEN 'Facebook'
            WHEN crm_source = 'сарафанное радио'           THEN 'Сарафанка'
            WHEN crm_source = 'наш ученик'                 THEN 'Рекомендация'
            WHEN crm_source = 'дтм тест'                   THEN 'ДТМ тест'
            WHEN crm_source = 'сайт'
                 OR source IN ('site_quiz','site_web')     THEN 'Сайт/Квиз'
            WHEN utm_source = 'google' AND utm_medium='cpc' THEN 'Google Ads'
            WHEN yclid IS NOT NULL OR utm_source IN ('yandex','yd') THEN 'Яндекс'
            WHEN utm_source = 'chatgpt.com'                THEN 'ChatGPT'
            ELSE 'Не определён'
        END ch
    FROM crm_leads
    WHERE pipeline_id = 7599026
      AND is_bot = 0
      AND created_at >= '2026-01-01'
)
SELECT ch,
       COUNT(*) total_leads,
       SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) won,
       ROUND(100.0*SUM(CASE WHEN status='won' THEN 1 ELSE 0 END)/COUNT(*),1) cr_pct,
       SUM(CASE WHEN tags IS NULL OR tags='' THEN 1 ELSE 0 END) no_phone_tag,
       ROUND(100.0*SUM(CASE WHEN tags IS NULL OR tags='' THEN 1 ELSE 0 END)/COUNT(*),1) pct_no_tag,
       SUM(CASE WHEN tags LIKE '%Клиент не%' THEN 1 ELSE 0 END) no_answer
FROM cc
GROUP BY ch
ORDER BY total_leads DESC;

-- ============================================================
-- Q18: ТРЁХСЕГМЕНТНАЯ КЛАССИФИКАЦИЯ КОНТАКТОВ (все воронки, 2026)
--
-- Сегмент 1 — ВЕБ: контакт имеет хотя бы один лид с тегом "Сайт" / "Сайт Квиз"
--   UTM-атрибуция внутри: Google Ads / Яндекс paid / Яндекс орг / Органика
--   Ограничение: Яндекс paid ≠ organic не разделяются без utm_medium='cpc'
--
-- Сегмент 2 — ЗВОНОК (чистый): тег "Входящий" / "Пропущенный",
--   НО у этого контакта нет ни одного лида с тегом "Сайт"
--
-- Сегмент 3 — СОЦСЕТИ/РУЧНЫЕ: всё остальное.
--   crm_source (поле 534651, ручная разметка оператора) — лучший доступный сигнал.
--   Кавалитация: оператор может проставить "сарафанка" на лид с UTM — это шум,
--   но в эту группу попадают только лиды без Сайт-тегов и без UTM, т.е. точно не веб.
-- ============================================================

WITH cs AS (
    SELECT
        contact_id,
        MAX(CASE WHEN tags LIKE '%Сайт%' THEN 1 ELSE 0 END)                          has_web,
        MAX(CASE WHEN (tags LIKE '%Входящий%' OR tags LIKE '%Пропущенный%')
                  AND tags NOT LIKE '%Сайт%' THEN 1 ELSE 0 END)                      has_pure_call,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND utm_source='google' AND utm_medium='cpc' THEN 1 ELSE 0 END)    web_google,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                  AND utm_medium='cpc' THEN 1 ELSE 0 END)                            web_yd_paid,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                  THEN 1 ELSE 0 END)                                                 web_yd_any,
        MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)                        won,
        MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                        lost,
        MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                        active,
        MAX(crm_source)                                                               crm_source_any,
        MIN(created_at)                                                               first_lead
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2026-01-01'      -- только новые контакты 2026
),
classified AS (
    SELECT *,
        CASE
            WHEN has_web=1 AND web_google=1  THEN 'Веб → Google Ads'
            WHEN has_web=1 AND web_yd_paid=1 THEN 'Веб → Яндекс Paid'
            WHEN has_web=1 AND web_yd_any=1  THEN 'Веб → Яндекс (орг/неизв)'
            WHEN has_web=1                   THEN 'Веб → Органика/Неразм'
            WHEN has_pure_call=1             THEN 'Звонок (чистый)'
            WHEN crm_source_any IN ('инстаграм')               THEN 'Соцсети → Instagram'
            WHEN crm_source_any IN ('телеграм','телеграм(и)')  THEN 'Соцсети → Telegram'
            WHEN crm_source_any = 'фейсбук'                    THEN 'Соцсети → Facebook'
            WHEN crm_source_any = 'сарафанное радио'           THEN 'Реф → Сарафанка'
            WHEN crm_source_any IN ('наш ученик')              THEN 'Реф → Рекомендация'
            WHEN crm_source_any = 'дтм тест'                   THEN 'ДТМ тест'
            ELSE 'Manual/Не определён'
        END segment
    FROM cs
)
SELECT
    segment,
    COUNT(*)                                                                 contacts,
    SUM(won)                                                                 won,
    SUM(lost)                                                                lost,
    SUM(active)                                                              active,
    ROUND(100.0*SUM(won)/COUNT(*),1)                                         cr_pct,
    ROUND(100.0*SUM(lost)/COUNT(*),1)                                        lost_pct
FROM classified
GROUP BY segment
ORDER BY contacts DESC;

-- ============================================================
-- Q19: ВЕБ — КВИЗ vs КОНТАКТНАЯ ФОРМА × UTM-КАНАЛ
-- Контакты с тегом "Сайт Квиз" vs "Сайт" (без квиза) × платный/орг
-- ============================================================

WITH cw AS (
    SELECT
        contact_id,
        MAX(CASE WHEN tags LIKE '%Сайт Квиз%'                             THEN 1 ELSE 0 END) is_quiz,
        MAX(CASE WHEN tags LIKE '%Сайт%' AND tags NOT LIKE '%Сайт Квиз%' THEN 1 ELSE 0 END) is_form,
        MAX(CASE WHEN utm_source='google' AND utm_medium='cpc'            THEN 1 ELSE 0 END) g,
        MAX(CASE WHEN (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                  AND utm_medium='cpc'                                     THEN 1 ELSE 0 END) yd_paid,
        MAX(CASE WHEN yclid IS NOT NULL OR utm_source IN ('yandex','yd') THEN 1 ELSE 0 END) yd_any,
        MAX(CASE WHEN status='won'  THEN 1 ELSE 0 END) won,
        MAX(CASE WHEN status='lost' THEN 1 ELSE 0 END) lost
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL AND tags LIKE '%Сайт%'
    GROUP BY contact_id
)
SELECT
    CASE
        WHEN is_form=1 AND is_quiz=0 AND g=1      THEN 'Форма → Google Ads'
        WHEN is_form=1 AND is_quiz=0 AND yd_paid=1 THEN 'Форма → Яндекс Paid'
        WHEN is_form=1 AND is_quiz=0 AND yd_any=1 THEN 'Форма → Яндекс (орг)'
        WHEN is_form=1 AND is_quiz=0               THEN 'Форма → Органика/Неразм'
        WHEN is_quiz=1 AND is_form=0 AND g=1      THEN 'Квиз → Google Ads'
        WHEN is_quiz=1 AND is_form=0 AND yd_paid=1 THEN 'Квиз → Яндекс Paid'
        WHEN is_quiz=1 AND is_form=0 AND yd_any=1 THEN 'Квиз → Яндекс (орг)'
        WHEN is_quiz=1 AND is_form=0               THEN 'Квиз → Органика/Неразм'
        ELSE 'Форма + Квиз (оба тега)'
    END sub_channel,
    COUNT(*)                                       contacts,
    SUM(won)                                       won,
    SUM(lost)                                      lost,
    ROUND(100.0*SUM(won)/COUNT(*),1)               cr_pct
FROM cw
GROUP BY sub_channel
ORDER BY contacts DESC;

-- ============================================================
-- Q20–Q22: 12-МЕСЯЧНЫЙ АНАЛИЗ (июл 2025 – июн 2026)
-- Источник: ВСЕ воронки (Архив + CC + прочие)
-- Контакт включается по дате первого лида в периоде
--
-- Архив (10486794): дек 2023 – дек 2025, crm_source заполнен на 78%
-- Call center (7599026): с янв 2026, crm_source заполнен на ~60%
-- Классификация каналов единая: теги → UTM → crm_source
-- ============================================================

-- Общий CTE контактов — используется во всех трёх запросах ниже
-- ATTACH DATABASE 'data/education_ads.db' AS ads;   -- нужен для Q22

-- ============================================================
-- Q20: ВОРОНКА ПО КАНАЛАМ — 12 МЕС
-- ============================================================

WITH all_contacts AS (
    SELECT contact_id,
        MIN(created_at)                                                      first_lead,
        strftime('%Y-%m', MIN(created_at))                                   first_month,
        MAX(CASE WHEN status='won'         THEN 1 ELSE 0 END)                ever_won,
        MAX(CASE WHEN status='lost'        THEN 1 ELSE 0 END)                ever_lost,
        MAX(CASE WHEN status='in_progress' THEN 1 ELSE 0 END)                ever_active,
        MAX(CASE WHEN tags LIKE '%Сайт%'   THEN 1 ELSE 0 END)                has_web,
        MAX(CASE WHEN tags LIKE '%Сайт%' AND utm_source='google'
                  AND utm_medium='cpc'                         THEN 1 ELSE 0 END) web_google,
        MAX(CASE WHEN tags LIKE '%Сайт%'
                  AND (yclid IS NOT NULL OR utm_source IN ('yandex','yd'))
                                                               THEN 1 ELSE 0 END) web_yd,
        MAX(CASE WHEN (tags LIKE '%Входящий%' OR tags LIKE '%Пропущенный%')
                  AND tags NOT LIKE '%Сайт%'                   THEN 1 ELSE 0 END) has_call,
        MAX(crm_source)                                                      crm_src
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-07-01'
       AND MIN(created_at) <  '2026-07-01'
),
classified AS (
    SELECT *,
        CASE
            WHEN has_web=1 AND web_google=1   THEN 'Google Ads (веб)'
            WHEN has_web=1 AND web_yd=1       THEN 'Яндекс (веб)'
            WHEN has_web=1                    THEN 'Органика / неразм (веб)'
            WHEN has_call=1                   THEN 'Входящие звонки'
            WHEN crm_src IN ('инстаграм')     THEN 'Instagram'
            WHEN crm_src IN ('телеграм','телеграм(и)') THEN 'Telegram'
            WHEN crm_src = 'фейсбук'          THEN 'Facebook'
            WHEN crm_src = 'сарафанное радио' THEN 'Сарафанное радио'
            WHEN crm_src IN ('наш ученик')    THEN 'Рекомендация'
            WHEN crm_src = 'наружная реклама' THEN 'Наружная реклама'
            WHEN crm_src IN ('дтм тест','рассылка дтм') THEN 'ДТМ тест'
            ELSE 'Не определён'
        END channel
    FROM all_contacts
)
SELECT channel,
       COUNT(*)                                    contacts,
       SUM(ever_won)                               won,
       ROUND(100.0*SUM(ever_won)/COUNT(*),1)       cr_pct,
       SUM(ever_lost)                              lost,
       SUM(ever_active)                            active
FROM classified
GROUP BY channel
ORDER BY contacts DESC;

-- ============================================================
-- Q21: ТРЕНД ПО МЕСЯЦАМ — 12 МЕС
-- Контакты + CR + Google Ads расход + Google-лиды из CRM
-- Примечание: Google Ads требует ATTACH ads БД
-- ============================================================

WITH all_contacts AS (
    SELECT contact_id,
        strftime('%Y-%m', MIN(created_at)) first_month,
        MAX(CASE WHEN status='won' THEN 1 ELSE 0 END) ever_won
    FROM crm_leads
    WHERE is_bot=0 AND contact_id IS NOT NULL
    GROUP BY contact_id
    HAVING MIN(created_at) >= '2025-07-01'
       AND MIN(created_at) <  '2026-07-01'
),
monthly_crm AS (
    SELECT first_month m, COUNT(*) contacts, SUM(ever_won) won
    FROM all_contacts GROUP BY first_month
),
monthly_ads AS (
    SELECT strftime('%Y-%m', date) m,
           ROUND(SUM(cost_micros)/1e6,0) spend
    FROM ads.ads_campaigns
    WHERE date >= '2025-07-01' AND date < '2026-07-01'
    GROUP BY m
),
monthly_gleads AS (
    SELECT strftime('%Y-%m', created_at) m, COUNT(*) gleads
    FROM crm_leads
    WHERE is_bot=0 AND created_at >= '2025-07-01' AND created_at < '2026-07-01'
      AND utm_source='google' AND utm_medium='cpc'
    GROUP BY m
)
SELECT c.m,
       c.contacts,
       c.won,
       ROUND(100.0*c.won/c.contacts,1)             cr_pct,
       COALESCE(a.spend,0)                         ga_spend_usd,
       COALESCE(g.gleads,0)                        google_crm_leads,
       CASE WHEN COALESCE(g.gleads,0)>0
            THEN ROUND(COALESCE(a.spend,0)/g.gleads,1) END cpl_usd
FROM monthly_crm c
LEFT JOIN monthly_ads  a ON a.m=c.m
LEFT JOIN monthly_gleads g ON g.m=c.m
ORDER BY c.m;

-- ============================================================
-- Q22: GOOGLE ADS — РАСХОД × CRM ЛИДЫ × CPL (12 МЕС)
-- Матч по campaign_id, зашитому в utm_campaign ('|cid|12345')
-- Кампании без |cid| (напр. fk_sert_pmax) в join не попадут
-- ============================================================

WITH crm_by_cid AS (
    SELECT
        CAST(SUBSTR(utm_campaign, INSTR(utm_campaign,'|cid|')+5) AS INTEGER) cid,
        COUNT(*) leads,
        SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) won
    FROM crm_leads
    WHERE is_bot=0 AND created_at >= '2025-07-01' AND created_at < '2026-07-01'
      AND utm_source='google' AND utm_campaign LIKE '%|cid|%'
    GROUP BY cid
),
ads_agg AS (
    SELECT campaign_id, campaign_name,
           ROUND(SUM(cost_micros)/1e6,1) spend,
           SUM(clicks) clicks,
           SUM(conversions) ga_conv
    FROM ads.ads_campaigns
    WHERE date >= '2025-07-01' AND date < '2026-07-01'
    GROUP BY campaign_id, campaign_name
)
SELECT a.campaign_name,
       a.spend                                     spend_usd,
       a.clicks,
       a.ga_conv                                   ga_conversions,
       COALESCE(c.leads,0)                         crm_leads,
       COALESCE(c.won,0)                           won,
       CASE WHEN COALESCE(c.leads,0)>0
            THEN ROUND(a.spend/c.leads,1) END      cpl_usd,
       CASE WHEN COALESCE(c.won,0)>0
            THEN ROUND(a.spend/c.won,0)  END       cpa_usd
FROM ads_agg a
LEFT JOIN crm_by_cid c ON c.cid=a.campaign_id
WHERE a.spend > 1
ORDER BY a.spend DESC;
