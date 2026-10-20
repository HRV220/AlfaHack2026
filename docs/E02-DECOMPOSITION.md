# E02. Платформа и инфраструктура — декомпозиция на задачи разработки

Источник: `docs/BACKLOG.md` (E02-01…E02-11), архитектура разделы 8, 9, 10.1, 11.1, 16, 21, 21.1. Статусы задач бэклога не менялись; подзадачи — кандидаты на тикеты. Оценка: S ≈ до 1 ч, M ≈ 1–3 ч, L ≈ 3–6 ч (одним исполнителем).

**Цель эпика.** `docker compose up` на машине с 16 ГБ ОЗУ без ключей и сети поднимает профиль `core` вместе с локальной LLM; healthcheck зелёные; миграции и топики создаются автоматически.

## Рекомендуемый порядок (критический путь)

```
E02-09 (uv workspace) ─► E02-01 (структура) ─► E02-10 (образы) ─┐
                                       │                        ├─► E02-02 (Compose core) ─► E02-06 (init-контейнер) ─► приёмка
E02-05 (конфиги) ──────────────────────┤                        │
E02-03 (миграции) ◄── E02-09           └─► E02-11 (web) ────────┤
E02-04 (брокер, outbox) ◄── E02-02 (Redpanda) + E02-03          │
E02-07 (LLM) ── параллельно, входит в E02-02/E02-06 ────────────┘
E02-08 (gpu, obs) — после приёмки core, Should-уровень (S)
```

Параллельно с первого часа: E02-09/E02-01 (Backend), E02-05 (Product пишет тексты `reason_codes`), E02-07 (DS/ML — выбор и замер модели), E02-11 (Frontend, на заглушке core-api).

## Расхождения и допущения (сверить до начала)

1. Дерево архитектуры (раздел 16) держит контракты в `contracts/`, фактически они в `docs/contracts/` (CLAUDE.md, E01). Принять `docs/contracts/` как источник; `libs/contracts` генерируется оттуда.
2. E01-08 фиксирует «CI не используется — решение владельца», а E02-09/E02-10 и раздел 16 говорят о CI. В E02 CI не делаем: проверки запускаются локально (`pre-commit`, `make check`); CI-конвейер — в E16.
3. E02-06 требует seed демо-компаний и синтетического реестра, но генераторы и фикстуры делает E03. В E02 init-контейнер получает точки расширения (`seed/` — пустые заглушки + минимум 3 демо-компании вручную), полный seed подключается в E03.
4. База знаний (`kb`) и модели MLflow до E10/E07 пусты: init создаёт схему `kb`, регистрацию моделей делает как «no-op, если артефактов нет».
5. Единый образ на сервис с режимами `api|consumer|relay` (раздел 21) — значит у `ml-service`, `core-api`, `doc-service` общий `entrypoint` с переключением режима переменной `SERVICE_MODE`.

---

## E02-09. Python-монорепозиторий (Backend, M) — делать первым

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-09.1 | Корневой `pyproject.toml` с `[tool.uv.workspace]` (members: `services/*`, `libs/*`), фиксация Python 3.12 (`.python-version`, `requires-python`) | S | `uv sync` проходит с нуля |
| E02-09.2 | `pyproject.toml` на сервисы `core-api`, `ml-service`, `doc-service`, `bank-sim`, `web`: минимальные зависимости из раздела 21, `[tool.uv.sources]` на `libs/*` | M | `uv sync --all-packages` собирает все пакеты; сервисы не импортируют друг друга |
| E02-09.3 | Пакеты `libs/common` (настройки через `pydantic-settings`, логирование `structlog`, `correlation_id`; заглушки JWT, outbox, идемпотентность), `libs/contracts` (пустой пакет-приёмник генерации из E01-10), `libs/featurebuilder` (каркас) | M | Импорт `libs.common`, `libs.contracts`, `libs.featurebuilder` из сервисов работает |
| E02-09.4 | Конфигурация `ruff` (lint+format), `mypy` (strict для `libs/*`, обычный для сервисов), `pytest` (`asyncio_mode=auto`, маркеры `unit/integration/e2e`) | S | `ruff check`, `mypy`, `pytest` проходят на пустом каркасе |
| E02-09.5 | `.pre-commit-config.yaml` (ruff, ruff-format, mypy, проверка `uv.lock` актуален, trailing whitespace, detect-secrets) | S | `pre-commit run --all-files` зелёный |
| E02-09.6 | Единая точка запуска проверок: `Makefile`/`justfile` (`sync`, `lint`, `type`, `test`, `check`, `up`, `down`), `uv.lock` в репозитории | S | `make check` одной командой |
| E02-09.7 | Файл ADR: выбор `uv`, граница `libs/*` ↔ `services/*`, запись в раздел 21 и журнал ADR 20.3 | S | ADR добавлен |

