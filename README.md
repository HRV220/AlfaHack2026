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

## Источники правды

Бизнес-требования кейса → `docs/contracts/` → ТЗ → архитектура (порядок и правила работы — `CLAUDE.md`, задачи — `docs/BACKLOG.md`).
