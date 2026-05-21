import json
from src.pipeline import Pipeline

def main():
    # Inisialisasi pipeline. Debug=False agar terminal tidak terlalu penuh dengan log internal.
    try:
        pipeline = Pipeline(debug=False)
    except Exception as e:
        print(f"Gagal memuat Pipeline: {e}")
        return

    # Pertanyaan tunggal untuk menguji kecerdasan LLM
    query = "Berapa dosis kina dihidroklorid untuk malaria berat pada anak?"

    print(f"\nPERTANYAAN: {query}")
    
    result = pipeline.run(query)

    print("\nJAWABAN LLM:")
    print(f"    {result['llm_response'].strip()}")

if __name__ == "__main__":
    main()