## E02-01. Структура монорепозитория (Backend, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-01.1 | Создать каталоги: `services/{core-api,ml-service,doc-service,bank-sim}`, `web/`, `config/`, `ml/{generators,training,eval/{recommendation,assistant,models},model_cards}`, `kb/`, `fixtures/{registry,news}/`, `deploy/{compose,observability}/`, `docs/{api,data-model,tests,research}/` (с `.gitkeep`/README) | S | Дерево совпадает с разделом 16 и 21.1 |
| E02-01.2 | Каркас пакета сервиса: `src/<service>/{api,app,domain,adapters}` (слои «API → прикладная логика → домен → адаптеры», раздел 10), `main.py` с `/health`, `tests/` | M | Каждый сервис стартует локально и отвечает `GET /health` |
| E02-01.3 | `README.md` (быстрый старт, карта репозитория, профили Compose), `THIRD_PARTY_NOTICES` (заготовка с таблицей), корневой `.gitignore`, `.dockerignore`, `.editorconfig` | S | README описывает запуск в 3 командах |
| E02-01.4 | Ссылки на контракты: `docs/contracts` как источник, симлинк/скрипт не нужны — путь зафиксировать в README и в `libs/contracts` | S | Нет дубля контрактов |

## E02-10. Базовые образы (Backend, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-10.1 | Общий `deploy/docker/Dockerfile.python` (параметры `SERVICE`): stage builder на `python:3.12-slim` + `uv sync --frozen --no-dev --package <service>`; stage runtime копирует только `.venv` и код | M | Образ собирается из lock-файла, повторная сборка использует кэш слоёв |
| E02-10.2 | Запуск не от root (`USER app`, UID фиксирован), `PYTHONUNBUFFERED`, `HEALTHCHECK` через `python -c`/curl-less проверку | S | `docker run … id` показывает не root |
| E02-10.3 | Entrypoint с `SERVICE_MODE=api\|consumer\|relay` (api → uvicorn; consumer → цикл потребителя; relay → outbox-релей) | M | Один образ запускается в трёх режимах (consumer/relay пока заглушки с логом) |
| E02-10.4 | Зафиксировать теги базовых образов (`python:3.12.x-slim-bookworm`), проверка размера образа (≤ ориентира, записать в README), без `torch` | S | Теги не `latest`; размеры записаны |
| E02-10.5 | Системные зависимости по сервисам: `doc-service` (poppler/tesseract — только S5, пока отложить), `libmagic` для `python-magic`, `librdkafka` через wheel `confluent-kafka` | S | `doc-service` образ содержит `libmagic` |

## E02-11. Каркас web (Frontend, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-11.1 | Приложение FastAPI + Jinja2: `web/src/web/{routes,templates,static,clients}`, клиент core-api на `httpx` (async) с общим `correlation_id` | M | Главная страница рендерится при недоступном core-api (экран ошибки) |
| E02-11.2 | Вендоринг статики в `web/static/vendor/`: HTMX (+ расширение SSE), Alpine.js, Chart.js — с фиксацией версий, лицензий в `THIRD_PARTY_NOTICES`, без CDN | S | В HTML нет внешних URL (проверка grep) |
| E02-11.3 | Базовый layout: `base.html`, адаптивная сетка от 360 px, собственный CSS (токены цветов, типографика, формы, кнопки, карточка, состояния «загрузка/ошибка/пусто») | L | Проверка в ширинах 360 / 768 / 1280 без горизонтального скролла |
| E02-11.4 | HTMX-SSE каркас: шаблон подключения `hx-ext="sse"` к `/api/stream`, обработка разрыва и переподключения, индикатор статуса | M | Тестовая страница получает `ping` с заглушки |
| E02-11.5 | CSRF-слой: токен из `GET /auth/me`, double-submit в заголовке `X-CSRF-Token` для мутирующих запросов, middleware отклоняет без токена, `SameSite`/`HttpOnly` cookie | M | Негативный тест: POST без токена → 403 (RFC 9457 `code`) |
| E02-11.6 | Страницы-заглушки: главная («Опишите задачу»), 404/500, `GET /health` | S | Каркас готов к E04–E06 |
| E02-11.7 | Тесты: `pytest` для маршрутов и CSRF, smoke Playwright (запуск позже, в E16) | S | `pytest web/` зелёный |

