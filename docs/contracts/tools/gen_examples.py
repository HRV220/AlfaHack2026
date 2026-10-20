"""Примеры по DEMO-1 (DC-1), рассчитанные по формулам ТЗ 4.2 (REC-02…REC-07), и примеры всех событий.
PD — иллюстративные значения (модель ещё не обучена)."""
import json, os, sys, uuid

ROOT = sys.argv[1]
EX = os.path.join(ROOT, "examples")
os.makedirs(os.path.join(EX, "events"), exist_ok=True)
U = lambda n: str(uuid.uuid5(uuid.NAMESPACE_URL, f"smart-credit/{n}"))
r2 = lambda x: round(x + 1e-9, 2)
INN = "7707083893"
NOW = "2026-10-14T09:00:00+07:00"
VERS = {k: "1.0.0" for k in ["catalog", "goal_fit", "grades", "weights", "checklist", "reason_codes", "pd_model", "feature_builder", "extraction_prompt"]}
TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"

def annuity_payment(p, rate, n):
    r = rate / 12
    return p * r / (1 - (1 + r) ** -n)
def annuity_pv(pay, rate, n):
    r = rate / 12
    return pay * (1 - (1 + r) ** -n) / r

# ---- профиль DC-1 ----
fcf, loan_pay, inflow6 = 1_150_000.0, 80_000.0, 3_500_000.0
allowed_payment = 0.5 * fcf - loan_pay           # REC-04: 495 000
need_amount, need_term = 2_000_000.0, 5          # «к марту» от 14.10.2026 → 01.03.2027 → 138 дн. / 30 → 5 мес.
GRADE_SURCHARGE = {"A": 0.0, "B": 0.02, "C": 0.04}
W = {"F1": .30, "F2": .20, "F3": .15, "F4": .10, "F5": .20, "F6": .05}  # приоритет не указан

def shap(items):
    return [{"feature": f, "value": v, "shap": s, "reason_code": rc} for f, v, s, rc in items]

def variant(code, name, fit, amount_avail, cap, term, base_rate, grade, pd, chance, payment, overpay, commission,
            adjustments, guarantor, docs_req, docs_rec):
    return {"product_code": code, "product_name": name, "amount_needed": need_amount, "amount_available": r2(amount_avail),
            "capacity_limit": r2(cap), "term_months": term, "rate": round(base_rate + GRADE_SURCHARGE[grade], 4), "pd": pd,
            "grade": grade, "chance": chance, "payment": r2(payment), "payment_during_deferral": None,
            "overpayment": r2(overpay), "commission": r2(commission), "deferral_months": 0, "guarantor_required": guarantor,
            "adjustments": adjustments, "documents_required": docs_req, "documents_recommended": docs_rec,
            "_fit": fit}

# P1 овердрафт: лимит = 50% поступлений, срок 12, платёж = S/2 + S*ставка/12, переплата = S*ставка*60/365
p1_avail = min(5_000_000, 0.5 * inflow6, need_amount)
p1 = variant("P1", "Овердрафт", 0.5, p1_avail, 0.5 * inflow6, 12, 0.17, "A", 0.018, "MEDIUM",
             p1_avail / 2 + p1_avail * 0.17 / 12, p1_avail * 0.17 * 60 / 365, 0, ["AMOUNT_TO_PRODUCT_MAX"], False, [], [])
# P2 оборотный: аннуитет 5 мес., 18% (A)
p2_cap = annuity_pv(allowed_payment, 0.18, 5)
p2_pay = annuity_payment(need_amount, 0.18, 5)
p2 = variant("P2", "Оборотный кредит", 1.0, need_amount, p2_cap, 5, 0.18, "A", 0.016, "HIGH",
             p2_pay, p2_pay * 5 - need_amount, 0, [], False, [], ["D1_OTHER_BANK_STATEMENT"])
