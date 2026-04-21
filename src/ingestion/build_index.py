import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def build_faiss_index(
    chunks_path="data/processed/ppm_chunks.txt",
    output_index_path="index/faiss.index",
    output_chunks_path="index/chunks.pkl",
    embedding_model="BAAI/bge-m3",
):
    with open(chunks_path, "r", encoding="utf-8") as chunks_file:
        raw = chunks_file.read()

    documents = [doc for doc in raw.split("\n\n---\n\n") if doc.strip()]

    model = SentenceTransformer(embedding_model)
    embeddings = model.encode(documents, normalize_embeddings=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(np.array(embeddings).astype("float32"))
    faiss.write_index(index, output_index_path)

    with open(output_chunks_path, "wb") as output_file:
        pickle.dump(documents, output_file)

    return {
        "index_path": output_index_path,
        "chunks_path": output_chunks_path,
        "document_count": len(documents),
    }


def main():
    result = build_faiss_index(
        chunks_path="data/processed/ppm_chunks.txt",
        output_index_path="index/faiss.index",
        output_chunks_path="index/chunks.pkl",
        embedding_model="BAAI/bge-m3",
    )
    print(
        "Index built from PPM: "
        f"{result['document_count']} docs -> {result['index_path']}"
    )


if __name__ == "__main__":
    main()
