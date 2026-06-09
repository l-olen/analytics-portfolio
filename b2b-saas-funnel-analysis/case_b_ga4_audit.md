# Case B: GA4/GTM Audit — Post-CMS Migration Data Quality Issues

## Context
After CMS migration, three distinct problems appeared simultaneously:
1. 35% drop in organic sessions in GA4
2. Sharp increase in (not set) values across source/medium, landing page, region
3. Form submission events firing inconsistently (double counting + missing)

Each problem has different root causes and requires a separate diagnostic path. They are listed together because they share a common trigger (CMS migration), but diagnosing them as one issue will produce incorrect conclusions.

---

## 1. Root Cause Diagnosis

### Step 0: Establish the timeline first
Before investigating causes, identify the exact date anomalies started and whether onset was immediate or gradual. Gradual onset suggests a slow-propagating configuration issue (CDN cache, partial deployment); immediate onset suggests a deployment error (missing GTM snippet on new templates). Compare GA4, Search Console, CRM, and server logs day-by-day around the migration date.

---

### Problem 1: 35% organic session drop

**First: verify whether the drop is real or a tracking artifact.**
Before investigating analytics configuration, check whether the CMS migration introduced SEO-level problems that could cause a genuine traffic drop: robots.txt blocking crawlers, meta noindex tags on key templates, incorrect canonical tags, broken or missing sitemap, redirect chains breaking link equity, or redirect mapping errors sending pages to 404. These are CMS migration failure modes independent of GA4.

Then use Search Console as an independent directional benchmark: if GSC clicks are stable while GA4 sessions dropped, the problem is tracking loss, not real traffic loss. Note: GSC clicks and GA4 sessions measure different things and will never match exactly -- this comparison is an anomaly detector, not a reconciliation tool.

**Tracking hypotheses (if SEO checks are clean):**

| Priority | Hypothesis | Mechanism | How to confirm |
|----------|------------|-----------|----------------|
| 1 | Consent Mode v2 missing or misconfigured | Post-2024 EU sites: GA4 blocked before consent; data loss even for users who consent if default state is wrong | Check gtag consent default/update in GTM DebugView |
| 2 | GTM snippet missing from new CMS templates | New templates not inheriting GTM → pages send no data | Screaming Frog crawl, flag pages without GTM |
| 3 | Cross-domain tracking broken | Domain/subdomain changes → organic sessions re-attributed as (direct)/(none) | GA4 Admin → Data Streams → cross-domain settings |
| 4 | Referral exclusion list outdated | New CMS domain treated as external referral → session splits | GA4 Admin → Referral exclusions |
| 5 | Redirect chains before GA4 fires | Heavy redirect stack → hits lost before page loads | DevTools Network tab |

---

### Problem 2: (not set) in dimensions

| Dimension | Root cause |
|-----------|-----------|
| source/medium | Events firing without session context; Referer header stripped by CDN; cross-domain tracking missing; UTM parameters lost in redirect chain; session_start event not firing |
| landing page | page_view event not firing on some CMS templates → GA4 has no page_location to attribute the session to |
| region | IP lookup failing -- CDN or reverse proxy not forwarding original IP (X-Forwarded-For header missing) |

**Key insight:** (not set) in source/medium is typically a symptom of broken session context -- the event exists in GA4 but has no parent session to attach attribution to. It is not a measurement error in isolation; it signals that session initialization failed upstream. This happens when custom events fire before page_view, or when SPA routing triggers events before GA4 re-initializes.

**Quick tests:**
- `curl -I -e "https://google.com" [site URL]` -- check if Referer header survives CDN
- DevTools → Network → `collect?v=2` -- verify `dr` (document referrer) in GA4 hit payload

---

### Problem 3: Form events double counting and missing

**Foundational rule:** there must be a single source of event truth -- either GTM manages all GA4 events, or a hardcoded gtag.js does. Running both simultaneously guarantees duplicate events and makes debugging nearly impossible. The first diagnostic step is to check the page source for both `GTM-` and `gtag` occurrences and eliminate the duplicate.

**Double counting causes:**
- GA4 tag in GTM fires AND a hardcoded gtag.js snippet exists directly on the page
- GTM trigger fires on both form submit AND thank-you page load
- Multiple GTM containers on the same page
- SPA routing: form submit fires on interaction AND again on route change to confirmation page
- GA4 Enhanced Measurement auto-tracking firing alongside custom GTM event for the same form
- New CMS plugin sending events independently from GTM