# P3 кредитная линия: срок приведён к 12, 17,5% (A) + комиссия 0,5%, поручитель
p3_cap = annuity_pv(allowed_payment, 0.175, 12)
p3_pay = annuity_payment(need_amount, 0.175, 12)
p3 = variant("P3", "Кредитная линия", 0.8, need_amount, p3_cap, 12, 0.175, "A", 0.019, "HIGH",
             p3_pay, p3_pay * 12 - need_amount + 0.005 * need_amount, 0.005 * need_amount,
             ["TERM_TO_PRODUCT_BOUNDS", "GUARANTOR_REQUIRED"], True, ["D2_GUARANTOR_FORM", "D3_FINANCIAL_STATEMENTS"], ["D1_OTHER_BANK_STATEMENT"])

vs = [p1, p2, p3]
max_over = max(v["overpayment"] for v in vs)
chance_score = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.2}
for v in vs:
    f = {"F1": v.pop("_fit"), "F2": min(1, v["amount_available"] / need_amount), "F3": max(0, 1 - v["payment"] / fcf),
         "F4": 1 - v["overpayment"] / max_over, "F5": chance_score[v["chance"]], "F6": 0.0}
    v["factors"] = {k: round(x, 4) for k, x in f.items()}
    v["contributions"] = {k: round(W[k] * x, 4) for k, x in f.items()}
    v["score"] = round(sum(v["contributions"].values()), 4)
    v["why_fits"] = [k for k, _ in sorted(v["contributions"].items(), key=lambda kv: -kv[1])[:3]]
    v["shap_top"] = shap([("debt_load", 0.023, 0.11, "HIGH_DEBT_LOAD"), ("inflow_volatility", 0.22, 0.05, "VOLATILE_TURNOVER"),
                          ("amount_to_inflow", round(v["amount_available"] / inflow6, 3), 0.04, "AMOUNT_HIGH_FOR_TURNOVER")])
    v["risk_reason_codes"] = ["HIGH_DEBT_LOAD", "VOLATILE_TURNOVER", "AMOUNT_HIGH_FOR_TURNOVER"]
    v["comfortable_payment_exceeded"] = False
ranked = sorted(vs, key=lambda v: (-v["score"], v["overpayment"], v["product_code"]))
best = ranked[0]
alts = [v["product_code"] for v in ranked[1:] if v["score"] >= 0.7 * best["score"]][:2]
assert best["product_code"] == "P2", [(v["product_code"], v["score"]) for v in ranked]

byc = {v["product_code"]: v for v in vs}
evaluations = [
    {"product_code": "P1", "eligibility": "ADMITTED_ADJUSTED", "reason_codes": [], "variant": byc["P1"]},
    {"product_code": "P2", "eligibility": "ADMITTED", "reason_codes": [], "variant": byc["P2"]},
    {"product_code": "P3", "eligibility": "ADMITTED_ADJUSTED", "reason_codes": [], "variant": byc["P3"]},
    {"product_code": "P4", "eligibility": "REJECTED", "reason_codes": ["GOAL_MISMATCH"], "variant": None},
    {"product_code": "P5", "eligibility": "REJECTED", "reason_codes": ["COLLATERAL_REQUIRED"], "variant": None},
    {"product_code": "P6", "eligibility": "REJECTED", "reason_codes": ["INDUSTRY_NOT_IN_PROGRAM"], "variant": None},
]

def nf(value, conf=1, default=False, source="CLIENT", fragment=None):
    return {"value": value, "confidence": conf, "is_default": default, "source": source, "fragment": fragment}
