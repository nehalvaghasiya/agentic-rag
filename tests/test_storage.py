"""Vector and knowledge-base persistence regressions."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest
from langchain_core.documents import Document

import backend.storage.kb as kb_module
from backend.config import Settings
from backend.storage import KBStore, VectorStore
from tests.support import ScriptedEmbedder


def test_empty_vector_store_does_not_embed_or_return_results() -> None:
    embedder = ScriptedEmbedder({"query": [1.0, 0.0]})
    store = VectorStore(embedder)

    store.add([])

    assert store.count == 0
    assert store.search("query") == []
    assert embedder.document_calls == []
    assert embedder.query_calls == []


def test_vector_search_orders_scores_limits_results_and_preserves_inputs() -> None:
    embedder = ScriptedEmbedder(
        {
            "alpha": [1.0, 0.0],
            "diagonal": [1.0, 1.0],
            "beta": [0.0, 1.0],
            "query": [1.0, 0.0],
        }
    )
    store = VectorStore(embedder)
    docs = [
        Document(page_content="alpha", metadata={"source": "a.txt"}),
        Document(page_content="diagonal", metadata={"source": "d.txt"}),
        Document(page_content="beta", metadata={"source": "b.txt"}),
    ]
    store.add(docs)

    results = store.search("query", k=2)

    assert [doc.page_content for doc in results] == ["alpha", "diagonal"]
    assert results[0].metadata["similarity_score"] == pytest.approx(1.0)
    assert results[1].metadata["similarity_score"] == pytest.approx(2**-0.5)
    assert all("similarity_score" not in doc.metadata for doc in docs)
    assert embedder.document_calls == [["alpha", "diagonal", "beta"]]
    assert embedder.query_calls == ["query"]


def test_vector_store_save_and_load_round_trip(tmp_path: Path) -> None:
    embedder = ScriptedEmbedder({"alpha": [1.0, 0.0], "query": [1.0, 0.0]})
    store = VectorStore(embedder)
    store.add([Document(page_content="alpha", metadata={"source": "a.txt"})])
    path = tmp_path / "nested" / "vectors.pkl"

    store.save(path)
    loaded = VectorStore.load(path, embedder)

    assert path.exists()
    assert loaded.count == 1
    assert loaded.search("query")[0].page_content == "alpha"


def test_loading_missing_vector_store_returns_empty_store(tmp_path: Path) -> None:
    store = VectorStore.load(
        tmp_path / "missing.pkl",
        ScriptedEmbedder({"query": [1.0, 0.0]}),
    )

    assert store.count == 0
    assert store.search("query") == []


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 20, 12, 0, 0, tzinfo=tz)


@pytest.mark.asyncio
async def test_kb_ids_remain_unique_when_created_at_same_time(
    monkeypatch: pytest.MonkeyPatch,
    kb_store: KBStore,
    settings: Settings,
    upload_file_factory,
) -> None:
    monkeypatch.setattr(kb_module, "datetime", FrozenDateTime)

    first = await kb_store.create(
        "First",
        "offline-embedding",
        [upload_file_factory("first.txt", b"alpha")],
        settings,
    )
    second = await kb_store.create(
        "Second",
        "offline-embedding",
        [upload_file_factory("second.txt", b"beta")],
        settings,
    )

    assert first.id != second.id
    assert re.fullmatch(r"kb_[0-9a-f]{32}", first.id)
    assert re.fullmatch(r"kb_[0-9a-f]{32}", second.id)
    assert (settings.data_dir / "kbs" / first.id / "manifest.json").exists()
    assert (settings.data_dir / "kbs" / second.id / "manifest.json").exists()


@pytest.mark.asyncio
async def test_kb_create_list_and_load_round_trip_uses_temporary_storage(
    kb_store: KBStore,
    settings: Settings,
    upload_file_factory,
) -> None:
    created = await kb_store.create(
        "Knowledge",
        "offline-embedding",
        [upload_file_factory("notes.txt", b"alpha knowledge")],
        settings,
    )

    listed = kb_store.list_all()
    loaded = kb_store.load(created.id, settings)

    assert [kb.id for kb in listed] == [created.id]
    assert listed[0].file_count == 1
    assert listed[0].total_size == len(b"alpha knowledge")
    assert loaded is not None
    manifest, vectors = loaded
    assert manifest.id == created.id
    assert vectors.count == 1
    assert vectors.search("alpha knowledge", k=1)[0].metadata["source"].endswith("notes.txt")
    artifacts = [path for path in settings.data_dir.rglob("*") if path.is_file()]
    assert artifacts
    assert all(path.is_relative_to(settings.data_dir) for path in artifacts)


@pytest.mark.asyncio
async def test_kb_create_rejects_upload_without_filename(
    kb_store: KBStore,
    settings: Settings,
    upload_file_factory,
) -> None:
    with pytest.raises(ValueError, match="must have a filename"):
        await kb_store.create(
            "Invalid",
            "offline-embedding",
            [upload_file_factory(None, b"content")],
            settings,
        )


def test_kb_store_handles_missing_and_invalid_manifests(
    kb_store: KBStore, settings: Settings
) -> None:
    invalid = settings.data_dir / "kbs" / "kb_invalid" / "manifest.json"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("not-json")

    assert kb_store.list_all() == []
    assert kb_store.load("kb_missing", settings) is None
    assert not kb_store.exists("kb_missing")
