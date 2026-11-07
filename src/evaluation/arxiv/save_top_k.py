import csv
from pathlib import Path

from src.retrieval.retriever import Retriever


ROOT_DIR = Path(__file__).resolve().parents[2]
INPUT_CSV = ROOT_DIR / "data" / "rules" / "q_datasets_gpt_oss_120b.csv"
OUTPUT_CSV = ROOT_DIR / "data" / "rules" / "retrieval_top_3_187.csv"
TOP_K = 3


def main() -> None:
    with INPUT_CSV.open(encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file, delimiter=";")
        required_columns = {"id", "question", "llm_rag_response"}
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError(
                "Input CSV must contain 'id', 'question', and 'llm_rag_response' "
                f"columns: {INPUT_CSV}"
            )

        queries = [
            (
                row["id"].strip(),
                row["question"].strip(),
                row["llm_rag_response"] or "",
            )
            for row in reader
            if (row.get("id") or "").strip() and (row.get("question") or "").strip()
        ]

    if not queries:
        raise ValueError(f"No query rows found in {INPUT_CSV}")

    fieldnames = ["id", "question"]
    for rank in range(1, TOP_K + 1):
        fieldnames.extend([f"top_{rank}_document", f"top_{rank}_score"])
    fieldnames.append("llm_rag_response")

    retriever = Retriever(
        index_path=str(ROOT_DIR / "index" / "faiss.index"),
        chunks_path=str(ROOT_DIR / "index" / "chunks.pkl"),
    )

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()

        for query_id, question, rag_response in queries:
            documents, scores = retriever.search(question, top_k=TOP_K)
            score_values = scores[0].tolist() if len(scores) else []
            result_row = {
                "id": query_id,
                "question": question,
                "llm_rag_response": rag_response,
            }

            for index in range(TOP_K):
                document_key = f"top_{index + 1}_document"
                score_key = f"top_{index + 1}_score"
                result_row[document_key] = (
                    documents[index] if index < len(documents) else ""
                )
                result_row[score_key] = (
                    score_values[index] if index < len(score_values) else ""
                )

            writer.writerow(result_row)

    print(f"Saved top-{TOP_K} retrieval results for {len(queries)} queries to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()