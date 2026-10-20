# Контракт API и схемы событий — «Умный кредитный кабинет предпринимателя»

Версия контракта 1.0.0. Основание: ТЗ 4.1 и архитектура MVP (разделы 8–13).
Контракт — единственный источник правды для Frontend, Backend и DS/ML: любое поле, которого нет здесь, в API не передаётся.
Язык реализации сервисов контракт не задаёт; по этим файлам можно сгенерировать клиентов, серверные заглушки и мок-сервер.

## 1. Состав

| Папка / файл | Что внутри | Кто использует |
|---|---|---|
| `schemas/domain.schema.json` | 108 общих определений (`$defs`): перечисления, сущности, ошибки. На них ссылаются все остальные файлы | все |
| `openapi/core-api.yaml` | Публичный API кабинета и панели андеррайтера, 50 операций | Frontend ↔ core-api |
| `openapi/ml-service.yaml` | Внутренний API расчётов, 11 операций | core-api → ml-service |
| `openapi/bank-sim.yaml` | Имитация АБС, РКО, БКИ, антифрода, 5 операций | core-api, ml-service → bank-sim |
| `events/envelope.schema.json` | Конверт любого события брокера | все продюсеры и консьюмеры |
| `events/<topic>.schema.json` | Схема поля `data` для каждого из 11 топиков | см. таблицу 4 |
| `events/topics.yaml` | Реестр топиков: ключ, продюсер, консьюмеры, версия, требования, DLQ | Backend, DevOps |
| `sse/chat-events.schema.json` | События потока ответа ассистента | Frontend ↔ core-api |
| `sse/stream-events.schema.json` | События общего потока `GET /events/stream` | Frontend ↔ core-api |
| `examples/` | Эталонные примеры DEMO-1 (DC-1) и по одному примеру на каждый топик | тесты всех команд |
| `tools/` | Генераторы схем и примеров, скрипт проверки | владелец контракта, CI |

## 2. Общие соглашения

1. **Формат.** JSON в UTF-8, имена полей — `snake_case`, JSON Schema 2020-12, OpenAPI 3.1.
2. **Деньги** — число в рублях, округлённое отправителем до 2 знаков (`418178.65`). Валюта всегда RUB, поле валюты не передаётся.
3. **Ставки, вероятности, доли** — дробь: `0.18` = 18 %, `0.5537` = оценка 55,37 %.
4. **Даты** — `YYYY-MM-DD`; моменты времени — ISO 8601 с часовым поясом (`2026-10-14T09:30:00+03:00`).
5. **Идентификаторы** — UUID v4; ИНН — 10 цифр (ЮЛ) или 12 цифр (ИП); коды продуктов `P1`…`P6`.
6. **Аутентификация** — httpOnly-cookie `session` (JWT, 8 ч). Изменяющие запросы передают `X-CSRF-Token`, который выдаёт `GET /auth/me`.
7. **Изоляция компании (NFR-13).** core-api берёт ИНН только из сессии. В пути и теле клиентских запросов ИНН принимается только при входе (`/registry/{inn}`, `/auth/inn-login`).
8. **Ошибки** — `application/problem+json` по RFC 9457 с обязательным машинным полем `code` из перечисления `ErrorCode` (19 значений). Интерфейс выбирает текст по `code`, а не по `detail`.
9. **Идемпотентность.** Операции с заголовком `Idempotency-Key` при повторе с тем же ключом возвращают первый ответ. Тот же ключ с другим телом даёт `409 IDEMPOTENCY_CONFLICT`. Ключ хранится 24 ч.
10. **Трассировка.** Каждый запрос и ответ несёт `traceparent` (W3C). Его trace id записывается в `correlation_id` всех событий, порождённых запросом.
11. **Асинхронность.** Подача заявки (`POST /applications/{id}/submit`) отвечает `202`. Решение приходит в `GET /events/stream` событием `application.status` (SC-08: ≤ 60 с).

## 3. API core-api — группы операций