need = {
    "id": U("need"), "inn": INN, "version": 2, "origin": "TEXT",
    "text": "Нужно 2 млн на закупку к новогоднему сезону, верну к марту",
    "fields": {
        "goal": nf("PURCHASE", 1, False, "CLIENT", "на закупку"),
        "amount": nf(2_000_000.0, 1, False, "CLIENT", "2 млн"),
        "term_months": nf(5, 1, False, "CLIENT", "верну к марту"),
        "collateral": nf([], 1, False, "CLIENT", None),
        "urgency": nf("NOT_URGENT", 0, True, "DEFAULT"),
        "priority": nf("NONE", 0, True, "DEFAULT"),
        "regularity": nf("ONE_TIME", 0, True, "DEFAULT"),
        "comfortable_payment": nf(None, 0, True, "DEFAULT"),
    },
    "non_target": False, "questions_asked": 1, "proposed_amount": None, "insight_id": None,
    "created_at": NOW, "updated_at": "2026-10-14T09:00:20+07:00",
}
rec_body = {"inn": INN, "need": need, "profile_version": "fb-1.0:2026-10-14T08:59:00", "weights_profile": "NONE",
            "evaluations": evaluations, "best_product_code": best["product_code"], "alternative_product_codes": alts,
            "proposed_amount": None, "versions": VERS, "latency_ms": 840}
recommendation = dict(rec_body, id=U("rec"), created_at="2026-10-14T09:00:21+07:00", trigger="CLIENT", previous_id=None)