**Missing events causes:**
- Form IDs, CSS selectors, or element names changed in the new CMS → GTM triggers no longer match HTML
- AJAX form submission: page does not reload → standard "Form Submission" trigger requires page reload
- Thank-you page redirect fires before GA4 hit completes
- GTM snippet missing from thank-you page template
- JavaScript errors on form pages blocking GTM execution
- Consent restrictions blocking GA4 for specific user segments

---

## 2. GTM/GA4 Validation Process (6-step chain)

**Step 1 -- Baseline comparison:** Pull pre/post-migration sessions by URL pattern in GA4. Identify which page types lost sessions. Compare (not set) percentage before and after migration date.

**Step 2 -- GTM Preview Mode audit:** Run on every key template (home, product landing, blog, form page, thank-you page). Check: does GA4 Configuration tag fire? How many times? Does form event fire once per submission?

**Step 3 -- GA4 DebugView:** Validate each key event through the full chain:

| Step | Check |
|------|-------|
| 1 | User action occurs in browser |
| 2 | dataLayer push visible in GTM Preview |
| 3 | GTM trigger activates |
| 4 | GA4 hit visible in Network tab (collect?v=2) |
| 5 | Event appears in DebugView with correct parameters |
| 6 | Event visible in GA4 reports and BigQuery export |

Required parameters on each event: `session_id`, `page_location`, `page_referrer`, `source`, `medium`, form identifier.

**Step 4 -- DevTools Network tab:** Filter to `collect?v=2`. Count hits per form submission. Inspect `dl` (document location), `dr` (document referrer), `_ga` cookie.

**Step 5 -- Supporting tools:**

| Tool | What it checks |
|------|---------------|
| GTM Preview | Tag firing logic, trigger conditions, event count |
| GA4 DebugView | Real-time event validation with parameters |
| Chrome DevTools (Network) | Raw GA4 requests, payload inspection |
| Google Search Console | Organic traffic directional benchmark |
| Screaming Frog | GTM snippet presence across all pages |
| GA4 BigQuery export | Unsampled raw event-level data for affected period |

**Step 6 -- Problem-specific checks:**
- Organic drop: Screaming Frog crawl for missing GTM; verify Measurement ID in GA4 Admin; check Consent Mode v2 default + update states in DebugView; check robots.txt, noindex, canonicals
- (not set): curl Referer test; check X-Forwarded-For in CDN config; verify dataLayer initialization order
- Form events: page source search for `gtag` and `GTM-` occurrences; submit form exactly once and count events in DebugView; verify CSS selectors match new CMS HTML; for AJAX forms replace "Form Submission" trigger with custom dataLayer.push on AJAX success callback

---

## 3. Historical Data Reconstruction

The affected period has corrupted data that cannot be fully restored. The approach is to establish ground truth from alternative sources and annotate the gap.

**For sessions:** Use Google Search Console as an independent directional baseline for organic. Apply correction factor: `actual_sessions ≈ recorded_sessions / (1 - tracking_loss_rate)` where tracking_loss_rate is estimated from the share of pages missing GTM × their traffic volume.

**For conversions:**
- Use CRM as the source of truth: pull all leads created during the affected period with original source attribution
- Cross-reference CRM timestamps with GA4 to estimate double-count rate
- Apply deduplication: GA4 events within 60 seconds in the same session flagged as duplicates
- If BigQuery export was active before the incident: use raw event-level SQL to identify duplicates and reconstruct clean counts
- Example: if CRM records 500 leads but GA4 records 700 → ~200 duplicates. If GA4 records 350 → ~150 missing. This ratio guides the reconstruction approach.

**Documentation:** Add GA4 annotation for the affected date range. Note in all dashboards using this period. Do not blend affected and clean data in trend analysis without explicit flagging.

---

## 4. Governance to Prevent Recurrence

**Pre-migration checklist (mandatory before any CMS/platform change):**

1. UAT on staging before production deployment
2. GTM Preview validation on staging across all page templates
3. GA4 DebugView test of all key events on staging
4. Screaming Frog crawl of staging -- verify GTM snippet on all pages
5. Cookie consent and Consent Mode v2 compatibility verified
6. Cross-domain/subdomain tracking configuration verified
7. Referral exclusion list updated with new CMS domains
8. UTM parameter preservation verified across all redirects
9. Enhanced Measurement settings reviewed for conflicts with custom events
10. Post-release KPI validation within 24 hours: sessions, organic traffic, source/medium, conversion volume

