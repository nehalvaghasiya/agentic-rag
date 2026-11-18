"""Actual RAGBench schema adapter, tested with synthetic records (not claimed real HF data)."""

import json

import pytest

from agentic_rag.eval.hf import HFEvaluator


async def test_ragbench_workflow_and_proxy_warning(runtime, tmp_path) -> None:
    source = tmp_path / "ragbench_like.jsonl"
    source.write_text(
        json.dumps(
            {
                "id": "sample",
                "question": "Which planet has rings?",
                "documents": ["Saturn has rings made of icy debris."],
                "answer": "Saturn",
                "label_adherence": True,
            }
        )
        + "\n"
    )
    report = await HFEvaluator(runtime).run(source)
    assert [r["mode"] for r in report["rows"]] == ["baseline", "advanced", "agentic"]
    assert report["modes"]["agentic"]["cases"] == 1
    assert all(r["reference_is_ground_truth"] is False for r in report["rows"])
    assert "not a gold answer" in report["label_warning"]


async def test_ragbench_rejects_bad_schema(runtime, tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({"question": "what", "documents": "not a list"}) + "\n")
    with pytest.raises(ValueError, match="list"):
        await HFEvaluator(runtime).run(path)


async def test_missing_ragbench_data_fails_cleanly(runtime, tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="Download"):
        await HFEvaluator(runtime).run(tmp_path / "missing.jsonl")
