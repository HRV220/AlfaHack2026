"""Настройки web: адрес core-api и таймауты (переменные окружения)."""

from cabinet_common.settings import BaseServiceSettings


class WebSettings(BaseServiceSettings):
    service_name: str = "web"
    # Базовый адрес core-api внутри сети Compose; префикс `/api/v1` задаёт контракт.
    core_api_url: str = "http://core-api:8000"
    core_api_timeout_sec: float = 5.0
    csrf_cache_ttl_sec: int = 300
