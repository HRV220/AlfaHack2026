"""Базовые настройки сервисов: переменные окружения без значений по умолчанию для секретов."""

from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceMode(StrEnum):
    API = "api"
    CONSUMER = "consumer"
    RELAY = "relay"


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "service"
    service_mode: ServiceMode = ServiceMode.API
    log_level: str = "INFO"
    kafka_bootstrap_servers: str = "redpanda:9092"
    schema_registry_url: str = "http://redpanda:8081"
    event_handlers: str | None = None  # 'модуль:имя' словаря «топик → обработчик» для consumer
