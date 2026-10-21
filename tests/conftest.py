import asyncio
import sys
from collections.abc import Callable, Mapping

import pytest


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    """Psycopg 3 не работает на ProactorEventLoop (Windows): нужен SelectorEventLoop."""
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
