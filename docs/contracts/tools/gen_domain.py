"""Генерирует contracts/schemas/domain.schema.json — общие схемы для API и событий."""
import json, os, sys

OUT = sys.argv[1]
ref = lambda name: {"$ref": f"#/$defs/{name}"}
def obj(props, required=None, desc=None, extra=False):
    o = {"type": "object", "properties": props, "additionalProperties": extra}
    if required:
        o["required"] = required
    if desc:
        o["description"] = desc
    return o
def enum(values, desc):
    return {"type": "string", "enum": values, "description": desc}
def arr(items, desc=None, **kw):
    a = {"type": "array", "items": items}
    if desc:
        a["description"] = desc
    a.update(kw)
    return a
def nullable(s):
    return {"anyOf": [s, {"type": "null"}]}
S = lambda desc=None, **kw: dict({"type": "string"}, **({"description": desc} if desc else {}), **kw)
I = lambda desc=None, **kw: dict({"type": "integer"}, **({"description": desc} if desc else {}), **kw)
N = lambda desc=None, **kw: dict({"type": "number"}, **({"description": desc} if desc else {}), **kw)
B = lambda desc=None: dict({"type": "boolean"}, **({"description": desc} if desc else {}))

D = {}

# ---------- примитивы ----------
D["Uuid"] = S("Идентификатор UUID v4", format="uuid")
D["Inn"] = S("ИНН: 10 цифр — юрлицо, 12 — ИП", pattern="^([0-9]{10}|[0-9]{12})$")
D["Money"] = N("Сумма в рублях; округление до копеек (2 знака) выполняет отправитель", minimum=0)
D["SignedMoney"] = N("Сумма в рублях со знаком (остаток может быть отрицательным); 2 знака после запятой")
D["Rate"] = N("Годовая ставка долей: 0.18 = 18%", minimum=0, maximum=1)
D["Probability"] = N("Вероятность от 0 до 1", minimum=0, maximum=1)
D["DateTime"] = S("Дата и время ISO 8601 с часовым поясом", format="date-time")
D["Date"] = S("Дата ISO 8601", format="date")
D["Month"] = S("Месяц YYYY-MM", pattern="^[0-9]{4}-(0[1-9]|1[0-2])$")
D["Version"] = S("Версия артефакта: конфигурации, модели, промпта", minLength=1, maxLength=64)

# ---------- перечисления (ТЗ 4.1) ----------
D["Opf"] = enum(["IP", "LLC"], "ОПФ: IP — индивидуальный предприниматель, LLC — ООО (PRF-01)")
D["IndustryGroup"] = enum([f"G{i:02d}" for i in range(1, 13)], "Отраслевая группа по таблице «ОКВЭД → группа» (ТЗ, раздел 7)")
D["RegistryStatus"] = enum(["ACTIVE", "LIQUIDATING", "LIQUIDATED", "BANKRUPT", "REORGANIZING"],
                           "Статус по реестру: действующая, ликвидируется, ликвидирована, банкротство, реорганизация (PRF-04)")
D["RegistryOrigin"] = enum(["DADATA", "FIXTURE", "SYNTHETIC"],
                           "Откуда реквизиты (REG-06): DADATA — ответ DaData (в том числе из кэша), FIXTURE — сохранённый ответ из репозитория, SYNTHETIC — реестр недоступен")
D["FieldSource"] = enum(["EGRUL", "BANK_DEMO", "DOCUMENT", "FORECAST", "CLIENT", "DEFAULT", "SYSTEM"],
                        "Источник значения (REG-08): EGRUL — реестр; BANK_DEMO — демо-данные банка; DOCUMENT — распознанный документ; FORECAST — прогноз; CLIENT — ввод клиента; DEFAULT — значение по умолчанию (допущение); SYSTEM — расчёт системы")
D["Goal"] = enum(["CASH_GAP", "PURCHASE", "SEASONAL", "EQUIPMENT", "RENOVATION", "CONTRACT", "OTHER"],
                 "Цель: кассовый разрыв; закупка товара или сырья; сезонная подготовка; оборудование и транспорт; ремонт и расширение; исполнение контракта; другая бизнес-цель")
D["Urgency"] = enum(["TODAY_TOMORROW", "WITHIN_WEEK", "NOT_URGENT"], "Срочность: сегодня–завтра; в течение недели; не срочно")
D["Priority"] = enum(["NONE", "MIN_PAYMENT", "MIN_OVERPAYMENT", "SPEED", "NO_COLLATERAL"],
                     "Приоритет: не указан; минимальный платёж; минимальная переплата; скорость; без залога")
D["Regularity"] = enum(["ONE_TIME", "RECURRING"], "Регулярность: разовая; повторяющаяся")
D["CollateralKind"] = enum(["EQUIPMENT", "VEHICLE", "REAL_ESTATE", "GUARANTOR"],
                           "Вид обеспечения: оборудование, транспорт, недвижимость, поручитель. Пустой список обеспечения = «нет»")
D["ProductCode"] = enum(["P1", "P2", "P3", "P4", "P5", "P6"],
                        "Продукт: P1 овердрафт, P2 оборотный кредит, P3 кредитная линия, P4 кредит на развитие, P5 кредит под залог, P6 льготный кредит")
D["EligibilityStatus"] = enum(["ADMITTED", "ADMITTED_ADJUSTED", "REJECTED"],
                              "Допуск (REC-01): допущен; допущен с корректировкой; не допущен")
D["Adjustment"] = enum(["AMOUNT_TO_PRODUCT_MAX", "AMOUNT_TO_PRODUCT_MIN", "TERM_TO_PRODUCT_BOUNDS", "GUARANTOR_REQUIRED"],
                       "Корректировка при допуске: сумма приведена к максимуму или минимуму продукта; срок приведён к границам; потребуется поручитель")
