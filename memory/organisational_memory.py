from __future__ import annotations

import asyncio
import functools
import os
from datetime import UTC, datetime

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore[assignment]
import structlog

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:  # pragma: no cover
    HuggingFaceEmbeddings = None  # type: ignore[assignment,misc]

from interpret.record import InterpretRecord
from memory.schemas import OrgMemoryEntry

logger = structlog.get_logger()

# Resolve to absolute path at import time — CWD changes don't affect it
_DEFAULT_CHROMA_PATH = os.path.abspath(os.getenv("FORGESDLC_CHROMA_PATH", "./chroma_db"))

# Shared singleton — the 90 MB model loads once per process
_SHARED_EMBEDDINGS: HuggingFaceEmbeddings | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Return shared HuggingFaceEmbeddings — loaded once, never reloaded."""
    global _SHARED_EMBEDDINGS
    if _SHARED_EMBEDDINGS is None:
        if HuggingFaceEmbeddings is None:
            raise ImportError("langchain-huggingface required: pip install langchain-huggingface")
        cache_folder = os.getenv("TRANSFORMERS_CACHE", os.path.expanduser("~/.cache/huggingface"))
        _SHARED_EMBEDDINGS = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            cache_folder=cache_folder,
        )
        logger.info("org_memory.embeddings_loaded", model="all-MiniLM-L6-v2")
    return _SHARED_EMBEDDINGS


class OrgMemory:
    """Layer 2 memory — learnable facts in ChromaDB.

    Uses PersistentClient so data survives server restarts.
    Embeddings: all-MiniLM-L6-v2 via sentence-transformers (~90MB, cached after
    first download, no API key needed, works fully offline).
    Emits InterpretRecord(layer="memory") before every read and write.
    """

    def __init__(self, chroma_path: str = _DEFAULT_CHROMA_PATH) -> None:

        self._chroma_path = os.path.abspath(chroma_path)
        if chromadb is None:
            raise ImportError(
                "chromadb is required for Layer 2 memory. Install it: pip install chromadb"
            )
        self._client = chromadb.PersistentClient(path=self._chroma_path)
        self._collection = self._client.get_or_create_collection(
            "forgesdlc_org_memory",
            metadata={"hnsw:space": "cosine"},
        )
        # Reuse shared singleton
        self._embeddings = _get_embeddings()
        logger.info(
            "org_memory.init",
            chroma_path=self._chroma_path,
            collection=self._collection.name,
        )

    async def upsert(self, entry: OrgMemoryEntry) -> None:
        """Store a learnable fact. Emits InterpretRecord before write."""
        self._emit_record("write", "upsert", entry.entry_id)
        # Embedding is CPU-bound — run in thread executor to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None,
            functools.partial(self._embeddings.embed_documents, [entry.content]),
        )
        embedding = embedding[0]
        self._collection.upsert(
            ids=[entry.entry_id],
            documents=[entry.content],
            embeddings=[embedding],
            metadatas=[
                {
                    "project_id": entry.project_id,
                    "category": entry.category,
                    "source_run_id": entry.source_run_id,
                    "timestamp": entry.timestamp.isoformat(),
                }
            ],
        )
        logger.info(
            "org_memory.upsert",
            entry_id=entry.entry_id,
            project_id=entry.project_id,
            category=entry.category,
        )

    async def search(self, query: str, project_id: str, limit: int = 10) -> list[OrgMemoryEntry]:
        """Semantic similarity search filtered by project_id.

        Emits InterpretRecord before read.
        Returns empty list if no entries exist for the project.
        """
        self._emit_record("read", "search", query[:50])

        total = self._collection.count()
        if total == 0:
            logger.info("org_memory.search.empty_collection")
            return []

        # ChromaDB raises if n_results exceeds total collection size — cap it first
        # Use min(limit, total) — project filter applied by ChromaDB after candidate fetch.
        # If project has fewer results than n_results, ChromaDB returns what it finds.
        n_results = min(limit, total)

        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None,
            functools.partial(self._embeddings.embed_query, query),
        )
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where={"project_id": project_id},
        )

        entries: list[OrgMemoryEntry] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for entry_id, content, meta, distance in zip(
            ids, documents, metadatas, distances, strict=False
        ):  # noqa: E501
            # Cosine distance → similarity score (0=identical, 2=opposite)
            relevance = max(0.0, 1.0 - (distance / 2.0))
            entries.append(
                OrgMemoryEntry(
                    entry_id=entry_id,
                    project_id=meta["project_id"],
                    content=content,
                    category=meta["category"],  # type: ignore[arg-type]
                    source_run_id=meta["source_run_id"],
                    timestamp=datetime.fromisoformat(meta["timestamp"]),
                    relevance_score=relevance,
                )
            )

        logger.info(
            "org_memory.search",
            query=query[:50],
            project_id=project_id,
            results=len(entries),
        )
        return entries

    def _emit_record(self, action_type: str, action: str, key: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="OrgMemory",
            action=f"{action_type}: {action} — key={key}",
            inputs={"key": key},
            expected_outputs={"entries": "list[OrgMemoryEntry]"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=["chromadb_local"],
            model_selected=None,
            tool_delegated_to=None,
            reversible=(action_type == "read"),
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.memory",
            action=record.action,
            layer=record.layer,
        )
        return record
