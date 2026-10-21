# Умный кредитный кабинет предпринимателя

Прототип для хакатона (кейс Альфа-Банк). Python 3.12, монорепозиторий на `uv`.

## Быстрый старт (разработка)

```bash
uv sync --all-packages   # окружение из uv.lock
make check               # lock-check, ruff, mypy, pytest
uv run pre-commit install
```

Запуск стенда через Docker Compose (`docker compose --profile core up`) появится после задач E02-02 и E02-06.

## Карта репозитория

| Путь | Назначение |
| --- | --- |
| `services/core-api` | вход, подбор (advisor), ассистент, заявки, андеррайтинг, outbox |
| `services/ml-service` | движок подбора, PD-скоринг, what-if, прогноз |
| `services/doc-service` | распознавание документов (воркер) |
| `services/bank-sim` | имитация АБС и витрины РКО |
| `web/` | интерфейс: FastAPI + Jinja2 + HTMX |
| `libs/common`, `libs/contracts`, `libs/featurebuilder` | общий код; сервисы зависят только от `libs/*`, не друг от друга |
| `config/` | версионируемые конфиги подбора (продукты, допуск, веса, коды причин) |
| `ml/` | генераторы данных, обучение, оценка качества, карточки моделей |
| `kb/` | база знаний ассистента |
| `fixtures/{registry,news}/` | синтетический реестр и материалы ленты |
| `deploy/{compose,observability}/` | Docker Compose и стек наблюдаемости |
| `docs/contracts/` | **контракты API и событий — источник правды** (OpenAPI, JSON Schema, генераторы) |
| `docs/{api,data-model,tests,research}/` | описание API, ER-диаграммы, тест-кейсы, исследования |

Структура сервиса: `src/<пакет>/{api,app,domain,adapters}` (слои «API → прикладная логика → домен → адаптеры»), `tests/`, `GET /health`.

## Docker-образы

Один `deploy/docker/Dockerfile.python` на все сервисы (multi-stage: `uv sync --frozen --no-dev --package <service>`, запуск от пользователя `app`, UID 10001). Контекст сборки — корень репозитория. Режим задаёт `SERVICE_MODE` (`api` по умолчанию | `consumer` | `relay`; в двух последних пока заглушка с логом до E02-04).

```bash
docker build -f deploy/docker/Dockerfile.python \
  --build-arg SERVICE=core-api --build-arg APP_MODULE=core_api.main:app -t alfacase/core-api:dev .
```

| Сервис | `SERVICE` | `APP_MODULE` | Доп. параметры |
| --- | --- | --- | --- |
| core-api | `core-api` | `core_api.main:app` | — |
| ml-service | `ml-service` | `ml_service.main:app` | — |
| doc-service | `doc-service` | `doc_service.main:app` | `--build-arg APT_PACKAGES=libmagic1` |
| bank-sim | `bank-sim` | `bank_sim.main:app` | — |
| web | `web` | `cabinet_web.main:app` | — |

Базовый образ — `python:3.12.8-slim-bookworm`, `uv` — `0.13.4` (теги зафиксированы, без `latest`; `torch` в образы не входит). Размеры на 2026-10-21 (`docker images`): core-api 215 МБ, ml-service 215 МБ, doc-service 222 МБ, bank-sim 212 МБ, web 217 МБ. Числовой порог не задан, значения служат базой для сравнения.

## Compose-профиль core

Запуск: `make up` (сборка образов, затем все сервисы профиля `core`), остановка: `make down`. Compose-файл — `deploy/compose/compose.yaml`; пути в нём считаются от корня репозитория, поэтому вызывается с `--project-directory .` (это делает `Makefile`). Без `.env` работают значения по умолчанию; шаблон переменных — `.env.example`. Теги всех образов зафиксированы, `latest` нет (NFR-20).

| Порт на хосте (только 127.0.0.1) | Что |
| --- | --- |
| `8443` (`EDGE_HTTPS_PORT`) | edge: кабинет `/` и API `/api/`, самоподписанный сертификат (dev) |
| `8081` (`CONSOLE_PORT`) | Redpanda Console |
| `5000` (`MLFLOW_PORT`) | MLflow |

Порядок старта: хранилища и брокер → `init` (пока заглушка, наполняется в E02-03, E02-04, E02-06) → `ml-service`, `bank-sim` → `core-api` → `web` → `edge`. Прикладные сервисы не зависят от Ollama: при недоступной локальной LLM подбор работает через форму. Образы: MinIO — `bitnamilegacy/minio` (ADR 23), MLflow собирается из `deploy/docker/Dockerfile.mlflow`, Ollama весит около 4,9 ГБ (модель в образ не входит, загрузка — E02-07).

### Лимиты памяти

Сумма лимитов постоянно работающих контейнеров вместе с локальной LLM не превышает 14 ГиБ (NFR-01, NFR-22); проверка — `python deploy/compose/check_limits.py` (код 1 при нарушении, `--table` печатает таблицу ниже). Замеры `docker stats` в простое на 2026-10-21: ClamAV ~950 МиБ, MLflow ~740–750 МиБ (под нагрузкой до 83% прежнего лимита 896 МиБ, поэтому лимит поднят до 1024 МиБ), Redpanda ~255 МиБ, MinIO ~250 МиБ, Python-сервисы 27–32 МиБ, Ollama без модели ~14–34 МиБ. Лимит Ollama (6 ГиБ) рассчитан на модель Qwen2.5-7B Q4_K_M; замер под нагрузкой — E02-07.

| Контейнер | Лимит, МиБ | Работает постоянно |
| --- | ---: | :---: |
| bank-sim | 128 | да |
| clamav | 1536 | да |
| core-api | 320 | да |
| core-api-consumer | 192 | да |
| core-api-relay | 128 | да |
| doc-service-consumer | 256 | да |
| doc-service-relay | 128 | да |
| edge | 64 | да |
| edge-certs-init | 64 | нет (разовый) |
| init | 128 | нет (разовый) |
| minio | 384 | да |
| minio-init | 128 | нет (разовый) |
| ml-service | 640 | да |
| ml-service-consumer | 256 | да |
| ml-service-relay | 128 | да |
| mlflow | 1024 | да |
| mlflow-db-init | 128 | нет (разовый) |
| ollama | 6144 | да |
| postgres | 640 | да |
| redis | 128 | да |
| redpanda | 1024 | да |
| redpanda-console | 192 | да |
| web | 192 | да |
| **Итого (постоянные)** | **13504** (13.19 ГиБ) | |


## Источники правды

Бизнес-требования кейса → `docs/contracts/` → ТЗ → архитектура (порядок и правила работы — `CLAUDE.md`, задачи — `docs/BACKLOG.md`).
