from __future__ import annotations

from datetime import datetime, timezone

import chromadb
import structlog
from langchain_huggingface import HuggingFaceEmbeddings

from interpret.record import InterpretRecord
from memory.schemas import OrgMemoryEntry

logger = structlog.get_logger()


class OrgMemory:
    """Layer 2 memory — learnable facts in ChromaDB.

    Uses PersistentClient so data survives server restarts.
    Embeddings: all-MiniLM-L6-v2 via sentence-transformers (~90MB, cached after
    first download, no API key needed, works fully offline).
    Emits InterpretRecord(layer="memory") before every read and write.
    """

    def __init__(self, chroma_path: str = "./chroma_db") -> None:
        # PersistentClient — data written to disk, survives process restarts.
        # Never use chromadb.Client() / EphemeralClient() — loses data on exit.
        self._client = chromadb.PersistentClient(path=chroma_path)
        self._collection = self._client.get_or_create_collection(
            "forgesdlc_org_memory",
            metadata={"hnsw:space": "cosine"},
        )
        # Model downloads ~90MB on first run, cached to ~/.cache/huggingface/
        self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        logger.info(
            "org_memory.init",
            chroma_path=chroma_path,
            collection=self._collection.name,
        )

    async def upsert(self, entry: OrgMemoryEntry) -> None:
        """Store a learnable fact. Emits InterpretRecord before write."""
        self._emit_record("write", "upsert", entry.entry_id)
        embedding = self._embeddings.embed_documents([entry.content])[0]
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

    async def search(
        self, query: str, project_id: str, limit: int = 10
    ) -> list[OrgMemoryEntry]:
        """Semantic similarity search filtered by project_id.

        Emits InterpretRecord before read.
        Returns empty list if no entries exist for the project.
        """
        self._emit_record("read", "search", query[:50])

        # Guard: if collection is empty, return early
        if self._collection.count() == 0:
            logger.info("org_memory.search.empty_collection")
            return []

        embedding = self._embeddings.embed_query(query)
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(limit, self._collection.count()),
            where={"project_id": project_id},
        )

        entries: list[OrgMemoryEntry] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for entry_id, content, meta, distance in zip(
            ids, documents, metadatas, distances
        ):
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
            timestamp=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "interpret_record.memory",
            action=record.action,
            layer=record.layer,
        )
        return record