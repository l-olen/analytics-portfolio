-- Воронка: канал → лиды → сделки
-- Фаза 2, Неделя 3-4: JOIN + агрегации + CTE
SELECT
    source,
    COUNT(*)                                   AS leads_total,
    SUM(CASE WHEN status = 'won'  THEN 1 END)  AS won,
    SUM(CASE WHEN status = 'lost' THEN 1 END)  AS lost,
    ROUND(100.0 * SUM(CASE WHEN status = 'won' THEN 1 END) / COUNT(*), 1) AS conv_pct
FROM crm_leads
GROUP BY source
ORDER BY leads_total DESC;

/*
РЕЗУЛЬТАТ: source → leads / won / lost / conv_pct
  call         → наибольший conv% (31.4%), основной канал реальных пациентов
  site_paid    → 510 лидов, utm_medium=cpc в CRM. Но до реального приёма
                 доходят только 16 из 510 (3.1%) — остальные оседают в воронке База.
  site_organic → схожая картина с site_paid по доходимости
  other        → соцсети, мессенджеры, без атрибуции

NB: site_paid < GA4 paid forms (351) не из-за потери UTM, а из-за разной
логики атрибуции: CRM берёт utm из URL напрямую, GA4 — через куки/сессии
(блокируется адблокерами). Дубли в CRM: 15 шт, на картину не влияют.
Подробнее: sql/02_gap_analysis.sql
*/

-- Воронка по pipeline
SELECT
    pipeline_id,
    COUNT(*)                                                           AS leads_total,
    SUM(CASE WHEN status = 'won'  THEN 1 END)                        AS won,
    SUM(CASE WHEN status = 'lost' THEN 1 END)                        AS lost,
    ROUND(100.0 * SUM(CASE WHEN status = 'won' THEN 1 END) / COUNT(*), 1) AS conv_pct
FROM crm_leads
GROUP BY pipeline_id
ORDER BY leads_total DESC;

/*
┌─────────────┬──────────────────────────┬───────────────────────────────────┐
│ pipeline_id │         Название         │            Смысл "won"            │
├─────────────┼──────────────────────────┼───────────────────────────────────┤
│ 10176374    │ База                     │ Первичный пул всех новых лидов    │
├─────────────┼──────────────────────────┼───────────────────────────────────┤
│ 7844402     │ Касание/Квалификация     │ Квалифицированный, готов к записи │
├─────────────┼──────────────────────────┼───────────────────────────────────┤
│ 10176362    │ Назначение/приём         │ Приём состоялся                   │
├─────────────┼──────────────────────────┼───────────────────────────────────┤
│ 10298490    │ Повторные взаимодействия │ Реактивация старых лидов          │
└─────────────┴──────────────────────────┴───────────────────────────────────┘
Итоговая картина структуры:
- База — всё новое входящее, цена приблизительная
- Касание/Квалификация — отдельный поток, возможно холодные или требующие квалификации
- Назначение — факт записи с реальной ценой услуги
- Повторные — реактивация, отдельный поток
*/

--контакты ,у которых лиды в нескольких воронках, чтобы отследить путь лида
SELECT
    contact_id,
    COUNT(DISTINCT pipeline_id)          AS pipelines_count,
    GROUP_CONCAT(DISTINCT pipeline_id)   AS pipelines,
    COUNT(*)                             AS leads_total,
    MAX(CASE WHEN pipeline_id = 10176362
             AND status = 'won' THEN 1 ELSE 0 END) AS had_appointment
FROM crm_leads
WHERE contact_id IS NOT NULL
GROUP BY contact_id
HAVING pipelines_count > 1
ORDER BY pipelines_count DESC, leads_total DESC
LIMIT 20;

--Сколько всего лидов прошли путь по воронке
 SELECT
    COUNT(DISTINCT contact_id) AS unique_contacts,
    SUM(CASE WHEN pipelines_count > 1 THEN 1 END) AS multi_pipeline,
    SUM(CASE WHEN pipelines_count = 1 THEN 1 END) AS single_pipeline
FROM (
    SELECT contact_id, COUNT(DISTINCT pipeline_id) AS pipelines_count
    FROM crm_leads
    WHERE contact_id IS NOT NULL
    GROUP BY contact_id
);

