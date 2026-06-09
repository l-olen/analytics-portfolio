# Case A: A/B Test Design — Landing Page Redesign

## Context
The marketing team plans to redesign the main product landing page:
- Replace hero section copy
- Restructure feature comparison block
- Move primary CTA above the fold

Goal: increase MQL conversion rate.

**Note on test design:** This is a holistic test of the redesign as a unit -- not a test of individual elements. The result will tell us whether the redesign package works, not which element drove it. This is the correct approach for a low-traffic B2B environment where sequential single-element tests would take months and introduce unacceptable seasonality risk. If the variant wins, follow-up tests on individual elements are recommended to optimize further.

---

## 1. Pre-Launch: Data and Instrumentation

### Baseline metrics (minimum 4 weeks of stable data)
- Landing page sessions per week (by source/medium)
- Visitor → Lead conversion rate
- Visitor → MQL conversion rate (primary)
- CTA click rate (current position)
- Form start rate, form completion rate, form error rate
- Bounce rate, exit rate, scroll depth, avg session duration

### Event tracking required (GA4)

| Event | Parameters |
|-------|-----------|
| `page_view` | page_path |
| `variant_assignment` | experiment_id, variant (control/treatment) |
| `scroll_depth` | milestone: 25/50/75/100% |
| `cta_click` | position: above_fold / below_fold |
| `feature_comparison_interaction` | action: view / expand |
| `form_start` | form_id |
| `form_submit` | form_id |
| `form_error` | error_type |
| `lead_created` | source, product |
| `mql_created` | source, product |

**Per user/session:** experiment_id, variant, timestamp, source/medium, device, geography -- set as User Property or Session-scoped custom dimension in GA4 (not as page_view parameters, to avoid polluting standard reports).

**Critical for B2B:** MQL must be tracked at CRM level, not just form submission. When a lead is marked MQL in CRM, fire the event back to GA4 via Measurement Protocol or webhook. Form submit and MQL qualification often happen in different sessions.

### Randomization and contamination protection
- Assignment method: cookie-based with TTL >= test duration; user-ID based for authenticated users
- Each user is assigned once at first page visit and stays in the same variant throughout the test
- No cross-contamination: users should not see both variants
- QA before launch: verify 50/50 split, no FOUC (visual flicker), all events firing in both variants

---

## 2. Success Metrics, Sample Size, Duration

### Primary metric
**Visitor → MQL conversion rate** (CRM-qualified leads / unique page visitors)

### Secondary metrics
- CTA click-through rate
- Form start rate
- Form completion rate
- Visitor → lead rate (before MQL qualification)

### Guardrail metrics (must not worsen)

| Guardrail | Why |
|-----------|-----|
| MQL → SAL conversion rate | More MQLs is worthless if quality drops |
| Page load time (Core Web Vitals) | Redesign must not slow the page |
| Mobile conversion rate | CTA repositioning affects mobile UX differently |
| Bounce rate / exit rate | Should not increase significantly |
| Form error rate | New layout must not break form UX |
| Cost per MQL (paid traffic) | Revenue efficiency must be maintained |

### Sample size
Calculated using a two-proportion z-test with p0 from the 4-week baseline MQL conversion rate, MDE of 15% relative lift (minimum business-meaningful improvement), alpha = 0.05 two-tailed, and 80% power. For example: if baseline MQL rate is 3.0%, the detectable minimum is 3.45%. Required sample size is calculated per variant; total = 2n. The 4-week baseline window is mandatory -- without a stable p0 the sample size estimate is unreliable.

**Why not optimize for CTR alone:** high CTA click-through rate without MQL quality is not success. A variant could increase clicks by attracting lower-intent visitors who abandon before form completion or fail MQL qualification. The primary metric must remain downstream of the click.

### Test duration
- Minimum: 2 full business weeks (B2B traffic has Mon-Fri pattern)
- Recommended: 3-4 weeks (captures novelty effect decay + weekly cycles)
- Maximum: 6 weeks (beyond this, seasonality contaminates results)
- Duration = whichever is longer: sample size requirement or minimum weeks

### MQL lag and evaluation metric
In B2B, MQL qualification may occur days or weeks after the initial visit. Before launch, define explicitly which metric the experiment is evaluated on: form submission, lead creation, or CRM-qualified MQL. These three can diverge significantly. The recommended primary metric is CRM-qualified MQL, but the observation window must be long enough to capture delayed conversions. Recommended: attribute MQL to the experiment if qualification occurs within 30 days of the variant_assignment event. Evaluate final results only after the attribution window closes for the last cohort of visitors.