D["Chance"] = enum(["HIGH", "MEDIUM", "LOW"], "Шанс одобрения по REC-03")
D["Grade"] = enum(["A", "B", "C", "D"], "Грейд: A < 2%, B 2–5%, C 5–12%, D ≥ 12%")
D["Factor"] = enum(["F1", "F2", "F3", "F4", "F5", "F6"],
                   "Фактор ранжирования (REC-06): F1 соответствие цели, F2 покрытие, F3 комфорт платежа, F4 стоимость, F5 шанс, F6 приоритет")
D["ReasonCode"] = enum([
    "STOP_REGISTRY", "STOP_FRAUD", "STOP_OVERDUE", "STOP_YOUNG",
    "GOAL_MISMATCH", "AGE_BELOW_MIN", "INFLOW_BELOW_MIN", "INFLOW_HISTORY_SHORT", "INDUSTRY_NOT_IN_PROGRAM",
    "COLLATERAL_REQUIRED", "AMOUNT_BELOW_MIN", "CAPACITY_BELOW_MIN",
    "LOW_TURNOVER", "VOLATILE_TURNOVER", "FALLING_TURNOVER", "HIGH_DEBT_LOAD", "PAST_OVERDUE", "LOW_CASH_RESERVE",
    "CUSTOMER_CONCENTRATION", "YOUNG_BUSINESS", "AMOUNT_HIGH_FOR_TURNOVER",
    "AMOUNT_ABOVE_LIMIT", "STATEMENT_NOT_VERIFIED", "INN_MISMATCH"],
    "Код причины из справочника ТЗ, раздел 5.4")
D["ReasonGroup"] = enum(["STOP", "ELIGIBILITY", "PD_FACTOR", "LIMIT", "DOCUMENT"], "Группа кода причины")
D["ApplicationStatus"] = enum(
    ["DRAFT", "SUBMITTED", "DOCUMENTS_PARSING", "CHECKING", "MANUAL_REVIEW", "APPROVED", "APPROVED_REDUCED", "DECLINED", "ACCEPTED"],
    "Статус заявки (ТЗ, раздел 6): черновик, подана, документы распознаются, проверка, доп. проверка, одобрено, одобрено на меньшую сумму, отказ, условия приняты")
D["DecisionOutcome"] = enum(["APPROVED", "APPROVED_REDUCED", "MANUAL_REVIEW", "DECLINED"], "Итог скоринга (SC-04)")
D["DocumentType"] = enum(["D1_OTHER_BANK_STATEMENT", "D2_GUARANTOR_FORM", "D3_FINANCIAL_STATEMENTS", "D4_ESTIMATE_OR_INVOICE", "D5_COLLATERAL_DOCS"],
                         "Тип документа по чек-листу (ТЗ, раздел 4.3)")
D["DocumentStatus"] = enum(["UPLOADED", "CHECKING", "ACCEPTED", "PARSED", "REPLACE_REQUIRED"],
                           "Статус документа (DOC-02): загружен, проверяется, принят (проверка файла пройдена, распознавание не требуется), распознан, требует замены")
D["DocumentRejectReason"] = enum(["TYPE_NOT_ALLOWED", "TOO_LARGE", "INFECTED", "MACRO", "UNREADABLE", "INN_MISMATCH", "BALANCE_MISMATCH", "PERIOD_TOO_SHORT"],
                                 "Причина «требует замены»: недопустимый тип, больше 10 МБ, вирус, макрос, не распознан, чужой ИНН, остатки не сходятся, период < 6 мес.")
D["TxCategory"] = enum(["CUSTOMER_INFLOW", "SUPPLIER_PAYMENT", "TAXES", "SALARY", "RENT", "LOAN_PAYMENT", "LOAN_RECEIVED", "OWN_TRANSFER", "UNDEFINED"],
                       "Категория операции (DOC-05)")
D["Direction"] = enum(["IN", "OUT"], "Направление операции: зачисление или списание")
D["Role"] = enum(["CLIENT", "UNDERWRITER"], "Роль пользователя")
D["ChatStage"] = enum(["NEED", "RECOMMENDATION", "APPLICATION", "WAITING_DECISION", "EXPLANATION"],
                      "Стадия диалога (архитектура 7.4)")
D["ActionType"] = enum(["CREATE_APPLICATION", "FILL_FIELD", "APPLY_WHAT_IF"],
                       "Действие, которое ассистент предлагает и клиент подтверждает кнопкой (РШ-5)")
D["EscalationReason"] = enum(["USER_REQUEST", "COMPLAINT", "NO_DATA", "NON_TARGET", "NO_OPTIONS"],
                             "Причина обращения (AI-07, NEED-07, REC-15)")
D["NeedField"] = enum(["goal", "amount", "term_months", "collateral", "urgency", "priority", "regularity", "comfortable_payment"],
                      "Поле потребности (ТЗ 4.2), порядок = порядок вопросов при равенстве")
D["NeedOrigin"] = enum(["TEXT", "FORM", "FORECAST"], "Откуда потребность: текст клиента, структурированная форма, прогноз разрыва")
D["NeedNext"] = enum(["QUESTION", "READY", "NON_TARGET"], "Что дальше после обработки потребности")
D["RecommendationTrigger"] = enum(["CLIENT", "FORECAST", "PROFILE_UPDATED", "NEED_EDITED"], "Почему выполнен подбор")
D["ErrorCode"] = enum([
    "INN_INVALID", "COMPANY_NOT_FOUND", "UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND", "VALIDATION_ERROR",
    "STATUS_CONFLICT", "IDEMPOTENCY_CONFLICT", "CHECKLIST_INCOMPLETE", "CONSENT_REQUIRED", "CONSENT_CODE_INVALID",
    "FILE_TYPE_NOT_ALLOWED", "FILE_TOO_LARGE", "FILE_INFECTED", "FILE_MACRO", "RATE_LIMITED", "LLM_UNAVAILABLE",
    "FEATURE_DISABLED", "INTERNAL"], "Машинный код ошибки")