**Ongoing monitoring:**

- GA4 Intelligence Alert: session volume drop >15% vs same day last week
- Custom alert: (not set) in source/medium >5%
- Weekly automated report: form submissions in GA4 vs CRM leads created (delta >10% triggers review)
- Automated monitoring dashboard (Looker Studio): daily sessions, conversions, source/medium distribution, (not set) rate

**Structural safeguard:** Maintain CRM-based conversion count as an independent source of truth. Never rely solely on GA4 for conversion reporting -- always cross-validate with CRM.

---

## 5. Recommended Action Sequence

When this type of incident is discovered, the response should follow a fixed order:

1. **Freeze reporting** -- stop using the affected period's data in dashboards and decision-making; add GA4 annotations
2. **Diagnose and repair** -- work through the hypotheses above in priority order; fix tracking before touching data
3. **Reconstruct** -- use CRM and Search Console to estimate ground truth for the affected period; apply correction factors; document methodology
4. **Validate fix** -- run full 6-step validation chain before declaring the issue resolved
5. **Relaunch monitoring** -- activate automated alerts; confirm clean data for 48-72 hours post-fix before resuming normal reporting

---
---

# Кейс B: Аудит GA4/GTM -- Проблемы качества данных после миграции CMS

## Контекст
После миграции CMS одновременно возникли три проблемы:
1. Падение органических сессий в GA4 на 35%
2. Резкий рост значений (not set) в source/medium, landing page, region
3. Непоследовательное срабатывание событий форм (двойной счёт и пропуски)

Каждая проблема имеет разные root causes и требует отдельного диагностического пути. Они объединены, потому что имеют общий триггер (миграция CMS), но диагностировать их как одну проблему -- значит получить неверные выводы.

---

## 1. Диагностика root causes

### Шаг 0: Сначала устанавливаем временную шкалу
До начала расследования -- найти точную дату начала аномалий и характер их появления (мгновенное или постепенное). Постепенное нарастание указывает на медленно распространяющуюся проблему (CDN-кеш, частичный деплой); мгновенное -- на ошибку деплоя (отсутствие GTM-сниппета на шаблонах). Сравниваем GA4, Search Console, CRM и серверные логи по дням вокруг даты миграции.

---

### Проблема 1: Падение органических сессий на 35%

**Сначала: определить, реальное ли это падение или потеря трекинга.**
До исследования конфигурации аналитики -- проверить, не внесла ли миграция CMS SEO-проблемы, которые могут вызвать реальное падение трафика: блокировка роботов через robots.txt, теги meta noindex на ключевых шаблонах, неверные canonical-теги, отсутствие или ошибки в sitemap, цепочки редиректов с потерей ссылочного веса, ошибки маппинга редиректов со страницами 404. Это точки отказа миграции CMS, не зависящие от GA4.

Затем использовать Search Console как независимый ориентир: если клики GSC стабильны, а сессии GA4 упали -- проблема в потере трекинга, а не реального трафика. Важно: клики GSC и сессии GA4 измеряют разные вещи и никогда не совпадают точно -- это инструмент обнаружения аномалий, не инструмент сверки.

**Гипотезы по трекингу (если SEO-проверки в порядке):**

| Приоритет | Гипотеза | Механизм | Как подтвердить |
|-----------|----------|----------|----------------|
| 1 | Consent Mode v2 отсутствует или настроен неверно | После 2024 года: GA4 блокируется до получения согласия; потеря данных даже от давших согласие, если default-состояние неверное | Проверить gtag consent default/update в GTM DebugView |
| 2 | GTM-сниппет отсутствует на части шаблонов CMS | Новые шаблоны не наследуют GTM → страницы есть, данных нет | Crawl Screaming Frog, отметить страницы без GTM |
| 3 | Кросс-доменный трекинг сломан | Изменения домена/поддомена → органические сессии атрибутируются как (direct)/(none) | GA4 Admin → Data Streams → настройки кросс-домена |
| 4 | Устаревший список исключений реферралов | Новый домен CMS воспринимается как внешний реферрал → разбивка сессий | GA4 Admin → Referral exclusions |
| 5 | Цепочки редиректов до срабатывания GA4 | Тяжёлый стек редиректов → часть хитов не успевает отправиться | DevTools Network |

