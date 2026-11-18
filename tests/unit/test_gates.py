"""Regression CI controls refuse silent missing metrics."""

from agentic_rag.eval.gate import Gate


def test_missing_faithfulness_never_passes_gate() -> None:
    gate = Gate({"retrieval_recall": 0.7, "judge_faithfulness": 0.8})
    assert gate.check({"retrieval_recall": 0.9, "judge_faithfulness": None}) == {
        "retrieval_recall": True,
        "judge_faithfulness": False,
    }
    assert gate.exit_code({"retrieval_recall": 0.9}) == 1


def test_passing_gate() -> None:
    gate = Gate({"retrieval_recall": 0.6})
    assert gate.exit_code({"retrieval_recall": 0.8}) == 0