# ---------- ошибки ----------
D["Problem"] = obj({
    "type": S("URI типа ошибки: https://errors.smart-credit.local/<code>", format="uri"),
    "title": S("Краткое описание для разработчика"),
    "status": I("HTTP-статус", minimum=400, maximum=599),
    "detail": S("Текст для показа пользователю на русском"),
    "instance": S("Путь запроса"),
    "code": ref("ErrorCode"),
    "errors": arr(obj({"field": S("Путь поля, например term_months"), "message": S("Текст ошибки")}, ["field", "message"]),
                  "Ошибки полей для VALIDATION_ERROR"),
    "correlation_id": S("Идентификатор трассы", pattern="^[0-9a-f]{32}$"),
}, ["type", "title", "status", "code", "correlation_id"], "Ошибка в формате RFC 9457 (application/problem+json)")

# ---------- реестр и профиль ----------
D["CompanyPreview"] = obj({
    "inn": ref("Inn"), "name": S("Краткое наименование с ОПФ"), "opf": ref("Opf"),
    "registry_status": ref("RegistryStatus"), "address": S("Адрес одной строкой"),
    "origin": ref("RegistryOrigin"), "fetched_at": ref("DateTime"),
}, ["inn", "name", "opf", "registry_status", "address", "origin", "fetched_at"], "Предпросмотр компании перед входом (REG-02)")

D["RegistryData"] = obj({
    "inn": ref("Inn"), "kpp": nullable(S(pattern="^[0-9]{9}$")), "ogrn": S(pattern="^([0-9]{13}|[0-9]{15})$"),
    "name": S(), "opf": ref("Opf"), "manager_name": S("Руководитель (ООО) или ФИО ИП"), "address": S(),
    "okved": S("Основной ОКВЭД", pattern="^[0-9]{2}(\\.[0-9]{1,2}){0,2}$"), "industry_group": ref("IndustryGroup"),
    "registry_status": ref("RegistryStatus"), "registered_at": ref("Date"), "liquidated_at": nullable(ref("Date")),
    "origin": ref("RegistryOrigin"), "fetched_at": ref("DateTime"),
}, ["inn", "kpp", "ogrn", "name", "opf", "manager_name", "address", "okved", "industry_group", "registry_status",
    "registered_at", "liquidated_at", "origin", "fetched_at"], "Реквизиты (REG-05)")

D["SourceMark"] = obj({"source": ref("FieldSource"), "as_of": ref("DateTime")}, ["source", "as_of"], "Источник и дата значения")

D["InflowAverages"] = obj({
    "m3": ref("Money"), "m6": ref("Money"), "m12": ref("Money"),
    "bank_m6": ref("Money"), "other_banks_m6": nullable(ref("Money")), "total_m6": ref("Money"),
}, ["m3", "m6", "m12", "bank_m6", "other_banks_m6", "total_m6"],
    "Средние поступления (PRF-05). m3/m6/m12 — по банку; total_m6 = bank_m6 + other_banks_m6")

D["ProfileMetrics"] = obj({
    "business_age_months": I(minimum=0), "inflow_avg": ref("InflowAverages"),
    "seasonality": N("PRF-06", minimum=0), "volatility": N("PRF-07", minimum=0),
    "free_cash_flow_m6": ref("SignedMoney"), "current_loan_payments": ref("Money"),
    "max_overdue_days_12m": I(minimum=0), "months_with_inflow_6m": I(minimum=0, maximum=6),
}, ["business_age_months", "inflow_avg", "seasonality", "volatility", "free_cash_flow_m6",
    "current_loan_payments", "max_overdue_days_12m", "months_with_inflow_6m"], "Показатели профиля PRF-03, PRF-05…PRF-10")

D["GapReason"] = obj({
    "type": enum(["PAYMENT", "INFLOW_DROP"], "Регулярный платёж в окне разрыва или снижение поступлений"),
    "category": nullable(ref("TxCategory")), "counterparty": nullable(S()), "amount": nullable(ref("Money")),
    "date": nullable(ref("Date")), "drop_pct": nullable(N(minimum=0, maximum=100)),
}, ["type", "category", "counterparty", "amount", "date", "drop_pct"], "Причина разрыва (CF-06)")

D["Gap"] = obj({
    "date": ref("Date"), "probability": ref("Probability"), "deficit": ref("Money"),
    "cushion": ref("Money"), "return_date_p50": nullable(ref("Date")),
    "reasons": arr(ref("GapReason"), maxItems=4), "recurring_last_year": B("В том же месяце прошлого года остаток был ниже подушки"),
}, ["date", "probability", "deficit", "cushion", "return_date_p50", "reasons", "recurring_last_year"], "Найденный разрыв (CF-04)")

D["Profile"] = obj({
    "inn": ref("Inn"), "version": ref("Version"), "as_of": ref("DateTime"),
    "registry": ref("RegistryData"), "metrics": ref("ProfileMetrics"),
    "expected_gap": nullable(ref("Gap")),
    "sources": {"type": "object", "additionalProperties": ref("SourceMark"),
                "description": "Источник и дата каждого поля: ключ — путь поля (registry.name, metrics.inflow_avg.m6)"},
    "demo_bank_data": B("Банковские данные синтетические — интерфейс показывает метку «данные банка — демо»"),
}, ["inn", "version", "as_of", "registry", "metrics", "expected_gap", "sources", "demo_bank_data"], "Профиль компании для подбора")

# ---------- потребность ----------
D["Collateral"] = obj({"kind": ref("CollateralKind"), "value": nullable(ref("Money"))}, ["kind", "value"],
                      "Обеспечение; value обязателен для EQUIPMENT, VEHICLE, REAL_ESTATE и равен null для GUARANTOR")