---

## 3. Analysis Framework

### Step 1: Validate the experiment
Before analyzing results, test for **Sample Ratio Mismatch (SRM)** -- verify that the actual traffic split matches the planned 50/50 ratio using a chi-square test. A significant imbalance indicates a randomization or tracking problem and invalidates the results regardless of the primary metric outcome. Also verify comparable group composition (source/medium, device, geography) and no tracking gaps.

### Step 2: Primary metric analysis
For each variant calculate:
- MQL Conversion Rate
- Absolute lift
- Relative lift
- 95% Confidence Interval
- Statistical significance (p-value)

### Step 3: Funnel analysis
Identify where behavioral change occurred:
`Sessions → CTA click → Form start → Form submit → Lead → MQL`

Pinpoint the stage with the largest delta between control and treatment.

### Step 4: Novelty effect check
Plot the daily conversion trend for both variants. Use Week 2+ as the primary analysis window only if Week 1 shows a clear spike followed by decay back toward control levels -- that pattern indicates novelty effect. If the trend is stable from Day 1, use the full test period.

### Step 5: Segment analysis

| Segment | Why it matters |
|---------|---------------|
| Traffic source (organic / paid / direct) | Different intent levels |
| Device (desktop vs mobile) | CTA repositioning affects mobile UX differently |
| New vs returning visitors | Novelty effect smaller for returning users |
| Region (EU / LatAm / US) | Copy changes may resonate differently across markets |
| Campaign type (brand vs non-brand) | Different funnel stages, different conversion expectations |

For segments where the variant underperforms: assess whether the segment is strategically important and evaluate the trade-off between overall gains and segment-specific losses. A small underperforming segment in an otherwise strong result may not block shipping, but a key acquisition segment (e.g. organic traffic or a major region) warrants investigation before proceeding.

### Step 6: Stopping rules
No peeking and stopping early without pre-defined rules -- this inflates the false positive rate.
- **Early stop for harm:** if a guardrail metric degrades beyond its predefined threshold at any point → stop immediately
- **Early stop for success:** only if interim checks follow pre-defined rules designed to control error rates
- **Scheduled interim checks:** maximum 2 looks (at 50% and 75% of planned sample) with statistical correction applied to maintain overall alpha at 0.05

### Step 7: Decision

**Ship rule:** ship only if (1) primary metric shows statistically significant improvement, AND (2) all guardrail metrics remain within predefined acceptable thresholds. Both conditions must be true simultaneously -- a significant lift that breaks a guardrail is not a ship.

| Result | Decision |
|--------|----------|
| Primary metric significant, guardrails all within thresholds, consistent across segments | Ship |
| Directional improvement, not significant | Extend test or iterate design |
| Significant lift but guardrail broken (e.g. MQL→SAL drops, load time increases) | Do not ship -- investigate quality issue |
| Effect concentrated in one segment only | Do not ship globally -- iterate for that segment |
| No improvement or degradation | Abandon variant; analyze funnel drop-off to reframe hypothesis before next test |

---

## Key Assumptions and Limitations
1. Sufficient weekly traffic to reach sample size in 3-4 weeks
2. GA4 → CRM integration must be in place before launch
3. Holistic test -- cannot isolate individual element effects; follow-up tests needed if variant wins
4. B2B consideration cycle may span multiple sessions; user-level assignment preferred
5. MQL attribution window (30 days) must be defined and enforced before launch
6. Null result plan: analyze funnel drop-off data to reframe hypothesis before next iteration

---
---

# Кейс A: Дизайн A/B теста — Редизайн лендинга

## Контекст
Маркетинговая команда планирует редизайн основного продуктового лендинга:
- Замена текста в hero-секции
- Реструктуризация блока сравнения функциональности
- Перенос основного CTA выше первого экрана

Цель: увеличение конверсии в MQL.

**Важно о дизайне теста:** Это целостный тест редизайна как единого пакета изменений -- не тест отдельных элементов. Результат покажет, работает ли редизайн в целом, но не выявит, какой элемент обеспечил эффект. Для B2B-среды с невысоким трафиком это правильный подход: последовательное тестирование каждого элемента заняло бы месяцы и внесло бы сезонные искажения. Если вариант побеждает -- рекомендуются follow-up тесты по отдельным элементам.

---

## 1. Подготовка: данные и инструментация