| Группа | Операции | Требования ТЗ |
|---|---|---|
| Вход и реестр | `GET /registry/{inn}`, `POST /auth/inn-login`, `GET /demo/companies`, `POST /auth/demo-login`, `POST /auth/staff-login`, `GET /auth/me`, `POST /auth/logout` | REG-01…REG-07 |
| Профиль, каталог | `GET /profile`, `GET /products`, `GET /dictionaries/reason-codes` | REG-08, PRF-01…PRF-10, CAT-01, 5.4 |
| Потребность | `POST /needs`, `GET /needs/{id}`, `PATCH /needs/{id}` | NEED-01…NEED-08 |
| Подбор | `POST /recommendations`, `GET /recommendations/{id}`, `GET …/why-not/{product_code}` | REC-01…REC-17 |
| «Что сделать» | `POST /recommendations/{id}/what-if`, `POST /what-if/evaluate`, `POST /applications/{id}/what-if`, `POST /applications/{id}/versions`, `POST /recommendations/{id}/applications` | WI-01…WI-08 |
| Финансовый пульс | `GET /cashflow/summary`, `GET /cashflow/forecast`, `GET /insights`, `POST /insights/{id}/dismiss` | CF-01…CF-07 |
| Заявка | `GET/POST /applications`, `GET/PATCH /applications/{id}`, `GET …/checklist`, `POST …/consent/request`, `POST …/consent/confirm`, `POST …/submit`, `POST …/accept`, `GET …/decision` | APP-01…APP-08, SC-08 |
| Документы | `POST /applications/{id}/documents`, `GET/DELETE /documents/{id}`, `PATCH /documents/{id}/fields`, `GET /documents/{id}/content` | DOC-01…DOC-09 |
| Ассистент | `POST /chat/sessions`, `GET /chat/sessions/{id}`, `POST /chat/sessions/{id}/messages` (SSE), `POST /chat/actions/{id}/confirm`, `POST /escalations` | AI-01…AI-12 |
| Поток событий | `GET /events/stream` (SSE) | APP-05, CF-06, DOC-02, REC-10 |
| Андеррайтер | `GET /uw/queue`, `GET /uw/applications/{id}`, `POST /uw/applications/{id}/decision`, `POST /uw/escalations/{id}/close` | UW-01…UW-04 |

Сквозной сценарий DEMO-1 по вызовам:
`POST /auth/demo-login` → `POST /needs {text}` → `PATCH /needs/{id} {answer}` (пока `next = ASK`) → `POST /recommendations` → `POST /applications {recommendation_id, product_code}` → `POST /applications/{id}/documents` → `POST …/consent/request` → `POST …/consent/confirm` → `POST …/submit` → событие `application.status` в `/events/stream` → `GET …/decision` → `POST …/accept`.

## 4. События брокера

Брокер — Redpanda (Kafka API) со Schema Registry в прототипе, Kafka в банке.

1. Каждое сообщение — конверт `{event_id, type, source, time, subject, schema_version, correlation_id, data}`. Ключ сообщения = `subject`.
2. Доставка как минимум один раз. Консьюмер обязан быть идемпотентным по `event_id` (таблица обработанных событий).
3. Продюсер публикует через outbox: событие пишется в одной транзакции с изменением данных.
4. Ошибка обработки: 3 повтора через 1 с, 5 с, 25 с, затем `<topic>.dlq`.
5. Совместимость схем — BACKWARD: разрешено только добавлять необязательные поля. Ломающее изменение = новый мажор `schema_version` и топик `<topic>.v2`.

| Топик | Ключ | Продюсер → консьюмеры | Требования |
|---|---|---|---|
| `bank.transactions_updated` | inn | bank-sim → ml-service | REG-07 |
| `document.uploaded` | application_id | core-api → doc-service | DOC-01, DOC-02 |
| `document.parsed` | application_id | doc-service → core-api, ml-service | DOC-03…DOC-05, DOC-08, DOC-09 |
| `document.failed` | application_id | doc-service → core-api | DOC-01, DOC-02 |
| `profile.updated` | inn | ml-service → core-api | PRF-01, REC-10, DOC-08 |
| `cashflow.forecast_ready` | inn | ml-service → core-api | CF-03 |
| `cashflow.gap_detected` | inn | ml-service → core-api | CF-04…CF-06 |
| `application.submitted` | application_id | core-api → ml-service | APP-03, SC-01, SC-04 |
| `decision.made` | application_id | ml-service → core-api | SC-04, SC-06…SC-08 |
| `application.status_changed` | application_id | core-api → аналитика | APP-05 |
| `recommendation.made` | inn | core-api → аналитика | REC-08, Q-08, Q-09 |