def nf(value_schema, desc):
    return obj({
        "value": value_schema, "confidence": {"type": "number", "enum": [0, 0.5, 1], "description": "NEED-03"},
        "is_default": B("Подставлено значение по умолчанию — показывать «допущение»"),
        "source": ref("FieldSource"), "fragment": nullable(S("Фрагмент текста клиента, из которого взято значение")),
    }, ["value", "confidence", "is_default", "source", "fragment"], desc)
D["NeedFields"] = obj({
    "goal": nf(nullable(ref("Goal")), "Цель; null — не определена, нужен вопрос"),
    "amount": nf(nullable(ref("Money")), "Сумма; null — «не знаю» (NEED-06)"),
    "term_months": nf(I(minimum=1, maximum=120), "Срок, мес."),
    "collateral": nf(arr(ref("Collateral"), maxItems=5), "Обеспечение; пустой список — «нет»"),
    "urgency": nf(ref("Urgency"), "Срочность"),
    "priority": nf(ref("Priority"), "Приоритет"),
    "regularity": nf(ref("Regularity"), "Регулярность"),
    "comfortable_payment": nf(nullable(ref("Money")), "Комфортный платёж; null — не учитывается"),
}, ["goal", "amount", "term_months", "collateral", "urgency", "priority", "regularity", "comfortable_payment"], "8 полей потребности")
D["Need"] = obj({
    "id": ref("Uuid"), "inn": ref("Inn"), "version": I(minimum=1), "origin": ref("NeedOrigin"),
    "text": nullable(S(maxLength=2000)), "fields": ref("NeedFields"),
    "non_target": B("Запрос нецелевой (NEED-07)"), "questions_asked": I(minimum=0, maximum=5),
    "proposed_amount": nullable(obj({"value": ref("Money"), "basis": enum(["GAP_DEFICIT", "BEST_VARIANT_AVAILABLE"], "Откуда сумма")}, ["value", "basis"])),
    "insight_id": nullable(ref("Uuid")), "created_at": ref("DateTime"), "updated_at": ref("DateTime"),
}, ["id", "inn", "version", "origin", "text", "fields", "non_target", "questions_asked", "proposed_amount", "insight_id", "created_at", "updated_at"],
    "Потребность клиента")
D["NeedFieldsInput"] = obj({
    "goal": ref("Goal"), "amount": nullable(ref("Money")), "term_months": I(minimum=1, maximum=120),
    "collateral": arr(ref("Collateral"), maxItems=5), "urgency": ref("Urgency"), "priority": ref("Priority"),
    "regularity": ref("Regularity"), "comfortable_payment": nullable(ref("Money")),
}, None, "Значения полей, введённые клиентом в форме или карточке; отсутствующее поле не меняется")
D["QuestionOption"] = obj({"value": {"description": "Значение поля, которое уйдёт в PATCH /needs/{id}"}, "label": S()}, ["value", "label"])
D["Question"] = obj({
    "id": ref("Uuid"), "field": ref("NeedField"), "text": S("Текст вопроса"),
    "options": arr(ref("QuestionOption"), minItems=2, maxItems=6), "number": I(minimum=1, maximum=5),
}, ["id", "field", "text", "options", "number"], "Уточняющий вопрос (NEED-05)")
D["NeedResult"] = obj({
    "need": ref("Need"), "next": ref("NeedNext"), "question": nullable(ref("Question")),
}, ["need", "next", "question"], "Результат обработки потребности: следующий вопрос, готовность к подбору или нецелевой запрос")

# ---------- каталог ----------
D["Product"] = obj({
    "code": ref("ProductCode"), "name": S(), "amount_min": ref("Money"), "amount_max": ref("Money"),
    "amount_max_rule": nullable(S("Правило максимума, если он зависит от данных (P1: 50% поступлений; P5: 70% залога)")),
    "term_min_months": I(minimum=1), "term_max_months": I(minimum=1), "base_rate": ref("Rate"),
    "grade_surcharge_applies": B("Применяется ли надбавка грейда (у P6 — нет)"), "commission_pct": N(minimum=0, maximum=1),
    "deferral_months": I(minimum=0), "collateral_rule": S("Требование к обеспечению текстом для клиента"),
    "eligibility_rule": S("Условия допуска текстом для клиента"), "fast": B("Быстрое оформление (F6, приоритет «скорость»)"),
    "catalog_version": ref("Version"),
}, ["code", "name", "amount_min", "amount_max", "amount_max_rule", "term_min_months", "term_max_months", "base_rate",
    "grade_surcharge_applies", "commission_pct", "deferral_months", "collateral_rule", "eligibility_rule", "fast", "catalog_version"],
    "Продукт каталога (CAT-01)")
D["ReasonCodeEntry"] = obj({"code": ref("ReasonCode"), "group": ref("ReasonGroup"), "client_text": S(), "version": ref("Version")},
                           ["code", "group", "client_text", "version"], "Текст кода причины для клиента")

# ---------- подбор ----------
D["ShapItem"] = obj({"feature": S("Имя признака"), "value": {"description": "Значение признака"}, "shap": N("Вклад в PD (лог-шансы)"),
                     "reason_code": nullable(ref("ReasonCode"))}, ["feature", "value", "shap", "reason_code"])
D["FactorScores"] = obj({f: N(minimum=0, maximum=1) for f in ["F1", "F2", "F3", "F4", "F5", "F6"]},
                        ["F1", "F2", "F3", "F4", "F5", "F6"], "Значения или вклады факторов")