### Базовые метрики (минимум 4 недели стабильных данных)
- Сессии на лендинге в неделю (по источнику/каналу)
- Конверсия посетитель → лид
- Конверсия посетитель → MQL (основная)
- CTR основного CTA (текущее положение)
- Доля начатых форм, завершённых форм, ошибок форм
- Показатель отказов, exit rate, глубина прокрутки, среднее время на странице

### Необходимые события в GA4

| Событие | Параметры |
|---------|-----------|
| `page_view` | page_path |
| `variant_assignment` | experiment_id, variant (control/treatment) |
| `scroll_depth` | milestone: 25/50/75/100% |
| `cta_click` | position: above_fold / below_fold |
| `feature_comparison_interaction` | action: view / expand |
| `form_start` | form_id |
| `form_submit` | form_id |
| `form_error` | error_type |
| `lead_created` | source, product |
| `mql_created` | source, product |

**На уровне пользователя/сессии:** experiment_id, variant, timestamp, source/medium, устройство, география -- передавать как User Property или Session-scoped custom dimension (не как параметры page_view, чтобы не засорять стандартные отчёты GA4).

**Критически важно для B2B:** MQL отслеживается на уровне CRM, а не только по отправке формы. Когда лид получает статус MQL в CRM -- нужно отправить событие обратно в GA4 через Measurement Protocol или webhook. Отправка формы и присвоение статуса MQL часто происходят в разных сессиях.

### Рандомизация и защита от загрязнения выборки
- Метод назначения: cookie-based с TTL >= длительность теста; user-ID для авторизованных пользователей
- Каждый пользователь назначается в вариант один раз при первом визите и остаётся в нём до конца теста
- Исключить перекрёстное загрязнение: пользователи не должны видеть оба варианта
- QA-чеклист перед запуском: проверить корректность сплита 50/50, отсутствие FOUC (мигание между вариантами), корректность срабатывания событий в обоих вариантах

---

## 2. Метрики успеха, размер выборки, длительность

### Основная метрика
**Конверсия посетитель → MQL** (лиды, квалифицированные в CRM / уникальные посетители страницы)

### Вторичные метрики
- CTR кнопки CTA
- Доля начатых форм
- Доля завершённых форм
- Конверсия посетитель → лид (до MQL-квалификации)

### Guardrail-метрики (не должны ухудшаться)

| Метрика | Почему важна |
|---------|-------------|
| Конверсия MQL → SAL | Больше MQL бессмысленно, если падает качество лидов |
| Скорость загрузки страницы (Core Web Vitals) | Редизайн не должен замедлять страницу |
| Конверсия на мобильных | Перенос CTA по-разному влияет на мобильный UX |
| Показатель отказов / exit rate | Не должен значительно расти |
| Доля ошибок формы | Новый макет не должен ломать UX формы |
| Cost per MQL (для платного трафика) | Эффективность расходов должна сохраняться |

### Размер выборки
Рассчитывается по двухвыборочному z-тесту для пропорций: p0 из 4-недельного baseline, MDE = 15% относительный прирост (минимально значимый для бизнеса), alpha = 0.05 двусторонний, мощность = 80%. Пример: если базовая конверсия в MQL 3,0% -- минимально обнаруживаемый эффект 3,45%. Расчёт на вариант, итоговая выборка = 2n. 4-недельное baseline-окно обязательно -- без стабильного p0 оценка размера выборки ненадёжна.

**Почему не оптимизировать по CTR:** высокий CTR кнопки без качества MQL -- не успех. Вариант может увеличить клики, привлекая менее заинтересованных посетителей, которые не завершат форму или не пройдут MQL-квалификацию. Основная метрика должна находиться ниже по воронке, чем клик.

### Длительность теста
- Минимум: 2 полные рабочие недели (B2B трафик имеет паттерн пн-пт)
- Рекомендуется: 3-4 недели (охватывает затухание novelty effect + недельные циклы)
- Максимум: 6 недель (далее сезонность искажает результаты)
- Длительность = максимум из двух: достижение размера выборки или минимум недель

### Задержка MQL и выбор метрики оценки
В B2B MQL-квалификация может происходить спустя дни или недели после первого визита. До запуска необходимо явно определить, по какой метрике оценивается эксперимент: отправка формы, создание лида или CRM-квалифицированный MQL. Эти три показателя могут существенно расходиться. Рекомендуемая основная метрика -- CRM-квалифицированный MQL, но окно наблюдения должно быть достаточным для захвата отложенных конверсий. Рекомендуется: атрибутировать MQL к эксперименту, если квалификация произошла в течение 30 дней с момента события variant_assignment. Финальные результаты оцениваются только после закрытия окна атрибуции для последней когорты посетителей.

