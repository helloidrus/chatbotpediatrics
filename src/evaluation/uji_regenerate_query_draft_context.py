import csv
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
INPUT_CSV = ROOT_DIR / "data" / "rules" / "retrieval_top_3_187.csv"
OUTPUT_CSV = ROOT_DIR / "data" / "rules" / "hasil_regenerate_query_draft_context.csv"
BATCH_SIZE = 5

REQUIRED_COLUMNS = {
    "id",
    "question",
    "top_1_document",
    "top_2_document",
    "top_3_document",
    "llm_rag_response",
}


def build_user_prompt(
    query: str,
    contexts: list[str],
    draft_response: str,
) -> str:
    context_text = "\n\n".join(
        f"Context {index}:\n{context or '[Tidak tersedia]'}"
        for index, context in enumerate(contexts, start=1)
    )
    return f"""
Question:
{query}

Retrieved contexts:
{context_text}

Previous answer (draft):
{draft_response}

Review the numeric values (dose, frequency, duration, and interval) in the
previous answer against the retrieved contexts, and correct those that the
contexts do not support. Do not add information that is not in the contexts.
Rewrite the final answer in Indonesian. Without explaining the verification process.
"""


def main() -> None:
    with INPUT_CSV.open(encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file, delimiter=";")
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(
                f"Input CSV must contain these columns: {', '.join(sorted(REQUIRED_COLUMNS))}"
            )

        input_columns = reader.fieldnames
        rows = [
            row
            for row in reader
            if (row.get("id") or "").strip() and (row.get("question") or "").strip()
        ]

    if not rows:
        raise ValueError(f"No query rows found in {INPUT_CSV}")

    output_columns = [*input_columns, "regenerated_response"]
    completed_ids: set[str] = set()

    if OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0:
        with OUTPUT_CSV.open(encoding="utf-8-sig", newline="") as output_file:
            output_reader = csv.DictReader(output_file, delimiter=";")
            if output_reader.fieldnames != output_columns:
                raise ValueError(
                    f"Output CSV has unexpected columns: {OUTPUT_CSV}"
                )
            for output_row in output_reader:
                query_id = (output_row.get("id") or "").strip()
                if not query_id or not (output_row.get("regenerated_response") or "").strip():
                    raise ValueError(
                        f"Output CSV contains a row without an ID or regenerated response: "
                        f"{OUTPUT_CSV}"
                    )
                if query_id in completed_ids:
                    raise ValueError(
                        f"Output CSV contains duplicate query ID {query_id}: {OUTPUT_CSV}"
                    )
                completed_ids.add(query_id)

    source_ids = {row["id"].strip() for row in rows}
    unexpected_ids = completed_ids - source_ids
    if unexpected_ids:
        raise ValueError(
            f"Output CSV contains IDs not found in the input: {', '.join(sorted(unexpected_ids))}"
        )

    pending_rows = [
        row for row in rows if row["id"].strip() not in completed_ids
    ][:BATCH_SIZE]
    if not pending_rows:
        print(f"All {len(rows)} queries have already been processed.")
        return

    from src.llm.generator import Generator

    generator = Generator()
    file_exists = OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0

    with OUTPUT_CSV.open(
        "a" if file_exists else "w",
        encoding="utf-8-sig",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(output_file, fieldnames=output_columns, delimiter=";")
        if not file_exists:
            writer.writeheader()

        for index, row in enumerate(pending_rows, start=1):
            contexts = [
                row["top_1_document"] or "",
                row["top_2_document"] or "",
                row["top_3_document"] or "",
            ]
            regenerated_response = generator._chat(
                system_prompt=(
                    "You are a pediatric clinical editor. "
                     "Correct the answer to comply with the guidelines using the minimal necessary changes."
                ),
                user_prompt=build_user_prompt(
                    query=row["question"],
                    contexts=contexts,
                    draft_response=row["llm_rag_response"] or "",
                ),
                temperature=0,
            )
            if not (regenerated_response or "").strip():
                raise RuntimeError(
                    f"Generator returned an empty response for query {row['id']}"
                )
            writer.writerow({**row, "regenerated_response": regenerated_response})
            output_file.flush()
            print(f"Processed {index}/{len(pending_rows)} in this run: {row['id']}")

    print(f"Saved this batch to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