D["Variant"] = obj({
    "product_code": ref("ProductCode"), "product_name": S(),
    "amount_needed": nullable(ref("Money")), "amount_available": ref("Money"), "capacity_limit": ref("Money"),
    "term_months": I(minimum=1), "rate": ref("Rate"), "pd": ref("Probability"), "grade": ref("Grade"), "chance": ref("Chance"),
    "payment": ref("Money"), "payment_during_deferral": nullable(ref("Money")), "overpayment": ref("Money"),
    "commission": ref("Money"), "deferral_months": I(minimum=0),
    "guarantor_required": B(), "adjustments": arr(ref("Adjustment")),
    "documents_required": arr(ref("DocumentType")), "documents_recommended": arr(ref("DocumentType")),
    "factors": ref("FactorScores"), "contributions": ref("FactorScores"), "score": N(minimum=0, maximum=1),
    "why_fits": arr(ref("Factor"), maxItems=3, description="3 фактора с наибольшим вкладом (REC-12)"),
    "risk_reason_codes": arr(ref("ReasonCode"), maxItems=3, description="Reason codes топ-3 SHAP, повышающих PD"),
    "shap_top": arr(ref("ShapItem"), maxItems=3), "comfortable_payment_exceeded": B(),
}, ["product_code", "product_name", "amount_needed", "amount_available", "capacity_limit", "term_months", "rate", "pd", "grade",
    "chance", "payment", "payment_during_deferral", "overpayment", "commission", "deferral_months", "guarantor_required",
    "adjustments", "documents_required", "documents_recommended", "factors", "contributions", "score", "why_fits",
    "risk_reason_codes", "shap_top", "comfortable_payment_exceeded"], "Вариант продукта (REC-02…REC-06)")
D["ProductEvaluation"] = obj({
    "product_code": ref("ProductCode"), "eligibility": ref("EligibilityStatus"),
    "reason_codes": arr(ref("ReasonCode"), description="Пусто для ADMITTED и ADMITTED_ADJUSTED"),
    "variant": nullable(ref("Variant")),
}, ["product_code", "eligibility", "reason_codes", "variant"], "Результат допуска и расчёта по одному продукту")
D["ConfigVersions"] = obj({k: ref("Version") for k in ["catalog", "goal_fit", "grades", "weights", "checklist", "reason_codes", "pd_model", "feature_builder", "extraction_prompt"]},
                          ["catalog", "goal_fit", "grades", "weights", "checklist", "reason_codes", "pd_model", "feature_builder", "extraction_prompt"],
                          "Версии артефактов, использованных в расчёте (REC-08)")
D["RecommendationBody"] = obj({
    "inn": ref("Inn"), "need": ref("Need"), "profile_version": ref("Version"),
    "weights_profile": ref("Priority"), "evaluations": arr(ref("ProductEvaluation"), minItems=6, maxItems=6),
    "best_product_code": nullable(ref("ProductCode")),
    "alternative_product_codes": arr(ref("ProductCode"), maxItems=2),
    "proposed_amount": nullable(ref("Money")), "versions": ref("ConfigVersions"), "latency_ms": I(minimum=0),
}, ["inn", "need", "profile_version", "weights_profile", "evaluations", "best_product_code", "alternative_product_codes",
    "proposed_amount", "versions", "latency_ms"], "Результат расчёта подбора — ответ ml-service")
def extend(base, props, required, desc):
    b = D[base]
    return obj(dict(b["properties"], **props), b["required"] + required, desc)
D["Recommendation"] = extend("RecommendationBody", {
    "id": ref("Uuid"), "created_at": ref("DateTime"), "trigger": ref("RecommendationTrigger"),
    "previous_id": nullable(ref("Uuid")),
}, ["id", "created_at", "trigger", "previous_id"], "Снимок подбора (REC-08), неизменяемый: тело от ml-service + поля core-api")
D["FactorDiff"] = obj({"factor": ref("Factor"), "this": N(), "best": N(), "diff": N("this − best по вкладу")},
                      ["factor", "this", "best", "diff"])
D["WhyNot"] = obj({
    "product_code": ref("ProductCode"), "kind": enum(["ELIGIBILITY", "RANKING", "IS_BEST"], "Не допущен; уступил в ранжировании; это и есть лучший"),
    "reason_codes": arr(ref("ReasonCode")), "factor_diffs": arr(ref("FactorDiff")),
    "variant": nullable(ref("Variant")), "best_variant": nullable(ref("Variant")),
}, ["product_code", "kind", "reason_codes", "factor_diffs", "variant", "best_variant"], "Ответ на «почему не X?» (REC-14)")

# ---------- what-if ----------
D["WhatIfChanges"] = obj({
    "amount": nullable(ref("Money")), "term_months": nullable(I(minimum=1, maximum=120)),
    "product_code": nullable(ref("ProductCode")), "repay_loan_ids": arr(ref("Uuid"), maxItems=2),
    "add_collateral": B("Добавить залог из потребности"),
}, ["amount", "term_months", "product_code", "repay_loan_ids", "add_collateral"], "Изменения относительно исходных параметров; null — без изменения")
D["WhatIfOption"] = obj({
    "id": ref("Uuid"), "changes": ref("WhatIfChanges"), "cost": N(minimum=0), "outcome": ref("DecisionOutcome"),
    "requires_review": B("Итог «доп. проверка» — пометка «потребуется проверка сотрудником»"),
    "variant": ref("Variant"),
}, ["id", "changes", "cost", "outcome", "requires_review", "variant"], "Вариант «что сделать» (WI-04)")
D["WhatIfResult"] = obj({
    "base": obj({"product_code": ref("ProductCode"), "amount": ref("Money"), "term_months": I(minimum=1)}, ["product_code", "amount", "term_months"]),
    "options": arr(ref("WhatIfOption"), maxItems=3), "combinations_evaluated": I(minimum=0, maximum=10000),
    "suggest_statement_upload": B("Показать действие «Загрузить выписку другого банка» (WI-08)"), "latency_ms": I(minimum=0),
}, ["base", "options", "combinations_evaluated", "suggest_statement_upload", "latency_ms"], "Результат перебора (WI-02…WI-04)")
D["WhatIfEvaluation"] = obj({"changes": ref("WhatIfChanges"), "outcome": nullable(ref("DecisionOutcome")),
                             "eligibility": ref("EligibilityStatus"), "reason_codes": arr(ref("ReasonCode")),
                             "variant": nullable(ref("Variant")), "latency_ms": I(minimum=0)},
                            ["changes", "outcome", "eligibility", "reason_codes", "variant", "latency_ms"], "Пересчёт одной комбинации (WI-05)")

