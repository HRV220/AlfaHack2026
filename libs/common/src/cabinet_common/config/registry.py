"""Все конфиги каталога: загрузка при старте и версии для снимков (REC-08)."""

from dataclasses import dataclass
from pathlib import Path

from cabinet_common.config.eligibility import EligibilityConfig
from cabinet_common.config.goal_fit import GoalFitConfig
from cabinet_common.config.loader import LoadedConfig, load_config
from cabinet_common.config.okved import OkvedGroupsConfig
from cabinet_common.config.products import ProductsConfig
from cabinet_common.config.ranking import RankingWeightsConfig, ThresholdsConfig
from cabinet_common.config.reason_codes import ReasonCodesConfig


@dataclass(frozen=True)
class ConfigFile:
    name: str
    versions_key: str | None  # поле `ConfigVersions` контракта; None — в снимок не попадает


CONFIG_FILES = (
    ConfigFile("products.yaml", "catalog"),
    ConfigFile("goal_fit.yaml", "goal_fit"),
    ConfigFile("eligibility.yaml", None),
    ConfigFile("ranking_weights.yaml", "weights"),
    ConfigFile("thresholds.yaml", "grades"),
    ConfigFile("reason_codes.yaml", "reason_codes"),
    ConfigFile("okved_groups.yaml", None),
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
        return {
            "catalog": self.products.version,
            "goal_fit": self.goal_fit.version,
            "grades": self.thresholds.version,
            "weights": self.ranking_weights.version,
            "reason_codes": self.reason_codes.version,
        }


def load_all_configs(config_dir: Path | str) -> LoadedConfigs:
    """Читает и проверяет схемами все файлы каталога конфигов; любая ошибка — `ConfigError`."""
    directory = Path(config_dir)
    return LoadedConfigs(
        products=load_config(directory / "products.yaml", ProductsConfig),
        goal_fit=load_config(directory / "goal_fit.yaml", GoalFitConfig),
        eligibility=load_config(directory / "eligibility.yaml", EligibilityConfig),
        ranking_weights=load_config(directory / "ranking_weights.yaml", RankingWeightsConfig),
        thresholds=load_config(directory / "thresholds.yaml", ThresholdsConfig),
        reason_codes=load_config(directory / "reason_codes.yaml", ReasonCodesConfig),
        okved_groups=load_config(directory / "okved_groups.yaml", OkvedGroupsConfig),
    )
