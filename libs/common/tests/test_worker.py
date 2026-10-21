import pytest
from cabinet_common.worker import SERVICE_SCHEMAS, load_handlers, schema_for


def test_every_outbox_service_has_a_schema() -> None:
    assert schema_for("core-api") == "core"
    assert schema_for("ml-service") == "ml"
    assert schema_for("doc-service") == "docs"
    assert set(SERVICE_SCHEMAS) == {"core-api", "ml-service", "doc-service", "bank-sim"}


def test_unknown_service_has_no_schema() -> None:
    with pytest.raises(ValueError, match="service"):
        schema_for("service")


def test_no_handlers_by_default() -> None:
    assert load_handlers(None) == {}
    assert load_handlers("") == {}


def test_handlers_are_loaded_from_module_attribute() -> None:
    handlers = load_handlers("cabinet_common.worker:SERVICE_SCHEMAS")
    assert handlers["core-api"] == "core"  # type: ignore[comparison-overlap]


def test_handlers_spec_needs_attribute() -> None:
    with pytest.raises(ValueError, match="модуль:имя"):
        load_handlers("cabinet_common.worker")
