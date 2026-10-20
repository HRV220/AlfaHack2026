import json

import pytest
from cabinet_common.logging import configure_logging, correlation_id


def test_correlation_id_in_log(capsys: pytest.CaptureFixture[str]) -> None:
    import structlog

    configure_logging("INFO")
    structlog.configure(
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
        processors=structlog.get_config()["processors"],
    )
    correlation_id.set("abc-1")
    structlog.get_logger().info("hello")
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["correlation_id"] == "abc-1"
