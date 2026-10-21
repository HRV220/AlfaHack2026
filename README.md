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

## Источники правды

Бизнес-требования кейса → `docs/contracts/` → ТЗ → архитектура (порядок и правила работы — `CLAUDE.md`, задачи — `docs/BACKLOG.md`).