---

### Проблема 2: Рост (not set) в измерениях

| Измерение | Root cause |
|-----------|-----------|
| source/medium | События срабатывают вне сессионного контекста; реферер обрезается CDN; нет кросс-доменного трекинга; UTM теряются в редиректах; событие session_start не срабатывает |
| landing page | Событие page_view не срабатывает на части шаблонов CMS → GA4 не может атрибутировать сессию к странице |
| region | Ошибка определения IP -- CDN или reverse proxy не передаёт оригинальный IP (заголовок X-Forwarded-For отсутствует) |

**Ключевой инсайт:** (not set) в source/medium -- это симптом сломанного сессионного контекста: событие существует в GA4, но у него нет родительской сессии для атрибуции. Это не изолированная ошибка измерения -- это сигнал о том, что инициализация сессии сломалась выше по цепочке. Происходит когда кастомные события срабатывают до page_view, или когда SPA-роутинг вызывает события до реинициализации GA4.

**Быстрые тесты:**
- `curl -I -e "https://google.com" [URL сайта]` -- проверить, сохраняется ли заголовок Referer после CDN
- DevTools → Network → `collect?v=2` -- проверить `dr` (document referrer) в payload GA4-хита

---

### Проблема 3: События форм -- двойной счёт и пропуски

**Основополагающее правило:** должен быть единственный источник событий -- либо GTM управляет всеми GA4-событиями, либо хардкодный gtag.js. Оба одновременно гарантируют дубли и делают отладку почти невозможной. Первый диагностический шаг -- проверить исходный код страницы на наличие обоих: `GTM-` и `gtag`, и устранить дублирование.

**Причины двойного счёта:**
- GA4-тег в GTM срабатывает И одновременно есть хардкодный gtag.js на странице
- GTM-триггер срабатывает и на submit формы, и на загрузку страницы подтверждения
- На странице установлено несколько GTM-контейнеров
- SPA-роутинг: submit срабатывает при взаимодействии И повторно при смене роута
- Enhanced Measurement в GA4 автоматически отслеживает форму параллельно с кастомным событием GTM
- CMS-плагин отправляет события независимо от GTM

**Причины пропуска событий:**
- ID форм, CSS-селекторы или названия элементов изменились в новой CMS → GTM-триггеры больше не соответствуют HTML
- AJAX-форма: страница не перезагружается → стандартный триггер "Form Submission" требует перезагрузки
- Редирект на страницу подтверждения срабатывает до отправки GA4-хита
- GTM-сниппет отсутствует на шаблоне страницы подтверждения
- JavaScript-ошибки на странице формы блокируют выполнение GTM
- Ограничения согласия блокируют GA4 для части пользователей

---

## 2. Процесс валидации GTM/GA4 (6 шагов)

**Шаг 1 -- Baseline-сравнение:** Сравнить сессии до и после миграции по типам страниц. Определить, где потери. Сравнить долю (not set) до и после даты миграции.

**Шаг 2 -- GTM Preview Mode:** Запустить на каждом ключевом шаблоне. Проверить: срабатывает ли GA4 Configuration Tag? Сколько раз? Сколько событий формы на одну отправку?

**Шаг 3 -- GA4 DebugView:** Проверить каждое ключевое событие по цепочке:

| Шаг | Проверка |
|-----|---------|
| 1 | Действие пользователя в браузере |
| 2 | dataLayer push виден в GTM Preview |
| 3 | GTM-триггер активируется |
| 4 | GA4-хит виден в Network (collect?v=2) |
| 5 | Событие в DebugView с корректными параметрами |
| 6 | Событие видно в отчётах GA4 и экспорте BigQuery |

Обязательные параметры на каждом событии: `session_id`, `page_location`, `page_referrer`, `source`, `medium`, идентификатор формы.

**Шаг 4 -- DevTools Network:** Фильтр `collect?v=2`. Количество хитов на одну отправку формы. Проверить `dl` (location), `dr` (referrer), куки `_ga`.

**Шаг 5 -- Инструменты:**

| Инструмент | Что проверяет |
|-----------|--------------|
| GTM Preview | Логика срабатывания тегов, триггеры, количество событий |
| GA4 DebugView | Валидация событий в реальном времени с параметрами |
| Chrome DevTools (Network) | Сырые GA4-запросы, инспекция payload |
| Google Search Console | Ориентир по органическому трафику |
| Screaming Frog | Наличие GTM-сниппета на всех страницах |
| GA4 BigQuery export | Несэмплированные данные на уровне событий |

