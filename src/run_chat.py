from src.pipeline import Pipeline

def main():
    pipeline = Pipeline()

    while True:
        query = input("\nAsk: ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        result = pipeline.run(query) # Run the full pipeline: LLM -> RAG -> RAG+Rule

        print("\nLLM Response:")
        print(result["llm_response"])

        print("\nRAG Response:")
        print(result["rag_response"])

        print("\nVerified Response:")
        print(result["verified_response"])

if __name__ == "__main__":
    main()
