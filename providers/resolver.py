from __future__ import annotations

import os

import structlog

from orchestrator.constants import LOCAL_DB_URL, MCP_SERVER_PORT
from providers.manifest import ProviderManifest, ProviderSelection

logger = structlog.get_logger()


class ProviderResolver:
    """Resolves 13 infrastructure services from environment variables.

    NEVER raises — every _resolve_* method catches all exceptions and
    returns a valid ProviderSelection with healthy=False on failure.
    Calling resolve_all() with zero env vars set must succeed.
    """

    def resolve_all(self) -> ProviderManifest:
        """Resolve all 13 services. Never raises."""
        return ProviderManifest(
            llm=self._resolve_llm(),
            embeddings=self._resolve_embeddings(),
            vector_store=self._resolve_vector(),
            database=self._resolve_db(),
            blob_storage=self._resolve_blob(),
            monitoring=self._resolve_monitoring(),
            experiment=self._resolve_experiment(),
            deployment=self._resolve_deployment(),
            docs_fetcher=self._resolve_docs(),
            connected_tools=self._resolve_tools(),
            auth=self._resolve_auth(),
            mcp=self._resolve_mcp(),
            cache=self._resolve_cache(),
        )

    def print_table(self) -> None:
        """Print a summary table of all resolved providers."""
        manifest = self.resolve_all()
        print(f"\n{'Service':<22} {'Provider':<28} {'Healthy':<8} {'Reason'}")
        print("-" * 90)
        for sel in manifest.all_services():
            mark = "✓" if sel.healthy else "✗"
            print(f"{sel.service:<22} {sel.provider:<28} {mark:<8} {sel.reason}")
        print()

    # ------------------------------------------------------------------ resolvers

    def _resolve_llm(self) -> ProviderSelection:
        try:
            if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
                return ProviderSelection(
                    service="llm",
                    provider="azure_openai",
                    connection_string=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                    healthy=True,
                    reason="Azure OpenAI configured",
                )
            if os.getenv("OPENAI_API_KEY"):
                return ProviderSelection(
                    service="llm",
                    provider="openai",
                    connection_string="https://api.openai.com/v1",
                    healthy=True,
                    reason="OPENAI_API_KEY set",
                )
            if os.getenv("GROQ_API_KEY"):
                return ProviderSelection(
                    service="llm",
                    provider="groq",
                    connection_string="https://api.groq.com/openai/v1",
                    healthy=True,
                    reason="GROQ_API_KEY set",
                )
            return ProviderSelection(
                service="llm",
                provider="ollama_local",
                connection_string="http://localhost:11434",
                healthy=False,
                reason="No API keys set — Ollama local fallback",
            )
        except Exception as exc:
            return ProviderSelection(
                service="llm",
                provider="none",
                connection_string="",
                healthy=False,
                reason=f"Resolution failed: {exc}",
            )

    def _resolve_embeddings(self) -> ProviderSelection:
        try:
            if os.getenv("AZURE_OPENAI_API_KEY"):
                return ProviderSelection(
                    service="embeddings",
                    provider="azure_openai_embeddings",
                    connection_string=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                    healthy=True,
                    reason="Azure OpenAI configured",
                )
            return ProviderSelection(
                service="embeddings",
                provider="huggingface_local",
                connection_string="all-MiniLM-L6-v2",
                healthy=True,
                reason="Local sentence-transformers (no API key needed)",
            )
        except Exception as exc:
            return ProviderSelection(
                service="embeddings",
                provider="huggingface_local",
                connection_string="all-MiniLM-L6-v2",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_vector(self) -> ProviderSelection:
        try:
            if os.getenv("AZURE_AI_SEARCH_ENDPOINT"):
                return ProviderSelection(
                    service="vector_store",
                    provider="azure_ai_search",
                    connection_string=os.getenv("AZURE_AI_SEARCH_ENDPOINT", ""),
                    healthy=True,
                    reason="Azure AI Search configured",
                )
            return ProviderSelection(
                service="vector_store",
                provider="chromadb_local",
                connection_string="./chroma_db",
                healthy=True,
                reason="ChromaDB local PersistentClient",
            )
        except Exception as exc:
            return ProviderSelection(
                service="vector_store",
                provider="chromadb_local",
                connection_string="./chroma_db",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_db(self) -> ProviderSelection:
        try:
            url = os.getenv("DATABASE_URL", LOCAL_DB_URL)
            if not url.startswith("postgresql"):
                raise ValueError("Must be PostgreSQL")
            return ProviderSelection(
                service="database",
                provider="postgresql",
                connection_string=url,
                healthy=True,
                reason="PostgreSQL configured",
            )
        except Exception as exc:
            return ProviderSelection(
                service="database",
                provider="postgresql_local",
                connection_string=LOCAL_DB_URL,
                healthy=False,
                reason=f"Fallback to local Docker: {exc}",
            )

    def _resolve_blob(self) -> ProviderSelection:
        try:
            if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
                return ProviderSelection(
                    service="blob_storage",
                    provider="azure_blob",
                    connection_string="azure://",
                    healthy=True,
                    reason="Azure Blob Storage configured",
                )
            return ProviderSelection(
                service="blob_storage",
                provider="local_filesystem",
                connection_string="./data",
                healthy=True,
                reason="Local filesystem fallback",
            )
        except Exception as exc:
            return ProviderSelection(
                service="blob_storage",
                provider="local_filesystem",
                connection_string="./data",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_monitoring(self) -> ProviderSelection:
        try:
            if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
                return ProviderSelection(
                    service="monitoring",
                    provider="azure_monitor",
                    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
                    healthy=True,
                    reason="Azure Application Insights configured",
                )
            return ProviderSelection(
                service="monitoring",
                provider="structlog_local",
                connection_string="stderr",
                healthy=True,
                reason="structlog local output",
            )
        except Exception as exc:
            return ProviderSelection(
                service="monitoring",
                provider="structlog_local",
                connection_string="stderr",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_experiment(self) -> ProviderSelection:
        try:
            if os.getenv("AZURE_ML_WORKSPACE"):
                return ProviderSelection(
                    service="experiment",
                    provider="azure_ml",
                    connection_string=os.getenv("AZURE_ML_WORKSPACE", ""),
                    healthy=True,
                    reason="Azure ML configured",
                )
            return ProviderSelection(
                service="experiment",
                provider="mlflow_local",
                connection_string="./mlruns",
                healthy=True,
                reason="MLflow local tracking",
            )
        except Exception as exc:
            return ProviderSelection(
                service="experiment",
                provider="mlflow_local",
                connection_string="./mlruns",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_deployment(self) -> ProviderSelection:
        try:
            if os.getenv("RENDER_API_KEY"):
                return ProviderSelection(
                    service="deployment",
                    provider="render",
                    connection_string="https://api.render.com/v1",
                    healthy=True,
                    reason="Render API key configured",
                )
            return ProviderSelection(
                service="deployment",
                provider="docker_local",
                connection_string="unix:///var/run/docker.sock",
                healthy=False,
                reason="No deployment provider configured — local Docker",
            )
        except Exception as exc:
            return ProviderSelection(
                service="deployment",
                provider="docker_local",
                connection_string="",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_docs(self) -> ProviderSelection:
        try:
            if os.getenv("TAVILY_API_KEY"):
                return ProviderSelection(
                    service="docs_fetcher",
                    provider="tavily",
                    connection_string="https://api.tavily.com",
                    healthy=True,
                    reason="Tavily API key configured",
                )
            return ProviderSelection(
                service="docs_fetcher",
                provider="duckduckgo",
                connection_string="https://duckduckgo.com",
                healthy=True,
                reason="DuckDuckGo free fallback",
            )
        except Exception as exc:
            return ProviderSelection(
                service="docs_fetcher",
                provider="duckduckgo",
                connection_string="https://duckduckgo.com",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_tools(self) -> ProviderSelection:
        try:
            tools: list[str] = []
            if os.getenv("CURSOR_API_KEY") and os.getenv("CURSOR_API_VERIFIED", "false") == "true":
                tools.append("cursor")
            if os.getenv("DEVIN_API_KEY"):
                tools.append("devin")
            tools.append("claude_code_cli")  # detected at runtime
            tools.append("direct_llm")
            return ProviderSelection(
                service="connected_tools",
                provider=",".join(tools),
                connection_string="",
                healthy=True,
                reason=f"Tools available: {tools}",
            )
        except Exception as exc:
            return ProviderSelection(
                service="connected_tools",
                provider="direct_llm",
                connection_string="",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_auth(self) -> ProviderSelection:
        try:
            has_secret = bool(os.getenv("SECRET_KEY"))
            return ProviderSelection(
                service="auth",
                provider="pyjwt_argon2",
                connection_string="",
                healthy=has_secret,
                reason="PyJWT + argon2-cffi" if has_secret else "SECRET_KEY not set",
            )
        except Exception as exc:
            return ProviderSelection(
                service="auth",
                provider="pyjwt_argon2",
                connection_string="",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_mcp(self) -> ProviderSelection:
        try:
            return ProviderSelection(
                service="mcp",
                provider="fastmcp",
                connection_string=f"http://0.0.0.0:{MCP_SERVER_PORT}/mcp",
                healthy=True,
                reason=f"FastMCP on port {MCP_SERVER_PORT}",
            )
        except Exception as exc:
            return ProviderSelection(
                service="mcp",
                provider="fastmcp",
                connection_string="",
                healthy=False,
                reason=f"Fallback: {exc}",
            )

    def _resolve_cache(self) -> ProviderSelection:
        try:
            if os.getenv("REDIS_URL"):
                return ProviderSelection(
                    service="cache",
                    provider="redis",
                    connection_string=os.getenv("REDIS_URL", ""),
                    healthy=True,
                    reason="Redis URL configured",
                )
            return ProviderSelection(
                service="cache",
                provider="in_memory_dict",
                connection_string="",
                healthy=True,
                reason="In-memory dict fallback (no Redis)",
            )
        except Exception as exc:
            return ProviderSelection(
                service="cache",
                provider="in_memory_dict",
                connection_string="",
                healthy=False,
                reason=f"Fallback: {exc}",
            )
