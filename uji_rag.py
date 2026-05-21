from src.pipeline import Pipeline

def main():
    # Inisialisasi pipeline
    try:
        # Debug=True diaktifkan agar kita bisa melihat log retrieval dan waktu eksekusi di terminal
        pipeline = Pipeline(debug=True)
    except Exception as e:
        print(f"Gagal memuat Pipeline: {e}")
        return

    # Pertanyaan yang memerlukan referensi data klinis
    query = "Apa regimen lengkap primakuin untuk malaria vivax?"

    print(f"\nPERTANYAAN: {query}")

    # Memanggil langsung metode run_rag. 
    # Berbeda dengan .run(), metode ini hanya melakukan Retrieval + Generation 
    # tanpa menjalankan proses ekstraksi klaim dan verifikasi rule_pediatrics.json.
    #print("\n--- MENJALANKAN RAG (TANPA VERIFIKASI) ---")
    result = pipeline.run_rag(query)

    print("\nJAWABAN RAG (LLM + CONTEXT):")
    #print("=" * 60)
    print(result["rag_response"])
    #print("=" * 60)

    #print(f"\nInfo: Dihasilkan menggunakan {len(result['retrieved_docs'])} potongan dokumen referensi.")

if __name__ == "__main__":
    main()