---

## 3. Фреймворк анализа

### Шаг 1: Валидация эксперимента
До анализа результатов -- проверить на **Sample Ratio Mismatch (SRM)**: убедиться, что фактическое распределение трафика соответствует запланированному соотношению 50/50 с помощью chi-square теста. Значимый дисбаланс свидетельствует о проблеме рандомизации или трекинга и делает результаты недостоверными независимо от значения основной метрики. Также проверить сопоставимость групп (источники трафика, устройства, география) и отсутствие пробелов в трекинге.

### Шаг 2: Анализ основной метрики
Для каждого варианта рассчитать:
- Конверсию в MQL
- Абсолютный прирост
- Относительный прирост
- 95% доверительный интервал
- Статистическую значимость (p-value)

### Шаг 3: Воронковый анализ
Определить, где произошло изменение поведения:
`Сессии → клик CTA → начало формы → отправка формы → лид → MQL`

Найти этап с наибольшей дельтой между контролем и вариантом.

### Шаг 4: Проверка на novelty effect
Построить дневной тренд конверсии для обоих вариантов. Использовать данные с недели 2+ как основной период анализа только если в неделе 1 наблюдается чёткий всплеск с последующим затуханием до уровня контроля -- это и есть признак novelty effect. Если тренд стабилен с первого дня -- использовать весь период теста.

### Шаг 5: Сегментный анализ

| Сегмент | Почему важен |
|---------|-------------|
| Источник трафика (organic / paid / direct) | Разный уровень намерения |
| Устройство (desktop vs mobile) | Перенос CTA по-разному влияет на мобильный UX |
| Новые vs повторные посетители | Novelty effect меньше у повторных пользователей |
| Регион (EU / LatAm / US) | Изменения текста могут по-разному резонировать |
| Тип кампании (brand vs non-brand) | Разные этапы воронки |

Если вариант проигрывает в каком-то сегменте: оценить стратегическую важность сегмента и взвесить trade-off между общим приростом и потерями в отдельном сегменте. Небольшой проигрывающий сегмент при в целом сильном результате не обязательно блокирует запуск, но ключевой сегмент (например, органический трафик или крупный регион) требует расследования до принятия решения.

### Шаг 6: Правила остановки
Нельзя смотреть на результаты и останавливать тест без заранее определённых правил -- это накручивает ошибку первого рода.
- **Досрочная остановка по вреду:** если guardrail-метрика ухудшается сверх заданного порога → останавливаем немедленно
- **Досрочная остановка по успеху:** только если промежуточные проверки следуют предопределённым правилам контроля ошибок
- **Плановые промежуточные проверки:** максимум 2 проверки (на 50% и 75% выборки) со статистической коррекцией для сохранения общего alpha = 0,05

### Шаг 7: Решение

**Правило запуска:** запускать только если (1) основная метрика показывает статистически значимое улучшение, И (2) все guardrail-метрики остаются в пределах заданных допустимых порогов. Оба условия должны выполняться одновременно -- значимый прирост при нарушении guardrail не является основанием для запуска.

| Результат | Решение |
|-----------|---------|
| Основная метрика значима, guardrails в норме, результат устойчив по сегментам | Запускаем |
| Позитивная тенденция, но не значима | Продлить тест или итерировать дизайн |
| Значимый прирост, но guardrail нарушен (MQL→SAL падает, время загрузки растёт) | Не запускаем -- расследуем |
| Эффект только в одном сегменте | Не запускаем глобально -- итерируем под этот сегмент |
| Нет улучшения или ухудшение | Отказываемся от варианта; анализируем воронку для переформулировки гипотезы |

---

## Допущения и ограничения
1. Достаточный трафик для достижения размера выборки за 3-4 недели
2. Интеграция GA4 → CRM должна быть настроена до запуска
3. Целостный тест -- нельзя изолировать индивидуальные эффекты; нужны follow-up тесты если вариант побеждает
4. Цикл принятия решения в B2B охватывает несколько сессий; предпочтительно назначение на уровне пользователя
5. Окно атрибуции MQL (30 дней) должно быть явно определено и закреплено до запуска
6. Null result plan: анализировать воронку для переформулировки гипотезы перед следующей итерацией
