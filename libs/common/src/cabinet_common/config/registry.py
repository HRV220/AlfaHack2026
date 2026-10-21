"""Все конфиги каталога: загрузка при старте и версии для снимков (REC-08)."""

from dataclasses import dataclass
from pathlib import Path

from cabinet_common.config.eligibility import EligibilityConfig
from cabinet_common.config.goal_fit import GoalFitConfig
from cabinet_common.config.loader import ConfigModel, LoadedConfig, load_config
from cabinet_common.config.okved import OkvedGroupsConfig
from cabinet_common.config.products import ProductsConfig
from cabinet_common.config.ranking import RankingWeightsConfig, ThresholdsConfig
from cabinet_common.config.reason_codes import ReasonCodesConfig


@dataclass(frozen=True)
class ConfigFile:
    name: str
    model: type[ConfigModel]
    versions_key: str | None  # поле `ConfigVersions` контракта; None — в снимок не попадает


CONFIG_FILES = (
    ConfigFile("products.yaml", ProductsConfig, "catalog"),
    ConfigFile("goal_fit.yaml", GoalFitConfig, "goal_fit"),
    ConfigFile("eligibility.yaml", EligibilityConfig, None),
    ConfigFile("ranking_weights.yaml", RankingWeightsConfig, "weights"),
    ConfigFile("thresholds.yaml", ThresholdsConfig, "grades"),
    ConfigFile("reason_codes.yaml", ReasonCodesConfig, "reason_codes"),
    ConfigFile("okved_groups.yaml", OkvedGroupsConfig, None),
)


@dataclass(frozen=True)
class LoadedConfigs:
    products: LoadedConfig[ProductsConfig]
    goal_fit: LoadedConfig[GoalFitConfig]
    eligibility: LoadedConfig[EligibilityConfig]
    ranking_weights: LoadedConfig[RankingWeightsConfig]
    thresholds: LoadedConfig[ThresholdsConfig]
    reason_codes: LoadedConfig[ReasonCodesConfig]
    okved_groups: LoadedConfig[OkvedGroupsConfig]

    def versions(self) -> dict[str, str]:
        """Версии для `ConfigVersions` снимка: ключ контракта → `version` файла."""
        versions: dict[str, str] = {}
        for file in CONFIG_FILES:
            if file.versions_key is not None:
                versions[file.versions_key] = getattr(self, file.name.removesuffix(".yaml")).version
        return versions


def load_all_configs(config_dir: Path | str) -> LoadedConfigs:
    """Читает и проверяет схемами все файлы каталога конфигов; любая ошибка — `ConfigError`."""
    directory = Path(config_dir)
    loaded = {
        file.name.removesuffix(".yaml"): load_config(directory / file.name, file.model)
        for file in CONFIG_FILES
    }
    return LoadedConfigs(**loaded)  # type: ignore[arg-type]
