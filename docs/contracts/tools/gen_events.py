"""Генерирует схемы событий брокера, конверт, топики и события SSE."""
import json, os, sys

ROOT = sys.argv[1]
DOM = "../schemas/domain.schema.json#/$defs/"
d = lambda n: {"$ref": DOM + n}
def obj(props, required, desc=None):
    o = {"type": "object", "properties": props, "required": required, "additionalProperties": False}
    if desc:
        o["description"] = desc
    return o
nullable = lambda s: {"anyOf": [s, {"type": "null"}]}

def write(path, schema):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    json.dump(schema, open(full, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

BASE = "https://contracts.smart-credit.local/"

# ---------- конверт ----------
write("events/envelope.schema.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": BASE + "events/envelope.schema.json",
    "title": "Конверт события",
    "description": "Каждое сообщение в брокере — этот конверт; поле data валидируется схемой топика (events/<type>.schema.json).",
    **obj({
        "event_id": {"type": "string", "format": "uuid", "description": "Уникальный идентификатор; по нему потребитель обеспечивает идемпотентность"},
        "type": {"type": "string", "enum": [
            "bank.transactions_updated", "document.uploaded", "document.parsed", "document.failed", "profile.updated",
            "cashflow.forecast_ready", "cashflow.gap_detected", "application.submitted", "decision.made",
            "application.status_changed", "recommendation.made"], "description": "Совпадает с именем топика"},
        "source": {"type": "string", "enum": ["core-api", "ml-service", "doc-service", "bank-sim"], "description": "Сервис-производитель"},
        "time": {"type": "string", "format": "date-time"},
        "subject": {"type": "string", "description": "Ключ партиционирования: ИНН или application_id (topics.yaml)"},
        "schema_version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
        "correlation_id": {"type": "string", "pattern": "^[0-9a-f]{32}$", "description": "trace id OpenTelemetry"},
        "data": {"type": "object"},
    }, ["event_id", "type", "source", "time", "subject", "schema_version", "correlation_id", "data"])})

def event(name, desc, schema):
    write(f"events/{name}.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE + f"events/{name}.schema.json",
        "title": f"data события {name}", "description": desc, **schema})

event("bank.transactions_updated", "bank-sim → ml-service. Появились операции по счетам компании (первый вход или обновление).", obj({
    "inn": d("Inn"), "account_ids": {"type": "array", "items": d("Uuid"), "minItems": 1},
    "period_from": d("Date"), "period_to": d("Date"), "new_count": {"type": "integer", "minimum": 0},
}, ["inn", "account_ids", "period_from", "period_to", "new_count"]))

event("document.uploaded", "core-api → doc-service. Файл сохранён в карантин MinIO.", obj({
    "document_id": d("Uuid"), "application_id": d("Uuid"), "inn": d("Inn"), "document_type": d("DocumentType"),
    "object_key": {"type": "string", "pattern": "^documents/quarantine/"}, "filename": {"type": "string"},
    "mime_declared": {"type": "string"}, "size_bytes": {"type": "integer", "minimum": 1, "maximum": 10485760},
    "needs_parsing": {"type": "boolean", "description": "true для D1 (S2) и D3 (S6); иначе только проверка файла"},
}, ["document_id", "application_id", "inn", "document_type", "object_key", "filename", "mime_declared", "size_bytes", "needs_parsing"]))

event("document.parsed", "doc-service → core-api, ml-service. Файл прошёл проверку; для D1/D3 — распознан. accepted=false — не прошёл DOC-04 и не учитывается в профиле.", obj({
    "document_id": d("Uuid"), "application_id": d("Uuid"), "inn": d("Inn"), "document_type": d("DocumentType"),
    "status": {"type": "string", "enum": ["ACCEPTED", "PARSED", "REPLACE_REQUIRED"]},
    "accepted": {"type": "boolean"}, "reject_reason": nullable(d("DocumentRejectReason")),
    "clean_object_key": {"type": "string", "pattern": "^documents/clean/"},
    "result": nullable({"oneOf": [d("StatementParseResult"), d("FinancialStatementsResult")]}),
    "latency_ms": {"type": "integer", "minimum": 0},
}, ["document_id", "application_id", "inn", "document_type", "status", "accepted", "reject_reason", "clean_object_key", "result", "latency_ms"]))

