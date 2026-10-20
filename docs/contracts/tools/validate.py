"""Проверка контрактов: метасхема, все $ref указывают на существующие определения, примеры проходят схемы."""
import json, pathlib, re, sys, yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

root = pathlib.Path(sys.argv[1])
BASE = "https://contracts.smart-credit.local/"
dom = json.load(open(root / "schemas/domain.schema.json"))
defs = set(dom["$defs"])
resources = []
for p in list((root / "schemas").glob("*.json")) + list((root / "events").glob("*.json")) + list((root / "sse").glob("*.json")):
    s = json.load(open(p))
    Draft202012Validator.check_schema(s)
    resources.append((s["$id"], Resource.from_contents(s)))
reg = Registry().with_resources(resources)
print("metaschema ok:", len(resources), "files")

# все ссылки на domain.$defs существуют
bad = []
for p in list(root.rglob("*.json")) + list(root.rglob("*.yaml")):
    for m in re.finditer(r"domain\.schema\.json#/\$defs/([A-Za-z0-9_]+)", p.read_text(encoding="utf-8")):
        if m.group(1) not in defs:
            bad.append((p.name, m.group(1)))
    for m in re.finditer(r"\"\$ref\": \"#/\$defs/([A-Za-z0-9_]+)\"", p.read_text(encoding="utf-8")):
        if p.name == "domain.schema.json" and m.group(1) not in defs:
            bad.append((p.name, m.group(1)))
print("broken refs:", bad or "none")

def check(schema_uri, inst, label):
    v = Draft202012Validator({"$ref": schema_uri}, registry=reg)
    errs = sorted(v.iter_errors(inst), key=lambda e: list(e.path))
    print(("OK  " if not errs else "FAIL"), label)
    for e in errs[:5]:
        print("    ", list(e.path), e.message[:200])
    return not errs

ok = True
topics = yaml.safe_load(open(root / "events/topics.yaml"))["topics"]
for t in topics:
    ex = json.load(open(root / f"examples/events/{t['name']}.example.json"))
    ok &= check(BASE + "events/envelope.schema.json", ex, f"envelope {t['name']}")
    ok &= check(BASE + f"events/{t['schema']}", ex["data"], f"data    {t['name']}")
    assert ex["type"] == t["name"] and ex["source"] == t["producer"]
D = BASE + "schemas/domain.schema.json#/$defs/"
ok &= check(D + "Recommendation", json.load(open(root / "examples/recommendation.DEMO-1.json")), "Recommendation DEMO-1")
ok &= check(D + "NeedResult", json.load(open(root / "examples/need-result.DEMO-1.json")), "NeedResult DEMO-1")
ok &= check(D + "Decision", json.load(open(root / "examples/decision.DEMO-1.json")), "Decision DEMO-1")
# отрицательные проверки: схема должна ловить ошибки
neg = json.load(open(root / "examples/recommendation.DEMO-1.json")); neg["evaluations"][0]["variant"]["chance"] = "VERY_HIGH"
v = Draft202012Validator({"$ref": D + "Recommendation"}, registry=reg); assert list(v.iter_errors(neg)), "negative test 1"
neg2 = json.load(open(root / "examples/events/decision.made.example.json")); neg2["data"]["decision"]["extra"] = 1
v = Draft202012Validator({"$ref": BASE + "events/decision.made.schema.json"}, registry=reg); assert list(v.iter_errors(neg2["data"])), "negative test 2"
print("negative tests ok")
print("ALL OK" if ok else "FAILURES")
sys.exit(0 if ok else 1)
