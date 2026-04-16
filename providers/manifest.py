from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderSelection:
    """Records which provider was selected for a service and why."""

    service: str
    provider: str
    connection_string: str
    healthy: bool
    reason: str


@dataclass
class ProviderManifest:
    """Full resolved provider map for all 13 forgeSDLC infrastructure services."""

    llm: ProviderSelection
    embeddings: ProviderSelection
    vector_store: ProviderSelection
    database: ProviderSelection
    blob_storage: ProviderSelection
    monitoring: ProviderSelection
    experiment: ProviderSelection
    deployment: ProviderSelection
    docs_fetcher: ProviderSelection
    connected_tools: ProviderSelection
    auth: ProviderSelection
    mcp: ProviderSelection
    cache: ProviderSelection

    def all_services(self) -> list[ProviderSelection]:
        return [
            self.llm, self.embeddings, self.vector_store, self.database,
            self.blob_storage, self.monitoring, self.experiment, self.deployment,
            self.docs_fetcher, self.connected_tools, self.auth, self.mcp, self.cache,
        ]