# ---------- документы ----------
D["StatementTransaction"] = obj({
    "date": ref("Date"), "amount": ref("Money"), "direction": ref("Direction"), "counterparty": S(),
    "counterparty_inn": nullable(ref("Inn")), "purpose": S(), "category": ref("TxCategory"),
    "category_confidence": ref("Probability"),
}, ["date", "amount", "direction", "counterparty", "counterparty_inn", "purpose", "category", "category_confidence"])
D["StatementChecks"] = obj({"balance_ok": B(), "inn_match": B(), "period_months": I(minimum=0), "period_ok": B()},
                           ["balance_ok", "inn_match", "period_months", "period_ok"], "Проверки DOC-04")
D["StatementParseResult"] = obj({
    "doc_kind": {"const": "BANK_STATEMENT"}, "bank_name": S(), "bic": S(pattern="^[0-9]{9}$"), "account": S(pattern="^[0-9]{20}$"),
    "owner_inn": ref("Inn"), "period_from": ref("Date"), "period_to": ref("Date"),
    "opening_balance": ref("SignedMoney"), "closing_balance": ref("SignedMoney"),
    "transactions": arr(ref("StatementTransaction")), "checks": ref("StatementChecks"),
    "field_confidence": {"type": "object", "additionalProperties": ref("Probability")},
    "page_count": I(minimum=1), "used_ocr": B(),
}, ["doc_kind", "bank_name", "bic", "account", "owner_inn", "period_from", "period_to", "opening_balance", "closing_balance",
    "transactions", "checks", "field_confidence", "page_count", "used_ocr"], "Распознанная выписка (DOC-03)")
D["FinancialStatementsResult"] = obj({
    "doc_kind": {"const": "FINANCIAL_STATEMENTS"}, "year": I(minimum=2000, maximum=2100),
    "lines": obj({c: nullable(N()) for c in ["2110", "2400", "1600", "1700", "1500"]}, ["2110", "2400", "1600", "1700", "1500"],
                 "Строки: 2110 выручка, 2400 чистая прибыль, 1600 активы, 1700 пассивы, 1500 краткосрочные обязательства, тыс. ₽"),
    "balance_ok": B("1600 = 1700"), "field_confidence": {"type": "object", "additionalProperties": ref("Probability")},
}, ["doc_kind", "year", "lines", "balance_ok", "field_confidence"], "Распознанная отчётность (DOC-09)")
D["FieldEdit"] = obj({"path": S("Путь поля, например closing_balance или transactions[3].amount"),
                      "original": {"description": "Исходное значение"}, "value": {"description": "Новое значение"},
                      "deviation_pct": nullable(N(minimum=0)), "to_underwriter": B("Передаётся андеррайтеру по DOC-06"),
                      "edited_at": ref("DateTime")}, ["path", "original", "value", "deviation_pct", "to_underwriter", "edited_at"])
D["Document"] = obj({
    "id": ref("Uuid"), "application_id": ref("Uuid"), "type": ref("DocumentType"), "filename": S(),
    "mime": S(), "size_bytes": I(minimum=1, maximum=10485760), "status": ref("DocumentStatus"),
    "reject_reason": nullable(ref("DocumentRejectReason")),
    "parse_result": nullable({"oneOf": [ref("StatementParseResult"), ref("FinancialStatementsResult")]}),
    "edits": arr(ref("FieldEdit")), "uploaded_at": ref("DateTime"), "updated_at": ref("DateTime"),
}, ["id", "application_id", "type", "filename", "mime", "size_bytes", "status", "reject_reason", "parse_result", "edits",
    "uploaded_at", "updated_at"], "Документ заявки")

# ---------- заявка ----------
D["ChecklistItem"] = obj({"document_type": ref("DocumentType"), "required": B(), "recommended": B(),
                          "document_ids": arr(ref("Uuid")), "done": B("Есть документ со статусом ACCEPTED или PARSED")},
                         ["document_type", "required", "recommended", "document_ids", "done"])
D["Consent"] = obj({"given": B(), "given_at": nullable(ref("DateTime"))}, ["given", "given_at"], "Согласие на проверку кредитной истории (APP-03)")
D["Obligation"] = obj({"type": {"const": "REPAY_LOAN"}, "loan_id": ref("Uuid")}, ["type", "loan_id"], "Обязательство клиента из варианта what-if (WI-07)")
D["ApplicationParams"] = obj({
    "product_code": ref("ProductCode"), "amount": ref("Money"), "term_months": I(minimum=1, maximum=120),
    "goal": ref("Goal"), "collateral": arr(ref("Collateral"), maxItems=5), "obligations": arr(ref("Obligation"), maxItems=2),
}, ["product_code", "amount", "term_months", "goal", "collateral", "obligations"], "Параметры кредита в заявке")
D["Application"] = obj({
    "id": ref("Uuid"), "version": I(minimum=1), "status": ref("ApplicationStatus"), "inn": ref("Inn"),
    "recommendation_id": ref("Uuid"), "params": ref("ApplicationParams"),
    "phone": nullable(S(pattern="^\\+7[0-9]{10}$")), "email": nullable(S(format="email")),
    "company": ref("CompanyPreview"),
    "prefilled_fields": arr(enum(["product_code", "amount", "term_months", "goal", "collateral", "phone", "email"], "Поле APP-01"),
                            description="Поля, заполненные автоматически (метрика автозаполнения)"),
    "checklist": arr(ref("ChecklistItem")), "consent": ref("Consent"),
    "status_text": S("Что происходит (таблица статусов ТЗ, раздел 6)"), "next_step_text": S("Что нужно от клиента"),
    "decision_id": nullable(ref("Uuid")), "previous_version_id": nullable(ref("Uuid")),
    "created_at": ref("DateTime"), "updated_at": ref("DateTime"), "submitted_at": nullable(ref("DateTime")),
}, ["id", "version", "status", "inn", "recommendation_id", "params", "phone", "email", "company", "prefilled_fields",
    "checklist", "consent", "status_text", "next_step_text", "decision_id", "previous_version_id", "created_at", "updated_at",
    "submitted_at"], "Заявка")