## E02-03. Миграции БД (Backend, M)

Принцип: по одной Alembic-среде на сервис, своя схема, свой `alembic_version` в этой схеме; никаких внешних ключей и `SELECT` в чужие схемы.

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-03.1 | Alembic-окружение для каждого сервиса (`core`, `bank`, `ml`, `docs`, `kb`): `env.py` с `version_table_schema`, async-подключение (psycopg 3), отдельные роли БД на сервис с правами только на свою схему | M | `alembic upgrade head` создаёт схему и таблицу версий; роль сервиса не читает чужую схему (тест) |
| E02-03.2 | Расширения: `vector` (pgvector), `pgcrypto`/`uuid-ossp` — отдельная миграция «bootstrap» от суперпользователя в init | S | `CREATE EXTENSION` идемпотентно |
| E02-03.3 | `core`, часть 1 — вход и профиль: `registry_snapshot`, `company`, `applicant_role`, `need`, `recommendation` (неизменяемый снимок) | M | Поля по `domain.schema.json`; `recommendation` без `UPDATE` (триггер или права) |
| E02-03.4 | `core`, часть 2 — заявка: `application`, `application_version`, `status_history`, `document`, `consent`, `decision`, `clarification_request`, `contract` | M | Связи по ER-диаграмме 11.1; `decision` неизменяем |
| E02-03.5 | `core`, часть 3 — ассистент и прочее: `insight`, `chat_session`, `message`, `pending_action`, `escalation`, `feed_item`, `feed_impression`, `outbox`, `processed_events` | M | Таблицы созданы; индексы по `company_id`, `application_id` |
| E02-03.6 | Row-Level Security по `company_id` для клиентских таблиц `core` (политики + `SET LOCAL app.company_id`) и тест изоляции между двумя ИНН | M | Тест: запрос под чужим `company_id` возвращает 0 строк |
| E02-03.7 | `bank`: `account`, `transaction`, `credit_record`, `fraud_flag`, `ground_truth` | S | Индексы по ИНН и дате |
| E02-03.8 | `ml`: `profile_snapshot`, `enriched_transaction`, `recurring_payment`, `forecast`, `cash_gap`, `scoring_log`, `recommendation_log`, `whatif_log`, `outbox`, `processed_events` | M | Миграция применяется на чистой БД |
| E02-03.9 | `docs`: `parse_job`, `extracted_field`, `validation_result`, `outbox`, `processed_events`; `kb`: `article`, `chunk` (вектор + `tsvector`, GIN/HNSW-индексы) | M | Индекс полнотекстового и векторного поиска создан |
| E02-03.10 | Тест миграций: подъём с нуля, `downgrade -1`, повторный `upgrade`; проверка отсутствия межсхемных FK | S | Скрипт `make migrate-test` зелёный |
| E02-03.11 | Первичная ER-диаграмма по схемам в `docs/data-model/` (экспорт из миграций) — основа для DEL-07 | S | Файл в репозитории |