event("document.failed", "doc-service → core-api. Файл отклонён проверкой DOC-01 или не распознан технически.", obj({
    "document_id": d("Uuid"), "application_id": d("Uuid"), "inn": d("Inn"),
    "reason": {"type": "string", "enum": ["TYPE_NOT_ALLOWED", "TOO_LARGE", "INFECTED", "MACRO", "UNREADABLE"]},
    "details": {"type": "string"},
}, ["document_id", "application_id", "inn", "reason", "details"]))

event("profile.updated", "ml-service → core-api. Профиль пересчитан; core-api пересчитывает активный подбор (REC-10).", obj({
    "inn": d("Inn"), "profile_version": d("Version"), "previous_version": nullable(d("Version")),
    "cause": {"type": "string", "enum": ["BANK_DATA", "DOCUMENT", "FORECAST"]},
    "changed": {"type": "array", "items": obj({"path": {"type": "string"}, "before": {}, "after": {}}, ["path", "before", "after"])},
}, ["inn", "profile_version", "previous_version", "cause", "changed"]))

event("cashflow.forecast_ready", "ml-service → core-api. Готов прогноз остатка (CF-03).", obj({
    "inn": d("Inn"), "forecast_id": d("Uuid"), "horizon_days": {"type": "integer", "const": 90},
    "model_version": d("Version"), "generated_at": d("DateTime"),
}, ["inn", "forecast_id", "horizon_days", "model_version", "generated_at"]))

event("cashflow.gap_detected", "ml-service → core-api. Найден разрыв в ближайшие 30 дней (CF-04); core-api формирует потребность по CF-05 и карточку CF-06.", obj({
    "inn": d("Inn"), "forecast_id": d("Uuid"), "gap": d("Gap"),
}, ["inn", "forecast_id", "gap"]))

event("application.submitted", "core-api → ml-service. Заявка подана; ml-service считает решение (SC-01…SC-07).", obj({
    "application_id": d("Uuid"), "application_version": {"type": "integer", "minimum": 1}, "inn": d("Inn"),
    "recommendation_id": d("Uuid"), "params": d("ApplicationParams"),
    "has_unverified_statement": {"type": "boolean"}, "has_client_edits": {"type": "boolean"},
    "pending_document_ids": {"type": "array", "items": d("Uuid"), "description": "Выписки, ещё не распознанные; скоринг ждёт их document.parsed"},
}, ["application_id", "application_version", "inn", "recommendation_id", "params", "has_unverified_statement", "has_client_edits", "pending_document_ids"]))

event("decision.made", "ml-service → core-api. Решение скоринга со снимком (SC-07).", obj({
    "decision": d("DecisionBody"), "latency_ms": {"type": "integer", "minimum": 0},
}, ["decision", "latency_ms"]))

event("application.status_changed", "core-api → аналитика. Переход статуса заявки (для TTD и воронки).", obj({
    "application_id": d("Uuid"), "application_version": {"type": "integer", "minimum": 1}, "inn": d("Inn"),
    "from": nullable(d("ApplicationStatus")), "to": d("ApplicationStatus"), "at": d("DateTime"),
    "actor": {"type": "string", "enum": ["CLIENT", "SYSTEM", "UNDERWRITER"]},
}, ["application_id", "application_version", "inn", "from", "to", "at", "actor"]))

event("recommendation.made", "core-api → аналитика. Сохранён снимок подбора (метрики Q и воронка).", obj({
    "recommendation_id": d("Uuid"), "inn": d("Inn"), "need_id": d("Uuid"), "trigger": d("RecommendationTrigger"),
    "best_product_code": nullable(d("ProductCode")), "best_chance": nullable(d("Chance")),
    "alternative_product_codes": {"type": "array", "items": d("ProductCode"), "maxItems": 2},
    "questions_asked": {"type": "integer", "minimum": 0, "maximum": 5}, "latency_ms": {"type": "integer", "minimum": 0},
}, ["recommendation_id", "inn", "need_id", "trigger", "best_product_code", "best_chance", "alternative_product_codes", "questions_asked", "latency_ms"]))