`document.parsed` содержит флаг `accepted`: при несовпадении ИНН в документе с ИНН компании (DOC-04) `accepted = false` и код `INN_MISMATCH`; данные документа в профиль не попадают.

## 5. Потоки SSE

| Поток | Типы событий |
|---|---|
| Ответ ассистента (`POST /chat/sessions/{id}/messages`) | `delta` — фрагмент текста; `tool` — вызов инструмента; `need` — обновлённая потребность; `question` — уточняющий вопрос; `recommendation` — снимок подбора; `action` — действие, ждущее подтверждения кнопкой; `escalation` — передача сотруднику; `done`; `error` |
| Общий поток (`GET /events/stream`) | `application.status`, `insight.created`, `document.status`, `recommendation.updated`, `ping` каждые 15 с |

При обрыве клиент переподключается с заголовком `Last-Event-ID`. Сервер повторяет события за последние 5 минут.

## 6. Эталонные примеры DEMO-1

Компания DC-1, потребность «закупка товара или сырья, 2 000 000 ₽, 5 мес.» (правило выбора цели ТЗ 4.2, NEED-08). Числа посчитаны по формулам ТЗ 4.3–4.4 скриптом `tools/gen_examples.py`.

| Величина | Значение |
|---|---|
| СДП | 1 150 000,00 ₽ |
| P2: платёж за 2 млн на 5 мес. под 18 % | 418 178,65 ₽ |
| P2: допустимый лимит | 2 367 409,26 ₽ |
| P1: доступный лимит | 1 750 000,00 ₽ |
| Итоговые оценки | P2 0,8511 · P3 0,7661 · P1 0,5537 |
| Лучший / альтернативы | P2 / [P3] (0,7661 ≥ 0,7 × 0,8511; P1 ниже порога) |

Эти файлы — эталон для тестов: результат ml-service на DC-1 должен совпасть с `examples/recommendation.DEMO-1.json` по `best_product_code`, `alternatives`, суммам и оценкам (Q-06).

## 7. Принятые допущения

1. Деньги передаются числом в рублях, не в копейках: так проще интерфейсу, а округление до 2 знаков делает отправитель.
2. Клиентское представление решения (`ClientDecisionView`) не содержит PD и SHAP — только грейд, условия и причины текстом (APP-06, AI-09). Полный `Decision` видит только андеррайтер.
3. Код согласия — имитация SMS: `POST …/consent/request` возвращает его в поле `demo_code`, интерфейс показывает его на экране.
4. Идентификаторы снимков подбора присваивает core-api; идентификаторы вариантов «что сделать» присваивает ml-service, core-api их сохраняет, чтобы `POST …/versions` и `POST /recommendations/{id}/applications` ссылались на сохранённый вариант.
5. bank-sim получает отраслевую группу и дату регистрации из заголовков `X-Industry-Group`, `X-Registered-At`, чтобы генерация данных соответствовала реестру (REG-07).

## 8. Проверка и изменение контракта

Инструменты проверки не зависят от языка сервисов. Нужны `jsonschema`, `referencing`, `pyyaml`, `openapi-spec-validator`:

```
pip install jsonschema referencing pyyaml openapi-spec-validator
python3 tools/validate.py .
python3 -m openapi_spec_validator openapi/core-api.yaml
python3 -m openapi_spec_validator openapi/ml-service.yaml
python3 -m openapi_spec_validator openapi/bank-sim.yaml
```

`validate.py` проверяет: все JSON Schema соответствуют метасхеме 2020-12; все ссылки на `domain.schema.json#/$defs/…` существуют; каждый пример события проходит конверт и схему `data`; примеры DEMO-1 проходят свои схемы; негативные примеры отклоняются.

Порядок изменения:
1. Правка вносится в генератор (`tools/gen_domain.py`, `tools/gen_events.py`) или в YAML-файл OpenAPI, а не в сгенерированный JSON.
2. Пересборка: `python3 tools/gen_domain.py schemas/domain.schema.json && python3 tools/gen_events.py . && python3 tools/gen_examples.py .`
3. Проверка командами выше. CI не пропускает изменение без зелёной проверки.
4. Изменение версии: новое необязательное поле — минорная версия; удаление или переименование — мажорная (см. раздел 4, п. 5).
5. Изменение согласуют владельцы затронутых сервисов (Frontend для core-api, DS/ML для ml-service и событий скоринга).