## E02-04. Топики, Schema Registry, outbox, DLQ (Backend, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-04.1 | Скрипт создания топиков из `docs/contracts/events/topics.yaml`: 11 топиков + `<топик>.dlq`, партиции, ключ, `replication=1`, идемпотентно (`confluent-kafka` AdminClient) | M | Повторный запуск не падает; `rpk topic list` показывает 22 топика |
| E02-04.2 | Регистрация JSON Schema (конверт + `data` каждого топика) в Schema Registry Redpanda, совместимость BACKWARD, subject = `<топик>-value` | M | `GET /subjects` содержит 11 subjects; повторная регистрация той же схемы — no-op |
| E02-04.3 | `libs/common/events`: конверт события (`event_id`, `type`, `source`, `time`, `subject`, `schema_version`, `correlation_id`, `data`), валидация `jsonschema` перед публикацией и после чтения | M | Невалидное событие отклоняется (негативный тест) |
| E02-04.4 | Outbox: SQLAlchemy-модель/миксин `outbox` (id, topic, key, payload, created_at, published_at, attempts), функция `emit(session, event)` в той же транзакции, что и изменение | M | Откат транзакции → события нет (тест) |
| E02-04.5 | Релей (`SERVICE_MODE=relay`): `SELECT … FOR UPDATE SKIP LOCKED` пачкой, публикация с `acks=all`, пометка `published_at`, ключ = ключ топика (партиционирование) | L | Событие из outbox появляется в топике; параллельные релеи не дублируют |
| E02-04.6 | Потребитель: базовый класс (`SERVICE_MODE=consumer`), идемпотентность через `processed_events(event_id)` в той же транзакции, что и обработка | M | Повторная доставка того же `event_id` обрабатывается один раз |
| E02-04.7 | Повторы и DLQ: 3 попытки с экспоненциальной задержкой, затем публикация в `<топик>.dlq` с причиной и исходным конвертом | M | Тест с ошибкой в обработчике: 3 попытки → сообщение в DLQ |
| E02-04.8 | Сквозной тест «outbox → Redpanda → consumer → processed_events» на Compose-стенде, пример из `docs/contracts/examples/events/` | M | Тест зелёный для минимум 2 топиков |
| E02-04.9 | Сквозной `correlation_id` (HTTP-заголовок → событие → лог) | S | В логах один `correlation_id` на всей цепочке теста |

## E02-05. Конфиги с версией (Backend + Product, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-05.1 | Загрузчик конфигов в `libs/common/config`: чтение YAML, схема Pydantic на каждый файл, поле `version`, хэш содержимого, ошибка старта при невалидном конфиге | M | Невалидный файл → сервис не стартует с понятным сообщением |
| E02-05.2 | `config/products.yaml`: 6 продуктов (ТЗ 4.3, CAT-01–CAT-05): код, название, параметры сумм/сроков/ставок, ограничения | M | Все 6 продуктов; коды совпадают с перечислением в `domain.schema.json` |
| E02-05.3 | `config/goal_fit.yaml`: матрица «цель × продукт» (оценка соответствия) | S | Покрыты все цели из контракта |
| E02-05.4 | `config/eligibility.yaml`: правила допуска с кодами причин отказа | M | Каждое правило ссылается на существующий reason code |
| E02-05.5 | `config/ranking_weights.yaml`: веса ранжирования (начальные, подбор — S8) и `config/thresholds.yaml`: пороги (SC-06, шансы одобрения, границы грейдов) | S | Сумма весов проверяется схемой |
| E02-05.6 | `config/reason_codes.yaml`: коды и тексты (тексты — Product), связь с кодами из контракта | M | Набор кодов совпадает с `domain.schema.json`; для каждого есть клиентский текст |
| E02-05.7 | `config/okved_groups.yaml`: группы ОКВЭД → отрасль/риск | S | Покрывает отрасли синтетического реестра (E03) |
| E02-05.8 | Тест согласованности: перечисления в конфигах ⊆ контракт; версии конфигов попадают в снимок подбора (поле «версии каталога, правил, весов») | S | `pytest config/` зелёный |

