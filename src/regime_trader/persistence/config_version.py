from __future__ import annotations

from regime_trader.config.models import AppConfig


class ConfigVersionRepository:
    def __init__(self) -> None:
        self._versions: dict[str, AppConfig] = {}

    def persist(self, config: AppConfig) -> str:
        version = config.version
        self._versions[version] = config
        return version

    def get(self, version: str) -> AppConfig | None:
        return self._versions.get(version)
