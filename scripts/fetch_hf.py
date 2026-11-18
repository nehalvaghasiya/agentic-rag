"""Fetch a small real Hugging Face RAGBench sample for external evaluation.

Requires internet and optional `datasets` group. This is not the synthetic CI corpus.
The model response and supplied documents are benchmark records; re-ingest those
passages and re-generate answers for a true system comparison.
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", type=Path, default=Path("datasets/golden/ragbench_50.jsonl"))
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    from datasets import load_dataset

    ds = load_dataset("galileo-ai/ragbench", "covidqa", split=f"test[:{args.limit}]")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for i, row in enumerate(ds):
            docs = row.get("documents") or []
            record = {
                "id": f"ragbench_{i:04}",
                "question": row["question"],
                "answer": row["response"],
                "documents": docs,
                "label_adherence": row.get("adherence_score"),
                "source": "galileo-ai/ragbench:covidqa:test",
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Downloaded {len(ds)} published RAGBench rows into {args.out}")


if __name__ == "__main__":
    main()