def save(name, obj):
    json.dump(obj, open(os.path.join(EX, name), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
save("recommendation.DEMO-1.json", recommendation)
save("need-result.DEMO-1.json", {"need": dict(need, version=1, questions_asked=0, fields=dict(need["fields"], collateral=nf([], 0, True, "DEFAULT"))),
                                  "next": "QUESTION",
                                  "question": {"id": U("q1"), "field": "collateral", "text": "Есть ли у вас залог?", "number": 1,
                                               "options": [{"value": [], "label": "Нет"},
                                                           {"value": [{"kind": "EQUIPMENT", "value": None}], "label": "Оборудование"},
                                                           {"value": [{"kind": "REAL_ESTATE", "value": None}], "label": "Недвижимость"}]}})

decision_body = {
    "application_id": U("app"), "application_version": 1, "inn": INN, "outcome": "APPROVED", "stop_reason": None,
    "pd_raw": 0.021, "pd": 0.016, "grade": "A", "amount_requested": need_amount, "amount_approved": need_amount,
    "rate": 0.18, "term_months": 5, "payment": r2(p2_pay), "reason_codes": [],
    "shap_top10": byc["P2"]["shap_top"], "features": [
        {"name": "inflow_avg_m6", "value": inflow6, "source": "BANK_DEMO"},
        {"name": "business_age_months", "value": 61, "source": "REGISTRY"},
        {"name": "debt_load", "value": 0.023, "source": "BANK_DEMO"}],
    "review_triggers": [], "recommendation_id": recommendation["id"], "versions": VERS, "decided_at": "2026-10-14T09:03:05+07:00"}
save("decision.DEMO-1.json", dict(decision_body, id=U("dec"), final_outcome="APPROVED", underwriter=None, clarifications=[]))

# ---- события ----
def env(topic, source, subject, data, n):
    e = {"event_id": U(f"evt-{n}"), "type": topic, "source": source, "time": NOW, "subject": subject,
         "schema_version": "1.0.0", "correlation_id": TRACE, "data": data}
    save(f"events/{topic}.example.json", e)
gap = {"date": "2026-10-26", "probability": 0.62, "deficit": 612_400.0, "cushion": 245_000.0, "return_date_p50": "2026-11-09",
       "reasons": [{"type": "PAYMENT", "category": "TAXES", "counterparty": "УФК по г. Москве", "amount": 640_000.0, "date": "2026-10-25", "drop_pct": None},
                   {"type": "PAYMENT", "category": "SALARY", "counterparty": "Сотрудники", "amount": 460_000.0, "date": "2026-10-25", "drop_pct": None}],
       "recurring_last_year": False}
APP = U("app")
env("bank.transactions_updated", "bank-sim", INN, {"inn": INN, "account_ids": [U("acc")], "period_from": "2025-10-14", "period_to": "2026-10-13", "new_count": 2814}, 1)
env("document.uploaded", "core-api", APP, {"document_id": U("doc"), "application_id": APP, "inn": INN, "document_type": "D1_OTHER_BANK_STATEMENT",
    "object_key": f"documents/quarantine/{U('doc')}.pdf", "filename": "vypiska.pdf", "mime_declared": "application/pdf", "size_bytes": 482113, "needs_parsing": True}, 2)
env("document.parsed", "doc-service", APP, {"document_id": U("doc"), "application_id": APP, "inn": INN, "document_type": "D1_OTHER_BANK_STATEMENT",
    "status": "PARSED", "accepted": True, "reject_reason": None, "clean_object_key": f"documents/clean/{U('doc')}.pdf",
    "result": {"doc_kind": "BANK_STATEMENT", "bank_name": "Банк Пример", "bic": "044525000", "account": "40702810900000000001", "owner_inn": INN,
               "period_from": "2026-04-01", "period_to": "2026-09-30", "opening_balance": 310000.0, "closing_balance": 455000.0,
               "transactions": [{"date": "2026-04-03", "amount": 145000.0, "direction": "IN", "counterparty": "ООО Покупатель",
                                 "counterparty_inn": "7701234567", "purpose": "Оплата по счёту 15", "category": "CUSTOMER_INFLOW", "category_confidence": 0.97}],
               "checks": {"balance_ok": True, "inn_match": True, "period_months": 6, "period_ok": True},
               "field_confidence": {"owner_inn": 0.99, "closing_balance": 0.98}, "page_count": 7, "used_ocr": False},
    "latency_ms": 12400}, 3)
env("document.failed", "doc-service", APP, {"document_id": U("doc2"), "application_id": APP, "inn": INN, "reason": "INFECTED", "details": "ClamAV: Eicar-Signature"}, 4)
env("profile.updated", "ml-service", INN, {"inn": INN, "profile_version": "fb-1.0:2026-10-14T09:05:00", "previous_version": "fb-1.0:2026-10-14T08:59:00",
    "cause": "DOCUMENT", "changed": [{"path": "metrics.inflow_avg.other_banks_m6", "before": None, "after": 2000000.0}]}, 5)
env("cashflow.forecast_ready", "ml-service", INN, {"inn": INN, "forecast_id": U("fc"), "horizon_days": 90, "model_version": "forecast-1.0.0", "generated_at": NOW}, 6)
env("cashflow.gap_detected", "ml-service", INN, {"inn": INN, "forecast_id": U("fc"), "gap": gap}, 7)
env("application.submitted", "core-api", APP, {"application_id": APP, "application_version": 1, "inn": INN, "recommendation_id": recommendation["id"],
    "params": {"product_code": "P2", "amount": need_amount, "term_months": 5, "goal": "PURCHASE", "collateral": [], "obligations": []},
    "has_unverified_statement": False, "has_client_edits": False, "pending_document_ids": []}, 8)
env("decision.made", "ml-service", APP, {"decision": decision_body, "latency_ms": 310}, 9)
env("application.status_changed", "core-api", APP, {"application_id": APP, "application_version": 1, "inn": INN, "from": "CHECKING", "to": "APPROVED",
    "at": "2026-10-14T09:03:06+07:00", "actor": "SYSTEM"}, 10)
env("recommendation.made", "core-api", INN, {"recommendation_id": recommendation["id"], "inn": INN, "need_id": need["id"], "trigger": "CLIENT",
    "best_product_code": "P2", "best_chance": "HIGH", "alternative_product_codes": alts, "questions_asked": 1, "latency_ms": 840}, 11)
print("best:", best["product_code"], "scores:", {v["product_code"]: v["score"] for v in vs}, "alts:", alts)
print("P2 payment", r2(p2_pay), "P2 capacity", r2(p2_cap), "P1 avail", p1_avail)