D["ApplicationPatch"] = obj({
    "amount": ref("Money"), "term_months": I(minimum=1, maximum=120), "goal": ref("Goal"),
    "collateral": arr(ref("Collateral"), maxItems=5), "phone": S(pattern="^\\+7[0-9]{10}$"), "email": S(format="email"),
}, None, "Изменение полей черновика (APP-02, APP-08); продукт меняется только новой версией")

# ---------- решение ----------
D["FeatureValue"] = obj({"name": S(), "value": {"description": "Значение"}, "source": ref("FieldSource")}, ["name", "value", "source"])
D["UnderwriterDecision"] = obj({"decision": enum(["APPROVE", "DECLINE"], "Решение"), "comment": S(minLength=1, maxLength=2000),
                                "user": S(), "at": ref("DateTime")}, ["decision", "comment", "user", "at"])
D["DecisionBody"] = obj({
    "application_id": ref("Uuid"), "application_version": I(minimum=1), "inn": ref("Inn"),
    "outcome": ref("DecisionOutcome"), "stop_reason": nullable(ref("ReasonCode")),
    "pd_raw": nullable(ref("Probability")), "pd": nullable(ref("Probability")), "grade": nullable(ref("Grade")),
    "amount_requested": ref("Money"), "amount_approved": nullable(ref("Money")), "rate": nullable(ref("Rate")),
    "term_months": I(minimum=1), "payment": nullable(ref("Money")),
    "reason_codes": arr(ref("ReasonCode"), maxItems=6), "shap_top10": arr(ref("ShapItem"), maxItems=10),
    "features": arr(ref("FeatureValue")), "review_triggers": arr(enum(["PD_ZONE", "UNVERIFIED_STATEMENT", "CLIENT_EDITS"], "Почему доп. проверка (SC-04)")),
    "recommendation_id": ref("Uuid"), "versions": ref("ConfigVersions"), "decided_at": ref("DateTime"),
}, ["application_id", "application_version", "inn", "outcome", "stop_reason", "pd_raw", "pd", "grade", "amount_requested",
    "amount_approved", "rate", "term_months", "payment", "reason_codes", "shap_top10", "features", "review_triggers",
    "recommendation_id", "versions", "decided_at"], "Снимок решения скоринга (SC-07) — ответ ml-service")
D["Decision"] = extend("DecisionBody", {
    "id": ref("Uuid"), "final_outcome": enum(["APPROVED", "APPROVED_REDUCED", "MANUAL_REVIEW", "DECLINED"], "Итог с учётом решения андеррайтера"),
    "underwriter": nullable(ref("UnderwriterDecision")),
}, ["id", "final_outcome", "underwriter"], "Снимок решения (SC-07) с решением андеррайтера (UW-04)")
D["ClientDecisionView"] = obj({
    "application_id": ref("Uuid"), "status": ref("ApplicationStatus"), "amount_requested": ref("Money"),
    "amount_approved": nullable(ref("Money")), "rate": nullable(ref("Rate")), "term_months": I(minimum=1),
    "payment": nullable(ref("Money")), "reasons": arr(ref("ReasonCodeEntry")),
    "actions": arr(enum(["ACCEPT", "WHAT_IF", "CONTACT_STAFF"], "Доступное действие (APP-06)")), "decided_at": ref("DateTime"),
}, ["application_id", "status", "amount_requested", "amount_approved", "rate", "term_months", "payment", "reasons", "actions", "decided_at"],
    "Решение для клиента: без PD и SHAP")

# ---------- денежный поток ----------
D["CashflowMonth"] = obj({"month": ref("Month"), "inflow": ref("Money"), "outflow": ref("Money"),
                          "by_category": {"type": "object", "propertyNames": ref("TxCategory"), "additionalProperties": ref("Money")}},
                         ["month", "inflow", "outflow", "by_category"])
D["RecurringPayment"] = obj({"counterparty": S(), "category": ref("TxCategory"), "period_days": {"type": "integer", "enum": [7, 14, 30, 90]},
                             "amount": ref("Money"), "next_date": ref("Date")}, ["counterparty", "category", "period_days", "amount", "next_date"])
D["CashflowSummary"] = obj({
    "inn": ref("Inn"), "months": arr(ref("CashflowMonth"), maxItems=12),
    "balance_daily": arr(obj({"date": ref("Date"), "balance": ref("SignedMoney")}, ["date", "balance"])),
    "recurring": arr(ref("RecurringPayment")), "sources": arr(ref("FieldSource")), "as_of": ref("DateTime"),
}, ["inn", "months", "balance_daily", "recurring", "sources", "as_of"], "«Финансовый пульс» (CF-01)")
D["Forecast"] = obj({
    "id": ref("Uuid"), "inn": ref("Inn"), "horizon_days": {"type": "integer", "enum": [30, 60, 90]}, "cushion": ref("Money"),
    "daily": arr(obj({"date": ref("Date"), "p10": ref("SignedMoney"), "p50": ref("SignedMoney"), "p90": ref("SignedMoney")}, ["date", "p10", "p50", "p90"])),
    "model_version": ref("Version"), "generated_at": ref("DateTime"),
}, ["id", "inn", "horizon_days", "cushion", "daily", "model_version", "generated_at"], "Прогноз остатка (CF-03)")
D["Insight"] = obj({
    "id": ref("Uuid"), "inn": ref("Inn"), "gap": ref("Gap"), "days_until": I(minimum=0, maximum=30),
    "recommendation_id": nullable(ref("Uuid")), "status": enum(["NEW", "OPENED", "DISMISSED"], "Реакция клиента"),
    "created_at": ref("DateTime"),
}, ["id", "inn", "gap", "days_until", "recommendation_id", "status", "created_at"], "Карточка разрыва (CF-06)")