## E02-02. Compose-профиль `core` (Backend, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-02.1 | `deploy/compose/compose.yaml`: сеть, тома, `profiles`, `x-` якоря (общие env, healthcheck, logging); корневой `.env.example` | M | `docker compose config` валиден |
| E02-02.2 | Хранилища: PostgreSQL 16 + pgvector (образ `pgvector/pgvector:pg16`, фиксированный тег), Redis 7, MinIO (+ создание бакетов `documents`, `mlflow`) — с healthcheck | M | Healthy; бакеты создаются init-ом |
| E02-02.3 | Брокер: Redpanda (Kafka API + Schema Registry) и Redpanda Console, режим `dev-container`, ограничение памяти | M | Console открывается, Registry отвечает на `/subjects` |
| E02-02.4 | Сервисы приложения: `core-api` (api + relay + consumer как отдельные контейнеры одного образа), `ml-service` (api + consumer + relay), `doc-service` (consumer + relay), `bank-sim` (api), `web` — зависимости `depends_on: condition: service_healthy / service_completed_successfully` (init) | L | Порядок старта соответствует разделу 16 |
| E02-02.5 | ClamAV (clamd, healthcheck, том для сигнатур; режим без сети — сигнатуры в образе/томе) и MLflow (backend — PostgreSQL, артефакты — MinIO) | M | `clamd PING` → PONG; MLflow UI доступен |
| E02-02.6 | Edge (Nginx): маршруты `/` → web, `/api` → core-api; `proxy_buffering off` и `proxy_read_timeout` для SSE; `limit_req` rate limit; TLS самоподписанный (dev), заголовки безопасности | L | SSE-эндпоинт не буферизуется (проверка curl -N); `/api` и `/` маршрутизируются |
| E02-02.7 | Ollama в профиле `core` (том моделей, healthcheck, предзагрузка — см. E02-07) | S | Контейнер healthy |
| E02-02.8 | `mem_limit` на каждый контейнер; таблица лимитов в README; сумма вместе с LLM ≤ 14 ГБ (замер — день 2) | M | `docker stats` под нагрузкой не превышает лимиты; сумма проверяется скриптом по `compose config` |
| E02-02.9 | Healthcheck на каждый сервис (`/health` с проверкой зависимостей: БД, брокер, Redis) | M | `docker compose ps` — все `healthy` |
| E02-02.10 | Фиксация тегов образов (NFR-20), `.env.example` без секретов (только dev-значения-плейсхолдеры, генерация паролей при первом старте) | S | Нет `latest` в compose (grep) |
| E02-02.11 | Режим по умолчанию: `LLM_PROVIDER=local`, `LLM_MODEL`, `ASSISTANT_ENABLED`, `CHECKING_DELAY_SEC` | S | Переменные описаны в `.env.example` |

## E02-07. Локальная LLM (DS/ML + Backend, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-07.1 | Подтвердить выбор: Qwen2.5-7B-Instruct Q4_K_M (Apache 2.0) vs запасной вариант меньше (например, 3B) — проверка лицензии весов и тега Ollama, запись в `THIRD_PARTY_NOTICES` и ADR | S | Решение с обоснованием в разделе 21/ADR |
| E02-07.2 | Загрузка весов без сети в проверяемой версии: способ поставки (предзагруженный том/`ollama create` из GGUF в репозитории или релизе), скрипт `scripts/pull_models.sh`; эмбеддинги `bge-m3` | M | Чистая машина без интернета поднимает модель из локального артефакта |
| E02-07.3 | Замер на 16 ГБ: резидентная память, время до первого токена, токенов/с, на коротком (потребность) и длинном (объяснение) промптах, с одновременной работой всех сервисов `core` | M | Таблица замеров в `docs/research/llm-benchmark.md` |
| E02-07.4 | Замер качества на выборке для NFR-22 / извлечения потребности (пока 20–30 примеров) и сравнение с запасной моделью; зафиксировать решение | M | Решение принято по данным замера |
| E02-07.5 | `LlmPort` в `libs/common/llm`: протокол (`chat`, `stream`, `embed`), реализация `OpenAiCompatibleLlm` (`openai` SDK → `http://ollama:11434/v1`), таймауты, ретраи, передача `correlation_id`, учёт токенов | M | Юнит-тесты на фейковом сервере; потоковая отдача работает |
| E02-07.6 | Заглушка `FakeLlm` для тестов без модели (детерминированные ответы) и переключатель по `LLM_PROVIDER` (`local`/`fake`); облачные адаптеры не добавляются | S | CI/тесты не требуют Ollama |
| E02-07.7 | Прогрев модели при старте (`keep_alive`), деградация: при недоступной LLM `ASSISTANT_ENABLED=false` не роняет подбор (graceful) | S | Тест: LLM недоступна → `/health` core-api остаётся `ok` с признаком `llm: degraded` |

