import re
from src.pipeline import Pipeline

MAX_QUERY_LENGTH = 500  # karakter
FORBIDDEN_PATTERNS = [
    r"ignore previous instructions",
    r"system prompt",
    r"jailbreak",
]

def validate_input(query: str) -> str:
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query terlalu panjang (maks {MAX_QUERY_LENGTH} karakter)")
    
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            raise ValueError("Input mengandung instruksi yang tidak diizinkan")
    
    # Sanitasi dasar
    return query.strip()

def main():
    try:
        pipeline = Pipeline()
    except RuntimeError as exc:
        print(f"Setup error: {exc}")
        return

    while True:
        query = input("\nAsk: ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        try:
            query = validate_input(query)
            result = pipeline.run(query) # Run the full pipeline: LLM -> RAG -> RAG+Rule
        except RuntimeError as exc:
            print(f"Runtime error: {exc}")
            continue

        # print("\nLLM Response:")
        # print(result["llm_response"])

        print("\nRAG Response:")
        print(result["rag_response"])

        print("\nVerified Response:")
        print(result["verified_response"])

if __name__ == "__main__":
    main()