# ---------- ассистент, обращения, андеррайтер ----------
D["PendingAction"] = obj({
    "id": ref("Uuid"), "type": ref("ActionType"), "label": S("Подпись кнопки"),
    "payload": {"type": "object", "description": "CREATE_APPLICATION: {recommendation_id}; FILL_FIELD: {application_id, field, value}; APPLY_WHAT_IF: {application_id|recommendation_id, option_id}"},
    "status": enum(["PROPOSED", "CONFIRMED", "EXPIRED"], "Статус"), "expires_at": ref("DateTime"),
}, ["id", "type", "label", "payload", "status", "expires_at"], "Предложенное действие (AI-11)")
D["ChatMessage"] = obj({
    "id": ref("Uuid"), "role": enum(["USER", "ASSISTANT"], "Автор"), "text": S(), "created_at": ref("DateTime"),
    "need_id": nullable(ref("Uuid")), "recommendation_id": nullable(ref("Uuid")), "question_id": nullable(ref("Uuid")),
    "action_ids": arr(ref("Uuid")), "blocked_by_guard": B("Ответ заменён шаблоном (AI-08, AI-09)"),
}, ["id", "role", "text", "created_at", "need_id", "recommendation_id", "question_id", "action_ids", "blocked_by_guard"])
D["ChatSession"] = obj({
    "id": ref("Uuid"), "stage": ref("ChatStage"), "inn": ref("Inn"), "need_id": nullable(ref("Uuid")),
    "recommendation_id": nullable(ref("Uuid")), "application_id": nullable(ref("Uuid")), "insight_id": nullable(ref("Uuid")),
    "messages": arr(ref("ChatMessage")), "assistant_enabled": B("false — LLM отключена (NFR-09)"), "created_at": ref("DateTime"),
}, ["id", "stage", "inn", "need_id", "recommendation_id", "application_id", "insight_id", "messages", "assistant_enabled", "created_at"])
D["Escalation"] = obj({
    "id": ref("Uuid"), "inn": ref("Inn"), "reason": ref("EscalationReason"), "session_id": nullable(ref("Uuid")),
    "application_id": nullable(ref("Uuid")), "summary": S("Резюме для сотрудника без лишних ПДн"),
    "status": enum(["OPEN", "CLOSED"], "Статус"), "created_at": ref("DateTime"), "closed_comment": nullable(S()),
}, ["id", "inn", "reason", "session_id", "application_id", "summary", "status", "created_at", "closed_comment"], "Обращение (AI-07)")
D["Discrepancy"] = obj({
    "type": enum(["CLIENT_EDIT", "UNVERIFIED_STATEMENT", "INFLOW_MISMATCH"], "UW-03"), "document_id": nullable(ref("Uuid")),
    "description": S(), "details": {"type": "object"},
}, ["type", "document_id", "description", "details"])
D["UwQueueItem"] = obj({
    "kind": enum(["APPLICATION", "ESCALATION"], "Тип элемента очереди"), "id": ref("Uuid"), "inn": ref("Inn"),
    "company_name": S(), "title": S("Продукт и сумма или причина обращения"), "since": ref("DateTime"),
}, ["kind", "id", "inn", "company_name", "title", "since"], "Элемент очереди UW-01")
D["UwCard"] = obj({
    "application": ref("Application"), "need": ref("Need"), "recommendation": ref("Recommendation"),
    "decision": ref("Decision"), "profile": ref("Profile"), "forecast": nullable(ref("Forecast")),
    "discrepancies": arr(ref("Discrepancy")), "documents": arr(ref("Document")),
}, ["application", "need", "recommendation", "decision", "profile", "forecast", "discrepancies", "documents"], "Карточка андеррайтера (UW-02)")

# ---------- банк ----------
D["Account"] = obj({"id": ref("Uuid"), "inn": ref("Inn"), "number": S(pattern="^[0-9]{20}$"), "opened_at": ref("Date"),
                    "balance": ref("SignedMoney"), "demo": {"const": True}}, ["id", "inn", "number", "opened_at", "balance", "demo"])
D["BankTransaction"] = obj({
    "id": ref("Uuid"), "account_id": ref("Uuid"), "date": ref("Date"), "amount": ref("Money"), "direction": ref("Direction"),
    "counterparty": S(), "counterparty_inn": nullable(ref("Inn")), "purpose": S(), "balance_after": ref("SignedMoney"),
}, ["id", "account_id", "date", "amount", "direction", "counterparty", "counterparty_inn", "purpose", "balance_after"],
    "Операция по счёту. Категорию определяет ml-service, bank-sim её не отдаёт")
D["Loan"] = obj({
    "id": ref("Uuid"), "inn": ref("Inn"), "lender": S(), "amount": ref("Money"), "monthly_payment": ref("Money"),
    "opened_at": ref("Date"), "closed_at": nullable(ref("Date")), "max_overdue_days": I(minimum=0), "active": B(),
}, ["id", "inn", "lender", "amount", "monthly_payment", "opened_at", "closed_at", "max_overdue_days", "active"], "Кредит в кредитной истории")
D["FraudFlag"] = obj({"inn": ref("Inn"), "flag": B()}, ["inn", "flag"])

doc = {"$schema": "https://json-schema.org/draft/2020-12/schema",
       "$id": "https://contracts.smart-credit.local/schemas/domain.schema.json",
       "title": "Доменные схемы «Умного кредитного кабинета»",
       "description": "Общие схемы для OpenAPI и событий. Источник требований — ТЗ 4.1. Версия контрактов 1.0.0.",
       "$defs": D}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("defs:", len(D))
