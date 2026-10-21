import json
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError, load_config
from cabinet_common.config.products import PRODUCT_CODES, ProductsConfig

ROOT = Path(__file__).resolve().parents[3]
PRODUCTS = ROOT / "config" / "products.yaml"
DOMAIN = json.loads(
    (ROOT / "docs/contracts/schemas/domain.schema.json").read_text(encoding="utf-8")
)
MACHINE_ONLY = {"deferral_min_term_months", "security"}


def test_loads_six_products() -> None:
    loaded = load_config(PRODUCTS, ProductsConfig)
    assert [p.code for p in loaded.data.products] == list(PRODUCT_CODES)
    assert loaded.version


def test_codes_match_contract_enum() -> None:
    assert list(PRODUCT_CODES) == DOMAIN["$defs"]["ProductCode"]["enum"]


def test_fields_match_contract_product() -> None:
    contract = set(DOMAIN["$defs"]["Product"]["properties"]) - {"catalog_version"}
    first = load_config(PRODUCTS, ProductsConfig).data.products[0]
    assert set(first.model_dump()) - MACHINE_ONLY == contract


def test_values_from_tz_table() -> None:
    by_code = {p.code: p for p in load_config(PRODUCTS, ProductsConfig).data.products}
    assert by_code["P3"].commission_pct == 0.005
    assert by_code["P3"].base_rate == 0.175
    assert by_code["P4"].deferral_months == 3
    assert not by_code["P6"].grade_surcharge_applies
    assert by_code["P5"].security.required == "collateral"
    assert by_code["P2"].security.amount_over == 3_000_000
    assert by_code["P4"].security.amount_from == 5_000_000
    assert {c for c, p in by_code.items() if p.fast} == {"P1", "P2"}


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    text = PRODUCTS.read_bytes().decode("utf-8")
    assert old in text
    file = tmp_path / "products.yaml"
    file.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    return file


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ("code: P6", "code: P7", "P7"),
        ("amount_min: 100000\n", "amount_min: 99000000\n", "amount_min больше amount_max"),
        ("base_rate: 0.17\n", "base_rate: 17\n", "base_rate"),
        ("deferral_min_term_months: 24", "deferral_min_term_months: 0", "deferral_months"),
        ("security: {required: none}", "security: {required: none, amount_over: 1}", "порог"),
        ("amount_from: 5000000", "amount_from: 5000000\n      amount_over: 1", "взаимоисключающие"),
        ("security: {required: guarantor}", "security: {required: guarantor, x: 1}", "x"),
    ],
)
def test_broken_catalog_rejected(tmp_path: Path, old: str, new: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_config(_broken(tmp_path, old, new), ProductsConfig)


def test_term_range_inverted_rejected(tmp_path: Path) -> None:
    file = _broken(tmp_path, "term_min_months: 3\n", "term_min_months: 30\n")
    with pytest.raises(ConfigError, match="term_min_months больше"):
        load_config(file, ProductsConfig)


def test_missing_product_rejected(tmp_path: Path) -> None:
    text = PRODUCTS.read_bytes().decode("utf-8")
    file = tmp_path / "products.yaml"
    file.write_bytes(text[: text.index("  - code: P6")].encode("utf-8"))
    with pytest.raises(ConfigError, match="ожидались продукты"):
        load_config(file, ProductsConfig)