**Шаг 6 -- Специфические проверки по проблемам:**
- Падение органики: crawl Screaming Frog; проверить Measurement ID в GA4 Admin; проверить Consent Mode v2 default + update в DebugView; robots.txt, noindex, canonical
- (not set): curl-тест Referer; X-Forwarded-For в конфиге CDN; порядок инициализации dataLayer
- События форм: поиск `gtag` и `GTM-` в исходном коде; отправить форму один раз и посчитать события в DebugView; проверить CSS-селекторы; для AJAX-форм заменить "Form Submission" триггер на кастомный dataLayer.push в коллбэке AJAX-успеха

---

## 3. Восстановление исторических данных

Период с повреждёнными данными не может быть полностью восстановлен. Подход -- установить ground truth из альтернативных источников и задокументировать пробел.

**По сессиям:** Google Search Console как независимый ориентир для органики. Коэффициент коррекции: `реальные_сессии ≈ зафиксированные_сессии / (1 - потеря_трекинга)`, где потеря_трекинга оценивается как доля страниц без GTM × их доля трафика.

**По конверсиям:**
- CRM как источник истины: выгрузить все лиды за период с оригинальной source-атрибуцией
- Сопоставить временные метки CRM с GA4 для оценки доли дублей
- Дедупликация: GA4-события в течение 60 секунд в одной сессии -- флаг дубля
- Если до инцидента был активен BigQuery-экспорт: SQL-запросы по сырым данным для выявления дублей
- Пример: если CRM фиксирует 500 лидов, а GA4 -- 700, то ~200 дублей. Если GA4 -- 350, то ~150 пропущено. Это соотношение определяет подход к реконструкции.

**Документирование:** Добавить аннотацию в GA4 на период с проблемами. Отметить во всех дашбордах. Не смешивать проблемный и чистый периоды в анализе трендов без явного указания.

---

## 4. Governance для предотвращения повторения

**Чеклист перед миграцией (обязателен перед любым изменением CMS/платформы):**

1. UAT на staging до деплоя в production
2. GTM Preview на staging по всем ключевым шаблонам страниц
3. GA4 DebugView -- тест всех ключевых событий на staging
4. Screaming Frog crawl staging -- проверить GTM-сниппет на всех страницах
5. Проверить совместимость cookie consent и Consent Mode v2
6. Проверить конфигурацию кросс-доменного/поддоменного трекинга
7. Обновить список исключений реферралов с новыми доменами CMS
8. Проверить сохранение UTM-параметров через все редиректы
9. Пересмотреть настройки Enhanced Measurement на конфликты с кастомными событиями
10. KPI-валидация в течение 24 часов после релиза: сессии, органика, source/medium, объём конверсий

**Текущий мониторинг:**

- GA4 Intelligence Alert: падение объёма сессий >15% vs тот же день прошлой недели
- Кастомный алерт: (not set) в source/medium >5%
- Еженедельный автоматический отчёт: отправки форм в GA4 vs лиды в CRM (дельта >10% -- триггер проверки)
- Автоматизированный дашборд мониторинга (Looker Studio): ежедневные сессии, конверсии, распределение source/medium, доля (not set)

**Структурная защита:** Поддерживать CRM-счётчик конверсий как независимый источник истины. Никогда не полагаться только на GA4 для отчётности по конверсиям -- всегда кросс-валидировать с CRM.

---

## 5. Рекомендуемая последовательность действий

При обнаружении инцидента такого типа -- фиксированный порядок ответа:

1. **Заморозить отчётность** -- прекратить использовать данные за проблемный период в дашбордах и принятии решений; добавить аннотации в GA4
2. **Диагностировать и исправить** -- разобрать гипотезы выше в порядке приоритета; исправить трекинг до работы с данными
3. **Реконструировать** -- использовать CRM и Search Console для оценки ground truth за проблемный период; применить коэффициенты коррекции; задокументировать методологию
4. **Валидировать исправление** -- провести полную 6-шаговую цепочку валидации до объявления проблемы решённой
5. **Перезапустить мониторинг** -- активировать автоматические алерты; подтвердить чистые данные в течение 48-72 часов после исправления, затем возобновить нормальную отчётность