## E02-06. Единый старт и init-контейнер (Backend, M)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-06.1 | Образ/сценарий `init` (`SERVICE_MODE=init` одного из образов или отдельный `deploy/init`), запускается как `service_completed_successfully`, идемпотентен | M | Повторный `docker compose up` не падает и не дублирует данные |
| E02-06.2 | Шаги init по порядку: ожидание БД/брокера → bootstrap расширений → миграции всех сервисов (E02-03) → бакеты MinIO → топики и схемы (E02-04) | M | Лог init показывает шаги и итог |
| E02-06.3 | Шаг seed: загрузка демо-компаний (минимум DEMO-1…) и синтетического реестра из `fixtures/registry/` (заглушка до E03, механизм — «upsert по ИНН») | M | Идёмпотентный seed; демо-ИНН находится в `core.registry_snapshot` |
| E02-06.4 | Шаг MLflow: создать эксперименты, зарегистрировать модели с алиасом `champion`, если артефакты есть (иначе — предупреждение) | S | Пропуск без ошибки, если моделей ещё нет |
| E02-06.5 | Шаг LLM: проверка наличия модели в Ollama (`/api/tags`) и при необходимости загрузка из локального источника | S | Init сообщает, готова ли LLM |
| E02-06.6 | `.env.example` + скрипт первого запуска (`scripts/bootstrap.sh|ps1`: копирует `.env`, генерирует пароли/JWT-секрет), раздел «Быстрый старт» в README | S | Новый разработчик поднимает стенд по README без правок |
| E02-06.7 | Приёмочный скрипт `scripts/smoke.sh`: ждёт healthy, проверяет `/health` всех сервисов, Registry, MLflow, MinIO, ClamAV, Ollama | M | Скрипт зелёный на чистой машине; время холодного старта записано |

## E02-08. Профили `gpu` и `obs` (Backend, S — после приёмки core)

| ID | Подзадача | Оценка | Готово, когда |
| --- | --- | --- | --- |
| E02-08.1 | Профиль `gpu`: override для Ollama с `deploy.resources.reservations.devices` (nvidia), переменная `LLM_MODEL` для большей модели | S | `docker compose --profile gpu config` валиден; без GPU не мешает `core` |
| E02-08.2 | Профиль `obs`: OTel Collector, Prometheus, Grafana, Loki, Tempo (Phoenix — S9, не в этом эпике) — конфиги в `deploy/observability/`, выключен по умолчанию | M | `--profile obs up` поднимает стек; без профиля контейнеров нет |
| E02-08.3 | Каркас инструментирования: OTel SDK в `libs/common` (трассы, `correlation_id`), `/metrics` через `prometheus-client` | M | Метрики видны в Prometheus |
| E02-08.4 | Сумма `mem_limit` профиля `core` не меняется при включении `obs` (проверка, раздел 16) | S | Описано в README |

---

## Приёмка эпика (проверка «Готово, когда»)

1. Чистая машина, 16 ГБ ОЗУ, без сети: `scripts/bootstrap` → `docker compose --profile core up -d` → `scripts/smoke` зелёный (E02-02, E02-06).
2. Все сервисы `healthy`; миграции применены; 22 топика (11 + DLQ) и 11 схем в Registry (E02-03, E02-04).
3. Локальная LLM отвечает через `LlmPort`; замер памяти и задержек зафиксирован (E02-07).
4. `make check` (ruff, mypy, pytest) и `pre-commit` зелёные; `uv.lock` актуален (E02-09).
5. Отсутствуют внешние URL в web-шаблонах и ключи/секреты в репозитории (E02-11, E02-06).

## Итого по объёму

80 подзадач: ориентир ~1 день для 4 человек при распараллеливании (день 1 плана). Если не укладываемся — срезать по порядку: E02-08 (S), затем E02-07.4, E02-04.9, E02-03.11 переносятся на день 2; E02-02, E02-03, E02-04, E02-06, E02-09, E02-10 (критический путь) не режутся.

## Вопросы разработчику до старта (CLAUDE.md, шаг 2)

Задаются по каждой задаче отдельно через `AskUserQuestion` при взятии в работу. Уже видимые кандидаты:

- E02-06: полный seed делает E03 — достаточно ли в E02 заглушек и 3 демо-компаний вручную?
- E02-07: если Qwen2.5-7B Q4_K_M не укладывается в бюджет памяти вместе с остальным `core` — принимаем 3B как основную или поднимаем планку `mem_limit` выше 14 ГБ (нарушает NFR-01)?
- E02-02: TLS на edge — самоподписанный сертификат достаточен для проверяемой версии?
