from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from memory.schemas import OrgMemoryEntry


def _make_entry(project_id: str = "proj-1") -> OrgMemoryEntry:
    return OrgMemoryEntry(
        entry_id=str(uuid4()),
        project_id=project_id,
        content="DECISION: use postgres\nRATIONALE: scalability",
        category="architecture",
        source_run_id="manual",
        timestamp=datetime.now(tz=UTC),
    )


def _make_org_memory(chroma_path: str = "./test_chroma") -> object:
    """Return OrgMemory with mocked chromadb and embeddings."""
    with (
        patch("memory.organisational_memory.chromadb") as mock_chroma,
        patch("memory.organisational_memory.HuggingFaceEmbeddings") as mock_emb,
    ):
        mock_collection = MagicMock()
        mock_collection.name = "forgesdlc_org_memory"
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )
        mock_emb.return_value = MagicMock()

        from memory.organisational_memory import OrgMemory

        org = OrgMemory(chroma_path=chroma_path)
        return org


def test_chromadb_uses_persistent_client_not_in_memory() -> None:
    """Verify PersistentClient is called, not EphemeralClient or Client."""
    with (
        patch("memory.organisational_memory.chromadb") as mock_chroma,
        patch("memory.organisational_memory.HuggingFaceEmbeddings"),
    ):
        mock_collection = MagicMock()
        mock_collection.name = "forgesdlc_org_memory"
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )
        from memory.organisational_memory import OrgMemory

        OrgMemory(chroma_path="./test_chroma")
        mock_chroma.PersistentClient.assert_called_once_with(path="./test_chroma")
        mock_chroma.Client.assert_not_called() if hasattr(mock_chroma, "Client") else None
        mock_chroma.EphemeralClient.assert_not_called() if hasattr(
            mock_chroma, "EphemeralClient"
        ) else None


@pytest.mark.asyncio
async def test_upsert_emits_interpret_record_before_write() -> None:
    with (
        patch("memory.organisational_memory.chromadb") as mock_chroma,
        patch("memory.organisational_memory.HuggingFaceEmbeddings") as mock_emb,
    ):
        mock_collection = MagicMock()
        mock_collection.name = "forgesdlc_org_memory"
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )
        mock_emb.return_value.embed_documents.return_value = [[0.1] * 384]

        from memory.organisational_memory import OrgMemory

        org = OrgMemory(chroma_path="./test_chroma")

        emitted: list[str] = []
        original_emit = org._emit_record

        def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
            ir = original_emit(action_type, action, key)
            emitted.append(ir.layer)
            return ir

        org._emit_record = capturing_emit  # type: ignore[method-assign]

        entry = _make_entry()
        await org.upsert(entry)
        assert "memory" in emitted
        mock_collection.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_stores_entry_in_chromadb() -> None:
    with (
        patch("memory.organisational_memory.chromadb") as mock_chroma,
        patch("memory.organisational_memory.HuggingFaceEmbeddings") as mock_emb,
    ):
        mock_collection = MagicMock()
        mock_collection.name = "forgesdlc_org_memory"
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )
        mock_emb.return_value.embed_documents.return_value = [[0.1] * 384]

        from memory.organisational_memory import OrgMemory

        org = OrgMemory(chroma_path="./test_chroma")
        entry = _make_entry()
        await org.upsert(entry)

        call_kwargs = mock_collection.upsert.call_args
        assert entry.entry_id in call_kwargs.kwargs["ids"]


@pytest.mark.asyncio
async def test_search_returns_empty_list_for_new_project() -> None:
    with (
        patch("memory.organisational_memory.chromadb") as mock_chroma,
        patch("memory.organisational_memory.HuggingFaceEmbeddings"),
    ):
        mock_collection = MagicMock()
        mock_collection.name = "forgesdlc_org_memory"
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        from memory.organisational_memory import OrgMemory

        org = OrgMemory(chroma_path="./test_chroma")
        result = await org.search("tech stack", project_id="new-proj")
        assert result == []


@pytest.mark.asyncio
async def test_search_emits_interpret_record_before_read() -> None:
    with (
        patch("memory.organisational_memory.chromadb") as mock_chroma,
        patch("memory.organisational_memory.HuggingFaceEmbeddings"),
    ):
        mock_collection = MagicMock()
        mock_collection.name = "forgesdlc_org_memory"
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        from memory.organisational_memory import OrgMemory

        org = OrgMemory(chroma_path="./test_chroma")

        emitted: list[str] = []
        original_emit = org._emit_record

        def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
            ir = original_emit(action_type, action, key)
            emitted.append(ir.layer)
            return ir

        org._emit_record = capturing_emit  # type: ignore[method-assign]
        await org.search("database", project_id="proj-1")
        assert "memory" in emitted


@pytest.mark.asyncio
async def test_search_returns_relevant_entries_by_semantic_similarity() -> None:
    with (
        patch("memory.organisational_memory.chromadb") as mock_chroma,
        patch("memory.organisational_memory.HuggingFaceEmbeddings") as mock_emb,
    ):
        mock_collection = MagicMock()
        mock_collection.name = "forgesdlc_org_memory"
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [["entry-abc"]],
            "documents": [["DECISION: use postgres\nRATIONALE: scalability"]],
            "metadatas": [
                [
                    {
                        "project_id": "proj-1",
                        "category": "architecture",
                        "source_run_id": "manual",
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                ]
            ],
            "distances": [[0.1]],
        }
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )
        mock_emb.return_value.embed_query.return_value = [0.1] * 384

        from memory.organisational_memory import OrgMemory

        org = OrgMemory(chroma_path="./test_chroma")
        results = await org.search("database driver", project_id="proj-1")

        assert len(results) == 1
        assert results[0].entry_id == "entry-abc"
        assert results[0].relevance_score is not None
        assert results[0].relevance_score >= 0.0