# ---------- SSE ----------
def sse_set(name, title, events):
    write(f"sse/{name}.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": BASE + f"sse/{name}.schema.json",
        "title": title,
        "description": "Каждое SSE-сообщение: строка `event: <имя>` и строка `data: <JSON>`. Ниже — схема пары {event, data}.",
        "oneOf": [obj({"event": {"const": e}, "data": s}, ["event", "data"], desc) for e, desc, s in events]})

sse_set("chat-events", "События SSE ответа ассистента (POST /chat/sessions/{id}/messages)", [
    ("delta", "Очередное проверенное предложение текста", obj({"message_id": d("Uuid"), "text": {"type": "string"}}, ["message_id", "text"])),
    ("tool", "Выполняется инструмент — для индикатора «смотрю прогноз…»", obj({"name": {"type": "string"}, "status": {"type": "string", "enum": ["STARTED", "FINISHED"]}}, ["name", "status"])),
    ("need", "Карточка понятой потребности (NEED-04)", obj({"need": d("Need")}, ["need"])),
    ("question", "Уточняющий вопрос с кнопками (NEED-05)", obj({"question": d("Question")}, ["question"])),
    ("recommendation", "Готов подбор — карточку и сравнение рисовать из GET /recommendations/{id}", obj({"recommendation_id": d("Uuid"), "best_product_code": nullable(d("ProductCode"))}, ["recommendation_id", "best_product_code"])),
    ("action", "Карточка действия (AI-11)", obj({"action": d("PendingAction")}, ["action"])),
    ("escalation", "Создано обращение (AI-07)", obj({"escalation": d("Escalation")}, ["escalation"])),
    ("done", "Конец ответа", obj({"message_id": d("Uuid"), "stage": d("ChatStage")}, ["message_id", "stage"])),
    ("error", "Ошибка; text — безопасный текст для клиента", obj({"code": d("ErrorCode"), "text": {"type": "string"}}, ["code", "text"])),
])
sse_set("stream-events", "События общего потока GET /events/stream", [
    ("application.status", "Статус заявки изменился (APP-05)", obj({"application_id": d("Uuid"), "status": d("ApplicationStatus"), "status_text": {"type": "string"}, "next_step_text": {"type": "string"}}, ["application_id", "status", "status_text", "next_step_text"])),
    ("insight.created", "Новая карточка разрыва (CF-06)", obj({"insight": d("Insight")}, ["insight"])),
    ("document.status", "Статус документа (DOC-02)", obj({"document_id": d("Uuid"), "application_id": d("Uuid"), "status": d("DocumentStatus"), "reject_reason": nullable(d("DocumentRejectReason"))}, ["document_id", "application_id", "status", "reject_reason"])),
    ("recommendation.updated", "Подбор пересчитан после новых данных (REC-10, DOC-08)", obj({
        "recommendation_id": d("Uuid"), "previous_id": d("Uuid"),
        "changes": {"type": "array", "items": obj({"field": {"type": "string", "description": "best_product_code, amount_available, chance"}, "before": {}, "after": {}}, ["field", "before", "after"])},
        "message": {"type": "string", "description": "Текст для клиента: «Доступная сумма выросла с X до Y ₽»"}}, ["recommendation_id", "previous_id", "changes", "message"])),
    ("clarification.requested", "Сотрудник запросил уточнение по заявке (UW-05)", obj({"application_id": d("Uuid"), "clarification": d("ClarificationRequest")}, ["application_id", "clarification"])),
    ("feed.updated", "Лента пересчитана (NEWS-04, S13)", obj({"new_item_ids": {"type": "array", "items": d("Uuid")}, "generated_at": d("DateTime")}, ["new_item_ids", "generated_at"])),
    ("ping", "Поддержание соединения раз в 15 с", obj({"at": d("DateTime")}, ["at"])),
])
print("events ok")
